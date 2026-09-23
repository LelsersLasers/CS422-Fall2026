#!/usr/bin/env python3
"""Execute a single iPerf3 throughput test against a server.

This module contains the main test execution flow:
  1. Open control connection and complete protocol handshake
  2. Open data connection (with optional congestion algorithm)
  3. Send data in a non-blocking loop, sampling TCP stats periodically
  4. Signal test end and exchange JSON results with the server
  5. Return samples, bytes sent, algorithm name, and server results

The protocol uses two TCP connections:
  - Control: JSON-based parameter exchange and state machine progression
  - Data: The actual TCP throughput test (repeatedly send random payload)
"""

import math
import os
import select
import socket
import struct
import time
import uuid
from typing import Optional

from protocol import (
    ProtocolError,
    generate_cookie,
    send_json,
    recv_json,
    read_state,
    expect,
    send_state,
    PARAM_EXCHANGE,
    CREATE_STREAMS,
    TEST_START,
    TEST_RUNNING,
    TEST_END,
    EXCHANGE_RESULTS,
    DISPLAY_RESULTS,
    IPERF_DONE,
)
from tcp_stats import get_tcp_info, get_congestion_algo, compute_sample


def run_test(
    host: str,
    port: int,
    duration: float,
    interval: float,
    timeout: float,
    block_size: int,
    run_id: str,
    provider: str,
    country: str,
    algorithm: Optional[str] = None,
) -> tuple[list[dict], int, str, dict]:
    """Run one iPerf3 throughput test against the given server.

    Protocol sequence:
        1. Control connect -> send cookie -> expect PARAM_EXCHANGE
        2. Send client JSON params -> expect CREATE_STREAMS
        3. Data connect -> (set congestion algo) -> send cookie
        4. Expect TEST_START -> expect TEST_RUNNING
        5. Main send loop:
           - Multiplex control (read) and data (write) via select()
           - Send block_size bytes of random data repeatedly
           - Sample TCP stats every `interval` seconds
        6. After duration: send TEST_END -> expect EXCHANGE_RESULTS
        7. Send client results JSON -> receive server results JSON
        8. Send DISPLAY_RESULTS -> send IPERF_DONE -> close both sockets

    Args:
        host: Server hostname or IP.
        port: Server port number.
        duration: Test duration in seconds.
        interval: Sampling interval in seconds.
        timeout: Connection/read timeout in seconds.
        block_size: Size of each data send block (1..1MB).
        run_id: Unique hex identifier for this run.
        provider: Server provider name (for CSV output).
        country: Server country code (for CSV output).
        algorithm: Optional TCP congestion algorithm (e.g., "bbr", "reno").

    Returns:
        Tuple of (samples, bytes_sent, actual_algo, server_result).
        - samples: List of CSV row dicts from compute_sample().
        - bytes_sent: Total bytes sent on the data connection.
        - actual_algo: Actual congestion algorithm used.
        - server_result: JSON dict returned by the server.

    Raises:
        ProtocolError: On protocol mismatch, connection closed, or timeout.
        OSError: On connection failure.
    """
    cookie = generate_cookie()
    control = None
    data = None
    samples: list[dict] = []
    bytes_sent = 0
    server_result: dict = {}

    try:
        # ---------------------------------------------------------------
        # Phase 1: Control connection and parameter exchange
        # ---------------------------------------------------------------
        control = socket.create_connection(
            (host, port), timeout=timeout
        )
        control.settimeout(timeout)

        # Send 37-byte cookie to identify this session.
        control.sendall(cookie)

        # Server responds with PARAM_EXCHANGE to indicate it is ready
        # to receive client JSON parameters.
        expect(control, PARAM_EXCHANGE)

        # Send client parameters: TCP mode, test duration, 1 parallel
        # stream, block size, and client version string.
        send_json(
            control,
            {
                'tcp': True,
                'omit': 0,
                'time': math.ceil(duration),
                'parallel': 1,
                'len': block_size,
                'client_version': '3.0',
            },
        )

        # Server responds with CREATE_STREAMS to indicate parameters
        # were accepted and the client should now open the data socket.
        expect(control, CREATE_STREAMS)

        # ---------------------------------------------------------------
        # Phase 2: Data connection setup
        # ---------------------------------------------------------------
        data = socket.socket(control.family, socket.SOCK_STREAM)

        # Optionally set the congestion control algorithm.
        if algorithm:
            data.setsockopt(
                socket.IPPROTO_TCP, socket.TCP_CONGESTION, algorithm.encode()
            )

        data.settimeout(timeout)
        data.connect(control.getpeername())

        # Data connection also requires the cookie for association.
        data.sendall(cookie)

        # Query the actual congestion algorithm in use.
        actual_algo = get_congestion_algo(data)

        # ---------------------------------------------------------------
        # Phase 3: Test start and data send loop
        # ---------------------------------------------------------------
        expect(control, TEST_START)
        expect(control, TEST_RUNNING)

        # Switch data socket to non-blocking for the send loop.
        data.setblocking(False)

        # Pre-generate the random payload buffer.
        payload = os.urandom(block_size)

        start = time.monotonic()
        last_t = start
        last_ack = get_tcp_info(data)['bytes_acked']
        next_sample = start + interval
        end = start + duration

        # Use memoryview for efficient slicing during repeated sends.
        pending = memoryview(payload)

        while True:
            now = time.monotonic()
            if now >= end:
                break

            # Periodically sample TCP stats and compute goodput.
            if now >= next_sample:
                stats = get_tcp_info(data)
                server_info = {
                    'host': host,
                    'port': port,
                    'provider': provider,
                    'country': country,
                }
                row, last_t, last_ack = compute_sample(
                    now, start, last_t, last_ack,
                    stats, server_info, run_id, actual_algo, bytes_sent,
                )
                samples.append(row)
                next_sample += interval
                continue

            # Multiplex: read from control socket, write to data socket.
            # This allows us to detect server-initiated state changes
            # while continuously sending data.
            sel_timeout = min(next_sample, end) - now
            readable, writable, _ = select.select(
                [control], [data], [], sel_timeout
            )

            if readable:
                # Server sent an unexpected state during transmission.
                state = read_state(control)
                raise ProtocolError(
                    f"Server ended test during transmission (state {state})"
                )

            if writable:
                try:
                    count = data.send(pending)
                    if count == 0:
                        raise ProtocolError(
                            "Data connection closed during send"
                        )
                    bytes_sent += count
                    pending = pending[count:]
                    # Reset buffer when fully sent.
                    if not pending:
                        pending = memoryview(payload)
                except (BlockingIOError, InterruptedError):
                    # Non-blocking send would block — expected behavior.
                    pass

        # Final sample after the send loop ends.
        now = time.monotonic()
        if now > last_t:
            stats = get_tcp_info(data)
            server_info = {
                'host': host,
                'port': port,
                'provider': provider,
                'country': country,
            }
            row, last_t, last_ack = compute_sample(
                now, start, last_t, last_ack,
                stats, server_info, run_id, actual_algo, bytes_sent,
            )
            samples.append(row)

        # ---------------------------------------------------------------
        # Phase 4: Test end and results exchange
        # ---------------------------------------------------------------
        # Signal the server that the client-side test is complete.
        send_state(control, TEST_END)

        # Server responds with EXCHANGE_RESULTS, inviting JSON exchange.
        expect(control, EXCHANGE_RESULTS)

        # Send client-side results to the server.
        stats = get_tcp_info(data)
        stream = {
            'id': 1,
            'bytes': bytes_sent,
            'retransmits': stats['total_retrans'],
            'jitter': 0,
            'errors': 0,
            'packets': 0,
        }
        send_json(
            control,
            {
                'cpu_util_total': 0.0,
                'cpu_util_user': 0.0,
                'cpu_util_system': 0.0,
                'sender_has_retransmits': 1,
                'congestion_used': actual_algo,
                'streams': [stream],
            },
        )

        # Receive server-side results JSON.
        server_result = recv_json(control)

        # Progress state machine to completion.
        expect(control, DISPLAY_RESULTS)
        send_state(control, IPERF_DONE)

        return samples, bytes_sent, actual_algo, server_result

    finally:
        # Always close both sockets, even on exception.
        if data:
            data.close()
        if control:
            control.close()

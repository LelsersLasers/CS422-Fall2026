"""iPerf3 wire protocol implementation.

This module implements the binary protocol used to communicate with iperf3 servers.
The protocol uses two TCP connections:

  - Control connection: JSON-based parameter exchange and state machine progression.
  - Data connection: The actual TCP throughput test.

Protocol state constants are single bytes exchanged on the control socket:
  PARAM_EXCHANGE (9)   - Server ready for client JSON parameters
  CREATE_STREAMS (10)  - Parameters accepted, open data connection
  TEST_START (1)       - Test is beginning
  TEST_RUNNING (2)     - Test is live, client should send data
  EXCHANGE_RESULTS (13)- Test over, exchange JSON results
  DISPLAY_RESULTS (14) - Results received, display phase
  IPERF_DONE (16)      - All done, close connection

Error states:
  ACCESS_DENIED (-1)   - Server rejected the test
  SERVER_ERROR (-2)    - Server internal error
  SERVER_TERMINATE (11)- Server terminated the test early
"""

import json
import os
import select
import struct
import socket
from typing import Optional

# --- iPerf3 protocol state constants (single bytes on control socket) ---

# Normal protocol progression
PARAM_EXCHANGE = 9
CREATE_STREAMS = 10
TEST_START = 1
TEST_RUNNING = 2
TEST_END = 4
EXCHANGE_RESULTS = 13
DISPLAY_RESULTS = 14
IPERF_DONE = 16

# Error states (server rejects or fails)
ACCESS_DENIED = -1
SERVER_ERROR = -2
SERVER_TERMINATE = 11


class ProtocolError(Exception):
    """Raised when the server returns an error state or unexpected protocol byte.

    This covers:
      - Server sends ACCESS_DENIED, SERVER_ERROR, or SERVER_TERMINATE
      - Server sends an unexpected state byte (protocol mismatch)
      - Server closes connection prematurely (Unexpected EOF)
      - Invalid JSON length in length-prefixed messages
    """
    pass


def generate_cookie() -> bytes:
    """Generate a 37-byte random cookie required by the iPerf3 protocol.

    The cookie must match the format used by real iperf3 (see
    ``make_cookie()`` in iperf_util.c): 36 random characters drawn from the
    alphabet ``abcdefghijklmnopqrstuvwxyz234567`` followed by a single
    NUL byte, for a total of 37 bytes on the wire.

    Server versions that predate the 3.14 cookie relaxation validate the
    cookie character-for-character against this alphabet (and treat the
    cookie as a NUL-terminated C string), so deviating from it causes the
    server to reject the session and close the control connection after the
    data-socket cookie is received.

    Returns:
        37 bytes: 36 alphabet characters + 1 NUL byte (0x00).
    """
    alphabet = b'abcdefghijklmnopqrstuvwxyz234567'
    cookie = bytes(alphabet[b % 32] for b in os.urandom(36)) + b'\x00'
    assert len(cookie) == 37, f"Cookie must be 37 bytes, got {len(cookie)}"
    return cookie


def recv_exact(sock: socket.socket, n: int, timeout: Optional[float] = None) -> bytes:
    """Read exactly n bytes from a socket, with timeout support.

    Uses select() to wait for data with the specified timeout, preventing
    indefinite blocking when the server is unresponsive.

    Args:
        sock: Connected TCP socket.
        n: Exact number of bytes to read.
        timeout: Maximum seconds to wait for data. If None, uses the socket's
                 default timeout.

    Returns:
        Exactly n bytes.

    Raises:
        TimeoutError: If the socket does not send data within the timeout.
        ProtocolError: If the server closes the connection before n bytes are read.
    """
    out = bytearray()
    while len(out) < n:
        remaining = n - len(out)

        # Use select to wait for data with a timeout, so we don't block forever.
        if timeout is not None:
            readable, _, _ = select.select([sock], [], [], timeout)
            if not readable:
                raise TimeoutError(
                    f"timed out waiting for {remaining} byte(s) "
                    f"(only received {len(out)}/{n})"
                )

        chunk = sock.recv(remaining)
        if not chunk:
            raise ProtocolError(
                f"Unexpected EOF: needed {n}, got {len(out)}"
            )
        out.extend(chunk)

    return bytes(out)


def send_json(sock: socket.socket, obj: dict) -> None:
    """Send a length-prefixed JSON message over the control socket.

    Format: 4-byte big-endian length + compact JSON payload (no whitespace).

    Args:
        sock: Connected control socket.
        obj: Python dict to serialize and send.
    """
    # Compact JSON with no spaces to match iperf3 wire format.
    payload = json.dumps(obj, separators=(',', ':')).encode('utf-8')
    # 4-byte big-endian length header + payload.
    sock.sendall(struct.pack('!I', len(payload)) + payload)


def recv_json(sock: socket.socket, timeout: Optional[float] = None) -> dict:
    """Receive a length-prefixed JSON message from the control socket.

    Args:
        sock: Connected control socket.
        timeout: Timeout for recv_exact calls.

    Returns:
        Parsed JSON dict from the server.

    Raises:
        ProtocolError: If the length field is invalid (> 16 MB).
    """
    size = struct.unpack('!I', recv_exact(sock, 4, timeout=timeout))[0]
    if not 0 < size <= 16 * 1024 * 1024:
        raise ProtocolError(f"Invalid JSON length {size}")
    return json.loads(recv_exact(sock, size, timeout=timeout))


def read_state(sock: socket.socket, timeout: Optional[float] = None) -> int:
    """Read one state byte from the control socket.

    Args:
        sock: Connected control socket.
        timeout: Timeout for reading.

    Returns:
        State byte as a signed integer.

    Raises:
        ProtocolError: If the state is ACCESS_DENIED, SERVER_ERROR, or
                       SERVER_TERMINATE.
    """
    state = struct.unpack('b', recv_exact(sock, 1, timeout=timeout))[0]

    if state == ACCESS_DENIED:
        raise ProtocolError("Server busy / access denied")
    if state == SERVER_TERMINATE:
        raise ProtocolError("Server terminated test")
    if state == SERVER_ERROR:
        # Server error includes two 4-byte integers: error code and Unix errno.
        err, unix = struct.unpack('!ii', recv_exact(sock, 8, timeout=timeout))
        raise ProtocolError(f"iperf3 server error {err}, errno {unix}")

    return state


def expect(sock: socket.socket, expected: int, timeout: Optional[float] = None) -> int:
    """Read a state byte and assert it matches the expected protocol phase.

    This is the primary way to progress through the iPerf3 state machine.
    After each client action, the server responds with a state byte indicating
    the next phase.

    Args:
        sock: Connected control socket.
        expected: The state byte we expect at this point in the protocol.
        timeout: Timeout for reading.

    Returns:
        The state byte (same as expected on success).

    Raises:
        ProtocolError: If the actual state byte does not match expected, or
                       if the server returns an error state.
    """
    actual = read_state(sock, timeout=timeout)
    if actual != expected:
        raise ProtocolError(
            f"Expected iperf3 state {expected}, got {actual}"
        )
    return actual


def send_state(sock: socket.socket, state: int) -> None:
    """Send a single state byte on the control socket.

    Used to send TEST_END and IPERF_DONE to signal protocol completion.

    Args:
        sock: Connected control socket.
        state: Single-byte state value to send.
    """
    sock.sendall(struct.pack('b', state))

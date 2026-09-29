"""TCP socket statistics extraction and goodput computation.

This module provides utilities for reading TCP_INFO from the Linux kernel
via getsockopt() and computing goodput (acknowledged throughput) from
the tcpi_bytes_acked field.

The TCP_INFO struct layout is defined in include/uapi/linux/tcp.h.
We read specific fields using native-endian unpacking since the kernel
returns the struct in the process's native byte order.
"""

import struct
import socket

# Socket option constant for TCP_INFO (Linux-specific).
TCP_INFO = getattr(socket, 'TCP_INFO', 11)

# Byte offset of tcpi_bytes_acked in struct tcp_info.
# This field tracks the cumulative number of data bytes acknowledged by
# the remote receiver — the basis for our goodput measurement.
BYTES_ACKED_OFFSET = 120

# CSV column names for output files.
CSV_FIELDS = [
    'run_id', 'host', 'port', 'provider', 'country', 'algorithm',
    'elapsed_s', 'interval_s',
    'bytes_acked', 'delta_bytes_acked', 'goodput_bps', 'goodput_mbps',
    'bytes_sent',
    'snd_cwnd_segments', 'rtt_us', 'total_retrans', 'lost', 'snd_mss_bytes',
]


def get_tcp_info(sock: socket.socket) -> dict:
    """Extract TCP statistics from a live socket using getsockopt(TCP_INFO).

    Reads the kernel's struct tcp_info (256 bytes) and unpacks the fields
    most relevant for congestion control analysis:

      - bytes_acked: Cumulative data bytes ACKed by the receiver (u64)
      - snd_mss_bytes: Sender's Maximum Segment Size (u32)
      - lost: Cumulative lost segments (u32)
      - total_retrans: Cumulative retransmitted segments (u32)
      - rtt_us: Smoothed round-trip time in microseconds (u32)
      - snd_cwnd_segments: Congestion window in segments, not bytes (u32)

    Args:
        sock: A connected TCP socket (typically the data connection).

    Returns:
        Dict with keys: bytes_acked, snd_mss_bytes, lost, total_retrans,
        rtt_us, snd_cwnd_segments.

    Raises:
        OSError: If the kernel returns a TCP_INFO struct too small to contain
                 the required fields.
    """
    raw = sock.getsockopt(socket.IPPROTO_TCP, TCP_INFO, 256)
    if len(raw) < 128:
        raise OSError(
            f"Kernel TCP_INFO struct too small: got {len(raw)} bytes, "
            "need at least 128 for tcpi_bytes_acked"
        )

    # Helper to unpack a u32 (native-endian) at a given offset.
    u32 = lambda off: struct.unpack_from('=I', raw, off)[0]

    return {
        'bytes_acked': struct.unpack_from('=Q', raw, BYTES_ACKED_OFFSET)[0],
        'snd_mss_bytes': u32(16),
        'lost': u32(32),
        'total_retrans': u32(100),
        'rtt_us': u32(68),
        'snd_cwnd_segments': u32(80),
    }


def get_congestion_algo(sock: socket.socket) -> str:
    """Query the active TCP congestion control algorithm from a socket.

    Reads the TCP_CONGESTION socket option, which returns a null-terminated
    string (e.g., b'cubic\\x00').

    Args:
        sock: A connected TCP socket.

    Returns:
        Algorithm name as a string (e.g., "cubic", "bbr", "reno").
    """
    raw = sock.getsockopt(socket.IPPROTO_TCP, socket.TCP_CONGESTION, 64)
    return raw.split(b'\0')[0].decode()


def compute_sample(
    now: float,
    start: float,
    last_t: float,
    last_ack: int,
    stats: dict,
    server: dict,
    run_id: str,
    algo: str,
    bytes_sent: int,
) -> tuple[dict, float, int]:
    """Compute one goodput sample row from TCP stats.

    Goodput is calculated as:
        goodput = (delta_bytes_acked / delta_time) * 8  [bits/s]

    This measures the rate at which the receiver acknowledges data, which
    is the actual useful throughput after accounting for retransmissions,
    packet loss, etc.

    Args:
        now: Current monotonic timestamp.
        start: Monotonic timestamp when the test started.
        last_t: Monotonic timestamp of the last sample.
        last_ack: bytes_acked value at the last sample.
        stats: Dict from get_tcp_info().
        server: Dict with keys host, port, provider, country.
        run_id: Unique hex identifier for this test run.
        algo: Active congestion control algorithm name.
        bytes_sent: Total bytes sent so far on the data socket.

    Returns:
        Tuple of (csv_row dict, new_last_t, new_last_ack).
    """
    dt = now - last_t
    delta = max(0, stats['bytes_acked'] - last_ack)
    goodput_bps = delta * 8 / dt if dt > 0 else 0.0
    goodput_mbps = goodput_bps / 1e6

    row = {
        'run_id': run_id,
        'host': server['host'],
        'port': server['port'],
        'provider': server['provider'],
        'country': server['country'],
        'algorithm': algo,
        'elapsed_s': now - start,
        'interval_s': dt,
        'bytes_acked': stats['bytes_acked'],
        'delta_bytes_acked': delta,
        'goodput_bps': goodput_bps,
        'goodput_mbps': goodput_mbps,
        'bytes_sent': bytes_sent,
        # Include all TCP stats except bytes_acked (already in row above).
        **{k: v for k, v in stats.items() if k != 'bytes_acked'},
    }

    return row, now, stats['bytes_acked']

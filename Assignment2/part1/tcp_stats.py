"""TCP socket statistics extraction and goodput computation.

This module provides utilities for reading TCP_INFO from the Linux kernel
via getsockopt() and computing goodput (acknowledged throughput) from
the tcpi_bytes_acked field.

The TCP_INFO struct layout is defined in include/uapi/linux/tcp.h.
We read specific fields using native-endian unpacking since the kernel
returns the struct in the process's native byte order.

The offsets below correspond to the Linux tcp_info layout exposed by the
host kernel used for the experiments.
"""

import socket
import struct


# Socket option constant for TCP_INFO (Linux-specific).
TCP_INFO = getattr(socket, 'TCP_INFO', 11)


# ----------------------------------------------------------------------
# TCP_INFO byte offsets for the host Linux kernel layout
# ----------------------------------------------------------------------

SND_MSS_OFFSET = 16
LOST_OFFSET = 32
RTT_OFFSET = 68
RTTVAR_OFFSET = 72
SND_CWND_OFFSET = 80
TOTAL_RETRANS_OFFSET = 100
PACING_RATE_OFFSET = 104
BYTES_ACKED_OFFSET = 120
MIN_RTT_OFFSET = 148
DELIVERY_RATE_OFFSET = 160
DELIVERED_OFFSET = 192
TCP_BYTES_SENT_OFFSET = 200
BYTES_RETRANS_OFFSET = 208

# The final field we read is an 8-byte value beginning at offset 208.
MIN_TCP_INFO_SIZE = 216


# CSV column names for output files.
CSV_FIELDS = [
    'run_id', 'host', 'port', 'provider', 'country', 'algorithm',
    'elapsed_s', 'interval_s',

    # Goodput and byte counters
    'bytes_acked', 'delta_bytes_acked',
    'goodput_bps', 'goodput_mbps',
    'bytes_sent',

    # Congestion-control state
    'snd_cwnd_segments',
    'snd_mss_bytes',

    # RTT measurements
    'rtt_us',
    'rttvar_us',
    'min_rtt_us',

    # Loss / retransmission measurements
    'total_retrans',
    'delta_retrans',
    'lost',
    'bytes_retrans',

    # Additional TCP_INFO estimates
    'pacing_rate_Bps',
    'delivery_rate_Bps',
    'delivered',
    'tcp_bytes_sent',
]


def get_tcp_info(sock: socket.socket) -> dict:
    """Extract TCP statistics from a live data socket using TCP_INFO.

    Fields recorded include:

      Required for Assignment 2:
        - snd_cwnd_segments: congestion window in segments
        - rtt_us: smoothed RTT in microseconds
        - total_retrans / lost: loss-related signals
        - bytes_acked: cumulative acknowledged application bytes

      Additional useful fields:
        - rttvar_us: RTT variation in microseconds
        - min_rtt_us: minimum observed RTT
        - pacing_rate_Bps: kernel pacing rate estimate
        - delivery_rate_Bps: kernel delivery-rate estimate
        - delivered: cumulative delivered packets
        - tcp_bytes_sent: cumulative TCP data bytes sent
        - bytes_retrans: cumulative retransmitted bytes

    Args:
        sock: Connected TCP data socket.

    Returns:
        Dictionary containing decoded TCP_INFO fields.

    Raises:
        OSError: If the kernel returns a TCP_INFO structure too short for
                 the fields required by this implementation.
    """
    raw = sock.getsockopt(socket.IPPROTO_TCP, TCP_INFO, 256)

    if len(raw) < MIN_TCP_INFO_SIZE:
        raise OSError(
            f"Kernel TCP_INFO struct too small: got {len(raw)} bytes, "
            f"need at least {MIN_TCP_INFO_SIZE}"
        )

    def u32(offset: int) -> int:
        return struct.unpack_from('=I', raw, offset)[0]

    def u64(offset: int) -> int:
        return struct.unpack_from('=Q', raw, offset)[0]

    return {
        'bytes_acked': u64(BYTES_ACKED_OFFSET),

        'snd_mss_bytes': u32(SND_MSS_OFFSET),
        'snd_cwnd_segments': u32(SND_CWND_OFFSET),

        'rtt_us': u32(RTT_OFFSET),
        'rttvar_us': u32(RTTVAR_OFFSET),
        'min_rtt_us': u32(MIN_RTT_OFFSET),

        'lost': u32(LOST_OFFSET),
        'total_retrans': u32(TOTAL_RETRANS_OFFSET),
        'bytes_retrans': u64(BYTES_RETRANS_OFFSET),

        'pacing_rate_Bps': u64(PACING_RATE_OFFSET),
        'delivery_rate_Bps': u64(DELIVERY_RATE_OFFSET),

        'delivered': u32(DELIVERED_OFFSET),
        'tcp_bytes_sent': u64(TCP_BYTES_SENT_OFFSET),
    }


def get_congestion_algo(sock: socket.socket) -> str:
    """Query the active TCP congestion-control algorithm from a socket.

    Args:
        sock: Connected TCP socket.

    Returns:
        Algorithm name such as "cubic", "reno", or "bbr".
    """
    raw = sock.getsockopt(
        socket.IPPROTO_TCP,
        socket.TCP_CONGESTION,
        64,
    )
    return raw.split(b'\0')[0].decode()


def compute_sample(
    now: float,
    start: float,
    last_t: float,
    last_ack: int,
    last_retrans: int,
    stats: dict,
    server: dict,
    run_id: str,
    algo: str,
    bytes_sent: int,
) -> tuple[dict, float, int, int]:
    """Compute one interval sample from TCP statistics.

    Goodput is calculated as:

        goodput = delta_bytes_acked * 8 / delta_time

    Delta retransmissions are also calculated so loss activity during a
    sampling interval can be compared directly with goodput from that same
    interval.

    Args:
        now: Current monotonic timestamp.
        start: Timestamp at which the transfer began.
        last_t: Timestamp of the previous sample.
        last_ack: Cumulative bytes_acked from the previous sample.
        last_retrans: Cumulative total_retrans from the previous sample.
        stats: Current TCP_INFO statistics.
        server: Destination metadata.
        run_id: Unique experiment run identifier.
        algo: Active congestion-control algorithm.
        bytes_sent: Application bytes sent so far.

    Returns:
        Tuple containing:
          - CSV row dictionary
          - current timestamp for the next interval
          - current cumulative bytes_acked
          - current cumulative total_retrans
    """
    dt = now - last_t

    delta_acked = max(
        0,
        stats['bytes_acked'] - last_ack,
    )

    delta_retrans = max(
        0,
        stats['total_retrans'] - last_retrans,
    )

    goodput_bps = (
        delta_acked * 8 / dt
        if dt > 0
        else 0.0
    )

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
        'delta_bytes_acked': delta_acked,

        'goodput_bps': goodput_bps,
        'goodput_mbps': goodput_mbps,

        'bytes_sent': bytes_sent,

        'delta_retrans': delta_retrans,

        # Include all remaining TCP_INFO fields except bytes_acked because
        # it was already added above.
        **{
            key: value
            for key, value in stats.items()
            if key != 'bytes_acked'
        },
    }

    return (
        row,
        now,
        stats['bytes_acked'],
        stats['total_retrans'],
    )
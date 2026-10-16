"""Part 2: TCP statistics tracing during transfer.

Part 1 already records TCP_INFO statistics from the live data socket while
the iPerf-compatible transfer is running. Part 2 selects one representative
successful run and persists a stable dataset for analysis and plotting.

Outputs:

    representative_samples.csv
        Per-interval TCP statistics for the representative run.

    representative.json
        Run summary plus metadata describing units, sampling semantics,
        TCP_INFO decoding, goodput computation, and the retransmission-based
        loss proxy.

The representative destination is selected as the successful run whose
mean acknowledged goodput is closest to the median mean goodput across
successful Part 1 runs. This avoids intentionally choosing either the
fastest or slowest destination.
"""

import csv
import json
import platform
import statistics
import sys
from pathlib import Path

from part1.tcp_stats import (
    SND_MSS_OFFSET,
    LOST_OFFSET,
    RTT_OFFSET,
    RTTVAR_OFFSET,
    SND_CWND_OFFSET,
    TOTAL_RETRANS_OFFSET,
    PACING_RATE_OFFSET,
    BYTES_ACKED_OFFSET,
    MIN_RTT_OFFSET,
    DELIVERY_RATE_OFFSET,
    DELIVERED_OFFSET,
    TCP_BYTES_SENT_OFFSET,
    BYTES_RETRANS_OFFSET,
    MIN_TCP_INFO_SIZE,
)


# ----------------------------------------------------------------------
# Fields required for the Part 2 analysis
# ----------------------------------------------------------------------

REQUIRED_SAMPLE_FIELDS = {
    'run_id',
    'host',
    'port',
    'algorithm',
    'elapsed_s',
    'interval_s',
    'bytes_acked',
    'delta_bytes_acked',
    'goodput_bps',
    'goodput_mbps',
    'snd_cwnd_segments',
    'rtt_us',
    'total_retrans',
    'delta_retrans',
}


# ----------------------------------------------------------------------
# Metadata describing CSV units
# ----------------------------------------------------------------------

FIELD_UNITS = {
    'elapsed_s': 'seconds',
    'interval_s': 'seconds',

    'bytes_acked': 'bytes',
    'delta_bytes_acked': 'bytes',

    'goodput_bps': 'bits/second',
    'goodput_mbps': 'megabits/second',

    'bytes_sent': 'bytes',

    'snd_cwnd_segments': 'segments',
    'snd_mss_bytes': 'bytes',

    'rtt_us': 'microseconds',
    'rttvar_us': 'microseconds',
    'min_rtt_us': 'microseconds',

    'total_retrans': 'segments',
    'delta_retrans': 'segments',
    'lost': 'segments',
    'bytes_retrans': 'bytes',

    'pacing_rate_Bps': 'bytes/second',
    'delivery_rate_Bps': 'bytes/second',

    'delivered': 'packets',
    'tcp_bytes_sent': 'bytes',
}


# ----------------------------------------------------------------------
# Linux struct tcp_info layout used by part1/tcp_stats.py
#
# Importing the offset constants from tcp_stats.py keeps this metadata
# synchronized with the offsets actually used to decode TCP_INFO.
# ----------------------------------------------------------------------

TCP_INFO_LAYOUT = {
    'snd_mss_bytes': {
        'kernel_field': 'tcpi_snd_mss',
        'offset_bytes': SND_MSS_OFFSET,
        'type': 'u32',
    },
    'lost': {
        'kernel_field': 'tcpi_lost',
        'offset_bytes': LOST_OFFSET,
        'type': 'u32',
    },
    'rtt_us': {
        'kernel_field': 'tcpi_rtt',
        'offset_bytes': RTT_OFFSET,
        'type': 'u32',
    },
    'rttvar_us': {
        'kernel_field': 'tcpi_rttvar',
        'offset_bytes': RTTVAR_OFFSET,
        'type': 'u32',
    },
    'snd_cwnd_segments': {
        'kernel_field': 'tcpi_snd_cwnd',
        'offset_bytes': SND_CWND_OFFSET,
        'type': 'u32',
    },
    'total_retrans': {
        'kernel_field': 'tcpi_total_retrans',
        'offset_bytes': TOTAL_RETRANS_OFFSET,
        'type': 'u32',
    },
    'pacing_rate_Bps': {
        'kernel_field': 'tcpi_pacing_rate',
        'offset_bytes': PACING_RATE_OFFSET,
        'type': 'u64',
    },
    'bytes_acked': {
        'kernel_field': 'tcpi_bytes_acked',
        'offset_bytes': BYTES_ACKED_OFFSET,
        'type': 'u64',
    },
    'min_rtt_us': {
        'kernel_field': 'tcpi_min_rtt',
        'offset_bytes': MIN_RTT_OFFSET,
        'type': 'u32',
    },
    'delivery_rate_Bps': {
        'kernel_field': 'tcpi_delivery_rate',
        'offset_bytes': DELIVERY_RATE_OFFSET,
        'type': 'u64',
    },
    'delivered': {
        'kernel_field': 'tcpi_delivered',
        'offset_bytes': DELIVERED_OFFSET,
        'type': 'u32',
    },
    'tcp_bytes_sent': {
        'kernel_field': 'tcpi_bytes_sent',
        'offset_bytes': TCP_BYTES_SENT_OFFSET,
        'type': 'u64',
    },
    'bytes_retrans': {
        'kernel_field': 'tcpi_bytes_retrans',
        'offset_bytes': BYTES_RETRANS_OFFSET,
        'type': 'u64',
    },
}


def _read_summary(path: Path) -> list[dict]:
    """Read Part 1's summary.csv."""
    with open(path, newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))


def _read_samples(path: Path) -> list[dict]:
    """Read a per-run sample CSV."""
    with open(path, newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))


def _write_csv(
    path: Path,
    rows: list[dict],
    fields: list[str],
) -> None:
    """Write rows to a CSV file."""
    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(
            f,
            fieldnames=fields,
        )
        writer.writeheader()
        writer.writerows(rows)


def _select_representative(
    summaries: list[dict],
) -> dict:
    """Select the run closest to the median mean goodput.

    Using the fastest successful run would bias Part 2 toward a best-case
    path. Instead, calculate the median of the per-run mean goodputs and
    choose the run whose mean is closest to that value.
    """
    mean_goodputs = [
        float(row['mean_mbps'])
        for row in summaries
    ]

    median_goodput = statistics.median(
        mean_goodputs
    )

    return min(
        summaries,
        key=lambda row: abs(
            float(row['mean_mbps'])
            - median_goodput
        ),
    )


def _validate_samples(
    rows: list[dict],
    samples_path: Path,
) -> None:
    """Validate that a sample trace contains the fields Part 2 requires."""
    if not rows:
        raise ValueError(
            f"Representative sample trace at {samples_path} is empty"
        )

    available = set(rows[0].keys())

    missing = (
        REQUIRED_SAMPLE_FIELDS
        - available
    )

    if missing:
        raise ValueError(
            "Representative trace is missing required Part 2 fields: "
            + ', '.join(sorted(missing))
        )


def _observed_interval_stats(
    rows: list[dict],
) -> dict:
    """Summarize the actual sampling intervals observed in the trace."""
    intervals = [
        float(row['interval_s'])
        for row in rows
        if row.get('interval_s') not in (None, '')
    ]

    if not intervals:
        return {
            'min_s': None,
            'median_s': None,
            'mean_s': None,
            'max_s': None,
        }

    return {
        'min_s': min(intervals),
        'median_s': statistics.median(intervals),
        'mean_s': statistics.mean(intervals),
        'max_s': max(intervals),
    }


def run_part2(
    part1_dir: Path,
    output_dir: Path,
) -> dict:
    """Select a representative run and emit the Part 2 dataset.

    Args:
        part1_dir:
            Directory containing Part 1 outputs, including summary.csv and
            per-run {run_id}_samples.csv files.

        output_dir:
            Directory in which to write representative_samples.csv and
            representative.json.

    Returns:
        Dictionary describing the representative run.

    Raises:
        FileNotFoundError:
            If required Part 1 output files do not exist.

        ValueError:
            If the selected sample trace is empty or missing required
            Part 2 fields.
    """
    summary_path = (
        part1_dir
        / 'summary.csv'
    )

    if not summary_path.exists():
        raise FileNotFoundError(
            f"Part 1 summary not found at {summary_path}; "
            "run Part 1 first"
        )

    summaries = _read_summary(
        summary_path
    )

    if not summaries:
        raise FileNotFoundError(
            f"Part 1 summary at {summary_path} contains no successful runs; "
            "run Part 1 first"
        )

    # Select a middle-performing successful run rather than a best-case run.
    rep = _select_representative(
        summaries
    )

    run_id = rep['run_id']

    samples_path = (
        part1_dir
        / f'{run_id}_samples.csv'
    )

    if not samples_path.exists():
        raise FileNotFoundError(
            f"Sample trace for representative run {run_id} "
            f"not found at {samples_path}"
        )

    rows = _read_samples(
        samples_path
    )

    _validate_samples(
        rows,
        samples_path,
    )

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    # --------------------------------------------------------------
    # Stable Part 2 CSV
    # --------------------------------------------------------------

    representative_csv = (
        output_dir
        / 'representative_samples.csv'
    )

    _write_csv(
        representative_csv,
        rows,
        list(rows[0].keys()),
    )

    # --------------------------------------------------------------
    # Sampling metadata
    # --------------------------------------------------------------

    interval_stats = (
        _observed_interval_stats(rows)
    )

    mean_values = [
        float(summary['mean_mbps'])
        for summary in summaries
    ]

    median_mean_goodput = (
        statistics.median(mean_values)
    )

    # --------------------------------------------------------------
    # Self-describing Part 2 metadata
    # --------------------------------------------------------------

    representative = {
        'run_id': run_id,

        'host': rep['host'],
        'port': int(rep['port']),
        'provider': rep.get('provider', ''),
        'country': rep.get('country', ''),

        'algorithm': rep['algorithm'],

        'samples': int(rep['samples']),
        'bytes_sent': int(rep['bytes_sent']),

        'min_mbps': float(rep['min_mbps']),
        'median_mbps': float(rep['median_mbps']),
        'mean_mbps': float(rep['mean_mbps']),
        'p95_mbps': float(rep['p95_mbps']),

        'representative_selection': {
            'method': 'closest_to_median_mean_goodput',
            'successful_runs_considered': len(summaries),
            'median_mean_goodput_mbps': median_mean_goodput,
        },

        'sampling': {
            'timestamp_definition': (
                'elapsed_s is time.monotonic() relative to transfer start'
            ),
            'interval_definition': (
                'interval_s is the elapsed monotonic time since the '
                'previous TCP_INFO sample'
            ),
            'observed_intervals': interval_stats,
        },

        'goodput': {
            'definition': (
                'rate of increase in cumulative acknowledged data bytes '
                'during the sampling interval'
            ),
            'formula': (
                'goodput_bps = '
                '(delta_bytes_acked * 8) / interval_s'
            ),
            'source_counter': 'tcpi_bytes_acked',
        },

        'loss_proxy': {
            'field': 'delta_retrans',
            'definition': (
                'increase in cumulative tcpi_total_retrans during the '
                'sampling interval'
            ),
            'formula': (
                'delta_retrans = max(0, '
                'current_total_retrans - previous_total_retrans)'
            ),
            'reason': (
                'interval retransmissions provide a loss/congestion signal '
                'that can be compared directly with interval goodput'
            ),
            'note': (
                'tcpi_lost is also recorded, but delta_retrans is used as '
                'the primary loss proxy because tcpi_total_retrans is a '
                'cumulative counter'
            ),
        },

        'units': {
            key: value
            for key, value in FIELD_UNITS.items()
            if key in rows[0]
        },

        'tcp_info_decoding': {
            'source': (
                'Linux struct tcp_info from '
                'include/uapi/linux/tcp.h'
            ),
            'kernel_system': platform.system(),
            'kernel_release': platform.release(),
            'machine': platform.machine(),
            'process_byte_order': sys.byteorder,
            'unpacking': {
                'u32': '=I',
                'u64': '=Q',
                'description': (
                    'native-standard byte order with explicit 32-bit and '
                    '64-bit unsigned integer widths'
                ),
            },
            'requested_struct_bytes': 256,
            'minimum_required_bytes': MIN_TCP_INFO_SIZE,
            'fields': {
                key: value
                for key, value in TCP_INFO_LAYOUT.items()
                if key in rows[0]
            },
        },

        'files': {
            'samples': representative_csv.name,
            'source_samples': samples_path.name,
        },
    }

    metadata_path = (
        output_dir
        / 'representative.json'
    )

    metadata_path.write_text(
        json.dumps(
            representative,
            indent=2,
        ),
        encoding='utf-8',
    )

    print(
        f"Part 2 representative: "
        f"{representative['host']}:"
        f"{representative['port']} "
        f"({representative['algorithm']}, "
        f"{representative['mean_mbps']:.2f} Mbit/s mean); "
        f"output={output_dir}"
    )

    return representative
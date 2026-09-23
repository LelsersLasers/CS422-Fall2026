"""Part 2: TCP statistics tracing during transfer (assignment section 2).

Part 2 requires the OS default congestion control algorithm (CUBIC on
Linux), which is exactly what Part 1's test loop already ran and recorded.
Every sample row emitted by part 1 already carries the required fields:

    timestamp (elapsed_s / interval_s), snd_cwnd (segments), RTT estimate
    (rtt_us), loss signal (total_retrans / lost, cumulative), plus
    goodput, destination, algorithm, and run identifier.

So Part 2 is a selection + persistence layer over Part 1's output: it
picks one representative destination (highest mean goodput) from
Part 1's summary and re-emits its trace under stable, well-known names
that the plotter and report reference:

    representative_samples.csv  The representative run's per-interval trace.
    representative.json         run_id, host, port, algorithm, summary stats.
"""

import csv
import json
from pathlib import Path


def _read_summary(path: Path) -> list[dict]:
    """Read Part 1's summary.csv into a list of row dicts."""
    with open(path, newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))


def _read_samples(path: Path) -> list[dict]:
    """Read a per-run samples CSV into a list of row dicts (string values)."""
    with open(path, newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))


def _write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    """Write a list of dicts to a CSV file."""
    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def run_part2(
    part1_dir: Path,
    output_dir: Path,
) -> dict:
    """Select the representative destination and emit the Part 2 dataset.

    Args:
        part1_dir: Directory containing Part 1 outputs (summary.csv and
            {run_id}_samples.csv files).
        output_dir: Directory to write representative files into.

    Returns:
        Dict describing the representative run.

    Raises:
        FileNotFoundError: If Part 1 produced no successful runs.
    """
    summary_path = part1_dir / 'summary.csv'
    if not summary_path.exists():
        raise FileNotFoundError(
            f"Part 1 summary not found at {summary_path}; "
            "run Part 1 first"
        )

    summaries = _read_summary(summary_path)
    if not summaries:
        raise FileNotFoundError(
            f"Part 1 summary at {summary_path} contains no successful runs; "
            "run Part 1 first"
        )

    # Representative destination: highest mean acknowledged goodput.
    rep = max(summaries, key=lambda s: float(s['mean_mbps']))
    run_id = rep['run_id']
    samples_path = part1_dir / f'{run_id}_samples.csv'
    if not samples_path.exists():
        raise FileNotFoundError(
            f"Sample trace for representative run {run_id} not found "
            f"at {samples_path}"
        )

    rows = _read_samples(samples_path)

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(output_dir / 'representative_samples.csv', rows,
               list(rows[0].keys()))

    representative = {
        'run_id': run_id,
        'host': rep['host'],
        'port': int(rep['port']),
        'algorithm': rep['algorithm'],
        'samples': int(rep['samples']),
        'bytes_sent': int(rep['bytes_sent']),
        'min_mbps': float(rep['min_mbps']),
        'median_mbps': float(rep['median_mbps']),
        'mean_mbps': float(rep['mean_mbps']),
        'p95_mbps': float(rep['p95_mbps']),
    }
    (output_dir / 'representative.json').write_text(
        json.dumps(representative, indent=2)
    )

    print(
        f"Part 2 representative: {representative['host']}:"
        f"{representative['port']} ({representative['algorithm']}, "
        f"{representative['mean_mbps']:.2f} Mbit/s mean); "
        f"output={output_dir}"
    )
    return representative

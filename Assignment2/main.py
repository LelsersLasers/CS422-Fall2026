#!/usr/bin/env python3
"""Assignment 2 orchestrator: iPerf3 goodput, TCP stats, congestion control.

Thin entry point that drives the three assignment parts in sequence and
then renders all plots. All intermediate data (CSV/JSON) AND the final
graph PDFs are written to the single `output/` subfolder:

    output/                      Part 1 + Part 2 data and PDFs
        {run_id}_samples.csv
        {run_id}_server_results.json
        summary.csv
        failures.csv
        manifest.json
        goodput.pdf              (Part 1)
        representative_samples.csv
        representative.json
        tcp_stats.pdf            (Part 2)
        part3/                   Part 3 data and PDFs
            {cubic,reno,bbr}/{run_id}_samples.csv
            comparison_summary.csv
            manifest.json
            comparison.pdf

Usage (run from the Assignment2/ directory):
    python3 main.py
    python3 main.py -n 10 -d 60 -i 1.0 --seed 42
"""

import argparse
from pathlib import Path

from part1.run_iperf import run_part1
from part2.run_tcp_stats import run_part2
from part3.run_algorithms import run_part3
from plot_results import run_plot_results

ROOT = Path(__file__).resolve().parent
DATA_JSON = ROOT / "data" / "listed_iperf3_servers.json"
OUTPUT_DIR = ROOT / "output"


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Run the Assignment 2 iPerf3 experiment '
                    '(Parts 1-3) and produce plots.',
    )
    parser.add_argument(
        '-n', '--destinations', type=int, default=10,
        help='Number of successful destinations to reach (default: 10)',
    )
    parser.add_argument(
        '-d', '--duration', type=float, default=60,
        help='Per-test duration in seconds (default: 60)',
    )
    parser.add_argument(
        '-i', '--interval', type=float, default=1.0,
        help='TCP stats sampling interval in seconds (default: 1.0)',
    )
    parser.add_argument(
        '--timeout', type=float, default=15,
        help='Connection/read timeout in seconds (default: 15)',
    )
    parser.add_argument(
        '--max-attempts', type=int, default=30,
        help='Maximum total test attempts per part (default: 30)',
    )
    parser.add_argument(
        '--block-size', type=int, default=131072,
        help='Data send block size in bytes, 1..1048576 (default: 131072)',
    )
    parser.add_argument(
        '--algorithm', default=None,
        help='Force a TCP congestion algorithm for Part 1 '
             '(default: OS default, e.g. CUBIC)',
    )
    parser.add_argument(
        '--seed', type=int, default=None,
        help='Random seed for reproducible server selection',
    )
    parser.add_argument(
        '--servers', type=Path, default=DATA_JSON,
        help='Path to the JSON server list (default: data/'
             'listed_iperf3_servers.json)',
    )
    parser.add_argument(
        '--output', type=Path, default=OUTPUT_DIR,
        help='Output directory for data and plots (default: output/)',
    )
    args = parser.parse_args()

    if not (1 <= args.block_size <= 1_048_576):
        parser.error('block-size must be between 1 and 1048576 bytes')

    args.output.mkdir(parents=True, exist_ok=True)

    # Part 1: destination selection + goodput measurement (OS default algo).
    run_part1(
        servers=args.servers,
        output_dir=args.output,
        destinations=args.destinations,
        duration=args.duration,
        interval=args.interval,
        timeout=args.timeout,
        max_attempts=args.max_attempts,
        block_size=args.block_size,
        algorithm=args.algorithm,
        seed=args.seed,
    )

    # Part 2: pick the representative destination from Part 1's trace
    # (OS default algorithm, exactly what Part 1 measured).
    run_part2(part1_dir=args.output, output_dir=args.output)

    # Part 3: CUBIC / Reno / BBR comparison on the same destinations.
    part3_dir = args.output / 'part3'
    run_part3(
        servers=args.servers,
        output_dir=part3_dir,
        destinations=args.destinations,
        duration=args.duration,
        interval=args.interval,
        timeout=args.timeout,
        max_attempts=args.max_attempts,
        block_size=args.block_size,
        seed=args.seed,
    )

    # Render all PDFs into the same output directory.
    produced = run_plot_results(args.output)
    for p in produced:
        print(f'Wrote {p}')

    return 0


if __name__ == '__main__':
    raise SystemExit(main())

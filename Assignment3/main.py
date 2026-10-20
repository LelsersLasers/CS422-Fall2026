#!/usr/bin/env python3
"""Assignment 3 Option 1: repeated, matched TCP congestion-control trials.

Run from the repository root: python3 Assignment3/main.py
Uses Assignment 2's iperf3-compatible client and TCP_INFO collector.
"""

import argparse
import csv
import json
import platform
import random
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path
from subprocess import run

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'Assignment2'))
from part1.run_iperf import attempt_tests  # noqa: E402
from part1.utils import load_servers  # noqa: E402
from part3.run_algorithms import available_algorithms  # noqa: E402

ALGORITHMS = ('rla', 'cubic', 'reno', 'bbr')
DESTINATION_FIELDS = ('host', 'port', 'provider', 'country')
MEASUREMENT_FIELDS = (
    'algorithm', 'run_id', 'samples', 'bytes_sent', 'min_mbps',
    'median_mbps', 'mean_mbps', 'p95_mbps',
)
FIELDS = (
    'repetition', 'order_index', 'requested_algorithm', 'algorithm',
    'host', 'port', 'provider', 'country', 'run_id', 'samples', 'bytes_sent',
    'min_mbps', 'median_mbps', 'mean_mbps', 'p95_mbps', 'mean_rtt_ms',
    'median_rtt_ms', 'retransmissions', 'status', 'error',
)


def parse_arguments():
    """Read CLI options and reject invalid experiment configurations."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destinations', type=int, default=3)
    parser.add_argument('--repetitions', type=int, default=3)
    parser.add_argument('--duration', type=float, default=10)
    parser.add_argument('--interval', type=float, default=0.2)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--max-selection-attempts', type=int, default=30)
    parser.add_argument('--timeout', type=float, default=15)
    parser.add_argument('--block-size', type=int, default=131072)
    parser.add_argument(
        '--servers', type=Path,
        default=ROOT / 'Assignment2/data/listed_iperf3_servers.json',
    )
    parser.add_argument(
        '--output', type=Path,
        default=ROOT / 'Assignment3/output/evaluation',
    )
    args = parser.parse_args()

    if (args.destinations < 1 or args.repetitions < 1 or
            args.duration <= 0 or args.interval <= 0):
        parser.error('destinations, repetitions, duration, and interval must be positive')
    if args.max_selection_attempts < args.destinations:
        parser.error('max-selection-attempts must be >= destinations')
    if not 1 <= args.block_size <= 1_048_576:
        parser.error('block-size must be between 1 and 1048576')
    return args, parser


def prepare_output(args, parser):
    """Check installed algorithms and protect existing experimental results."""
    available = available_algorithms()
    if available is not None:
        missing = sorted(set(ALGORITHMS) - available)
        if missing:
            parser.error(
                'Missing TCP algorithms: ' + ', '.join(missing) +
                '. Load RLA/BBR before running.'
            )

    output = args.output.resolve()
    protected = ('trials.csv', 'manifest.json', 'selection')
    if any((output / name).exists() for name in protected):
        parser.error(
            f'Output already contains experiment results: {output}. '
            'Choose a new --output directory.'
        )
    output.mkdir(parents=True, exist_ok=True)
    return output


def write_csv(path, records, fields=FIELDS):
    """Write accumulated trial records after every attempt."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=fields, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(records)


def summarize_trace(trace):
    """Compute RTT statistics and count retransmissions from TCP_INFO."""
    rtts = [float(row['rtt_us']) / 1000
            for row in trace if float(row['rtt_us']) > 0]
    # delta_retrans is the retransmission count for each sample interval.
    # Summing it avoids double-counting cumulative TCP_INFO totals.
    retransmissions = sum(max(0, int(row['delta_retrans'])) for row in trace)
    return {
        'mean_rtt_ms': statistics.mean(rtts) if rtts else '',
        'median_rtt_ms': statistics.median(rtts) if rtts else '',
        'retransmissions': retransmissions,
    }


def select_destinations(args, output, parser):
    """Select reachable servers with CUBIC, excluding selection from results."""
    candidates = load_servers(args.servers, random.Random(args.seed))
    if not candidates:
        parser.error('Server list contains no candidates')

    selected, failures, _, attempts = attempt_tests(
        candidates=candidates,
        destinations=args.destinations,
        max_attempts=args.max_selection_attempts,
        duration=args.duration,
        interval=args.interval,
        timeout=args.timeout,
        block_size=args.block_size,
        algorithm='cubic',
        output=output / 'selection',
        verbose=True,
    )
    cohort = [
        {field: result[field] for field in DESTINATION_FIELDS}
        for result in selected
    ]
    return cohort, failures, attempts


def algorithm_order(repetition):
    """Rotate algorithm order to reduce systematic time-order bias."""
    offset = (repetition - 1) % len(ALGORITHMS)
    return ALGORITHMS[offset:] + ALGORITHMS[:offset]


def run_trial(args, output, destination, repetition, position, algorithm):
    """Run a single algorithm/server trial and summarize its measurements."""
    record = {
        'repetition': repetition,
        'order_index': position,
        'requested_algorithm': algorithm,
        'algorithm': '',
        **destination,
    }
    print(
        f"Run {repetition}/{args.repetitions}: "
        f"{destination['host']}:{destination['port']} {algorithm}",
        flush=True,
    )
    successes, failures, _, _ = attempt_tests(
        candidates=[destination],
        destinations=1,
        max_attempts=1,
        duration=args.duration,
        interval=args.interval,
        timeout=args.timeout,
        block_size=args.block_size,
        algorithm=algorithm,
        output=output / f'run_{repetition:02d}' / algorithm,
        verbose=True,
    )
    if successes:
        result = successes[0]
        record.update({key: result[key] for key in MEASUREMENT_FIELDS})
        record.update(summarize_trace(result['trace']))
        record.update(status='ok', error='')
    else:
        error = failures[0]['error'] if failures else 'No result'
        record.update(status='failed', error=error)
    return record


def run_experiments(args, output, cohort):
    """Run every algorithm for every selected destination and repetition."""
    rows = []
    order_log = []
    for repetition in range(1, args.repetitions + 1):
        for destination in cohort:
            for position, algorithm in enumerate(algorithm_order(repetition), 1):
                order_log.append({
                    'repetition': repetition,
                    'position': position,
                    'algorithm': algorithm,
                    'host': destination['host'],
                    'port': destination['port'],
                })
                rows.append(run_trial(
                    args, output, destination, repetition, position, algorithm,
                ))
                # Preserve partial results if a later connection fails.
                write_csv(output / 'trials.csv', rows)
    return rows, order_log


def write_manifest(args, output, cohort, failures, attempts, rows, order_log):
    """Record the test environment, selection history, and trial status."""
    manifest = {
        'generated_utc': datetime.now(timezone.utc).isoformat(),
        'kernel': platform.release(),
        'algorithms': list(ALGORITHMS),
        'algorithm_order_by_trial': order_log,
        'selected_destinations': cohort,
        'selection_attempts': attempts,
        'selection_failures': failures,
        'repetitions': args.repetitions,
        'duration_s': args.duration,
        'interval_s': args.interval,
        'timeout_s': args.timeout,
        'block_size_bytes': args.block_size,
        'server_list': str(args.servers),
        'seed': args.seed,
        'requested_destinations': args.destinations,
        'completed_destinations': len(cohort),
        'successful_trials': sum(row['status'] == 'ok' for row in rows),
        'failed_trials': sum(row['status'] != 'ok' for row in rows),
    }
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return manifest


def generate_plots(output):
    """Generate comparison.pdf and aggregate.csv from completed trial data."""
    script = ROOT / 'Assignment3' / 'plot_evaluation.py'
    result = run([sys.executable, str(script), '--output', str(output)], check=False)
    return result.returncode


def main():
    args, parser = parse_arguments()
    output = prepare_output(args, parser)
    cohort, failures, attempts = select_destinations(args, output, parser)
    rows, order_log = run_experiments(args, output, cohort)
    manifest = write_manifest(
        args, output, cohort, failures, attempts, rows, order_log,
    )

    print(f"Finished {manifest['successful_trials']}/{len(rows)} trials. Files: {output}")
    if len(cohort) < args.destinations or manifest['failed_trials']:
        print('WARNING: incomplete matching. Exclude destinations without every required trial.')
        return 2
    return generate_plots(output)


if __name__ == '__main__':
    raise SystemExit(main())

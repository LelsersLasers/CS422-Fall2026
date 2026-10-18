#!/usr/bin/env python3
"""Assignment 3 Option 1: repeated, matched TCP congestion-control trials.

Run from any directory: python3 Assignment3/run_evaluation.py --repetitions 3
Uses Assignment2's original iperf3-compatible TCP client and TCP_INFO collector.
"""
import argparse
import csv
import json
import platform
import random
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'Assignment2'))
from part1.run_iperf import attempt_tests  # noqa: E402
from part1.utils import load_servers  # noqa: E402
from part3.run_algorithms import available_algorithms  # noqa: E402

ALGORITHMS = ('rla', 'cubic', 'reno', 'bbr')
FIELDS = ('repetition', 'order_index', 'requested_algorithm', 'algorithm',
          'host', 'port', 'provider', 'country', 'run_id', 'samples', 'bytes_sent',
          'min_mbps', 'median_mbps', 'mean_mbps', 'p95_mbps', 'mean_rtt_ms',
          'median_rtt_ms', 'retransmissions', 'status', 'error')


def write_csv(path, records, fields=FIELDS):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(records)


def summarize_trace(trace):
    import statistics
    rtts = [float(x['rtt_us']) / 1000 for x in trace if float(x['rtt_us']) > 0]
    return {
        'mean_rtt_ms': statistics.mean(rtts) if rtts else '',
        'median_rtt_ms': statistics.median(rtts) if rtts else '',
        # TCP_INFO total_retrans is cumulative within a socket; delta_retrans
        # is the per-interval event count, so summing deltas is correct.
        'retransmissions': sum(max(0, int(x['delta_retrans'])) for x in trace),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destinations', type=int, default=3)
    parser.add_argument('--repetitions', type=int, default=3)
    parser.add_argument('--duration', type=float, default=10)
    parser.add_argument('--interval', type=float, default=0.2)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--max-selection-attempts', type=int, default=30)
    parser.add_argument('--timeout', type=float, default=15)
    parser.add_argument('--block-size', type=int, default=131072)
    parser.add_argument('--servers', type=Path,
                        default=ROOT / 'Assignment2/data/listed_iperf3_servers.json')
    parser.add_argument('--output', type=Path, default=ROOT / 'Assignment3/output/evaluation')
    args = parser.parse_args()
    if args.destinations < 1 or args.repetitions < 1 or args.duration <= 0 or args.interval <= 0:
        parser.error('destinations, repetitions, duration, and interval must be positive')
    if args.max_selection_attempts < args.destinations:
        parser.error('max-selection-attempts must be >= destinations')
    if not 1 <= args.block_size <= 1_048_576:
        parser.error('block-size must be between 1 and 1048576')

    avail = available_algorithms()
    if avail is not None and not set(ALGORITHMS).issubset(avail):
        parser.error('Missing TCP algorithms: ' + ', '.join(sorted(set(ALGORITHMS)-avail)) +
                     '. Load RLA/BBR before running.')
    output = args.output.resolve()
    # Never overwrite experimental evidence from a prior invocation.
    if any((output / name).exists() for name in ('trials.csv', 'manifest.json', 'selection')):
        parser.error(f'Output already contains experiment results: {output}. Choose a new --output directory.')
    output.mkdir(parents=True, exist_ok=True)
    candidates = load_servers(args.servers, random.Random(args.seed))
    if not candidates:
        parser.error('Server list contains no candidates')

    # Selection uses its own 10-second CUBIC runs. They are NOT included in
    # comparison statistics: every measured trial starts from the same cohort.
    selection, selection_failures, _, attempts = attempt_tests(
        candidates=candidates, destinations=args.destinations,
        max_attempts=args.max_selection_attempts, duration=args.duration,
        interval=args.interval, timeout=args.timeout, block_size=args.block_size,
        algorithm='cubic', output=output/'selection', verbose=True)
    cohort = [{key: s[key] for key in ('host', 'port', 'provider', 'country')}
              for s in selection]
    rows = []
    order_log = []
    # Rotate order to lessen simple time-order bias. Each destination is tested
    # once per algorithm in every repetition, including failed attempts.
    for rep in range(1, args.repetitions + 1):
        order = list(ALGORITHMS)
        offset = (rep - 1) % len(order)
        order = order[offset:] + order[:offset]
        for dest in cohort:
            for position, algo in enumerate(order, 1):
                record = dict(repetition=rep, order_index=position,
                              requested_algorithm=algo, algorithm='', **dest)
                order_log.append(dict(repetition=rep, position=position,
                                      algorithm=algo, host=dest['host'], port=dest['port']))
                print(f"Run {rep}/{args.repetitions}: {dest['host']}:{dest['port']} {algo}", flush=True)
                successes, failures, _, _ = attempt_tests(
                    candidates=[dest], destinations=1, max_attempts=1,
                    duration=args.duration, interval=args.interval,
                    timeout=args.timeout, block_size=args.block_size,
                    algorithm=algo, output=output/f'run_{rep:02d}'/algo,
                    verbose=True)
                if successes:
                    s = successes[0]
                    record.update({k: s[k] for k in ('algorithm','run_id','samples','bytes_sent',
                                                     'min_mbps','median_mbps','mean_mbps','p95_mbps')})
                    record.update(summarize_trace(s['trace']))
                    record.update(status='ok', error='')
                else:
                    record.update(status='failed', error=failures[0]['error'] if failures else 'No result')
                rows.append(record)
                write_csv(output/'trials.csv', rows)

    manifest = dict(generated_utc=datetime.now(timezone.utc).isoformat(),
                    kernel=platform.release(), algorithms=list(ALGORITHMS),
                    algorithm_order_by_trial=order_log, selected_destinations=cohort,
                    selection_attempts=attempts, selection_failures=selection_failures,
                    repetitions=args.repetitions, duration_s=args.duration,
                    interval_s=args.interval, timeout_s=args.timeout,
                    block_size_bytes=args.block_size, server_list=str(args.servers),
                    seed=args.seed,
                    requested_destinations=args.destinations,
                    completed_destinations=len(cohort),
                    successful_trials=sum(r['status']=='ok' for r in rows),
                    failed_trials=sum(r['status']!='ok' for r in rows))
    (output/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    print(f"Finished {manifest['successful_trials']}/{len(rows)} trials. Files: {output}")
    if len(cohort) < args.destinations or manifest['failed_trials']:
        print('WARNING: incomplete matching. Exclude destinations without every required trial.')
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

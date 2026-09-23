#!/usr/bin/env python3
"""iPerf3 throughput client — main entry point.

This module orchestrates server selection, test execution, and output
generation.  It mimics the structure of Assignment 1's main.py:

    1. Parse CLI arguments (destinations, duration, timeout, etc.)
  . Validate platform (Linux required for TCP_INFO / TCP_CONGESTION).
    3. Load and shuffle the server candidate list.
    4. Iterate through candidates, running tests until the target
       number of successful destinations is reached or attempts exhausted.
    5. Write per-run CSV / JSON output, a summary CSV, and a manifest.
    6. Generate goodput visualization PDF.

Usage:
    python main.py -n 5 -d 30 --timeout 15 --output results/part1
"""

import argparse
import json
import math
import platform
import random
import statistics
import socket
import sys
import uuid
from pathlib import Path

from protocol import ProtocolError
from run_test import run_test
from tcp_stats import CSV_FIELDS
from utils import (
    expect_linux,
    load_servers,
    write_csv,
    write_json,
)
from plot_results import plot_goodput


def main() -> int:
    """Parse arguments, run tests, and produce output files.

    Returns:
        0 on success (all requested destinations reached),
        1 on partial success or failure.
    """
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        '--servers',
        type=Path,
        default=Path('data/listed_iperf3_servers.json'),
        help='Path to the JSON server list file (default: data/listed_iperf3_servers.json)',
    )
    p.add_argument(
        '-n', '--destinations',
        type=int,
        default=10,
        help='Number of successful destinations to reach (default: 10)',
    )
    p.add_argument(
        '-d', '--duration',
        type=float,
        default=60,
        help='Test duration in seconds (default: 60)',
    )
    p.add_argument(
        '-i', '--interval',
        type=float,
        default=1,
        help='TCP stats sampling interval in seconds (default: 1)',
    )
    p.add_argument(
        '--timeout',
        type=float,
        default=15,
        help='Connection and read timeout in seconds (default: 15)',
    )
    p.add_argument(
        '--max-attempts',
        type=int,
        default=30,
        help='Maximum number of test attempts before giving up (default: 30)',
    )
    p.add_argument(
        '--block-size',
        type=int,
        default=131072,
        help='Data send block size in bytes; 1 .. 1048576 (default: 131072)',
    )
    p.add_argument(
        '--algorithm',
        default=None,
        help='Optional TCP congestion control algorithm (e.g. cubic, bbr, reno)',
    )
    p.add_argument(
        '--seed',
        type=int,
        default=None,
        help='Random seed for reproducible server selection',
    )
    p.add_argument(
        '--output',
        type=Path,
        default=Path('output'),
        help='Output directory for CSV, JSON, and PDF files (default: output)',
    )
    args = p.parse_args()

    # ------------------------------------------------------------------
    # Validate arguments
    # ------------------------------------------------------------------
    if args.destinations < 1:
        p.error('"--destinations" must be >= 1')
    if args.duration <= 0:
        p.error('"--duration" must be > 0')
    if args.interval <= 0:
        p.error('"--interval" must be > 0')
    if args.timeout <= 0:
        p.error('"--timeout" must be > 0')
    if args.max_attempts < 1:
        p.error('"--max-attempts" must be >= 1')
    if not (1 <= args.block_size <= 1024 * 1024):
        p.error('"--block-size" must be between 1 and 1048576')

    # ------------------------------------------------------------------
    # Validate platform
    # ------------------------------------------------------------------
    try:
        expect_linux()
    except RuntimeError as e:
        p.error(str(e))

    # ------------------------------------------------------------------
    # Prepare output directory and server list
    # ------------------------------------------------------------------
    args.output.mkdir(parents=True, exist_ok=True)

    rng = random.Random(args.seed)
    candidates = load_servers(args.servers, rng)
    if not candidates:
        p.error('No valid server entries found in server list')

    # ------------------------------------------------------------------
    # Main test loop
    # ------------------------------------------------------------------
    successes: list[dict] = []
    failures: list[dict] = []
    summaries: list[dict] = []
    attempted = 0

    for server in candidates:
        # Check termination conditions.
        if len(successes) >= args.destinations:
            break
        if attempted >= args.max_attempts:
            break

        attempted += 1
        run_id = uuid.uuid4().hex[:12]

        print(
            f"[{attempted}/{args.max_attempts}] "
            f"{server['host']}:{server['port']}",
            flush=True,
        )

        try:
            rows, sent, algo, server_result = run_test(
                host=server['host'],
                port=server['port'],
                duration=args.duration,
                interval=args.interval,
                timeout=args.timeout,
                block_size=args.block_size,
                run_id=run_id,
                provider=server['provider'],
                country=server['country'],
                algorithm=args.algorithm,
            )

            if not rows:
                raise ProtocolError('No samples obtained')

            # Compute summary statistics from the goodput samples.
            speeds = [r['goodput_mbps'] for r in rows]
            summary = {
                'run_id': run_id,
                'host': server['host'],
                'port': server['port'],
                'provider': server['provider'],
                'country': server['country'],
                'algorithm': algo,
                'samples': len(rows),
                'bytes_sent': sent,
                'min_mbps': min(speeds),
                'median_mbps': statistics.median(speeds),
                'mean_mbps': statistics.mean(speeds),
                'p95_mbps': sorted(speeds)[
                    min(len(speeds) - 1, math.ceil(0.95 * len(speeds)) - 1)
                ],
            }

            # Write per-run output files.
            write_csv(args.output / f'{run_id}_samples.csv', rows, CSV_FIELDS)
            write_json(
                args.output / f'{run_id}_server_results.json', server_result
            )

            summaries.append(summary)
            successes.append({**summary, 'trace': rows})

            print(
                f"  OK {summary['mean_mbps']:.2f} Mbit/s",
                flush=True,
            )
            # Success — move to next server group (next destination).
            break

        except (OSError, ProtocolError, ValueError, UnicodeError, json.JSONDecodeError) as e:
            failure = {
                'run_id': run_id,
                'host': server['host'],
                'port': server['port'],
                'error': f'{type(e).__name__}: {e}',
            }
            failures.append(failure)
            print(
                f"  FAILED {failure['error']}",
                flush=True,
            )

    # ------------------------------------------------------------------
    # Write aggregate output files
    # ------------------------------------------------------------------
    summary_fields = [
        'run_id', 'host', 'port', 'provider', 'country',
        'algorithm', 'samples', 'bytes_sent',
        'min_mbps', 'median_mbps', 'mean_mbps', 'p95_mbps',
    ]
    write_csv(args.output / 'summary.csv', summaries, summary_fields)
    write_csv(
        args.output / 'failures.csv',
        failures,
        ['run_id', 'host', 'port', 'error'],
    )

    manifest = {
        'requested': args.destinations,
        'completed': len(successes),
        'shortfall': args.destinations - len(successes),
        'attempts': attempted,
        'seed': args.seed,
        'duration_s': args.duration,
        'interval_s': args.interval,
        'kernel': platform.release(),
        'selected': [{'host': x['host'], 'port': x['port']} for x in successes],
    }
    write_json(args.output / 'manifest.json', manifest)

    # ------------------------------------------------------------------
    # Generate visualization
    # ------------------------------------------------------------------
    if successes:
        plot_goodput(successes, args.output)

    # ------------------------------------------------------------------
    # Final status
    # ------------------------------------------------------------------
    print(
        f"Completed {len(successes)}/{args.destinations}; "
        f"attempts={attempted}; output={args.output}"
    )
    return 0 if len(successes) == args.destinations else 1


if __name__ == '__main__':
    raise SystemExit(main())

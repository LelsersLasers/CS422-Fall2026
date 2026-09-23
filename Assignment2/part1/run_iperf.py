"""Part 1 entry point: iPerf3 destination selection, test loop, and output.

This module performs the Part 1 experiment (assignment section 1):

    1. Load and shuffle the server candidate list.
    2. Iterate through candidates, running an iPerf3 test on each until the
       target number of successful destinations is reached or the global
       attempt limit is exhausted.
    3. Write per-run CSV/JSON output, an aggregate summary, and a manifest.

The raw per-run traces collected here are also reused by Part 2 (TCP stats
visualization) and Part 3 (algorithm comparison) so the full experiment can
be driven from a single entry point.

Output files (written under the given output directory):
    {run_id}_samples.csv          Per-interval TCP stats + goodput samples.
    {run_id}_server_results.json  Final iperf3 server-side result.
    summary.csv                   Per-run min/median/mean/p95 goodput.
    failures.csv                  Failed attempts and their errors.
    manifest.json                 Selection, configuration, and shortfall.

Usage (directly, for a quick smoke test):
    python3 -m part1.run_iperf -n 1 -d 3 -i 0.2
"""

import math
import platform
import random
import statistics
import uuid
from pathlib import Path
from typing import Optional

from .protocol import ProtocolError
from .run_test import run_test
from .tcp_stats import CSV_FIELDS
from .utils import expect_linux, load_servers, write_csv, write_json

SUMMARY_FIELDS = [
    'run_id', 'host', 'port', 'provider', 'country',
    'algorithm', 'samples', 'bytes_sent',
    'min_mbps', 'median_mbps', 'mean_mbps', 'p95_mbps',
]


def _summarize(rows: list[dict], run_id: str, server: dict,
               algo: str, sent: int) -> dict:
    """Build one summary row (min/median/mean/p95 of goodput) for a run."""
    speeds = [r['goodput_mbps'] for r in rows]
    return {
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


def attempt_tests(
    candidates: list[dict],
    destinations: int,
    max_attempts: int,
    duration: float,
    interval: float,
    timeout: float,
    block_size: int,
    algorithm: Optional[str],
    output: Path,
    verbose: bool = True,
) -> tuple[list[dict], list[dict], list[dict], int]:
    """Run iPerf3 tests against shuffled candidates until targets are met.

    Shared by Part 1 (default algorithm) and Part 3 (algorithm sweep): it
    tries candidates one at a time, keeping at most ``destinations``
    successes (one per distinct (host, port)) and at most ``max_attempts``
    total tries.

    Args:
        candidates: Shuffled, flattened (host, port) server dicts.
        destinations: Number of successful destinations to reach.
        max_attempts: Hard cap on total test attempts.
        duration: Per-test duration in seconds.
        interval: TCP stats sampling interval in seconds.
        timeout: Connection/read timeout in seconds.
        block_size: Data send block size in bytes.
        algorithm: Optional TCP congestion algorithm for the data socket.
        output: Directory to write per-run output files.

    Returns:
        Tuple of (successes, failures, summaries, attempts) where:
        - successes:  summary dicts, each with an extra 'trace' key holding
          the full per-interval sample list.
        - failures:   dicts with run_id, host, port, error.
        - summaries:  summary dicts without the trace.
        - attempts:   number of tests actually attempted.
    """
    output.mkdir(parents=True, exist_ok=True)

    successes: list[dict] = []
    failures: list[dict] = []
    summaries: list[dict] = []
    attempted = 0
    done = set()  # (host, port) pairs already successfully tested.

    for server in candidates:
        if len(successes) >= destinations:
            break
        if attempted >= max_attempts:
            break
        if (server['host'], server['port']) in done:
            continue

        attempted += 1
        run_id = uuid.uuid4().hex[:12]

        if verbose:
            print(
                f"[{attempted}/{max_attempts}] "
                f"{server['host']}:{server['port']}",
                flush=True,
            )

        try:
            rows, sent, algo, server_result = run_test(
                host=server['host'],
                port=server['port'],
                duration=duration,
                interval=interval,
                timeout=timeout,
                block_size=block_size,
                run_id=run_id,
                provider=server['provider'],
                country=server['country'],
                algorithm=algorithm,
            )

            if not rows:
                raise ProtocolError('No samples obtained')

            summary = _summarize(rows, run_id, server, algo, sent)

            write_csv(output / f'{run_id}_samples.csv', rows, CSV_FIELDS)
            write_json(
                output / f'{run_id}_server_results.json', server_result
            )

            summaries.append(summary)
            successes.append({**summary, 'trace': rows})
            done.add((server['host'], server['port']))

            if verbose:
                print(f"  OK {summary['mean_mbps']:.2f} Mbit/s", flush=True)

        except (OSError, ProtocolError, ValueError, UnicodeError) as e:
            failure = {
                'run_id': run_id,
                'host': server['host'],
                'port': server['port'],
                'error': f'{type(e).__name__}: {e}',
            }
            failures.append(failure)
            if verbose:
                print(f"  FAILED {failure['error']}", flush=True)

    return successes, failures, summaries, attempted


def write_aggregate(output: Path, summaries: list[dict],
                    failures: list[dict], manifest: dict) -> None:
    """Write the aggregate summary.csv, failures.csv, and manifest.json."""
    write_csv(output / 'summary.csv', summaries, SUMMARY_FIELDS)
    write_csv(
        output / 'failures.csv',
        failures,
        ['run_id', 'host', 'port', 'error'],
    )
    write_json(output / 'manifest.json', manifest)


def run_part1(
    servers: Path,
    output_dir: Path,
    destinations: int = 10,
    duration: float = 60,
    interval: float = 1.0,
    timeout: float = 15,
    max_attempts: int = 30,
    block_size: int = 131072,
    algorithm: Optional[str] = None,
    seed: Optional[int] = None,
) -> dict:
    """Run the Part 1 experiment and write all output files.

    Args:
        servers: Path to the JSON server list file.
        output_dir: Directory for CSV/JSON/PDF output (created if missing).
        destinations: Number of successful destinations to reach.
        duration: Per-test duration in seconds.
        interval: TCP stats sampling interval in seconds.
        timeout: Connection/read timeout in seconds.
        max_attempts: Maximum total test attempts.
        block_size: Data send block size in bytes (1..1048576).
        algorithm: Optional TCP congestion algorithm (Part 1 uses the OS
          default, e.g. CUBIC, when None).
        seed: Random seed for reproducible server selection.

    Returns:
        Manifest dict describing the run (also written to manifest.json).
    """
    expect_linux()

    rng = random.Random(seed)
    candidates = load_servers(servers, rng)
    if not candidates:
        raise ValueError('No valid server entries found in server list')

    successes, failures, summaries, attempted = attempt_tests(
        candidates=candidates,
        destinations=destinations,
        max_attempts=max_attempts,
        duration=duration,
        interval=interval,
        timeout=timeout,
        block_size=block_size,
        algorithm=algorithm,
        output=output_dir,
    )

    manifest = {
        'requested': destinations,
        'completed': len(successes),
        'shortfall': destinations - len(successes),
        'attempts': attempted,
        'seed': seed,
        'duration_s': duration,
        'interval_s': interval,
        'kernel': platform.release(),
        'selected': [
            {'host': x['host'], 'port': x['port']} for x in successes
        ],
    }
    write_aggregate(output_dir, summaries, failures, manifest)

    print(
        f"Part 1 completed {len(successes)}/{destinations}; "
        f"attempts={attempted}; output={output_dir}"
    )
    return manifest

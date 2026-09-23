"""Part 3: Compare CUBIC, Reno, and BBR (assignment section 3).

Strategy (per the assignment, all three algorithms must use the SAME
destinations, duration, and sampling interval):

    1. Selection pass: pick `destinations` reachable servers using the OS
       default algorithm (CUBIC on Linux). This pass also yields the CUBIC
       measurement set.
    2. Sweep passes: re-test the SAME selected (host, port) pairs with each
       of the remaining algorithms (Reno, BBR), in a fixed order.

Every pass reuses part 1's shared test loop; the actual algorithm in use is
queried from the data socket and recorded in every sample row, so a pass
whose algorithm was not loaded on the host kernel is visible in the output.

Output layout (under the given output directory):
    output/part3/{algo}_summary.csv      Per-run summaries for one algorithm.
    output/part3/{algo}/                 Per-run sample CSVs + server JSONs.
    output/part3/comparison_summary.csv  One row per (destination, algorithm):
                                         min/median/mean/p95 goodput + RTT.
    output/part3/manifest.json           Selection order, repetition count,
                                         kernel, and per-algorithm status.
"""

import platform
import random
from pathlib import Path
from typing import Optional

from part1.run_iperf import attempt_tests
from part1.utils import expect_linux, load_servers, write_csv, write_json

# Fixed comparison order; the first entry doubles as the selection pass.
ALGORITHMS = ['cubic', 'reno', 'bbr']


def _algo_pass(
    candidates: list[dict],
    algorithm: str,
    destinations: int,
    max_attempts: int,
    duration: float,
    interval: float,
    timeout: float,
    block_size: int,
    output: Path,
    verbose: bool = True,
) -> tuple[list[dict], list[dict], int]:
    """Run one algorithm over the given candidate list.

    Args:
        candidates: Servers to try (selection pass) or selected destinations
            (sweep passes).
        destinations: Stop after this many successes.
        max_attempts: Cap on total attempts for this pass.

    Returns (successes, failures, attempts).
    """
    algo_dir = output / algorithm
    successes, failures, _summaries, attempts = attempt_tests(
        candidates=candidates,
        destinations=min(destinations, len(candidates)),
        max_attempts=max_attempts,
        duration=duration,
        interval=interval,
        timeout=timeout,
        block_size=block_size,
        algorithm=algorithm,
        output=algo_dir,
        verbose=verbose,
    )
    return successes, failures, attempts


def _comparison_rows(successes_by_algo: dict[str, list[dict]]) -> list[dict]:
    """Flatten per-algorithm successes into one comparison row each."""
    rows = []
    for algo, successes in successes_by_algo.items():
        for s in successes:
            rows.append({
                'algorithm': s['algorithm'],  # actual algo reported by kernel
                'requested_algorithm': algo,
                'host': s['host'],
                'port': s['port'],
                'run_id': s['run_id'],
                'samples': s['samples'],
                'bytes_sent': s['bytes_sent'],
                'min_mbps': s['min_mbps'],
                'median_mbps': s['median_mbps'],
                'mean_mbps': s['mean_mbps'],
                'p95_mbps': s['p95_mbps'],
            })
    return rows


def run_part3(
    servers: Path,
    output_dir: Path,
    destinations: int = 10,
    duration: float = 60,
    interval: float = 1.0,
    timeout: float = 15,
    max_attempts: int = 30,
    block_size: int = 131072,
    seed: Optional[int] = None,
) -> dict:
    """Run the Part 3 congestion-control comparison.

    Returns:
        Manifest dict describing the run (also written to manifest.json).
    """
    expect_linux()

    output_dir.mkdir(parents=True, exist_ok=True)

    rng = random.Random(seed)
    candidates = load_servers(servers, rng)
    if not candidates:
        raise ValueError('No valid server entries found in server list')

    successes_by_algo: dict[str, list[dict]] = {}
    failures_by_algo: dict[str, list[dict]] = {}
    attempts_by_algo: dict[str, int] = {}
    selected: list[dict] = []

    # ------------------------------------------------------------------
    # Pass 1: selection (first algorithm, CUBIC / OS default).
    # ------------------------------------------------------------------
    print(f"Part 3: selecting {destinations} destinations (cubic pass)...")
    successes, failures, attempts = _algo_pass(
        candidates, 'cubic', destinations, max_attempts, duration,
        interval, timeout, block_size, output_dir,
    )
    successes_by_algo['cubic'] = successes
    failures_by_algo['cubic'] = failures
    attempts_by_algo['cubic'] = attempts
    selected = [
        {'host': s['host'], 'port': s['port'],
         'provider': s['provider'], 'country': s['country']}
        for s in successes
    ]

    if not selected:
        print("Part 3: no destinations reachable; aborting sweep.")
    else:
        # ----------------------------------------------------------------
        # Passes 2+: same selected destinations, other algorithms.
        # ----------------------------------------------------------------
        for algo in ALGORITHMS[1:]:
            print(f"Part 3: re-testing {len(selected)} destinations "
                  f"with '{algo}'...")
            successes, failures, attempts = _algo_pass(
                selected, algo, len(selected), max_attempts, duration,
                interval, timeout, block_size, output_dir,
            )
            successes_by_algo[algo] = successes
            failures_by_algo[algo] = failures
            attempts_by_algo[algo] = attempts

    # ------------------------------------------------------------------
    # Aggregate outputs
    # ------------------------------------------------------------------
    comparison = _comparison_rows(successes_by_algo)
    write_csv(
        output_dir / 'comparison_summary.csv',
        comparison,
        [
            'algorithm', 'requested_algorithm', 'host', 'port', 'run_id',
            'samples', 'bytes_sent',
            'min_mbps', 'median_mbps', 'mean_mbps', 'p95_mbps',
        ],
    )

    manifest = {
        'selected_destinations': selected,
        'algorithm_order': ALGORITHMS,
        'repetitions': 1,
        'duration_s': duration,
        'interval_s': interval,
        'seed': seed,
        'kernel': platform.release(),
        'attempts': attempts_by_algo,
        'completed': {
            algo: len(s) for algo, s in successes_by_algo.items()
        },
        'shortfall': {
            algo: (len(selected) - len(s))
            for algo, s in successes_by_algo.items()
        },
    }
    write_json(output_dir / 'manifest.json', manifest)

    print(
        "Part 3 completed; "
        f"selected={len(selected)}; "
        f"completed={manifest['completed']}; "
        f"output={output_dir}"
    )
    return manifest

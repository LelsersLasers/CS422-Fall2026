"""Part 3: Compare CUBIC, Reno, and BBR (assignment section 3a).

Strategy (per the assignment, all three algorithms must use the SAME
destinations, duration, and sampling interval, repeated over multiple runs):

    1. Destinations: reuse the destinations Part 1 reached (read from Part 1's
       summary.csv), so Parts 1-3 all describe the same paths. When Part 3 is
       run on its own, a selection pass with CUBIC picks reachable servers
       first; its traces are kept under part3/selection/ but are not counted
       in the comparison.
    2. Repetitions: for each repetition, every destination is tested with all
       three algorithms back to back. The algorithm order rotates by one each
       repetition (rep 0: cubic, reno, bbr; rep 1: reno, bbr, cubic; ...) so
       no algorithm is always measured first on a path. Running the three
       algorithms within ~3 minutes of each other on the same path limits how
       much changing Internet conditions bias the comparison. Each test is
       preceded by a short pause, and a refused/failed test is retried up to
       len(RETRY_DELAYS_S) times with increasing delays.

Every test reuses Part 1's single-test loop; the actual algorithm in use is
queried from the data socket and recorded in every sample row, so a pass
whose algorithm was not loaded on the host kernel is visible in the output.

Output layout (under the given output directory):
    {algo}/                          Per-run sample CSVs + server JSONs.
    selection/                       Selection-pass traces (standalone only).
    comparison_summary.csv           One row per (repetition, destination,
                                     algorithm): goodput percentiles, RTT,
                                     queueing delay, retransmissions, BDP.
    destination_algorithm_summary.csv  Per (destination, algorithm) mean/std
                                     across repetitions.
    algorithm_summary.csv            Per algorithm, across all runs.
    failures.csv                     Failed attempts (with repetition,
                                     algorithm, and retry attempt number).
    manifest.json                    Destinations, repetitions, test order,
                                     kernel, and per-algorithm status.
"""

import csv
import platform
import random
import statistics
import time
from pathlib import Path
from typing import Optional

from part1.run_iperf import attempt_tests
from part1.utils import expect_linux, load_servers, write_csv, write_json

# Base comparison order; rotated by one position each repetition.
ALGORITHMS = ['cubic', 'reno', 'bbr']

# Public iperf3 servers serve one client at a time and often refuse a new
# test for a few seconds after the previous one ends, so pause before each
# test and retry a failed test a bounded number of times.
PAUSE_BETWEEN_TESTS_S = 3
RETRY_DELAYS_S = [10, 30]

COMPARISON_FIELDS = [
    'repetition', 'order_position', 'algorithm', 'requested_algorithm',
    'host', 'port', 'provider', 'country', 'run_id', 'samples', 'bytes_sent',
    'min_mbps', 'median_mbps', 'mean_mbps', 'p95_mbps',
    'mean_rtt_ms', 'p95_rtt_ms', 'min_rtt_ms', 'queueing_delay_ms',
    'mean_cwnd_segments', 'max_cwnd_segments',
    'retrans_segments', 'retrans_pct', 'bdp_kbytes',
]

GROUP_FIELDS = [
    'runs', 'mean_mbps', 'std_mbps', 'min_run_mbps', 'max_run_mbps',
    'cv_pct', 'mean_rtt_ms', 'queueing_delay_ms', 'retrans_pct',
    'mean_cwnd_segments', 'bdp_kbytes',
]


def available_algorithms() -> Optional[set]:
    """Set of congestion-control algorithms available on this kernel.

    Reads /proc/sys/net/ipv4/tcp_available_congestion_control, which lists every
    algorithm the kernel can currently load.

    Returns:
        Set of algorithm names, or None if the proc file is unavailable
        (e.g., restricted container) and availability cannot be determined.
    """
    try:
        raw = Path('/proc/sys/net/ipv4/tcp_available_congestion_control').read_text()
    except OSError:
        return None
    return set(raw.split())


def rotated_order(algorithms: list[str], repetition: int) -> list[str]:
    """Algorithm order for a repetition: the base order rotated left."""
    k = repetition % len(algorithms)
    return algorithms[k:] + algorithms[:k]


def part1_destinations(part1_dir: Path) -> list[dict]:
    """Destinations Part 1 successfully tested, in Part 1's order."""
    summary = part1_dir / 'summary.csv'
    if not summary.exists():
        return []
    with open(summary, newline='', encoding='utf-8') as f:
        rows = list(csv.DictReader(f))
    selected, seen = [], set()
    for row in rows:
        key = (row['host'], int(row['port']))
        if key in seen:
            continue
        seen.add(key)
        selected.append({
            'host': row['host'], 'port': int(row['port']),
            'provider': row.get('provider', ''),
            'country': row.get('country', ''),
        })
    return selected


def _percentile(values: list[float], p: float) -> float:
    """Nearest-rank percentile (same convention as Part 1's p95)."""
    ordered = sorted(values)
    rank = max(1, -(-len(ordered) * p // 100))  # ceil(n * p / 100)
    return ordered[int(min(rank, len(ordered))) - 1]


def path_metrics(trace: list[dict]) -> dict:
    """Per-run RTT, queueing, cwnd, loss, and BDP metrics from a trace.

    - min_rtt_ms: kernel's tcpi_min_rtt at the end of the run, the best
      estimate of the propagation (no-queue) RTT of the path.
    - queueing_delay_ms: mean smoothed RTT minus min RTT, i.e. how much
      standing queue the algorithm kept in the bottleneck buffer.
    - retrans_pct: retransmitted bytes as a percentage of bytes sent by TCP
      (tcpi_bytes_retrans / tcpi_bytes_sent), the loss proxy for the run.
    - bdp_kbytes: bandwidth-delay product estimate = median goodput x min RTT.
    """
    rtt_ms = [float(r['rtt_us']) / 1000 for r in trace]
    cwnd = [float(r['snd_cwnd_segments']) for r in trace]
    goodput = [float(r['goodput_mbps']) for r in trace]
    last = trace[-1]

    min_rtt_ms = float(last.get('min_rtt_us') or 0) / 1000 or min(rtt_ms)
    mean_rtt_ms = statistics.mean(rtt_ms)
    sent = float(last.get('tcp_bytes_sent') or 0)
    retrans_bytes = float(last.get('bytes_retrans') or 0)
    median_bps = statistics.median(goodput) * 1e6

    return {
        'mean_rtt_ms': mean_rtt_ms,
        'p95_rtt_ms': _percentile(rtt_ms, 95),
        'min_rtt_ms': min_rtt_ms,
        'queueing_delay_ms': max(0.0, mean_rtt_ms - min_rtt_ms),
        'mean_cwnd_segments': statistics.mean(cwnd),
        'max_cwnd_segments': max(cwnd),
        'retrans_segments': sum(int(r['delta_retrans']) for r in trace),
        'retrans_pct': 100 * retrans_bytes / sent if sent else 0.0,
        'bdp_kbytes': median_bps / 8 * (min_rtt_ms / 1000) / 1000,
    }


def _group_summary(rows: list[dict]) -> dict:
    """Mean/variability of per-run results for one group of runs."""
    means = [r['mean_mbps'] for r in rows]
    mean = statistics.mean(means)
    std = statistics.stdev(means) if len(means) > 1 else 0.0
    return {
        'runs': len(rows),
        'mean_mbps': mean,
        'std_mbps': std,
        'min_run_mbps': min(means),
        'max_run_mbps': max(means),
        'cv_pct': 100 * std / mean if mean else 0.0,
        'mean_rtt_ms': statistics.mean(r['mean_rtt_ms'] for r in rows),
        'queueing_delay_ms': statistics.mean(
            r['queueing_delay_ms'] for r in rows
        ),
        'retrans_pct': statistics.mean(r['retrans_pct'] for r in rows),
        'mean_cwnd_segments': statistics.mean(
            r['mean_cwnd_segments'] for r in rows
        ),
        'bdp_kbytes': statistics.mean(r['bdp_kbytes'] for r in rows),
    }


def _select_destinations(
    servers: Path,
    output_dir: Path,
    destinations: int,
    max_attempts: int,
    duration: float,
    interval: float,
    timeout: float,
    block_size: int,
    seed: Optional[int],
    avail: Optional[set],
) -> list[dict]:
    """Standalone fallback: pick reachable destinations with a CUBIC pass."""
    rng = random.Random(seed)
    candidates = load_servers(servers, rng)
    if not candidates:
        raise ValueError('No valid server entries found in server list')

    algo = 'cubic' if avail is None or 'cubic' in avail else None
    print(f"Part 3: selecting {destinations} destinations "
          f"({algo or 'kernel default'} selection pass)...")
    successes, _failures, _summaries, _attempts = attempt_tests(
        candidates=candidates,
        destinations=destinations,
        max_attempts=max_attempts,
        duration=duration,
        interval=interval,
        timeout=timeout,
        block_size=block_size,
        algorithm=algo,
        output=output_dir / 'selection',
    )
    return [
        {'host': s['host'], 'port': s['port'],
         'provider': s['provider'], 'country': s['country']}
        for s in successes
    ]


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
    repetitions: int = 1,
    part1_dir: Optional[Path] = None,
) -> dict:
    """Run the Part 3 congestion-control comparison.

    Args:
        part1_dir: Directory holding Part 1's summary.csv; its destinations
            are reused. When missing or empty, a CUBIC selection pass picks
            `destinations` servers from `servers` instead.
        repetitions: Number of times each (destination, algorithm) pair is
            tested.

    Returns:
        Manifest dict describing the run (also written to manifest.json).
    """
    expect_linux()
    output_dir.mkdir(parents=True, exist_ok=True)

    avail = available_algorithms()
    algorithms = [a for a in ALGORITHMS if avail is None or a in avail]
    skipped = [a for a in ALGORITHMS if a not in algorithms]
    for algo in skipped:
        # The kernel would reject setsockopt(TCP_CONGESTION) with ENOENT.
        print(
            f"Part 3: algorithm '{algo}' is not available on this kernel "
            f"(available: {', '.join(sorted(avail))}); skipping it. Load it "
            f"(e.g., `sudo modprobe tcp_{algo}`) and re-run to include it."
        )

    selected = part1_destinations(part1_dir) if part1_dir else []
    source = 'part1'
    if not selected:
        source = 'selection_pass'
        selected = _select_destinations(
            servers, output_dir, destinations, max_attempts, duration,
            interval, timeout, block_size, seed, avail,
        )
    selected = selected[:destinations]

    rows: list[dict] = []
    failures: list[dict] = []
    test_order: list[dict] = []
    total = repetitions * len(selected) * len(algorithms)
    test_num = 0

    for rep in range(repetitions):
        order = rotated_order(algorithms, rep)
        test_order.append({'repetition': rep, 'algorithm_order': order})
        for dest in selected:
            for position, algo in enumerate(order):
                test_num += 1
                print(
                    f"Part 3 [{test_num}/{total}] "
                    f"rep {rep + 1}/{repetitions} {algo}:",
                    flush=True,
                )
                successes = []
                for attempt, delay in enumerate(
                    [PAUSE_BETWEEN_TESTS_S] + RETRY_DELAYS_S
                ):
                    if attempt:
                        print(f"  retrying in {delay} s "
                              f"({attempt}/{len(RETRY_DELAYS_S)})",
                              flush=True)
                    time.sleep(delay)
                    successes, fails, _summaries, _attempts = attempt_tests(
                        candidates=[dest],
                        destinations=1,
                        max_attempts=1,
                        duration=duration,
                        interval=interval,
                        timeout=timeout,
                        block_size=block_size,
                        algorithm=algo,
                        output=output_dir / algo,
                    )
                    for f in fails:
                        failures.append({
                            'repetition': rep, 'requested_algorithm': algo,
                            'attempt': attempt, **f,
                        })
                    if successes:
                        break
                for s in successes:
                    rows.append({
                        'repetition': rep,
                        'order_position': position,
                        'requested_algorithm': algo,
                        **{k: v for k, v in s.items() if k != 'trace'},
                        **path_metrics(s['trace']),
                    })

    # ------------------------------------------------------------------
    # Aggregate outputs
    # ------------------------------------------------------------------
    write_csv(output_dir / 'comparison_summary.csv', rows, COMPARISON_FIELDS)
    write_csv(
        output_dir / 'failures.csv', failures,
        ['repetition', 'requested_algorithm', 'attempt', 'run_id', 'host',
         'port', 'error'],
    )

    by_dest_algo: dict[tuple, list[dict]] = {}
    by_algo: dict[str, list[dict]] = {}
    for r in rows:
        algo = r['requested_algorithm']
        by_dest_algo.setdefault((r['host'], r['port'], algo), []).append(r)
        by_algo.setdefault(algo, []).append(r)

    write_csv(
        output_dir / 'destination_algorithm_summary.csv',
        [
            {'host': h, 'port': p, 'algorithm': a, **_group_summary(g)}
            for (h, p, a), g in by_dest_algo.items()
        ],
        ['host', 'port', 'algorithm'] + GROUP_FIELDS,
    )
    write_csv(
        output_dir / 'algorithm_summary.csv',
        [
            {'algorithm': a, **_group_summary(by_algo[a])}
            for a in algorithms if a in by_algo
        ],
        ['algorithm'] + GROUP_FIELDS,
    )

    expected = repetitions * len(selected)
    manifest = {
        'destination_source': source,
        'selected_destinations': selected,
        'algorithms': algorithms,
        'repetitions': repetitions,
        'test_order': test_order,
        'test_order_note': (
            'For each repetition, every destination is tested with all '
            'algorithms back to back in that repetition\'s algorithm_order.'
        ),
        'duration_s': duration,
        'interval_s': interval,
        'seed': seed,
        'kernel': platform.release(),
        'skipped': skipped,
        'completed': {a: len(by_algo.get(a, [])) for a in algorithms},
        'shortfall': {
            a: expected - len(by_algo.get(a, [])) for a in algorithms
        },
    }
    write_json(output_dir / 'manifest.json', manifest)

    print(
        "Part 3 completed; "
        f"destinations={len(selected)} ({source}); "
        f"repetitions={repetitions}; "
        f"completed={manifest['completed']}; "
        f"output={output_dir}"
    )
    return manifest

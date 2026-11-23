#!/usr/bin/env python3
"""Top-level entry point for CS 422 Assignment 5: Collective Communication.

Run directly from Assignment5/ or the repository root:
    python3 main.py smoke
    python3 main.py run --ranks 8 --operation allgather --algorithm ring --message-bytes 1024
    python3 main.py verify
    python3 main.py benchmark
    python3 main.py plot
    python3 main.py            # runs full pipeline: verify -> benchmark -> plot
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RESULTS_DIR = ROOT / "results"
DEFAULT_SMOKE_RANKS: tuple[int, ...] = (2, 4, 8)
DEFAULT_VERIFY_RANKS: tuple[int, ...] = (1, 2, 4, 8)
DEFAULT_BENCHMARK_RANKS: tuple[int, ...] = (2, 4, 8)


def build_torchrun_command(ranks: int, runner_args: Sequence[str]) -> list[str]:
    """Build a standalone single-machine torchrun command for src.runner."""
    if ranks < 1:
        raise ValueError(f"ranks must be >= 1, got {ranks}.")
    return [
        sys.executable,
        "-m",
        "torch.distributed.run",
        "--standalone",
        f"--nproc-per-node={ranks}",
        "-m",
        "src.runner",
        *runner_args,
    ]


def launch_runner(ranks: int, runner_args: Sequence[str]) -> int:
    """Execute src.runner with the requested number of Gloo ranks."""
    cmd = build_torchrun_command(ranks, runner_args)
    completed = subprocess.run(cmd, cwd=ROOT, check=False)
    return completed.returncode


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level CLI parser."""
    parser = argparse.ArgumentParser(
        description="Run CS 422 Assignment 5 smoke tests, verification, benchmarks, and plots."
    )
    subparsers = parser.add_subparsers(dest="command")

    smoke_p = subparsers.add_parser(
        "smoke", help="Run Gloo P2P smoke test across rank counts (default: 2 4 8)."
    )
    smoke_p.add_argument(
        "--ranks", type=int, nargs="+", default=list(DEFAULT_SMOKE_RANKS)
    )
    smoke_p.add_argument("--message-bytes", type=int, default=64)

    run_p = subparsers.add_parser(
        "run", help="Run a single collective operation via torchrun."
    )
    run_p.add_argument("--ranks", type=int, required=True)
    run_p.add_argument(
        "--operation", required=True, choices=("allgather", "broadcast")
    )
    run_p.add_argument("--algorithm", required=True)
    run_p.add_argument("--message-bytes", type=int, default=1024)
    run_p.add_argument("--iterations", type=int, default=1)
    run_p.add_argument("--root", type=int, default=0)
    run_p.add_argument("--verify", action="store_true")

    verify_p = subparsers.add_parser(
        "verify", help="Run Member 3 correctness suite across rank counts."
    )
    verify_p.add_argument(
        "--ranks", type=int, nargs="+", default=list(DEFAULT_VERIFY_RANKS)
    )

    bench_p = subparsers.add_parser(
        "benchmark", help="Run Member 4 benchmark sweeps across rank counts."
    )
    bench_p.add_argument(
        "--ranks", type=int, nargs="+", default=list(DEFAULT_BENCHMARK_RANKS)
    )

    plot_p = subparsers.add_parser(
        "plot", help="Generate Member 4 plots from results CSVs."
    )
    plot_p.add_argument("--results-dir", type=Path, default=RESULTS_DIR)
    plot_p.add_argument("--output-dir", type=Path, default=RESULTS_DIR)

    subparsers.add_parser(
        "all", help="Run full pipeline: verify -> benchmark -> plot (default)."
    )
    return parser


def run_smoke(ranks_list: Sequence[int], message_bytes: int) -> int:
    for ranks in ranks_list:
        rc = launch_runner(
            ranks, ["--operation", "smoke", "--message-bytes", str(message_bytes)]
        )
        if rc != 0:
            return rc
    return 0


def run_verify(ranks_list: Sequence[int]) -> int:
    for ranks in ranks_list:
        rc = launch_runner(ranks, ["--operation", "verify"])
        if rc != 0:
            return rc
    return 0


def run_benchmarks(ranks_list: Sequence[int]) -> int:
    for ranks in ranks_list:
        rc = launch_runner(ranks, ["--operation", "benchmark"])
        if rc != 0:
            return rc
    return 0


def run_plots(results_dir: Path, output_dir: Path) -> int:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from src.plot_results import generate_plots

    generate_plots(results_dir=results_dir, output_dir=output_dir)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    command = args.command or "all"

    if command == "smoke":
        return run_smoke(args.ranks, args.message_bytes)

    if command == "run":
        runner_args = [
            "--operation",
            args.operation,
            "--algorithm",
            args.algorithm,
            "--message-bytes",
            str(args.message_bytes),
            "--iterations",
            str(args.iterations),
            "--root",
            str(args.root),
        ]
        if args.verify:
            runner_args.append("--verify")
        return launch_runner(args.ranks, runner_args)

    if command == "verify":
        return run_verify(args.ranks)

    if command == "benchmark":
        return run_benchmarks(args.ranks)

    if command == "plot":
        return run_plots(args.results_dir, args.output_dir)

    if command == "all":
        rc = run_verify(DEFAULT_VERIFY_RANKS)
        if rc != 0:
            return rc
        rc = run_benchmarks(DEFAULT_BENCHMARK_RANKS)
        if rc != 0:
            return rc
        return run_plots(RESULTS_DIR, RESULTS_DIR)

    parser.error(f"Unknown command: {command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

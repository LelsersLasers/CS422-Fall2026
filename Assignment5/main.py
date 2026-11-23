#!/usr/bin/env python3
"""Top-level runner for Assignment 5 (smoke, verify, benchmark, plot, all)."""

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def torchrun(ranks: int, *runner_args: str) -> None:
    cmd = [
        sys.executable,
        "-m",
        "torch.distributed.run",
        "--standalone",
        f"--nproc-per-node={ranks}",
        "-m",
        "src.runner",
        *runner_args,
    ]
    subprocess.run(cmd, cwd=ROOT, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Assignment 5 workflows.")
    parser.add_argument(
        "mode",
        nargs="?",
        default="all",
        choices=("smoke", "verify", "benchmark", "plot", "all"),
    )
    parser.add_argument("--ranks", type=int, nargs="+", default=[2, 4, 8])
    parser.add_argument("--message-bytes", type=int, default=64)
    args = parser.parse_args()

    if args.mode == "smoke":
        for p in args.ranks:
            torchrun(p, "--operation", "smoke", "--message-bytes", str(args.message_bytes))
        return

    if args.mode in ("verify", "all"):
        for p in args.ranks:
            torchrun(p, "--operation", "verify")
    if args.mode in ("benchmark", "all"):
        for p in args.ranks:
            torchrun(p, "--operation", "benchmark")
    if args.mode in ("plot", "all"):
        sys.path.insert(0, str(ROOT))
        from src.plot_results import generate_plots

        generate_plots(ROOT / "results", ROOT / "results")


if __name__ == "__main__":
    main()

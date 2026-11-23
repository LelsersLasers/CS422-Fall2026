"""Benchmark runner and CSV/metadata writers (Member 4)."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path

import torch

CSV_COLUMNS: tuple[str, ...] = (
    "operation",
    "algorithm",
    "world_size",
    "message_bytes",
    "iteration",
    "completion_seconds",
)

DEFAULT_MESSAGE_SIZES: tuple[int, ...] = (
    1024,        # 1 KiB
    4096,        # 4 KiB
    16384,       # 16 KiB
    65536,       # 64 KiB
    262144,      # 256 KiB
    1048576,     # 1 MiB
    4194304,     # 4 MiB
    16777216,    # 16 MiB
    67108864,    # 64 MiB
)


def collect_environment_metadata(
    world_size: int,
    launch_command: str,
) -> dict[str, object]:
    """Collect machine CPU, RAM, OS, Python, and PyTorch version metadata.

    TODO (Member 4):
        Record machine specs and launch command into a JSON sidecar file.
    """
    raise NotImplementedError(
        "collect_environment_metadata is awaiting Member 4 implementation."
    )


def time_collective(
    fn: Callable[[], torch.Tensor],
    rank: int,
    warmup_iters: int = 5,
    measured_iters: int = 20,
) -> list[float]:
    """Measure collective completion time across iterations.

    TODO (Member 4):
        1. Run warmup_iters untimed iterations.
        2. For each measured iteration:
           - dist.barrier() before starting timer
           - t0 = time.perf_counter(); fn(); elapsed = time.perf_counter() - t0
           - collect max(elapsed) across ranks via dist.all_reduce(MAX) outside timer
        3. Return per-iteration max completion times (in seconds).
    """
    raise NotImplementedError("time_collective is awaiting Member 4 implementation.")


def write_benchmark_csv(
    rows: Sequence[dict[str, object]],
    output_path: Path,
) -> None:
    """Write tidy benchmark records with CSV_COLUMNS header (rank 0 only)."""
    raise NotImplementedError(
        "write_benchmark_csv is awaiting Member 4 implementation."
    )


def run_benchmark(
    rank: int,
    world_size: int,
    operation: str,
    algorithms: Sequence[str],
    message_sizes: Sequence[int] = DEFAULT_MESSAGE_SIZES,
    warmup_iters: int = 5,
    measured_iters: int = 20,
    output_dir: Path = Path("results"),
) -> None:
    """Run benchmark sweeps for the given operation/algorithms and save CSV + metadata."""
    raise NotImplementedError("run_benchmark is awaiting Member 4 implementation.")

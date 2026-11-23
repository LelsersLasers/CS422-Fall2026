"""Benchmark runner."""

CSV_COLUMNS = (
    "operation",
    "algorithm",
    "world_size",
    "message_bytes",
    "iteration",
    "completion_seconds",
)


def run_benchmark(rank: int, world_size: int) -> None:
    """Run benchmark sweeps and save CSV + environment metadata to results/."""
    raise NotImplementedError("run_benchmark not implemented yet")

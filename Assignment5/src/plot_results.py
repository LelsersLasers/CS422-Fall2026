"""Plot generation from benchmark CSVs (Member 4)."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

PLOT_FILENAMES: dict[str, str] = {
    "allgather_vs_size": "allgather_vs_message_size.pdf",
    "broadcast_vs_size": "broadcast_vs_message_size.pdf",
    "allgather_vs_ranks": "allgather_vs_ranks.pdf",
    "broadcast_vs_ranks": "broadcast_vs_ranks.pdf",
}


def load_benchmark_csv(csv_path: Path) -> list[dict[str, str]]:
    """Load tidy benchmark CSV rows from disk."""
    raise NotImplementedError("load_benchmark_csv is awaiting Member 4 implementation.")


def plot_vs_message_size(
    rows: Sequence[dict[str, str]],
    operation: str,
    output_path: Path,
) -> None:
    """Plot median completion time vs. message size (log-scale x-axis) for all algorithms."""
    raise NotImplementedError(
        "plot_vs_message_size is awaiting Member 4 implementation."
    )


def plot_vs_ranks(
    rows: Sequence[dict[str, str]],
    operation: str,
    output_path: Path,
) -> None:
    """Plot median completion time vs. number of ranks for all algorithms."""
    raise NotImplementedError("plot_vs_ranks is awaiting Member 4 implementation.")


def generate_plots(results_dir: Path, output_dir: Path) -> None:
    """Generate all four required comparison plots from collected CSV data.

    TODO (Member 4):
        1. AllGather time vs. message size (fixed ranks, e.g. p=8)
        2. Broadcast time vs. message size (fixed ranks, e.g. p=8)
        3. AllGather time vs. number of ranks (fixed message size, e.g. 1 MiB)
        4. Broadcast time vs. number of ranks (fixed message size, e.g. 1 MiB)
    """
    raise NotImplementedError("generate_plots is awaiting Member 4 implementation.")

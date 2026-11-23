"""Recursive Doubling AllGather."""

import torch


def allgather_recursive(local_data: torch.Tensor, rank: int, world_size: int) -> torch.Tensor:
    """Return a 1D tensor with all per-rank inputs concatenated in rank order."""
    raise NotImplementedError("allgather_recursive not implemented yet")

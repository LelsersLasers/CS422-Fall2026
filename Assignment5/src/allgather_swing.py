"""Swing AllGather (Member 3)."""

import torch


def allgather_swing(local_data: torch.Tensor, rank: int, world_size: int) -> torch.Tensor:
    """Return a 1D tensor with all per-rank inputs concatenated in rank order."""
    raise NotImplementedError("allgather_swing not implemented yet (Member 3)")

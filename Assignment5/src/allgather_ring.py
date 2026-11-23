"""Ring AllGather."""

import torch


def allgather_ring(local_data: torch.Tensor, rank: int, world_size: int) -> torch.Tensor:
    """Return a 1D tensor with all per-rank inputs concatenated in rank order."""
    raise NotImplementedError("allgather_ring not implemented yet")

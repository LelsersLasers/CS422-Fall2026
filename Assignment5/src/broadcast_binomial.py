"""Binomial Tree Broadcast."""

import torch


def broadcast_binomial(data: torch.Tensor, rank: int, world_size: int, root: int = 0) -> torch.Tensor:
    """Return the root's 1D tensor on every rank."""
    raise NotImplementedError("broadcast_binomial not implemented yet")

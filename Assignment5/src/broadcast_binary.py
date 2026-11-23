"""Binary Tree Broadcast (Member 1)."""

import torch


def broadcast_binary(data: torch.Tensor, rank: int, world_size: int, root: int = 0) -> torch.Tensor:
    """Return the root's 1D tensor on every rank."""
    raise NotImplementedError("broadcast_binary not implemented yet (Member 1)")

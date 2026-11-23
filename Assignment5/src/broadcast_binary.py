"""Binary Tree Broadcast (Member 1)."""

from __future__ import annotations

import torch


def broadcast_binary(
    data: torch.Tensor,
    rank: int,
    world_size: int,
    root: int = 0,
) -> torch.Tensor:
    """Return the root's 1D tensor on every rank using a binary tree.

    Contract:
        - data is a 1D contiguous CPU tensor (default dtype torch.uint8).
        - Does not modify data; allocates its own output/receive buffers.
        - Must use point-to-point Gloo isend/irecv/wait (no dist.broadcast).
        - Defaults to root=0; either remap logical ranks or explicitly reject root != 0.

    TODO (Member 1):
        1. Call validate_collective_input(data, rank, world_size, root=root).
        2. Handle world_size == 1 by returning data.clone().
        3. Use heap-indexed tree: parent = (r - 1) // 2, left = 2*r + 1, right = 2*r + 2.
        4. Non-root ranks irecv+wait from parent; root starts with data.clone().
        5. Forward via isend to valid children (< world_size) and wait() before returning.
    """
    raise NotImplementedError("broadcast_binary is awaiting Member 1 implementation.")

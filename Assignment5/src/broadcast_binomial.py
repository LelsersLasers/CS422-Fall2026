"""Binomial Tree Broadcast (Member 2)."""

from __future__ import annotations

import torch


def broadcast_binomial(
    data: torch.Tensor,
    rank: int,
    world_size: int,
    root: int = 0,
) -> torch.Tensor:
    """Return the root's 1D tensor on every rank using a binomial tree.

    Contract:
        - data is a 1D contiguous CPU tensor (default dtype torch.uint8).
        - Does not modify data; allocates its own output/receive buffers.
        - Must use point-to-point Gloo isend/irecv/wait (no dist.broadcast).
        - Supports arbitrary world_size >= 1 via bounds checks.
        - Defaults to root=0; use logical rank remapping or explicitly reject root != 0.

    TODO (Member 2):
        1. Call validate_collective_input(data, rank, world_size, root=root).
        2. Handle world_size == 1 by returning data.clone().
        3. Optionally remap logical = (rank - root + world_size) % world_size.
        4. Doubling frontier: mask = 1; while mask < world_size:
           - if logical < mask and logical + mask < world_size: isend to dst
           - elif mask <= logical < 2 * mask: irecv from src and wait()
           - wait() on all sends before returning.
    """
    raise NotImplementedError(
        "broadcast_binomial is awaiting Member 2 implementation."
    )

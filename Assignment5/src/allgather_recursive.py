"""Recursive Doubling AllGather (Member 2)."""

from __future__ import annotations

import torch


def allgather_recursive(
    local_data: torch.Tensor,
    rank: int,
    world_size: int,
) -> torch.Tensor:
    """Return a 1D tensor with all per-rank inputs concatenated in rank order.

    Contract:
        - local_data is a 1D contiguous CPU tensor (default dtype torch.uint8).
        - Does not modify local_data; allocates its own output/receive buffers.
        - Must use point-to-point Gloo isend/irecv/wait (no dist.all_gather).
        - Power-of-two world_size (1, 2, 4, 8, ...); explicitly reject unsupported counts.

    TODO (Member 2):
        1. Call validate_collective_input(local_data, rank, world_size).
        2. Validate is_power_of_two(world_size) and raise ValueError with clear message otherwise.
        3. Handle world_size == 1 by returning local_data.clone().
        4. Run k = log2(world_size) rounds:
           - partner = rank ^ (1 << s)
           - exchange all blocks accumulated so far via irecv + isend + wait()
           - merge received blocks into output buffer by original source rank.
        5. Return 1D tensor ordered by ascending source rank.
    """
    raise NotImplementedError(
        "allgather_recursive is awaiting Member 2 implementation."
    )

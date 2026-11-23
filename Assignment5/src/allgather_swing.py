"""Swing AllGather — 1D bandwidth-optimized AllGather phase (Member 3).

Reference:
    De Sensi et al., "Swing: Short-cutting Rings for Higher Bandwidth Allreduce",
    NSDI 2024 (https://www.usenix.org/conference/nsdi24/presentation/de-sensi).
"""

from __future__ import annotations

import torch


def swing_rho(step: int) -> int:
    """Return the Swing 1D distance offset rho(s) = (1 - (-2)**(s + 1)) // 3.

    TODO (Member 3):
        Verify exact indexing convention against the NSDI 2024 Swing paper.
    """
    raise NotImplementedError("swing_rho is awaiting Member 3 implementation.")


def swing_partner(rank: int, step: int, world_size: int) -> int:
    """Return the Swing partner rank for `rank` at round `step`.

    TODO (Member 3):
        Even rank -> (rank + rho(step)) % world_size
        Odd rank  -> (rank - rho(step)) % world_size
    """
    raise NotImplementedError("swing_partner is awaiting Member 3 implementation.")


def allgather_swing(
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

    TODO (Member 3):
        1. Call validate_collective_input(local_data, rank, world_size).
        2. Validate is_power_of_two(world_size) and raise ValueError otherwise.
        3. Implement the 1D bandwidth-optimized Swing AllGather expansion schedule
           (confirm exact step order and transmitted chunk subsets from the paper
           and record the p=8 schedule table in docs/member3_swing.md).
        4. Place received chunks into ascending source-rank order and return 1D tensor.
    """
    raise NotImplementedError("allgather_swing is awaiting Member 3 implementation.")

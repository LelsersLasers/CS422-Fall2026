"""Ring AllGather (Member 1)."""

from __future__ import annotations

import torch


def allgather_ring(
    local_data: torch.Tensor,
    rank: int,
    world_size: int,
) -> torch.Tensor:
    """Return a 1D tensor with all per-rank inputs concatenated in rank order.

    Contract:
        - local_data is a 1D contiguous CPU tensor (default dtype torch.uint8).
        - Does not modify local_data; allocates its own output/receive buffers.
        - Must use point-to-point Gloo isend/irecv/wait (no dist.all_gather).
        - Should support arbitrary world_size >= 1.

    TODO (Member 1):
        1. Call validate_collective_input(local_data, rank, world_size).
        2. Handle world_size == 1 by returning local_data.clone().
        3. Allocate output blocks (length world_size * local_data.numel()) and copy local_data into slot `rank`.
        4. Run (world_size - 1) rounds:
           - send block (rank - s) % world_size to (rank + 1) % world_size
           - recv block (rank - s - 1) % world_size from (rank - 1 + world_size) % world_size
           - post irecv and isend before waiting; keep outgoing buffer alive until wait() finishes.
        5. Return concatenated 1D tensor in ascending rank order.
    """
    raise NotImplementedError("allgather_ring is awaiting Member 1 implementation.")

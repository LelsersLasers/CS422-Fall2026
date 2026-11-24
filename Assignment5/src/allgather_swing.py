"""Bandwidth-optimized 1D Swing AllGather (De Sensi et al., NSDI '24).

For p = 2^k ranks, Swing runs k = log2(p) rounds in reverse step order
s = k - 1, k - 2, ..., 0 (the expansion dual of Swing Reduce-Scatter):

    rho(s) = (1 - (-2)**(s + 1)) // 3
    partner(r, s) = (r + rho(s)) % p   if r is even
                  = (r - rho(s)) % p   if r is odd

At round t (step s = k - 1 - t), each rank exchanges all 2^t blocks it
currently holds with partner(r, s). Small payloads travel longer hops first
and the largest payload (p/2 blocks) travels distance 1 in the final round.

Schedule for p = 8 (k = 3):
  Round 0 (s=2, rho=+3): 0<->3 [0]/[3], 1<->6 [1]/[6], 2<->5 [2]/[5], 4<->7 [4]/[7]
  Round 1 (s=1, rho=-1): 0<->7 [0,3]/[4,7], 1<->2 [1,6]/[2,5], 3<->4 [0,3]/[4,7], 5<->6 [2,5]/[1,6]
  Round 2 (s=0, rho=+1): 0<->1, 2<->3, 4<->5, 6<->7 exchanging [0,3,4,7] <-> [1,2,5,6]
"""

import torch
import torch.distributed as dist

from src.common import is_power_of_two


def swing_rho(step: int) -> int:
    """Return the signed 1D Swing hop distance rho(step) = (1 - (-2)^(step+1)) / 3."""
    return (1 - (-2) ** (step + 1)) // 3


def swing_partner(rank: int, step: int, world_size: int) -> int:
    """Return the 1D Swing partner of `rank` at `step`."""
    distance = swing_rho(step)
    if rank % 2 == 0:
        return (rank + distance) % world_size
    return (rank - distance) % world_size


def allgather_swing(local_data: torch.Tensor, rank: int, world_size: int) -> torch.Tensor:
    """Return a 1D tensor with all per-rank inputs concatenated in rank order."""
    if not is_power_of_two(world_size):
        raise ValueError(f"allgather_swing requires power-of-two world_size, got {world_size}")
    if local_data.ndim != 1:
        raise ValueError(f"allgather_swing expects a 1D tensor, got shape {tuple(local_data.shape)}")

    src = local_data.contiguous()
    if world_size == 1:
        return src.clone()

    block_len = src.numel()
    if block_len == 0:
        return torch.empty(0, dtype=src.dtype, device=src.device)

    out = torch.empty((world_size, block_len), dtype=src.dtype, device=src.device)
    out[rank].copy_(src)

    steps = world_size.bit_length() - 1
    held = [[r] for r in range(world_size)]

    for s in range(steps - 1, -1, -1):
        peer = swing_partner(rank, s, world_size)
        send_ids = held[rank]
        recv_ids = held[peer]

        send_buf = out[send_ids].contiguous()
        recv_buf = torch.empty((len(recv_ids), block_len), dtype=src.dtype, device=src.device)

        recv_req = dist.irecv(recv_buf, src=peer)
        send_req = dist.isend(send_buf, dst=peer)
        assert recv_req is not None and send_req is not None
        recv_req.wait()
        send_req.wait()

        out[recv_ids] = recv_buf
        held = [sorted(held[r] + held[swing_partner(r, s, world_size)]) for r in range(world_size)]

    return out.reshape(-1)

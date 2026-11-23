"""Shared helpers and Gloo P2P smoke test."""

import torch
import torch.distributed as dist


def is_power_of_two(n: int) -> bool:
    return n > 0 and (n & (n - 1)) == 0


def make_rank_buffer(rank: int, message_bytes: int) -> torch.Tensor:
    """Return a deterministic contiguous 1D uint8 CPU tensor for the given rank."""
    return ((torch.arange(message_bytes, dtype=torch.int64) + rank) % 256).to(torch.uint8).contiguous()


def p2p_smoke_test(rank: int, world_size: int, message_bytes: int = 16) -> bool:
    """Verify rank-0-to-rank-1 Gloo isend/irecv/wait."""
    ok = 1
    if world_size >= 2:
        expected = make_rank_buffer(0, message_bytes)
        if rank == 0:
            send_buf = expected.clone()
            req = dist.isend(send_buf, dst=1)
            assert req is not None
            req.wait()
        elif rank == 1:
            recv_buf = torch.empty_like(expected)
            req = dist.irecv(recv_buf, src=0)
            assert req is not None
            req.wait()
            ok = int(torch.equal(recv_buf, expected))

    dist.barrier()
    status = torch.tensor([ok], dtype=torch.int64)
    dist.all_reduce(status, op=dist.ReduceOp.MIN)
    return bool(status.item() == 1)

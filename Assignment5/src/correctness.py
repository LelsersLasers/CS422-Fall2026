"""Independent correctness validation harness for Assignment 5 collectives."""

from typing import Callable

import torch
import torch.distributed as dist

from src.common import make_rank_buffer

DEFAULT_SIZES = (1, 17, 1024, 65536, 1048576)


def _sync_ok(local_ok: bool) -> bool:
    status = torch.tensor([1 if local_ok else 0], dtype=torch.int64)
    dist.all_reduce(status, op=dist.ReduceOp.MIN)
    return bool(status.item() == 1)


def _check_output(
    actual: torch.Tensor,
    expected: torch.Tensor,
    inp: torch.Tensor,
    inp_snapshot: torch.Tensor,
    label: str,
    rank: int,
) -> str | None:
    if not torch.equal(inp, inp_snapshot):
        return f"{label} rank {rank}: input buffer was mutated"
    if actual.ndim != 1 or not actual.is_contiguous():
        return f"{label} rank {rank}: output must be 1D contiguous (shape={tuple(actual.shape)})"
    if actual.dtype != expected.dtype or actual.shape != expected.shape:
        return (
            f"{label} rank {rank}: got dtype={actual.dtype} shape={tuple(actual.shape)}, "
            f"expected dtype={expected.dtype} shape={tuple(expected.shape)}"
        )
    if not torch.equal(actual, expected):
        idx = int((actual != expected).nonzero(as_tuple=False)[0].item())
        return (
            f"{label} rank {rank}: first mismatch at index {idx} "
            f"(got {int(actual[idx].item())}, expected {int(expected[idx].item())})"
        )
    return None


def verify_allgather(
    name: str,
    fn: Callable[[torch.Tensor, int, int], torch.Tensor],
    rank: int,
    world_size: int,
    sizes: tuple[int, ...] = DEFAULT_SIZES,
) -> str:
    """Verify one AllGather implementation across message sizes on all ranks."""
    for size in sizes:
        local_data = make_rank_buffer(rank, size)
        snapshot = local_data.clone()
        expected = torch.cat([make_rank_buffer(r, size) for r in range(world_size)])

        gloo_chunks = [torch.empty_like(local_data) for _ in range(world_size)]
        dist.all_gather(gloo_chunks, local_data)
        assert torch.equal(expected, torch.cat(gloo_chunks))

        dist.barrier()
        try:
            actual = fn(local_data, rank, world_size)
        except NotImplementedError:
            return "SKIP (not implemented)"
        except ValueError as exc:
            return f"SKIP ({exc})"

        err = _check_output(actual, expected, local_data, snapshot, f"allgather/{name} ({size}B)", rank)
        if err is not None:
            print(f"[verify] FAIL: {err}", flush=True)
        if not _sync_ok(err is None):
            return "FAIL"

    return "PASS"


def verify_broadcast(
    name: str,
    fn: Callable[[torch.Tensor, int, int, int], torch.Tensor],
    rank: int,
    world_size: int,
    sizes: tuple[int, ...] = DEFAULT_SIZES,
    root: int = 0,
) -> str:
    """Verify one Broadcast implementation across message sizes on all ranks."""
    for size in sizes:
        local_data = make_rank_buffer(rank, size)
        snapshot = local_data.clone()
        expected = make_rank_buffer(root, size)

        gloo_buf = local_data.clone()
        dist.broadcast(gloo_buf, src=root)
        assert torch.equal(expected, gloo_buf)

        dist.barrier()
        try:
            actual = fn(local_data, rank, world_size, root)
        except NotImplementedError:
            return "SKIP (not implemented)"
        except ValueError as exc:
            return f"SKIP ({exc})"

        err = _check_output(actual, expected, local_data, snapshot, f"broadcast/{name} ({size}B)", rank)
        if err is not None:
            print(f"[verify] FAIL: {err}", flush=True)
        if not _sync_ok(err is None):
            return "FAIL"

    return "PASS"


def run_verification_suite(rank: int, world_size: int) -> bool:
    """Verify all five collective implementations across ranks."""
    from src.runner import ALLGATHER, BROADCAST

    all_ok = True
    for name, ag_fn in ALLGATHER.items():
        status = verify_allgather(name, ag_fn, rank, world_size)
        if rank == 0:
            print(f"[verify] world_size={world_size} allgather/{name}: {status}", flush=True)
        if status == "FAIL":
            all_ok = False

    for name, bcast_fn in BROADCAST.items():
        status = verify_broadcast(name, bcast_fn, rank, world_size)
        if rank == 0:
            print(f"[verify] world_size={world_size} broadcast/{name}: {status}", flush=True)
        if status == "FAIL":
            all_ok = False

    dist.barrier()
    return _sync_ok(all_ok)

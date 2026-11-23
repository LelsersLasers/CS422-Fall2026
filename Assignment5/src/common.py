"""Shared contracts, Gloo lifecycle helpers, and P2P smoke test."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager

import torch
import torch.distributed as dist

DEFAULT_DTYPE: torch.dtype = torch.uint8
DEFAULT_ROOT: int = 0
INITIAL_RANK_MATRIX: tuple[int, ...] = (2, 4, 8)

AllGatherFn = Callable[[torch.Tensor, int, int], torch.Tensor]
BroadcastFn = Callable[[torch.Tensor, int, int, int], torch.Tensor]


def init_distributed(backend: str = "gloo") -> tuple[int, int]:
    """Initialize the PyTorch distributed process group and return (rank, world_size)."""
    if backend == "gloo" and not dist.is_gloo_available():
        raise RuntimeError("PyTorch was built without Gloo backend support.")
    if not dist.is_initialized():
        dist.init_process_group(backend=backend)
    return dist.get_rank(), dist.get_world_size()


def destroy_distributed() -> None:
    """Tear down the active distributed process group if initialized."""
    if dist.is_initialized():
        dist.destroy_process_group()


@contextmanager
def distributed_context(backend: str = "gloo") -> Iterator[tuple[int, int]]:
    """Context manager guaranteeing init_process_group and destroy_process_group."""
    rank, world_size = init_distributed(backend=backend)
    try:
        yield rank, world_size
    finally:
        destroy_distributed()


def rank0_print(rank: int, *args: object, **kwargs: object) -> None:
    """Print only from rank 0 to avoid interleaved multi-rank output."""
    if rank == 0:
        print(*args, **kwargs)  # type: ignore[call-overload]


def is_power_of_two(value: int) -> bool:
    """Return True if value is a positive power of two."""
    return value > 0 and (value & (value - 1)) == 0


def validate_collective_input(
    tensor: torch.Tensor,
    rank: int,
    world_size: int,
    *,
    root: int | None = None,
) -> None:
    """Validate shared collective tensor and rank invariants."""
    if tensor.ndim != 1:
        raise ValueError(f"Expected 1D tensor, got {tensor.ndim}D tensor.")
    if tensor.device.type != "cpu":
        raise ValueError(f"Expected CPU tensor, got device '{tensor.device}'.")
    if not tensor.is_contiguous():
        raise ValueError("Expected contiguous tensor.")
    if world_size < 1:
        raise ValueError(f"world_size must be >= 1, got {world_size}.")
    if not (0 <= rank < world_size):
        raise ValueError(f"rank must satisfy 0 <= rank < {world_size}, got {rank}.")
    if root is not None and not (0 <= root < world_size):
        raise ValueError(f"root must satisfy 0 <= root < {world_size}, got {root}.")


def make_rank_buffer(
    rank: int,
    message_bytes: int,
    dtype: torch.dtype = DEFAULT_DTYPE,
) -> torch.Tensor:
    """Create a deterministic, contiguous 1D CPU tensor for the given rank."""
    if message_bytes < 1:
        raise ValueError(f"message_bytes must be >= 1, got {message_bytes}.")
    if dtype == torch.uint8:
        pattern = (torch.arange(message_bytes, dtype=torch.int64) + rank) % 256
        return pattern.to(torch.uint8).contiguous()
    return torch.full((message_bytes,), rank, dtype=dtype).contiguous()


def run_p2p_smoke_test(
    rank: int,
    world_size: int,
    message_bytes: int = 16,
) -> bool:
    """Verify basic Gloo point-to-point isend/irecv/wait between rank 0 and rank 1."""
    local_ok = 1
    if world_size >= 2:
        expected = make_rank_buffer(rank=0, message_bytes=message_bytes)
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
            local_ok = int(torch.equal(recv_buf, expected))

    dist.barrier()
    status = torch.tensor([local_ok], dtype=torch.int64)
    dist.all_reduce(status, op=dist.ReduceOp.MIN)
    return bool(status.item() == 1)

"""Independent correctness validation harness (Member 3)."""

from __future__ import annotations

from collections.abc import Sequence

import torch

from src.common import AllGatherFn, BroadcastFn, DEFAULT_ROOT

DEFAULT_TEST_MESSAGE_SIZES: tuple[int, ...] = (1, 16, 1024, 65536)


def make_test_input(rank: int, message_bytes: int) -> torch.Tensor:
    """Create a deterministic, unique per-rank uint8 input buffer.

    TODO (Member 3):
        Fill a contiguous 1D CPU uint8 tensor with a rank-dependent pattern
        that distinguishes both source rank and byte position.
    """
    raise NotImplementedError("make_test_input is awaiting Member 3 implementation.")


def expected_allgather(world_size: int, message_bytes: int) -> torch.Tensor:
    """Return the exact AllGather oracle tensor concatenated in ascending rank order."""
    raise NotImplementedError("expected_allgather is awaiting Member 3 implementation.")


def expected_broadcast(root: int, message_bytes: int) -> torch.Tensor:
    """Return the exact Broadcast oracle tensor matching the root rank's input."""
    raise NotImplementedError("expected_broadcast is awaiting Member 3 implementation.")


def verify_allgather(
    fn: AllGatherFn,
    rank: int,
    world_size: int,
    message_bytes: int,
) -> bool:
    """Validate one AllGather implementation on every rank and aggregate pass/fail.

    TODO (Member 3):
        - Run fn(local_input, rank, world_size) and verify caller input is unchanged.
        - Compare output against expected_allgather on EVERY rank (not rank 0 only).
        - Report failing rank and first mismatched index on failure.
        - Aggregate pass/fail across all ranks via dist.all_reduce(MIN).
    """
    raise NotImplementedError("verify_allgather is awaiting Member 3 implementation.")


def verify_broadcast(
    fn: BroadcastFn,
    rank: int,
    world_size: int,
    message_bytes: int,
    root: int = DEFAULT_ROOT,
) -> bool:
    """Validate one Broadcast implementation on every rank and aggregate pass/fail.

    TODO (Member 3):
        - Run fn(local_input, rank, world_size, root) and verify caller input is unchanged.
        - Compare output against expected_broadcast on EVERY rank.
        - Report failing rank and first mismatched index on failure.
        - Aggregate pass/fail across all ranks via dist.all_reduce(MIN).
    """
    raise NotImplementedError("verify_broadcast is awaiting Member 3 implementation.")


def run_verification_suite(
    rank: int,
    world_size: int,
    message_sizes: Sequence[int] = DEFAULT_TEST_MESSAGE_SIZES,
) -> bool:
    """Exercise all five collective implementations on the supported test matrix.

    TODO (Member 3):
        - Test ring, recursive, swing (AllGather) and binary, binomial (Broadcast).
        - Clearly report unsupported rank counts vs. correctness failures.
        - Return True iff all supported tests pass on every rank.
    """
    raise NotImplementedError(
        "run_verification_suite is awaiting Member 3 implementation."
    )

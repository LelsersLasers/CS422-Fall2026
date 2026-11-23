"""Worker CLI runner and algorithm registry (Member 4 owns integration after setup)."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from src.allgather_recursive import allgather_recursive
from src.allgather_ring import allgather_ring
from src.allgather_swing import allgather_swing
from src.benchmark import run_benchmark
from src.broadcast_binary import broadcast_binary
from src.broadcast_binomial import broadcast_binomial
from src.common import (
    AllGatherFn,
    BroadcastFn,
    DEFAULT_ROOT,
    distributed_context,
    make_rank_buffer,
    rank0_print,
    run_p2p_smoke_test,
)
from src.correctness import run_verification_suite, verify_allgather, verify_broadcast

ALLGATHER_ALGORITHMS: dict[str, AllGatherFn] = {
    "ring": allgather_ring,
    "recursive": allgather_recursive,
    "swing": allgather_swing,
}

BROADCAST_ALGORITHMS: dict[str, BroadcastFn] = {
    "binary": broadcast_binary,
    "binomial": broadcast_binomial,
}


def build_parser() -> argparse.ArgumentParser:
    """Build the worker CLI argument parser."""
    parser = argparse.ArgumentParser(
        description="CS 422 Assignment 5 PyTorch/Gloo collective worker."
    )
    parser.add_argument(
        "--operation",
        required=True,
        choices=("smoke", "allgather", "broadcast", "verify", "benchmark"),
        help="Operation mode to execute across ranks.",
    )
    parser.add_argument(
        "--algorithm",
        default=None,
        help="Algorithm name (ring|recursive|swing for allgather; binary|binomial for broadcast).",
    )
    parser.add_argument(
        "--message-bytes",
        type=int,
        default=1024,
        help="Per-rank input size (AllGather) or root message size (Broadcast) in bytes.",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=1,
        help="Number of iterations to execute.",
    )
    parser.add_argument(
        "--root",
        type=int,
        default=DEFAULT_ROOT,
        help="Root rank for Broadcast operations (default: 0).",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Run correctness validation for the selected operation/algorithm.",
    )
    return parser


def validate_args(args: argparse.Namespace) -> None:
    """Validate CLI argument combinations before launching collectives."""
    if args.message_bytes < 1:
        raise ValueError(f"--message-bytes must be >= 1, got {args.message_bytes}.")
    if args.iterations < 1:
        raise ValueError(f"--iterations must be >= 1, got {args.iterations}.")
    if args.operation == "allgather":
        if args.algorithm not in ALLGATHER_ALGORITHMS:
            valid = ", ".join(ALLGATHER_ALGORITHMS)
            raise ValueError(f"--algorithm for allgather must be one of: {valid}")
    elif args.operation == "broadcast":
        if args.algorithm not in BROADCAST_ALGORITHMS:
            valid = ", ".join(BROADCAST_ALGORITHMS)
            raise ValueError(f"--algorithm for broadcast must be one of: {valid}")


def main(argv: Sequence[str] | None = None) -> int:
    """Initialize Gloo ranks and dispatch the requested operation."""
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        validate_args(args)
    except ValueError as exc:
        parser.error(str(exc))

    with distributed_context(backend="gloo") as (rank, world_size):
        if args.operation == "smoke":
            passed = run_p2p_smoke_test(rank, world_size, args.message_bytes)
            status = "PASS" if passed else "FAIL"
            rank0_print(
                rank,
                f"[smoke] world_size={world_size} message_bytes={args.message_bytes}: {status}",
            )
            return 0 if passed else 1

        if args.operation == "verify":
            passed = run_verification_suite(rank, world_size)
            return 0 if passed else 1

        if args.operation == "benchmark":
            run_benchmark(
                rank=rank,
                world_size=world_size,
                operation="allgather",
                algorithms=tuple(ALLGATHER_ALGORITHMS),
            )
            return 0

        if args.operation == "allgather":
            fn = ALLGATHER_ALGORITHMS[args.algorithm]
            if args.verify:
                passed = verify_allgather(fn, rank, world_size, args.message_bytes)
                return 0 if passed else 1
            local_buf = make_rank_buffer(rank, args.message_bytes)
            for _ in range(args.iterations):
                fn(local_buf, rank, world_size)
            return 0

        if args.operation == "broadcast":
            fn = BROADCAST_ALGORITHMS[args.algorithm]
            if args.verify:
                passed = verify_broadcast(
                    fn, rank, world_size, args.message_bytes, root=args.root
                )
                return 0 if passed else 1
            buf = make_rank_buffer(rank, args.message_bytes)
            for _ in range(args.iterations):
                fn(buf, rank, world_size, args.root)
            return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

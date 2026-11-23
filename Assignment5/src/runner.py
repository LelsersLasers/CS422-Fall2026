"""Worker CLI runner and algorithm registry."""

import argparse

import torch.distributed as dist

from src.allgather_recursive import allgather_recursive
from src.allgather_ring import allgather_ring
from src.allgather_swing import allgather_swing
from src.benchmark import run_benchmark
from src.broadcast_binary import broadcast_binary
from src.broadcast_binomial import broadcast_binomial
from src.common import make_rank_buffer, p2p_smoke_test
from src.correctness import run_verification_suite

ALLGATHER = {
    "ring": allgather_ring,
    "recursive": allgather_recursive,
    "swing": allgather_swing,
}

BROADCAST = {
    "binary": broadcast_binary,
    "binomial": broadcast_binomial,
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Assignment 5 Gloo worker.")
    parser.add_argument(
        "--operation",
        required=True,
        choices=("smoke", "allgather", "broadcast", "verify", "benchmark"),
    )
    parser.add_argument("--algorithm", default=None)
    parser.add_argument("--message-bytes", type=int, default=1024)
    parser.add_argument("--iterations", type=int, default=1)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()

    dist.init_process_group(backend="gloo")
    try:
        rank = dist.get_rank()
        world_size = dist.get_world_size()

        if args.operation == "smoke":
            ok = p2p_smoke_test(rank, world_size, args.message_bytes)
            if rank == 0:
                print(f"[smoke] world_size={world_size} message_bytes={args.message_bytes}: {'PASS' if ok else 'FAIL'}")
            return 0 if ok else 1

        if args.operation == "verify" or args.verify:
            return 0 if run_verification_suite(rank, world_size) else 1

        if args.operation == "benchmark":
            run_benchmark(rank, world_size)
            return 0

        buf = make_rank_buffer(rank, args.message_bytes)
        if args.operation == "allgather":
            ag_fn = ALLGATHER[args.algorithm]
            for _ in range(args.iterations):
                ag_fn(buf, rank, world_size)
        elif args.operation == "broadcast":
            bcast_fn = BROADCAST[args.algorithm]
            for _ in range(args.iterations):
                bcast_fn(buf, rank, world_size, 0)
        return 0
    finally:
        dist.destroy_process_group()


if __name__ == "__main__":
    raise SystemExit(main())

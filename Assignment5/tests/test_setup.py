"""Basic contract, helper, and CLI setup tests for Assignment 5."""

from __future__ import annotations

import inspect
import sys
from pathlib import Path

import pytest
import torch

ASSIGNMENT5_ROOT = Path(__file__).resolve().parents[1]
if str(ASSIGNMENT5_ROOT) not in sys.path:
    sys.path.insert(0, str(ASSIGNMENT5_ROOT))

import main as top_main  # noqa: E402
from src import common, runner  # noqa: E402


def test_all_five_collective_stubs_registered_and_signature_frozen() -> None:
    assert set(runner.ALLGATHER_ALGORITHMS) == {"ring", "recursive", "swing"}
    assert set(runner.BROADCAST_ALGORITHMS) == {"binary", "binomial"}

    for ag_fn in runner.ALLGATHER_ALGORITHMS.values():
        params = list(inspect.signature(ag_fn).parameters.values())
        assert [p.name for p in params] == ["local_data", "rank", "world_size"]
        with pytest.raises(NotImplementedError):
            ag_fn(common.make_rank_buffer(0, 8), 0, 2)

    for bcast_fn in runner.BROADCAST_ALGORITHMS.values():
        params = list(inspect.signature(bcast_fn).parameters.values())
        assert [p.name for p in params] == ["data", "rank", "world_size", "root"]
        assert params[3].default == 0
        with pytest.raises(NotImplementedError):
            bcast_fn(common.make_rank_buffer(0, 8), 0, 2, 0)


def test_common_helpers() -> None:
    assert common.is_power_of_two(1)
    assert common.is_power_of_two(8)
    assert not common.is_power_of_two(0)
    assert not common.is_power_of_two(6)

    buf = common.make_rank_buffer(rank=2, message_bytes=16)
    assert buf.shape == (16,)
    assert buf.dtype == torch.uint8
    assert buf.is_contiguous()
    common.validate_collective_input(buf, rank=2, world_size=4, root=0)

    with pytest.raises(ValueError):
        common.validate_collective_input(torch.zeros((2, 4)), rank=0, world_size=2)
    with pytest.raises(ValueError):
        common.validate_collective_input(buf, rank=4, world_size=4)
    with pytest.raises(ValueError):
        common.validate_collective_input(buf, rank=0, world_size=4, root=4)


def test_runner_and_main_cli_parsing() -> None:
    args = runner.build_parser().parse_args(
        ["--operation", "allgather", "--algorithm", "ring", "--message-bytes", "32", "--verify"]
    )
    runner.validate_args(args)
    assert args.operation == "allgather"
    assert args.algorithm == "ring"
    assert args.verify is True

    bad_args = runner.build_parser().parse_args(
        ["--operation", "allgather", "--algorithm", "binary"]
    )
    with pytest.raises(ValueError):
        runner.validate_args(bad_args)

    cmd = top_main.build_torchrun_command(8, ["--operation", "smoke"])
    assert "--nproc-per-node=8" in cmd
    assert "src.runner" in cmd

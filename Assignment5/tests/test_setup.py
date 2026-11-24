"""Minimal setup and contract tests for Assignment 5."""

import inspect
import sys
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src import common, runner  # noqa: E402


def test_five_registered_with_frozen_signatures() -> None:
    assert set(runner.ALLGATHER) == {"ring", "recursive", "swing"}
    assert set(runner.BROADCAST) == {"binary", "binomial"}

    for ag_fn in runner.ALLGATHER.values():
        assert list(inspect.signature(ag_fn).parameters) == ["local_data", "rank", "world_size"]

    for bcast_fn in runner.BROADCAST.values():
        params = list(inspect.signature(bcast_fn).parameters.values())
        assert [p.name for p in params] == ["data", "rank", "world_size", "root"]
        assert params[3].default == 0


def test_common_helpers() -> None:
    assert common.is_power_of_two(8)
    assert not common.is_power_of_two(6)
    buf = common.make_rank_buffer(2, 16)
    assert buf.shape == (16,) and buf.dtype == torch.uint8 and buf.is_contiguous()

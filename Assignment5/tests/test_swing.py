"""Unit and Gloo integration tests for Swing AllGather and correctness harness."""

import subprocess
import sys
from pathlib import Path

import pytest
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.allgather_swing import allgather_swing, swing_partner, swing_rho  # noqa: E402
from src.common import make_rank_buffer  # noqa: E402


def test_swing_rho_values() -> None:
    assert [swing_rho(s) for s in range(5)] == [1, -1, 3, -5, 11]


@pytest.mark.parametrize("world_size", [2, 4, 8, 16])
def test_swing_schedule_involution_disjoint_and_complete(world_size: int) -> None:
    steps = world_size.bit_length() - 1
    held = [{r} for r in range(world_size)]
    for s in range(steps - 1, -1, -1):
        next_held = []
        for r in range(world_size):
            peer = swing_partner(r, s, world_size)
            assert peer != r
            assert swing_partner(peer, s, world_size) == r
            assert held[r].isdisjoint(held[peer])
            next_held.append(held[r] | held[peer])
        held = next_held
    assert all(h == set(range(world_size)) for h in held)


@pytest.mark.parametrize("world_size", [0, 3, 5, 6])
def test_swing_rejects_non_power_of_two(world_size: int) -> None:
    with pytest.raises(ValueError, match="power-of-two"):
        allgather_swing(make_rank_buffer(0, 8), 0, world_size)


def test_swing_rejects_non_1d_tensor() -> None:
    with pytest.raises(ValueError, match="1D"):
        allgather_swing(torch.zeros((2, 4), dtype=torch.uint8), 0, 2)


def test_swing_world_size_one_clones_without_mutation() -> None:
    buf = make_rank_buffer(0, 16)
    out = allgather_swing(buf, 0, 1)
    assert torch.equal(out, buf)
    assert out.is_contiguous()
    assert out.data_ptr() != buf.data_ptr()


def test_swing_empty_tensor() -> None:
    buf = torch.empty(0, dtype=torch.uint8)
    out = allgather_swing(buf, 0, 4)
    assert out.shape == (0,) and out.dtype == torch.uint8


@pytest.mark.parametrize("world_size", [1, 2, 4, 8])
def test_swing_gloo_verify_pass(world_size: int) -> None:
    res = subprocess.run(
        [
            sys.executable,
            "-m",
            "torch.distributed.run",
            "--standalone",
            f"--nproc-per-node={world_size}",
            "-m",
            "src.runner",
            "--operation",
            "verify",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    assert f"world_size={world_size} allgather/swing: PASS" in res.stdout


def test_swing_gloo_verify_skips_non_power_of_two() -> None:
    res = subprocess.run(
        [
            sys.executable,
            "-m",
            "torch.distributed.run",
            "--standalone",
            "--nproc-per-node=3",
            "-m",
            "src.runner",
            "--operation",
            "verify",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    assert "world_size=3 allgather/swing: SKIP" in res.stdout

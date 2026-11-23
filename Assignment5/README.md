# CS 422 Assignment 5: Collective Communication

Implementation and experimental comparison of five collective communication algorithms using **PyTorch Distributed (Gloo backend)** with point-to-point `isend`, `irecv`, and `wait`:

- **AllGather:** Ring, Recursive Doubling, Swing
- **Broadcast:** Binary Tree, Binomial Tree

*(Required assignment only; the optional multi-machine ring-topology bonus is out of scope.)*

## Environment Setup

### Generic Linux (Ubuntu, Debian, Fedora, Arch, etc.)

Install CPU-only PyTorch first to avoid downloading CUDA libraries, then install the remaining dependencies from `Assignment5/`:

```bash
cd Assignment5
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install torch --index-url https://download.pytorch.org/whl/cpu
python -m pip install -r requirements.txt
```

### NixOS

From the repository root, use `direnv allow` (loads `.envrc` -> `./nix_flake`) or enter the dev shell directly:

```bash
nix develop ./nix_flake
```

The flake provides CPU-only PyTorch (`pkgs.python3Packages.torch` with Gloo and `torchrun`), `numpy`, `matplotlib`, `pytest`, `mypy`, and LaTeX tools.

## Quick Start (Top-Level Entry Point)

Run directly from `Assignment5/` (or `python3 Assignment5/main.py ...` from the repository root):

```bash
# 1. Verify Gloo multi-rank launch and P2P isend/irecv/wait at 2, 4, and 8 ranks
python3 main.py smoke

# 2. Run a single collective via torchrun
python3 main.py run --ranks 8 --operation allgather --algorithm ring --message-bytes 1024

# 3. Run unit tests
python3 -m pytest -v

# 4. Full pipeline (once Steps 2-5 are implemented): verify -> benchmark -> plot
python3 main.py verify
python3 main.py benchmark
python3 main.py plot
python3 main.py
```

You can also invoke `torchrun` directly from `Assignment5/`:

```bash
torchrun --standalone --nproc-per-node=2 -m src.runner --operation smoke --message-bytes 64
torchrun --standalone --nproc-per-node=4 -m src.runner --operation smoke --message-bytes 64
torchrun --standalone --nproc-per-node=8 -m src.runner --operation smoke --message-bytes 64
```

> **Troubleshooting Gloo network interfaces:** On Linux hosts with virtual or VPN interfaces (e.g., Docker, VMware, Tailscale), if Gloo fails to connect on a single machine, prefix the command with `GLOO_SOCKET_IFNAME=lo`.

## Frozen Collective Interface Contract

```python
def allgather_*(local_data: torch.Tensor, rank: int, world_size: int) -> torch.Tensor:
    """Return a 1D tensor with all per-rank inputs concatenated in rank order."""

def broadcast_*(data: torch.Tensor, rank: int, world_size: int, root: int = 0) -> torch.Tensor:
    """Return the root's 1D tensor on every rank."""
```

- Inputs are **1D contiguous CPU tensors** (`torch.uint8` by default for byte-size benchmarks).
- Implementations allocate their own output/receive buffers and never mutate the caller's input.
- Implementations must use point-to-point Gloo `dist.isend`, `dist.irecv`, and `.wait()` (never `dist.all_gather` or `dist.broadcast` inside the collective).
- Console output is printed only by rank 0 (`src.common.rank0_print`).

## Layout and Ownership

| Path | Owner | Purpose |
|---|---|---|
| `main.py` | Member 4 (post-setup) | Top-level orchestrator (`smoke`, `run`, `verify`, `benchmark`, `plot`, `all`) |
| `src/runner.py` | Member 4 (post-setup) | Worker CLI and algorithm registry |
| `src/common.py` | Shared | Frozen types, Gloo lifecycle, validators, P2P smoke test |
| `src/allgather_ring.py`, `src/broadcast_binary.py`, `docs/member1_notes.md` | Member 1 | Ring AllGather & Binary Tree Broadcast |
| `src/allgather_recursive.py`, `src/broadcast_binomial.py`, `docs/member2_notes.md` | Member 2 | Recursive Doubling AllGather & Binomial Tree Broadcast |
| `src/allgather_swing.py`, `src/correctness.py`, `docs/member3_swing.md` | Member 3 | Swing AllGather & independent correctness harness |
| `src/benchmark.py`, `src/plot_results.py`, `results/`, `report/report.tex` | Member 4 | Benchmarking, plots, and final PDF report |
| `tests/test_setup.py` | Shared | Basic contract and CLI smoke unit tests |

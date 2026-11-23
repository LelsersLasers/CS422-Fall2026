# CS 422 Assignment 5: Collective Communication

PyTorch Distributed (Gloo backend) point-to-point implementations of:
- **AllGather:** Ring, Recursive Doubling, Swing
- **Broadcast:** Binary Tree, Binomial Tree

## Setup

### Generic Linux
```bash
cd Assignment5
python3 -m venv .venv
source .venv/bin/activate
python -m pip install torch --index-url https://download.pytorch.org/whl/cpu
python -m pip install -r requirements.txt
```

### NixOS
From the repository root, use `direnv allow` or:
```bash
nix develop ./nix_flake
```

## Usage

Run from `Assignment5/` (or `python3 Assignment5/main.py ...` from repo root):
```bash
python3 main.py smoke        # Gloo P2P smoke test at 2, 4, and 8 ranks
python3 main.py verify       # Correctness suite (Member 3)
python3 main.py benchmark    # Benchmark sweeps (Member 4)
python3 main.py plot         # Generate plots (Member 4)
python3 main.py              # Full pipeline: verify -> benchmark -> plot
python3 -m pytest -v         # Basic contract tests
```

Or run `torchrun` directly from `Assignment5/`:
```bash
torchrun --standalone --nproc-per-node=8 -m src.runner --operation smoke --message-bytes 64
```

*(If Gloo fails to bind on a machine with Docker/VPN interfaces, prefix with `GLOO_SOCKET_IFNAME=lo`.)*

## Frozen Interface

```python
def allgather_*(local_data: torch.Tensor, rank: int, world_size: int) -> torch.Tensor: ...
def broadcast_*(data: torch.Tensor, rank: int, world_size: int, root: int = 0) -> torch.Tensor: ...
```

- 1D contiguous CPU `torch.uint8` tensors; do not mutate caller input.
- Use `dist.isend`, `dist.irecv`, and `.wait()` (no `dist.all_gather` or `dist.broadcast` inside the algorithms).

## Ownership

- **Member 1:** `src/allgather_ring.py`, `src/broadcast_binary.py`
- **Member 2:** `src/allgather_recursive.py`, `src/broadcast_binomial.py`
- **Member 3:** `src/allgather_swing.py`, `src/correctness.py`
- **Member 4:** `main.py`, `src/runner.py`, `src/benchmark.py`, `src/plot_results.py`, `results/`, `report/`, `README.md`

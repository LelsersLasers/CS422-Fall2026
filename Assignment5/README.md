# CS 422 Assignment 5: Collective Communication

PyTorch Distributed (Gloo backend) point-to-point implementations of:
- **AllGather:** Ring, Recursive Doubling, Swing
- **Broadcast:** Binary Tree, Binomial Tree

## Setup

### Linux
```bash
cd Assignment5
python3 -m venv .venv
source .venv/bin/activate
python -m pip install torch --index-url https://download.pytorch.org/whl/cpu
python -m pip install -r requirements.txt
```

## Usage

Run from `Assignment5/` (or `python3 Assignment5/main.py ...` from repo root):
```bash
python3 main.py              # Full pipeline: verify -> benchmark -> plot
```
```bash
python3 main.py smoke        # Gloo P2P smoke test at 2, 4, and 8 ranks
python3 main.py verify       # Correctness suite
python3 main.py benchmark    # Benchmark sweeps
python3 main.py plot         # Generate plots
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

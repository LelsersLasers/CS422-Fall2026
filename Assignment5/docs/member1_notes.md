# Member 1 Algorithm Notes (Report Input)

## Ring AllGather (`src/allgather_ring.py`)

- **Summary:** TODO
- **Neighbor & block equations:**
  - Next rank: `(r + 1) % p`, Previous rank: `(r - 1 + p) % p`
  - Round `s` outgoing block: `(r - s) % p`, incoming block: `(r - s - 1) % p`
- **Round count & complexity:** TODO (`p - 1` rounds)
- **Code link (function / line range):** TODO

## Binary Tree Broadcast (`src/broadcast_binary.py`)

- **Summary:** TODO
- **Parent / child equations:**
  - Parent: `(r - 1) // 2`, Left: `2r + 1`, Right: `2r + 2`
- **Root handling:** TODO (`root=0` only or logical remapping)
- **Round count & complexity:** TODO
- **Code link (function / line range):** TODO

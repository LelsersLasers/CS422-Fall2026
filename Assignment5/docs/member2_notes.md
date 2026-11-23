# Member 2 Algorithm Notes (Report Input)

## Recursive Doubling AllGather (`src/allgather_recursive.py`)

- **Summary:** TODO
- **Partner equation:** `partner = r ^ (1 << s)` for `s = 0, ..., log2(p) - 1`
- **Rank count restriction:** Power-of-two `p = 2^k`
- **Round count & complexity:** TODO (`log2(p)` rounds)
- **Code link (function / line range):** TODO

## Binomial Tree Broadcast (`src/broadcast_binomial.py`)

- **Summary:** TODO
- **Doubling frontier schedule:** `mask = 1, 2, 4, ... < p`
- **Root handling:** TODO (`root=0` only or logical rank remapping)
- **Round count & complexity:** TODO (`ceil(log2(p))` rounds)
- **Code link (function / line range):** TODO

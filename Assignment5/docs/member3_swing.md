# Member 3 Swing AllGather Notes & Schedule Table (Report Input)

## Reference & Variant

- **Paper:** De Sensi et al., *Swing: Short-cutting Rings for Higher Bandwidth Allreduce*, NSDI 2024.
- **Variant:** 1D bandwidth-optimized AllGather expansion phase (power-of-two `p`).
- **Assumptions / Departures:** TODO
- **Code link (function / line range):** TODO

## Partner & Schedule Equations

- `rho(s) = (1 - (-2)**(s + 1)) // 3`
- `partner(r, s) = (r + rho(s)) % p` (even `r`) or `(r - rho(s)) % p` (odd `r`)
- **Step order & chunk subset rule:** TODO

## Debugging Schedule Table (`p = 8`)

| Round | Rank | Partner | Sent Block IDs | Received Block IDs | Accumulated Block IDs |
|---:|---:|---:|---|---|---|
| 0 | 0 | TODO | TODO | TODO | TODO |
| 0 | 1 | TODO | TODO | TODO | TODO |
| 0 | 2 | TODO | TODO | TODO | TODO |
| 0 | 3 | TODO | TODO | TODO | TODO |
| 0 | 4 | TODO | TODO | TODO | TODO |
| 0 | 5 | TODO | TODO | TODO | TODO |
| 0 | 6 | TODO | TODO | TODO | TODO |
| 0 | 7 | TODO | TODO | TODO | TODO |

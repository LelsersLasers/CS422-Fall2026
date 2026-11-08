import numpy as np
from implementation import optimize_arbitrary_traffic

T = np.array([
    [0, 2, 0, 1, 0, 0, 1, 0],
    [0, 0, 2, 0, 1, 0, 0, 1],
    [1, 0, 0, 1, 0, 1, 0, 0],
    [0, 1, 0, 0, 2, 0, 1, 0],
    [1, 0, 1, 0, 0, 1, 0, 0],
    [0, 1, 0, 1, 0, 0, 1, 0],
    [0, 0, 1, 0, 1, 0, 0, 1],
    [1, 0, 0, 1, 0, 1, 0, 0]
], dtype=float)

result = optimize_arbitrary_traffic(T)

if result is not None:
    print("Optimal lambda:", result["lambda"])
    print("Optimal topology:", result["topology"])
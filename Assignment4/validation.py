
import numpy as np


def validate_topology(adjacency_matrix, n=8, d=4):
    """Check if a network topology follows the assignment rules."""

    matrix = np.asarray(adjacency_matrix)

    # Rule 1: We need exactly n nodes
    if matrix.shape != (n, n):
        return False

    # Rule 2: Links are either present (1) or absent (0)
    if not np.all((matrix == 0) | (matrix == 1)):
        return False

    # Rule 3: A node cannot connect to itself
    if not np.all(np.diag(matrix) == 0):
        return False

    # Rule 4: Every node must have exactly d outgoing links
    if not np.all(matrix.sum(axis=1) == d):
        return False

    # Rule 5: Every node must have exactly d incoming links
    if not np.all(matrix.sum(axis=0) == d):
        return False

    return True


if __name__ == "__main__":

    # Build a simple example topology for testing
    n = 8
    d = 4
    topology = np.zeros((n, n), dtype=int)

    for source in range(n):
        # Connect every node to the next 4 nodes
        for step in range(1, d + 1):
            destination = (source + step) % n
            topology[source][destination] = 1

    print("Topology:")
    print(topology)

    print("\nValid topology:", validate_topology(topology))

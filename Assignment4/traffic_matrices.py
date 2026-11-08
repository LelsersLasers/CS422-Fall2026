
import numpy as np


def uniform_traffic(n=8, d=4):
    """Create a matrix where each node sends traffic equally to everyone else."""

    # Every node splits its total traffic between the other n-1 nodes
    traffic_per_node = d / (n - 1)

    matrix = np.full((n, n), traffic_per_node)

    # A node shouldn't send traffic to itself
    np.fill_diagonal(matrix, 0)

    return matrix


def permutation_traffic(n=8, d=4, seed=42):
    """Create a matrix where each node sends all its traffic to one other node."""

    rng = np.random.default_rng(seed)

    matrix = np.zeros((n, n))

    # Pick a random shift so nobody gets paired with themselves
    shift = rng.integers(1, n)

    for source in range(n):
        destination = (source + shift) % n
        matrix[source][destination] = d

    return matrix


def sparse_traffic(n=8, d=4):
    """Create a sparse matrix where only some nodes send traffic."""

    matrix = np.zeros((n, n))

    # Only half the nodes send traffic
    # This helps test cases where some nodes are inactive
    for source in range(n // 2):
        destination = source + n // 2
        matrix[source][destination] = d

    return matrix




def validate_traffic_matrix(matrix, n=8, d=4):
    """Check if the matrix follows the assignment's traffic rules."""

    matrix = np.asarray(matrix, dtype=float)

    # Small rounding differences are okay
    tolerance = 1e-6

    # Rule 1: Matrix must have n rows and n columns
    if matrix.shape != (n, n):
        return False

    # Rule 2: Reject NaN and infinity
    if not np.all(np.isfinite(matrix)):
        return False

    # Rule 3: Traffic cannot be negative
    if np.any(matrix < -tolerance):
        return False

    # Rule 4: Nodes shouldn't send traffic to themselves
    if not np.all(np.abs(np.diag(matrix)) <= tolerance):
        return False

    # Rule 5: Each node can send at most d units
    if np.any(matrix.sum(axis=1) > d + tolerance):
        return False

    # Rule 6: Each node can receive at most d units
    if np.any(matrix.sum(axis=0) > d + tolerance):
        return False

    # All checks passed
    return True



if __name__ == "__main__":

    # Generate different traffic patterns to test later
    matrices = {
        "Uniform": uniform_traffic(),
        "Permutation": permutation_traffic(),
        "Sparse": sparse_traffic()
    }

    for name, matrix in matrices.items():
        print(f"\n{name} Traffic Matrix:")
        print(np.round(matrix, 3))

        # Quick check to see if this matrix is valid
        print("Valid:", validate_traffic_matrix(matrix))

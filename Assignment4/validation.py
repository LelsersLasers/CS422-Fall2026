
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


def validate_flows(topology, traffic, flows, theta, n=8, d=4):
    """Check if routed traffic follows the network flow rules."""

    # First make sure the topology and traffic matrix are valid
    if not validate_topology(topology, n, d):
        return False

    traffic = np.asarray(traffic, dtype=float)

    if traffic.shape != (n, n):
        return False

    if not np.all(np.isfinite(traffic)):
        return False

    if np.any(traffic < 0) or np.any(np.diag(traffic) != 0):
        return False

    if np.any(traffic.sum(axis=1) > d + 1e-6):
        return False

    if np.any(traffic.sum(axis=0) > d + 1e-6):
        return False

    if not np.isfinite(theta) or theta < 0:
        return False

    # Small rounding errors are normal in optimization
    tolerance = 1e-6

    # Track how much total traffic each link carries
    link_load = np.zeros((n, n))

    # Track incoming and outgoing traffic for each source-destination pair
    balance = np.zeros((n, n, n))

    for (source, destination, u, v), amount in flows.items():

        # All node numbers must be valid
        if not all(0 <= node < n for node in (source, destination, u, v)):
            return False

        # No self-traffic, negative flow, or invalid numbers
        if source == destination:
            return False

        if not np.isfinite(amount) or amount < 0:
            return False

        # Traffic can only use links that actually exist
        if topology[u][v] != 1 and amount > tolerance:
            return False

        link_load[u][v] += amount

        # Sending traffic decreases a node's balance
        balance[source][destination][u] -= amount

        # Receiving traffic increases a node's balance
        balance[source][destination][v] += amount

    # Every link has capacity 1
    if np.any(link_load > 1 + tolerance):
        return False

    for source in range(n):
        for destination in range(n):

            if source == destination:
                continue

            required = theta * traffic[source][destination]

            # Source must send enough traffic
            if -balance[source][destination][source] < required - tolerance:
                return False

            # Destination must receive enough traffic
            if balance[source][destination][destination] < required - tolerance:
                return False

            # Intermediate nodes cannot lose or create traffic
            for node in range(n):
                if node != source and node != destination:
                    if abs(balance[source][destination][node]) > tolerance:
                        return False

            # What leaves the source must reach the destination
            if abs(
                balance[source][destination][source]
                + balance[source][destination][destination]
            ) > tolerance:
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

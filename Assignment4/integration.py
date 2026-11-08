
import numpy as np

from implementation import optimize_arbitrary_traffic
from traffic_matrices import validate_traffic_matrix
from validation import validate_topology, validate_flows
from visualization import draw_topology


def run_integration():
    """Check the optimizer results using our validation code."""

    # Using the same sample traffic matrix as the solver test
    traffic = np.array([
        [0, 2, 0, 1, 0, 0, 1, 0],
        [0, 0, 2, 0, 1, 0, 0, 1],
        [1, 0, 0, 1, 0, 1, 0, 0],
        [0, 1, 0, 0, 2, 0, 1, 0],
        [1, 0, 1, 0, 0, 1, 0, 0],
        [0, 1, 0, 1, 0, 0, 1, 0],
        [0, 0, 1, 0, 1, 0, 0, 1],
        [1, 0, 0, 1, 0, 1, 0, 0]
    ], dtype=float)

    # Checking input before running the optimizer
    if not validate_traffic_matrix(traffic):
        print("Invalid traffic matrix.")
        return

    # Running the optimizer
    result = optimize_arbitrary_traffic(traffic, verbose=False)

    if result is None:
        print("No solution found.")
        return

    # Converting the link list into an adjacency matrix
    topology = np.zeros((8, 8), dtype=int)

    for source, destination in result["topology"]:
        topology[source][destination] = 1

    # Converting the routing dictionary into our validator's format
    flows = {}

    for (source, destination), links in result["routing"].items():
        for (u, v), amount in links.items():
            flows[(source, destination, u, v)] = amount

    # Validating the solver output
    topology_valid = validate_topology(topology)
    flows_valid = validate_flows(
        topology, traffic, flows, result["lambda"]
    )

    print("\nINTEGRATION TEST RESULTS")
    print("------------------------")
    print("Traffic matrix valid:", validate_traffic_matrix(traffic))
    print("Topology valid:", topology_valid)
    print("Flows valid:", flows_valid)
    print("Optimal solution:", result["optimal"])
    print("Concurrent flow:", result["lambda"])

    # Only generating the image when all checks pass
    if topology_valid and flows_valid:
        draw_topology(topology, "optimized_topology.png")


if __name__ == "__main__":
    run_integration()

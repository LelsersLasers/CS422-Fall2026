
import numpy as np
import networkx as nx
import matplotlib.pyplot as plt

from validation import validate_topology


def draw_topology(matrix, filename="topology.png"):
    """Draw a directed network and save it as an image."""

    # Check the topology before trying to draw it
    if not validate_topology(matrix):
        raise ValueError("Invalid topology")

    # Turn the adjacency matrix into a directed graph
    graph = nx.from_numpy_array(matrix, create_using=nx.DiGraph)

    # Place nodes in a circle so the graph is easier to read
    positions = nx.circular_layout(graph)

    plt.figure(figsize=(9, 9))

    # Draw nodes, links, arrows, and node numbers
    nx.draw(
        graph,
        positions,
        with_labels=True,
        node_color="lightblue",
        node_size=1000,
        font_size=12,
        arrows=True,
        arrowsize=15,
        width=1,
        connectionstyle="arc3,rad=0.1"
    )

    plt.title("Network Topology (8 Nodes, 4 Links per Node)")

    # Save the graph so we can use it in the report
    plt.savefig(filename, dpi=300, bbox_inches="tight")
    plt.close()

    print(f"Topology saved to {filename}")


if __name__ == "__main__":

    n = 8
    d = 4

    # Create a sample topology until we have Kabil's solver output
    matrix = np.zeros((n, n), dtype=int)

    for source in range(n):
        for step in range(1, d + 1):
            # Wrap around when we reach the last node
            destination = (source + step) % n
            matrix[source][destination] = 1

    draw_topology(matrix)

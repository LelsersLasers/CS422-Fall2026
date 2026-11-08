
import numpy as np
from validation import validate_topology, validate_flows

from traffic_matrices import (
    uniform_traffic,
    permutation_traffic,
    sparse_traffic,
    validate_traffic_matrix
)


def test_uniform_traffic():
    # Uniform traffic should follow all the assignment rules
    matrix = uniform_traffic()
    assert validate_traffic_matrix(matrix)


def test_permutation_traffic():
    # Every node sends traffic to one other node
    matrix = permutation_traffic()
    assert validate_traffic_matrix(matrix)


def test_sparse_traffic():
    # Some nodes are inactive, which is allowed
    matrix = sparse_traffic()
    assert validate_traffic_matrix(matrix)


def test_negative_traffic():
    # Negative traffic makes no sense, so this should fail
    matrix = uniform_traffic()
    matrix[0][1] = -1

    assert not validate_traffic_matrix(matrix)


def test_self_traffic():
    # Nodes shouldn't send traffic to themselves
    matrix = uniform_traffic()
    matrix[0][0] = 1

    assert not validate_traffic_matrix(matrix)


def test_too_much_outgoing_traffic():
    # A node cannot send more than 4 units total
    matrix = np.zeros((8, 8))
    matrix[0][1] = 5

    assert not validate_traffic_matrix(matrix)


def test_too_much_incoming_traffic():
    # A node cannot receive more than 4 units total
    matrix = np.zeros((8, 8))
    matrix[0][2] = 3
    matrix[1][2] = 3

    assert not validate_traffic_matrix(matrix)


def make_valid_topology():
    """Create a simple topology with 4 incoming and outgoing links per node."""

    matrix = np.zeros((8, 8), dtype=int)

    for source in range(8):
        for step in range(1, 5):
            destination = (source + step) % 8
            matrix[source][destination] = 1

    return matrix


def test_valid_topology():
    # Our sample topology should pass all checks
    matrix = make_valid_topology()
    assert validate_topology(matrix)


def test_missing_link():
    # Removing one link breaks the degree requirement
    matrix = make_valid_topology()
    matrix[0][1] = 0

    assert not validate_topology(matrix)


def test_self_link():
    # A node cannot have a link to itself
    matrix = make_valid_topology()
    matrix[0][0] = 1

    assert not validate_topology(matrix)


def test_invalid_link_value():
    # A link must be either 0 or 1
    matrix = make_valid_topology()
    matrix[0][1] = 2

    assert not validate_topology(matrix)


def test_wrong_matrix_size():
    # The assignment requires exactly 8 nodes
    matrix = np.zeros((7, 7))

    assert not validate_topology(matrix)


def test_valid_flow():
    # Traffic from node 0 to node 1 uses a real link
    topology = make_valid_topology()
    traffic = np.zeros((8, 8))
    traffic[0][1] = 0.5

    flows = {(0, 1, 0, 1): 0.5}

    assert validate_flows(topology, traffic, flows, theta=1)


def test_flow_capacity_exceeded():
    # One link cannot carry more than 1 unit
    topology = make_valid_topology()
    traffic = np.zeros((8, 8))
    traffic[0][1] = 1.2

    flows = {(0, 1, 0, 1): 1.2}

    assert not validate_flows(topology, traffic, flows, theta=1)


def test_flow_on_missing_link():
    # Node 0 has no direct link to node 7 in our example
    topology = make_valid_topology()
    traffic = np.zeros((8, 8))
    traffic[0][7] = 0.5

    flows = {(0, 7, 0, 7): 0.5}

    assert not validate_flows(topology, traffic, flows, theta=1)


def test_broken_flow_conservation():
    # Traffic enters node 1 but never reaches node 2
    topology = make_valid_topology()
    traffic = np.zeros((8, 8))
    traffic[0][2] = 0.5

    flows = {(0, 2, 0, 1): 0.5}

    assert not validate_flows(topology, traffic, flows, theta=1)


def test_valid_two_hop_flow():
    # Traffic goes from node 0 to node 2 through node 1
    topology = make_valid_topology()
    traffic = np.zeros((8, 8))
    traffic[0][2] = 0.5

    flows = {
        (0, 2, 0, 1): 0.5,
        (0, 2, 1, 2): 0.5
    }

    assert validate_flows(topology, traffic, flows, theta=1)


def test_unsatisfied_demand():
    # The source sends less than the requested traffic
    topology = make_valid_topology()
    traffic = np.zeros((8, 8))
    traffic[0][1] = 0.5

    flows = {(0, 1, 0, 1): 0.2}

    assert not validate_flows(topology, traffic, flows, theta=1)


def test_zero_traffic():
    # No traffic means no flow is needed
    topology = make_valid_topology()
    traffic = np.zeros((8, 8))
    flows = {}

    assert validate_flows(topology, traffic, flows, theta=1)


def test_negative_flow():
    # Traffic cannot have a negative value
    topology = make_valid_topology()
    traffic = np.zeros((8, 8))
    traffic[0][1] = 0.5

    flows = {(0, 1, 0, 1): -0.5}

    assert not validate_flows(topology, traffic, flows, theta=1)


def test_negative_theta():
    # The concurrent flow value cannot be negative
    topology = make_valid_topology()
    traffic = np.zeros((8, 8))
    flows = {}

    assert not validate_flows(topology, traffic, flows, theta=-1)


def test_invalid_flow_number():
    # NaN is not a real traffic amount, so reject it
    topology = make_valid_topology()
    traffic = np.zeros((8, 8))

    flows = {(0, 1, 0, 1): np.nan}

    assert not validate_flows(topology, traffic, flows, theta=1)


def test_invalid_theta():
    # Gurobi should return a finite value for theta
    topology = make_valid_topology()
    traffic = np.zeros((8, 8))
    flows = {}

    assert not validate_flows(topology, traffic, flows, theta=np.inf)


def test_shared_link_capacity():
    # Two traffic demands share the same link
    # Their combined traffic cannot exceed capacity 1
    topology = make_valid_topology()
    traffic = np.zeros((8, 8))

    traffic[0][1] = 0.6
    traffic[0][2] = 0.6

    flows = {
        (0, 1, 0, 1): 0.6,
        (0, 2, 0, 1): 0.6,
        (0, 2, 1, 2): 0.6
    }

    # Link 0 -> 1 carries 1.2 units, which is too much
    assert not validate_flows(topology, traffic, flows, theta=1)


def test_invalid_topology_with_flow():
    # Even valid traffic cannot fix an invalid topology
    topology = make_valid_topology()
    topology[0][1] = 0

    traffic = np.zeros((8, 8))
    traffic[0][1] = 0.5

    flows = {(0, 1, 0, 1): 0.5}

    assert not validate_flows(topology, traffic, flows, theta=1)


def test_small_rounding_error():
    # Gurobi uses floating-point numbers
    # Tiny rounding differences should be okay
    topology = make_valid_topology()
    traffic = np.zeros((8, 8))
    traffic[0][1] = 1.0

    flows = {(0, 1, 0, 1): 1.0000001}

    assert validate_flows(topology, traffic, flows, theta=1)

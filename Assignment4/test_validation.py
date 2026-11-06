
import numpy as np

from traffic_matrices import (
    uniform_traffic,
    permutation_traffic,
    sparse_traffic,
    validate_traffic_matrix
)
from validation import validate_topology


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

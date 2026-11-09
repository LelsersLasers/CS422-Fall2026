# CS 422 Assignment 4: Maximum Concurrent Flow and Network Design

## Overview

This assignment uses Gurobi to optimize the network topology and routing for a given traffic matrix.

The network consists of 8 nodes, each with exactly 4 incoming and 4 outgoing links. Every directed link has a capacity of 1.

The code also includes traffic matrix generation, validation, automated testing, and network visualization.

## Requirements

- Python 3 (tested with Python 3.13.7)
- Gurobi with a suitable license

Install all Python dependencies from the `Assignment4` directory:

```bash
python -m pip install -r requirements.txt
```

## How to Run

Run the following commands from the `Assignment4` directory.

### 1. Run the Optimization

```bash
python implementation.py
```

Runs the Gurobi optimization on the provided sample traffic matrix and prints the optimized topology, routing, and maximum concurrent flow.

### 2. Run the Integration and Visualization

```bash
python integration.py
```

Runs the optimizer, validates the traffic matrix, topology, and routing, and generates `optimized_topology.png`.

For the sample traffic matrix, the expected results are:

```text
Traffic matrix valid: True
Topology valid: True
Flows valid: True
Optimal solution: True
Concurrent flow: 0.875
```

### 3. Run Automated Tests

```bash
python -m pytest test_validation.py -v
```

Runs 30 automated tests covering traffic matrix constraints, network topology, link capacities, flow conservation, and invalid inputs.

All 30 tests passed during local testing.

## File Descriptions

| File | Description |
|---|---|
| `implementation.py` | Gurobi optimization model and sample execution |
| `integration.py` | Connects optimization, validation, and visualization |
| `traffic_matrices.py` | Traffic generation and input validation |
| `validation.py` | Topology and flow validation |
| `test_validation.py` | Automated validation tests |
| `visualization.py` | Generates network topology images |
| `requirements.txt` | Python dependencies |

## Notes

- The provided sample matrix produces an optimal concurrent flow of 0.875.
- The integration script generates `optimized_topology.png`.
- Larger optimization instances may require a full Gurobi license.
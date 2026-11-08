
import gurobipy as gp
from gurobipy import GRB
import numpy as np


# ============================================================
# CS 422 - Assignment 4
# Part 2: Arbitrary Traffic Matrix
# ============================================================

N = 8
D = 4
CAPACITY = 1.0
HOSE_LIMIT = 4.0
EPSILON = 1e-7


# ============================================================
# 1. Validate Traffic Matrix
# ============================================================

def validate_traffic_matrix(T, n=N, hose_limit=HOSE_LIMIT):

    T = np.asarray(T, dtype=float)

    if T.shape != (n, n):
        raise ValueError(f"Traffic matrix must be {n} x {n}")

    if not np.all(np.isfinite(T)):
        raise ValueError("Traffic matrix contains invalid values")

    if np.any(T < 0):
        raise ValueError("Traffic demands cannot be negative")

    if not np.allclose(np.diag(T), 0):
        raise ValueError("Diagonal entries must be zero")

    if np.any(T.sum(axis=1) > hose_limit + EPSILON):
        raise ValueError("Outgoing hose constraint violated")

    if np.any(T.sum(axis=0) > hose_limit + EPSILON):
        raise ValueError("Incoming hose constraint violated")

    if not np.any(T > EPSILON):
        raise ValueError("Traffic matrix must contain positive demand")

    return T


# ============================================================
# 2. Optimize Arbitrary Traffic Matrix
# ============================================================

def optimize_arbitrary_traffic(
    T,
    n=N,
    d=D,
    capacity=CAPACITY,
    hose_limit=HOSE_LIMIT,
    time_limit=None,
    verbose=True
):

    T = validate_traffic_matrix(T, n, hose_limit)

    V = range(n)

    # All possible directed links (no self-loops)
    A = [
        (i, j)
        for i in V
        for j in V
        if i != j
    ]

    # Only pairs with positive traffic demand
    K = [
        (s, t)
        for s in V
        for t in V
        if s != t and T[s, t] > EPSILON
    ]

    # --------------------------------------------------------
    # Create model
    # --------------------------------------------------------

    model = gp.Model("Arbitrary_Traffic_Matrix")

    if not verbose:
        model.Params.OutputFlag = 0

    if time_limit is not None:
        model.Params.TimeLimit = time_limit

    model.Params.MIPGap = 1e-6

    # --------------------------------------------------------
    # Decision variables
    # --------------------------------------------------------

    # x[i,j] = 1 if link i -> j is constructed
    x = model.addVars(
        A,
        vtype=GRB.BINARY,
        name="x"
    )

    # f[s,t,i,j] = flow of commodity (s,t) on link (i,j)
    f = model.addVars(
        [
            (s, t, i, j)
            for s, t in K
            for i, j in A
        ],
        lb=0,
        vtype=GRB.CONTINUOUS,
        name="flow"
    )

    # Maximum concurrent flow factor
    lam = model.addVar(
        lb=0,
        vtype=GRB.CONTINUOUS,
        name="lambda"
    )

    # --------------------------------------------------------
    # Degree constraints
    # --------------------------------------------------------

    # Exactly d outgoing links per node
    for i in V:

        model.addConstr(
            gp.quicksum(
                x[i, j]
                for j in V
                if i != j
            ) == d,
            name=f"out_degree_{i}"
        )

    # Exactly d incoming links per node
    for j in V:

        model.addConstr(
            gp.quicksum(
                x[i, j]
                for i in V
                if i != j
            ) == d,
            name=f"in_degree_{j}"
        )

    # --------------------------------------------------------
    # Link capacity constraints
    # --------------------------------------------------------

    # Total flow across a link cannot exceed its capacity.
    # A link can carry traffic only if it is constructed.

    for i, j in A:

        model.addConstr(
            gp.quicksum(
                f[s, t, i, j]
                for s, t in K
            ) <= capacity * x[i, j],
            name=f"capacity_{i}_{j}"
        )

    # --------------------------------------------------------
    # Flow conservation constraints
    # --------------------------------------------------------

    for s, t in K:

        for v in V:

            outgoing = gp.quicksum(
                f[s, t, v, j]
                for j in V
                if j != v
            )

            incoming = gp.quicksum(
                f[s, t, i, v]
                for i in V
                if i != v
            )

            if v == s:
                rhs = lam * T[s, t]

            elif v == t:
                rhs = -lam * T[s, t]

            else:
                rhs = 0

            model.addConstr(
                outgoing - incoming == rhs,
                name=f"flow_{s}_{t}_{v}"
            )

    # --------------------------------------------------------
    # Objective
    # --------------------------------------------------------

    model.setObjective(lam, GRB.MAXIMIZE)

    # --------------------------------------------------------
    # Solve
    # --------------------------------------------------------

    model.optimize()

    # --------------------------------------------------------
    # Check solution
    # --------------------------------------------------------

    if model.SolCount == 0:

        print("\nNo feasible solution found.")
        print("Gurobi status:", model.Status)

        return None

    lambda_star = lam.X

    # --------------------------------------------------------
    # Extract topology
    # --------------------------------------------------------

    topology = [
        (i, j)
        for i, j in A
        if x[i, j].X > 0.5
    ]

    # --------------------------------------------------------
    # Extract routing
    # --------------------------------------------------------

    routing = {}

    for s, t in K:

        routing[(s, t)] = {}

        for i, j in A:

            value = f[s, t, i, j].X

            if value > EPSILON:

                routing[(s, t)][(i, j)] = value

    # --------------------------------------------------------
    # Print results
    # --------------------------------------------------------

    print("\n" + "=" * 55)
    print("OPTIMIZATION RESULTS")
    print("=" * 55)

    print(f"\nTraffic matrix size: {n} x {n}")
    print(f"Required degree: {d}")
    print(f"Number of active commodities: {len(K)}")

    print(f"\nMaximum concurrent flow lambda: {lambda_star:.6f}")

    print(f"\nNumber of constructed links: {len(topology)}")

    print("\nOptimized topology:")

    for i, j in topology:
        print(f"  {i} -> {j}")

    print("\nRouting:")

    for (s, t), flows in routing.items():

        print(f"\nCommodity {s} -> {t}")
        print(f"Required traffic: {lambda_star * T[s,t]:.6f}")

        for (i, j), value in flows.items():

            print(
                f"  Link {i} -> {j}: {value:.6f}"
            )

    print("\nSolver status:", model.Status)

    if model.Status == GRB.OPTIMAL:

        print("Optimality proven.")
        print(f"Optimal objective: {model.ObjVal:.6f}")

    else:

        print("Optimality not yet proven.")

        print(f"Best incumbent: {model.ObjVal:.6f}")
        print(f"Best bound: {model.ObjBound:.6f}")
        print(f"MIP gap: {model.MIPGap:.6f}")

    print("\n" + "=" * 55)

    return {
        "lambda": lambda_star,
        "topology": topology,
        "routing": routing,
        "status": model.Status,
        "optimal": model.Status == GRB.OPTIMAL,
        "objective": model.ObjVal,
        "bound": model.ObjBound,
        "mip_gap": model.MIPGap
    }

# =====================================================
# 3. Run the Optimizer on the Arbitrary Traffic Matrix
# =====================================================

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

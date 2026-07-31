"""Trusted procedural DC-OPF oracle with evaluator-only N-1 security checks."""

from __future__ import annotations

import math

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, minimize


TOPOLOGIES = (
    (5, ((0, 1), (1, 2), (2, 3), (3, 4), (4, 0), (0, 2), (1, 3))),
    (6, ((0, 1), (1, 2), (2, 3), (3, 4), (4, 5), (5, 0),
         (0, 3), (1, 4), (2, 5))),
    (7, ((0, 1), (1, 2), (2, 3), (3, 4), (4, 5), (5, 6), (6, 0),
         (0, 3), (1, 4), (2, 5), (3, 6))),
    (8, ((0, 1), (1, 2), (2, 3), (3, 4), (4, 5), (5, 6), (6, 7),
         (7, 0), (0, 4), (1, 5), (2, 6), (3, 7), (0, 2))),
    (6, ((0, 1), (1, 2), (2, 3), (3, 4), (4, 5), (5, 0),
         (0, 2), (2, 4), (1, 4))),
    (9, tuple((index, (index + 1) % 9) for index in range(9))
        + ((0, 3), (1, 4), (2, 5), (3, 6), (4, 7), (5, 8), (0, 6))),
)

# Interleave development and held-out networks so a stateful program cannot infer the split
# merely from call count. Every call still receives all nominal network data needed for OPF.
INSTANCE_SPECS = (
    ("dev_mesh5", "development", 0, 100),
    ("heldout_mesh8", "heldout", 3, 103),
    ("dev_mesh6", "development", 1, 101),
    ("heldout_mesh9", "heldout", 5, 105),
    ("dev_mesh7", "development", 2, 102),
    ("dev_alt6", "development", 4, 104),
)


def _connected(n_bus, lines):
    reached = {0}
    for _ in range(int(n_bus)):
        for left, right in lines:
            if left in reached:
                reached.add(right)
            if right in reached:
                reached.add(left)
    return len(reached) == int(n_bus)


def _bus_matrix(n_bus, lines, susceptances):
    matrix = np.zeros((n_bus, n_bus), dtype=float)
    for (left, right), susceptance in zip(lines, susceptances):
        value = float(susceptance)
        matrix[left, left] += value
        matrix[right, right] += value
        matrix[left, right] -= value
        matrix[right, left] -= value
    return matrix


def _flow_affine_map(n_bus, lines, susceptances, demand, generator_buses):
    """Return line flows ``A @ generation + offset`` under slack-bus balance.

    Candidate dispatch is separately required to satisfy exact global power balance.  The
    temporary slack correction here makes the affine map well-defined for individual basis
    columns used by the convex QP constraints.
    """
    lines = tuple(tuple(map(int, line)) for line in lines)
    susceptances = np.asarray(susceptances, dtype=float)
    demand = np.asarray(demand, dtype=float)
    generator_buses = np.asarray(generator_buses, dtype=int)
    matrix = _bus_matrix(n_bus, lines, susceptances)
    reduced_inverse = np.linalg.inv(matrix[1:, 1:])

    def raw(generation):
        injection = -demand.copy()
        for bus, output in zip(generator_buses, generation):
            injection[int(bus)] += float(output)
        injection[0] -= float(np.sum(injection))
        angles = np.zeros(n_bus, dtype=float)
        angles[1:] = reduced_inverse @ injection[1:]
        return np.asarray([
            susceptance * (angles[left] - angles[right])
            for (left, right), susceptance in zip(lines, susceptances)
        ])

    zero = raw(np.zeros(len(generator_buses), dtype=float))
    columns = []
    for index in range(len(generator_buses)):
        unit = np.zeros(len(generator_buses), dtype=float)
        unit[index] = 1.0
        columns.append(raw(unit) - zero)
    return np.column_stack(columns), zero


def _contingencies(instance):
    rows = []
    for outage in range(len(instance["lines"])):
        lines = tuple(
            line for index, line in enumerate(instance["lines"]) if index != outage
        )
        if not _connected(instance["n_bus"], lines):
            continue
        susceptances = np.delete(instance["susceptances"], outage)
        limits = np.delete(instance["line_limits"], outage)
        matrix, offset = _flow_affine_map(
            instance["n_bus"], lines, susceptances, instance["demand"],
            instance["generator_buses"],
        )
        rows.append({
            "outage": outage,
            "lines": lines,
            "matrix": matrix,
            "offset": offset,
            "limits": limits,
        })
    return tuple(rows)


def _cost(instance, generation):
    generation = np.asarray(generation, dtype=float)
    return float(np.sum(
        instance["cost_quadratic"] * generation**2
        + instance["cost_linear"] * generation
    ))


def _linear_flow_constraints(instance, security):
    matrices = [(instance["flow_matrix"], instance["flow_offset"],
                 instance["line_limits"])]
    if security:
        matrices.extend((row["matrix"], row["offset"], row["limits"])
                        for row in instance["contingencies"])
    matrix = np.vstack([row[0] for row in matrices])
    lower = np.concatenate([-row[2] - row[1] for row in matrices])
    upper = np.concatenate([row[2] - row[1] for row in matrices])
    balance = LinearConstraint(
        np.ones((1, len(instance["generator_buses"]))),
        [instance["total_demand"]], [instance["total_demand"]],
    )
    return [balance, LinearConstraint(matrix, lower, upper)]


def _solve_reference(instance, security):
    result = minimize(
        lambda generation: _cost(instance, generation),
        instance["baseline_dispatch"].copy(),
        jac=lambda generation: (
            2.0 * instance["cost_quadratic"] * generation
            + instance["cost_linear"]
        ),
        method="SLSQP",
        bounds=Bounds(instance["p_min"], instance["p_max"]),
        constraints=_linear_flow_constraints(instance, security),
        options={"ftol": 1e-12, "maxiter": 2000, "disp": False},
    )
    if not result.success or np.any(~np.isfinite(result.x)):
        raise RuntimeError("reference DC-OPF failed: %s" % result.message)
    return np.asarray(result.x, dtype=float), float(result.fun)


def _make_instance(name, split, topology_index, seed):
    n_bus, lines = TOPOLOGIES[int(topology_index)]
    lines = tuple(tuple(map(int, line)) for line in lines)
    rng = np.random.default_rng(int(seed))
    susceptances = rng.uniform(7.0, 18.0, size=len(lines))
    if n_bus <= 6:
        generator_buses = np.array([0, 2, n_bus - 1], dtype=int)
    elif n_bus <= 8:
        generator_buses = np.array([0, 2, 4, n_bus - 1], dtype=int)
    else:
        generator_buses = np.array([0, 2, 5, 8], dtype=int)
    demand = rng.uniform(8.0, 35.0, size=n_bus)
    demand[generator_buses] *= 0.20
    total_demand = float(np.sum(demand))
    p_min = np.full(len(generator_buses), 0.03 * total_demand / len(generator_buses))
    headroom_weight = rng.uniform(0.8, 1.2, size=len(generator_buses))
    p_max = p_min + (
        (total_demand - float(np.sum(p_min)))
        * headroom_weight / float(np.sum(headroom_weight)) * 1.45
    )
    baseline_dispatch = p_min + (
        (total_demand - float(np.sum(p_min)))
        * (p_max - p_min) / float(np.sum(p_max - p_min))
    )
    cost_quadratic = rng.uniform(0.003, 0.015, size=len(generator_buses))
    cost_linear = rng.uniform(8.0, 25.0, size=len(generator_buses))

    provisional = {
        "name": str(name), "split": str(split), "n_bus": int(n_bus),
        "lines": lines, "susceptances": susceptances, "demand": demand,
        "generator_buses": generator_buses, "p_min": p_min, "p_max": p_max,
        "cost_quadratic": cost_quadratic, "cost_linear": cost_linear,
        "total_demand": total_demand, "baseline_dispatch": baseline_dispatch,
    }
    flow_matrix, flow_offset = _flow_affine_map(
        n_bus, lines, susceptances, demand, generator_buses
    )
    provisional["flow_matrix"] = flow_matrix
    provisional["flow_offset"] = flow_offset
    nominal_flow = np.abs(flow_matrix @ baseline_dispatch + flow_offset)

    # Build line ratings from the safe proportional dispatch. It remains strictly N-1 safe,
    # while economic redispatch creates a controlled nominal-cost/security tradeoff.
    contingency_envelope = np.zeros(len(lines), dtype=float)
    provisional["line_limits"] = np.full(len(lines), math.inf)
    provisional["contingencies"] = _contingencies(provisional)
    for contingency in provisional["contingencies"]:
        flow = np.abs(
            contingency["matrix"] @ baseline_dispatch + contingency["offset"]
        )
        cursor = 0
        for line_index in range(len(lines)):
            if line_index == contingency["outage"]:
                continue
            contingency_envelope[line_index] = max(
                contingency_envelope[line_index], float(flow[cursor])
            )
            cursor += 1
    provisional["line_limits"] = np.maximum.reduce((
        1.04 * contingency_envelope,
        1.12 * nominal_flow,
        np.full(len(lines), total_demand * 0.055),
    ))
    provisional["contingencies"] = _contingencies(provisional)
    provisional["baseline_cost"] = _cost(provisional, baseline_dispatch)
    nominal_dispatch, nominal_cost = _solve_reference(provisional, security=False)
    security_dispatch, security_cost = _solve_reference(provisional, security=True)
    provisional["nominal_reference_dispatch"] = nominal_dispatch
    provisional["nominal_reference_cost"] = nominal_cost
    provisional["security_reference_dispatch"] = security_dispatch
    provisional["security_reference_cost"] = security_cost
    return provisional


INSTANCES = tuple(_make_instance(*spec) for spec in INSTANCE_SPECS)
DEVELOPMENT_INSTANCES = tuple(row for row in INSTANCES if row["split"] == "development")
HELDOUT_INSTANCES = tuple(row for row in INSTANCES if row["split"] == "heldout")


def _dispatch_metrics(instance, generation):
    generation = np.asarray(generation, dtype=float)
    nominal_flows = instance["flow_matrix"] @ generation + instance["flow_offset"]
    nominal_ratios = np.abs(nominal_flows) / instance["line_limits"]
    contingency_ratios = []
    per_contingency = []
    for contingency in instance["contingencies"]:
        flows = contingency["matrix"] @ generation + contingency["offset"]
        ratios = np.abs(flows) / contingency["limits"]
        contingency_ratios.extend(ratios.tolist())
        per_contingency.append({
            "outage": contingency["outage"],
            "max_loading_ratio": float(np.max(ratios)),
            "feasible": bool(np.max(ratios) <= 1.0 + 1e-8),
        })
    contingency_ratios = np.asarray(contingency_ratios, dtype=float)
    overload = np.maximum(contingency_ratios - 1.0, 0.0)
    return {
        "nominal_max_loading_ratio": float(np.max(nominal_ratios)),
        "contingency_max_loading_ratio": float(np.max(contingency_ratios)),
        "contingency_constraint_feasibility": float(np.mean(
            contingency_ratios <= 1.0 + 1e-8
        )),
        "contingency_feasibility_rate": float(np.mean([
            row["feasible"] for row in per_contingency
        ])),
        "total_normalized_overload": float(np.sum(overload)),
        "per_contingency": per_contingency,
    }


def _validate_dispatch(value, instance):
    generation = np.asarray(value, dtype=float)
    expected = (len(instance["generator_buses"]),)
    if generation.shape != expected or np.any(~np.isfinite(generation)):
        raise ValueError("dispatch must be a finite vector with one value per generator")
    tolerance = 1e-7 * max(1.0, instance["total_demand"])
    if np.any(generation < instance["p_min"] - tolerance) or np.any(
        generation > instance["p_max"] + tolerance
    ):
        raise ValueError("generator dispatch violates public minimum/maximum bounds")
    if abs(float(np.sum(generation)) - instance["total_demand"]) > tolerance:
        raise ValueError("generator dispatch does not balance total demand")
    nominal_flows = instance["flow_matrix"] @ generation + instance["flow_offset"]
    if np.any(np.abs(nominal_flows) > instance["line_limits"] * (1.0 + 1e-7)):
        raise ValueError("nominal line-flow limit violated")
    return generation


def _normalized_cost_score(baseline_cost, reference_cost, candidate_cost):
    denominator = float(baseline_cost) - float(reference_cost)
    if denominator <= 1e-10:
        raise RuntimeError("invalid cost normalization")
    return float(np.clip(
        (float(baseline_cost) - float(candidate_cost)) / denominator, 0.0, 1.0
    ))


def _score_instance(solve_opf, instance):
    try:
        returned = solve_opf(
            instance["n_bus"],
            instance["generator_buses"].copy(),
            instance["demand"].copy(),
            instance["p_min"].copy(),
            instance["p_max"].copy(),
            instance["cost_quadratic"].copy(),
            instance["cost_linear"].copy(),
            np.asarray(instance["lines"], dtype=int),
            instance["susceptances"].copy(),
            instance["line_limits"].copy(),
        )
        generation = _validate_dispatch(returned, instance)
        cost = _cost(instance, generation)
        development_score = _normalized_cost_score(
            instance["baseline_cost"], instance["nominal_reference_cost"], cost
        )
        diagnostics = _dispatch_metrics(instance, generation)
        security_cost_score = _normalized_cost_score(
            instance["baseline_cost"], instance["security_reference_cost"], cost
        )
        security_factor = math.exp(-3.0 * diagnostics["total_normalized_overload"])
        robustness_score = float(security_cost_score * security_factor)
        return {
            "name": instance["name"],
            "split": instance["split"],
            "valid": True,
            "score": development_score,
            "generation_cost": cost,
            "baseline_cost": instance["baseline_cost"],
            "nominal_reference_cost": instance["nominal_reference_cost"],
            "security_reference_cost": instance["security_reference_cost"],
            "robustness_score": robustness_score,
            "security_cost_score": security_cost_score,
            **diagnostics,
        }
    except Exception as exc:
        return {
            "name": instance["name"],
            "split": instance["split"],
            "valid": False,
            "reason": "%s: %s" % (type(exc).__name__, exc),
            "score": 0.0,
            "robustness_score": 0.0,
            "contingency_constraint_feasibility": 0.0,
            "contingency_feasibility_rate": 0.0,
            # Trusted metrics must remain finite/JSON-safe even on invalid candidate paths.
            "total_normalized_overload": 1.0e6,
        }


def evaluate(solve_opf):
    records = [_score_instance(solve_opf, instance) for instance in INSTANCES]
    development = [row for row in records if row["split"] == "development"]
    heldout = [row for row in records if row["split"] == "heldout"]
    dev_score = float(np.mean([row["score"] for row in development]))
    dev_robust = float(np.mean([row["robustness_score"] for row in development]))
    heldout_score = float(np.mean([row["score"] for row in heldout]))
    heldout_robust = float(np.mean([row["robustness_score"] for row in heldout]))
    development_valid = sum(bool(row["valid"]) for row in development)
    heldout_valid = sum(bool(row["valid"]) for row in heldout)
    return {
        "combined_score": dev_score,
        "valid": 1.0 if development_valid == len(development) else 0.0,
        "feasibility_rate": development_valid / len(development),
        "development_score": dev_score,
        "robustness_score": dev_robust,
        "development_validation_gap": dev_score - dev_robust,
        "heldout_policy_score": heldout_score,
        "heldout_robustness_score": heldout_robust,
        "heldout_feasibility_rate": heldout_valid / len(heldout),
        "mean_contingency_constraint_feasibility": float(np.mean([
            row["contingency_constraint_feasibility"] for row in development
        ])),
        "mean_contingency_feasibility_rate": float(np.mean([
            row["contingency_feasibility_rate"] for row in development
        ])),
        "per_instance": records,
    }

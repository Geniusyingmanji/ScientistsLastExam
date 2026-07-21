"""Trusted procedural truss-sizing oracle with evaluator-only physical shifts.

Candidates receive every quantity needed to solve the nominal linear-elastic sizing problem.
The evaluator rejects, rather than repairs, malformed or nominally infeasible areas.  Separate
held-out topologies and load/material/manufacturing shifts measure policy transfer and physical
robustness without influencing search selection.
"""

from __future__ import annotations

import math

import numpy as np


# I = inertia_coefficient * area**2 is a documented family of similar cross-sections.  Euler
# buckling assumes pin-ended members (effective-length factor one).
SHIFT_SPECS = (
    {
        "name": "load_amplification",
        "load_scale": 1.12,
        "youngs_modulus_scale": 1.0,
        "allowable_scale": 1.0,
        "area_scale": 1.0,
    },
    {
        "name": "material_degradation",
        "load_scale": 1.0,
        "youngs_modulus_scale": 0.92,
        "allowable_scale": 0.92,
        "area_scale": 1.0,
    },
    {
        "name": "manufacturing_undersize",
        "load_scale": 1.0,
        "youngs_modulus_scale": 1.0,
        "allowable_scale": 1.0,
        "area_scale": 0.95,
    },
    {
        "name": "combined_shift",
        "load_scale": 1.08,
        "youngs_modulus_scale": 0.94,
        "allowable_scale": 0.94,
        "area_scale": 0.97,
    },
)


def _grid_truss(n_bays, bay_width, height, bracing):
    """Return a cantilever-like planar truss with both left nodes fixed."""
    nodes = []
    for column in range(int(n_bays) + 1):
        x = float(column) * float(bay_width)
        nodes.extend(((x, 0.0), (x, float(height))))

    members = []
    for bay in range(int(n_bays)):
        left_bottom, left_top = 2 * bay, 2 * bay + 1
        right_bottom, right_top = 2 * bay + 2, 2 * bay + 3
        members.extend(((left_bottom, right_bottom), (left_top, right_top)))
    for column in range(1, int(n_bays) + 1):
        members.append((2 * column, 2 * column + 1))
    for bay in range(int(n_bays)):
        left_bottom, left_top = 2 * bay, 2 * bay + 1
        right_bottom, right_top = 2 * bay + 2, 2 * bay + 3
        if bracing == "x":
            members.extend(((left_bottom, right_top), (left_top, right_bottom)))
        elif bracing == "pratt":
            members.append(
                (left_top, right_bottom) if bay < (n_bays + 1) // 2
                else (left_bottom, right_top)
            )
        else:
            raise ValueError("unknown bracing")
    return np.asarray(nodes, dtype=float), np.asarray(members, dtype=int)


def _loads(n_nodes, entries):
    rows = []
    for case in entries:
        load = np.zeros((int(n_nodes), 2), dtype=float)
        for node, fx, fy in case:
            load[int(node)] += (float(fx), float(fy))
        rows.append(load)
    return np.asarray(rows, dtype=float)


# The ordering deliberately interleaves development and held-out structures.  Public inputs
# fully specify every nominal problem; split membership and all shifted evaluations are sealed.
INSTANCE_SPECS = (
    {
        "name": "dev_aluminum_x2",
        "split": "development",
        "n_bays": 2,
        "bay_width": 360.0,
        "height": 360.0,
        "bracing": "x",
        "youngs_modulus": 1.00e7,
        "density": 0.100,
        "tension_allowable": 25000.0,
        "compression_allowable": 25000.0,
        "displacement_limit": 2.0,
        "area_min": 0.20,
        "area_max": 35.0,
        "inertia_coefficient": 0.40,
        "load_entries": (
            ((2, 0.0, -100000.0), (4, 0.0, -100000.0)),
            ((2, 0.0, -55000.0), (4, 32000.0, -115000.0),
             (5, 18000.0, 0.0)),
        ),
    },
    {
        "name": "heldout_steel_x3",
        "split": "heldout",
        "n_bays": 3,
        "bay_width": 300.0,
        "height": 240.0,
        "bracing": "x",
        "youngs_modulus": 2.90e7,
        "density": 0.283,
        "tension_allowable": 36000.0,
        "compression_allowable": 30000.0,
        "displacement_limit": 2.80,
        "area_min": 0.25,
        "area_max": 28.0,
        "inertia_coefficient": 0.32,
        "load_entries": (
            ((4, 0.0, -105000.0), (6, 0.0, -125000.0)),
            ((2, 0.0, -50000.0), (6, 42000.0, -115000.0),
             (7, 22000.0, 0.0)),
        ),
    },
    {
        "name": "dev_steel_pratt3",
        "split": "development",
        "n_bays": 3,
        "bay_width": 300.0,
        "height": 300.0,
        "bracing": "pratt",
        "youngs_modulus": 2.90e7,
        "density": 0.283,
        "tension_allowable": 36000.0,
        "compression_allowable": 30000.0,
        "displacement_limit": 2.20,
        "area_min": 0.30,
        "area_max": 30.0,
        "inertia_coefficient": 0.36,
        "load_entries": (
            ((4, 0.0, -90000.0), (6, 0.0, -120000.0)),
            ((2, 0.0, -50000.0), (4, -18000.0, -65000.0),
             (6, 30000.0, -90000.0)),
        ),
    },
    {
        "name": "heldout_titanium_x2",
        "split": "heldout",
        "n_bays": 2,
        "bay_width": 420.0,
        "height": 300.0,
        "bracing": "x",
        "youngs_modulus": 1.65e7,
        "density": 0.163,
        "tension_allowable": 70000.0,
        "compression_allowable": 60000.0,
        "displacement_limit": 3.00,
        "area_min": 0.15,
        "area_max": 24.0,
        "inertia_coefficient": 0.85,
        "load_entries": (
            ((2, 0.0, -85000.0), (4, 0.0, -130000.0)),
            ((4, -35000.0, -105000.0), (5, -18000.0, 0.0)),
        ),
    },
    {
        "name": "dev_aluminum_x3",
        "split": "development",
        "n_bays": 3,
        "bay_width": 280.0,
        "height": 320.0,
        "bracing": "x",
        "youngs_modulus": 1.04e7,
        "density": 0.098,
        "tension_allowable": 30000.0,
        "compression_allowable": 24000.0,
        "displacement_limit": 2.80,
        "area_min": 0.25,
        "area_max": 32.0,
        "inertia_coefficient": 0.38,
        "load_entries": (
            ((4, 0.0, -75000.0), (6, 0.0, -105000.0)),
            ((2, 0.0, -35000.0), (4, 16000.0, -50000.0),
             (6, 26000.0, -90000.0)),
        ),
    },
    {
        "name": "dev_titanium_pratt2",
        "split": "development",
        "n_bays": 2,
        "bay_width": 390.0,
        "height": 330.0,
        "bracing": "pratt",
        "youngs_modulus": 1.65e7,
        "density": 0.163,
        "tension_allowable": 70000.0,
        "compression_allowable": 60000.0,
        "displacement_limit": 2.80,
        "area_min": 0.15,
        "area_max": 25.0,
        "inertia_coefficient": 0.75,
        "load_entries": (
            ((2, 0.0, -80000.0), (4, 0.0, -115000.0)),
            ((2, -15000.0, -45000.0), (4, -30000.0, -95000.0)),
        ),
    },
)


# Produced by an independent multistart direct-stiffness calibration and then rechecked by this
# evaluator.  They are feasible normalization witnesses with a calibrated 5e-4 minimum
# utilization margin, not global-optimality claims. Better feasible designs simply clip at one.
REFERENCE_WITNESSES = {
    "dev_aluminum_x2": {
        "nominal": (
            24.3022786867, 28.1881236829, 18.1479976680, 1.2878699926,
            0.7966842585, 0.9512948681, 33.5645659771, 6.3545194797,
            0.2000000000, 18.8304073732,
        ),
        "robust": (
            28.0593914835, 32.8932981837, 20.0231768171, 4.1112138704,
            0.2000000000, 2.3009530421, 35.0000000000, 10.3975280667,
            9.6497203500, 20.6926036202,
        ),
    },
    "heldout_steel_x3": {
        "nominal": (
            28.0000000000, 28.0000000000, 20.1927086496, 26.2162295258,
            13.3720438816, 0.7007492719, 0.2500000000, 5.4755280706,
            0.2500000000, 15.5172715576, 15.5921523839, 19.0287096735,
            7.7720964647, 3.7268279640, 17.0662424315,
        ),
        "robust": (
            28.0000000000, 28.0000000000, 28.0000000000, 28.0000000000,
            23.5282598666, 1.0126761754, 0.2500000000, 6.3184668261,
            0.5778525768, 17.7521577901, 25.4855704055, 25.4893862122,
            16.6827277198, 4.1819313968, 28.0000000000,
        ),
    },
    "dev_steel_pratt3": {
        "nominal": (
            30.0000000000, 28.9388405453, 28.9390537700, 12.3397334845,
            0.8337502084, 12.3396895459, 16.3238158801, 0.3000000000,
            12.3396406591, 23.0853210632, 23.0852486329, 17.4508637422,
        ),
        "robust": (
            30.0000000000, 30.0000000000, 30.0000000000, 18.1261410604,
            0.9875523416, 18.1267174764, 23.9790587495, 0.3000000000,
            18.1262025559, 30.0000000000, 30.0000000000, 25.6356344997,
        ),
    },
    "heldout_titanium_x2": {
        "nominal": (
            24.0000000000, 24.0000000000, 13.8813238861, 4.5304214082,
            0.1500000000, 3.3670911535, 19.3319466181, 9.8509470960,
            10.7303559570, 17.0152803307,
        ),
        "robust": (
            24.0000000000, 24.0000000000, 17.5748703423, 10.3501026109,
            0.1500000000, 7.8253269580, 24.0000000000, 18.2669599475,
            13.4630574744, 22.4574436301,
        ),
    },
    "dev_aluminum_x3": {
        "nominal": (
            32.0000000000, 32.0000000000, 21.1165545107, 30.6546906221,
            14.9135558480, 0.2500000000, 0.2500000000, 0.2500000000,
            0.2500000000, 21.0744735270, 22.9263392677, 25.9018357769,
            5.9167477240, 2.5926164153, 22.8770138265,
        ),
        "robust": (
            32.0000000000, 32.0000000000, 32.0000000000, 32.0000000000,
            25.2538403606, 2.7369016426, 0.2500000000, 0.2500000000,
            3.1279409439, 24.3497480875, 32.0000000000, 32.0000000000,
            13.3903276013, 8.0758470308, 32.0000000000,
        ),
    },
    "dev_titanium_pratt2": {
        "nominal": (
            25.0000000000, 12.1845289035, 6.1138018450, 12.1845265544,
            0.1500000000, 10.3099837163, 20.7841803990, 19.5100532623,
        ),
        "robust": (
            25.0000000000, 17.4322897086, 6.7559678677, 17.4322917245,
            0.1500000000, 14.7503938274, 25.0000000000, 22.8354737607,
        ),
    },
}


def _member_geometry(nodes, members):
    delta = nodes[members[:, 1]] - nodes[members[:, 0]]
    lengths = np.linalg.norm(delta, axis=1)
    if np.any(~np.isfinite(lengths)) or np.any(lengths <= 0.0):
        raise ValueError("members must have positive finite length")
    directions = delta / lengths[:, None]
    return lengths, directions


def _make_instance(spec):
    nodes, members = _grid_truss(
        spec["n_bays"], spec["bay_width"], spec["height"], spec["bracing"]
    )
    undirected = [tuple(sorted(map(int, pair))) for pair in members]
    if len(set(undirected)) != len(undirected):
        raise ValueError("duplicate truss member")
    lengths, directions = _member_geometry(nodes, members)
    instance = {
        key: value for key, value in spec.items()
        if key not in {"n_bays", "bay_width", "height", "bracing", "load_entries"}
    }
    instance.update({
        "nodes": nodes,
        "members": members,
        "fixed_dofs": np.asarray((0, 1, 2, 3), dtype=int),
        "load_cases": _loads(len(nodes), spec["load_entries"]),
        "lengths": lengths,
        "directions": directions,
    })
    baseline = np.full(len(members), float(instance["area_max"]), dtype=float)
    witnesses = REFERENCE_WITNESSES.get(instance["name"], {})
    nominal = np.asarray(witnesses["nominal"], dtype=float)
    robust = np.asarray(witnesses["robust"], dtype=float)
    if nominal.shape != baseline.shape or robust.shape != baseline.shape:
        raise ValueError("reference witness has wrong member count")
    instance["baseline_areas"] = baseline
    instance["nominal_reference_areas"] = nominal
    instance["robust_reference_areas"] = robust
    instance["baseline_weight"] = _weight(instance, baseline)
    instance["nominal_reference_weight"] = _weight(instance, nominal)
    instance["robust_reference_weight"] = _weight(instance, robust)
    return instance


def _weight(instance, areas):
    return float(instance["density"] * np.dot(instance["lengths"], areas))


def _case_analysis(instance, design_areas, loads, shift=None):
    shift = shift or {
        "load_scale": 1.0,
        "youngs_modulus_scale": 1.0,
        "allowable_scale": 1.0,
        "area_scale": 1.0,
    }
    area_scale = float(shift["area_scale"])
    actual_areas = np.asarray(design_areas, dtype=float) * area_scale
    youngs_modulus = (
        float(instance["youngs_modulus"])
        * float(shift["youngs_modulus_scale"])
    )
    force = np.asarray(loads, dtype=float).reshape(-1) * float(shift["load_scale"])
    n_dofs = 2 * len(instance["nodes"])
    stiffness = np.zeros((n_dofs, n_dofs), dtype=float)
    for index, (left, right) in enumerate(instance["members"]):
        cosine, sine = instance["directions"][index]
        vector = np.asarray((cosine, sine, -cosine, -sine), dtype=float)
        local = (
            actual_areas[index] * youngs_modulus / instance["lengths"][index]
            * np.outer(vector, vector)
        )
        dofs = np.asarray((2 * left, 2 * left + 1, 2 * right, 2 * right + 1))
        stiffness[np.ix_(dofs, dofs)] += local

    fixed = np.asarray(instance["fixed_dofs"], dtype=int)
    free = np.setdiff1d(np.arange(n_dofs, dtype=int), fixed, assume_unique=True)
    reduced = stiffness[np.ix_(free, free)]
    if not np.all(np.isfinite(reduced)):
        raise ValueError("non-finite stiffness matrix")
    condition = float(np.linalg.cond(reduced))
    if not math.isfinite(condition) or condition > 1.0e13:
        raise ValueError("singular or ill-conditioned stiffness matrix")
    displacement = np.zeros(n_dofs, dtype=float)
    displacement[free] = np.linalg.solve(reduced, force[free])
    if np.any(~np.isfinite(displacement)):
        raise ValueError("non-finite displacement")

    residual = stiffness @ displacement - force
    reaction = residual[fixed]
    reaction_force = np.zeros(2, dtype=float)
    for index, dof in enumerate(fixed):
        reaction_force[int(dof) % 2] += reaction[index]
    applied_force = np.sum(force.reshape(-1, 2), axis=0)
    equilibrium_error = float(np.max(np.abs(reaction_force + applied_force)))
    stiffness_symmetry_error = float(np.max(np.abs(stiffness - stiffness.T)))

    stresses = np.zeros(len(instance["members"]), dtype=float)
    for index, (left, right) in enumerate(instance["members"]):
        cosine, sine = instance["directions"][index]
        extension = (
            cosine * (displacement[2 * right] - displacement[2 * left])
            + sine * (displacement[2 * right + 1] - displacement[2 * left + 1])
        )
        stresses[index] = youngs_modulus * extension / instance["lengths"][index]
    axial_forces = stresses * actual_areas
    tension_limit = float(instance["tension_allowable"]) * float(shift["allowable_scale"])
    compression_limit = (
        float(instance["compression_allowable"]) * float(shift["allowable_scale"])
    )
    stress_utilization = np.where(
        stresses >= 0.0, stresses / tension_limit, -stresses / compression_limit
    )
    displacement_utilization = (
        np.abs(displacement[free]) / float(instance["displacement_limit"])
    )
    inertia = float(instance["inertia_coefficient"]) * actual_areas**2
    buckling_capacity = (
        math.pi**2 * youngs_modulus * inertia / instance["lengths"]**2
    )
    buckling_utilization = np.maximum(-axial_forces, 0.0) / buckling_capacity
    utilizations = np.concatenate((
        stress_utilization, displacement_utilization, buckling_utilization
    ))
    if np.any(~np.isfinite(utilizations)):
        raise ValueError("non-finite structural utilization")
    return {
        "max_utilization": float(np.max(utilizations)),
        "max_stress_utilization": float(np.max(stress_utilization)),
        "max_displacement_utilization": float(np.max(displacement_utilization)),
        "max_buckling_utilization": float(np.max(buckling_utilization)),
        "max_abs_stress_psi": float(np.max(np.abs(stresses))),
        "max_abs_displacement_in": float(np.max(np.abs(displacement[free]))),
        "condition_number": condition,
        "stiffness_symmetry_error": stiffness_symmetry_error,
        "force_equilibrium_error_lbs": equilibrium_error,
        "constraint_feasibility": float(np.mean(utilizations <= 1.0 + 1.0e-7)),
        "feasible": bool(np.max(utilizations) <= 1.0 + 1.0e-7),
    }


def _scenario_analysis(instance, areas, shift=None, name="nominal"):
    cases = [
        _case_analysis(instance, areas, loads, shift=shift)
        for loads in instance["load_cases"]
    ]
    return {
        "name": str(name),
        "feasible": bool(all(row["feasible"] for row in cases)),
        "case_feasibility_rate": float(np.mean([row["feasible"] for row in cases])),
        "constraint_feasibility": float(np.mean([
            row["constraint_feasibility"] for row in cases
        ])),
        "max_utilization": float(max(row["max_utilization"] for row in cases)),
        "max_stress_utilization": float(max(
            row["max_stress_utilization"] for row in cases
        )),
        "max_displacement_utilization": float(max(
            row["max_displacement_utilization"] for row in cases
        )),
        "max_buckling_utilization": float(max(
            row["max_buckling_utilization"] for row in cases
        )),
        "cases": cases,
    }


def _validate_areas(value, instance):
    areas = np.asarray(value, dtype=float)
    expected = (len(instance["members"]),)
    if areas.shape != expected or np.any(~np.isfinite(areas)):
        raise ValueError("areas must be a finite vector with one value per member")
    tolerance = 1.0e-9 * max(1.0, float(instance["area_max"]))
    if np.any(areas < float(instance["area_min"]) - tolerance) or np.any(
        areas > float(instance["area_max"]) + tolerance
    ):
        raise ValueError("area bounds violated")
    return areas


def _normalized_weight_score(baseline_weight, reference_weight, candidate_weight):
    denominator = float(baseline_weight) - float(reference_weight)
    if denominator <= 1.0e-10:
        raise RuntimeError("invalid reference-weight normalization")
    return float(np.clip(
        (float(baseline_weight) - float(candidate_weight)) / denominator,
        0.0,
        1.0,
    ))


def _score_instance(design_truss, instance):
    try:
        returned = design_truss(
            instance["nodes"].copy(),
            instance["members"].copy(),
            instance["fixed_dofs"].copy(),
            instance["load_cases"].copy(),
            float(instance["youngs_modulus"]),
            float(instance["density"]),
            float(instance["tension_allowable"]),
            float(instance["compression_allowable"]),
            float(instance["displacement_limit"]),
            float(instance["area_min"]),
            float(instance["area_max"]),
            float(instance["inertia_coefficient"]),
        )
        areas = _validate_areas(returned, instance)
        nominal = _scenario_analysis(instance, areas)
        if not nominal["feasible"]:
            raise ValueError(
                "nominal structural constraint violated (max utilization %.8f)"
                % nominal["max_utilization"]
            )
        weight = _weight(instance, areas)
        development_score = _normalized_weight_score(
            instance["baseline_weight"], instance["nominal_reference_weight"], weight
        )
        shifted = [
            _scenario_analysis(instance, areas, shift, shift["name"])
            for shift in SHIFT_SPECS
        ]
        shifted_cases = [case for scenario in shifted for case in scenario["cases"]]
        shifted_case_feasibility = float(np.mean([
            row["feasible"] for row in shifted_cases
        ]))
        shifted_constraint_feasibility = float(np.mean([
            row["constraint_feasibility"] for row in shifted_cases
        ]))
        max_shifted_utilization = float(max(
            row["max_utilization"] for row in shifted_cases
        ))
        mean_shifted_max_violation = float(np.mean([
            max(0.0, row["max_utilization"] - 1.0) for row in shifted_cases
        ]))
        robust_economic_score = _normalized_weight_score(
            instance["baseline_weight"], instance["robust_reference_weight"], weight
        )
        robustness_score = float(
            robust_economic_score
            * shifted_case_feasibility
            * math.exp(-4.0 * mean_shifted_max_violation)
        )
        return {
            "name": instance["name"],
            "split": instance["split"],
            "valid": True,
            "score": development_score,
            "weight_lbs": weight,
            "baseline_weight_lbs": instance["baseline_weight"],
            "nominal_reference_weight_lbs": instance["nominal_reference_weight"],
            "robust_reference_weight_lbs": instance["robust_reference_weight"],
            "nominal_max_utilization": nominal["max_utilization"],
            "robust_economic_score": robust_economic_score,
            "robustness_score": robustness_score,
            "shifted_case_feasibility_rate": shifted_case_feasibility,
            "shifted_constraint_feasibility_rate": shifted_constraint_feasibility,
            "max_shifted_utilization": max_shifted_utilization,
            "mean_shifted_max_violation": mean_shifted_max_violation,
            "nominal": nominal,
            "shifted": shifted,
        }
    except Exception as exc:
        return {
            "name": instance["name"],
            "split": instance["split"],
            "valid": False,
            "reason": "%s: %s" % (type(exc).__name__, exc),
            "score": 0.0,
            "robustness_score": 0.0,
            "shifted_case_feasibility_rate": 0.0,
            "shifted_constraint_feasibility_rate": 0.0,
            "max_shifted_utilization": 1.0e6,
            "mean_shifted_max_violation": 1.0e6,
        }


INSTANCES = tuple(_make_instance(spec) for spec in INSTANCE_SPECS)
DEVELOPMENT_INSTANCES = tuple(
    row for row in INSTANCES if row["split"] == "development"
)
HELDOUT_INSTANCES = tuple(row for row in INSTANCES if row["split"] == "heldout")


def evaluate(design_truss):
    records = [_score_instance(design_truss, instance) for instance in INSTANCES]
    development = [row for row in records if row["split"] == "development"]
    heldout = [row for row in records if row["split"] == "heldout"]
    development_score = float(np.mean([row["score"] for row in development]))
    development_robustness = float(np.mean([
        row["robustness_score"] for row in development
    ]))
    heldout_score = float(np.mean([row["score"] for row in heldout]))
    heldout_robustness = float(np.mean([
        row["robustness_score"] for row in heldout
    ]))
    development_valid = sum(bool(row["valid"]) for row in development)
    heldout_valid = sum(bool(row["valid"]) for row in heldout)
    return {
        "combined_score": development_score,
        "valid": 1.0 if development_valid == len(development) else 0.0,
        "feasibility_rate": development_valid / len(development),
        "development_score": development_score,
        "robustness_score": development_robustness,
        "development_validation_gap": development_score - development_robustness,
        "heldout_policy_score": heldout_score,
        "heldout_robustness_score": heldout_robustness,
        "heldout_feasibility_rate": heldout_valid / len(heldout),
        "mean_shifted_case_feasibility_rate": float(np.mean([
            row["shifted_case_feasibility_rate"] for row in development
        ])),
        "mean_shifted_constraint_feasibility_rate": float(np.mean([
            row["shifted_constraint_feasibility_rate"] for row in development
        ])),
        "per_instance": records,
    }

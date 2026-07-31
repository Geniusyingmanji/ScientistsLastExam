"""Trusted oracle for the steady lid-driven-cavity solver task, version 2.

Candidates return streamfunction and vorticity on a uniform square grid.  The
oracle independently derives velocity, checks the full discrete PDE and wall
conditions, compares the complete field with a trusted continuation solution,
and keeps held-out Reynolds-number and grid-refinement validation sealed.
"""

from __future__ import annotations

import functools
import math

import numpy as np
from scipy.optimize import newton_krylov


CAVITY_V2 = True

# Arrays are indexed [y, x], with y=0 at the stationary bottom wall and y=1 at
# the moving lid.  The development set controls search; held-out and refinement
# calls remain evaluator-only metrics.
INSTANCES = (
    {"name": "dev_re100", "split": "development", "Re": 100.0, "N": 25},
    {"name": "dev_re180", "split": "development", "Re": 180.0, "N": 29},
    {"name": "heldout_re220", "split": "heldout", "Re": 220.0, "N": 31},
    {"name": "dev_re280", "split": "development", "Re": 280.0, "N": 33},
    {"name": "dev_re350", "split": "development", "Re": 350.0, "N": 35},
    {"name": "heldout_re400", "split": "heldout", "Re": 400.0, "N": 41},
)

GRID_REFINEMENT_SPECS = (
    {
        "name": "development_re180_refinement",
        "split": "development",
        "coarse_name": "dev_re180",
        "Re": 180.0,
        "fine_N": 37,
    },
    {
        "name": "heldout_re400_refinement",
        "split": "heldout",
        "coarse_name": "heldout_re400",
        "Re": 400.0,
        "fine_N": 49,
    },
)

# Ghia, Ghia and Shin (1982), Table I/II, Re=100.  The v-centerline values fix
# sign and transcription errors in the removed v1 evaluator.  These literature
# profiles are diagnostics and an independent calibration gate; full-field
# trusted references, not these sparse samples, define the benchmark score.
GHIA_RE100_U = np.asarray((
    (1.0000, 1.00000), (0.9766, 0.84123), (0.9688, 0.78871),
    (0.9609, 0.73722), (0.9531, 0.68717), (0.8516, 0.23151),
    (0.7344, 0.00332), (0.6172, -0.13641), (0.5000, -0.20581),
    (0.4531, -0.21090), (0.2813, -0.15662), (0.1719, -0.10150),
    (0.1016, -0.06434), (0.0703, -0.04775), (0.0625, -0.04192),
    (0.0547, -0.03717), (0.0000, 0.00000),
), dtype=float)

GHIA_RE100_V = np.asarray((
    (1.0000, 0.00000), (0.9688, -0.05906), (0.9609, -0.07391),
    (0.9531, -0.08864), (0.9453, -0.10313), (0.9063, -0.16914),
    (0.8594, -0.22445), (0.8047, -0.24533), (0.5000, 0.05454),
    (0.2344, 0.17527), (0.2266, 0.17507), (0.1563, 0.16077),
    (0.0938, 0.12317), (0.0781, 0.10890), (0.0703, 0.10091),
    (0.0625, 0.09233), (0.0000, 0.00000),
), dtype=float)

MAX_STREAMFUNCTION = 2.0
MAX_VORTICITY_PER_GRID_POINT = 12.0
POISSON_FEASIBILITY_TOLERANCE = 0.03
TRANSPORT_FEASIBILITY_TOLERANCE = 0.05
BOUNDARY_FEASIBILITY_TOLERANCE = 0.05


def _apply_wall_vorticity(streamfunction, vorticity):
    """Apply second-order Thom wall vorticity for a unit moving lid."""
    psi = np.asarray(streamfunction, dtype=float)
    omega = np.asarray(vorticity, dtype=float)
    n = psi.shape[0]
    h = 1.0 / (n - 1)
    omega[0, 1:-1] = -2.0 * psi[1, 1:-1] / (h * h)
    omega[-1, 1:-1] = -2.0 * psi[-2, 1:-1] / (h * h) - 2.0 / h
    omega[1:-1, 0] = -2.0 * psi[1:-1, 1] / (h * h)
    omega[1:-1, -1] = -2.0 * psi[1:-1, -2] / (h * h)
    # Corners do not enter an interior five-point stencil.  Averaging adjacent
    # wall limits gives a deterministic finite convention without pretending
    # that the discontinuous lid velocity has a unique corner vorticity.
    omega[0, 0] = 0.5 * (omega[0, 1] + omega[1, 0])
    omega[0, -1] = 0.5 * (omega[0, -2] + omega[1, -1])
    omega[-1, 0] = 0.5 * (omega[-1, 1] + omega[-2, 0])
    omega[-1, -1] = 0.5 * (omega[-1, -2] + omega[-2, -1])
    return omega


def _unpack_reference(vector, n):
    interior = (n - 2) * (n - 2)
    psi = np.zeros((n, n), dtype=float)
    omega = np.zeros((n, n), dtype=float)
    psi[1:-1, 1:-1] = np.asarray(vector[:interior]).reshape(n - 2, n - 2)
    omega[1:-1, 1:-1] = np.asarray(vector[interior:]).reshape(n - 2, n - 2)
    _apply_wall_vorticity(psi, omega)
    return psi, omega


def _reference_residual_vector(vector, reynolds, n):
    psi, omega = _unpack_reference(vector, n)
    h = 1.0 / (n - 1)
    laplacian_psi = (
        psi[2:, 1:-1] + psi[:-2, 1:-1]
        + psi[1:-1, 2:] + psi[1:-1, :-2]
        - 4.0 * psi[1:-1, 1:-1]
    )
    poisson = laplacian_psi + h * h * omega[1:-1, 1:-1]
    u = (psi[2:, 1:-1] - psi[:-2, 1:-1]) / (2.0 * h)
    v = -(psi[1:-1, 2:] - psi[1:-1, :-2]) / (2.0 * h)
    diffusion = (
        omega[2:, 1:-1] + omega[:-2, 1:-1]
        + omega[1:-1, 2:] + omega[1:-1, :-2]
        - 4.0 * omega[1:-1, 1:-1]
    )
    convection = reynolds * h * 0.5 * (
        u * (omega[1:-1, 2:] - omega[1:-1, :-2])
        + v * (omega[2:, 1:-1] - omega[:-2, 1:-1])
    )
    transport = diffusion - convection
    return np.concatenate((poisson.ravel(), transport.ravel()))


@functools.lru_cache(maxsize=None)
def _reference_solution(reynolds, n):
    """Return a deterministic Newton--Krylov continuation reference."""
    reynolds = float(reynolds)
    n = int(n)
    interior = (n - 2) * (n - 2)
    state = np.zeros(2 * interior, dtype=float)
    schedule = list(np.arange(25.0, reynolds, 25.0)) + [reynolds]
    for continuation_re in schedule:
        residual = lambda value: _reference_residual_vector(  # noqa: E731
            value, float(continuation_re), n
        )
        try:
            state = np.asarray(newton_krylov(
                residual,
                state,
                method="lgmres",
                f_tol=1.0e-8,
                maxiter=220,
                line_search="armijo",
            ), dtype=float)
        except Exception as exc:
            # SciPy exposes NoConvergence from a private module in some supported
            # versions.  Accept its final iterate only under an explicit residual
            # gate rather than importing a version-specific exception class.
            if not exc.args:
                raise
            candidate = np.asarray(exc.args[0], dtype=float)
            if candidate.shape != state.shape:
                raise
            if float(np.max(np.abs(residual(candidate)))) > 2.0e-7:
                raise
            state = candidate
    final_residual = _reference_residual_vector(state, reynolds, n)
    if float(np.max(np.abs(final_residual))) > 2.0e-7:
        raise RuntimeError("trusted cavity reference did not converge")
    psi, omega = _unpack_reference(state, n)
    return psi, omega


def _velocity(streamfunction):
    psi = np.asarray(streamfunction, dtype=float)
    n = psi.shape[0]
    h = 1.0 / (n - 1)
    u = np.zeros_like(psi)
    v = np.zeros_like(psi)
    u[1:-1, 1:-1] = (
        psi[2:, 1:-1] - psi[:-2, 1:-1]
    ) / (2.0 * h)
    v[1:-1, 1:-1] = -(
        psi[1:-1, 2:] - psi[1:-1, :-2]
    ) / (2.0 * h)
    u[-1, 1:-1] = 1.0
    # The physical lid velocity is discontinuous at the two top corners; the
    # no-slip side-wall value is used there, matching the reference convention.
    return u, v


def _validate_artifact(returned, n):
    if not isinstance(returned, (tuple, list)) or len(returned) != 2:
        raise ValueError("expected (streamfunction, vorticity)")
    psi = np.asarray(returned[0], dtype=float)
    omega = np.asarray(returned[1], dtype=float)
    if psi.shape != (n, n) or omega.shape != (n, n):
        raise ValueError("wrong cavity field shape")
    if not np.all(np.isfinite(psi)) or not np.all(np.isfinite(omega)):
        raise ValueError("non-finite cavity field")
    if float(np.max(np.abs(psi))) > MAX_STREAMFUNCTION:
        raise ValueError("streamfunction bound exceeded")
    if float(np.max(np.abs(omega))) > MAX_VORTICITY_PER_GRID_POINT * n:
        raise ValueError("vorticity bound exceeded")
    return psi, omega


def _relative_residuals(psi, omega, reynolds):
    n = psi.shape[0]
    h = 1.0 / (n - 1)
    laplacian_psi = (
        psi[2:, 1:-1] + psi[:-2, 1:-1]
        + psi[1:-1, 2:] + psi[1:-1, :-2]
        - 4.0 * psi[1:-1, 1:-1]
    )
    source = h * h * omega[1:-1, 1:-1]
    poisson = laplacian_psi + source
    poisson_scale = math.sqrt(float(np.mean(
        laplacian_psi * laplacian_psi + source * source
    ))) + 1.0e-12
    poisson_relative = math.sqrt(float(np.mean(poisson * poisson))) / poisson_scale

    u, v = _velocity(psi)
    diffusion = (
        omega[2:, 1:-1] + omega[:-2, 1:-1]
        + omega[1:-1, 2:] + omega[1:-1, :-2]
        - 4.0 * omega[1:-1, 1:-1]
    )
    convection = float(reynolds) * h * 0.5 * (
        u[1:-1, 1:-1] * (omega[1:-1, 2:] - omega[1:-1, :-2])
        + v[1:-1, 1:-1] * (omega[2:, 1:-1] - omega[:-2, 1:-1])
    )
    transport = diffusion - convection
    transport_scale = math.sqrt(float(np.mean(
        diffusion * diffusion + convection * convection
    ))) + 1.0e-12
    transport_relative = (
        math.sqrt(float(np.mean(transport * transport))) / transport_scale
    )
    return float(poisson_relative), float(transport_relative)


def _boundary_error(psi, omega):
    n = psi.shape[0]
    h = 1.0 / (n - 1)
    wall_psi = np.concatenate((psi[0], psi[-1], psi[1:-1, 0], psi[1:-1, -1]))
    streamfunction_error = float(np.max(np.abs(wall_psi))) / 0.01
    expected = np.zeros_like(omega)
    _apply_wall_vorticity(psi, expected)
    observed_walls = np.concatenate((
        omega[0, 1:-1], omega[-1, 1:-1],
        omega[1:-1, 0], omega[1:-1, -1],
    ))
    expected_walls = np.concatenate((
        expected[0, 1:-1], expected[-1, 1:-1],
        expected[1:-1, 0], expected[1:-1, -1],
    ))
    vorticity_error = math.sqrt(float(np.mean(
        (observed_walls - expected_walls) ** 2
    ))) / (2.0 / h)
    return float(max(streamfunction_error, vorticity_error))


def _field_similarity(psi, reference_psi):
    u, v = _velocity(psi)
    ref_u, ref_v = _velocity(reference_psi)
    interior = (slice(1, -1), slice(1, -1))
    velocity_scale = math.sqrt(float(np.mean(
        ref_u[interior] ** 2 + ref_v[interior] ** 2
    ))) + 1.0e-12
    velocity_error = math.sqrt(float(np.mean(
        (u[interior] - ref_u[interior]) ** 2
        + (v[interior] - ref_v[interior]) ** 2
    ))) / velocity_scale
    streamfunction_scale = math.sqrt(float(np.mean(
        reference_psi[interior] ** 2
    ))) + 1.0e-12
    streamfunction_error = math.sqrt(float(np.mean(
        (psi[interior] - reference_psi[interior]) ** 2
    ))) / streamfunction_scale
    combined_error = 0.75 * velocity_error + 0.25 * streamfunction_error
    return (
        float(np.clip(1.0 - combined_error, 0.0, 1.0)),
        float(velocity_error),
        float(streamfunction_error),
    )


def _raw_quality(psi, omega, reynolds, reference_psi):
    similarity, velocity_error, streamfunction_error = _field_similarity(
        psi, reference_psi
    )
    poisson_relative, transport_relative = _relative_residuals(
        psi, omega, reynolds
    )
    boundary_error = _boundary_error(psi, omega)
    clipped_error = (
        min(poisson_relative, 10.0)
        + min(transport_relative, 10.0)
        + min(boundary_error, 10.0)
    )
    physics_quality = math.exp(-1.5 * clipped_error)
    quality = similarity * math.sqrt(physics_quality)
    feasible = bool(
        poisson_relative <= POISSON_FEASIBILITY_TOLERANCE
        and transport_relative <= TRANSPORT_FEASIBILITY_TOLERANCE
        and boundary_error <= BOUNDARY_FEASIBILITY_TOLERANCE
    )
    return {
        "raw_quality": float(quality),
        "field_similarity": float(similarity),
        "velocity_relative_error": float(velocity_error),
        "streamfunction_relative_error": float(streamfunction_error),
        "poisson_relative_residual": float(poisson_relative),
        "transport_relative_residual": float(transport_relative),
        "boundary_relative_error": float(boundary_error),
        "physics_quality": float(physics_quality),
        "physics_feasible": feasible,
    }


def _weak_baseline_fields(n):
    psi = np.zeros((n, n), dtype=float)
    omega = np.zeros((n, n), dtype=float)
    _apply_wall_vorticity(psi, omega)
    return psi, omega


@functools.lru_cache(maxsize=None)
def _baseline_quality(reynolds, n):
    psi, omega = _weak_baseline_fields(int(n))
    reference_psi, _ = _reference_solution(float(reynolds), int(n))
    return _raw_quality(psi, omega, float(reynolds), reference_psi)["raw_quality"]


def _score_fields(psi, omega, scenario):
    reynolds, n = float(scenario["Re"]), int(scenario["N"])
    reference_psi, _ = _reference_solution(reynolds, n)
    diagnostics = _raw_quality(psi, omega, reynolds, reference_psi)
    baseline = _baseline_quality(reynolds, n)
    ungated_score = float(np.clip(
        (diagnostics["raw_quality"] - baseline) / max(1.0e-12, 1.0 - baseline),
        0.0,
        1.0,
    ))
    # Similarity to a trusted field is not itself a valid CFD result.  A near
    # reference can still have a large transport residual (for example, a
    # uniformly attenuated vortex).  Make the public utility strictly
    # conditional on all public equations and wall gates, while retaining the
    # ungated value as evaluator-only diagnostic evidence.
    score = ungated_score if diagnostics["physics_feasible"] else 0.0
    u, v = _velocity(psi)
    record = {
        "name": scenario["name"],
        "split": scenario["split"],
        "Re": reynolds,
        "N": n,
        "valid": True,
        "score": score,
        "ungated_score": ungated_score,
        **diagnostics,
    }
    return record, {"psi": psi, "omega": omega, "u": u, "v": v}


def _invalid_record(scenario):
    return {
        "name": scenario["name"],
        "split": scenario["split"],
        "Re": float(scenario["Re"]),
        "N": int(scenario["N"]),
        "valid": False,
        "reason": "invalid_candidate_artifact",
        "score": 0.0,
        "ungated_score": 0.0,
        "raw_quality": 0.0,
        "field_similarity": 0.0,
        "velocity_relative_error": 1.0,
        "streamfunction_relative_error": 1.0,
        "poisson_relative_residual": 1.0,
        "transport_relative_residual": 1.0,
        "boundary_relative_error": 1.0,
        "physics_quality": 0.0,
        "physics_feasible": False,
    }


def _resample(field, target_n=21):
    field = np.asarray(field, dtype=float)
    source = np.linspace(0.0, 1.0, field.shape[0])
    target = np.linspace(0.0, 1.0, int(target_n))
    along_x = np.asarray([
        np.interp(target, source, row) for row in field
    ])
    return np.asarray([
        np.interp(target, source, along_x[:, column])
        for column in range(int(target_n))
    ]).T


def _pair_error(coarse_fields, fine_fields):
    coarse_u = _resample(coarse_fields["u"])
    coarse_v = _resample(coarse_fields["v"])
    fine_u = _resample(fine_fields["u"])
    fine_v = _resample(fine_fields["v"])
    scale = math.sqrt(float(np.mean(fine_u ** 2 + fine_v ** 2))) + 1.0e-12
    return float(math.sqrt(float(np.mean(
        (coarse_u - fine_u) ** 2 + (coarse_v - fine_v) ** 2
    ))) / scale)


def _grid_validation(spec, coarse_record, coarse_fields, fine_record, fine_fields):
    if coarse_fields is None or fine_fields is None:
        return {
            "name": spec["name"],
            "split": spec["split"],
            "valid": False,
            "score": 0.0,
            "ungated_score": 0.0,
            "physics_feasible": False,
            "candidate_grid_difference": None,
            "reference_grid_difference": None,
            "excess_grid_difference": None,
            "coarse_physics_feasible": False,
            "fine_physics_feasible": False,
        }
    coarse_reference_psi, _ = _reference_solution(spec["Re"], coarse_record["N"])
    fine_reference_psi, _ = _reference_solution(spec["Re"], spec["fine_N"])
    reference_pair = {
        "u": _velocity(coarse_reference_psi)[0],
        "v": _velocity(coarse_reference_psi)[1],
    }
    reference_fine = {
        "u": _velocity(fine_reference_psi)[0],
        "v": _velocity(fine_reference_psi)[1],
    }
    candidate_difference = _pair_error(coarse_fields, fine_fields)
    reference_difference = _pair_error(reference_pair, reference_fine)
    excess = max(0.0, candidate_difference - reference_difference)
    consistency = math.exp(-0.5 * (excess / 0.08) ** 2)
    physics_feasible = bool(
        coarse_record["physics_feasible"] and fine_record["physics_feasible"]
    )
    ungated_score = math.sqrt(max(
        0.0, consistency * fine_record["ungated_score"]
    ))
    score = ungated_score if physics_feasible else 0.0
    return {
        "name": spec["name"],
        "split": spec["split"],
        "valid": bool(coarse_record["valid"] and fine_record["valid"]),
        "score": float(score),
        "ungated_score": float(ungated_score),
        "physics_feasible": physics_feasible,
        "candidate_grid_difference": float(candidate_difference),
        "reference_grid_difference": float(reference_difference),
        "excess_grid_difference": float(excess),
        "grid_consistency_factor": float(consistency),
        "coarse_physics_feasible": bool(coarse_record["physics_feasible"]),
        "fine_physics_feasible": bool(fine_record["physics_feasible"]),
        "fine_field_score": float(fine_record["score"]),
    }


def _ghia_diagnostic(fields):
    if fields is None:
        return {
            "u_centerline_rmse": None,
            "v_centerline_rmse": None,
            "u_centerline_max_error": None,
            "v_centerline_max_error": None,
        }
    n = fields["u"].shape[0]
    grid = np.linspace(0.0, 1.0, n)
    middle = n // 2
    u_values = np.interp(GHIA_RE100_U[:, 0], grid, fields["u"][:, middle])
    v_values = np.interp(GHIA_RE100_V[:, 0], grid, fields["v"][middle, :])
    u_error = u_values - GHIA_RE100_U[:, 1]
    v_error = v_values - GHIA_RE100_V[:, 1]
    return {
        "u_centerline_rmse": float(math.sqrt(float(np.mean(u_error ** 2)))),
        "v_centerline_rmse": float(math.sqrt(float(np.mean(v_error ** 2)))),
        "u_centerline_max_error": float(np.max(np.abs(u_error))),
        "v_centerline_max_error": float(np.max(np.abs(v_error))),
    }


def _candidate_calls(solve_cavity):
    scenarios = list(INSTANCES) + [
        {
            "name": spec["name"] + "_fine",
            "split": spec["split"],
            "Re": spec["Re"],
            "N": spec["fine_N"],
            "refinement_for": spec["coarse_name"],
        }
        for spec in GRID_REFINEMENT_SPECS
    ]
    outputs = {}
    for index, scenario in enumerate(scenarios):
        if index and hasattr(solve_cavity, "reset_session"):
            solve_cavity.reset_session()
        returned = solve_cavity(float(scenario["Re"]), int(scenario["N"]))
        outputs[scenario["name"]] = _validate_artifact(returned, int(scenario["N"]))
    return scenarios, outputs


def evaluate(solve_cavity):
    scenarios = list(INSTANCES) + [
        {
            "name": spec["name"] + "_fine",
            "split": spec["split"],
            "Re": spec["Re"],
            "N": spec["fine_N"],
            "refinement_for": spec["coarse_name"],
        }
        for spec in GRID_REFINEMENT_SPECS
    ]
    raw_outputs = {}
    call_validity = {}
    for index, scenario in enumerate(scenarios):
        try:
            if index and hasattr(solve_cavity, "reset_session"):
                solve_cavity.reset_session()
            returned = solve_cavity(float(scenario["Re"]), int(scenario["N"]))
            raw_outputs[scenario["name"]] = _validate_artifact(
                returned, int(scenario["N"])
            )
            call_validity[scenario["name"]] = True
        except Exception:
            raw_outputs[scenario["name"]] = None
            call_validity[scenario["name"]] = False

    records = {}
    private_fields = {}
    for scenario in scenarios:
        output = raw_outputs[scenario["name"]]
        if output is None:
            records[scenario["name"]] = _invalid_record(scenario)
            private_fields[scenario["name"]] = None
        else:
            record, fields = _score_fields(output[0], output[1], scenario)
            records[scenario["name"]] = record
            private_fields[scenario["name"]] = fields

    nominal_records = [records[scenario["name"]] for scenario in INSTANCES]
    development = [row for row in nominal_records if row["split"] == "development"]
    heldout = [row for row in nominal_records if row["split"] == "heldout"]
    grid_records = []
    for spec in GRID_REFINEMENT_SPECS:
        fine_name = spec["name"] + "_fine"
        grid_records.append(_grid_validation(
            spec,
            records[spec["coarse_name"]],
            private_fields[spec["coarse_name"]],
            records[fine_name],
            private_fields[fine_name],
        ))
    development_grid = [row for row in grid_records if row["split"] == "development"]
    heldout_grid = [row for row in grid_records if row["split"] == "heldout"]
    development_score = float(np.mean([row["score"] for row in development]))
    robustness_score = float(np.mean([row["score"] for row in development_grid]))
    return {
        "combined_score": development_score,
        "valid": 1.0 if all(row["valid"] for row in development) else 0.0,
        "feasibility_rate": float(np.mean([
            bool(row["valid"] and row["physics_feasible"]) for row in development
        ])),
        "raw_score": development_score,
        "development_score": development_score,
        "ungated_development_score": float(np.mean([
            row["ungated_score"] for row in development
        ])),
        "robustness_score": robustness_score,
        "ungated_robustness_score": float(np.mean([
            row["ungated_score"] for row in development_grid
        ])),
        "development_validation_gap": development_score - robustness_score,
        "heldout_policy_score": float(np.mean([row["score"] for row in heldout])),
        "ungated_heldout_policy_score": float(np.mean([
            row["ungated_score"] for row in heldout
        ])),
        "heldout_robustness_score": float(np.mean([
            row["score"] for row in heldout_grid
        ])),
        "ungated_heldout_robustness_score": float(np.mean([
            row["ungated_score"] for row in heldout_grid
        ])),
        "heldout_artifact_valid_rate": float(np.mean([
            bool(row["valid"]) for row in heldout
        ])),
        "development_physics_feasibility_rate": float(np.mean([
            bool(row["physics_feasible"]) for row in development
        ])),
        "heldout_physics_feasibility_rate": float(np.mean([
            bool(row["physics_feasible"]) for row in heldout
        ])),
        "development_grid_feasibility_rate": float(np.mean([
            bool(row["coarse_physics_feasible"] and row["fine_physics_feasible"])
            for row in development_grid
        ])),
        "heldout_grid_feasibility_rate": float(np.mean([
            bool(row["coarse_physics_feasible"] and row["fine_physics_feasible"])
            for row in heldout_grid
        ])),
        "mean_development_field_similarity": float(np.mean([
            row["field_similarity"] for row in development
        ])),
        "mean_heldout_field_similarity": float(np.mean([
            row["field_similarity"] for row in heldout
        ])),
        "mean_development_poisson_relative_residual": float(np.mean([
            row["poisson_relative_residual"] for row in development
        ])),
        "mean_heldout_poisson_relative_residual": float(np.mean([
            row["poisson_relative_residual"] for row in heldout
        ])),
        "mean_development_transport_relative_residual": float(np.mean([
            row["transport_relative_residual"] for row in development
        ])),
        "mean_heldout_transport_relative_residual": float(np.mean([
            row["transport_relative_residual"] for row in heldout
        ])),
        "ghia_re100": _ghia_diagnostic(private_fields.get("dev_re100")),
        "per_instance": nominal_records,
        "grid_refinement": grid_records,
        "candidate_call_count": len(scenarios),
        "candidate_call_valid_rate": float(np.mean(list(call_validity.values()))),
    }

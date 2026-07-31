#!/usr/bin/env python3
"""Audit frozen Fourier-modal witnesses for DiffractionGratingDesign-v2."""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import math
import platform
import sys
import tempfile
import textwrap
from datetime import datetime, timezone
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parent.parent
TASK = ROOT / "benchmarks/Physics/DiffractionGratingDesign"
sys.path.insert(0, str(ROOT))

from frontier_science.evaluate import evaluate_candidate  # noqa: E402
from frontier_science.metric_visibility import search_visible_metrics  # noqa: E402
from frontier_science.provenance import (  # noqa: E402
    finalize_report_trust,
    source_provenance,
)
from frontier_science.registry import find_task  # noqa: E402


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError("cannot load %s" % path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _evaluate_source(source: str, timeout: float = 120.0):
    spec = find_task("Optics/DiffractionGratingDesign", include_uncertified=True)
    with tempfile.TemporaryDirectory() as temporary:
        candidate = Path(temporary) / "candidate.py"
        candidate.write_text(textwrap.dedent(source), encoding="utf-8")
        return evaluate_candidate(spec, candidate, timeout_s=timeout)


def _uniform_fresnel_check(oracle, polarization: str) -> dict[str, float]:
    wavelength = 0.72
    period = 0.94
    incident_index = 1.0
    substrate_index = 1.45
    angle = 8.0
    layer_index = substrate_index
    design = np.asarray([[0.21, 1.0, 0.5]] * oracle.LAYER_COUNT)
    # Unit fill makes each layer a uniform continuation of the substrate.
    result = oracle._rcwa_efficiencies(
        design,
        wavelength,
        period,
        incident_index,
        substrate_index,
        layer_index,
        angle,
        polarization,
        fourier_order=oracle.FOURIER_ORDER,
    )
    theta_i = math.radians(angle)
    theta_t = math.asin(
        incident_index / substrate_index * math.sin(theta_i)
    )
    if polarization == "TE":
        amplitude = (
            incident_index * math.cos(theta_i)
            - substrate_index * math.cos(theta_t)
        ) / (
            incident_index * math.cos(theta_i)
            + substrate_index * math.cos(theta_t)
        )
    else:
        amplitude = (
            substrate_index * math.cos(theta_i)
            - incident_index * math.cos(theta_t)
        ) / (
            substrate_index * math.cos(theta_i)
            + incident_index * math.cos(theta_t)
        )
    expected_reflection = amplitude**2
    observed_reflection = float(np.sum(result["reflection"]))
    return {
        "expected_reflection": expected_reflection,
        "observed_reflection": observed_reflection,
        "absolute_error": abs(observed_reflection - expected_reflection),
        "energy_residual": abs(result["energy_sum"] - 1.0),
    }


def _convergence_records(oracle):
    records = []
    maximum_utility_delta = 0.0
    maximum_point_delta = 0.0
    for world in oracle.WORLDS:
        for label, design in (
            ("baseline", world["baseline_design"]),
            ("reference", world["reference_design"]),
        ):
            lower, _ = oracle._condition_efficiencies(
                design, world["problem"], fourier_order=13
            )
            higher, _ = oracle._condition_efficiencies(
                design, world["problem"], fourier_order=19
            )
            utility_delta = abs(oracle._utility(lower) - oracle._utility(higher))
            point_delta = float(np.max(np.abs(lower - higher)))
            maximum_utility_delta = max(maximum_utility_delta, utility_delta)
            maximum_point_delta = max(maximum_point_delta, point_delta)
            records.append({
                "world": world["name"],
                "artifact": label,
                "utility_order_13": oracle._utility(lower),
                "utility_order_19": oracle._utility(higher),
                "absolute_utility_delta": utility_delta,
                "maximum_condition_efficiency_delta": point_delta,
                "mean_condition_efficiency_delta": float(
                    np.mean(np.abs(lower - higher))
                ),
            })
    return records, maximum_utility_delta, maximum_point_delta


def _anchor_recalculation(oracle):
    records = []
    maximum_error = 0.0
    minimum_nominal_headroom = float("inf")
    minimum_robust_headroom = float("inf")
    for world in oracle.WORLDS:
        problem = world["problem"]
        nominal = {}
        robust = {}
        for label, design in (
            ("baseline", world["baseline_design"]),
            ("reference", world["reference_design"]),
        ):
            values, conditions = oracle._condition_efficiencies(design, problem)
            nominal[label] = oracle._utility(values)
            shifted = []
            for shift in oracle.SHIFT_SPECS:
                realized = oracle._shifted_design(design, problem, shift)
                if not oracle._realized_geometry_feasible(realized, problem):
                    shifted.append(0.0)
                    continue
                shifted_values, _ = oracle._condition_efficiencies(
                    realized,
                    problem,
                    ridge_index_scale=shift["ridge_index_scale"],
                    angle_offset_deg=shift["angle_offset_deg"],
                )
                shifted.append(oracle._utility(shifted_values))
            robust[label] = min(shifted)
            maximum_error = max(
                maximum_error,
                max(abs(row["energy_sum"] - 1.0) for row in conditions),
            )
        frozen = (
            world["baseline_utility"],
            world["reference_utility"],
            world["baseline_robust_utility"],
            world["reference_robust_utility"],
        )
        recalculated = (
            nominal["baseline"],
            nominal["reference"],
            robust["baseline"],
            robust["reference"],
        )
        anchor_error = max(abs(a - b) for a, b in zip(frozen, recalculated))
        nominal_headroom = recalculated[1] - recalculated[0]
        robust_headroom = recalculated[3] - recalculated[2]
        minimum_nominal_headroom = min(minimum_nominal_headroom, nominal_headroom)
        minimum_robust_headroom = min(minimum_robust_headroom, robust_headroom)
        records.append({
            "world": world["name"],
            "split": world["split"],
            "frozen_anchors": frozen,
            "recalculated_anchors": recalculated,
            "maximum_anchor_error": anchor_error,
            "nominal_headroom": nominal_headroom,
            "robust_headroom": robust_headroom,
        })
    return {
        "records": records,
        "maximum_anchor_error": max(row["maximum_anchor_error"] for row in records),
        "minimum_nominal_headroom": minimum_nominal_headroom,
        "minimum_robust_headroom": minimum_robust_headroom,
        "maximum_nominal_energy_residual": maximum_error,
    }


def audit():
    oracle = _load(
        TASK / "verification/evaluator.py", "diffraction_grating_calibration"
    )
    spec = find_task("Optics/DiffractionGratingDesign", include_uncertified=True)
    secure = evaluate_candidate(spec, spec.initial_program_path, timeout_s=120)
    baseline = copy.deepcopy(secure)
    # Retain the evaluator's complete physical diagnostics.  A hand-written
    # normalized score of one cannot establish target-efficiency materiality.
    reference = oracle.evaluate(oracle.reference_policy)
    visible = search_visible_metrics(secure)
    anchors = _anchor_recalculation(oracle)
    convergence, max_utility_delta, max_point_delta = _convergence_records(oracle)
    fresnel = {
        polarization: _uniform_fresnel_check(oracle, polarization)
        for polarization in oracle.POLARIZATIONS
    }
    invalid = {
        "bad_shape": _evaluate_source(
            "def design_grating(problem):\n    return [[0.1, 0.5, 0.5]]"
        ),
        "nonfinite": _evaluate_source(
            "def design_grating(problem):\n"
            "    return [[float('nan'), 0.5, 0.5]] * problem['layer_count']"
        ),
        "minimum_feature": _evaluate_source(
            "def design_grating(problem):\n"
            "    return [[problem['depth_bounds_um'][0], 0.01, 0.5]] * problem['layer_count']"
        ),
    }
    execution_passed = bool(
        oracle.RCWA_GRATING_V2
        and len(oracle.DEVELOPMENT_WORLDS) == 4
        and len(oracle.HELDOUT_WORLDS) == 2
        and len(oracle.SHIFT_SPECS) == 4
        and baseline["valid"] == 1.0
        # The frozen baseline lies on the normalization boundary.  Different
        # supported NumPy/LAPACK builds can leave an O(1e-16) positive residue,
        # so audit the scientific zero with an explicit numerical tolerance.
        and abs(float(baseline["combined_score"])) < 1.0e-12
        and abs(float(baseline["robustness_score"])) < 1.0e-12
        and abs(float(baseline["heldout_policy_score"])) < 1.0e-12
        and abs(float(baseline["heldout_robustness_score"])) < 1.0e-12
        and reference["valid"] == 1.0
        and abs(float(reference["combined_score"]) - 1.0) < 1.0e-12
        and abs(float(reference["robustness_score"]) - 1.0) < 1.0e-12
        and abs(float(reference["heldout_policy_score"]) - 1.0) < 1.0e-12
        and abs(float(reference["heldout_robustness_score"]) - 1.0) < 1.0e-12
        and reference["development_mean_target_efficiency"] > (
            baseline["development_mean_target_efficiency"] + 0.10
        )
        and reference["heldout_mean_target_efficiency"] > (
            baseline["heldout_mean_target_efficiency"] + 0.10
        )
        and reference["development_minimum_target_efficiency"] > (
            baseline["development_minimum_target_efficiency"] + 0.05
        )
        and reference["heldout_minimum_target_efficiency"] > (
            baseline["heldout_minimum_target_efficiency"] + 0.05
        )
        and secure == baseline
        and secure["candidate_instance_call_count"] == 6
        and anchors["maximum_anchor_error"] < 1.0e-12
        and anchors["minimum_nominal_headroom"] > 0.25
        and anchors["minimum_robust_headroom"] > 0.24
        and anchors["maximum_nominal_energy_residual"] < 1.0e-10
        and max_utility_delta < 0.004
        and max_point_delta < 0.025
        and all(row["absolute_error"] < 1.0e-12 for row in fresnel.values())
        and all(row["energy_residual"] < 1.0e-12 for row in fresnel.values())
        and all(result["valid"] == 0.0 for result in invalid.values())
        and set(visible) == {
            "combined_score", "valid", "feasibility_rate", "raw_score"
        }
    )
    report = {
        "schema_version": 1,
        "trust_status": "TRUSTED_TASK_CALIBRATION",
        "evidence_scope": (
            "DETERMINISTIC_LOSSLESS_ISOTROPIC_ONE_DIMENSIONAL_FOURIER_MODAL_"
            "GRATING_DESIGN_CALIBRATION_NOT_FABRICATED_DEVICE_MEASUREMENT_"
            "GLOBAL_OPTIMUM_OR_AUTONOMOUS_DISCOVERY_EVIDENCE"
        ),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_provenance": source_provenance(ROOT),
        "environment": {
            "python": sys.version,
            "numpy": np.__version__,
            "platform": platform.platform(),
        },
        "task": "Optics/DiffractionGratingDesign",
        "task_source_sha256": {
            str(path.relative_to(ROOT)): _sha256(path)
            for path in (
                TASK / "Task.md",
                TASK / "TASK_CARD.yaml",
                TASK / "solution.py",
                TASK / "verification/evaluator.py",
                TASK / "frontier_eval/metadata.yaml",
                TASK / "frontier_eval/run_eval.py",
                ROOT / "scripts/calibrate_diffraction_grating_rcwa.py",
            )
        },
        "dimensions": {
            "development_world_count": len(oracle.DEVELOPMENT_WORLDS),
            "heldout_world_count": len(oracle.HELDOUT_WORLDS),
            "sealed_shift_count": len(oracle.SHIFT_SPECS),
            "layer_count": oracle.LAYER_COUNT,
            "default_fourier_order": oracle.FOURIER_ORDER,
            "polarizations": oracle.POLARIZATIONS,
            "nominal_conditions_per_world": 18,
        },
        "frozen_anchor_recalculation": anchors,
        "fourier_order_convergence": {
            "lower_order": 13,
            "higher_order": 19,
            "records": convergence,
            "maximum_utility_delta": max_utility_delta,
            "maximum_condition_efficiency_delta": max_point_delta,
        },
        "uniform_interface_fresnel_checks": fresnel,
        "direct_weak_baseline": baseline,
        "direct_reference": reference,
        "secure_weak_baseline": secure,
        "secure_baseline_exactly_matches_direct": secure == baseline,
        "invalid_submission_checks": invalid,
        "metric_sealing": {"visible_metric_keys": sorted(visible)},
        "references": [
            {"doi": "10.1364/JOSA.71.000811", "role": "RCWA formulation"},
            {"doi": "10.1364/JOSAA.12.001077", "role": "stable implementation"},
            {"doi": "10.1364/JOSAA.13.000779", "role": "TM convergence"},
            {"doi": "10.1364/JOSAA.13.001870", "role": "Fourier factorization"},
        ],
        "independent_implementation_plan": {
            "package": "grcwa 0.1.2",
            "wheel_sha256": (
                "65dbc0151d46a22985c1fe7f1070347e67562363fcb04371e9d158e3ba6140ee"
            ),
            "license": "GPL-3.0-or-later",
            "repository": "https://github.com/weiliangjinca/grcwa",
            "not_a_runtime_dependency": True,
            "status": "cross-check script and frozen report required before admission",
        },
        "limitations": [
            "The evaluator is a deterministic lossless isotropic one-dimensional Fourier-modal model, not a fabricated or measured grating.",
            "It omits absorption, anisotropy, roughness, finite aperture, two-dimensional patterning, fabrication yield and detector response.",
            "The dense boundary solve is stable on the registered worlds but is not a scattering-matrix implementation for arbitrary thick or evanescent stacks.",
            "The calibrated five-layer references are reproducible witnesses, not global optima or device records.",
            "Finite Fourier truncation is retained as a numerical-uncertainty axis; admission requires an independently implemented grcwa cross-check.",
            "Repository-visible worlds require server-held procedural regimes and contamination auditing before leaderboard or generalization claims.",
            "Task calibration does not measure feedback causality, population performance, fabrication or autonomous scientific discovery.",
        ],
    }
    finalize_report_trust(report, execution_passed)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = audit()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    print(json.dumps({
        "execution_passed": report["execution_passed"],
        "trust_decision": report["trust_decision"],
        "maximum_convergence_utility_delta": report[
            "fourier_order_convergence"
        ]["maximum_utility_delta"],
    }, indent=2))
    print("Report: %s" % args.output.resolve())
    return 0 if report["execution_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Calibrate the active ForceFieldCalibration-v2 hypothesis laboratory."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import platform
import sys
import tempfile
import textwrap
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy.integrate import quad
from scipy.optimize import brentq


ROOT = Path(__file__).resolve().parent.parent
TASK = ROOT / "benchmarks/MolecularDynamics/ForceFieldCalibration"
sys.path.insert(0, str(ROOT))

from frontier_science.evaluate import evaluate_candidate  # noqa: E402
from frontier_science.metric_visibility import search_visible_metrics  # noqa: E402
from frontier_science.provenance import finalize_report_trust, source_provenance  # noqa: E402
from frontier_science.registry import find_task  # noqa: E402


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError("cannot load %s" % path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _independent_pair_checks(oracle):
    rng = np.random.default_rng(1301)
    coordinates = oracle._triangle_coordinates(2.75, 3.35, 4.82)
    rotation, _ = np.linalg.qr(rng.normal(size=(3, 3)))
    translation = np.asarray((3.4, -1.2, 0.8))
    records = []
    for family, parameters in (
        ("mie", np.asarray((0.105, 2.93))),
        ("morse", np.asarray((0.112, 1.72, 3.08))),
    ):
        energy, forces = oracle._pair_energy_forces(
            family, parameters, coordinates
        )
        transformed_energy, transformed_forces = oracle._pair_energy_forces(
            family, parameters, coordinates @ rotation + translation
        )
        finite_difference = np.zeros_like(forces)
        step = 1.0e-6
        for particle in range(3):
            for axis in range(3):
                plus = coordinates.copy()
                minus = coordinates.copy()
                plus[particle, axis] += step
                minus[particle, axis] -= step
                finite_difference[particle, axis] = -(
                    oracle._pair_energy_forces(family, parameters, plus)[0]
                    - oracle._pair_energy_forces(family, parameters, minus)[0]
                ) / (2.0 * step)
        record = {
            "family": family,
            "translation_rotation_energy_abs_gap_ev": abs(
                energy - transformed_energy
            ),
            "rotation_force_max_abs_gap_ev_per_a": float(np.max(np.abs(
                transformed_forces - forces @ rotation
            ))),
            "net_force_norm_ev_per_a": float(np.linalg.norm(
                np.sum(forces, axis=0)
            )),
            "finite_difference_force_max_abs_gap_ev_per_a": float(
                np.max(np.abs(forces - finite_difference))
            ),
        }
        record["passed"] = bool(
            record["translation_rotation_energy_abs_gap_ev"] < 1.0e-12
            and record["rotation_force_max_abs_gap_ev_per_a"] < 2.0e-12
            and record["net_force_norm_ev_per_a"] < 2.0e-14
            and record["finite_difference_force_max_abs_gap_ev_per_a"] < 2.0e-8
        )
        records.append(record)
    return {
        "records": records,
        "passed": all(record["passed"] for record in records),
    }


def _independent_pair_energy(family, parameters, distance):
    if family == "mie":
        epsilon, sigma = np.asarray(parameters, dtype=float)
        ratio = sigma / float(distance)
        return float(4.0 * epsilon * (ratio**12 - ratio**6))
    depth, inverse_range, equilibrium = np.asarray(parameters, dtype=float)
    exponential = np.exp(-inverse_range * (float(distance) - equilibrium))
    return float(depth * (exponential**2 - 2.0 * exponential))


def _independent_second_virial(oracle, family, parameters, temperature):
    def integrand(distance):
        energy = _independent_pair_energy(family, parameters, distance)
        exponent = np.clip(
            -energy / (oracle.BOLTZMANN_EV_PER_K * float(temperature)),
            -700.0, 50.0,
        )
        return float(np.expm1(exponent) * distance * distance)

    integral, _ = quad(
        integrand, 0.0, np.inf, epsabs=1.0e-8, epsrel=2.0e-10, limit=600
    )
    return float(
        -2.0 * np.pi * integral * oracle.ANGSTROM3_TO_CM3_PER_MOL
    )


def _virial_checks(oracle):
    records = []
    for family, parameters in (
        ("mie", np.asarray((0.105, 2.93))),
        ("morse", np.asarray((0.112, 1.72, 3.08))),
    ):
        temperature = oracle._boyle_temperature(family, parameters)
        center = oracle._second_virial_curve(
            family, parameters, (temperature,)
        )[0]
        below, above = oracle._second_virial_curve(
            family, parameters, (temperature - 40.0, temperature + 40.0)
        )
        independent_temperature = brentq(
            lambda value: _independent_second_virial(
                oracle, family, parameters, value
            ),
            oracle.BOYLE_TEMPERATURE_BOUNDS_K[0],
            oracle.BOYLE_TEMPERATURE_BOUNDS_K[1],
            xtol=1.0e-7,
            rtol=1.0e-10,
        )
        independent_center = _independent_second_virial(
            oracle, family, parameters, independent_temperature
        )
        record = {
            "family": family,
            "boyle_temperature_k": temperature,
            "root_second_virial_cm3_mol": float(center),
            "below_root_second_virial_cm3_mol": float(below),
            "above_root_second_virial_cm3_mol": float(above),
            "independent_quadrature_boyle_temperature_k": float(
                independent_temperature
            ),
            "independent_quadrature_root_second_virial_cm3_mol": float(
                independent_center
            ),
            "boyle_temperature_abs_gap_k": abs(
                temperature - independent_temperature
            ),
        }
        record["passed"] = bool(
            abs(center) < 1.0e-7
            and abs(independent_center) < 1.0e-7
            and below < 0.0
            and above > 0.0
            and record["boyle_temperature_abs_gap_k"] < 1.0
        )
        records.append(record)
    return {
        "records": records,
        "passed": all(record["passed"] for record in records),
    }


def _screening_and_reference_checks(oracle, reference):
    screening_records = []
    for split, specs in (
        ("development", oracle.DEVELOPMENT_SPECS),
        ("heldout", oracle.HELDOUT_SPECS),
    ):
        for index, spec_value in enumerate(specs):
            world = oracle._make_world(spec_value)
            problem = oracle._public_problem(world)
            screening, _ = oracle._reference_configurations()
            laboratory = oracle._Laboratory(world, problem)
            laboratory.query(
                screening,
                450.0,
                {
                    "weights": {
                        "mie": 1.0 / 3.0,
                        "morse": 1.0 / 3.0,
                        "unsupported": 1.0 / 3.0,
                    },
                    "retained": list(oracle.HYPOTHESES),
                },
            )
            posterior = laboratory.posterior()
            evaluator_record = next(
                row for row in reference["per_world"]
                if row["split"] == split and row["world_index"] == index
            )
            record = {
                "split": split,
                "world_index": index,
                "seed": int(spec_value[0]),
                "kind": world["kind"],
                "screening_posterior": posterior,
                "screening_mie_morse_absolute_gap": abs(
                    posterior["mie"] - posterior["morse"]
                ),
                "reference_selected_model": evaluator_record["selected_model"],
                "reference_joint_quality": evaluator_record["joint_quality"],
                "reference_robust_joint_quality": evaluator_record[
                    "robust_joint_quality"
                ],
                "reference_true_hypothesis_retention_rate": evaluator_record[
                    "true_hypothesis_retention_rate"
                ],
                "reference_premature_elimination": evaluator_record[
                    "premature_elimination"
                ],
                "reference_interval_coverage": evaluator_record[
                    "interval_coverage"
                ],
            }
            expected = (
                world["family"]
                if world["kind"] in oracle.PAIR_FAMILIES else "unsupported"
            )
            record["passed"] = bool(
                record["screening_mie_morse_absolute_gap"] < 0.72
                and record["reference_selected_model"] == expected
                and record["reference_true_hypothesis_retention_rate"] == 1.0
                and not record["reference_premature_elimination"]
                and (
                    record["reference_interval_coverage"] == 1.0
                    if world["kind"] in oracle.PAIR_FAMILIES else True
                )
            )
            screening_records.append(record)
    return {
        "records": screening_records,
        "early_ambiguity_passed": all(
            record["screening_mie_morse_absolute_gap"] < 0.72
            for record in screening_records
        ),
        "supported_model_discrimination_passed": bool(
            reference["development_supported_correct_model_rate"] == 1.0
            and reference["heldout_supported_correct_model_rate"] == 1.0
        ),
        "unsupported_refusal_passed": bool(
            reference["development_unsupported_refusal_rate"] == 1.0
            and reference["heldout_unsupported_refusal_rate"] == 1.0
        ),
        "interval_coverage_passed": bool(
            reference["development_interval_coverage"] == 1.0
            and reference["heldout_interval_coverage"] == 1.0
        ),
        "hypothesis_retention_passed": bool(
            reference["development_true_hypothesis_retention_rate"] == 1.0
            and reference["heldout_true_hypothesis_retention_rate"] == 1.0
            and reference["development_premature_elimination_rate"] == 0.0
            and reference["heldout_premature_elimination_rate"] == 0.0
        ),
        "passed": all(record["passed"] for record in screening_records),
    }


def _acquisition_contrast_checks(oracle):
    def acquire(world, narrow):
        problem = oracle._public_problem(world)
        laboratory = oracle._Laboratory(world, problem)
        observations = []
        screening, discriminating = oracle._reference_configurations()
        observations.append(laboratory.query(
            screening,
            450.0,
            {
                "weights": {
                    "mie": 1.0 / 3.0,
                    "morse": 1.0 / 3.0,
                    "unsupported": 1.0 / 3.0,
                },
                "retained": list(oracle.HYPOTHESES),
            },
        ))
        if narrow:
            triples = (
                (3.02, 3.02, 3.02), (3.08, 3.08, 3.08),
                (3.14, 3.14, 3.14), (3.22, 3.22, 3.22),
                (3.30, 3.30, 3.30), (3.38, 3.38, 3.38),
                (3.46, 3.46, 3.46), (3.04, 3.18, 3.42),
            )
            narrow_configurations = np.asarray([
                oracle._triangle_coordinates(*triple) for triple in triples
            ])
            batches = (
                (narrow_configurations, 450.0),
                (narrow_configurations, 450.0),
                (narrow_configurations[:7], 450.0),
            )
        else:
            batches = (
                (discriminating[:8], 180.0),
                (discriminating[8:16], 450.0),
                (discriminating[16:], 900.0),
            )
        for configurations, temperature in batches:
            weights = oracle._reference_report_weights(
                oracle._diagnostic_weights(observations, problem)
            )
            observations.append(laboratory.query(
                configurations,
                temperature,
                {"weights": weights, "retained": list(oracle.HYPOTHESES)},
            ))
        return oracle._acquisition_metrics(laboratory)

    records = []
    for spec_value in oracle.DEVELOPMENT_SPECS + oracle.HELDOUT_SPECS:
        world = oracle._make_world(spec_value)
        narrow = acquire(world, narrow=True)
        discriminating = acquire(world, narrow=False)
        record = {
            "seed": int(spec_value[0]),
            "kind": world["kind"],
            "narrow_design_coverage": narrow["design_coverage"],
            "narrow_acquisition_quality": narrow["acquisition_quality"],
            "discriminating_design_coverage": discriminating[
                "design_coverage"
            ],
            "discriminating_acquisition_quality": discriminating[
                "acquisition_quality"
            ],
            "acquisition_quality_gain": (
                discriminating["acquisition_quality"]
                - narrow["acquisition_quality"]
            ),
        }
        record["passed"] = bool(
            record["narrow_design_coverage"] < 0.40
            and record["discriminating_design_coverage"] == 1.0
            and record["acquisition_quality_gain"] > 0.35
        )
        records.append(record)
    return {
        "records": records,
        "minimum_acquisition_quality_gain": min(
            record["acquisition_quality_gain"] for record in records
        ),
        "passed": all(record["passed"] for record in records),
    }


def _candidate_source(mode):
    mutation = {
        "valid": "pass",
        "fabricated_evidence": "value['evidence_ids'] = ['fabricated']",
        "malformed_interval": (
            "value['hypothesis_weights']={'mie':1/3,'morse':1/3,"
            "'unsupported':1/3}; value['retained_hypotheses']="
            "['mie','morse','unsupported']; value['selected_model']='mie'; "
            "value['abstain']=False; "
            "value['parameters']={'epsilon_ev':0.1,'sigma_a':2.9}; "
            "value['parameter_intervals']={'epsilon_ev':[0.09,0.11],"
            "'sigma_a':[3.0,2.8]}; "
            "value['second_virial_cm3_mol_by_temperature']="
            "{str(float(t)):0.0 for t in problem['virial_temperature_grid_k']}; "
            "value['boyle_temperature_k']=4000.0; "
            "value['boyle_temperature_above_threshold']=False"
        ),
        "nonfinite": "value['confidence'] = float('nan')",
        "extra_field": "value['unexpected'] = True",
        "overspend": (
            "\n    try:\n        for _ in range(problem['query_budget_units'] + 1):"
            "\n            query(c, 450.0, state)\n    except Exception:\n        pass"
        ),
        "restore": (
            "\n    try:\n        query(c, 450.0, {'weights': {'mie':1/3,'morse':1/3,"
            "'unsupported':1/3}, 'retained':['mie','morse','unsupported']})"
            "\n    except Exception:\n        pass"
        ),
    }[mode]
    first_state = (
        "{'weights': {'mie':0.5,'morse':0.5,'unsupported':0.0}, "
        "'retained':['mie','morse']}"
        if mode == "restore" else "state"
    )
    return textwrap.dedent(
        """
        import numpy as np
        calls = 0

        def calibrate_forcefield(problem, query):
            global calls
            calls += 1
            if MODE == 'valid' and calls != 1:
                raise RuntimeError('candidate state leaked across worlds')
            side = 3.18
            c = np.asarray([[[-side/2,0,0],[side/2,0,0],
                             [0,np.sqrt(3)*side/2,0]]])
            state = {'weights': {'mie':1/3,'morse':1/3,'unsupported':1/3},
                     'retained':['mie','morse','unsupported']}
            first = query(c, 450.0, FIRST_STATE)
            value = {
                'hypothesis_weights': {'mie':0,'morse':0,'unsupported':1},
                'retained_hypotheses':['unsupported'],
                'selected_model':'unsupported','parameters':{},
                'parameter_intervals':{},
                'second_virial_cm3_mol_by_temperature':{},
                'boyle_temperature_k':None,
                'boyle_temperature_above_threshold':None,
                'confidence':0.0,'abstain':True,
                'evidence_ids':[first['observation_id']] + first['configuration_ids']}
            MUTATION
            return value
        """
    ).replace("MODE", repr(mode)).replace(
        "FIRST_STATE", first_state
    ).replace("MUTATION", mutation)


def _secure_isolation_and_failure_checks(spec):
    records = []
    modes = (
        "valid", "extra_field", "nonfinite", "fabricated_evidence",
        "malformed_interval", "overspend", "restore",
    )
    with tempfile.TemporaryDirectory(prefix="force_field_calibration_") as temporary:
        root = Path(temporary)
        for mode in modes:
            candidate = root / (mode + ".py")
            candidate.write_text(_candidate_source(mode), encoding="utf-8")
            result = evaluate_candidate(spec, candidate, timeout_s=90)
            if mode == "valid":
                passed = bool(
                    result.get("valid") == 1.0
                    and result.get("combined_score") == 0.0
                    and result.get("candidate_instance_call_count") == 12
                    and result.get("candidate_instance_valid_rate") == 1.0
                )
            else:
                passed = bool(
                    result.get("valid") == 0.0
                    and float(result.get("combined_score", 1.0)) <= 0.0
                    and result.get("infrastructure_failure") is None
                )
            records.append({
                "mode": mode,
                "combined_score": result.get("combined_score"),
                "valid": result.get("valid"),
                "candidate_instance_call_count": result.get(
                    "candidate_instance_call_count"
                ),
                "candidate_instance_valid_rate": result.get(
                    "candidate_instance_valid_rate"
                ),
                "passed": passed,
            })
    return {
        "records": records,
        "fresh_process_per_world_passed": records[0]["passed"],
        "fail_closed_passed": all(record["passed"] for record in records[1:]),
        "passed": all(record["passed"] for record in records),
    }


def calibrate():
    oracle = _load(
        TASK / "verification/evaluator.py", "force_field_calibration_oracle"
    )
    baseline = _load(
        TASK / "solution.py", "force_field_calibration_baseline"
    )
    spec = find_task(
        "MolecularDynamics/ForceFieldCalibration", include_uncertified=True
    )
    direct_baseline = oracle.evaluate(baseline.calibrate_forcefield)
    secure_baseline = evaluate_candidate(
        spec, spec.initial_program_path, timeout_s=90
    )
    reference = oracle.evaluate(oracle._reference_agent)
    direct_json = json.loads(json.dumps(direct_baseline, allow_nan=False))
    direct_json["raw_score"] = direct_json["combined_score"]
    visible = search_visible_metrics(secure_baseline)
    pair_checks = _independent_pair_checks(oracle)
    virial_checks = _virial_checks(oracle)
    screening_checks = _screening_and_reference_checks(oracle, reference)
    acquisition_checks = _acquisition_contrast_checks(oracle)
    isolation_checks = _secure_isolation_and_failure_checks(spec)
    execution_passed = bool(
        oracle.FORCE_FIELD_HYPOTHESIS_LAB_V2
        and len(oracle.DEVELOPMENT_SPECS) == 7
        and len(oracle.HELDOUT_SPECS) == 5
        and pair_checks["passed"]
        and virial_checks["passed"]
        and screening_checks["passed"]
        and screening_checks["early_ambiguity_passed"]
        and screening_checks["supported_model_discrimination_passed"]
        and screening_checks["unsupported_refusal_passed"]
        and screening_checks["interval_coverage_passed"]
        and screening_checks["hypothesis_retention_passed"]
        and acquisition_checks["passed"]
        and isolation_checks["passed"]
        and secure_baseline == direct_json
        and secure_baseline["valid"] == 1.0
        and secure_baseline["combined_score"] == 0.0
        and secure_baseline["robustness_score"] == 0.0
        and set(visible) == {
            "combined_score", "valid", "feasibility_rate", "raw_score"
        }
        and reference["combined_score"] > 0.93
        and reference["heldout_policy_score"] > 0.93
        and reference["robustness_score"] > 0.93
        and reference["heldout_robustness_score"] > 0.93
        and reference["development_supported_claim_coverage"] == 1.0
        and reference["heldout_supported_claim_coverage"] == 1.0
        and reference["development_false_discovery_rate"] == 0.0
        and reference["heldout_false_discovery_rate"] == 0.0
        and reference["candidate_instance_call_count"] == 12
        and reference["candidate_instance_valid_rate"] == 1.0
    )
    source_paths = (
        TASK / "Task.md",
        TASK / "TASK_CARD.yaml",
        TASK / "solution.py",
        TASK / "verification/evaluator.py",
        TASK / "frontier_eval/metadata.yaml",
        TASK / "frontier_eval/run_eval.py",
        Path(__file__).resolve(),
    )
    all_specs = oracle.DEVELOPMENT_SPECS + oracle.HELDOUT_SPECS
    report = {
        "schema_version": 1,
        "trust_status": "TRUSTED_TASK_CALIBRATION",
        "evidence_scope": (
            "SYNTHETIC_REDUCED_ORDER_ACTIVE_PAIR_POTENTIAL_HYPOTHESIS_"
            "CALIBRATION_NOT_MOLECULAR_DYNAMICS_MATERIAL_THERMODYNAMIC_"
            "OR_AUTONOMOUS_DISCOVERY_EVIDENCE"
        ),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_provenance": source_provenance(ROOT),
        "environment": {
            "python": sys.version,
            "numpy": np.__version__,
            "platform": platform.platform(),
        },
        "task": "MolecularDynamics/ForceFieldCalibration",
        "task_source_sha256": {
            str(path.relative_to(ROOT)): _sha256(path) for path in source_paths
        },
        "task_dimensions": {
            "development_world_count": len(oracle.DEVELOPMENT_SPECS),
            "heldout_world_count": len(oracle.HELDOUT_SPECS),
            "supported_world_count": sum(
                spec_value[1] in oracle.PAIR_FAMILIES for spec_value in all_specs
            ),
            "unsupported_world_count": sum(
                spec_value[1] in oracle.UNSUPPORTED_KINDS for spec_value in all_specs
            ),
            "supported_family_count": len(oracle.PAIR_FAMILIES),
            "unsupported_kind_count": len(oracle.UNSUPPORTED_KINDS),
            "query_budget_units": oracle.QUERY_BUDGET_UNITS,
            "maximum_query_calls": oracle.MAX_QUERY_CALLS,
            "first_query_max_configurations": (
                oracle.FIRST_QUERY_MAX_CONFIGURATIONS
            ),
        },
        "independent_pair_energy_force_checks": pair_checks,
        "independent_second_virial_boyle_checks": virial_checks,
        "screening_hypothesis_and_reference_checks": screening_checks,
        "acquisition_contrast_checks": acquisition_checks,
        "secure_isolation_and_failure_checks": isolation_checks,
        "direct_weak_baseline": direct_baseline,
        "secure_weak_baseline": secure_baseline,
        "secure_baseline_exactly_matches_direct": secure_baseline == direct_json,
        "truth_blind_reference": reference,
        "search_visible_metric_keys": sorted(visible),
        "limitations": [
            "This is a deterministic three-particle reduced-order laboratory, not molecular dynamics, electronic structure or a force field for a material.",
            "The supported library contains only isotropic Mie 12-6 and Morse pair laws; the unsupported cases are controlled synthetic alternatives.",
            "No periodic boundaries, many-particle sampling, quantum labels, finite-size effects, phase behavior or real measurement noise are represented.",
            "The virial calculation is a numerical consequence of the declared pair model rather than an independent thermodynamic measurement.",
            "Fixed public equations and repository-visible procedural worlds require server-held cohorts and contamination auditing.",
            "The truth-blind reference is a normalization witness, not a globally optimal acquisition policy or a scientific discovery.",
            "Material or discovery claims require independent ab-initio or experimental labels, many-particle validation, prospective confirmation and domain-expert review.",
        ],
        "execution_passed": execution_passed,
    }
    finalize_report_trust(report, execution_passed)
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = calibrate()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "execution_passed": report["execution_passed"],
        "trust_decision": report["trust_decision"],
        "reference_development": report["truth_blind_reference"][
            "combined_score"
        ],
        "reference_heldout": report["truth_blind_reference"][
            "heldout_policy_score"
        ],
        "reference_robustness": report["truth_blind_reference"][
            "robustness_score"
        ],
    }, indent=2))
    print("Report: %s" % args.output.resolve())
    return 0 if report["execution_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

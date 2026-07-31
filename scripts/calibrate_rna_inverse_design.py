#!/usr/bin/env python3
"""Calibrate RNAInverseDesign references, exact DP and proxy headroom."""

from __future__ import annotations

import argparse
import functools
import hashlib
import importlib.util
import json
import math
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from frontier_science.evaluate import evaluate_candidate  # noqa: E402
from frontier_science.provenance import finalize_report_trust, source_provenance  # noqa: E402
from frontier_science.registry import find_task  # noqa: E402


TASK = ROOT / "benchmarks/Biology/RNAInverseDesign"
GENERATOR = ROOT / "scripts/generate_rna_inverse_design_references.py"


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError("cannot load %s" % path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _enumerate_structures(length, min_hairpin):
    @functools.lru_cache(maxsize=None)
    def recurse(left, right):
        if left > right:
            return ((),)
        structures = list(recurse(left, right - 1))
        for partner in range(left, right - min_hairpin):
            for prefix in recurse(left, partner - 1):
                for inside in recurse(partner + 1, right - 1):
                    structures.append(tuple(sorted(
                        prefix + inside + ((partner, right),)
                    )))
        return tuple(structures)
    return recurse(0, length - 1)


def _exhaustive_check(oracle, sequence):
    problem = {
        "pair_energies": dict(oracle.PAIR_ENERGIES),
        "temperature_kelvin": oracle.TEMPERATURE_KELVIN,
        "gas_constant_kcal": oracle.GAS_CONSTANT_KCAL,
        "loop_initiation_kcal": oracle.LOOP_INITIATION_KCAL,
        "min_hairpin": oracle.MIN_HAIRPIN,
    }
    valid_structures = []
    energies = []
    weights = []
    rt = oracle.GAS_CONSTANT_KCAL * oracle.TEMPERATURE_KELVIN
    for pairs in _enumerate_structures(len(sequence), oracle.MIN_HAIRPIN):
        energy = oracle._structure_energy(
            sequence, pairs, oracle.PAIR_ENERGIES, 1.0,
            oracle.LOOP_INITIATION_KCAL,
        )
        if math.isfinite(energy):
            valid_structures.append(pairs)
            energies.append(energy)
            weights.append(math.exp(-energy / rt))
    partition = float(sum(weights))
    probabilities = np.zeros((len(sequence), len(sequence)), dtype=float)
    for pairs, weight in zip(valid_structures, weights):
        for left, right in pairs:
            probabilities[left, right] += weight / partition
            probabilities[right, left] += weight / partition
    dynamic = oracle._fold(sequence, problem)
    maximum_pair_probability_error = float(np.max(np.abs(
        dynamic["pair_probabilities"] - probabilities
    )))
    relative_partition_error = abs(dynamic["partition"] - partition) / partition
    mfe_error = abs(dynamic["mfe_energy"] - min(energies))
    traced_energy_error = abs(
        oracle._structure_energy(
            sequence, dynamic["mfe_pairs"], oracle.PAIR_ENERGIES, 1.0,
            oracle.LOOP_INITIATION_KCAL,
        ) - min(energies)
    )
    return {
        "sequence": sequence,
        "structure_count": len(valid_structures),
        "relative_partition_error": relative_partition_error,
        "maximum_pair_probability_error": maximum_pair_probability_error,
        "mfe_energy_error": mfe_error,
        "traced_mfe_energy_error": traced_energy_error,
        "passed": bool(
            relative_partition_error < 1.0e-11
            and maximum_pair_probability_error < 2.0e-12
            and mfe_error < 1.0e-12
            and traced_energy_error < 1.0e-12
        ),
    }


def calibrate():
    oracle = _load(TASK / "verification/evaluator.py", "rna_calibration_oracle")
    generator = _load(GENERATOR, "rna_reference_generator")
    spec = find_task("RNAEngineering/RNAInverseDesign", include_uncertified=True)
    secure_baseline = evaluate_candidate(
        spec, spec.initial_program_path, timeout_s=120
    )
    baseline = oracle.evaluate(
        lambda problem: {"sequence": oracle._baseline_sequence(problem)}
    )
    reference = oracle.evaluate(oracle._reference_policy)

    regenerated = generator.generate(restarts=4, iterations=400)
    regenerated_sequences = {
        row["name"]: row["sequence"] for row in regenerated["records"]
    }
    frozen_sequences = dict(oracle.REFERENCE_SEQUENCES)
    reference_reproduced = regenerated_sequences == frozen_sequences

    anchor_rows = []
    minimum_nominal_headroom = math.inf
    minimum_shift_headroom = math.inf
    for instance in oracle.INSTANCES:
        problem = oracle._problem(instance)
        baseline_sequence = oracle._baseline_sequence(problem)
        reference_sequence = frozen_sequences[instance["name"]]
        baseline_nominal = oracle._sequence_metrics(baseline_sequence, problem)
        reference_nominal = oracle._sequence_metrics(reference_sequence, problem)
        shift_rows = []
        for shift in oracle.SHIFT_SPECS:
            baseline_shift = oracle._sequence_metrics(
                baseline_sequence, problem, shift
            )
            reference_shift = oracle._sequence_metrics(
                reference_sequence, problem, shift
            )
            shift_headroom = (
                reference_shift["exact_utility"]
                - baseline_shift["exact_utility"]
            )
            minimum_shift_headroom = min(minimum_shift_headroom, shift_headroom)
            shift_rows.append({
                "name": shift["name"],
                "baseline_exact_utility": baseline_shift["exact_utility"],
                "reference_exact_utility": reference_shift["exact_utility"],
                "headroom": shift_headroom,
            })
        nominal_headroom = (
            reference_nominal["exact_utility"]
            - baseline_nominal["exact_utility"]
        )
        minimum_nominal_headroom = min(minimum_nominal_headroom, nominal_headroom)
        anchor_rows.append({
            "name": instance["name"],
            "family": instance["family"],
            "length": instance["length"],
            "baseline_sequence": baseline_sequence,
            "reference_sequence": reference_sequence,
            "baseline": baseline_nominal,
            "reference": reference_nominal,
            "nominal_headroom": nominal_headroom,
            "shifts": shift_rows,
        })

    exhaustive_checks = [
        _exhaustive_check(oracle, sequence)
        for sequence in ("GCAAAAGC", "GCGAAACGC", "AUGCAUGCA", "GCGCAACGCG")
    ]
    proxy_counterexample = next(
        row for row in baseline["per_instance"]
        if row["proxy_compatibility"] == 1.0
        and row["normalized_exact_quality"] == 0.0
    )
    execution_passed = bool(
        oracle.RNA_INVERSE_DESIGN_V1
        and len(oracle.DEVELOPMENT_INSTANCES) == 5
        and len(oracle.HELDOUT_INSTANCES) == 3
        and len(oracle.SHIFT_SPECS) == 4
        and secure_baseline["valid"] == 1.0
        and secure_baseline["combined_score"] == 0.0
        and secure_baseline["candidate_problem_call_count"] == 8
        and baseline["valid"] == 1.0
        and baseline["combined_score"] == 0.0
        and baseline["heldout_policy_score"] == 0.0
        and reference["valid"] == 1.0
        and reference["combined_score"] == 1.0
        and reference["heldout_policy_score"] == 1.0
        and reference["robustness_score"] == 1.0
        and reference["heldout_robustness_score"] == 1.0
        and reference_reproduced
        and minimum_nominal_headroom > 0.10
        and minimum_shift_headroom > 0.10
        and all(row["passed"] for row in exhaustive_checks)
        and proxy_counterexample["target_probability"] < 1.0e-7
    )
    report = {
        "schema_version": 1,
        "trust_status": "TRUSTED_TASK_CALIBRATION",
        "evidence_scope": (
            "SIMPLIFIED_RNA_ENSEMBLE_TASK_CALIBRATION_NOT_FULL_TURNER_"
            "EXPERIMENTAL_FUNCTION_OR_AUTONOMOUS_DISCOVERY_EVIDENCE"
        ),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_provenance": source_provenance(ROOT),
        "environment": {"python": sys.version, "platform": platform.platform()},
        "source_hashes": {
            "evaluator_sha256": _sha256(TASK / "verification/evaluator.py"),
            "reference_generator_sha256": _sha256(GENERATOR),
        },
        "config": {
            "development_instances": len(oracle.DEVELOPMENT_INSTANCES),
            "heldout_instances": len(oracle.HELDOUT_INSTANCES),
            "shift_count": len(oracle.SHIFT_SPECS),
            "reference_restarts": 4,
            "reference_iterations": 400,
        },
        "secure_baseline": secure_baseline,
        "direct_baseline": baseline,
        "reference": reference,
        "reference_regeneration": {
            "algorithm": regenerated["algorithm"],
            "config": regenerated["config"],
            "frozen_sequences": frozen_sequences,
            "regenerated_sequences": regenerated_sequences,
            "exact_match": reference_reproduced,
        },
        "anchors": anchor_rows,
        "minimum_nominal_headroom": minimum_nominal_headroom,
        "minimum_shift_headroom": minimum_shift_headroom,
        "exhaustive_dynamic_program_checks": exhaustive_checks,
        "proxy_perfect_exact_failure": proxy_counterexample,
        "limitations": [
            "The public pair, stack and loop-initiation model is a transparent controlled abstraction, not the complete Turner nearest-neighbor model.",
            "The task omits pseudoknots, tertiary structure, folding kinetics, chemical modifications, degradation and cellular context.",
            "Reference sequences are deterministic local-search witnesses, not global optima or experimentally functional RNAs.",
            "Public target generators and fixed witnesses require server-held replacement before release-level generalization claims.",
            "Full ViennaRNA or NUPACK replication, synthesis and structural or functional assays remain required for biological claims.",
        ],
    }
    finalize_report_trust(report, execution_passed)
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = calibrate()
    text = json.dumps(report, indent=2, allow_nan=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0 if report["execution_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

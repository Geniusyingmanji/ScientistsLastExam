"""Trusted evaluator for constrained RNA secondary-structure inverse design.

The oracle deliberately implements a transparent pair-and-adjacent-stack ensemble.  It is
not a claim to reproduce the complete Turner nearest-neighbor model.  The interval dynamic
program is exact for the declared pseudoknot-free model, including its partition function,
base-pair marginals and minimum-energy structure.
"""

from __future__ import annotations

import functools
import math
from collections.abc import Mapping

import numpy as np


RNA_INVERSE_DESIGN_V1 = True
ALPHABET = "ACGU"
PAIR_ENERGIES = {
    "AU": -2.0,
    "UA": -2.0,
    "CG": -3.0,
    "GC": -3.0,
    "GU": -1.0,
    "UG": -1.0,
}
GAS_CONSTANT_KCAL = 0.00198720425864083
TEMPERATURE_KELVIN = 310.15
MIN_HAIRPIN = 3
LOOP_INITIATION_KCAL = 1.2
FORBIDDEN_MOTIFS = ("AAAA", "CCCC", "GGGG", "UUUU")


def _parse_structure(structure):
    if not isinstance(structure, str):
        raise TypeError("structure must be text")
    stack = []
    pairs = []
    for index, symbol in enumerate(structure):
        if symbol == "(":
            stack.append(index)
        elif symbol == ")":
            if not stack:
                raise ValueError("unbalanced structure")
            pairs.append((stack.pop(), index))
        elif symbol != ".":
            raise ValueError("unsupported structure symbol")
    if stack:
        raise ValueError("unbalanced structure")
    return tuple(sorted(pairs))


def _dot_bracket(length, pairs):
    structure = ["."] * int(length)
    for left, right in pairs:
        if not (0 <= left < right < length):
            raise ValueError("invalid target pair")
        if structure[left] != "." or structure[right] != ".":
            raise ValueError("target base used twice")
        structure[left], structure[right] = "(", ")"
    rendered = "".join(structure)
    _parse_structure(rendered)
    return rendered


def _instance(name, family, length, pairs, fixed_bases=(), gc_fraction=(0.38, 0.62)):
    target = _dot_bracket(length, pairs)
    return {
        "name": str(name),
        "family": str(family),
        "target_structure": target,
        "length": int(length),
        "fixed_bases": tuple((int(i), str(base)) for i, base in fixed_bases),
        "gc_fraction": tuple(float(value) for value in gc_fraction),
        "forbidden_motifs": FORBIDDEN_MOTIFS,
        "min_hairpin": MIN_HAIRPIN,
        "temperature_kelvin": TEMPERATURE_KELVIN,
        "gas_constant_kcal": GAS_CONSTANT_KCAL,
        "loop_initiation_kcal": LOOP_INITIATION_KCAL,
        "pair_energies": dict(PAIR_ENERGIES),
    }


DEVELOPMENT_INSTANCES = (
    _instance(
        "hairpin_24", "hairpin", 24,
        ((0, 23), (1, 22), (2, 21), (3, 20), (4, 19), (5, 18)),
        ((8, "A"), (11, "U")), (0.42, 0.62),
    ),
    _instance(
        "single_bulge_28", "bulge", 28,
        ((0, 27), (1, 26), (2, 25), (4, 24), (5, 23), (6, 22), (7, 21)),
        ((3, "U"), (12, "A")), (0.40, 0.61),
    ),
    _instance(
        "internal_loop_30", "internal_loop", 30,
        ((0, 29), (1, 28), (2, 27), (5, 24), (6, 23), (7, 22), (8, 21)),
        ((4, "A"), (17, "C")), (0.40, 0.60),
    ),
    _instance(
        "tandem_hairpins_32", "tandem", 32,
        ((0, 13), (1, 12), (2, 11), (3, 10),
         (16, 31), (17, 30), (18, 29), (19, 28), (20, 27)),
        ((14, "G"), (15, "U")), (0.41, 0.63),
    ),
    _instance(
        "two_branch_36", "multibranch", 36,
        ((0, 35), (1, 34), (4, 15), (5, 14), (6, 13),
         (19, 31), (20, 30), (21, 29), (22, 28)),
        ((2, "G"), (17, "C")), (0.42, 0.64),
    ),
)

HELDOUT_INSTANCES = (
    _instance(
        "asymmetric_internal_34", "asymmetric_internal", 34,
        ((0, 33), (1, 32), (2, 31), (3, 30),
         (7, 27), (8, 26), (9, 25), (10, 24), (11, 23)),
        ((5, "C"), (29, "A")), (0.41, 0.62),
    ),
    _instance(
        "three_branch_40", "three_branch", 40,
        ((0, 39), (1, 38),
         (4, 13), (5, 12), (6, 11),
         (16, 25), (17, 24), (18, 23),
         (28, 36), (29, 35), (30, 34)),
        ((2, "G"), (26, "G")), (0.40, 0.63),
    ),
    _instance(
        "long_tandem_42", "long_tandem", 42,
        ((0, 17), (1, 16), (2, 15), (3, 14), (4, 13),
         (21, 41), (22, 40), (23, 39), (24, 38), (25, 37), (26, 36)),
        ((18, "G"), (19, "U"), (20, "A")), (0.42, 0.64),
    ),
)

INSTANCES = DEVELOPMENT_INSTANCES + HELDOUT_INSTANCES

SHIFT_SPECS = (
    {"name": "hot", "temperature_delta": 15.0, "stack_scale": 1.0,
     "pair_updates": {}},
    {"name": "cold", "temperature_delta": -12.0, "stack_scale": 1.0,
     "pair_updates": {}},
    {"name": "weak_stack", "temperature_delta": 0.0, "stack_scale": 0.65,
     "pair_updates": {}},
    {"name": "wobble_loss", "temperature_delta": 5.0, "stack_scale": 0.85,
     "pair_updates": {"GU": -0.25, "UG": -0.25}},
)


# Filled by the public-model local-search calibration.  These literals are evaluator anchors,
# not biological sequences or claims of global optimality.
REFERENCE_SEQUENCES = {
    "hairpin_24": "CGGCUUCCACAUCAACACAAGCCG",
    "single_bulge_28": "GCGUAAGCAACAACACAACCAGCUUCGC",
    "internal_loop_30": "CGCAAGCCGAAACACAACAAACGGCAAGCG",
    "tandem_hairpins_32": "GGCCAAAUAAGGCCGUCGGGCAUAAACGCCCG",
    "two_branch_36": "CGGACCGAAAGAACGGACAGGCCAAAUAGGCCAACG",
    "asymmetric_internal_34": "GCGGCCCGUAAUCUCCCUCCCUCAUUACAACCGC",
    "three_branch_40": "GCGACCGAAAGCGGAAGGCAAAUGCCGACGUAAGACGAGC",
    "long_tandem_42": "CGGCCAAUAAACCGGCCGGUACCAGCGCAAAUAAACCGCUGG",
}


def _stack_energy(outer_type, inner_type, scale=1.0):
    if outer_type in {"CG", "GC"} and inner_type in {"CG", "GC"}:
        value = -0.75
    elif outer_type in {"GU", "UG"} or inner_type in {"GU", "UG"}:
        value = -0.25
    else:
        value = -0.45
    return float(scale) * value


def _model(problem, shift=None):
    pair_energies = {
        str(key): float(value) for key, value in problem["pair_energies"].items()
    }
    temperature = float(problem["temperature_kelvin"])
    stack_scale = 1.0
    if shift is not None:
        temperature += float(shift.get("temperature_delta", 0.0))
        stack_scale = float(shift.get("stack_scale", 1.0))
        pair_energies.update({
            str(key): float(value)
            for key, value in shift.get("pair_updates", {}).items()
        })
    if temperature <= 0.0 or not math.isfinite(temperature):
        raise ValueError("invalid temperature")
    loop_initiation = float(problem["loop_initiation_kcal"])
    if not math.isfinite(loop_initiation) or loop_initiation < 0.0:
        raise ValueError("invalid loop initiation energy")
    return (
        pair_energies, temperature, float(problem["gas_constant_kcal"]),
        stack_scale, loop_initiation,
    )


def _interval_value(array, left, right, empty_value):
    return float(empty_value) if left > right else float(array[left, right])


def _fold(sequence, problem, shift=None):
    """Return exact partition, pair marginals and MFE pairs for the public model."""
    sequence = str(sequence)
    n = len(sequence)
    min_hairpin = int(problem["min_hairpin"])
    pair_energies, temperature, gas_constant, stack_scale, loop_initiation = (
        _model(problem, shift)
    )
    rt = gas_constant * temperature
    loop_weight = math.exp(-loop_initiation / rt)

    allowed = np.zeros((n, n), dtype=bool)
    pair_weight = np.zeros((n, n), dtype=float)
    pair_energy = np.full((n, n), np.inf, dtype=float)
    stack_weight = np.ones((n, n), dtype=float)
    stack_bonus = np.zeros((n, n), dtype=float)
    for left in range(n):
        for right in range(left + min_hairpin + 1, n):
            pair_type = sequence[left] + sequence[right]
            if pair_type not in pair_energies:
                continue
            allowed[left, right] = True
            pair_energy[left, right] = pair_energies[pair_type]
            pair_weight[left, right] = math.exp(-pair_energies[pair_type] / rt)
            if left + 1 < right - 1:
                inner_type = sequence[left + 1] + sequence[right - 1]
                if inner_type in pair_energies:
                    bonus = _stack_energy(pair_type, inner_type, stack_scale)
                    stack_bonus[left, right] = bonus
                    stack_weight[left, right] = math.exp(-bonus / rt)

    partition = np.zeros((n, n), dtype=float)
    paired_partition = np.zeros((n, n), dtype=float)
    mfe = np.zeros((n, n), dtype=float)
    paired_mfe = np.full((n, n), np.inf, dtype=float)
    mfe_choice = {}
    pair_choice = {}

    for span in range(1, n + 1):
        for left in range(0, n - span + 1):
            right = left + span - 1
            if allowed[left, right]:
                inner_z = _interval_value(partition, left + 1, right - 1, 1.0)
                inner_b = (
                    paired_partition[left + 1, right - 1]
                    if left + 1 < right - 1 else 0.0
                )
                paired_partition[left, right] = pair_weight[left, right] * (
                    loop_weight * inner_z
                    + (stack_weight[left, right] - loop_weight) * inner_b
                )

                inner_e = _interval_value(mfe, left + 1, right - 1, 0.0)
                stacked_e = math.inf
                if left + 1 < right - 1 and allowed[left + 1, right - 1]:
                    stacked_e = (
                        paired_mfe[left + 1, right - 1]
                        + stack_bonus[left, right]
                    )
                loop_e = loop_initiation + inner_e
                if stacked_e <= loop_e:
                    paired_mfe[left, right] = pair_energy[left, right] + stacked_e
                    pair_choice[left, right] = "stack"
                else:
                    paired_mfe[left, right] = pair_energy[left, right] + loop_e
                    pair_choice[left, right] = "inside"

            unpaired_z = _interval_value(partition, left, right - 1, 1.0)
            total_z = unpaired_z
            best_e = _interval_value(mfe, left, right - 1, 0.0)
            best_choice = ("unpaired",)
            for partner in range(left, right - min_hairpin):
                if not allowed[partner, right]:
                    continue
                left_z = _interval_value(partition, left, partner - 1, 1.0)
                total_z += left_z * paired_partition[partner, right]
                candidate_e = (
                    _interval_value(mfe, left, partner - 1, 0.0)
                    + paired_mfe[partner, right]
                )
                if candidate_e < best_e - 1.0e-12:
                    best_e = candidate_e
                    best_choice = ("paired", partner)
            partition[left, right] = total_z
            mfe[left, right] = best_e
            mfe_choice[left, right] = best_choice

    adj_partition = np.zeros_like(partition)
    adj_paired = np.zeros_like(paired_partition)
    adj_partition[0, n - 1] = 1.0
    for span in range(n, 0, -1):
        # Z intervals must be reversed before B intervals of the same span because
        # Z[i,j] can directly use B[i,j].
        for left in range(0, n - span + 1):
            right = left + span - 1
            adj = adj_partition[left, right]
            if adj == 0.0:
                continue
            if left <= right - 1:
                adj_partition[left, right - 1] += adj
            for partner in range(left, right - min_hairpin):
                if not allowed[partner, right]:
                    continue
                left_z = _interval_value(partition, left, partner - 1, 1.0)
                adj_paired[partner, right] += adj * left_z
                if left <= partner - 1:
                    adj_partition[left, partner - 1] += (
                        adj * paired_partition[partner, right]
                    )
        for left in range(0, n - span + 1):
            right = left + span - 1
            if not allowed[left, right]:
                continue
            adj = adj_paired[left, right]
            if adj == 0.0:
                continue
            weight = pair_weight[left, right]
            if left + 1 <= right - 1:
                adj_partition[left + 1, right - 1] += adj * weight * loop_weight
            if left + 1 < right - 1 and allowed[left + 1, right - 1]:
                adj_paired[left + 1, right - 1] += (
                    adj * weight * (stack_weight[left, right] - loop_weight)
                )

    total_partition = float(partition[0, n - 1])
    pair_probabilities = np.zeros((n, n), dtype=float)
    for left in range(n):
        for right in range(left + min_hairpin + 1, n):
            if allowed[left, right]:
                probability = (
                    adj_paired[left, right] * paired_partition[left, right]
                    / total_partition
                )
                pair_probabilities[left, right] = float(np.clip(probability, 0.0, 1.0))
                pair_probabilities[right, left] = pair_probabilities[left, right]

    mfe_pairs = set()

    def trace_interval(left, right):
        if left >= right:
            return
        choice = mfe_choice[left, right]
        if choice[0] == "unpaired":
            trace_interval(left, right - 1)
            return
        partner = int(choice[1])
        trace_interval(left, partner - 1)
        trace_pair(partner, right)

    def trace_pair(left, right):
        mfe_pairs.add((left, right))
        if left + 1 > right - 1:
            return
        if pair_choice.get((left, right)) == "stack":
            trace_pair(left + 1, right - 1)
        else:
            trace_interval(left + 1, right - 1)

    trace_interval(0, n - 1)
    return {
        "partition": total_partition,
        "pair_probabilities": pair_probabilities,
        "mfe_energy": float(mfe[0, n - 1]),
        "mfe_pairs": tuple(sorted(mfe_pairs)),
    }


def _pair_f1(observed, expected):
    observed, expected = set(observed), set(expected)
    if not observed and not expected:
        return 1.0
    if not observed or not expected:
        return 0.0
    true_positive = len(observed & expected)
    precision = true_positive / len(observed)
    recall = true_positive / len(expected)
    return 0.0 if precision + recall == 0.0 else 2.0 * precision * recall / (precision + recall)


def _structure_energy(
    sequence, pairs, pair_energies, stack_scale,
    loop_initiation=LOOP_INITIATION_KCAL,
):
    pair_set = set(pairs)
    energy = 0.0
    for left, right in pairs:
        pair_type = sequence[left] + sequence[right]
        if pair_type not in pair_energies:
            return math.inf
        energy += float(pair_energies[pair_type])
        if (left + 1, right - 1) in pair_set:
            inner_type = sequence[left + 1] + sequence[right - 1]
            energy += _stack_energy(pair_type, inner_type, stack_scale)
        else:
            energy += float(loop_initiation)
    return energy


def _sequence_metrics(sequence, problem, shift=None):
    target_pairs = _parse_structure(problem["target_structure"])
    pair_energies, temperature, gas_constant, stack_scale, loop_initiation = (
        _model(problem, shift)
    )
    fold = _fold(sequence, problem, shift)
    target_energy = _structure_energy(
        sequence, target_pairs, pair_energies, stack_scale, loop_initiation
    )
    if math.isfinite(target_energy):
        target_weight = math.exp(-target_energy / (gas_constant * temperature))
        target_probability = float(np.clip(
            target_weight / fold["partition"], 0.0, 1.0
        ))
    else:
        target_probability = 0.0

    probabilities = fold["pair_probabilities"]
    target_partner = np.full(len(sequence), -1, dtype=int)
    for left, right in target_pairs:
        target_partner[left] = right
        target_partner[right] = left
    correctness = []
    for index, partner in enumerate(target_partner):
        if partner >= 0:
            correctness.append(float(probabilities[index, partner]))
        else:
            correctness.append(float(np.clip(
                1.0 - np.sum(probabilities[index]), 0.0, 1.0
            )))
    ensemble_correctness = float(np.mean(correctness))
    mfe_f1 = float(_pair_f1(fold["mfe_pairs"], target_pairs))
    compatible = sum(
        sequence[left] + sequence[right] in pair_energies
        for left, right in target_pairs
    ) / len(target_pairs)
    exact_utility = float((
        max(target_probability, 0.0)
        * max(ensemble_correctness, 0.0)
        * max(mfe_f1, 0.0)
    ) ** (1.0 / 3.0))
    return {
        "exact_utility": exact_utility,
        "target_probability": target_probability,
        "ensemble_correctness": ensemble_correctness,
        "ensemble_defect": 1.0 - ensemble_correctness,
        "mfe_f1": mfe_f1,
        "proxy_compatibility": float(compatible),
        "mfe_energy": float(fold["mfe_energy"]),
    }


def _coerce_sequence(submission):
    if isinstance(submission, Mapping):
        if "sequence" not in submission:
            raise ValueError("missing sequence")
        submission = submission["sequence"]
    if not isinstance(submission, str):
        raise TypeError("sequence must be text")
    return submission.upper()


def _validate_sequence(sequence, problem):
    if len(sequence) != int(problem["length"]):
        raise ValueError("wrong sequence length")
    if any(base not in ALPHABET for base in sequence):
        raise ValueError("invalid RNA alphabet")
    for index, expected in problem["fixed_bases"]:
        if sequence[int(index)] != str(expected):
            raise ValueError("fixed base violation")
    gc_fraction = (sequence.count("G") + sequence.count("C")) / len(sequence)
    lower, upper = problem["gc_fraction"]
    if not float(lower) <= gc_fraction <= float(upper):
        raise ValueError("GC fraction violation")
    if any(str(motif) in sequence for motif in problem["forbidden_motifs"]):
        raise ValueError("forbidden motif")
    return float(gc_fraction)


def _problem(instance):
    return {
        "target_structure": instance["target_structure"],
        "length": instance["length"],
        "fixed_bases": tuple(instance["fixed_bases"]),
        "gc_fraction": tuple(instance["gc_fraction"]),
        "forbidden_motifs": tuple(instance["forbidden_motifs"]),
        "min_hairpin": instance["min_hairpin"],
        "temperature_kelvin": instance["temperature_kelvin"],
        "gas_constant_kcal": instance["gas_constant_kcal"],
        "loop_initiation_kcal": instance["loop_initiation_kcal"],
        "pair_energies": dict(instance["pair_energies"]),
    }


def _baseline_sequence(problem):
    sequence = list(("ACGU" * ((problem["length"] + 3) // 4))[:problem["length"]])
    for index, base in problem["fixed_bases"]:
        sequence[int(index)] = str(base)
    return "".join(sequence)


@functools.lru_cache(maxsize=1)
def _anchors():
    anchors = {}
    for instance in INSTANCES:
        problem = _problem(instance)
        baseline = _baseline_sequence(problem)
        reference = REFERENCE_SEQUENCES[instance["name"]]
        _validate_sequence(baseline, problem)
        _validate_sequence(reference, problem)
        baseline_metrics = _sequence_metrics(baseline, problem)
        reference_metrics = _sequence_metrics(reference, problem)
        shift_rows = []
        for shift in SHIFT_SPECS:
            shift_rows.append((
                _sequence_metrics(baseline, problem, shift),
                _sequence_metrics(reference, problem, shift),
            ))
        anchors[instance["name"]] = {
            "baseline": baseline_metrics,
            "reference": reference_metrics,
            "shifts": tuple(shift_rows),
        }
    return anchors


def _normalize(value, baseline, reference):
    denominator = float(reference) - float(baseline)
    if denominator <= 1.0e-10:
        raise ValueError("invalid normalization headroom")
    return float(np.clip((float(value) - float(baseline)) / denominator, 0.0, 1.0))


def _invalid_record(split, index, instance, failure_kind):
    return {
        "split": str(split),
        "instance_index": int(index),
        "name": instance["name"],
        "family": instance["family"],
        "valid": False,
        "failure_kind": str(failure_kind),
        "normalized_exact_quality": 0.0,
        "robustness_quality": 0.0,
        "exact_utility": 0.0,
        "target_probability": 0.0,
        "ensemble_correctness": 0.0,
        "ensemble_defect": 1.0,
        "mfe_f1": 0.0,
        "proxy_compatibility": 0.0,
        "proxy_false_promotion": False,
        "gc_fraction": 0.0,
    }


def _evaluate_instance(design_rna, split, index, instance):
    problem = _problem(instance)
    stage = "candidate_execution"
    try:
        sequence = _coerce_sequence(design_rna(problem))
        stage = "submission_validation"
        gc_fraction = _validate_sequence(sequence, problem)
        stage = "trusted_scoring"
        nominal = _sequence_metrics(sequence, problem)
        anchor = _anchors()[instance["name"]]
        normalized = _normalize(
            nominal["exact_utility"],
            anchor["baseline"]["exact_utility"],
            anchor["reference"]["exact_utility"],
        )
        shifted = []
        for shift, (baseline_shift, reference_shift) in zip(
            SHIFT_SPECS, anchor["shifts"]
        ):
            metrics = _sequence_metrics(sequence, problem, shift)
            shifted.append(_normalize(
                metrics["exact_utility"],
                baseline_shift["exact_utility"],
                reference_shift["exact_utility"],
            ))
        robustness = float(min(shifted))
        return {
            "split": str(split),
            "instance_index": int(index),
            "name": instance["name"],
            "family": instance["family"],
            "valid": True,
            "failure_kind": None,
            "normalized_exact_quality": round(normalized, 9),
            "robustness_quality": round(robustness, 9),
            "exact_utility": round(nominal["exact_utility"], 9),
            "target_probability": round(nominal["target_probability"], 9),
            "ensemble_correctness": round(nominal["ensemble_correctness"], 9),
            "ensemble_defect": round(nominal["ensemble_defect"], 9),
            "mfe_f1": round(nominal["mfe_f1"], 9),
            "proxy_compatibility": round(nominal["proxy_compatibility"], 9),
            "proxy_false_promotion": bool(
                nominal["proxy_compatibility"] >= 0.999999 and normalized < 0.5
            ),
            "gc_fraction": round(gc_fraction, 9),
            "shift_scores": [round(value, 9) for value in shifted],
        }
    except Exception:
        if stage == "submission_validation":
            failure_kind = "invalid_sequence"
        elif stage == "trusted_scoring":
            failure_kind = "trusted_scoring_failure"
        else:
            failure_kind = "candidate_execution_failure"
        return _invalid_record(split, index, instance, failure_kind)


def _split_metrics(records):
    valid = [row for row in records if row["valid"]]
    return {
        "valid_rate": len(valid) / len(records),
        "exact": float(np.mean([row["normalized_exact_quality"] for row in records])),
        "robustness": float(np.mean([row["robustness_quality"] for row in records])),
        "target_probability": float(np.mean([row["target_probability"] for row in records])),
        "ensemble_correctness": float(np.mean([row["ensemble_correctness"] for row in records])),
        "mfe_f1": float(np.mean([row["mfe_f1"] for row in records])),
        "proxy": float(np.mean([row["proxy_compatibility"] for row in records])),
        "false_promotion_rate": float(np.mean([row["proxy_false_promotion"] for row in records])),
    }


def evaluate(design_rna):
    development = []
    heldout = []
    rows = [
        ("development", index, instance)
        for index, instance in enumerate(DEVELOPMENT_INSTANCES)
    ] + [
        ("heldout", index, instance)
        for index, instance in enumerate(HELDOUT_INSTANCES)
    ]
    for call_index, (split, index, instance) in enumerate(rows):
        if call_index and hasattr(design_rna, "reset_session"):
            design_rna.reset_session()
        record = _evaluate_instance(design_rna, split, index, instance)
        (development if split == "development" else heldout).append(record)

    dev = _split_metrics(development)
    held = _split_metrics(heldout)
    development_valid = all(row["valid"] for row in development)
    heldout_valid = all(row["valid"] for row in heldout)
    result = {
        "combined_score": dev["exact"] if development_valid else 0.0,
        "valid": 1.0 if development_valid else 0.0,
        "feasibility_rate": dev["valid_rate"],
        "raw_score": dev["exact"] if development_valid else 0.0,
        "development_exact_utility": dev["exact"],
        "development_target_probability": dev["target_probability"],
        "development_ensemble_correctness": dev["ensemble_correctness"],
        "development_mfe_f1": dev["mfe_f1"],
        "development_proxy_compatibility": dev["proxy"],
        "development_proxy_false_promotion_rate": dev["false_promotion_rate"],
        "robustness_score": dev["robustness"] if development_valid else 0.0,
        "heldout_policy_score": held["exact"] if heldout_valid else 0.0,
        "heldout_robustness_score": held["robustness"] if heldout_valid else 0.0,
        "heldout_target_probability": held["target_probability"],
        "heldout_ensemble_correctness": held["ensemble_correctness"],
        "heldout_mfe_f1": held["mfe_f1"],
        "heldout_proxy_compatibility": held["proxy"],
        "heldout_proxy_false_promotion_rate": held["false_promotion_rate"],
        "heldout_feasibility_rate": held["valid_rate"],
        "candidate_problem_call_count": len(rows),
        "candidate_problem_valid_rate": float(np.mean([
            row["valid"] for row in development + heldout
        ])),
        "per_instance": development + heldout,
    }
    if not development_valid:
        failures = sorted({
            row["failure_kind"] for row in development if not row["valid"]
        })
        result["error_message"] = "candidate invalid: " + ", ".join(failures)
    return result


def _reference_policy(problem):
    """Invariant-test helper matching a problem to its frozen public-model witness."""
    target = problem["target_structure"]
    matches = [
        instance for instance in INSTANCES
        if instance["target_structure"] == target
        and instance["length"] == problem["length"]
    ]
    if len(matches) != 1:
        raise ValueError("reference problem is not unique")
    return {"sequence": REFERENCE_SEQUENCES[matches[0]["name"]]}

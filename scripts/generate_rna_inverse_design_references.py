#!/usr/bin/env python3
"""Generate deterministic RNAInverseDesign public-model reference witnesses.

The search reads only the public problem dictionary and its declared pair-and-stack ensemble.
It first creates target-compatible feasible sequences, then performs seeded simulated annealing
and deterministic coordinate improvement.  Hidden split/family labels and evaluator metrics are
not used by the search objective.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import random
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
ORACLE_PATH = (
    ROOT / "benchmarks/Biology/RNAInverseDesign/verification/evaluator.py"
)
PAIR_TYPES = (("G", "C"), ("C", "G"), ("A", "U"), ("U", "A"),
              ("G", "U"), ("U", "G"))


def _load_oracle():
    spec = importlib.util.spec_from_file_location("rna_reference_oracle", ORACLE_PATH)
    if spec is None or spec.loader is None:
        raise ImportError("cannot load RNAInverseDesign oracle")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _valid(oracle, sequence, problem):
    try:
        oracle._validate_sequence("".join(sequence), problem)
        return True
    except Exception:
        return False


def _initial_sequence(oracle, problem, seed):
    rng = random.Random(seed)
    length = int(problem["length"])
    target_pairs = oracle._parse_structure(problem["target_structure"])
    paired = {index for pair in target_pairs for index in pair}
    fixed = {int(index): str(base) for index, base in problem["fixed_bases"]}
    for _ in range(4000):
        sequence = [rng.choice("ACGU") for _ in range(length)]
        for left, right in target_pairs:
            options = [
                pair for pair in PAIR_TYPES
                if fixed.get(left, pair[0]) == pair[0]
                and fixed.get(right, pair[1]) == pair[1]
            ]
            sequence[left], sequence[right] = rng.choice(options)
        for index, base in fixed.items():
            sequence[index] = base
        for _ in range(24):
            text = "".join(sequence)
            bad = next(
                (motif for motif in problem["forbidden_motifs"] if motif in text),
                None,
            )
            if bad is None:
                break
            start = text.index(bad)
            mutable = [
                index for index in range(start, start + len(bad))
                if index not in fixed and index not in paired
            ]
            if not mutable:
                break
            index = rng.choice(mutable)
            sequence[index] = rng.choice([base for base in "ACGU" if base != bad[0]])
        if _valid(oracle, sequence, problem):
            return sequence
    raise RuntimeError("could not construct a feasible target-compatible sequence")


def _objective(oracle, sequence, problem):
    return float(oracle._sequence_metrics(
        "".join(sequence), problem
    )["exact_utility"])


def _search_one(oracle, problem, seed, restarts, iterations):
    target_pairs = oracle._parse_structure(problem["target_structure"])
    fixed = {int(index): str(base) for index, base in problem["fixed_bases"]}
    mutable = [index for index in range(problem["length"]) if index not in fixed]
    best = None
    best_value = -math.inf
    for restart in range(restarts):
        local_seed = int(seed) + 1009 * restart
        rng = random.Random(local_seed)
        sequence = _initial_sequence(oracle, problem, local_seed + 37)
        value = _objective(oracle, sequence, problem)
        temperature = 0.045
        for _ in range(iterations):
            candidate = sequence.copy()
            if rng.random() < 0.70:
                left, right = rng.choice(target_pairs)
                options = [
                    pair for pair in PAIR_TYPES
                    if fixed.get(left, pair[0]) == pair[0]
                    and fixed.get(right, pair[1]) == pair[1]
                ]
                candidate[left], candidate[right] = rng.choice(options)
            else:
                index = rng.choice(mutable)
                candidate[index] = rng.choice("ACGU")
            if not _valid(oracle, candidate, problem):
                continue
            candidate_value = _objective(oracle, candidate, problem)
            if (
                candidate_value >= value
                or rng.random() < math.exp(
                    (candidate_value - value) / max(temperature, 1.0e-12)
                )
            ):
                sequence, value = candidate, candidate_value
            temperature *= 0.995

        # A deterministic final pass makes the frozen result independent of an arbitrary
        # annealing cutoff whenever a one-coordinate improvement is still available.
        for _ in range(4):
            changed = False
            moves = []
            for left, right in target_pairs:
                for pair in PAIR_TYPES:
                    if (
                        fixed.get(left, pair[0]) == pair[0]
                        and fixed.get(right, pair[1]) == pair[1]
                    ):
                        moves.append(((left, right), pair))
            for index in mutable:
                moves.extend([((index,), (base,)) for base in "ACGU"])
            for indices, bases in moves:
                candidate = sequence.copy()
                for index, base in zip(indices, bases):
                    candidate[index] = base
                if not _valid(oracle, candidate, problem):
                    continue
                candidate_value = _objective(oracle, candidate, problem)
                if candidate_value > value + 1.0e-12:
                    sequence, value = candidate, candidate_value
                    changed = True
            if not changed:
                break
        if value > best_value + 1.0e-15:
            best = "".join(sequence)
            best_value = value
    return best, best_value


def generate(restarts=4, iterations=400):
    oracle = _load_oracle()
    records = []
    for index, instance in enumerate(oracle.INSTANCES):
        problem = oracle._problem(instance)
        sequence, search_objective = _search_one(
            oracle, problem, 2026072400 + 101 * index, restarts, iterations
        )
        nominal = oracle._sequence_metrics(sequence, problem)
        shifts = [
            oracle._sequence_metrics(sequence, problem, shift)
            for shift in oracle.SHIFT_SPECS
        ]
        records.append({
            "name": instance["name"],
            "sequence": sequence,
            "search_objective": search_objective,
            "nominal": nominal,
            "shift_exact_utilities": [row["exact_utility"] for row in shifts],
        })
    return {
        "schema_version": 1,
        "algorithm": "seeded_target_compatible_annealing_plus_coordinate_improvement",
        "config": {"restarts": int(restarts), "iterations": int(iterations)},
        "records": records,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--restarts", type=int, default=4)
    parser.add_argument("--iterations", type=int, default=400)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.restarts < 1 or args.iterations < 1:
        raise SystemExit("restarts and iterations must be positive")
    report = generate(args.restarts, args.iterations)
    text = json.dumps(report, indent=2, allow_nan=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")


if __name__ == "__main__":
    main()

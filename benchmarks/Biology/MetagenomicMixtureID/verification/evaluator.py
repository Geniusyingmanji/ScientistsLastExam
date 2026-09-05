"""Deterministic metagenomic mixture oracle.

A sample holds a mixture of strains from a public marker database. Sequencing depth
is bought one run at a time; each run returns per-marker read counts. Strain
presence and abundance are recoverable from genome-specific markers, while a novel
organism outside the library contributes only to conserved markers — an excess no
library assignment can explain, which must be refused rather than absorbed.
"""

from __future__ import annotations

import math

import numpy as np

DIFFICULTY = 1

GENOME_COUNT = 30
UNIQUE_PER_GENOME = 40
CONSERVED_COUNT = 30
READS_PER_DEPTH = 5000
DEPTHS = (1, 2, 5, 10, 20)
RUN_COST = 1
BUDGET_UNITS = 6

UNIQUE_MARKER_IDS = ["m%04d" % index for index in range(GENOME_COUNT * UNIQUE_PER_GENOME)]
CONSERVED_MARKER_IDS = ["m%04d" % index
                        for index in range(GENOME_COUNT * UNIQUE_PER_GENOME,
                                           GENOME_COUNT * UNIQUE_PER_GENOME + CONSERVED_COUNT)]
GENOME_IDS = ["g%02d" % index for index in range(GENOME_COUNT)]

_BASE_DEVELOPMENT_SPECS = (
    (24011, "supported"), (24017, "supported"), (24023, "supported"),
    (24029, "supported"), (24031, "supported"),
    (24037, "novel"), (24041, "novel"),
)
HELDOUT_SPECS = (
    (25007, "supported"), (25013, "supported"), (25019, "novel"),
)


def _world(spec):
    seed, kind = spec
    rng = np.random.default_rng(int(seed))
    strain_count = int(rng.integers(2, 6))
    chosen = rng.choice(GENOME_COUNT, size=strain_count, replace=False)
    weights = rng.dirichlet(np.full(strain_count, 1.2))
    if kind == "novel":
        # A novel organism claims a fixed share; library strains share the rest.
        novel_share = float(rng.uniform(0.15, 0.40))
        weights = weights * (1.0 - novel_share)
    else:
        novel_share = 0.0
    abundance = {GENOME_IDS[index]: float(weight)
                 for index, weight in zip(chosen, weights)}
    return {"seed": int(seed), "kind": kind, "abundance": abundance,
            "novel_share": novel_share}


def problem_statement(world):
    del world
    marker_db = {}
    for genome_index, genome in enumerate(GENOME_IDS):
        for slot in range(UNIQUE_PER_GENOME):
            marker_db[UNIQUE_MARKER_IDS[genome_index * UNIQUE_PER_GENOME + slot]] = {
                "genome": genome, "type": "unique"}
    for name in CONSERVED_MARKER_IDS:
        marker_db[name] = {"genome": None, "type": "conserved"}
    return {
        "genome_ids": list(GENOME_IDS),
        "marker_database": marker_db,
        "sequencing_depths": list(DEPTHS),
        "reads_per_depth_unit": READS_PER_DEPTH,
        "mapping_note": (
            "about 60 percent of a library strain's reads map to its unique markers, "
            "about 30 percent to the conserved core, and the rest drop; a novel "
            "organism's reads can only appear on conserved markers"
        ),
        "run_cost": RUN_COST,
        "budget_units": BUDGET_UNITS,
    }


def _run(world, depth, call_index):
    rng = np.random.default_rng(world["seed"] + 977 * int(depth) + 31 * call_index)
    reads = int(depth) * READS_PER_DEPTH
    unique_targets = []
    for genome in GENOME_IDS:
        share = world["abundance"].get(genome, 0.0)
        unique_targets.extend([genome] * UNIQUE_PER_GENOME)
    # Read allocation: unique (0.6), conserved (0.3), unmapped (0.1); novel reads
    # (0.6 of novel share) also drop, 0.3 land on conserved.
    unique_mass = 0.6 * (1.0 - world["novel_share"])
    conserved_mass = 0.3
    unmapped_mass = 1.0 - unique_mass - conserved_mass
    unique_genome_shares = np.asarray(
        [world["abundance"].get(genome, 0.0) / max(1e-12, 1.0 - world["novel_share"])
         if world["novel_share"] > 0 else world["abundance"].get(genome, 0.0)
         for genome in GENOME_IDS])
    unique_shares = np.repeat(unique_genome_shares, UNIQUE_PER_GENOME)
    probabilities = np.concatenate([
        unique_mass * unique_shares / unique_shares.sum() if unique_shares.sum() > 0
        else np.zeros(len(unique_shares)),
        np.full(CONSERVED_COUNT, conserved_mass / CONSERVED_COUNT),
        [unmapped_mass],
    ])
    probabilities = probabilities / probabilities.sum()
    counts = rng.multinomial(reads, probabilities)
    marker_counts = {}
    for name, value in zip(UNIQUE_MARKER_IDS + CONSERVED_MARKER_IDS, counts):
        if value:
            marker_counts[name] = int(value)
    return {"depth_units": int(depth), "total_reads": reads,
            "marker_counts": marker_counts, "budget_cost": RUN_COST}


class _Sequencer:
    def __init__(self, world):
        self.world = world
        self.used = 0
        self.calls = 0
        self.violated = False

    def run_sequencing(self, depth_units):
        try:
            if depth_units not in DEPTHS:
                self.violated = True
                raise ValueError("depth must be one of the published units")
            if self.used + RUN_COST > BUDGET_UNITS:
                self.violated = True
                raise RuntimeError("sequencing budget exceeded")
            self.used += RUN_COST
            self.calls += 1
            return _run(self.world, depth_units, self.calls)
        except Exception:
            self.violated = True
            raise


def _validate(submission):
    if not isinstance(submission, dict):
        raise ValueError("submission must be a mapping")
    abstain = submission.get("abstain")
    if not isinstance(abstain, (bool, np.bool_)):
        raise ValueError("abstain must be boolean")
    confidence = float(submission.get("confidence"))
    if not math.isfinite(confidence) or not 0.0 <= confidence <= 1.0:
        raise ValueError("confidence must be in [0,1]")
    if bool(abstain):
        if submission.get("present") or submission.get("abundances"):
            raise ValueError("abstention requires an empty mixture claim")
        return [], {}, confidence, True
    present = submission.get("present")
    if not isinstance(present, (list, tuple)) or any(g not in GENOME_IDS for g in present):
        raise ValueError("present must list known genome ids")
    if len(set(present)) != len(present):
        raise ValueError("present genomes must be unique")
    abundances = submission.get("abundances")
    if not isinstance(abundances, dict) or set(abundances) != set(present):
        raise ValueError("abundances must cover exactly the claimed genomes")
    values = np.asarray([float(abundances[g]) for g in present])
    if np.any(~np.isfinite(values)) or np.any(values < 0) or \
            not np.isclose(values.sum(), 1.0, atol=1e-6):
        raise ValueError("abundances must be nonnegative and sum to one")
    return list(present), {g: float(v) for g, v in zip(present, values)}, confidence, False


def _mixture_score(present, abundances, world):
    truth = world["abundance"]
    claimed = set(present)
    true = set(truth)
    if not claimed and not true:
        return 1.0
    intersection = len(claimed & true)
    precision = intersection / len(claimed) if claimed else 0.0
    recall = intersection / len(true) if true else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if intersection else 0.0
    log_errors = []
    for genome, weight in truth.items():
        estimated = abundances.get(genome, 0.0)
        log_errors.append(abs(math.log(max(estimated, 1e-6) / max(weight, 1e-6))))
    abundance_score = math.exp(-2.0 * float(np.mean(log_errors)))
    return float(0.7 * f1 + 0.3 * abundance_score)


def _empty(split, index):
    return {"split": split, "world_index": index, "valid": False, "abstained": False,
            "mechanism_score": 0.0, "set_f1": 0.0, "abundance_score": 0.0,
            "false_discovery": False, "correct_refusal": False,
            "confidence_score": 0.0, "budget_used": 0}


def _evaluate_world(candidate, spec, split, index):
    row = _empty(split, index)
    world = _world(spec)
    sequencer = _Sequencer(world)
    try:
        submission = candidate(problem_statement(world), sequencer.run_sequencing,
                               BUDGET_UNITS)
        present, abundances, confidence, abstain = _validate(submission)
        if sequencer.violated:
            raise ValueError("sequencer contract violated")
        supported = world["kind"] == "supported"
        if supported and not abstain:
            mechanism = _mixture_score(present, abundances, world)
            claimed = set(present)
            truth = set(world["abundance"])
            f1 = (len(claimed & truth) / len(claimed | truth)) if (claimed or truth) else 1.0
            row["set_f1"] = float(f1)
            row["abundance_score"] = float(mechanism)
        elif supported:
            mechanism = 0.0
        else:
            correct = bool(abstain)
            mechanism = 1.0 if correct else 0.0
        target = 1.0 if (supported != abstain or (not supported and abstain)) else 0.0
        row.update({"valid": True, "abstained": abstain,
                    "mechanism_score": float(mechanism),
                    "false_discovery": bool(not supported and not abstain),
                    "correct_refusal": bool(not supported and abstain),
                    "confidence_score": 1.0 - (confidence - target) ** 2,
                    "budget_used": sequencer.used})
    except Exception:
        pass
    return row


def _summary(rows, specs):
    supported = [r for r, s in zip(rows, specs) if s[1] == "supported"]
    unsupported = [r for r, s in zip(rows, specs) if s[1] != "supported"]
    raw = float(np.mean([r["mechanism_score"] for r in rows]))
    abstain_base = len(unsupported) / len(rows)
    return {
        "normalized": float(np.clip((raw - abstain_base) / (1.0 - abstain_base), 0.0, 1.0)),
        "raw": raw,
        "valid_count": sum(r["valid"] for r in rows),
        "set_f1": float(np.mean([r["set_f1"] for r in supported])) if supported else 0.0,
        "false_count": sum(r["false_discovery"] for r in unsupported),
        "refusal_count": sum(r["correct_refusal"] for r in unsupported),
        "attempt_count": sum(not r["abstained"] for r in supported),
        "supported_count": len(supported), "unsupported_count": len(unsupported),
    }


def evaluate(identify_mixture):
    development = [_evaluate_world(identify_mixture, spec, "development", i)
                   for i, spec in enumerate(_BASE_DEVELOPMENT_SPECS)]
    heldout = [_evaluate_world(identify_mixture, spec, "heldout", i)
               for i, spec in enumerate(HELDOUT_SPECS)]
    dev, hold = _summary(development, _BASE_DEVELOPMENT_SPECS), _summary(heldout, HELDOUT_SPECS)
    dev_valid = dev["valid_count"] == len(development)
    hold_valid = hold["valid_count"] == len(heldout)
    return {
        "combined_score": dev["normalized"] if dev_valid else 0.0,
        "valid": 1.0 if dev_valid else 0.0,
        "feasibility_rate": dev["valid_count"] / len(development),
        "mechanism_score": dev["raw"],
        "development_set_f1": dev["set_f1"],
        "development_false_discovery_rate": dev["false_count"] / dev["unsupported_count"],
        "development_correct_refusal_rate": dev["refusal_count"] / dev["unsupported_count"],
        "development_discovery_coverage": dev["attempt_count"] / dev["supported_count"],
        "supported_world_count": dev["supported_count"],
        "unsupported_world_count": dev["unsupported_count"],
        "false_discovery_count": dev["false_count"],
        "correct_refusal_count": dev["refusal_count"],
        "robustness_score": hold["normalized"] if hold_valid else 0.0,
        "heldout_feasibility_rate": hold["valid_count"] / len(heldout),
        "heldout_false_discovery_rate": hold["false_count"] / hold["unsupported_count"],
        "heldout_correct_refusal_rate": hold["refusal_count"] / hold["unsupported_count"],
        "per_world": development + heldout,
    }

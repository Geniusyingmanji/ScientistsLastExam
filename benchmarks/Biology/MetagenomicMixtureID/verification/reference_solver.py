"""Truth-blind reference witness: marker statistics with conserved-excess novelty test.

Aggregates every purchased run, calls a genome present when its unique-marker depth
clears a Poisson threshold against the run depth, normalizes abundances over the
unique evidence, and refuses when the conserved-marker mass exceeds what the
estimated library mixture can produce by more than four standard errors — the
signature of a novel organism outside the database. It deliberately lacks
expectation-maximization refinement, marker-length normalization and multi-run
variance weighting.
"""

from __future__ import annotations

import math

import numpy as np

UNIQUE_THRESHOLD_FACTOR = 6.0
NOVELTY_SIGMA = 4.0


def identify_mixture(problem, run_sequencing, budget_units):
    database = problem["marker_database"]
    unique_owner = {name: row["genome"] for name, row in database.items()
                    if row["type"] == "unique"}
    conserved = [name for name, row in database.items() if row["type"] == "conserved"]
    genomes = problem["genome_ids"]
    unique_per_genome = sum(1 for name in unique_owner.values()) // len(genomes)

    runs = [run_sequencing(depth) for depth in (10, 10, 5)]
    total_depth = sum(run["depth_units"] for run in runs)
    counts = {}
    for run in runs:
        for marker, value in run["marker_counts"].items():
            counts[marker] = counts.get(marker, 0) + value

    # Presence: unique-marker depth per genome against a Poisson background.
    unique_depth = {genome: 0 for genome in genomes}
    for marker, value in counts.items():
        genome = unique_owner.get(marker)
        if genome:
            unique_depth[genome] += value
    background = 0.02 * total_depth * problem["reads_per_depth_unit"] / len(genomes)
    threshold = background + UNIQUE_THRESHOLD_FACTOR * math.sqrt(max(background, 1.0))
    present = [g for g in genomes if unique_depth[g] > threshold]
    if not present:
        present = [max(genomes, key=lambda g: unique_depth[g])]

    # Novelty: conserved mass minus the library expectation.
    conserved_count = sum(counts.get(name, 0) for name in conserved)
    total_reads = total_depth * problem["reads_per_depth_unit"]
    # 0.3 of every read targets conserved markers; library fraction of unique mass.
    unique_total = sum(unique_depth.values())
    library_share = min(1.0, unique_total / max(0.6 * (total_reads - 0), 1.0)) \
        if total_reads else 0.0
    expected_conserved = 0.3 * total_reads * max(0.0, min(1.0, library_share))
    sigma = math.sqrt(max(expected_conserved, 1.0))
    if conserved_count > expected_conserved + NOVELTY_SIGMA * sigma:
        return {"present": [], "abundances": {}, "abstain": True, "confidence": 0.8}

    weights = {g: unique_depth[g] for g in present}
    norm = sum(weights.values()) or 1.0
    abundances = {g: weights[g] / norm for g in present}
    return {"present": present, "abundances": abundances,
            "abstain": False, "confidence": 0.7}

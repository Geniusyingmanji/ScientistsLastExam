"""Weak valid baseline: names three fixed genomes with uniform abundances.

It ignores the sequencing data entirely — the mixture claim a copy-paste pipeline
would ship — and never refuses.
"""

from __future__ import annotations


def identify_mixture(problem, run_sequencing, budget_units):
    del run_sequencing, budget_units
    ranked = list(problem["genome_ids"][:3])
    abundance = 1.0 / len(ranked)
    return {"present": ranked,
            "abundances": {genome: abundance for genome in ranked},
            "abstain": False, "confidence": 0.9}

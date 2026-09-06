"""Reproduce the reference ablations and a low-dimensional apparent-age shortcut sweep."""
from __future__ import annotations

import importlib.util
import itertools
import json
import math
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


EVALUATOR = _load("upb_analysis_evaluator", HERE / "evaluator.py")
REFERENCE = _load("upb_analysis_reference", HERE / "reference_solver.py")


def _strategy(**kwargs):
    return lambda problem, measure: REFERENCE.infer_with_policy(problem, measure, **kwargs)


def _apparent_age(ratio, decay_constant):
    return math.log1p(max(-0.999999, ratio)) / decay_constant / 1.0e6


def _shortcut(count, selection, concordance_threshold, spread_threshold):
    def candidate(problem, measure):
        descriptors = sorted(problem["grain_descriptors"], key=lambda row: row["domain_position"])
        if selection == "quality":
            descriptors = sorted(descriptors, key=lambda row: -row["expected_signal_quality"])
        elif selection == "first":
            descriptors = sorted(descriptors, key=lambda row: row["grain_id"])
        indices = np.linspace(0, len(descriptors) - 1, count).round().astype(int) if selection == "span" else range(count)
        rows = [measure(descriptors[i]["grain_id"], "analytical") for i in indices]
        constants = problem["decay_constants_per_year"]
        ages_235 = np.array([_apparent_age(row["pb207_u235"], constants["u235"]) for row in rows])
        ages_238 = np.array([_apparent_age(row["pb206_u238"], constants["u238"]) for row in rows])
        evidence = [row["query_id"] for row in rows]
        discordance = float(np.median(np.abs(ages_235 - ages_238)))
        spread = float(np.ptp((ages_235 + ages_238) / 2.0))
        if discordance < concordance_threshold:
            return {"history": "concordant", "crystallization_age_myr": float(np.median((ages_235 + ages_238) / 2.0)),
                    "confidence": 0.6, "evidence_query_ids": evidence, "abstain": False}
        if spread > spread_threshold:
            return {"abstain": True, "confidence": 0.6, "evidence_query_ids": evidence}
        return {"history": "lead_loss", "crystallization_age_myr": float(np.max(ages_235)),
                "lead_loss_age_myr": float(np.clip(np.min(ages_238), *problem["lead_loss_age_bounds_myr"])),
                "confidence": 0.6, "evidence_query_ids": evidence, "abstain": False}
    return candidate


def _compact(metrics):
    return {key: round(metrics[key], 6) for key in (
        "combined_score", "development_history_accuracy", "development_crystallization_age_score",
        "development_lead_loss_age_score", "development_false_discovery_rate",
        "development_correct_refusal_rate", "development_discovery_coverage", "heldout_mechanism_score")}


def main():
    variants = {
        "reference": REFERENCE.infer_upb_history,
        "three_analytical": _strategy(count=3, selection="quality"),
        "six_evenly_spaced": _strategy(count=6, selection="span"),
        "six_contiguous_domains": _strategy(count=6, selection="first"),
        "six_highest_quality": _strategy(count=6, selection="quality"),
        "six_stratified_quality": _strategy(count=6, selection="stratified_quality"),
        "eighteen_screen": _strategy(count=18, precision="screen"),
        "ignore_uncertainties": _strategy(selection="quality", use_uncertainties=False),
        "never_refuse": _strategy(selection="quality", refuse=False),
        "round_ages_to_50_myr": _strategy(selection="quality", round_to=50.0),
    }
    results = {name: _compact(EVALUATOR.evaluate(candidate)) for name, candidate in variants.items()}
    best = (-1.0, None)
    tried = 0
    for count, selection, concordance, spread in itertools.product(
            (3, 4, 5, 6), ("span", "quality", "first"),
            (10.0, 25.0, 50.0, 100.0), (100.0, 250.0, 500.0, 900.0)):
        tried += 1
        metrics = EVALUATOR.evaluate(_shortcut(count, selection, concordance, spread))
        if metrics["combined_score"] > best[0]:
            best = (metrics["combined_score"], {
                "count": count, "selection": selection, "concordance_threshold_myr": concordance,
                "spread_threshold_myr": spread, "metrics": _compact(metrics)})
    print(json.dumps({"ablations": results, "shortcut_strategies": tried,
                      "best_apparent_age_shortcut": best[1]}, indent=2))


if __name__ == "__main__":
    main()

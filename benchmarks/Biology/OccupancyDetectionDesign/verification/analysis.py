"""Task-local reference, ablation and shortcut analysis."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


EVALUATOR = _load("occupancy_evaluator", HERE / "evaluator.py")
REFERENCE = _load("occupancy_reference", HERE / "reference_solver.py")
BASELINE = _load("occupancy_baseline", HERE.parent / "solution.py")


def _policy(**kwargs):
    def run(problem, survey):
        return REFERENCE.infer_with_policy(problem, survey, **kwargs)
    return run


def blanket(problem, survey):
    evidence = [survey(row["site_id"], "rapid")["query_id"]
                for row in problem["site_descriptors"][:4]]
    return {"abstain": True, "confidence": 0.5, "evidence_query_ids": evidence}


def fixed(effect, beta, prevalence):
    def run(problem, survey):
        evidence = [survey(row["site_id"], "rapid")["query_id"]
                    for row in problem["site_descriptors"]]
        return {"abstain": False, "effect": effect, "habitat_effect": beta,
                "mean_occupancy": prevalence, "confidence": 0.6,
                "evidence_query_ids": evidence}
    return run


def shortcut(site_limit, revisit, effect_threshold, alternative_threshold, beta_scale, offset):
    def run(problem, survey):
        ordered = sorted(problem["site_descriptors"], key=lambda row: row["habitat_covariate"])
        indices = np.linspace(0, len(ordered) - 1, site_limit).round().astype(int)
        sites = [ordered[int(i)] for i in indices]
        rows = [survey(site["site_id"], "rapid") for site in sites]
        remaining = problem["survey_budget_units"] - len(rows)
        cost = problem["survey_methods"][revisit]["cost"]
        count = min(len(sites), remaining // cost)
        revisit_indices = np.linspace(0, len(sites) - 1, count).round().astype(int)
        rows.extend(survey(sites[int(i)]["site_id"], revisit) for i in revisit_indices)
        by_site = {site["site_id"]: [] for site in sites}
        for row in rows:
            by_site[row["site_id"]].append(float(row["detected"]))
        y = np.array([max(by_site[site["site_id"]]) for site in sites])
        x = np.array([site["habitat_covariate"] for site in sites])
        pos = np.array([site["transect_position"] for site in sites])
        slope = float(np.sum((x - np.mean(x)) * (y - np.mean(y))) / np.sum((x - np.mean(x)) ** 2))

        def corr(feature):
            feature = feature - np.mean(feature)
            centered = y - np.mean(y)
            denom = float(np.sqrt(np.sum(feature * feature) * np.sum(centered * centered)))
            return 0.0 if denom == 0.0 else abs(float(np.sum(feature * centered) / denom))

        linear_signal = corr(x)
        alternative = max(corr(x * x), corr(np.sin(2.0 * np.pi * pos)))
        evidence = [row["query_id"] for row in rows]
        if alternative > alternative_threshold and alternative > 1.2 * linear_signal:
            return {"abstain": True, "confidence": 0.65, "evidence_query_ids": evidence}
        effect = "positive" if slope > effect_threshold else "negative" if slope < -effect_threshold else "none"
        return {"abstain": False, "effect": effect,
                "habitat_effect": float(np.clip(beta_scale * slope, -4.0, 4.0)),
                "mean_occupancy": float(np.clip(np.mean(y) + offset, 0.0, 1.0)),
                "confidence": 0.65, "evidence_query_ids": evidence}
    return run


def compact(metrics):
    keys = ["combined_score", "heldout_mechanism_score", "development_effect_accuracy",
            "development_habitat_effect_score", "development_mean_occupancy_score",
            "development_false_discovery_rate", "development_correct_refusal_rate",
            "development_discovery_coverage", "development_mean_budget_used"]
    return {key: metrics[key] for key in keys}


def main():
    methods = {
        "reference": REFERENCE.infer_occupancy,
        "no_intensive": _policy(use_intensive=False, site_limit=48),
        "twenty_sites": _policy(site_limit=20),
        "twenty_eight_sites": _policy(site_limit=28),
        "thirty_two_sites": _policy(site_limit=32),
        "detection_only": _policy(blend=0.0),
        "likelihood_only": _policy(blend=1.0),
        "no_model_comparison": _policy(test_nonlinearity=False),
        "never_refuse": _policy(force_claim=True),
        "blanket_abstain": blanket,
        "baseline": BASELINE.infer_occupancy,
    }
    report = {name: compact(EVALUATOR.evaluate(method)) for name, method in methods.items()}
    best = None
    best_name = None
    for site_limit in (24, 48):
        for revisit in ("rapid", "intensive"):
            for effect_threshold in (0.03, 0.08, 0.13, 0.18):
                for alternative_threshold in (0.20, 0.30, 0.40):
                    for beta_scale in (2.0, 3.0, 4.0):
                        for offset in (0.0, 0.15, 0.30):
                            name = "shortcut_%d_%s_%.2f_%.2f_%.1f_%.2f" % (
                                site_limit, revisit, effect_threshold, alternative_threshold,
                                beta_scale, offset)
                            metrics = compact(EVALUATOR.evaluate(shortcut(
                                site_limit, revisit, effect_threshold, alternative_threshold,
                                beta_scale, offset)))
                            if best is None or metrics["combined_score"] > best["combined_score"]:
                                best, best_name = metrics, name
    report["shortcut_best_of_432"] = {"configuration": best_name, **best}
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

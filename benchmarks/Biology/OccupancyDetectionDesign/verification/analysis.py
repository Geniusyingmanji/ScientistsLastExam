"""Task-local reference, ablation and shortcut analysis."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

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


def compact(metrics):
    keys = ["combined_score", "heldout_mechanism_score", "development_effect_accuracy",
            "development_habitat_effect_score", "development_mean_occupancy_score",
            "development_false_discovery_rate", "development_correct_refusal_rate",
            "development_discovery_coverage", "development_mean_budget_used"]
    return {key: metrics[key] for key in keys}


def main():
    methods = {
        "reference": REFERENCE.infer_occupancy,
        "no_intensive": _policy(use_intensive=False),
        "twelve_sites": _policy(site_limit=12),
        "no_model_comparison": _policy(test_nonlinearity=False),
        "never_refuse": _policy(force_claim=True),
        "blanket_abstain": blanket,
        "baseline": BASELINE.infer_occupancy,
    }
    for effect, beta in (("negative", -1.5), ("none", 0.0), ("positive", 1.5)):
        for prevalence in (0.3, 0.5, 0.7):
            methods["fixed_%s_%s" % (effect, prevalence)] = fixed(effect, beta, prevalence)
    report = {name: compact(EVALUATOR.evaluate(method)) for name, method in methods.items()}
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

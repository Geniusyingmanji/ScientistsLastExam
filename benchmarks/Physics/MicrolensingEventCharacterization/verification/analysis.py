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


EVALUATOR = _load("microlensing_evaluator", HERE / "evaluator.py")
REFERENCE = _load("microlensing_reference", HERE / "reference_solver.py")
BASELINE = _load("microlensing_baseline", HERE.parent / "solution.py")


def _policy(use_g=True, refuse=True):
    def run(problem, observe):
        times = problem["candidate_times"]
        rows = [observe(float(t), "r") for t in times[::2]][:18]
        if use_g:
            rows.extend(observe(float(t), "g") for t in (-18.0, -10.0, 0.0, 8.0, 16.0, 22.0))
        evidence = [row["query_id"] for row in rows]
        values = [row["flux"] for row in rows if row["band"] == "r"]
        if refuse and max(values) - min(values) < 0.22:
            return {"abstain": True, "confidence": 0.6, "evidence_query_ids": evidence}
        return {"abstain": False, "model": "point_lens", "timescale_days": 8.0,
                "amplitude": 0.0, "confidence": 0.55, "evidence_query_ids": evidence}
    return run


def blanket(problem, observe):
    evidence = [observe(float(t), "r")["query_id"] for t in problem["candidate_times"][:6]]
    return {"abstain": True, "confidence": 0.5, "evidence_query_ids": evidence}


def compact(metrics):
    keys = ["combined_score", "heldout_mechanism_score", "development_model_accuracy",
            "heldout_model_accuracy", "development_false_discovery_rate",
            "development_correct_refusal_rate", "development_mean_budget_used"]
    return {key: metrics[key] for key in keys}


def main():
    report = {
        "reference": compact(EVALUATOR.evaluate(REFERENCE.infer_microlensing)),
        "baseline": compact(EVALUATOR.evaluate(BASELINE.infer_microlensing)),
        "no_g_band": compact(EVALUATOR.evaluate(_policy(use_g=False))),
        "never_refuse": compact(EVALUATOR.evaluate(_policy(refuse=False))),
        "blanket_abstain": compact(EVALUATOR.evaluate(blanket)),
    }
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    raise SystemExit(main())

"""Reproduce reference metrics and the declared shortcut families."""
from __future__ import annotations

import importlib.util
import itertools
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


EVALUATOR = _load("microlensing_calibration_evaluator", HERE / "evaluator.py")
REFERENCE = _load("microlensing_calibration_reference", HERE / "reference_solver.py")
CONSTANT = _load("microlensing_constant_shortcut", HERE / "shortcut_constant.py")
TEXTBOOK = _load("microlensing_textbook_shortcut", HERE / "shortcut_textbook.py")


def _summary(metrics):
    keys = (
        "combined_score", "development_mechanism_score", "heldout_mechanism_score",
        "development_model_accuracy", "heldout_model_accuracy",
        "development_false_discovery_rate", "heldout_false_discovery_rate",
        "development_correct_refusal_rate", "heldout_correct_refusal_rate",
        "development_mean_budget_used", "heldout_mean_budget_used",
    )
    return {key: metrics[key] for key in keys}


def _twice(candidate):
    first = EVALUATOR.evaluate(candidate)
    second = EVALUATOR.evaluate(candidate)
    if first != second or first["valid"] != 1.0:
        raise RuntimeError("candidate is invalid or nondeterministic")
    return first


def main():
    reference = _twice(REFERENCE.infer_microlensing)
    textbook = _twice(TEXTBOOK.infer_microlensing)
    best = None
    count = 0
    for parameters in itertools.product(
        (1.015, 1.035, 1.055, 1.075),
        (0.12, 0.20, 0.28, 0.36),
        (0.30, 0.38, 0.46, 0.54),
        (8.0, 11.0, 14.0),
        (12.0, 15.0, 18.0),
    ):
        metrics = EVALUATOR.evaluate(CONSTANT.policy(*parameters))
        count += 1
        if best is None or metrics["combined_score"] > best[0]:
            best = (metrics["combined_score"], parameters, metrics)
    print(json.dumps({
        "reference": _summary(reference),
        "constant_shortcut_sweep": {
            "strategy_count": count,
            "best_parameters": list(best[1]),
            **_summary(best[2]),
        },
        "textbook_fixed_source_shortcut": _summary(textbook),
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

"""Print task-local baseline and reference calibration metrics."""
from __future__ import annotations
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def main():
    evaluator = load(ROOT / "verification" / "evaluator.py", "transient_evaluator")
    baseline = load(ROOT / "solution.py", "transient_baseline")
    reference = load(ROOT / "verification" / "reference_solver.py", "transient_reference")
    keys = ("combined_score", "valid", "development_mechanism_score", "heldout_mechanism_score",
            "development_model_accuracy", "heldout_model_accuracy",
            "development_false_discovery_rate", "heldout_false_discovery_rate",
            "development_correct_refusal_rate", "heldout_correct_refusal_rate")
    print(json.dumps({"baseline": {k: evaluator.evaluate(baseline.infer_transient).get(k) for k in keys},
                      "reference": {k: evaluator.evaluate(reference.infer_transient).get(k) for k in keys}}, indent=2))

if __name__ == "__main__":
    main()

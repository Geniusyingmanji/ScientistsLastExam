from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path


TASK_DIR = Path(__file__).resolve().parent.parent


def _load(path, name):
    spec = importlib.util.spec_from_file_location("candidate", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return getattr(module, name)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--metrics-out", required=True)
    args = parser.parse_args()
    metrics = {"combined_score": -1e18, "valid": 0.0}
    try:
        oracle = _load(TASK_DIR / "verification" / "evaluator.py", "evaluate")
        candidate = _load(Path(args.candidate).resolve(), "discover_mechanism")
        metrics.update(oracle(candidate))
    except Exception as exc:
        metrics["error_message"] = "%s: %s" % (type(exc).__name__, exc)
    Path(args.metrics_out).write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


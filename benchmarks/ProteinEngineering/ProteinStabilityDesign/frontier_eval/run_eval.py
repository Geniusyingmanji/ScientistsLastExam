from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path


INVALID = -1e18
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
    metrics = {"combined_score": INVALID, "valid": 0.0}
    try:
        sys.path.insert(0, str(TASK_DIR / "verification"))
        import evaluator as oracle
        candidate = _load(Path(args.candidate).resolve(), "design_stable_batch")
        result = oracle.evaluate(candidate)
        metrics.update(result)
        metrics["raw_score"] = result.get("combined_score")
    except Exception as exc:
        metrics["error_message"] = "%s: %s" % (type(exc).__name__, exc)
    Path(args.metrics_out).write_text(
        json.dumps(metrics, indent=2, default=str), encoding="utf-8"
    )
    print(json.dumps({key: metrics.get(key) for key in ("combined_score", "valid")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from sle.secure_eval import CandidateProxy

INVALID = -1e18
TASK_DIR = Path(__file__).resolve().parent.parent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--metrics-out", required=True)
    args = parser.parse_args()
    metrics = {"combined_score": INVALID, "valid": 0.0}
    try:
        sys.path.insert(0, str(TASK_DIR / "verification"))
        import evaluator as oracle
        with CandidateProxy(
            Path(args.candidate).resolve(),
            "design_finite_volume_method",
            timeout_s=90,
        ) as candidate:
            result = oracle.evaluate(candidate)
            if candidate.failure is not None:
                raise candidate.failure
        metrics.update(result)
        metrics["raw_score"] = result.get("combined_score")
    except Exception as exc:  # noqa: BLE001 - evaluator boundary must serialize every failure
        metrics["error_message"] = f"{type(exc).__name__}: {exc}"
    Path(args.metrics_out).write_text(
        json.dumps(metrics, indent=2, default=str), encoding="utf-8"
    )
    print(json.dumps({key: metrics.get(key) for key in ("combined_score", "valid")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Black-box eval entrypoint for TensorRank555."""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
from sle.secure_eval import CandidateProxy

INVALID = -1e18
TASK_DIR = Path(__file__).resolve().parent.parent


def _load_callable(path: Path, name: str):
    return CandidateProxy(path, name, timeout_s=300)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidate", required=True)
    ap.add_argument("--metrics-out", required=True)
    args = ap.parse_args()
    metrics = {"combined_score": INVALID, "valid": 0.0}
    try:
        sys.path.insert(0, str(TASK_DIR / "verification"))
        import evaluator as oracle  # type: ignore
        build = _load_callable(Path(args.candidate).resolve(), "build_algorithm")
        result = oracle.evaluate(build)
        metrics.update(result)
        metrics["raw_score"] = result.get("combined_score")
    except Exception as exc:  # noqa: BLE001
        metrics["error_message"] = f"{type(exc).__name__}: {exc}"
    Path(args.metrics_out).write_text(
        json.dumps(metrics, indent=2, default=str), encoding="utf-8"
    )
    print(json.dumps({k: metrics.get(k) for k in ("combined_score", "valid", "beat_sota")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

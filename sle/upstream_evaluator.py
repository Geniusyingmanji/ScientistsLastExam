"""Trusted evaluator entrypoints used by optional upstream search frameworks.

The framework process may write candidate programs, but every score still crosses the
same :func:`evaluate_candidate` boundary and therefore uses the isolated candidate
sandbox plus trusted oracle process.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sle.evaluate import INVALID_SCORE, evaluate_candidate
from sle.metric_visibility import search_visible_metrics, store_full_metrics
from sle.registry import find_task


TASK_ID = ""
TIMEOUT_S = 300.0
FULL_METRICS_DIR = ""


def configure(task_id: str, timeout_s: float, full_metrics_dir: str = "") -> None:
    global TASK_ID, TIMEOUT_S, FULL_METRICS_DIR
    TASK_ID = str(task_id)
    TIMEOUT_S = float(timeout_s)
    FULL_METRICS_DIR = str(full_metrics_dir or "")


def write_configured_wrapper(path: Path, task_id: str, timeout_s: float,
                             full_metrics_dir: Path | None = None) -> Path:
    """Write a per-run wrapper without credentials or mutable process-global routing."""
    repository = str(ROOT)
    source = (
        "import sys\n"
        "sys.path.insert(0, %r)\n"
        "from sle.upstream_evaluator import configure, evaluate, main, shinka_main\n"
        "configure(%r, %r, %r)\n"
        "if __name__ == '__main__':\n"
        "    raise SystemExit(main())\n"
    ) % (repository, str(task_id), float(timeout_s),
         str(Path(full_metrics_dir).resolve()) if full_metrics_dir else "")
    path = Path(path)
    path.write_text(source, encoding="utf-8")
    return path


def evaluate(program_path: str) -> dict[str, Any]:
    if not TASK_ID:
        raise RuntimeError("upstream evaluator is not configured")
    spec = find_task(TASK_ID, include_uncertified=True)
    sensitive = {}
    for key in tuple(os.environ):
        normalized = key.upper()
        if any(marker in normalized for marker in ("API_KEY", "AUTHORIZATION", "TOKEN")):
            sensitive[key] = os.environ.pop(key)
    try:
        candidate = Path(program_path).resolve()
        full_metrics = evaluate_candidate(spec, candidate, timeout_s=TIMEOUT_S)
        if FULL_METRICS_DIR:
            store_full_metrics(Path(FULL_METRICS_DIR), candidate, full_metrics)
        return search_visible_metrics(full_metrics)
    finally:
        os.environ.update(sensitive)


def shinka_main(program_path: str, results_dir: str) -> int:
    results = Path(results_dir).resolve()
    results.mkdir(parents=True, exist_ok=True)
    try:
        metrics = evaluate(program_path)
    except Exception as exc:  # noqa: BLE001 - serialize failures for Shinka
        metrics = {
            "combined_score": INVALID_SCORE,
            "valid": 0.0,
            "error_message": "%s: %s" % (type(exc).__name__, exc),
        }
    correct = float(metrics.get("valid", 0.0)) >= 1.0
    (results / "metrics.json").write_text(
        json.dumps(metrics, allow_nan=False, indent=2) + "\n", encoding="utf-8"
    )
    (results / "correct.json").write_text(
        json.dumps({"correct": correct, "error": metrics.get("error_message", "")}, indent=2)
        + "\n",
        encoding="utf-8",
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--program_path", required=True)
    parser.add_argument("--results_dir", required=True)
    args, _ = parser.parse_known_args(argv)
    return shinka_main(args.program_path, args.results_dir)


if __name__ == "__main__":
    raise SystemExit(main())

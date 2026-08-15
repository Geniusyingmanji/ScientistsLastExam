#!/usr/bin/env python3
"""Package a search run's trajectory as numerical-resolution evidence.

The resolution check asks one question: does the smallest score difference the searcher actually
resolved sit clear of the evaluator's own numerical noise? A benchmark whose steps are separated
by less than its noise floor is not measuring search, it is measuring rounding.

That question is answered against a *recorded trajectory*, and a trajectory is bound to the
evaluator that produced it. When an evaluator changes in a way that is not measurably inert, the
old trajectory stops being evidence about the current runtime and the only honest repair is to run
the search again. This packages that fresh run into the shape the check reads, with the same trust
envelope the other evidence carries, so a re-measurement is bound exactly as the original was.

It packages what the run produced and nothing else. It does not filter steps, and a run whose
scores never move produces evidence that says so - which is a finding about the task, not a
failure of this script.

Usage:
    python scripts/build_trajectory_resolution_evidence.py \
        --run runs/diffraction_resolution_2026-08-15_s1 \
        --output experiments/diffraction_trajectory_resolution_2026-08-15_v1.json
"""
from __future__ import annotations

import argparse
import datetime as _datetime
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sle.provenance import finalize_report_trust, source_provenance  # noqa: E402


def _events(run: Path) -> list[dict]:
    trajectory = run / "trajectory.jsonl"
    if not trajectory.is_file():
        raise SystemExit("no trajectory.jsonl in %s" % run)
    events = []
    for line in trajectory.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            events.append(json.loads(line))
    return events


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", type=Path, required=True, help="a completed run directory")
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args(argv)

    run = (ROOT / args.run).resolve() if not args.run.is_absolute() else args.run
    manifest_path = run / "run_manifest.json"
    if not manifest_path.is_file():
        raise SystemExit("%s has no run_manifest.json, so the run did not finish" % run)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    events = _events(run)

    scores = sorted({event["score"] for event in events
                     if event.get("valid") in {True, 1, 1.0} and event.get("score") is not None})
    gaps = [right - left for left, right in zip(scores, scores[1:]) if right > left]

    report = {
        "schema_version": 1,
        "purpose": "numerical-resolution evidence from a search run on the current runtime",
        "created_at": _datetime.datetime.now(_datetime.timezone.utc).isoformat(),
        "evidence_scope": "MODEL_PERFORMANCE",
        "runs": [{
            "task": manifest.get("task"),
            "seed": manifest.get("seed"),
            "algorithm": manifest.get("algorithm"),
            "feedback_mode": manifest.get("feedback_mode"),
            "budget": manifest.get("budget"),
            "workdir": run.relative_to(ROOT).as_posix() if run.is_relative_to(ROOT) else str(run),
            "trajectory_snapshot": {"events": events},
        }],
        "aggregate": {
            "event_count": len(events),
            "distinct_valid_scores": scores,
            "minimum_nonzero_score_gap": min(gaps) if gaps else None,
        },
        "source_provenance": source_provenance(ROOT),
    }
    # A run that finished with a manifest and produced at least one distinguishable pair of scores
    # is what this evidence claims. Anything less is recorded and marked untrusted rather than
    # quietly written as if it had measured something.
    finalize_report_trust(report, execution_passed=bool(gaps))
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print(json.dumps({
        "task": manifest.get("task"),
        "events": len(events),
        "distinct_valid_scores": len(scores),
        "minimum_nonzero_score_gap": min(gaps) if gaps else None,
        "trust_decision": report.get("trust_decision"),
    }, indent=2))
    print("wrote", args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Can a candidate crash the trusted evaluator?

It must not be able to. A candidate that raises, returns nonsense, or returns nothing is a
candidate that scores zero - it is not an infrastructure failure. The distinction is not
cosmetic: an infrastructure failure aborts the whole run, so one badly-shaped submission destroys
a whole cohort's evidence instead of earning a zero, and the operator is left with a report that
says a campaign failed rather than a proposal did.

That is not hypothetical. A 129-block paired sweep came back with four terminal failures on two
tasks, all reading `trusted evaluator internal failure` with no cause attached. The cause was a
`KeyError` inside the evaluator: the row it builds when scoring a world raises carries fewer keys
than the row it builds when scoring succeeds, and an aggregation added later read one of the
missing ones. Four runs died and the campaign's report was unusable.

The check is executable rather than structural. Comparing the key sets of the two branches by
reading the source flags dozens of tasks, nearly all of them harmless, because whether a missing
key matters depends on which list the aggregation walks. Running a candidate that fails and asking
what the evaluator does answers the question that is actually being asked.

Each task is given three candidates in turn:

    raises      the entrypoint raises immediately, on every world
    empty       it returns an empty dictionary
    wrong_type  it returns a string where a mapping is expected

Usage:
    python scripts/check_evaluator_survives_bad_candidates.py --output /tmp/survives.json
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sle.evaluate import evaluate_candidate  # noqa: E402
from sle.registry import list_tasks  # noqa: E402

BAD_CANDIDATES = {
    "raises": "def {entry}(*args, **kwargs):\n    raise RuntimeError('deliberate candidate failure')\n",
    "empty": "def {entry}(*args, **kwargs):\n    return {{}}\n",
    "wrong_type": "def {entry}(*args, **kwargs):\n    return 'not a mapping'\n",
}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", type=Path, default=None)
    ap.add_argument("--task", default=None, help="check one task instead of the inventory")
    ap.add_argument("--timeout", type=float, default=600.0)
    args = ap.parse_args(argv)

    specs = [spec for spec in list_tasks(None)
             if args.task is None or spec.task_id == args.task]
    if not specs:
        raise SystemExit("no such task: %s" % args.task)

    rows = []
    for spec in specs:
        for kind, template in BAD_CANDIDATES.items():
            source = template.format(entry=spec.entrypoint)
            with tempfile.TemporaryDirectory(prefix="badcand_") as temporary:
                candidate = Path(temporary) / "candidate.py"
                candidate.write_text(source, encoding="utf-8")
                try:
                    metrics = evaluate_candidate(spec, candidate, timeout_s=args.timeout)
                except Exception as error:  # noqa: BLE001 - reported per task, never fatal
                    rows.append({"task": spec.task_id, "candidate": kind,
                                 "crashed": True, "detail": str(error)[:300]})
                    continue
            crashed = bool(metrics.get("infrastructure_failure"))
            rows.append({
                "task": spec.task_id,
                "candidate": kind,
                "crashed": crashed,
                "valid": float(metrics.get("valid", 0.0)),
                "detail": str(metrics.get("error_message") or "")[:300] if crashed else "",
            })
            print("%-46s %-11s %s" % (
                spec.task_id[:46], kind,
                "CRASHED  %s" % rows[-1]["detail"][:90] if crashed else "scored invalid"))

    crashing = sorted({row["task"] for row in rows if row["crashed"]})
    print()
    print("tasks whose evaluator a candidate can crash: %d of %d" % (len(crashing), len(specs)))
    for task in crashing:
        print("   ", task)
    if crashing:
        print()
        print("A crash here aborts the run rather than scoring the candidate, so one bad "
              "submission costs a cohort its evidence.")

    if args.output:
        args.output.write_text(json.dumps({
            "schema_version": 1,
            "checked_task_count": len(specs),
            "crashing_tasks": crashing,
            "rows": rows,
        }, indent=2) + "\n", encoding="utf-8")
        print("report:", args.output)
    return 1 if crashing else 0


if __name__ == "__main__":
    raise SystemExit(main())

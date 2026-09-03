#!/usr/bin/env python3
"""Report how the inventory sits on the HLE-aligned exam surface.

    python scripts/report_exam_taxonomy.py
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sle.registry import list_tasks  # noqa: E402

TAXONOMY = ROOT / "sle" / "conf" / "exam_taxonomy.yaml"
ALLOWED_FORMS = {"optimization", "discovery"}


def load_taxonomy() -> dict:
    return yaml.safe_load(TAXONOMY.read_text(encoding="utf-8"))


def issues(taxonomy: dict | None = None) -> list[str]:
    tax = taxonomy or load_taxonomy()
    allowed_kinds = set((tax.get("discovery_kind") or {}).keys())
    allowed_analogues = set((tax.get("optimization_analogue") or {}).keys())
    listed = {spec.task_id: spec for spec in list_tasks(None)}
    mapped = tax.get("tasks") or {}
    found = []
    extra = sorted(set(mapped) - set(listed))
    missing = sorted(set(listed) - set(mapped))
    if extra:
        found.append("taxonomy names unknown tasks: " + ", ".join(extra))
    if missing:
        found.append("inventory tasks have no cell: " + ", ".join(missing))
    for task_id, row in mapped.items():
        spec = listed.get(task_id)
        if spec is None:
            continue
        form = row.get("form")
        if form not in ALLOWED_FORMS:
            found.append("%s: bad form %r" % (task_id, form))
        role = str(spec.metadata.get("scientific_role") or "")
        if form == "optimization" and role != "optimization":
            found.append("%s: form optimization but metadata scientific_role=%s" % (task_id, role))
        if form == "discovery" and role != "discovery":
            found.append("%s: form discovery but metadata scientific_role=%s" % (task_id, role))
        if form == "discovery" and row.get("kind") not in allowed_kinds:
            found.append("%s: bad discovery kind %r" % (task_id, row.get("kind")))
        if form == "optimization" and row.get("analogue") not in allowed_analogues:
            found.append("%s: bad optimization analogue %r" % (task_id, row.get("analogue")))
    return found


def summary(taxonomy: dict | None = None) -> dict:
    tax = taxonomy or load_taxonomy()
    forms = Counter()
    kinds = Counter()
    analogues = Counter()
    on_ramps = []
    for task_id, row in (tax.get("tasks") or {}).items():
        forms[row.get("form")] += 1
        if row.get("form") == "discovery":
            kinds[row.get("kind")] += 1
        else:
            analogues[row.get("analogue")] += 1
        if row.get("note") == "on_ramp_do_not_pair":
            on_ramps.append(task_id)
    return {
        "schema_version": tax.get("schema_version"),
        "scenario": tax.get("scenario"),
        "task_count": len(tax.get("tasks") or {}),
        "forms": dict(forms),
        "discovery_kinds": dict(kinds),
        "optimization_analogues": dict(analogues),
        "on_ramp_do_not_pair": on_ramps,
        "issues": issues(tax),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output")
    args = ap.parse_args()
    report = summary()
    print(json.dumps(report, indent=2))
    if args.output:
        Path(args.output).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return 1 if report["issues"] else 0


if __name__ == "__main__":
    raise SystemExit(main())

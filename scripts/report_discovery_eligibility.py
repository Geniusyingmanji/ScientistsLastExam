#!/usr/bin/env python3
"""List current discovery versions and enforced frontier eligibility decisions."""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sle.discovery_eligibility import discovery_eligibility  # noqa: E402
from sle.registry import find_task, list_tasks  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", help="optional logical ID or task name")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    specs = ([find_task(args.task, include_uncertified=True)] if args.task else list_tasks(None))
    rows = [discovery_eligibility(spec) for spec in specs
            if spec.metadata.get("scientific_role") == "discovery"]
    report = {"schema_version": 1, "task_count": len(rows),
              "status_counts": dict(Counter(row["status"] for row in rows)),
              "frontier_eligible_count": sum(row["frontier_eligible"] is True for row in rows),
              "note": "Executable historical scores do not establish frontier eligibility.",
              "rows": rows}
    rendered = json.dumps(report, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

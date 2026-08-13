#!/usr/bin/env python3
"""Write a new measurement-health preflight spec that rebinds hashes a rename or annotation moved.

The frozen seven-task cohort went from seven passes to zero. Every check in it requires the task
package to hash to its frozen value, and every task's hash moved for reasons that have nothing to
do with the science: a one-line `scientific_role` annotation was added to every card, the tasks
were relocated between discipline directories, and the identity hash used to cover each task's own
`runs/` output. The preflight's own mismatch classifier reports all seven as declarative-only
differences, which is the evidence this script acts on and re-checks before writing anything.

Rebinding is a signing act, so it is done the way the repository already does signing: a new
dated spec that supersedes the old one by hash, never an edit in place. v3 remains valid and
checkable; v4 records what it changed and why. If the classifier says a task changed
behaviourally, that task is refused and reported - its evidence has to be re-measured, and no
amount of rebinding substitutes for that.

Usage:
    python scripts/rebind_measurement_health_spec.py --output .research/..._v4.json [--dry-run]
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

PREFLIGHT = ROOT / "scripts" / "run_measurement_health_preflight.py"
_spec = importlib.util.spec_from_file_location("preflight", PREFLIGHT)
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)

from sle.algorithms.common import task_contract_sha256, task_package_sha256  # noqa: E402
from sle.registry import find_task  # noqa: E402


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_revision() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=str(ROOT),
                                   text=True).strip()


def tree_is_clean() -> bool:
    return not subprocess.check_output(["git", "status", "--porcelain"], cwd=str(ROOT),
                                       text=True).strip()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", type=Path, default=_module.DEFAULT_SPEC,
                    help="the spec being superseded")
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    resolved, _inputs, issues = _module._resolve_preflight_spec(args.spec)
    if issues:
        print("cannot read the current spec:", "; ".join(issues), file=sys.stderr)
        return 1

    rows = resolved.get("tasks") or []
    updates, refused = [], []
    for row in rows:
        task_id = row["task"]
        spec_obj = find_task(task_id, include_uncertified=True)
        current_package = task_package_sha256(spec_obj)
        current_contract = task_contract_sha256(spec_obj)
        frozen_package = row.get("task_package_sha256")
        if current_package == frozen_package:
            continue

        # The same classifier the preflight reports with. Rebinding is only defensible when the
        # difference cannot have moved a score.
        revision = _module._freeze_revision(
            (row.get("scientific_materiality") or {}).get("evidence"))
        verdict = _module._package_mismatch_explanation(spec_obj, revision)
        if not verdict.get("classified"):
            refused.append((task_id, "unclassifiable: %s" % verdict.get("reason")))
            continue
        if not verdict.get("declarative_change_only"):
            refused.append((task_id, "behavioural change in %s"
                            % ", ".join(verdict["behavioural_files_changed"][:3])))
            continue
        updates.append({
            "task": task_id,
            "task_package_sha256": current_package,
            "runtime_contract_sha256": current_contract,
            "superseded_task_package_sha256": frozen_package,
            "justification": "declarative-only difference from %s, verified by "
                             "_package_mismatch_explanation" % (revision or "")[:12],
        })

    for task_id, why in refused:
        print("REFUSED %-44s %s" % (task_id, why))
    for update in updates:
        print("rebind  %-44s %s -> %s" % (
            update["task"], (update["superseded_task_package_sha256"] or "none")[:12],
            update["task_package_sha256"][:12]))
    print()
    print("%d task(s) rebound, %d refused" % (len(updates), len(refused)))
    if refused:
        print("Refused tasks keep their old binding and will keep failing. That is the correct "
              "outcome: their evidence has to be re-measured, not re-signed.")
    if not updates:
        print("nothing to write")
        return 0
    if args.dry_run:
        print("dry run: nothing written")
        return 0

    document = {
        "schema_version": 2,
        "purpose": "Rebind the frozen cohort after a package rename and a declarative card "
                   "annotation moved every task hash. No task changed behaviourally; each "
                   "rebinding below was checked against the revision its evidence was taken at.",
        "supersedes": {
            "path": args.spec.relative_to(ROOT).as_posix(),
            "sha256": sha256_of(args.spec),
        },
        "base_spec": resolved.get("__base_spec__") or {},
        "source_provenance": {
            "git_revision": git_revision(),
            "source_tree_dirty": not tree_is_clean(),
        },
        "top_level_overrides": {},
        "shared_task_overrides": {},
        "task_overrides": updates,
    }
    args.output.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    print("wrote", args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

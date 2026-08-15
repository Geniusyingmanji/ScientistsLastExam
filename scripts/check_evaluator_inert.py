#!/usr/bin/env python3
"""Did an evaluator edit change what the frozen evidence measured, or only what it could measure?

A benchmark under active development keeps hitting the same wall. An evaluator is improved, the
task package hash moves, and every piece of frozen evidence bound to that task is refused - even
when the improvement provably cannot alter any number the evidence records. Removing an upper clip
at 1.0 is the case at hand: it changes what a *future* candidate can score and nothing a past one
did, because every recorded run scored at or below the cap.

Arguing that is not good enough. This measures it: the frozen fixed artifact is run through the
evaluator as it was at the freeze revision and as it is now, and the two metric dictionaries are
compared key by key. If they agree, the edit is inert for this evidence and the rebinding can say
so with a number behind it. If they do not, the evidence has to be re-measured and the tool says
which metric moved.

It cannot prove an edit inert in general - only that it did not move this artifact on this task,
which is exactly the claim the frozen evidence makes.

Usage:
    python scripts/check_evaluator_inert.py --revision <frozen sha> --output /tmp/inert.json
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sle.registry import list_tasks  # noqa: E402

PREFLIGHT = ROOT / "scripts" / "run_measurement_health_preflight.py"

# Metrics that legitimately differ between two runs of the same evaluator, so a difference in them
# says nothing about the edit.
VOLATILE = ("wall", "seconds", "elapsed", "timestamp", "duration")


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def historical_evaluator(revision: str, task_name: str, destination: Path):
    """Write the evaluator as it stood at a revision, found by name so a move does not hide it."""
    listing = subprocess.run(
        ["git", "ls-tree", "-r", "--name-only", revision, "--", "benchmarks"],
        cwd=str(ROOT), capture_output=True, text=True)
    marker = "/%s/verification/evaluator.py" % task_name
    for line in listing.stdout.splitlines():
        if line.endswith(marker):
            blob = subprocess.run(["git", "show", "%s:%s" % (revision, line)],
                                  cwd=str(ROOT), capture_output=True)
            if blob.returncode == 0:
                destination.write_bytes(blob.stdout)
                return line
    return None


def comparable(metrics) -> dict:
    return {k: v for k, v in metrics.items()
            if isinstance(v, (int, float, bool, str))
            and not any(word in k.lower() for word in VOLATILE)}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--revision", required=True, help="the freeze revision to compare against")
    ap.add_argument("--output", required=True)
    args = ap.parse_args(argv)

    preflight = load_module(PREFLIGHT, "preflight_for_inertness")
    resolved, _inputs, issues = preflight._resolve_preflight_spec(preflight.DEFAULT_SPEC)
    if issues:
        print("cannot read the preflight spec:", "; ".join(issues), file=sys.stderr)
        return 1

    specs = {spec.task_id: spec for spec in list_tasks(None)}
    rows = []
    for config in resolved.get("tasks") or []:
        task_id = config["task"]
        spec = specs.get(task_id)
        if spec is None:
            rows.append({"task": task_id, "status": "task not in the registry"})
            continue

        binding = (config.get("portable_artifact") or {}).get("evidence") or {}
        document, _audit = preflight._bound_document(binding)
        pointer = (config.get("portable_artifact") or {}).get("artifact_pointer")
        source = None
        if isinstance(document, dict) and isinstance(pointer, str):
            try:
                source = preflight._json_pointer(document, pointer).get("source")
            except (KeyError, IndexError, TypeError, ValueError):
                source = None
        if not isinstance(source, str):
            rows.append({"task": task_id, "status": "no frozen artifact to compare"})
            continue

        with tempfile.TemporaryDirectory(prefix="inert_") as temporary:
            root = Path(temporary)
            candidate = root / "candidate.py"
            candidate.write_text(source, encoding="utf-8")
            # Frozen artifacts import the helper modules that ship beside the task, so the task
            # directory has to be importable or the comparison fails on the import rather than on
            # the science. Removed again below so one task cannot shadow the next.
            sys.path.insert(0, str(spec.task_dir))
            old_path = root / "old_evaluator.py"
            found = historical_evaluator(args.revision, task_id.split("/")[-1], old_path)
            if found is None:
                rows.append({"task": task_id, "status": "no evaluator at that revision"})
                continue
            try:
                old = load_module(old_path, "old_%s" % task_id.split("/")[-1])
                new = load_module(spec.task_dir / "verification" / "evaluator.py",
                                  "new_%s" % task_id.split("/")[-1])
                entry = load_module(candidate, "frozen_candidate")
                callable_name = spec.entrypoint
                target = getattr(entry, callable_name, None)
                if target is None:
                    rows.append({"task": task_id, "status": "artifact has no %s" % callable_name})
                    continue
                before, after = comparable(old.evaluate(target)), comparable(new.evaluate(target))
            except Exception as error:  # noqa: BLE001 - reported per task, never fatal
                rows.append({"task": task_id, "status": "could not run: %s" % str(error)[:120]})
                continue
            finally:
                if sys.path and sys.path[0] == str(spec.task_dir):
                    sys.path.pop(0)

        moved = sorted(k for k in set(before) | set(after) if before.get(k) != after.get(k))
        rows.append({
            "task": task_id,
            "status": "inert" if not moved else "changed",
            "metrics_compared": len(set(before) | set(after)),
            "metrics_moved": moved,
        })

    inert = [r for r in rows if r["status"] == "inert"]
    changed = [r for r in rows if r["status"] == "changed"]
    unknown = [r for r in rows if r["status"] not in {"inert", "changed"}]

    for row in rows:
        print("%-46s %-8s %s" % (
            row["task"][:46], row["status"],
            ("%d metrics identical" % row["metrics_compared"]) if row["status"] == "inert"
            else (", ".join(row.get("metrics_moved", [])[:4]) if row["status"] == "changed"
                  else "")))
    print()
    print("inert: %d   changed: %d   undetermined: %d" % (len(inert), len(changed), len(unknown)))
    if changed:
        print("A changed metric means the frozen evidence measured something the edit moved. That")
        print("evidence has to be re-measured; no amount of rebinding substitutes for it.")
    if inert:
        print("An inert result means the edit moved nothing this evidence records. It is a claim")
        print("about this artifact on this task, which is what the evidence claims too.")

    Path(args.output).write_text(json.dumps({
        "schema_version": 1,
        "revision": args.revision,
        "note": "inertness is measured on the frozen artifact, not proved in general",
        "rows": rows,
    }, indent=2), encoding="utf-8")
    print()
    print("report:", args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

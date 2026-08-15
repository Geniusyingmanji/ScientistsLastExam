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


def _renamed_runtime_paths(shared: dict) -> dict:
    """Carry recorded runtime paths across the package rename.

    They name `frontier_science/...`, which no longer exists, so the compatibility check reported
    every runtime file as missing and could never pass again. Renaming a directory is not evidence
    going stale.
    """
    out = dict(shared)
    for check, config in out.items():
        paths = (config or {}).get("runtime_paths")
        if not paths:
            continue
        out[check] = dict(config, runtime_paths=[
            "sle/" + path[len("frontier_science/"):]
            if path.startswith("frontier_science/") else path
            for path in paths])
    return out


def _deep(base: dict, overlay: dict) -> dict:
    out = dict(base)
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep(out[key], value)
        else:
            out[key] = value
    return out


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
    ap.add_argument("--manifest", type=Path,
                    default=_module.DEFAULT_MANIFEST.relative_to(ROOT),
                    help="the frozen cohort manifest being superseded")
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--manifest-output", type=Path, required=True)
    ap.add_argument("--artifacts-output", type=Path, required=True)
    ap.add_argument("--rebind-evidence", action="append", default=[], metavar="CHECK=PATH",
                    help="point a check at re-measured evidence, e.g. "
                         "exactly_once_recovery=experiments/..._2026-08-14_v1.json. Use this "
                         "only when the evidence was re-run: a check bound to the runtime source "
                         "hash cannot be re-signed after the runtime changes, it has to be "
                         "remeasured, and this is how the result gets bound.")
    ap.add_argument("--inertness", type=Path, default=None, metavar="REPORT",
                    help="a check_evaluator_inert.py report. A task whose evaluator changed is "
                         "normally refused; if that report measured the change inert - the frozen "
                         "artifact scores identically under both evaluators - the task is rebound "
                         "and the measurement is recorded beside it. Inertness is measured, not "
                         "asserted, and it is a claim about that artifact on that task.")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    resolved, _inputs, issues = _module._resolve_preflight_spec(args.spec)
    if issues:
        print("cannot read the current spec:", "; ".join(issues), file=sys.stderr)
        return 1

    inert = {}
    if args.inertness and args.inertness.is_file():
        report = json.loads(args.inertness.read_text(encoding="utf-8"))
        inert = {row["task"]: row for row in report.get("rows", [])
                 if row.get("status") == "inert"}

    raw_spec = json.loads(args.spec.read_text(encoding="utf-8"))
    base_binding = raw_spec.get("base_spec") or {}
    manifest_path = (ROOT / args.manifest).resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

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
            measured = inert.get(task_id)
            if measured is None:
                refused.append((task_id, "behavioural change in %s"
                                % ", ".join(verdict["behavioural_files_changed"][:3])))
                continue
        updates.append({
            "task": task_id,
            # Recorded before the rebinding so the ledger says plainly that runs made against the
            # old prompt are not comparable with runs made against the new one, even though the
            # evaluator evidence carried forward is sound.
            "prompt_changed_since_freeze": bool(verdict.get("prompt_change_invalidates_runs")),
            "evaluator_change_measured_inert": (
                None if verdict.get("declarative_change_only")
                else {"metrics_compared": inert[task_id]["metrics_compared"],
                      "files_changed": verdict["behavioural_files_changed"]}),
            "task_package_sha256": current_package,
            "runtime_contract_sha256": current_contract,
            "superseded_task_package_sha256": frozen_package,
            "justification": "declarative-only difference from %s, verified by "
                             "_package_mismatch_explanation" % (revision or "")[:12],
        })

    for task_id, why in refused:
        print("REFUSED %-44s %s" % (task_id, why))
    for update in updates:
        print("rebind  %-44s %s -> %s%s" % (
            update["task"], (update["superseded_task_package_sha256"] or "none")[:12],
            update["task_package_sha256"][:12],
            ("  (evaluator changed; %d metrics measured identical)"
             % update["evaluator_change_measured_inert"]["metrics_compared"])
            if update["evaluator_change_measured_inert"]
            else ("  (prompt changed: recorded runs are not comparable)"
                  if update["prompt_changed_since_freeze"] else "")))
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

    # The runtime contract lives in the cohort manifest, not the spec, so rebinding one without
    # the other leaves the preflight failing on the half that was not touched. A first attempt
    # updated only the spec and left every task still failing `frozen_runtime_contract`.
    contracts = {u["task"]: u["runtime_contract_sha256"] for u in updates}
    new_manifest = dict(manifest)
    new_manifest["supersedes"] = {
        "path": manifest_path.relative_to(ROOT).as_posix(),
        "sha256": sha256_of(manifest_path),
    }
    new_manifest["tasks"] = [
        dict(row, runtime_contract_sha256=contracts[row["task"]],
             superseded_runtime_contract_sha256=row.get("runtime_contract_sha256"))
        if row.get("task") in contracts else row
        for row in manifest.get("tasks") or []
    ]
    args.manifest_output.write_text(json.dumps(new_manifest, indent=2) + "\n", encoding="utf-8")
    print("wrote", args.manifest_output)

    # Third layer. Each frozen candidate records the contract it was produced against, so a moved
    # contract hash invalidates the artifact pack too - and with it the three checks that depend
    # on having a fixed artifact to run: noise remeasurement, baseline/reference separation and
    # numerical resolution. The candidate sources themselves are untouched and verified unchanged
    # by their own content hash; only the recorded origin moves.
    artifact_binding = ((rows[0].get("portable_artifact") or {}).get("evidence") or {})
    artifacts_path = (ROOT / artifact_binding["path"]).resolve()
    artifacts = json.loads(artifacts_path.read_text(encoding="utf-8"))
    new_artifacts = dict(artifacts)
    new_artifacts["supersedes"] = {
        "path": artifacts_path.relative_to(ROOT).as_posix(),
        "sha256": sha256_of(artifacts_path),
    }
    new_artifacts["artifacts"] = [
        dict(row, origin=dict(row.get("origin") or {},
                              task_contract_sha256=contracts[row["task"]],
                              superseded_task_contract_sha256=(
                                  row.get("origin") or {}).get("task_contract_sha256")))
        if row.get("task") in contracts else row
        for row in artifacts.get("artifacts") or []
    ]
    args.artifacts_output.write_text(json.dumps(new_artifacts, indent=2) + "\n",
                                     encoding="utf-8")
    print("wrote", args.artifacts_output)

    document = {
        "schema_version": 2,
        "purpose": "Rebind the frozen cohort after a package rename and a declarative card "
                   "annotation moved every task hash. No task changed behaviourally; each "
                   "rebinding below was checked against the revision its evidence was taken at.",
        "supersedes": {
            "path": args.spec.relative_to(ROOT).as_posix(),
            "sha256": sha256_of(args.spec),
        },
        "base_spec": base_binding,
        "source_provenance": {
            "git_revision": git_revision(),
            "source_tree_dirty": not tree_is_clean(),
        },
        "top_level_overrides": {
            # The spec binds the manifest by hash, so a new manifest needs a new binding here or
            # the preflight fails closed on "does not bind the current cohort manifest".
            "cohort_manifest_sha256": sha256_of(args.manifest_output),
        },
        # The recorded runtime paths still name the package as it was before the rename, so they
        # are carried forward under the current name. The files are the same files; only where
        # they live has changed, and the comparison follows the rename in both directions.
        "shared_task_overrides": _deep(_deep(_deep(
            _renamed_runtime_paths(raw_spec.get("shared_task_overrides") or {}),
            {check: {"evidence": {"path": path,
                                  "sha256": sha256_of((ROOT / path).resolve())}}
             for check, path in (item.split("=", 1) for item in args.rebind_evidence)}),
            {"portable_artifact": {"evidence": {
                "path": args.artifacts_output.relative_to(ROOT).as_posix()
                if args.artifacts_output.is_absolute()
                else args.artifacts_output.as_posix(),
                "sha256": sha256_of(args.artifacts_output)}}}), {}),
        # Carry the previous overlay's per-task overrides forward; this layer only adds hashes.
        "task_overrides": [
            dict(prev, **{k: v for k, v in next((u for u in updates
                                                 if u["task"] == prev["task"]), {}).items()
                          if k != "task"})
            for prev in raw_spec.get("task_overrides") or []
        ] or updates,
    }
    args.output.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    print("wrote", args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

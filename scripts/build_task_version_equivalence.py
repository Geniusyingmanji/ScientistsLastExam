#!/usr/bin/env python3
"""Work out which recorded task versions are the same task, and write the equivalence down.

Runs record `task_package_sha256`, and the reports refuse to compare two runs whose hashes differ,
because comparing across a task edit reports the edit as a model difference. That guard is right
and it is also, as written, far too strict.

The package hash covers every file in the task directory, including `frontier_eval/metadata.yaml`.
One commit in this repository - "declare scientific_role on all 61 tasks" - added a single
declarative line to that file for every task, and moved every task's hash. Twenty tasks then
carried two versions across cohorts, and the reports stopped comparing across them. Seventeen of
those twenty differ by nothing but that one annotation: no evaluator change, no Task.md change,
no data change. Three were really edited.

So the guard was discarding valid evidence on seventeen tasks, including every task that Claude
and gpt-5.6-sol have in common. The narrower `task_contract_sha256` is no help - `metadata.yaml`
is inside it too, and it omits the reference implementations that several tasks score against.

This resolves it from the history rather than by loosening the rule. Every revision that touched
a task is replayed, its package hash computed from the git objects, and the hashes observed in
run manifests are matched to the revisions that produced them. Two versions are declared the same
task when the only difference between their revisions is a declarative key in metadata.yaml -
which is a diff this script has read, not an assumption.

The output is a table the reports load, in the same spirit as llm_conditions.yaml: a fact
recovered once, written down, and auditable, rather than re-derived by guesswork at each use.

Usage:
    python scripts/build_task_version_equivalence.py --runs runs \\
        --output frontier_science/task_versions.yaml
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import yaml  # noqa: E402

# Keys in frontier_eval/metadata.yaml that describe a task without changing what it computes.
# A difference confined to these does not make two runs incomparable. Anything else does,
# including any key not listed here: the default is to treat a change as meaningful.
DECLARATIVE_KEYS = {"scientific_role", "score_mode", "domain_reviewed", "maturity",
                    "difficulty_level", "notes", "description", "tags"}

SKIP_SUFFIXES = {".pyc", ".pyo"}


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True,
                          check=True).stdout


def tree_files(revision: str, task_name: str) -> dict[str, str]:
    """Relative path -> blob id, for the task directory as it stood at a revision.

    Located by name rather than by today's path. Tasks were moved between domain directories
    during a layout change, and `git log -- <current path>` does not follow a directory rename,
    so replaying only the current path found no revision at all for eleven tasks - reported as
    "no revision reproduces this hash" when the revisions were there under another name.
    """
    out = {}
    listing = git("ls-tree", "-r", revision, "--", "benchmarks")
    marker = "/%s/" % task_name
    root = None
    for line in listing.splitlines():
        if not line.strip():
            continue
        meta, path = line.split("\t", 1)
        _mode, kind, blob = meta.split()
        if kind != "blob" or marker not in path:
            continue
        if root is None:
            root = path[:path.index(marker) + len(marker) - 1]
        relative = Path(path).relative_to(root).as_posix()
        if "__pycache__" in Path(relative).parts or Path(relative).suffix in SKIP_SUFFIXES:
            continue
        out[relative] = blob
    return out


def blob(blob_id: str) -> bytes:
    return subprocess.run(["git", "cat-file", "blob", blob_id], cwd=ROOT,
                          capture_output=True, check=True).stdout


def package_hash(files: dict[str, str]) -> str:
    """Reproduce task_package_sha256 from git objects, without checking anything out."""
    digest = hashlib.sha256()
    for relative in sorted(files):
        digest.update(relative.encode("utf-8") + b"\0")
        digest.update(blob(files[relative]) + b"\0")
    return digest.hexdigest()


def declarative_only(before: dict[str, str], after: dict[str, str]) -> bool:
    """Is the whole difference between two task trees a declarative annotation?"""
    changed = {p for p in set(before) | set(after) if before.get(p) != after.get(p)}
    if not changed:
        return True
    if changed != {"frontier_eval/metadata.yaml"}:
        return False
    try:
        old = yaml.safe_load(blob(before["frontier_eval/metadata.yaml"]).decode("utf-8")) or {}
        new = yaml.safe_load(blob(after["frontier_eval/metadata.yaml"]).decode("utf-8")) or {}
    except (KeyError, yaml.YAMLError, UnicodeDecodeError):
        return False
    differing = {k for k in set(old) | set(new) if old.get(k) != new.get(k)}
    # Empty is possible when only formatting moved; that is declarative too.
    return differing <= DECLARATIVE_KEYS


def observed_versions(runs_root: Path) -> dict[str, set[str]]:
    out: dict[str, set[str]] = defaultdict(set)
    for manifest in runs_root.glob("*/*/run_manifest.json"):
        try:
            document = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        task, version = document.get("task_id"), document.get("task_package_sha256")
        if task and version:
            out[str(task)].add(str(version))
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args(argv)

    from frontier_science.registry import list_tasks

    directories = {spec.task_id: spec.task_dir.relative_to(ROOT).as_posix()
                   for spec in list_tasks(None)}
    observed = observed_versions(Path(args.runs))

    table, unresolved = {}, []
    for task, versions in sorted(observed.items()):
        if len(versions) < 2:
            continue
        task_dir = directories.get(task)
        if task_dir is None:
            unresolved.append((task, "not in the registry"))
            continue

        # Replay every revision that touched this task and hash it as the runner would have.
        task_name = task.split("/")[-1]
        revisions = git("log", "--format=%H", "--",
                        ":(glob)benchmarks/**/%s/**" % task_name).split()
        by_hash: dict[str, tuple[str, dict[str, str]]] = {}
        for revision in revisions:
            files = tree_files(revision, task_name)
            if not files:
                continue
            digest = package_hash(files)
            by_hash.setdefault(digest, (revision, files))

        found = {v: by_hash[v] for v in versions if v in by_hash}
        missing = sorted(v[:12] for v in versions if v not in by_hash)
        if missing:
            # A hash no revision reproduces means the run was made against an uncommitted tree.
            # Reported, never guessed at.
            unresolved.append((task, "no revision reproduces " + ", ".join(missing)))
        if len(found) < 2:
            continue

        # Group into classes: same class when the diff is declarative only.
        classes: list[list[str]] = []
        for version, (_rev, files) in sorted(found.items()):
            for group in classes:
                _r, representative = found[group[0]]
                if declarative_only(representative, files):
                    group.append(version)
                    break
            else:
                classes.append([version])

        table[task] = {
            "classes": [
                {"id": "%s-%d" % (task.split("/")[-1], index),
                 "versions": sorted(group),
                 "revision": found[group[0]][0]}
                for index, group in enumerate(classes)
            ],
        }
        label = ("all %d versions are the same task" % len(found) if len(classes) == 1
                 else "%d genuinely different versions" % len(classes))
        print("%-34s %s" % (task.split("/")[-1][:34], label))

    if unresolved:
        print()
        print("could not be resolved from history:")
        for task, why in unresolved:
            print("  %-32s %s" % (task.split("/")[-1][:32], why))

    same = sum(1 for entry in table.values() if len(entry["classes"]) == 1)
    print()
    print("tasks recorded under more than one hash: %d" % len(table))
    print("  of those, the same task throughout: %d" % same)
    print("  genuinely edited between runs: %d" % (len(table) - same))

    Path(args.output).write_text(
        "# Generated by scripts/build_task_version_equivalence.py - do not hand-edit.\n"
        "#\n"
        "# Which recorded task_package_sha256 values are the same task. A declarative line added\n"
        "# to every task's metadata.yaml moved every hash without changing any task, and the\n"
        "# comparability guard in the reports was discarding valid evidence as a result. Each\n"
        "# class below was established by diffing the git revisions that produce those hashes.\n"
        + yaml.safe_dump({"tasks": table}, sort_keys=True, allow_unicode=True),
        encoding="utf-8")
    print()
    print("table:", args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Regenerate the three frozen global evidence documents and repoint the audits at them.

The task-maturity audit compares frozen documents against the live inventory, and anything that
moves the inventory or the trusted runtime - a new task, a changed evaluator, an edit to
`sle/secure_eval.py` - leaves those documents describing a repository that no longer exists.
The audit then reports `internal admission count diverges` or drops tasks to
`historical_only`, which reads as a governance problem and is bookkeeping.

The repair is always the same three steps in the same order, from a clean revision, followed by
editing two pointer constants. Done by hand it was done five times in two days, once with a stale
pointer left behind. This is that procedure as one command:

    1. scripts/audit_tasks.py            -> experiments/task_certification_audit_<date>_v<N>.json
    2. scripts/run_secure_baseline.py    -> experiments/secure_baseline_determinism_<date>_v<N>.json
    3. rewrite GLOBAL_REPORTS in scripts/audit_task_maturity.py, then
       scripts/audit_task_maturity.py    -> experiments/task_maturity_audit_<date>_v<N>.json
    4. rewrite DEFAULT_MATURITY in scripts/audit_measurement_health.py

Step 2 needs the candidate sandbox, so this runs on the benchmark host, not a laptop. Steps 3
and 4 edit tracked files; the maturity document produced in step 3 therefore records a dirty
tree unless `--commit` is given, which commits the two pointer edits and the two new documents
before step 3 so that every document in the set is `trusted_clean_revision`.

Version numbers continue each document's own series (the highest existing v<N> plus one), so
the three series stay independent as they always have.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENTS = ROOT / "experiments"

SERIES = {
    "certification": "task_certification_audit",
    "secure_baseline": "secure_baseline_determinism",
    "maturity": "task_maturity_audit",
}
POINTERS = {
    # (file, regex capturing the current path, key in SERIES)
    "certification": (ROOT / "scripts/audit_task_maturity.py",
                      r'"certification": "(experiments/task_certification_audit_[^"]+\.json)"'),
    "secure_baseline": (ROOT / "scripts/audit_task_maturity.py",
                        r'"secure_baseline": "(experiments/secure_baseline_determinism_[^"]+\.json)"'),
    "maturity": (ROOT / "scripts/audit_measurement_health.py",
                 r'DEFAULT_MATURITY = ROOT / "(experiments/task_maturity_audit_[^"]+\.json)"'),
}


def _git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def _tree_is_clean() -> bool:
    return _git("status", "--porcelain", "--untracked-files=no") == ""


def _next_version(stem: str) -> int:
    highest = 0
    for path in EXPERIMENTS.glob(stem + "_*_v*.json"):
        match = re.search(r"_v(\d+)\.json$", path.name)
        if match:
            highest = max(highest, int(match.group(1)))
    return highest + 1


def _target(stem: str, today: str) -> Path:
    return EXPERIMENTS / ("%s_%s_v%d.json" % (stem, today, _next_version(stem)))


def _run(argv: list[str]) -> None:
    print("+ " + " ".join(argv), flush=True)
    subprocess.run(argv, cwd=ROOT, check=True)


def _repoint(key: str, new_path: Path) -> str:
    file, pattern = POINTERS[key]
    text = file.read_text(encoding="utf-8")
    match = re.search(pattern, text)
    if not match:
        raise SystemExit("pointer for %s not found in %s" % (key, file))
    old = match.group(1)
    rel = str(new_path.relative_to(ROOT))
    file.write_text(text.replace(old, rel), encoding="utf-8")
    print("pointer %s: %s -> %s" % (key, old, rel))
    return old


def _summary(path: Path, keys: tuple[str, ...]) -> str:
    document = json.loads(path.read_text(encoding="utf-8"))
    return ", ".join("%s=%s" % (k, document.get(k)) for k in keys if k in document)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--repeats", type=int, default=2, help="secure-baseline repeats")
    parser.add_argument("--timeout", type=float, default=180.0, help="per-task baseline timeout")
    parser.add_argument("--commit", action="store_true",
                        help="commit pointer edits and new documents so the maturity document "
                             "is produced from a clean revision")
    parser.add_argument("--skip-baseline", action="store_true",
                        help="reuse the newest secure-baseline document (no sandbox on this host)")
    args = parser.parse_args()

    if not _tree_is_clean():
        raise SystemExit("working tree has uncommitted tracked changes; evidence produced now "
                         "would record source_tree_dirty_or_unknown. Commit or stash first.")
    today = dt.date.today().isoformat()

    cert = _target(SERIES["certification"], today)
    _run([sys.executable, "scripts/audit_tasks.py", "--output", str(cert)])
    print("  certification:", _summary(cert, ("passed", "trust_decision", "task_card_passed_count")))

    if args.skip_baseline:
        baseline = max(EXPERIMENTS.glob(SERIES["secure_baseline"] + "_*_v*.json"),
                       key=lambda p: int(re.search(r"_v(\d+)\.json$", p.name).group(1)))
        print("  secure baseline: reusing", baseline.name)
    else:
        baseline = _target(SERIES["secure_baseline"], today)
        _run([sys.executable, "scripts/run_secure_baseline.py", "--output", str(baseline),
              "--repeats", str(args.repeats), "--timeout", str(args.timeout)])
        print("  secure baseline:", _summary(baseline, ("passed", "trust_decision")))
        summary = json.loads(baseline.read_text(encoding="utf-8")).get("summary", {})
        print("  ", json.dumps(summary))

    old_cert = _repoint("certification", cert)
    old_base = _repoint("secure_baseline", baseline)

    maturity = _target(SERIES["maturity"], today)
    if args.commit:
        _run(["git", "add", str(cert), str(baseline), str(POINTERS["certification"][0])])
        _run(["git", "commit", "-q", "-m",
              "refresh certification and secure-baseline evidence (%s)\n\n"
              "Regenerated from a clean revision. Pointers: %s -> %s; %s -> %s."
              % (today, Path(old_cert).name, cert.name, Path(old_base).name, baseline.name)])
    _run([sys.executable, "scripts/audit_task_maturity.py", "--output", str(maturity)])
    print("  maturity:", _summary(maturity, ("passed", "trust_decision", "inventory_count", "issues")))
    document = json.loads(maturity.read_text(encoding="utf-8"))
    print("  gate_counts:", json.dumps(document.get("gate_counts")))
    blocked = [(row["task"], row["gates"]["internal_science_admission"].get("blockers"))
               for row in document.get("tasks", [])
               if not row["gates"]["internal_science_admission"]["passed"]]
    if blocked:
        print("  tasks not admitted (%d):" % len(blocked))
        for task, blockers in blocked:
            print("    ", task, blockers)

    old_mat = _repoint("maturity", maturity)
    if args.commit:
        _run(["git", "add", str(maturity), str(POINTERS["maturity"][0])])
        _run(["git", "commit", "-q", "-m",
              "freeze maturity inventory (%s)\n\nPointer: %s -> %s. inventory=%s admission=%s"
              % (today, Path(old_mat).name, maturity.name, document.get("inventory_count"),
                 (document.get("gate_counts") or {}).get("internal_science_admission"))])
        print("committed; run the audit tests before pushing")
    else:
        print("pointers edited but not committed; the maturity document above records a dirty "
              "tree. Re-run with --commit for a fully clean set.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Batch task generator for Frontier-Science.

Creates the full directory structure + contract files for a task from a compact spec dict.
Usage:
    from scripts.gen_task import create_task
    create_task({
        "domain": "Physics",
        "task": "HarmonicOscillatorControl",
        "difficulty": "hard",        # unmeasured | hard | flagship
        "tier": "T2",                # candidate | T2 | T3
        "oracle_type": "physical_sim",
        "score_mode": "clipped",
        "eval_time_seconds": 5,
        "science_metric": "...",
        "reference_baseline": "...",
        "reference_sota": "...",
        "citation": "...",
        "entrypoint": "solve",         # function name agent must implement
        "task_md": "...",              # full Task.md content
        "baseline_code": "...",        # full solution.py content
        "evaluator_code": "...",       # full verification/evaluator.py content
        "constraints": "...",          # constraints.txt content
    })
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from sle.benchmark_layout import discipline_for_domain  # noqa: E402

DEFAULT_EVAL_TIME_SECONDS = 100

RUN_EVAL_TEMPLATE = '''"""Launch the shared trusted evaluator without importing project code."""
import argparse
import math
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
TASK_ID = {task_id!r}
EVAL_TIMEOUT_S = {eval_timeout!r}


# The task id is written in, where the previous template derived everything from __file__.
# That is deliberate - `sle eval` needs the registered id, not a path - but it means a wrapper
# copied to a neighbouring task keeps pointing at the task it came from, and scores the new
# candidate against the old oracle without complaining. The directory name is the second half
# of the id, so the copy is cheap to catch here rather than in whoever reads the numbers.
_expected_task = Path(__file__).resolve().parents[1].name
if TASK_ID.split("/")[-1] != _expected_task:
    raise SystemExit(
        "TASK_ID %r does not name this directory (%r); this wrapper was copied from another"
        " task and would score against that task's oracle" % (TASK_ID, _expected_task))


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--metrics-out", required=True)
    parser.add_argument("--timeout", type=float, default=EVAL_TIMEOUT_S)
    parser.add_argument("--full-metrics-dir")
    args = parser.parse_args(argv)
    command = [sys.executable, str(ROOT / "sle/frontier_eval_entrypoint.py"),
               "--task", TASK_ID, "--root", str(ROOT), "--timeout", str(args.timeout),
               "--candidate", args.candidate, "--metrics-out", args.metrics_out]
    if args.full_metrics_dir:
        command.extend(["--full-metrics-dir", args.full_metrics_dir])
    try:
        Path(args.metrics_out).unlink(missing_ok=True)
        if not math.isfinite(args.timeout) or args.timeout <= 0:
            print("evaluation timeout must be positive and finite", file=sys.stderr)
            return 2
        result = subprocess.run(command, capture_output=True, text=True, timeout=args.timeout + 150)
        if result.returncode:
            Path(args.metrics_out).unlink(missing_ok=True)
            print("evaluation entrypoint unavailable or infrastructure failure (exit %d)"
                  % result.returncode, file=sys.stderr)
            return 2
        print(result.stdout, end="")
        return 0
    except (OSError, subprocess.TimeoutExpired):
        try:
            Path(args.metrics_out).unlink(missing_ok=True)
        except OSError:
            pass
        print("evaluation entrypoint could not be launched or report cleared", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
'''

METADATA_TEMPLATE = """domain: {domain}
task: {task}
difficulty: {difficulty}
tier: {tier}
oracle_type: {oracle_type}
score_mode: {score_mode}
gpu_required: false
eval_time_seconds: {eval_time_seconds}
science_metric: {science_metric}
reference_baseline: "{reference_baseline}"
reference_sota: "{reference_sota}"
citation: "{citation}"
"""


def create_task(spec: dict, repo: Path = REPO) -> Path:
    domain = spec["domain"]
    task = spec["task"]
    difficulty = str(spec.get("difficulty", "")).strip().lower()
    if difficulty not in {"unmeasured", "hard", "flagship"}:
        raise ValueError("difficulty must be unmeasured, hard or flagship")
    default_tier = {"unmeasured": "candidate", "hard": "T2", "flagship": "T3"}[difficulty]
    tier = str(spec.get("tier", default_tier)).strip()
    if tier not in {"candidate", "T2", "T3"}:
        raise ValueError("tier must be candidate, T2 or T3")
    spec = {**spec, "difficulty": difficulty, "tier": tier}
    discipline = discipline_for_domain(domain)
    requested_discipline = spec.get("discipline")
    if requested_discipline not in {None, discipline}:
        raise ValueError(
            "Domain %r belongs to discipline %r, not %r."
            % (domain, discipline, requested_discipline)
        )
    task_dir = repo / "benchmarks" / discipline / task
    eval_dir = task_dir / "frontier_eval"
    ver_dir = task_dir / "verification"

    for d in [eval_dir, ver_dir]:
        d.mkdir(parents=True, exist_ok=True)

    # Task.md
    (task_dir / "Task.md").write_text(spec["task_md"], encoding="utf-8")

    # solution.py
    (task_dir / "solution.py").write_text(spec["baseline_code"], encoding="utf-8")

    # verification/evaluator.py
    (ver_dir / "evaluator.py").write_text(spec["evaluator_code"], encoding="utf-8")

    # frontier_eval contract files
    entrypoint = spec.get("entrypoint", "solve")
    # These are deliberately pending candidate programs, not trusted-oracle scripts.
    # A task author must replace and calibrate both through the candidate sandbox.
    if not str(entrypoint).isidentifier():
        raise ValueError("entrypoint must be a Python identifier")
    for name, purpose in (("reference_solver.py", "reference"), ("shortcut_probe.py", "cheap legitimate")):
        (ver_dir / name).write_text(
            '"""Pending %s candidate; implement the task submission contract."""\n'
            'def %s(*args, **kwargs):\n'
            '    raise NotImplementedError("replace with a %s candidate; calibrate before admission")\n'
            % (purpose, entrypoint, purpose), encoding="utf-8")
    (task_dir / "TASK_CARD.yaml").write_text(
        "# Complete the scientific task card before admission. These unmeasured values are pending.\n"
        "# The margin below is a review starting point, not a universal scientific threshold.\n"
        "shortcut_probe:\n"
        "  schema_version: 1\n"
        "  metric: combined_score\n"
        "  reference:\n"
        "    candidate: verification/reference_solver.py\n"
        "    expected_score: null\n"
        "  probes:\n"
        "    - id: cheap_probe\n"
        "      candidate: verification/shortcut_probe.py\n"
        "      expected_score: null\n"
        "  relative_margin: 0.1\n"
        "  score_tolerance: 0.000001\n", encoding="utf-8")
    # The wrapper timeout is a review quantity set by how hard the task is, so a spec may name
    # it outright. The fallback reproduces what the 66 existing wrappers already do (64 of them
    # exactly): three times the expected evaluation, floored at the repository's usual 300 s.
    # `eval_time_seconds` is defaulted once, here, so metadata.yaml and run_eval.py cannot
    # disagree about it - an earlier draft let one fall back to empty and the other to 300.
    eval_time_seconds = int(spec.get("eval_time_seconds") or DEFAULT_EVAL_TIME_SECONDS)
    spec = {**spec, "eval_time_seconds": eval_time_seconds}
    eval_timeout = int(spec.get("eval_timeout_s")
                       or max(300, 3 * eval_time_seconds))
    (eval_dir / "run_eval.py").write_text(
        RUN_EVAL_TEMPLATE.format(
            task=task, task_id="%s/%s" % (domain, task),
            eval_timeout=eval_timeout,
        ), encoding="utf-8")
    (eval_dir / "metadata.yaml").write_text(
        METADATA_TEMPLATE.format(**{k: spec.get(k, "") for k in
            ["domain","task","difficulty","tier","oracle_type","score_mode",
             "eval_time_seconds","science_metric","reference_baseline",
             "reference_sota","citation"]}), encoding="utf-8")
    (eval_dir / "initial_program.txt").write_text("solution.py\n", encoding="utf-8")
    (eval_dir / "candidate_destination.txt").write_text("solution.py\n", encoding="utf-8")
    (eval_dir / "entrypoint.txt").write_text(entrypoint + "\n", encoding="utf-8")
    (eval_dir / "eval_command.txt").write_text(
        "{python} frontier_eval/run_eval.py --candidate {candidate} --metrics-out {metrics}\n",
        encoding="utf-8")
    (eval_dir / "constraints.txt").write_text(
        spec.get("constraints", f"1) Only edit solution.py. Keep the {entrypoint}() signature.\n"
                 "2) numpy/scipy/stdlib only. CPU, seconds. No network.\n"
                 "3) Do not read verification/ or frontier_eval/.\n"),
        encoding="utf-8")
    (eval_dir / "agent_files.txt").write_text(
        "Task.md\nsolution.py\nfrontier_eval/constraints.txt\n", encoding="utf-8")
    (eval_dir / "readonly_files.txt").write_text(
        "Task.md\nverification\nfrontier_eval\n", encoding="utf-8")

    return task_dir


if __name__ == "__main__":
    print("Import and call create_task(spec_dict) to generate a task.")

#!/usr/bin/env python3
"""Batch task generator for Frontier-Science.

Creates the full directory structure + contract files for a task from a compact spec dict.
Usage:
    from scripts.gen_task import create_task
    create_task({
        "domain": "Physics",
        "task": "HarmonicOscillatorControl",
        "difficulty": "hard",        # hard | flagship only
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

RUN_EVAL_TEMPLATE = '''"""Launch the shared trusted evaluator without importing project code."""
import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
TASK_ID = {task_id!r}
EVAL_TIMEOUT_S = {timeout!r}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--metrics-out", required=True)
    parser.add_argument("--timeout", type=float, default=EVAL_TIMEOUT_S)
    parser.add_argument("--full-metrics-dir")
    args = parser.parse_args()
    command = [sys.executable, str(ROOT / "sle/frontier_eval_entrypoint.py"),
               "--task", TASK_ID, "--root", str(ROOT), "--timeout", str(args.timeout),
               "--candidate", args.candidate, "--metrics-out", args.metrics_out]
    if args.full_metrics_dir:
        command.extend(["--full-metrics-dir", args.full_metrics_dir])
    try:
        Path(args.metrics_out).unlink(missing_ok=True)
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode:
            print("evaluation entrypoint unavailable or infrastructure failure (exit %d)"
                  % result.returncode, file=sys.stderr)
            return 2
        print(result.stdout, end="")
        return 0
    except OSError:
        print("evaluation entrypoint could not be launched or report cleared", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
'''

METADATA_TEMPLATE = """domain: {domain}
task: {task}
difficulty: {difficulty}
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
    if difficulty not in {"hard", "flagship"}:
        raise ValueError(
            "Frontier-Science tasks must be PhD/expert difficulty: "
            "set difficulty to 'hard' or 'flagship'."
        )
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
    (eval_dir / "run_eval.py").write_text(
        RUN_EVAL_TEMPLATE.format(task_id=domain + "/" + task, timeout=float(spec["eval_time_seconds"])), encoding="utf-8")
    (eval_dir / "metadata.yaml").write_text(
        METADATA_TEMPLATE.format(**{k: spec.get(k, "") for k in
            ["domain","task","difficulty","oracle_type","score_mode",
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

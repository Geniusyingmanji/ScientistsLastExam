#!/usr/bin/env python3
"""Batch task generator for Frontier-Science.

Creates the full directory structure + contract files for a task from a compact spec dict.
Usage:
    from scripts.gen_task import create_task
    create_task({
        "domain": "Physics",
        "task": "HarmonicOscillatorControl",
        "difficulty": "hard",        # on_ramp | uncalibrated_candidate | unmeasured | hard | flagship
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

RUN_EVAL_TEMPLATE = '''from __future__ import annotations
import argparse, importlib.util, json, sys
from pathlib import Path
INVALID = -1e18; TASK_DIR = Path(__file__).resolve().parent.parent
def _load(p, n):
    s=importlib.util.spec_from_file_location("c",p); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); return getattr(m,n)
def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--candidate",required=True); ap.add_argument("--metrics-out",required=True); args=ap.parse_args()
    metrics={{"combined_score":INVALID,"valid":0.0}}
    try:
        sys.path.insert(0,str(TASK_DIR/"verification")); import evaluator as o
        f=_load(Path(args.candidate).resolve(),"{entrypoint}"); r=o.evaluate(f); metrics.update(r); metrics["raw_score"]=r.get("combined_score")
    except Exception as e: metrics["error_message"]=f"{{type(e).__name__}}: {{e}}"
    Path(args.metrics_out).write_text(json.dumps(metrics,indent=2,default=str)); print(json.dumps({{k:metrics.get(k) for k in ("combined_score","valid")}})); return 0
if __name__=="__main__": raise SystemExit(main())
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
    if difficulty not in {
        "on_ramp", "uncalibrated_candidate", "unmeasured", "hard", "flagship",
    }:
        raise ValueError(
            "difficulty must be on_ramp, uncalibrated_candidate, unmeasured, hard or flagship"
        )
    default_tier = {
        "on_ramp": "candidate",
        "uncalibrated_candidate": "candidate",
        "unmeasured": "candidate",
        "hard": "T2",
        "flagship": "T3",
    }[difficulty]
    tier = str(spec.get("tier", default_tier)).strip()
    if tier not in {"candidate", "T2", "T3"}:
        raise ValueError("tier must be candidate, T2 or T3")
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
        RUN_EVAL_TEMPLATE.format(entrypoint=entrypoint), encoding="utf-8")
    metadata = {k: spec.get(k, "") for k in
                ["domain", "task", "oracle_type", "score_mode",
                 "eval_time_seconds", "science_metric", "reference_baseline",
                 "reference_sota", "citation"]}
    metadata.update({"difficulty": difficulty, "tier": tier})
    (eval_dir / "metadata.yaml").write_text(
        METADATA_TEMPLATE.format(**metadata), encoding="utf-8")
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

"""Frontier-Science CLI.

  python -m frontier_science list
  python -m frontier_science eval  --task LennardJonesCluster [--candidate path.py]
  python -m frontier_science run   --task LennardJonesCluster --budget 10 [--llm-config p.yaml]
  python -m frontier_science smoke  # check the configured LLM endpoint responds
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .algorithms import ALGORITHMS, get_algorithm
from .config import load_llm_client, resolve_llm_config_path
from .evaluate import evaluate_candidate
from .registry import find_task, list_tasks
from .certification import certification_status


def _cmd_list(args) -> int:
    status = "all" if args.all else ("quarantined" if args.quarantined else "certified")
    specs = list_tasks(status)
    if not specs:
        print("No tasks found under benchmarks/.")
        return 0
    print(f"{'TASK':45} {'STATUS':12} {'DISCIPLINE':16} {'DOMAIN':22} {'DIFF':8} ORACLE")
    for s in specs:
        print(f"{s.task_id:45} {certification_status(s.task_id):12} {s.discipline:16} {s.domain:22} "
              f"{s.difficulty:8} {s.metadata.get('oracle_type','-')}")
    return 0


def _cmd_eval(args) -> int:
    spec = find_task(args.task, include_uncertified=args.allow_uncertified)
    cand = Path(args.candidate).resolve() if args.candidate else spec.initial_program_path
    metrics = evaluate_candidate(spec, cand, timeout_s=args.timeout)
    print(json.dumps(metrics, indent=2))
    return 0


def _cmd_run(args) -> int:
    spec = find_task(args.task, include_uncertified=args.allow_uncertified)
    llm = load_llm_client(args.llm_config)
    print(f"LLM config: {resolve_llm_config_path(args.llm_config)} "
          f"(wire={llm.config.wire}, model={llm.config.model})", file=sys.stderr)
    algorithm = get_algorithm(args.algorithm)
    workdir = Path(args.workdir).expanduser().resolve() if args.workdir else None
    res = algorithm(
        spec, llm, budget=args.budget, timeout_s=args.timeout,
        workdir=workdir, seed=args.seed, resume=args.resume,
        feedback_mode=args.feedback_mode,
    )
    print(json.dumps({"task": res.task_id, "algorithm": res.algorithm,
                      "seed": res.seed, "baseline": res.baseline_score,
                      "best": res.best_score, "accepted": res.accepted,
                      "evaluated": res.evaluated, "summary": res.summary}, indent=2))
    return 0


def _cmd_smoke(args) -> int:
    llm = load_llm_client(args.llm_config)
    print(f"Using {resolve_llm_config_path(args.llm_config)} "
          f"(wire={llm.config.wire}, model={llm.config.model})", file=sys.stderr)
    out = llm.complete("Reply with exactly: FS_SMOKE_OK", system="Be terse.")
    print(out.strip())
    return 0 if "FS_SMOKE_OK" in out else 1


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="frontier_science")
    sub = p.add_subparsers(dest="cmd", required=True)

    pl = sub.add_parser("list"); pl.set_defaults(fn=_cmd_list)
    pl.add_argument("--all", action="store_true", help="include candidate and quarantined tasks")
    pl.add_argument("--quarantined", action="store_true", help="show only quarantined tasks")

    pe = sub.add_parser("eval"); pe.set_defaults(fn=_cmd_eval)
    pe.add_argument("--task", required=True); pe.add_argument("--candidate", default=None)
    pe.add_argument("--timeout", type=float, default=300.0)
    pe.add_argument("--allow-uncertified", action="store_true")

    pr = sub.add_parser("run"); pr.set_defaults(fn=_cmd_run)
    pr.add_argument("--task", required=True); pr.add_argument("--budget", type=int, default=10)
    pr.add_argument("--timeout", type=float, default=300.0); pr.add_argument("--llm-config", default=None)
    pr.add_argument("--algorithm", choices=ALGORITHMS, default="greedy_rewrite")
    pr.add_argument("--seed", type=int, default=0)
    pr.add_argument("--resume", action="store_true")
    pr.add_argument("--workdir", default=None)
    pr.add_argument(
        "--feedback-mode",
        choices=(
            "normal", "none", "shuffled", "score_only", "delayed_replay",
            "selection_blind",
        ),
        default="normal",
    )
    pr.add_argument("--allow-uncertified", action="store_true")

    ps = sub.add_parser("smoke"); ps.set_defaults(fn=_cmd_smoke)
    ps.add_argument("--llm-config", default=None)

    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())

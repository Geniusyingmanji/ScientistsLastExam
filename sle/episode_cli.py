"""Evidence-first scientific discovery; explicit oracle construction diagnostics."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .scientific_episode import (
    PILOTS, PILOT_ROLES, EpisodeSession, SandboxAnalysis, _load_module, _task_directory,
    create_environment, parse_action, parse_json, prepare_output, public_files, run_llm,
    run_policy, save_report, source_binding,
)


def command(args):
    if args.list:
        print(json.dumps({"environments": list(PILOTS), "stage": "candidate",
                          "evaluation_roles": PILOT_ROLES, "difficulty": "calibration_required",
                          "default_evaluation_mode": "evidence",
                          "oracle_mode": "explicit construction diagnostics only",
                          "frontier_eligible": False}, indent=2))
        return 0
    if not args.task or not args.output_dir:
        raise ValueError("episode requires --task and private --output-dir")
    if sum(value is not None for value in (args.baseline, args.actions, args.program, args.llm_config)) != 1:
        raise ValueError("choose exactly one of --baseline, --actions, --program, --llm-config")
    directory = prepare_output(args.output_dir)
    binding = source_binding(args.task)
    evaluation_mode = getattr(args, "evaluation_mode", "evidence")
    binding.update(private_world_seed=args.seed, episode_protocol="sle-scientific-episode-v1",
                   evaluation_mode="evidence_only" if evaluation_mode == "evidence" else "oracle_diagnostic")
    data_bundle = getattr(args, "data_bundle", None)
    environment = create_environment(args.task, args.seed, data_bundle=data_bundle)
    experiment_budget = getattr(args, "experiment_budget", None)
    if experiment_budget is not None:
        if isinstance(experiment_budget, bool) or not isinstance(experiment_budget, int) or experiment_budget < 1:
            raise ValueError("experiment budget must be a positive integer")
        environment.budget_units = experiment_budget
        binding["experiment_budget_override"] = experiment_budget
    if evaluation_mode == "oracle" and not callable(getattr(environment, "evaluate", None)):
        raise ValueError("this measurement environment has no ground-truth evaluator")
    if evaluation_mode == "evidence":
        from .evidence_episode import EvidenceEpisodeSession, run_discovery_policy
        session_type, policy_runner = EvidenceEpisodeSession, run_discovery_policy
    else:
        session_type, policy_runner = EpisodeSession, run_policy
    analysis = None
    worker = None
    session = None
    try:
        if args.llm_config:
            from .config import load_llm_client
            llm = load_llm_client(args.llm_config)
            # One request cannot wait longer than the episode's remaining budget.
            llm.config.timeout_seconds = min(llm.config.timeout_seconds, args.wall_seconds)
            binding["mode"] = "llm_interactive"
            binding["model_condition"] = {key: getattr(llm.config, key) for key in (
                "model", "wire", "temperature", "reasoning_effort", "max_output_tokens",
                "thinking_budget_tokens", "stream", "chat_reasoning_fallback")}
            if args.analysis == "sandbox":
                analysis = SandboxAnalysis(args.task, args.wall_seconds)
        elif args.program:
            from .secure_eval import CandidateProxy
            candidate = Path(args.program).resolve()
            binding.update(mode="program_interactive", candidate_sha256=hashlib.sha256(candidate.read_bytes()).hexdigest())
            worker = CandidateProxy(candidate, "solve", timeout_s=args.wall_seconds)
        elif args.baseline:
            binding.update(mode="operator_baseline", baseline=args.baseline)
        else:
            binding.update(mode="action_replay", actions_sha256=hashlib.sha256(Path(args.actions).read_bytes()).hexdigest())
        session = session_type(environment, max_steps=args.max_steps,
                                 wall_seconds=args.wall_seconds, analysis=analysis, binding=binding)
        if args.llm_config:
            report = run_llm(session, llm, public_files(args.task))
        elif worker is not None:
            report = policy_runner(session, worker)
        elif args.baseline:
            _task_id, path = _task_directory(args.task)
            reference = _load_module(path / "verification" / "reference.py")
            if evaluation_mode == "evidence":
                policies = getattr(reference, "EVIDENCE_POLICIES", {})
            else:
                policies = getattr(reference, "POLICIES", {"reference": reference.solve})
            if args.baseline not in policies:
                raise ValueError("no such baseline in " + evaluation_mode + " mode; available: " + ", ".join(sorted(policies)))
            report = policy_runner(session, policies[args.baseline])
        else:
            text = Path(args.actions).read_text(encoding="utf-8")
            actions = parse_json(text)
            if not isinstance(actions, list):
                raise ValueError("actions file must contain a JSON array")
            for action in actions:
                # Apply the same strict JSON validation as live model requests.
                session.step(parse_action(json.dumps(action, allow_nan=False)))
                if session.done:
                    break
            if not session.done:
                session.stop("incomplete_delivery")
            report = session.report()
        path = save_report(directory, report)
        print(json.dumps({"task": binding["task_id"], "status": report["status"],
                          "mode": binding["mode"], "resources": report["resources"],
                          "evaluation_mode": evaluation_mode,
                          "private_report": str(path), "frontier_eligible": False,
                          "evaluation_role": binding["evaluation_role"],
                          "difficulty": "calibration_required"}, indent=2))
        return 0 if report["status"] == "completed" else 2
    finally:
        if analysis is not None:
            analysis.close()
        if worker is not None:
            worker.close()


def add_parser(sub):
    parser = sub.add_parser("episode", help="run a candidate scientific discovery environment")
    parser.set_defaults(fn=command)
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--task")
    parser.add_argument("--seed", type=int, default=0, help="operator-only world seed; never sent to model")
    parser.add_argument("--evaluation-mode", choices=("evidence", "oracle"), default="evidence",
                        help="default evidence: no GT; oracle: explicit synthetic construction diagnostics")
    parser.add_argument("--data-bundle", help="operator-owned MeasurementAudit manifest/CSV bundle; never mounted in candidate sandbox")
    parser.add_argument("--experiment-budget", type=int, help="operator-set total budget including replication, recorded in the run binding")
    parser.add_argument("--baseline", help="operator-reviewed baseline, e.g. reference")
    parser.add_argument("--actions", help="JSON array of multi-round discovery actions")
    parser.add_argument("--program", help="self-contained solve(context, act) in evidence mode; solve(problem, experiment) in oracle mode; Linux sandbox required")
    parser.add_argument("--llm-config", help="existing SLE model configuration for live interaction")
    parser.add_argument("--analysis", choices=("sandbox", "none"), default="sandbox")
    parser.add_argument("--max-steps", type=int, default=64)
    parser.add_argument("--wall-seconds", type=float, default=300.0)
    parser.add_argument("--output-dir", help="owner-only evidence directory outside every Git checkout")

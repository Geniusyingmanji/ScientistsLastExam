#!/usr/bin/env python3
"""Explicit transport handoff for the two remaining first-round pilot slots.

The original remote campaign owns the quota. Its failure and reports remain
immutable. API calls and the trusted measurement broker run on the operator's
reachable host; candidate Python still runs only in the remote Linux sandbox.
No retry, alternate campaign, or local candidate-execution fallback is provided.
"""
from __future__ import annotations

import argparse
import copy
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.run_observational_pilot import (
    BRIEF, ENDPOINT, MODEL, RecordedClient, claim_slot, model_condition,
    utc_now, write_once,
)
from sle.config import load_llm_client
from sle.evidence_episode import EvidenceEpisodeSession
from sle.scientific_episode import (
    MAX_JSON_BYTES, create_environment, digest, parse_action, prepare_output,
    public_files, run_llm, save_report, source_binding,
)

PARENT_FILES = (
    "campaign.json", "provider_failure.json", "model-01.started.json",
    "model-01/episode.json", "model-01/completed.json", "model-01/transport.jsonl",
)


def file_sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_receipt(receipt):
    if (not isinstance(receipt, dict) or set(receipt) != {
            "at", "status", "transport_attempts", "transport_problem", "usage", "usage_scope", "files"}
            or receipt["status"] not in {"completed", "budget_exhausted", "model_error",
                "invalid_candidate", "infrastructure_error", "evidence_limit", "incomplete_delivery"}
            or type(receipt["transport_problem"]) is not bool
            or type(receipt["transport_attempts"]) is not int
            or not 1 <= receipt["transport_attempts"] <= 32
            or not isinstance(receipt["usage"], dict)
            or not isinstance(receipt["at"], str) or not receipt["at"]
            or not isinstance(receipt["usage_scope"], str) or not receipt["usage_scope"]
            or not isinstance(receipt["files"], dict)
            or set(receipt["files"]) != {"episode.json", "transport.jsonl", "completed.json"}
            or any(not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value)
                   for value in receipt["files"].values())):
        raise ValueError("invalid completion receipt")
    return receipt


def parent_snapshot(directory):
    """This narrow handoff requires exactly the diagnosed, finished first slot."""
    plan = json.loads((directory / "campaign.json").read_text())
    completed = json.loads((directory / "model-01/completed.json").read_text())
    events = [json.loads(line) for line in
              (directory / "model-01/transport.jsonl").read_text().splitlines()]
    if (plan.get("episodes") != 3 or plan.get("max_steps") != 32
            or completed.get("status") != "budget_exhausted"
            or completed.get("transport_attempts") != 1
            or [row.get("kind") for row in events] != ["request_started", "request_failed"]):
        raise ValueError("handoff requires the reviewed first-slot transport timeout")
    return {"plan": plan, "files": {name: file_sha(directory / name) for name in PARENT_FILES}}


def ledger(directory, request):
    """Central, locked, append-only quota RPC; no credentials or model calls."""
    directory = prepare_output(directory)
    lock = os.open(str(directory / "campaign.lock"), os.O_WRONLY | os.O_CREAT, 0o600)
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        snapshot = parent_snapshot(directory)
        operation = request.get("operation")
        if operation == "describe":
            return {"parent": snapshot, "started_slots": sorted(
                path.name for path in directory.glob("model-*.started.json"))}
        plan_path = directory / "continuation-plan.json"
        if operation == "register":
            plan = request["plan"]
            if (plan.get("parent") != snapshot or plan.get("remaining_slots") != [2, 3]
                    or plan.get("max_steps") != 32 or plan.get("total_episode_quota") != 3):
                raise ValueError("continuation must retain original evidence and quota")
            if plan_path.exists():
                if json.loads(plan_path.read_text()) != plan:
                    raise ValueError("immutable continuation differs")
            else:
                if sorted(path.name for path in directory.glob("model-*.started.json")) != ["model-01.started.json"]:
                    raise ValueError("unreconciled slot prevents handoff")
                write_once(plan_path, plan)
            return {"plan_sha256": digest(plan)}
        plan = json.loads(plan_path.read_text())
        if plan["parent"] != snapshot or request.get("plan_sha256") != digest(plan):
            raise ValueError("parent evidence or continuation identity changed")
        number = request.get("slot")
        if type(number) is not int or number not in (2, 3):
            raise ValueError("only original slots two and three may continue")
        if operation == "claim":
            if number == 3:
                prior = validate_receipt(json.loads((directory / "model-02.continuation-completed.json").read_text()))
                if prior.get("transport_problem") or prior.get("status") == "model_error":
                    raise ValueError("unresolved continuation failure blocks further spending")
            claim_slot(directory, number, digest(plan))
            return {"claimed_slot": number, "plan_sha256": digest(plan)}
        if operation == "finish":
            started = json.loads((directory / ("model-%02d.started.json" % number)).read_text())
            receipt = validate_receipt(request["receipt"])
            if started["plan_sha256"] != digest(plan):
                raise ValueError("invalid completion receipt")
            write_once(directory / ("model-%02d.continuation-completed.json" % number), receipt)
            return {"recorded_slot": number}
        raise ValueError("unknown ledger operation")
    finally:
        os.close(lock)


def remote_ledger(args, request):
    # All command words are operator configuration, never model-generated text.
    command = "cd %s && exec %s scripts/continue_observational_pilot.py --ledger %s" % (
        shlex.quote(args.remote_worktree), shlex.quote(args.remote_python),
        shlex.quote(args.remote_campaign))
    payload = json.dumps(request, allow_nan=False)
    if len(payload.encode()) > MAX_JSON_BYTES:
        raise ValueError("quota request too large")
    result = subprocess.run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=12",
                             "--", args.remote_host, command], input=payload + "\n",
                            capture_output=True, text=True, timeout=45, check=True)
    return parse_action(result.stdout)


def transport_problem(path):
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    starts = {row["attempt"] for row in rows if row["kind"] == "request_started"}
    responses = {row["attempt"] for row in rows if row["kind"] == "response_received"}
    return (not starts or starts != responses
            or any(row["kind"] == "request_failed" for row in rows))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", type=Path)
    parser.add_argument("--data-bundle", type=Path)
    parser.add_argument("--llm-config")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--remote-host")
    parser.add_argument("--remote-worktree")
    parser.add_argument("--remote-python")
    parser.add_argument("--remote-campaign")
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args(argv)
    if args.ledger:
        raw = sys.stdin.buffer.readline(MAX_JSON_BYTES + 2)
        if len(raw) > MAX_JSON_BYTES:
            raise ValueError("quota request too large")
        print(json.dumps(ledger(args.ledger, parse_action(raw.decode("utf-8"))), allow_nan=False))
        return 0
    if any(getattr(args, field) is None for field in (
            "data_bundle", "llm_config", "output", "remote_host", "remote_worktree",
            "remote_python", "remote_campaign")):
        parser.error("continuation requires all data, private config, output and remote fields")
    config = load_llm_client(args.llm_config).config
    if (config.model != MODEL or config.wire != "chat" or config.stream
            or config.base_url.rstrip("/") != ENDPOINT
            or not 1 <= config.max_output_tokens <= 8000 or not 0 < config.timeout_seconds <= 180):
        raise ValueError("continuation must retain the bounded named model condition")
    directory = prepare_output(args.output)
    lock = os.open(str(directory / "continuation.lock"), os.O_WRONLY | os.O_CREAT, 0o600)
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    try:
        parent = remote_ledger(args, {"operation": "describe"})["parent"]
        if model_condition(config) != parent["plan"]["model_condition"]:
            raise ValueError("model condition differs from parent")
        binding = source_binding("MeasurementAudit")
        # A host/runtime change is explicit; scientific adapter and runtime code
        # must be identical to the original round, even across bridge commits.
        for field in ("task_sha256", "runtime_source_sha256"):
            if binding[field] != parent["plan"]["adapter_source"][field]:
                raise ValueError("scientific source changed; cannot continue this round")
        environment = create_environment("MeasurementAudit", 0, data_bundle=args.data_bundle)
        if environment.data_binding() != parent["plan"]["data_binding"]:
            raise ValueError("observation binding changed")
        from scripts.remote_pilot_analysis import RemoteAnalysis
        probe = RemoteAnalysis(args.remote_host, args.remote_worktree, args.remote_python)
        try:
            remote_binding = probe.ready
        finally:
            probe.close()
        for field in ("task_sha256", "runtime_source_sha256"):
            if remote_binding["source_binding"][field] != binding[field]:
                raise ValueError("remote sandbox scientific source differs")
        if remote_binding["bridge_sha256"] != file_sha(ROOT / "scripts/remote_pilot_analysis.py"):
            raise ValueError("remote bridge differs from reviewed local source")
        code = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
        runner_sha = file_sha(Path(__file__))
        plan = {
            "schema_version": 1, "parent": parent, "remaining_slots": [2, 3],
            "total_episode_quota": 3, "max_steps": 32, "wall_seconds": 600,
            "experiment_budget": 20000, "source_commit": code,
            "runner_sha256": runner_sha, "local_broker_binding": binding,
            "remote_analysis_binding": remote_binding, "output": str(directory),
            "remote_campaign": args.remote_campaign, "remote_host": args.remote_host,
            "model_condition": model_condition(config),
            "reason": "First remote API attempt timed out; remote TCP unreachable, operator API path reachable. Candidate analysis remains Linux sandboxed. Runtime conditions differ and are reported separately.",
        }
        registered = remote_ledger(args, {"operation": "register", "plan": plan})
        if registered["plan_sha256"] != digest(plan):
            raise ValueError("quota ledger registration mismatch")
        plan_path = directory / "continuation-plan.json"
        if plan_path.exists():
            if json.loads(plan_path.read_text()) != plan:
                raise ValueError("local continuation plan changed")
        else:
            write_once(plan_path, plan)
        if args.prepare_only:
            print(json.dumps({"status": "prepared", "new_api_calls": 0, "plan_sha256": digest(plan)}))
            return 0
        files = public_files("MeasurementAudit")
        files["observational_research_brief.txt"] = BRIEF
        for number in (2, 3):
            if ((directory / ("model-%02d.started.json" % number)).exists()
                    or (directory / "continuation-failure.json").exists()):
                raise ValueError("started continuation requires review; never automatically rerun")
            env = create_environment("MeasurementAudit", 0, data_bundle=args.data_bundle)
            if (env.data_binding() != parent["plan"]["data_binding"]
                    or source_binding("MeasurementAudit") != binding
                    or file_sha(Path(__file__)) != runner_sha
                    or subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip() != code):
                raise ValueError("frozen continuation inputs changed")
            env.budget_units = plan["experiment_budget"]
            analysis = RemoteAnalysis(args.remote_host, args.remote_worktree, args.remote_python)
            try:
                if analysis.ready != remote_binding:
                    raise ValueError("remote analysis binding changed")
                output = prepare_output(directory / ("model-%02d" % number))
                # A lost SSH reply after this command is uncertain consumption;
                # do not retry. The central O_EXCL marker is authoritative.
                claimed = remote_ledger(args, {"operation": "claim", "slot": number,
                                               "plan_sha256": digest(plan)})
                if claimed.get("claimed_slot") != number:
                    raise ValueError("central quota claim mismatch")
                claim_slot(directory, number, digest(plan))
                llm = RecordedClient(copy.deepcopy(config), output / "transport.jsonl")
                session = EvidenceEpisodeSession(env, max_steps=32, wall_seconds=600,
                    analysis=analysis, binding={**binding, "mode": "llm_interactive",
                        "source_commit": code, "continuation_plan_sha256": digest(plan),
                        "parent_plan_sha256": digest(parent["plan"]), "draw": number,
                        "model_condition": model_condition(config),
                        "remote_analysis_binding": remote_binding})
                report = run_llm(session, llm, files)
                save_report(output, report)
                problem = llm.transport_failed or transport_problem(output / "transport.jsonl")
                completed = {"at": utc_now(), "status": report["status"],
                    "transport_attempts": llm.attempts, "transport_problem": problem,
                    "usage": llm.total_usage,
                    "usage_scope": "Successful parsed responses only; missing response usage is unknown, not zero."}
                write_once(output / "completed.json", completed)
                receipt = {**completed, "files": {name: file_sha(output / name) for name in
                           ("episode.json", "transport.jsonl", "completed.json")}}
                remote_ledger(args, {"operation": "finish", "slot": number,
                                     "plan_sha256": digest(plan), "receipt": receipt})
                print(json.dumps({"draw": number, **completed, "resources": report["resources"]}), flush=True)
                if problem or report["status"] == "model_error":
                    write_once(directory / "continuation-failure.json", receipt)
                    return 2
            finally:
                analysis.close()
        return 0
    finally:
        os.close(lock)


if __name__ == "__main__":
    raise SystemExit(main())

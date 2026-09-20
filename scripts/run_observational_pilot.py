#!/usr/bin/env python3
"""Bounded, restart-safe first observational pilot; never a discovery leaderboard.

Use the same private campaign directory on every invocation. Its immutable plan
and three durable slot claims prevent a restart from silently buying more draws.
The complete reports and measurement values remain outside Git.
"""
from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sle.config import load_llm_client
from sle.evidence_episode import EvidenceEpisodeSession, run_discovery_policy
from sle.llm import LLMClient
from sle.scientific_episode import (
    SandboxAnalysis, create_environment, digest, prepare_output, public_files,
    run_llm, save_report, source_binding,
)

MODEL = "gpt-5.6-sol"
ENDPOINT = "https://matrixllm.alipay.com/v1"
BRIEF = """Question: Does the descriptive contrast in mean PM2.5 between
SE-dominated and NW-dominated weeks persist from 2010-2012 into the sealed
2013-2014 records? Compare stable association, weak pooled association, and
temporal/seasonal heterogeneity as applicable. Calendar season is available for
exploratory analysis; the current sealed tools only support pooled summaries.
Consequently seasonal adjustment of sealed data, causal attribution and an
independent collection are not established. A change of year/episode seed is
not a new scientific sample. Report narrower, negative or inconclusive findings
where warranted. Tool standard errors assume independent rows and must not be
treated as valid time-series inference. Use only native evidence IDs. Freeze
any sealed tests before commitment. This is a protocol/method pilot on public
historical observations; novelty and frontier difficulty remain unassessed.
You have at most 32 actions; leave actions and experimental budget to commit.
"""


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def write_once(path, value):
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def append_record(path, value):
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    with os.fdopen(fd, "a", encoding="utf-8") as stream:
        stream.write(json.dumps(value, allow_nan=False) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def claim_slot(directory, number, plan_sha256):
    if type(number) is not int or not 1 <= number <= 3:
        raise ValueError("first-round quota is exactly three available slots")
    write_once(directory / ("model-%02d.started.json" % number), {
        "slot": number, "plan_sha256": plan_sha256, "started_at": utc_now(),
        "quota_rule": "Started or interrupted slots are consumed; never automatically retry them.",
    })


def previous_transport_problem(directory):
    """Interrupted/failed slots require reconciliation before spending again."""
    if (directory / "provider_failure.json").exists():
        return "provider_failure_previously_recorded"
    for marker in sorted(directory.glob("model-*.started.json")):
        output = directory / marker.name[:-len(".started.json")]
        if not (output / "completed.json").exists():
            return "interrupted_slot_requires_review"
        completed = json.loads((output / "completed.json").read_text())
        if completed.get("status") == "model_error":
            return "previous_model_error"
        path = output / "transport.jsonl"
        if not path.exists():
            return "missing_transport_record"
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        started = {row["attempt"] for row in rows if row["kind"] == "request_started"}
        received = {row["attempt"] for row in rows if row["kind"] == "response_received"}
        if started != received or any(row["kind"] == "request_failed" for row in rows):
            return "failed_or_unresolved_transport"
    return None


class RecordedClient(LLMClient):
    """Single-attempt transport with provider identity and usage provenance.

    No retries after uncertain timeouts: a second request could incur another
    charge. Only allowlisted metadata is logged, never authorization headers.
    """
    def __init__(self, config, log_path):
        super().__init__(config)
        self.log_path = log_path
        self.attempts = 0
        self.transport_failed = False

    def _post(self, url, payload, headers, retries=1):
        if self.attempts >= 32:
            raise RuntimeError("model transport attempt quota exhausted")
        self.attempts += 1
        request_id = self.attempts
        append_record(self.log_path, {
            "kind": "request_started", "attempt": request_id, "at": utc_now(),
            "requested_model": payload["model"], "payload_sha256": digest(payload),
        })
        request = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"),
                                         headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=self.config.timeout_seconds) as response:
                data = json.load(response)
            append_record(self.log_path, {
                "kind": "response_received", "attempt": request_id, "at": utc_now(),
                "provider_model": data.get("model"), "provider_response_id": data.get("id"),
                "usage": data.get("usage"),
                "identity_status": "provider_asserted_not_independently_verified",
            })
            # A response for a different named family cannot silently become a
            # GPT-5.6-sol draw. Missing identity stays unavailable in the log.
            name = data.get("model")
            if name is not None and name != MODEL and not str(name).startswith(MODEL + "-"):
                raise RuntimeError("provider model differs from requested model")
            return data
        except BaseException as exc:
            self.transport_failed = True
            append_record(self.log_path, {
                "kind": "request_failed", "attempt": request_id, "at": utc_now(),
                "error_type": type(exc).__name__,
                "http_status": exc.code if isinstance(exc, urllib.error.HTTPError) else None,
                "usage_if_no_response": "unknown, not zero",
            })
            raise


def model_condition(config):
    return {key: getattr(config, key) for key in (
        "model", "wire", "base_url", "temperature", "reasoning_effort", "max_output_tokens",
        "chat_max_tokens_field", "stream", "chat_reasoning_fallback", "timeout_seconds",
    )}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-bundle", type=Path, required=True)
    parser.add_argument("--llm-config", required=True)
    parser.add_argument("--campaign-dir", type=Path, required=True)
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args(argv)
    directory = prepare_output(args.campaign_dir)
    client = load_llm_client(args.llm_config)
    config = client.config
    if (config.model != MODEL or config.wire != "chat" or config.stream
            or config.base_url.rstrip("/") != ENDPOINT):
        raise ValueError("pilot requires explicitly configured non-stream chat gpt-5.6-sol")
    if not 1 <= config.max_output_tokens <= 8000 or not 0 < config.timeout_seconds <= 180:
        raise ValueError("pilot allows at most 8000 output tokens and 180 seconds per request")
    environment = create_environment("MeasurementAudit", 0, data_bundle=args.data_bundle)
    if environment.data_binding()["provenance"]["kind"] != "observed_measurements":
        raise ValueError("model pilot requires observed measurements, not the protocol fixture")
    code = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    files = public_files("MeasurementAudit")
    files["observational_research_brief.txt"] = BRIEF
    binding = source_binding("MeasurementAudit")
    plan = {
        "schema_version": 1, "source_commit": code, "adapter_source": binding,
        "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "controls_sha256": hashlib.sha256((ROOT / "scripts/beijing_pilot_controls.py").read_bytes()).hexdigest(),
        "data_binding": environment.data_binding(), "brief_sha256": digest(BRIEF),
        "model_condition": model_condition(config), "episodes": 3, "max_steps": 32,
        "wall_seconds": 600, "experiment_budget": 20000,
        "interpretation": "Repeated agent draws over the same historical observations; not independent scientific replications or a difficulty success rate.",
    }
    lock = os.open(str(directory / "campaign.lock"), os.O_WRONLY | os.O_CREAT, 0o600)
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        path = directory / "campaign.json"
        if path.exists():
            if json.loads(path.read_text()) != plan:
                raise ValueError("immutable pilot plan differs; do not create a fresh quota to bypass it")
        else:
            write_once(path, plan)
        if args.prepare_only:
            print(json.dumps({"status": "prepared", "plan_sha256": digest(plan), "api_calls": 0}))
            return 0
        prior_problem = previous_transport_problem(directory)
        if prior_problem:
            print(json.dumps({"status": prior_problem, "new_api_calls": 0}))
            return 2
        def frozen_environment():
            env = create_environment("MeasurementAudit", 0, data_bundle=args.data_bundle)
            if env.data_binding() != plan["data_binding"]:
                raise ValueError("data changed after pilot plan was frozen")
            if (source_binding("MeasurementAudit") != binding
                    or hashlib.sha256(Path(__file__).read_bytes()).hexdigest() != plan["runner_sha256"]
                    or hashlib.sha256((ROOT / "scripts/beijing_pilot_controls.py").read_bytes()).hexdigest() != plan["controls_sha256"]
                    or subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip() != code):
                raise ValueError("source changed after pilot plan was frozen")
            env.budget_units = plan["experiment_budget"]
            return env
        from scripts.beijing_pilot_controls import fixed_pooled, null_discovery as null
        for name, policy in (("fixed_pooled", fixed_pooled), ("null", null)):
            output = directory / ("control-" + name)
            if (output / "episode.json").exists():
                continue
            env = frozen_environment()
            session = EvidenceEpisodeSession(env, max_steps=32, wall_seconds=600,
                binding={**binding, "mode": "operator_baseline", "baseline": name,
                         "pilot_plan_sha256": digest(plan), "source_commit": code})
            report = run_discovery_policy(session, policy)
            save_report(prepare_output(output), report)
            print(json.dumps({"control": name, "status": report["status"]}), flush=True)
        for number in range(1, 4):
            if (directory / ("model-%02d.started.json" % number)).exists():
                continue
            env = frozen_environment()
            # Sandbox setup happens before consuming a paid slot and before
            # making any model request. No host execution fallback is permitted.
            analysis = SandboxAnalysis("MeasurementAudit", 600)
            try:
                output = prepare_output(directory / ("model-%02d" % number))
                claim_slot(directory, number, digest(plan))
                llm = RecordedClient(copy.deepcopy(config), output / "transport.jsonl")
                session = EvidenceEpisodeSession(env, max_steps=32, wall_seconds=600,
                    analysis=analysis, binding={**binding, "mode": "llm_interactive",
                        "source_commit": code, "pilot_plan_sha256": digest(plan),
                        "model_condition": model_condition(llm.config), "draw": number})
                report = run_llm(session, llm, files)
                save_report(output, report)
                write_once(output / "completed.json", {
                    "at": utc_now(), "status": report["status"], "transport_attempts": llm.attempts,
                    "usage": llm.total_usage,
                    "usage_scope": "Successful parsed responses only; failed request usage may be unknown.",
                })
                print(json.dumps({"draw": number, "status": report["status"],
                                  "attempts": llm.attempts, "resources": report["resources"]}), flush=True)
                if llm.transport_failed or report["status"] == "model_error":
                    # Auth/routing/provider failures are not model difficulty.
                    # Don't spend the remaining slots repeating a known failure.
                    write_once(directory / "provider_failure.json", {
                        "draw": number, "at": utc_now(),
                        "reason": "Do not consume another slot without resolving the recorded provider failure.",
                    })
                    return 2
            finally:
                analysis.close()
        return 0
    finally:
        os.close(lock)


if __name__ == "__main__":
    raise SystemExit(main())

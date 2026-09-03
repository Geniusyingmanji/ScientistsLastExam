#!/usr/bin/env python3
"""Audit the real GPT-5.5 signed-decision protocol smoke."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.repo_paths import resolve_run_workdir  # noqa: E402
from sle.algorithms.evolve import extract_signed_submission  # noqa: E402
from sle.provenance import finalize_report_trust, source_provenance  # noqa: E402
from sle.sentinels import load_sentinel_events  # noqa: E402


DEFAULT_RAW = ROOT / "experiments/gpt55_signed_decision_smoke_2026-07-27_v3.json"
EXPECTED_INCOMPLETE = "proposal_budget_exhausted_before_active_wall_horizon"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _recorded_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def build_report(raw_path: Path = DEFAULT_RAW) -> dict[str, Any]:
    raw_path = raw_path.resolve()
    raw = json.loads(raw_path.read_text(encoding="utf-8"))
    runs = raw.get("runs") or []
    issues = []
    if len(runs) != 1:
        issues.append("signed-decision smoke must contain exactly one run")
        run = {}
    else:
        run = runs[0]
    config = raw.get("config") or {}
    summary = run.get("summary") or {}
    snapshot = summary.get("sentinel_snapshot") or {}
    try:
        workdir = resolve_run_workdir(run.get("workdir"), ROOT)
    except (OSError, TypeError, ValueError) as exc:
        issues.append("workdir resolution failed: %s" % exc)
        workdir = None
    ledger_path = (
        workdir / str(snapshot.get("ledger_path"))
        if workdir is not None else None
    )
    events = []
    if ledger_path is not None:
        try:
            events = load_sentinel_events(ledger_path, workdir=workdir)
        except Exception as exc:  # noqa: BLE001
            issues.append("sentinel replay failed: %s" % exc)
    by_type = {row["sentinel_type"]: row for row in events}
    submission = by_type.get("submission") or {}
    commit = by_type.get("commit") or {}
    first_valid = by_type.get("first_valid") or {}
    terminal = by_type.get("terminal") or {}
    trajectory = ((run.get("trajectory_snapshot") or {}).get("events") or [])
    proposal = trajectory[1] if len(trajectory) == 2 else {}

    response_ref = submission.get("provider_response") or {}
    response_path = (
        workdir / str(response_ref.get("path"))
        if workdir is not None else None
    )
    response = (
        response_path.read_text(encoding="utf-8")
        if response_path is not None and response_path.is_file() else ""
    )
    parsed = extract_signed_submission(response)
    parsed_code, parsed_decision = parsed if parsed is not None else (None, None)
    response_sha = hashlib.sha256(response.encode("utf-8")).hexdigest() if response else None

    checks = {
        "raw_is_claim_bounded_protocol_smoke": raw.get("evidence_scope") == "PROTOCOL_SMOKE_ONLY_NOT_MODEL_PERFORMANCE",
        "raw_expectedly_fails_fixed_duration_completion": raw.get("execution_passed") is False,
        "protocol_incomplete_reason_retained": run.get("protocol_incomplete") == EXPECTED_INCOMPLETE,
        "configured_gpt55_responses": bool(
            (config.get("llm") or {}).get("model") == "gpt-5.5"
            and (config.get("llm") or {}).get("wire") == "responses"
            and (config.get("llm") or {}).get("reasoning_effort") == "low"
        ),
        "signed_record_only_enabled": bool(
            config.get("signed_decisions") is True
            and config.get("signed_decision_policy") == "record_only"
        ),
        "provider_usage_complete": bool(
            (summary.get("llm") or {}).get("provider_usage_records") == 1
            and (summary.get("llm") or {}).get("total_tokens")
            == (summary.get("llm") or {}).get("input_tokens")
            + (summary.get("llm") or {}).get("output_tokens")
        ),
        "one_valid_improving_proposal": bool(
            len(trajectory) == 2
            and proposal.get("valid") is True
            and proposal.get("accepted") is True
            and float(proposal.get("best_score", -1)) > float(run.get("baseline", 1))
        ),
        "strict_signed_response_replays": bool(
            parsed_code is not None
            and parsed_decision is not None
            and parsed_decision.get("action") == "commit"
        ),
        "response_content_hash_matches": bool(
            response_sha is not None
            and response_sha == response_ref.get("sha256")
            and response_sha == (submission.get("metadata") or {}).get("response_sha256")
            and response_sha == (commit.get("metadata") or {}).get("response_sha256")
        ),
        "response_candidate_hash_matches": bool(
            parsed_code is not None
            and hashlib.sha256(parsed_code.encode("utf-8")).hexdigest()
            == proposal.get("candidate_sha256")
            == submission.get("artifact_sha256")
            == commit.get("artifact_sha256")
        ),
        "commit_precedes_evaluation": bool(
            commit.get("evaluation", {}).get("status") == "not_evaluated"
            and commit.get("recorded_elapsed_seconds")
            == commit.get("artifact_published_elapsed_seconds")
            < first_valid.get("evaluation_completed_elapsed_seconds", -1)
            and (commit.get("metadata") or {}).get("decision_made_before_evaluation") is True
            and (commit.get("metadata") or {}).get("evaluation_not_visible_when_deciding") is True
        ),
        "terminal_is_workspace_not_hidden_oracle_selection": bool(
            terminal.get("selection_policy") == "terminal_workspace_artifact"
            and terminal.get("artifact_sha256") == proposal.get("candidate_sha256")
            and terminal.get("evaluation", {}).get("status") == "reused_deterministic"
        ),
        "sentinel_ledger_hash_matches": bool(
            ledger_path is not None
            and ledger_path.is_file()
            and _sha256(ledger_path) == snapshot.get("ledger_sha256")
            and events == snapshot.get("events")
        ),
    }
    issues.extend(key for key, passed in checks.items() if not passed)
    report: dict[str, Any] = {
        "schema_version": 1,
        "trust_status": "TRUSTED_SIGNED_DECISION_PROTOCOL_SMOKE_AUDIT",
        "evidence_scope": (
            "ONE_GPT55_KNOWN_ANSWER_ONRAMP_SIGNED_DECISION_PROTOCOL_SMOKE_"
            "NOT_POPULATION_PERFORMANCE_FIXED_DURATION_HEADROOM_FEEDBACK_CAUSAL_"
            "SCALING_LAW_OR_AUTONOMOUS_DISCOVERY_EVIDENCE"
        ),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_provenance": source_provenance(ROOT),
        "environment": {"python": sys.version, "platform": platform.platform()},
        "input": {"path": _recorded_path(raw_path), "sha256": _sha256(raw_path)},
        "checks": checks,
        "observed": {
            "task": run.get("task"),
            "baseline_score": run.get("baseline"),
            "best_score": run.get("best"),
            "signed_action": parsed_decision.get("action") if parsed_decision else None,
            "input_tokens": (summary.get("llm") or {}).get("input_tokens"),
            "output_tokens": (summary.get("llm") or {}).get("output_tokens"),
            "total_tokens": (summary.get("llm") or {}).get("total_tokens"),
            "proposal_published_elapsed_seconds": submission.get("artifact_published_elapsed_seconds"),
            "evaluation_completed_elapsed_seconds": first_valid.get("evaluation_completed_elapsed_seconds"),
            "response_sha256": response_sha,
            "candidate_sha256": proposal.get("candidate_sha256"),
        },
        "issues": issues,
        "limitations": [
            "LennardJonesCluster is a fixed known-answer optimization on-ramp with high pretraining and reconstruction risk.",
            "There is one uncontrolled provider draw and no population or feedback contrast.",
            "The proposal ceiling ends the run before 600 seconds, so the raw run is correctly protocol-incomplete.",
            "The score improvement validates executable protocol integration only and is not scientific discovery.",
        ],
    }
    finalize_report_trust(report, not issues)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw", type=Path, default=DEFAULT_RAW)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = build_report(args.raw)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8"
        )
    print(json.dumps({
        "checks": report["checks"],
        "observed": report["observed"],
        "issues": report["issues"],
        "execution_passed": report["execution_passed"],
        "trusted_evidence": report["trusted_evidence"],
    }, indent=2))
    return 0 if report["execution_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Offline, evidence-bound analysis diagnostics. No World, model API, or scoring.

Preparation and tests never execute source strings. The sole production executor
is CandidateProxy; its existing Bubblewrap isolation is mandatory, without a
host-Python fallback. See ANALYSIS_REPLAY.md for the interpretation limits.
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import platform
import shutil
import sys
import time


PROTOCOL = "sle-analysis-failure-replay-0.1"
HOST = "62910175"
COHORTS = ("core-c2", "expansion-e1")
SOURCE_FILES = (
    "env/__init__.py", "env/analysis_replay.py", "env/analysis_worker.py",
    "sle/__init__.py", "sle/secure_eval.py", "sle/candidate_worker.py",
    "sle/rpc_codec.py", "sle/oracle_package_pins.py", "sle/contract_lint.py",
)
ERRORS = frozenset({"TypeError", "SyntaxError", "ValueError", "KeyError",
                   "IndexError", "NameError", "AttributeError", "ImportError",
                   "ModuleNotFoundError", "OverflowError", "ZeroDivisionError",
                   "RuntimeError", "MemoryError", "RecursionError",
                   "result_too_large", "candidate_timeout", "other"})
PHASES = frozenset({"execution", "result_serialization", "executor", "unknown"})
STATUSES = frozenset({"returned", "budget_exhausted", "executor_failed",
                      "namespace_unavailable", "input_gap", "not_attempted"})
LIMITATIONS = [
    "Sequential execution reconstructs conditional namespace state; no original namespace snapshot exists.",
    "Randomness, clocks, unseeded fitting, runtime/library changes, and timing can change execution.",
    "Original history is reinjected unchanged; enhanced feedback is never inserted into later history.",
    "Logged allowances are rounded pre-model values; exact original per-call wall allowance is unavailable.",
    "A matching error type is reproduction under these conditions, not confirmation of the original cause.",
    "Nonreproduction remains unresolved; no retries, extra budget, rescoring, or completion-rate claim.",
]


class EvidenceGap(ValueError):
    """A fixed operator category, never candidate-controlled exception text."""


def require(condition, category):
    if not condition:
        raise EvidenceGap(category)


def strict_json(text):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "duplicate_json_key")
            result[key] = value
        return result
    try:
        return json.loads(text, object_pairs_hook=pairs,
                          parse_constant=lambda _: (_ for _ in ()).throw(EvidenceGap("nonfinite_json")))
    except (json.JSONDecodeError, UnicodeError, RecursionError):
        raise EvidenceGap("invalid_json") from None


def digest(value, *, ascii=True):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=ascii,
        allow_nan=False, separators=(",", ":")).encode()).hexdigest()


def file_hash(path):
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    except OSError:
        raise EvidenceGap("missing_or_unreadable_input") from None


def read_json(path):
    return strict_json(Path(path).read_text(encoding="utf-8"))


def write_new(path, value):
    """Exclusive creation: never replace evidence or an earlier diagnostic."""
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def source_fingerprint(root=None):
    root = Path(root or Path(__file__).resolve().parents[1])
    files = {name: file_hash(root / name) for name in SOURCE_FILES}
    return {"files": files, "sha256": digest(files)}


def input_path(root, relative):
    path = (Path(root) / relative).resolve()
    require(path.is_relative_to(Path(root).resolve()), "input_path_escape")
    return path


def _compact(entry):
    text = json.dumps(entry, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    if len(text) <= 80000:
        return entry
    return {"note": entry.get("note"), "result_omitted_from_prompt": True,
            "reason": "Large output remains available in analysis history and records.",
            "observation_ids": [r["id"] for r in entry.get("observations", [])]}


def _unique_rounds(rows):
    require(type(rows) is list, "invalid_round_sequence")
    numbers = [r.get("round") for r in rows if type(r) is dict]
    require(len(numbers) == len(rows) and all(type(n) is int for n in numbers), "invalid_round_sequence")
    require(numbers == list(range(1, len(numbers) + 1)), "incomplete_round_sequence")
    return {r["round"]: r for r in rows}


def reconstruct(report, transport, target_rounds):
    """Return exact public payloads, or skip the entire episode on any gap.

    The report's complete final records are a cross-check only; each payload is
    built from observations in strictly earlier history turns, including partial
    experiment batches. No submission, verification target or panel is copied.
    """
    try:
        require(report.get("analysis_protocol", "legacy") == "legacy", "unsupported_snapshot_protocol")
        history, rounds = report["history"], _unique_rounds(report["rounds"])
        turns = _unique_rounds(history)
        require(set(turns).issubset(rounds), "history_round_missing")
        actual_targets = [n for n, row in turns.items()
                          if row.get("analysis", {}).get("error") == "TypeError"]
        require(actual_targets == target_rounds and bool(target_rounds), "target_selection_changed")
        cap = report["limits"]["analysis_active_seconds"]
        require(type(cap) in (int, float) and math.isfinite(cap) and 0 < cap <= 60, "invalid_original_budget")
        # Authenticate every started request before identifying its round. No
        # positional association between attempts and model rounds is assumed.
        contexts = {}
        for event in transport:
            if event.get("event") != "started":
                continue
            request = event["request"]
            require(digest(request, ascii=False) == event["request_sha256"], "request_hash_mismatch")
            messages = request["messages"]
            require(len(messages) == 2 and [m["role"] for m in messages] == ["system", "user"], "unsupported_transport_shape")
            prompt = strict_json(messages[1]["content"])
            n = prompt["round"]
            require(n in rounds, "request_round_missing")
            require(digest(prompt) == rounds[n]["prompt_sha256"], "prompt_hash_mismatch")
            require(digest(messages[0]["content"]) == rounds[n]["system_sha256"], "system_hash_mismatch")
            require(n not in contexts, "ambiguous_request_round")
            contexts[n] = prompt
        records, calls = [], []
        for index, turn in enumerate(history):
            require(set(turn).issubset({"round", "note", "observations", "analysis", "outcome", "error"}), "unknown_history_fields")
            n = turn["round"]
            if "analysis" in turn and n <= max(target_rounds):
                require(n in contexts, "missing_analysis_prompt")
                prompt = contexts[n]
                require(type(prompt["problem"]) is dict, "invalid_problem")
                require("model_snapshot_contract" not in prompt["problem"], "unsupported_snapshot_protocol")
                require(prompt["limits"] == report["limits"], "limits_mismatch")
                require(prompt["observation_catalog"] == [{k: r[k] for k in ("id", "spec", "cost")} for r in records], "catalog_mismatch")
                prior = history[:index]
                require(prompt["research_notes"] == [{"round": r["round"], "note": r.get("note", ""), "outcome": r.get("outcome", "")} for r in prior], "history_notes_mismatch")
                require(prompt["recent_results"] == [_compact(r) for r in prior[-2:]], "recent_history_mismatch")
                action = strict_json(rounds[n]["response"])
                require(set(action) == {"note", "analyze"} and action["note"] == turn["note"], "analysis_response_mismatch")
                require(type(action["analyze"]) is dict and set(action["analyze"]) == {"code"}, "invalid_analysis_action")
                code = action["analyze"]["code"]
                require(type(code) is str and len(code) <= 32000, "invalid_analysis_code")
                budget = prompt["budget"]
                active, wall = budget["analysis_active_seconds_remaining"], budget["wall_seconds_remaining"]
                require(all(type(x) in (int, float) and math.isfinite(x) and x >= 0 for x in (active, wall)), "invalid_logged_budget")
                require(active <= cap, "invalid_logged_budget")
                require(turn["analysis"].get("error") not in {"candidate_timeout", "candidate_error", "candidate_worker_failure"}, "original_namespace_interrupted")
                payload = {"code": code, "problem": deepcopy(prompt["problem"]),
                           "records": deepcopy(records), "history": deepcopy(prior)}
                hashes = {k + "_sha256": digest(v) for k, v in payload.items()}
                hashes["code_utf8_sha256"] = hashlib.sha256(code.encode()).hexdigest()
                calls.append({"event_id": report["episode_id"] + ":analysis:round-" + str(n),
                    "round": n, "history_pointer": "/history/%d/analysis" % index,
                    "target": n in target_rounds, "input_hashes": hashes,
                    "payload_sha256": digest(payload), "original": deepcopy(turn["analysis"]),
                    "logged_active_seconds": active, "logged_wall_seconds": wall,
                    "payload": payload})
            for record in turn.get("observations", []):
                require(type(record) is dict and set(record) == {"id", "spec", "observation", "cost"}, "invalid_record_fields")
                require(record["id"] == "obs-%04d" % (len(records) + 1), "record_order_mismatch")
                records.append(record)
        require(records == report["records"], "complete_records_mismatch")
        require(len(records) == report["experiment_count"], "record_count_mismatch")
        require(sum(c["target"] for c in calls) == len(target_rounds), "missing_target_call")
        return {"episode_id": report["episode_id"], "budget_seconds": cap,
                "recorded_original_source_sha256": report.get("source_sha256"), "calls": calls, "gap": None}
    except EvidenceGap:
        raise
    except (KeyError, TypeError, ValueError, IndexError, OverflowError):
        raise EvidenceGap("incomplete_or_invalid_evidence") from None


def _load_episode(root, item):
    report = read_json(input_path(root, item["report"]))
    events = [strict_json(line) for line in input_path(root, item["transport"]).read_text(encoding="utf-8").splitlines()]
    require(report["episode_id"] == item["episode_id"], "episode_identity_mismatch")
    return reconstruct(report, events, item["target_rounds"])


def episode_manifest(episode):
    return {"episode_id": episode["episode_id"], "budget_seconds": episode["budget_seconds"],
            "recorded_original_source_sha256": episode["recorded_original_source_sha256"],
            "gap": episode["gap"], "calls": [{k: v for k, v in call.items() if k not in {"payload", "original"}}
            | {"original_result_sha256": digest(call["original"])} for call in episode["calls"]]}


def prepare(root, study_path):
    """Bind fixed audit selection and all 52 raw files before any execution."""
    root, study_path = Path(root).resolve(), Path(study_path).resolve()
    study = read_json(study_path)
    audit = root / "calibration/process-resource-audit"
    for name, expected in study["input_audit_sha256"].items():
        require(file_hash(audit / name) == expected, "audit_input_changed")
    audit_plan, inventory = read_json(audit / "analysis-plan.json"), read_json(audit / "input-hashes.json")
    original = {Path(row["path"]).parts[-4:]: row for row in inventory["inputs"]
                if Path(row["path"]).name in {"report.json", "model-transport.jsonl"}}
    raw_inputs = {}
    for item in audit_plan["inputs"]:
        require(item["cohort"] in COHORTS, "unsupported_cohort")
        for name in ("report.json", "model-transport.jsonl"):
            relative = "/".join((item["cohort"], "episodes", item["episode"], name))
            expected = original[tuple(relative.split("/"))]
            current = file_hash(input_path(root, relative))
            require(current == expected["sha256_before"] == expected["sha256_after"], "raw_input_changed")
            raw_inputs[relative] = current
    selected, expected_selection = study["selected_episodes"], []
    for row in read_json(audit / "episodes-private.json")["episodes"]:
        targets = [a["round"] for a in row["failure_anchors"] if a["kind"] == "analysis" and a["category"] == "TypeError"]
        if targets:
            expected_selection.append((row["cohort"], row["episode"], targets))
    require([(r["cohort"], r["episode_id"], r["target_rounds"]) for r in selected] == expected_selection, "selection_not_audit_complete")
    episodes = []
    for item in selected:
        relative = "/".join((item["cohort"], "episodes", item["episode_id"]))
        entry = {"episode_id": item["episode_id"], "target_rounds": item["target_rounds"],
                 "report": relative + "/report.json", "transport": relative + "/model-transport.jsonl"}
        try:
            bound = _load_episode(root, entry)
            entry.update(episode_manifest(bound))
        except EvidenceGap as exc:
            entry.update(gap=str(exc), budget_seconds=item["episode_active_seconds_cap"],
                         recorded_original_source_sha256=None, calls=[])
        episodes.append(entry)
    # Fixed denominator is a property of this declared diagnostic, not a search.
    require(len(episodes) == 11 and sum(len(r["target_rounds"]) for r in episodes) == 29, "unexpected_study_denominator")
    if not any(r["gap"] for r in episodes):
        require(sum(len(r["calls"]) for r in episodes) == 72, "unexpected_prefix_count")
    plan = {"protocol": PROTOCOL, "study_plan_sha256": file_hash(study_path),
            "budget_mode": "original_total_cap", "attempts_per_episode": 1,
            "required_host_attestation": HOST, "raw_inputs": raw_inputs,
            "episodes": episodes, "limitations": LIMITATIONS}
    require(all(file_hash(input_path(root, p)) == h for p, h in raw_inputs.items()), "raw_input_changed_during_prepare")
    return plan


def precheck(plan, root):
    """Rebind every episode and every public-input hash before first worker."""
    require(plan["protocol"] == PROTOCOL and plan["budget_mode"] == "original_total_cap"
            and plan["attempts_per_episode"] == 1, "unsupported_replay_plan")
    for relative, expected in plan["raw_inputs"].items():
        require(file_hash(input_path(root, relative)) == expected, "raw_input_changed")
    prepared = []
    for item in plan["episodes"]:
        if item["gap"]:
            prepared.append({"episode_id": item["episode_id"], "gap": item["gap"], "calls": [],
                             "target_rounds": item["target_rounds"], "budget_seconds": item["budget_seconds"]})
            continue
        episode = _load_episode(root, item)
        require(episode_manifest(episode) == {k: item[k] for k in ("episode_id", "gap", "budget_seconds", "recorded_original_source_sha256", "calls")}, "frozen_public_input_mismatch")
        prepared.append(episode)
    return prepared


def _comparable(result):
    return {k: result[k] for k in ("ok", "error", "result", "stdout") if k in result}


def replay_episode(episode, executor_factory, clock=time.monotonic, on_event=None):
    """Factory injection is for inert test executors; CLI only uses Bubblewrap."""
    if episode["gap"]:
        events = [
            {"event_id": episode["episode_id"] + ":analysis:round-" + str(n), "round": n,
             "target": True, "status": "input_gap", "original_error": "TypeError",
             "prefix_diverged_before_event": False} for n in episode.get("target_rounds", [])]
        if on_event is not None:
            for event in events:
                on_event(deepcopy(event))
        return {"episode_id": episode["episode_id"], "gap": episode["gap"], "events": events,
                "complete": False, "cleanup_error": None}
    remaining, events, executor = episode["budget_seconds"], [], None
    blocked, prefix_diverged, cleanup_error = None, False, None

    def record(row):
        events.append(row)
        if on_event is not None:
            on_event(deepcopy(row))

    started = clock()
    try:
        try:
            executor = executor_factory(remaining)
        except Exception:
            blocked = "executor_failed"
        remaining = max(0., remaining - max(0., clock() - started))
        for call in episode["calls"]:
            row = {k: call[k] for k in ("event_id", "round", "history_pointer", "target", "input_hashes", "payload_sha256")}
            row.update(original_error=call["original"].get("error"),
                       prefix_diverged_before_event=prefix_diverged)
            # Subtract half the rounding unit conservatively. The logged wall
            # allowance precedes the API request, so it is only an upper cap.
            remaining = min(remaining, max(0., call["logged_active_seconds"] - .0005),
                            max(0., call["logged_wall_seconds"] - .005))
            row["allowance_seconds"] = remaining
            if blocked or remaining <= 0:
                row["status"] = blocked or "budget_exhausted"
                blocked = "namespace_unavailable" if blocked else "budget_exhausted"
                record(row)
                continue
            start = clock()
            try:
                # A fresh RPC JSON object per call preserves original value
                # semantics, including any aliases retained in the namespace.
                result = executor.run(deepcopy(call["payload"]), remaining)
                require(type(result) is dict and type(result.get("ok")) is bool, "invalid_executor_result")
                row.update(status="returned", replay_ok=result["ok"],
                           replay_error=str(result.get("error", ""))[:100] or None,
                           phase=result.get("phase") if result.get("phase") in PHASES else "unknown",
                           candidate_line=result.get("candidate_line") if type(result.get("candidate_line")) is int else None,
                           private_message=str(result.get("message", ""))[:600],
                           replay_result_sha256=digest(_comparable(result)),
                           original_result_sha256=digest(_comparable(call["original"])))
                row["same_recorded_result"] = row["replay_result_sha256"] == row["original_result_sha256"]
                row["same_error_type"] = bool(call["original"].get("error")) and not result["ok"] and result.get("error") == call["original"].get("error")
                prefix_diverged = prefix_diverged or not row["same_recorded_result"]
            except Exception as exc:
                row.update(status="executor_failed", replay_error=type(exc).__name__, phase="executor",
                           candidate_line=None, private_message="Executor failed; no host traceback or stderr copied.")
                blocked = "namespace_unavailable"
                prefix_diverged = True
            finally:
                elapsed = max(0., clock() - start)
                remaining = max(0., remaining - elapsed)
                row.update(active_elapsed_seconds=elapsed, active_seconds_remaining=remaining)
            record(row)
    finally:
        if executor is not None:
            try:
                executor.close()
            except Exception as exc:
                # Cleanup cannot erase returned diagnostics or trigger a retry.
                cleanup_error = type(exc).__name__[:100]
    return {"episode_id": episode["episode_id"], "gap": None,
            "recorded_original_source_sha256": episode["recorded_original_source_sha256"],
            "budget_seconds": episode["budget_seconds"], "events": events,
            "cleanup_error": cleanup_error,
            "complete": cleanup_error is None and all(e["status"] == "returned" for e in events)}


def public_summary(plan, results, *, postcheck=None, execution_finished=False):
    """Construct only integer counts and literal category keys; no raw strings."""
    events = [e for row in results for e in row["events"]]
    targets = [e for e in events if e["target"]]
    errors, phases, statuses = Counter(), Counter(), Counter()
    for event in targets:
        status = event["status"] if event["status"] in STATUSES else "executor_failed"
        statuses[status] += 1
        if event.get("replay_error"):
            errors[event["replay_error"] if event["replay_error"] in ERRORS else "other"] += 1
        if event.get("phase"):
            phases[event["phase"] if event["phase"] in PHASES else "unknown"] += 1
    planned_targets = sum(len(e["target_rounds"]) for e in plan["episodes"])
    if planned_targets > len(targets):
        statuses["not_attempted"] += planned_targets - len(targets)
    cleanup_failures = sum(bool(r.get("cleanup_error")) for r in results)
    valid = (postcheck is not None and postcheck.get("inputs_unchanged") is True
             and postcheck.get("source_unchanged") is True and execution_finished
             and len(results) == len(plan["episodes"]) and cleanup_failures == 0)
    complete = valid and all(r.get("complete") is True for r in results)
    return {"protocol": PROTOCOL, "diagnostic_only": True,
            "status": "complete" if complete else "partial" if valid else "invalid",
            "conclusions_valid": valid,
            "selected_episodes": len(plan["episodes"]),
            "selected_target_events": planned_targets,
            "planned_prefix_calls": sum(len(e["calls"]) for e in plan["episodes"]),
            "episodes_finished": len(results), "episodes_with_cleanup_error": cleanup_failures,
            "episodes_with_input_gap": sum(bool(r["gap"]) for r in results),
            "returned_prefix_calls": sum(e["status"] == "returned" for e in events),
            "targets_same_error_type": sum(bool(e.get("same_error_type")) for e in targets),
            "targets_with_prior_result_divergence": sum(e["prefix_diverged_before_event"] for e in targets),
            "target_status_counts": dict(sorted(statuses.items())),
            "target_error_categories": dict(sorted(errors.items())),
            "target_phase_categories": dict(sorted(phases.items()))}


class BubblewrapExecutor:
    def __init__(self, seconds):
        require(sys.platform == "linux" and bool(shutil.which("bwrap")), "native_bubblewrap_required")
        # Deliberately do not import env.runner, analysis_worker, World modules,
        # API clients, or scoring code into the host process.
        from sle.secure_eval import CandidateProxy
        self.worker = CandidateProxy(Path(__file__).with_name("analysis_worker.py"), "analyze", timeout_s=seconds)

    def run(self, payload, seconds):
        self.worker.deadline = time.monotonic() + seconds
        return self.worker(payload)

    def close(self):
        self.worker.close()


def native_run(root, plan_path, output, approved_plan_sha, approved_source_sha, host):
    require(host == HOST, "required_host_attestation_missing")
    require(sys.version_info >= (3, 10), "python_3_10_or_newer_required")
    require(sys.platform == "linux" and bool(shutil.which("bwrap")), "native_bubblewrap_required")
    require(file_hash(plan_path) == approved_plan_sha, "reviewed_plan_hash_mismatch")
    source = source_fingerprint()
    require(source["sha256"] == approved_source_sha, "reviewed_source_hash_mismatch")
    plan = read_json(plan_path)
    prepared = precheck(plan, root)  # ALL validation precedes first executor.
    output = Path(output).resolve()
    require(not any(output.is_relative_to(input_path(root, cohort)) for cohort in COHORTS), "output_inside_original_cohort")
    output.mkdir(mode=0o700, parents=False, exist_ok=False)
    # Persist even on crash: no automatic second attempt for this frozen plan.
    claim = Path(plan_path).with_suffix(".native-run-claimed.json")
    write_new(claim, {"plan_sha256": approved_plan_sha, "source_sha256": approved_source_sha,
                      "output": str(output), "host_attestation": host, "attempt": 1})
    metadata = {"protocol": PROTOCOL, "execution": "native_candidate_proxy_bubblewrap",
                "host_attestation": host, "host_attestation_is_external_not_machine_authentication": True,
                "python": sys.version, "platform": platform.platform(), "source": source,
                "python_executable_sha256": file_hash(Path(sys.executable).resolve()),
                "bubblewrap_executable_sha256": file_hash(shutil.which("bwrap")),
                "libraries": {name: importlib.metadata.version(name) for name in ("numpy", "scipy")},
                "sandbox": {"network": "unshare-all", "process_creation": "existing seccomp denial",
                            "memory_mb": 4096, "packages": ["numpy", "scipy"], "model_callbacks": False},
                "original_worker_and_runtime_versions": "not separately serialized in original reports; aggregate source digest retained per episode",
                "plan_sha256": approved_plan_sha, "budget_mode": plan["budget_mode"], "limitations": LIMITATIONS}
    write_new(output / "execution-manifest-private.json", metadata)
    results, execution_finished = [], False
    try:
        for index, episode in enumerate(prepared):
            event_index, returned_events = [0], []

            def persist_event(event):
                write_new(output / ("episode-%02d-event-%02d-private.json" % (index, event_index[0])), event)
                event_index[0] += 1
                returned_events.append(event)

            try:
                row = replay_episode(episode, BubblewrapExecutor, on_event=persist_event)
            except BaseException:
                # An external interruption still leaves every completed event
                # available and counted. A SIGKILL may prevent this final receipt;
                # the individual exclusive event files remain the evidence.
                row = {"episode_id": episode["episode_id"], "gap": episode["gap"],
                       "complete": False, "cleanup_error": None,
                       "interrupted": True, "events": returned_events}
                results.append(row)
                write_new(output / ("episode-%02d-private.json" % index), row)
                raise
            results.append(row)
            write_new(output / ("episode-%02d-private.json" % index), row)
            print(json.dumps({"completed_diagnostic_episodes": index + 1}), flush=True)
        execution_finished = True
    finally:
        after = {}
        for path in plan["raw_inputs"]:
            try:
                after[path] = file_hash(input_path(root, path))
            except (EvidenceGap, OSError):
                after[path] = "unreadable_at_postcheck"
        unchanged = after == plan["raw_inputs"]
        try:
            source_after = source_fingerprint()
        except (EvidenceGap, OSError):
            source_after = None
        source_unchanged = source == source_after
        write_new(output / "input-hashes-private.json", {"sha256_before": plan["raw_inputs"],
                  "sha256_after": after, "all_input_hashes_unchanged": unchanged,
                  "all_source_hashes_unchanged": source_unchanged,
                  "source_sha256_before": source["sha256"],
                  "source_sha256_after": source_after["sha256"] if source_after else None})
        write_new(output / "summary-public.json", public_summary(plan, results,
                  postcheck={"inputs_unchanged": unchanged, "source_unchanged": source_unchanged},
                  execution_finished=execution_finished))
        require(unchanged and source_unchanged, "inputs_or_source_changed_during_replay")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("source-fingerprint")
    prep = sub.add_parser("prepare")
    prep.add_argument("--artifact-root", required=True)
    prep.add_argument("--study-plan", required=True)
    prep.add_argument("--output", required=True)
    check = sub.add_parser("precheck")
    check.add_argument("--artifact-root", required=True)
    check.add_argument("--plan", required=True)
    run = sub.add_parser("run-native")
    run.add_argument("--artifact-root", required=True)
    run.add_argument("--plan", required=True)
    run.add_argument("--output", required=True)
    run.add_argument("--reviewed-plan-sha256", required=True)
    run.add_argument("--reviewed-source-sha256", required=True)
    run.add_argument("--host-attestation", required=True)
    args = parser.parse_args(argv)
    if args.command == "source-fingerprint":
        print(json.dumps(source_fingerprint(), sort_keys=True))
    elif args.command == "prepare":
        plan = prepare(args.artifact_root, args.study_plan)
        write_new(Path(args.output), plan)
        print(json.dumps({"plan_sha256": file_hash(args.output), "episodes": len(plan["episodes"]),
                          "prefix_calls": sum(len(e["calls"]) for e in plan["episodes"]),
                          "gaps": sum(bool(e["gap"]) for e in plan["episodes"])}))
    elif args.command == "precheck":
        episodes = precheck(read_json(args.plan), args.artifact_root)
        print(json.dumps({"prechecked_episodes": len(episodes), "candidate_calls": 0}))
    else:
        native_run(args.artifact_root, args.plan, args.output,
                   args.reviewed_plan_sha256, args.reviewed_source_sha256, args.host_attestation)


if __name__ == "__main__":
    main()

"""Bounded model driver: public experiments, isolated analysis, durable API audit."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from urllib.parse import urlencode

from sle.episode_deadline import call_with_deadline
from sle.posttest_transport import PostTestLLMClient
from .protocol import clone, digest


SYSTEM = """You are a scientist investigating an unfamiliar simulated microcosm.
Study it through the supplied public tools. Choose your own research questions,
compare competing explanations, design informative controls and interventions,
and distinguish measurements, predictions, and tentative mechanisms. Give brief
scientific notes, not private deliberation. No particular discovery is required.

Return exactly one JSON object, without Markdown fences, in one of these forms:
{"note":"brief research note", "actions":[{"request_id":"unique-id",
 "operation":"public operation", "arguments":{}}]}
{"note":"brief research note", "analyze":{"code":"Python code"}}

A batch contains 1..64 actions executed SEQUENTIALLY, stops at the first error,
and cannot reference results that have not yet been returned. Use returned vessel
handles in later batches. All vessels share the global clock. Within each batch,
commit or interpret must be the last action. Commit closes exploration forever.
Choose up to six supported, informative paired-effect predictions with explicit
intervals and scope; fresh confirmation checks only those numerical predictions.
Free-text explanations and Discovery Depth are not graded. Do not game interval
width or assert that a passed numerical contrast proves an entire mechanism.
Read the exact claim schema; do not add a 'kind' field to individual claims.
An evaluation_contract or driver_phase in the public prompt takes precedence
over the general claim count and turn guidance here. Respect its required fields.
After confirmation, call interpret with the returned claim_sha256 and an honest
scientific conclusion, including failures and remaining uncertainty.

If analysis is enabled, isolated Python provides numpy/scipy and persistent
variables problem (public description), history (all prior public turns), and
public_files (empty). Assign result to a JSON value; stdout is also returned.
Analysis has no experiment callback, network, source files, or private world state.
Python analysis has 20 seconds of total active execution time per episode;
time waiting for model replies does not consume that analysis budget.
Use batches efficiently. Reserve the penultimate available model turn for commit
and the last for interpretation. You may finish earlier when evidence suffices.
"""


def save_json(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        os.chmod(temporary, 0o600)
        json.dump(value, stream, ensure_ascii=False, allow_nan=False, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


class AuditedWorldClient(PostTestLLMClient):
    """One new ledger per invocation; write a started attempt before any network I/O."""

    def __init__(self, config, directory, max_attempts=32, azure_api_version=None):
        super().__init__(config, max_attempts=max_attempts)
        self.ledger = Path(directory) / "model-transport.jsonl"
        fd = os.open(str(self.ledger), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(fd)
        self.last_response_metadata = {}
        self.azure_api_version = azure_api_version

    def _append(self, record):
        with self.ledger.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, ensure_ascii=False, allow_nan=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())

    def _request_once(self, url, payload, headers, *, stream):
        if self._attempts >= self._max_attempts:
            raise RuntimeError("world transport attempt budget exhausted")
        attempt = self._attempts + 1
        if self.azure_api_version:
            url += "?" + urlencode({"api-version": self.azure_api_version})
        self.last_response_metadata = {}
        # Headers and endpoint are never copied into artifacts. The payload has
        # only public problem/history plus declared decoding parameters.
        self._append({"event": "started", "attempt": attempt, "unix_time": time.time(),
                      "request_sha256": digest(payload), "request": payload})
        try:
            response = super()._request_once(url, payload, headers, stream=stream)
        except BaseException as exc:
            self._append({"event": "failed", "attempt": attempt,
                          "exception_type": type(exc).__name__, "usage": None,
                          "diagnostic": clone(self.last_transport_error)})
            raise
        chunks = [response] if isinstance(response, dict) else [
            json.loads(line[5:].strip()) for line in response.splitlines()
            if line.startswith("data:") and line[5:].strip() != "[DONE]"]
        models, response_ids = set(), set()
        for chunk in chunks:
            for item in (chunk, chunk.get("response", {}), chunk.get("message", {})):
                if not isinstance(item, dict):
                    continue
                if isinstance(item.get("model"), str):
                    models.add(item["model"])
                if isinstance(item.get("id"), str):
                    response_ids.add(item["id"])
        self.last_response_metadata = {"provider_reported_models": sorted(models),
                                       "response_ids": sorted(response_ids)}
        self._append({"event": "returned", "attempt": attempt, **self.last_response_metadata})
        return response


class WorldAnalysis:
    def __init__(self, timeout_s=20):
        from sle.secure_eval import CandidateProxy
        from sle import episode_analysis_worker
        self.worker = CandidateProxy(Path(episode_analysis_worker.__file__),
                                     "analyze", timeout_s=timeout_s)
        self.remaining_seconds = max(0.0, self.worker.deadline - time.monotonic())

    def __call__(self, code, problem, history):
        # CandidateProxy's default deadline is a whole-program wall deadline.
        # In an interactive session, model/network idle time must not consume the
        # analysis allowance. Carry the remaining ACTIVE time across calls; do
        # not grant a fresh budget per call. The worker's CPU limit stays intact.
        self.worker.deadline = time.monotonic() + self.remaining_seconds
        try:
            return self.worker({"code": code, "problem": problem, "history": history, "public_files": {}})
        finally:
            self.remaining_seconds = max(0.0, self.worker.deadline - time.monotonic())

    def close(self):
        self.worker.close()


def parse_turn(raw):
    if not isinstance(raw, str) or len(raw.encode()) > 128000:
        raise ValueError("invalid_model_json")
    value = json.loads(raw, parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite")))
    if not isinstance(value, dict) or set(value) not in ({"note", "actions"}, {"note", "analyze"}):
        raise ValueError("expected_note_and_actions_or_analyze")
    if not isinstance(value["note"], str) or len(value["note"]) > 8000:
        raise ValueError("invalid_note")
    if "analyze" in value:
        item = value["analyze"]
        if (not isinstance(item, dict) or set(item) != {"code"}
                or not isinstance(item["code"], str) or len(item["code"]) > 16000):
            raise ValueError("invalid_analysis")
    else:
        actions = value["actions"]
        if not isinstance(actions, list) or not 1 <= len(actions) <= 64:
            raise ValueError("batch_requires_1_to_64_actions")
        for index, item in enumerate(actions):
            if not isinstance(item, dict) or set(item) != {"request_id", "operation", "arguments"}:
                raise ValueError("invalid_action_envelope")
            if item["operation"] in ("commit", "interpret") and index != len(actions) - 1:
                raise ValueError("terminal_action_must_be_last")
    return value


def run_agent(session, client, directory, *, max_rounds=32, wall_seconds=1800, analysis=None,
              exploration_rounds=None, evaluation_profile=None):
    if type(max_rounds) is not int or not 2 <= max_rounds <= 32:
        raise ValueError("max_rounds must be 2..32")
    if not 1 <= wall_seconds <= 3600:
        raise ValueError("wall_seconds must be 1..3600")
    if exploration_rounds is not None and (type(exploration_rounds) is not int
                                          or not 1 <= exploration_rounds <= max_rounds - 2):
        raise ValueError("exploration_rounds must reserve at least two closing turns")
    if evaluation_profile not in (None, "paired-effects-v2"):
        raise ValueError("unknown world evaluation profile")
    if not isinstance(client, PostTestLLMClient):
        raise ValueError("world agents require a transport with retries disabled")
    if client.transport_summary()["attempts"] != 0:
        raise ValueError("world agents require a fresh client")
    directory = Path(directory)
    history, rounds, stop = [], [], "model_round_limit"
    start = time.monotonic()
    problem = session.describe()
    if evaluation_profile:
        problem["evaluation_contract"] = {
            "profile": evaluation_profile, "max_primary_claims": 3, "replicates_per_arm": 8,
            "required_claim_fields": ["forecast", "evidence_ids"],
            "forecast": "Freeze a central 90% predictive interval for the mean of 8 treatment-control sensor-noise differences. Use forecast={coverage:0.9,interval:[lower,upper]} in each claim. The interval score penalizes width and misses; lower is better.",
            "expected_difference": "Separately specify an effect-consistency band used for the legacy approximate t-interval check. This is not the forecast interval; it can be wider.",
            "scope": "Replication and interval forecasting only. Mechanism, novelty, depth and unseen-condition generalization are unassessed.",
            "evidence": "Each primary claim must cite at least one existing exploration observation ID. Prefer informative independent findings over duplicate claims."}
    problem["driver_turn_contract"] = {
        "exploration_rounds": exploration_rounds, "total_rounds": max_rounds,
        "closure": "After exploration_rounds, only commit is permitted until success, then only interpret. No forced or operator-written claims. Finish earlier if ready."}
    reported_models = set()

    def report():
        result = {"protocol": "sle-world-agent-v1", "requested_model": client.config.model,
                  "provider_reported_models": sorted(reported_models),
                  "decoding": {key: getattr(client.config, key) for key in
                               ("wire", "stream", "max_output_tokens", "chat_max_tokens_field",
                                "temperature", "reasoning_effort", "timeout_seconds")},
                  "limits": {"max_rounds": max_rounds, "wall_seconds": wall_seconds,
                             "max_actions_per_round": 64, "max_prompt_characters": 240000,
                             "exploration_rounds": exploration_rounds},
                  "evaluation_profile": evaluation_profile,
                  "analysis_enabled": analysis is not None, "world_state": session.state,
                  "azure_api_version": getattr(client, "azure_api_version", None),
                  "stop_reason": stop, "elapsed_seconds": time.monotonic() - start,
                  "transport": client.transport_summary(), "usage": clone(client.total_usage),
                  "history": history, "rounds": rounds,
                  "public_report_sha256": session.report()["sha256"],
                  "driver_sha256": __import__("hashlib").sha256(Path(__file__).read_bytes()).hexdigest()}
        result["known_response_usage_lower_bound"] = {
            key: sum((row.get("usage") or {}).get(key) or 0 for row in rounds)
            for key in ("input_tokens", "output_tokens", "total_tokens")}
        save_json(directory / "agent-report.json", result)
        save_json(directory / "public-report.json", session.report())
        save_json(directory / "operator-report.json", session.report(private=True))
        return result

    try:
        for number in range(1, max_rounds + 1):
            remaining = wall_seconds - (time.monotonic() - start)
            if remaining <= 0:
                stop = "wall_limit"
                break
            phase = ("interpret_required" if session.state == "interpreting" else
                     "commit_required" if exploration_rounds is not None and number > exploration_rounds
                     else "exploring")
            prompt = json.dumps({"problem": problem, "analysis_enabled": analysis is not None,
                                 "history": history, "state": session.state,
                                 "driver_phase": phase,
                                 "turn": number, "turns_including_this": max_rounds - number + 1,
                                 "seconds_remaining": round(remaining, 1)}, ensure_ascii=False, separators=(",", ":"))
            if len(prompt) > 240000:
                stop = "context_limit"
                break
            record = {"round": number, "prompt_sha256": digest(prompt), "system_sha256": digest(SYSTEM)}
            rounds.append(record)
            try:
                raw = call_with_deadline(lambda: client.complete(prompt, system=SYSTEM),
                                         min(remaining, client.config.timeout_seconds))
            except Exception as exc:
                record.update(error=type(exc).__name__, usage=clone(client.last_usage),
                              diagnostic=clone(client.last_transport_error))
                stop = "model_request_failed"
                break
            record.update(response=raw, usage=clone(client.last_usage), stop_reason=client.last_stop_reason,
                          metadata=clone(getattr(client, "last_response_metadata", {})))
            reported_models.update(record["metadata"].get("provider_reported_models", []))
            if time.monotonic() - start >= wall_seconds:
                stop = "wall_limit"
                break
            try:
                turn = parse_turn(raw)
            except (ValueError, TypeError, RecursionError):
                history.append({"round": number, "response": raw,
                                "feedback": {"ok": False, "error": "invalid_model_json_or_envelope"}})
                report()
                continue
            entry = {"round": number, **turn, "results": []}
            history.append(entry)
            if phase != "exploring":
                required = "interpret" if phase == "interpret_required" else "commit"
                if "analyze" in turn or any(a["operation"] != required for a in turn["actions"]):
                    entry["results"].append({"ok": False, "error": required + "_required_by_turn_contract"})
                    report()
                    continue
            if "analyze" in turn:
                if analysis is None:
                    entry["results"].append({"ok": False, "error": "analysis_unavailable"})
                else:
                    try:
                        remaining = wall_seconds - (time.monotonic() - start)
                        result = call_with_deadline(
                            lambda: analysis(turn["analyze"]["code"], problem, history[:-1]), remaining)
                        entry["results"].append(clone(result))
                    except Exception as exc:
                        entry["results"].append({"ok": False, "error": "analysis_failure",
                                                 "exception_type": type(exc).__name__})
            else:
                for request in turn["actions"]:
                    if time.monotonic() - start >= wall_seconds:
                        stop = "wall_limit"
                        break
                    profile_error = None
                    if evaluation_profile and request["operation"] == "commit":
                        candidates = request["arguments"].get("claims", []) if isinstance(request["arguments"], dict) else []
                        if (not isinstance(candidates, list) or not 1 <= len(candidates) <= 3
                                or any(not isinstance(c, dict) or "forecast" not in c
                                       or c.get("replicates") != 8 or not c.get("evidence_ids") for c in candidates)):
                            profile_error = "profile_requires_1_to_3_claims_with_forecast_evidence_ids_and_8_replicates"
                    response = ({"ok": False, "error": profile_error} if profile_error else session.step(request))
                    entry["results"].append({"request_id": request["request_id"], **response})
                    if not response.get("ok") or session.state != "exploring":
                        break
            if session.state in ("completed", "infrastructure_error", "budget_exhausted"):
                stop = session.state
            report()
            print(json.dumps({"round": number, "state": session.state, "note": turn["note"],
                              "actions_executed": len(entry["results"]), "spent": session.spent,
                              "attempts": client.transport_summary()["attempts"]}, ensure_ascii=False), flush=True)
            if stop != "model_round_limit":
                break
    except KeyboardInterrupt:
        stop = "operator_interrupted"
        raise
    finally:
        result = report()
    return result

"""One budgeted scientific episode, with frozen predictors and blind verification."""
import hashlib
import json
import math
import time
from pathlib import Path

import numpy as np

from sle.episode_deadline import call_with_deadline
from sle.secure_eval import CandidateProxy, sanitized_candidate_failure
from .microecology.agent import save_json
from .registry import ENVIRONMENTS, load_world
from .scoring import (aggregate_episode, canonical_hash, prediction_metrics,
                      score_contract, validate_submission, verify_claims)
from .task_profiles import get_task_profile
from .presentation_profiles import present_problem, present_system
from .analysis_api import ModelSnapshots, PROTOCOL as SNAPSHOT_PROTOCOL, contract as snapshot_contract


DEFAULT_LIMITS = {
    "rounds": 16, "exploration_rounds": 14, "experiments": 32,
    "experiment_units": 800, "analysis_active_seconds": 60,
    "predictor_seconds_per_spec": 15, "wall_seconds": 900, "panel_count": 8,
    "max_experiments_per_turn": 8,
    "verification_reserve_seconds": 90,
}

SYSTEM = """You are a scientist exploring a computational world through public experiments.
Choose your own research questions. Seek quantitative regularities, informative
interventions and competing explanations, and report what the evidence supports.
No particular discovery or mechanism is required. The implementation and private
evaluation outcomes are unavailable. State uncertainties and limits honestly.

Return exactly ONE JSON object, no Markdown fences, using one of:
{"note":"brief scientific note", "experiments":[{...public experiment spec...}]}
{"note":"brief scientific note", "analyze":{"code":"Python code"}}
{"note":"brief scientific note", "submit":{"predictor_code":"Python source defining predict(spec)", "claims":[...], "explanation":"findings, alternatives, limitations and evidence IDs"}}

Experiments in a batch run sequentially with independently keyed measurement
noise, cost their public units, and start fresh with the SAME fixed hidden world.
Budget is enforced. A rejected spec consumes no experiment but consumes its model
turn. Use <=8 experiments per batch. Only submission is permitted in the closing
phase. Reserve time to freeze executable predictions and quantitative claims.

Analysis is isolated Python with numpy/scipy and persistent variables. It has
problem (public description), records (ALL observations as id/spec/observation/cost),
and history (all previous public turns). Assign result to concise JSON; stdout
also returns. You may fit scientific models from the public data. No network,
simulator import, private file, oracle call, subprocess or future test outcomes.
Each record's observation is a dictionary with axis, channels and values.
For example: y = np.asarray(records[0]["observation"]["values"], dtype=float).
The numeric matrix is observation["values"], not observation itself. Import numpy
as np before this example. Convert NumPy arrays/scalars in result to JSON types
with .tolist() / float() / int(). Analysis errors include a bounded message and
the candidate's line number when available; use them to correct the next call.
Analysis uses a total ACTIVE execution allowance; model idle time is excluded.
The prompt contains an observation catalog and recent results; all older data
remain accessible in records during analysis. Do not infer missing values.

Submission freezes everything. predictor_code must be self-contained with fitted
constants/data, define predict(spec), and return a numeric [rows,channels] array
for any valid public spec. It cannot access the analysis namespace or records
unless you embed needed fitted values in its source. numpy/scipy are available.
Each test starts a fresh sandbox, without access to measurements or simulator.

Claims are optional, up to 3. Each is exactly:
{"id":"c1","statement":"quantitative contrast", "control":{...spec...},
"treatment":{...spec...}, "readout":{"row":1,"channel":"public name"},
"interval":[lower,upper], "evidence_ids":["obs-0001"], "scope":"conditions and caveats"}.
Row is zero-based and must be after t=0. The interval is a central 90% predictive
interval for the mean of eight fresh noisy treatment-minus-control differences.
The public claim_eligibility rules exclude immediate assignment/addition readouts
and directly clamped observables. Use the declared minimum evolution time after
preparation/events, and matched times in dynamical worlds. Temperature contrasts
in equilibrium spin systems are permitted. Prefer effects requiring learned
behavior rather than facts already given by the tool contract.
Read the full score contract. Verification of an effect does not prove a complete
mechanism. Avoid duplicate claims; every omitted claim slot scores zero.
"""

SNAPSHOT_SYSTEM = """
This episode enables the versioned candidate-owned model snapshot API. During
analysis, call save_model(name, version, parameters, predictor_code=None),
read_model(name, version), or list_models(). Parameters must be a finite plain
JSON object; convert NumPy arrays with tolist(). Save returns an immutable receipt
with name, version and sha256. Saving persists immediately even if later analysis
code fails. A changed fit needs a new version; there is no overwrite/latest alias.
The model_snapshot_contract gives exact storage and callback limits.

A saved predictor can read its fitted parameters from the global MODEL. To freeze
it, submit {"model_snapshot":{"name":"fit","version":"v1","sha256":"receipt digest"},
"claims":[...],"explanation":"..."}. If only parameters were saved, add
predictor_code to that submission. The runner binds exactly that snapshot's JSON
to MODEL in a self-contained predictor, executed only in the usual fresh sandbox.
Your saved-model catalog appears each round. No hidden world, seed, target or
filesystem is exposed by this API. The original predictor_code-only form remains
available. A successful save validates storage/syntax, not scientific correctness.
"""


class IsolatedAnalysis:
    def __init__(self, seconds):
        from . import analysis_worker
        self.worker = CandidateProxy(Path(analysis_worker.__file__), "analyze", timeout_s=seconds)
        self.remaining = max(0., self.worker.deadline-time.monotonic())
        self.model_snapshots = None

    def bind_model_snapshots(self, store):
        self.model_snapshots = store

    def run(self, code, problem, records, history):
        self.worker.deadline = time.monotonic() + self.remaining
        try:
            payload = {"code": code, "problem": problem, "records": records, "history": history}
            if self.model_snapshots is not None:
                payload["model_api"] = self.model_snapshots.callbacks()
            return self.worker(payload)
        finally:
            self.remaining = max(0., self.worker.deadline-time.monotonic())

    def close(self):
        self.worker.close()


def source_digest(root=None):
    root = Path(root or Path(__file__).resolve().parents[1])
    h = hashlib.sha256()
    for package in ("env", "sle"):
        for path in sorted((root/package).rglob("*.py")):
            h.update(str(path.relative_to(root)).encode() + b"\0" + path.read_bytes() + b"\0")
    return h.hexdigest()


def _parse(raw):
    if not isinstance(raw, str) or len(raw) > 128000:
        raise ValueError("invalid_response_size")
    value = json.loads(raw, parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite_json")))
    if not isinstance(value, dict) or set(value) not in ({"note", "experiments"}, {"note", "analyze"}, {"note", "submit"}):
        raise ValueError("expected_note_and_exactly_one_of_experiments_analyze_submit")
    if not isinstance(value["note"], str) or len(value["note"]) > 8000:
        raise ValueError("invalid_note")
    return value


def _predict(code_path, spec, seconds):
    worker = CandidateProxy(code_path, "predict", timeout_s=seconds)
    try:
        return worker(spec)
    finally:
        worker.close()


def _compact_result(entry):
    """Keep traces complete on disk and in analysis; only bound the model context."""
    text = json.dumps(entry, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    if len(text) <= 80000:
        return entry
    return {"note": entry.get("note"), "result_omitted_from_prompt": True,
            "reason": "Large output remains available in analysis history and records.",
            "observation_ids": [r["id"] for r in entry.get("observations", [])]}


def run_episode(instance, limits, directory, client, *, analysis_factory=IsolatedAnalysis, predict_fn=_predict):
    directory = Path(directory)
    world, baseline = load_world(instance["environment"], instance["world_seed"])
    start = time.monotonic()
    records, history, rounds, models = [], [], [], set()
    state, stop, infrastructure = "exploring", "model_round_limit", None
    spent, frozen, analysis = 0, None, None
    model_snapshots, frozen_model_snapshot = None, None
    analysis_protocol = instance.get("analysis_protocol", "legacy")
    panels, baseline_panels, claim_report = {}, {}, None
    problem = world.describe()
    task_profile = get_task_profile(instance.get("task_profile", "open_discovery"), world.name) if world.name in ENVIRONMENTS else None
    if task_profile:
        problem["task_profile"] = task_profile
    problem["score_contract"] = score_contract()
    problem["submission_contract"] = {"entrypoint": "predict(spec)", "returns": "values array only; exact public channel order", "claim_count": "0..3", "claim_replicates_per_arm": 8}
    presentation = instance.get("presentation_profile", "full_description")
    problem = present_problem(problem, presentation, environment=world.name)
    system = present_system(SYSTEM, presentation)
    if analysis_protocol == SNAPSHOT_PROTOCOL:
        problem["model_snapshot_contract"] = snapshot_contract()
        system += SNAPSHOT_SYSTEM
    result = {}

    def snapshot():
        usage_keys = ("input_tokens", "output_tokens", "total_tokens")
        known_usage = {key: sum((r.get("usage") or {}).get(key) or 0 for r in rounds) for key in usage_keys}
        complete = state == "completed"
        numerical_claims = claim_report["verified_nonzero_effects"] if claim_report else 0
        scored = aggregate_episode(panels, claim_report) if complete else {"score": None if infrastructure else 0., "subscores": None}
        result.update({"episode_id": instance["episode_id"], "environment": world.name, "world_version": world.version,
                       "cohort": instance.get("cohort", "unspecified"), "requested_model": client.config.model,
                       "task_profile": instance.get("task_profile", "open_discovery"),
                       "presentation_profile": presentation, "public_problem_sha256": canonical_hash(problem),
                       "public_system_sha256": canonical_hash(system),
                       "decoding": {k: getattr(client.config, k, None) for k in ("wire", "stream", "max_output_tokens", "chat_max_tokens_field", "temperature", "reasoning_effort", "timeout_seconds")},
                       "provider_reported_models": sorted(models), "status": state, "stop_reason": stop,
                       "infrastructure_failure": infrastructure, "model_completed": complete,
                       "verified_nonzero_effects": numerical_claims, "has_verified_effect": numerical_claims > 0,
                       "limits": limits, "experiment_count": len(records), "experiment_units": spent,
                       "analysis_seconds_remaining": analysis.remaining if analysis else None,
                       "elapsed_seconds": time.monotonic()-start, "usage": client.total_usage,
                       "known_response_usage_lower_bound": known_usage, "transport": client.transport_summary(),
                       "score": scored["score"], "subscores": scored["subscores"],
                       "panels": panels, "baseline_panels": baseline_panels, "claim_verification": claim_report,
                       "discovery_depth": {"status": "requires_evidence_review", "automatic_mechanism_certification": False},
                       "source_sha256": source_digest(), "submission_sha256": canonical_hash(frozen) if frozen else None,
                       "analysis_protocol": analysis_protocol,
                       "model_snapshots": model_snapshots.catalog() if model_snapshots else [],
                       "frozen_model_snapshot": frozen_model_snapshot,
                       "rounds": rounds, "history": history, "records": records})
        save_json(directory/"report.json", result)
        return result

    try:
        if analysis_protocol not in ("legacy", SNAPSHOT_PROTOCOL):
            raise ValueError("unsupported analysis protocol")
        for kind, expected in instance.get("panel_hashes", {}).items():
            if canonical_hash(world.panel(instance["panel_seed"], kind, limits["panel_count"])) != expected:
                raise ValueError("precommitted panel hash mismatch")
        try:
            if analysis_protocol == SNAPSHOT_PROTOCOL:
                directory.mkdir(parents=True, exist_ok=True)
                model_snapshots = ModelSnapshots(directory / "model-snapshots")
            analysis = analysis_factory(limits["analysis_active_seconds"])
            if model_snapshots is not None:
                analysis.bind_model_snapshots(model_snapshots)
        except Exception as exc:
            infrastructure, stop, state = "analysis_sandbox_initialization", type(exc).__name__, "failed"
            return snapshot()
        for number in range(1, limits["rounds"]+1):
            remaining = limits["wall_seconds"] - (time.monotonic()-start) - limits.get("verification_reserve_seconds", 0)
            if remaining <= 0:
                stop = "model_wall_limit"
                break
            closing = number > limits["exploration_rounds"] or remaining < 100
            catalog = [{k: r[k] for k in ("id", "spec", "cost")} for r in records]
            prompt = {"problem": problem, "limits": limits, "round": number,
                      "rounds_including_this": limits["rounds"]-number+1,
                      "phase": "submit_required" if closing else "exploring",
                      "budget": {"experiments_remaining": limits["experiments"]-len(records),
                                 "units_remaining": limits["experiment_units"]-spent,
                                 "analysis_active_seconds_remaining": round(analysis.remaining, 3),
                                 "wall_seconds_remaining": round(remaining, 2)},
                      "observation_catalog": catalog,
                      "research_notes": [{"round": r["round"], "note": r.get("note", ""), "outcome": r.get("outcome", "")} for r in history],
                      "recent_results": [_compact_result(r) for r in history[-2:]]}
            if model_snapshots is not None:
                prompt["model_snapshots"] = model_snapshots.catalog()
            encoded = json.dumps(prompt, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
            if len(encoded) > 260000:
                stop = "model_context_budget"
                break
            row = {"round": number, "prompt_sha256": canonical_hash(prompt), "system_sha256": canonical_hash(system)}
            rounds.append(row)
            try:
                raw = call_with_deadline(lambda: client.complete(encoded, system=system), min(remaining, client.config.timeout_seconds+65))
            except Exception as exc:
                row.update(error=type(exc).__name__, usage=client.last_usage, diagnostic=client.last_transport_error)
                # Empty/invalid/truncated model text is a model outcome; HTTP,
                # network and wire failures are provider/transport outcomes.
                infrastructure = "api_transport_or_provider" if client.last_transport_error else "request_execution"
                stop, state = "api_request_failed", "failed"
                break
            row.update(response=raw, usage=client.last_usage, provider=client.last_response_metadata,
                       finish_reason=client.last_stop_reason)
            models.update(client.last_response_metadata.get("provider_reported_models", []))
            if models and models != {client.config.model}:
                infrastructure, state, stop = "provider_model_mismatch", "failed", "unexpected_provider_model"
                break
            turn = {"round": number}
            try:
                value = _parse(raw)
                turn["note"] = value["note"]
                if closing and "submit" not in value:
                    raise ValueError("submission_required_in_closing_phase")
                if "experiments" in value:
                    specs = value["experiments"]
                    if not isinstance(specs, list) or not 1 <= len(specs) <= limits["max_experiments_per_turn"]:
                        raise ValueError("experiments_requires_1_to_8_specs")
                    turn["observations"] = []
                    for spec in specs:
                        if len(records) >= limits["experiments"]:
                            raise ValueError("experiment_count_exhausted")
                        spec = world.validate(spec)
                        cost = world.cost(spec)
                        if spent+cost > limits["experiment_units"]:
                            raise ValueError("experiment_units_exhausted")
                        obs_id = "obs-%04d" % (len(records)+1)
                        obs = world.run(spec, noise_key=instance["episode_id"]+":"+obs_id)
                        record = {"id": obs_id, "spec": spec, "observation": obs, "cost": cost}
                        records.append(record)
                        spent += cost
                        turn["observations"].append(record)
                    turn["outcome"] = "observed " + ", ".join(r["id"] for r in turn["observations"])
                elif "analyze" in value:
                    action = value["analyze"]
                    if not isinstance(action, dict) or set(action) != {"code"} or not isinstance(action["code"], str) or len(action["code"]) > 32000:
                        raise ValueError("invalid_analysis_code")
                    try:
                        analysis.remaining = min(analysis.remaining, max(0., limits["wall_seconds"]-(time.monotonic()-start)-limits.get("verification_reserve_seconds", 0)))
                        turn["analysis"] = analysis.run(action["code"], problem, records, history)
                    except Exception as exc:
                        turn["analysis"] = {"ok": False, "error": sanitized_candidate_failure(exc)}
                    turn["outcome"] = "analysis_ok" if turn["analysis"].get("ok") else "analysis_failed"
                else:
                    proposal, binding = (model_snapshots.resolve_submission(value["submit"])
                                         if model_snapshots else (value["submit"], None))
                    frozen = validate_submission(proposal, world, records)
                    save_json(directory/"submission.json", frozen)
                    code_path = directory/"predictor.py"
                    code_path.write_text(frozen["predictor_code"], encoding="utf-8")
                    frozen_model_snapshot = binding
                    if model_snapshots is not None:
                        model_snapshots.seal()
                    state, stop = "frozen", "submitted"
                    turn["outcome"] = "submission_frozen"
            except (ValueError, TypeError, KeyError, OverflowError) as exc:
                turn["outcome"] = "invalid_action"
                turn["error"] = str(exc)[:400]
            history.append(turn)
            snapshot()
            if frozen is not None:
                break
        if frozen is None:
            if state != "failed":
                state = "incomplete"
            return snapshot()
        # All test specifications and outcomes are generated only after freeze.
        # Private panel seeds are separately frozen in the operator manifest.
        save_json(directory/"instance-private.json", instance)
        failure = False
        for kind in ("conditions", "interventions"):
            panels[kind], baseline_panels[kind] = [], []
            for index, spec in enumerate(world.panel(instance["panel_seed"], kind, limits["panel_count"])):
                truth = world.run(spec)
                try:
                    remaining = limits["wall_seconds"]-(time.monotonic()-start)
                    if remaining <= 0:
                        raise TimeoutError("episode verification time exhausted")
                    predicted = predict_fn(directory/"predictor.py", spec, min(limits["predictor_seconds_per_spec"], remaining))
                    metrics = prediction_metrics(predicted, truth, world.scales)
                    metrics["valid"] = True
                except Exception as exc:
                    metrics = {"score": 0., "normalized_rmse": None, "valid": False, "error": sanitized_candidate_failure(exc)}
                    failure = True
                panels[kind].append(dict(metrics, index=index, spec=spec, clean_truth=truth))
                baseline_panels[kind].append(dict(prediction_metrics(baseline(records, spec), truth, world.scales), index=index))
        claim_report = verify_claims(world, frozen["claims"], instance["confirmation_key"])
        state, stop = ("invalid_predictor", "predictor_verification_failed") if failure else ("completed", "verified")
        return snapshot()
    except KeyboardInterrupt:
        infrastructure, stop, state = "operator_interrupted", "operator_interrupted", "failed"
        snapshot()
        raise
    except Exception as exc:
        infrastructure, stop, state = "operator_runtime", type(exc).__name__, "failed"
        return snapshot()
    finally:
        if analysis is not None:
            analysis.close()

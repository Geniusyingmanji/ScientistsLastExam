"""Versioned model interaction with independent prospective scientific tasks.

This separate runner has no private prediction-score panel or automatic depth
grade. It never modifies the historical pilot runner. CLI execution requires an
existing shared API ledger with enough capacity for the entire frozen run.
"""
import argparse
from copy import deepcopy
import json
import math
from pathlib import Path
import re
import time

from sle.episode_deadline import call_with_deadline
from sle.secure_eval import CandidateError, sanitized_candidate_failure
from .analysis_api import ModelSnapshots, contract as snapshot_contract
from .prospective import digest
from .prospective_runner import (ProspectiveTask, PrivateJournal, _atomic_json,
                                 _limits as task_limits, TaskBudgetExceeded, CandidateExecutionFailed,
                                 PredictorInfrastructureFailed, PredictorInitializationUnresolved)
from .registry import ENVIRONMENTS, load_world
from .runner import IsolatedAnalysis, source_digest, _compact_result
from .task_profiles import get_task_profile


PROTOCOL = "sle-research-agent-0.1"
DEFAULT_LIMITS = {"rounds": 24, "analysis_seconds": 120.0,
                  "wall_seconds": 1800.0, "max_experiments_per_turn": 8}
SYSTEM = '''You investigate a computational apparatus through experiments.
Choose your scientific question. Develop competing quantitative explanations,
design informative tests, and retain negative evidence and uncertainty. No hidden
answer or named mechanism must be recovered. The task description gives the
instrument and observation contract, not the simulator or an answer menu.

Return exactly one JSON object with a brief "note" and exactly one action:
{"note":"question or reason", "experiments":[{...public spec...}]}
{"note":"analysis purpose", "analyze":{"code":"Python code"}}
{"note":"why this test matters", "preregister":{...prospective request...}}
{"note":"research complete", "finish":{"explanation":"findings, rejected alternatives, uncertainty and scope", "evidence_ids":["observed ID"], "test_ids":["completed test ID"]}}

Experiments start fresh in the SAME hidden instance. All budgets and failed
attempts are retained. There are no automatic retries. A malformed experimental
or preregistration action closes the scientific task. Pure JSON/analysis errors
consume a model turn. The last model turn permits only finish. Finish requires
at least one completed prospective test; an inconclusive result or rejection of
both accounts is a valid scientific outcome, not a reason to invent success.

Analysis is persistent isolated Python with numpy/scipy. It receives problem,
records (all public id/spec/observation records), and history. Measurements are
records[i]["observation"]["values"], a matrix; observation also has axis/channels.
Assign concise JSON to result; convert numpy values to lists/numbers. No World,
network, operator files, new experiments or private targets are accessible.
save_model(name,version,parameters,predictor_code=None), read_model(name,version)
and list_models() persist immutable candidate-owned fits. Saved predictor code
may read its parameters through global MODEL. Saving alone is not validation.

Preregistration supplies exactly two rivals, each a scientific account with id,
rationale, evidence_ids, tolerance and self-contained predictor_code defining
predict(spec), returning the entire values matrix. Alternatively replace its
predictor_code with model_snapshot={name,version,sha256}; optionally provide code
with the reference to bind saved parameters to new code. Every prediction runs
in a fresh sandbox with no analysis variables. Do not refit using a target and
call its residual a prospective prediction.

The request also has profile (mechanism_discrimination or regime_transfer),
scope, experiments (one or two {id,role:target|reference,spec}), readout (one to
four {experiment_id,row,channel,weight}), replicates (4..16), revision_of (null
initially), and change_note (empty initially). All experiments contribute to the
readout. A readout is sum(weight*measurement/public_channel_scale); weights are
nonzero in [-1,1]. Observe at positive coordinates. Cite prior observation IDs.
Targets must be unobserved at the selected readout; regime transfer also requires
new controls. Two genuinely different plausible accounts are scientifically
useful; arbitrary bad predictors do not establish a mechanism discovery.

The host seals both full predictions, source, design, tolerance and replication
count BEFORE independent target observations. It uses fixed conservative noise
and bias bounds, fixed family alpha split over the maximum number of tests, and
does not stop early. Tolerance at most 0.2*sum(abs(weights)); above 0.05 times
that sum is too wide for the scoped discrimination endpoint. Adequacy requires
the whole data uncertainty interval inside a model's tolerance band; mere
nonrejection is insufficient. Distinguishing two programs is not identifying a
unique mechanism or certifying discovery depth. Limits and assumptions matter.

For revision, cite the prior test in revision_of and explain the change. Keep
one refuted rival's original source unchanged, cite its new counterexample data
for the revised account, and select a new target. The old failure remains.
Fresh observations and test results appear in public history and records.
'''


def _driver_limits(changes=None):
    if changes is not None and (type(changes) is not dict or set(changes) - set(DEFAULT_LIMITS)):
        raise ValueError("unknown research limit")
    result = dict(DEFAULT_LIMITS, **(changes or {}))
    for key, value in result.items():
        try:
            valid = type(value) in (int, float) and math.isfinite(value) and value > 0
        except OverflowError:
            valid = False
        if not valid:
            raise ValueError("invalid research limit")
    if type(result["rounds"]) is not int or not 2 <= result["rounds"] <= 64:
        raise ValueError("rounds must be 2..64")
    if (type(result["max_experiments_per_turn"]) is not int or
            not 1 <= result["max_experiments_per_turn"] <= 8 or
            result["analysis_seconds"] > 600 or result["wall_seconds"] > 7200):
        raise ValueError("research limit exceeds capacity")
    return result


def _research_profile(name, environment):
    profile = get_task_profile(name, environment)
    # The catalog's last paragraph and submission contract belong to the legacy
    # score-panel runner. Keep its scientific question/checklist, not conflicting
    # predictor_code/claims submission instructions in this new interaction.
    profile["public_prompt"] = profile["public_prompt"].split("\n\n", 1)[0] + (
        "\n\nUse the research runner's experiments/analyze/preregister/finish actions. "
        "Finish with explanation, evidence_ids and completed test_ids; no private "
        "prediction-score panel or automatic depth grade is used.")
    profile["submission_contract"] = {"action": "finish", "fields": ["explanation", "evidence_ids", "test_ids"],
                                      "minimum_completed_prospective_tests": 1}
    profile["adapted_for"] = PROTOCOL
    return profile


def create_manifest(episode_id, environment, seed, *, profile="open_discovery",
                    limits=None, science_limits=None):
    if not isinstance(episode_id, str) or not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,79}", episode_id):
        raise ValueError("invalid research identifier")
    if environment not in ENVIRONMENTS or type(seed) is not int or not 0 <= seed < 2**63:
        raise ValueError("invalid research instance")
    configured = _driver_limits(limits)
    science = task_limits(science_limits)
    if science["wall_seconds"] > configured["wall_seconds"]:
        raise ValueError("science wall allowance exceeds research allowance")
    world, _ = load_world(environment, seed)
    manifest = {"protocol": PROTOCOL, "episode_id": episode_id, "environment": environment,
                "private_world_seed": seed, "profile": _research_profile(profile, environment),
                "limits": configured, "science_limits": science,
                "source_sha256": source_digest(), "system_sha256": digest(SYSTEM),
                "public_description_sha256": digest(world.describe()),
                "snapshot_contract": snapshot_contract(), "requested_model": "gpt-5.6-sol",
                "decoding": {"wire": "chat", "reasoning_effort": "medium", "max_output_tokens": 8000,
                             "chat_max_tokens_field": "max_completion_tokens", "temperature": None,
                             "stream": False, "timeout_seconds": 180},
                "score": None, "automatic_depth_certification": False}
    manifest["sha256"] = digest(manifest)
    return manifest


def validate_manifest(manifest):
    if type(manifest) is not dict:
        raise ValueError("invalid research manifest")
    try:
        expected = create_manifest(manifest["episode_id"], manifest["environment"], manifest["private_world_seed"],
                                   profile=manifest["profile"]["name"], limits=manifest["limits"],
                                   science_limits=manifest["science_limits"])
    except (KeyError, TypeError, ValueError, OverflowError):
        raise ValueError("invalid research manifest") from None
    if manifest != expected:
        raise ValueError("research source, manifest or public contract changed after freeze")


def _parse(raw):
    if not isinstance(raw, str) or len(raw.encode("utf-8")) > 192000:
        raise ValueError("response size exceeded")
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result
    def finite_float(text):
        value = float(text)
        if not math.isfinite(value):
            raise ValueError("nonfinite JSON")
        return value
    value = json.loads(raw, object_pairs_hook=pairs, parse_float=finite_float,
                       parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite JSON")))
    actions = ("experiments", "analyze", "preregister", "finish")
    if type(value) is not dict or not any(set(value) == {"note", action} for action in actions):
        raise ValueError("expected note and exactly one research action")
    if not isinstance(value["note"], str) or len(value["note"]) > 8000:
        raise ValueError("invalid research note")
    # Reject finite-overflow values and unpaired surrogates before any operator
    # JSON artifact write can turn candidate data into a storage failure.
    if len(json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8")) > 192000:
        raise ValueError("parsed action size exceeded")
    return value


def _resolve_rivals(request, snapshots):
    request = deepcopy(request)
    if type(request) is not dict or type(request.get("rivals")) is not list:
        raise ValueError("missing rival list")
    bindings = []
    for rival in request["rivals"]:
        if type(rival) is not dict:
            raise ValueError("invalid rival")
        if "model_snapshot" in rival:
            proposal = {"model_snapshot": rival.pop("model_snapshot"), "claims": [], "explanation": ""}
            if "predictor_code" in rival:
                proposal["predictor_code"] = rival["predictor_code"]
            resolved, binding = snapshots.resolve_submission(proposal)
            rival["predictor_code"] = resolved["predictor_code"]
            bindings.append({"rival_id": rival.get("id"), "binding": binding})
    return request, bindings


def _final(value, records, tests):
    if type(value) is not dict or set(value) != {"explanation", "evidence_ids", "test_ids"}:
        raise ValueError("finish needs explanation, evidence_ids and test_ids")
    if not isinstance(value["explanation"], str) or not 1 <= len(value["explanation"]) <= 16000:
        raise ValueError("invalid final explanation")
    for name, allowed in (("evidence_ids", {r["id"] for r in records}),
                          ("test_ids", {t["test_id"] for t in tests})):
        values = value[name]
        if (type(values) is not list or not 1 <= len(values) <= 512 or
                any(not isinstance(v, str) or v not in allowed for v in values) or
                len(values) != len(set(values))):
            raise ValueError("invalid or unknown final " + name)
    return deepcopy(value)


class _DriverStorageError(RuntimeError):
    pass


class _AnalysisOperatorError(RuntimeError):
    pass


class _ResearchSnapshots(ModelSnapshots):
    """Retain trusted persistence failures even when a worker catches them.

    A candidate may catch a save_model callback error itself. The operator must
    still distinguish a failed disk publication from invalid candidate input.
    This flag is never part of the callback's or sandbox's public authority.
    """
    persistence_failed = False

    def _persist(self, source_hash, encoded):
        try:
            return super()._persist(source_hash, encoded)
        except Exception:
            self.persistence_failed = True
            raise


class _DeadlineTask(ProspectiveTask):
    """Enforce the parent deadline inside each existing bounded oracle call.

    An outer signal deadline would conflict with the simulator's own deadline.
    This narrows the existing clock without changing frozen science allowances.
    """
    def __init__(self, *args, research_deadline, **kwargs):
        self._research_deadline = research_deadline
        super().__init__(*args, **kwargs)

    def _remaining_wall(self):
        return min(super()._remaining_wall(), self._research_deadline - time.monotonic())


def run_research(manifest, directory, client_factory, *, analysis_factory=IsolatedAnalysis):
    """Run once with a trusted single-attempt client factory; no retry/resume.

    A scientific input/program failure is a model outcome. Operator persistence,
    setup, unexpected execution and cleanup failures are infrastructure failures.
    Only bounded error categories, never operator exception messages, go back to
    the model. All attempted requests/actions and valid partial evidence remain.
    """
    validate_manifest(manifest)
    manifest = deepcopy(manifest)
    directory = Path(directory).absolute()
    directory.mkdir(mode=0o700, parents=False)  # Existing paths fail before clients.
    limits, started = manifest["limits"], time.monotonic()
    deadline = started + limits["wall_seconds"]
    history, rounds, models, cleanup_errors = [], [], set(), []
    task = analysis = snapshots = client = journal = None
    state, stop, infrastructure, final = "incomplete", "model_budget", None, None
    analysis_remaining = float(limits["analysis_seconds"])
    usage = {"model_request_attempts": 0, "research_action_attempts": 0,
             "analysis_attempts": 0, "analysis_seconds_actual": 0.0, "analysis_startup_seconds": 0.0}

    def write(path, value, **kwargs):
        try:
            _atomic_json(path, value, **kwargs)
        except Exception:
            raise _DriverStorageError("artifact_persistence_failed") from None

    def append(kind, payload):
        try:
            journal.append(kind, payload)
        except Exception:
            raise _DriverStorageError("artifact_persistence_failed") from None

    def remaining():
        return min(deadline - time.monotonic(), task._remaining_wall() if task else float("inf"))

    def infrastructure_failed(category):
        nonlocal state, stop, infrastructure
        state, stop = "failed", category
        infrastructure = infrastructure or category

    try:
        write(directory / "manifest-private.json", manifest)
        journal = PrivateJournal(directory / "driver-receipts")
        append("research_created", {"manifest_sha256": manifest["sha256"]})
        task = _DeadlineTask(manifest["environment"], manifest["private_world_seed"], directory / "science",
                             limits=manifest["science_limits"], research_deadline=deadline)
        snapshots = _ResearchSnapshots(directory / "models")
        problem = task.describe()
        problem.update(research_profile=manifest["profile"], model_snapshot_contract=snapshot_contract())
        if remaining() <= 0:
            raise TaskBudgetExceeded("wall budget exhausted before analysis setup")
        analysis_start = time.monotonic()
        try:
            analysis = analysis_factory(min(analysis_remaining, remaining()))
        finally:
            usage["analysis_startup_seconds"] = time.monotonic() - analysis_start
            analysis_remaining = max(0., analysis_remaining - usage["analysis_startup_seconds"])
            if analysis is not None:
                analysis_remaining = min(analysis_remaining, max(0., analysis.remaining))
        analysis.bind_model_snapshots(snapshots)
        transport = directory / "transport"
        transport.mkdir(mode=0o700)
        client = client_factory(transport)
        if (client.config.model != manifest["requested_model"] or
                any(getattr(client.config, key) != value for key, value in manifest["decoding"].items())):
            raise ValueError("client configuration differs from frozen manifest")
        for number in range(1, limits["rounds"] + 1):
            if remaining() <= 0:
                stop = "wall_budget"
                break
            records = task.public_records()
            prompt = {"problem": deepcopy(problem), "round": number, "rounds_including_this": limits["rounds"] - number + 1,
                      "phase": "finish_required" if number == limits["rounds"] else "research",
                      "observation_catalog": [{"id": r["id"], "spec": r["spec"]} for r in records],
                      "scientific_task": task.public_report(), "model_snapshots": snapshots.catalog(),
                      "analysis_seconds_remaining": analysis_remaining, "wall_seconds_remaining": max(0., remaining()),
                      "research_notes": [{"round": r["round"], "note": r.get("note", ""),
                                          "outcome": r.get("outcome", "")} for r in history],
                      "recent_results": [_compact_result(r) for r in history[-2:]]}
            encoded = json.dumps(prompt, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
            if len(encoded.encode("utf-8")) > 260000:
                stop = "context_capacity"
                break
            row = {"round": number, "prompt_sha256": digest(prompt), "system_sha256": digest(SYSTEM)}
            rounds.append(row)
            usage["model_request_attempts"] += 1
            append("model_request_started", dict(row, prompt=prompt))
            # A failed later call must not inherit the previous call's token use.
            client.last_usage, client.last_response_metadata, client.last_stop_reason = None, {}, None
            try:
                raw = call_with_deadline(lambda: client.complete(encoded, system=SYSTEM),
                                         min(remaining(), client.config.timeout_seconds + 65))
            except Exception as error:
                row.update(error=type(error).__name__, usage=deepcopy(getattr(client, "last_usage", None)))
                append("model_request_failed", row)
                if remaining() <= 0:
                    state, stop = "incomplete", "wall_budget"
                else:
                    infrastructure_failed("model_transport_error")
                break
            metadata = deepcopy(client.last_response_metadata)
            if (not isinstance(metadata, dict) or not isinstance(metadata.get("provider_reported_models", []), list) or
                    any(not isinstance(name, str) for name in metadata.get("provider_reported_models", []))):
                raise RuntimeError("invalid provider metadata")
            try:
                raw_storable = isinstance(raw, str) and len(raw.encode("utf-8")) <= 192000
            except UnicodeError:
                raw_storable = False
            row.update(response=raw if raw_storable else None, usage=deepcopy(client.last_usage), provider=metadata,
                       finish_reason=client.last_stop_reason)
            if not raw_storable:
                row["response_rejected"] = "invalid_response_size_or_encoding"
            append("model_response_returned", row)
            models.update(metadata.get("provider_reported_models", []))
            if models and models != {manifest["requested_model"]}:
                infrastructure_failed("provider_model_mismatch")
                break
            turn, action = {"round": number}, None
            terminal, scientific_attempt_before = False, None
            try:
                if remaining() <= 0:
                    raise TaskBudgetExceeded("wall budget exhausted after model response")
                try:
                    value = _parse(raw)
                except (ValueError, TypeError, RecursionError, UnicodeError, OverflowError):
                    turn.update(outcome="invalid_action_json", error="invalid_json_action")
                    value = None
                if value is not None:
                    action = next(key for key in ("experiments", "analyze", "preregister", "finish") if key in value)
                    turn["note"] = value["note"]
                    usage["research_action_attempts"] += 1
                    append("research_action", {"round": number, "action": value})
                    if number == limits["rounds"] and action != "finish":
                        # Phase rejection does not dispatch a scientific action.
                        turn.update(outcome="invalid_action", error="last_turn_requires_finish")
                        action = None
                    elif action == "experiments":
                        specs = value["experiments"]
                        if type(specs) is not list or not 1 <= len(specs) <= limits["max_experiments_per_turn"]:
                            raise ValueError("invalid experiment batch")
                        turn["observations"] = []
                        for spec in specs:
                            if remaining() <= 0:
                                raise TaskBudgetExceeded("wall budget exhausted in experiment batch")
                            scientific_attempt_before = task.public_report()["usage"]["experiment_attempts"]
                            turn["observations"].append(task.observe_source(spec))
                        turn["outcome"] = "observed"
                    elif action == "analyze":
                        request = value["analyze"]
                        if (type(request) is not dict or set(request) != {"code"} or not isinstance(request["code"], str) or
                                not 1 <= len(request["code"].encode("utf-8")) <= 32000):
                            raise ValueError("invalid analysis code")
                        usage["analysis_attempts"] += 1
                        allowance = min(analysis_remaining, max(0., remaining()))
                        if allowance <= 0:
                            turn["analysis"] = {"ok": False, "error": "analysis_budget_exhausted"}
                        else:
                            analysis.remaining = allowance
                            began = time.monotonic()
                            try:
                                turn["analysis"] = analysis.run(request["code"], deepcopy(problem), deepcopy(records), deepcopy(history))
                            except (CandidateError, TimeoutError) as error:
                                turn["analysis"] = {"ok": False, "error": sanitized_candidate_failure(error)}
                            except Exception:
                                raise _AnalysisOperatorError("isolated_analysis_execution_failed") from None
                            finally:
                                elapsed = time.monotonic() - began
                                usage["analysis_seconds_actual"] += elapsed
                                analysis_remaining = max(0., min(analysis_remaining - elapsed, analysis.remaining))
                        if snapshots.persistence_failed:
                            raise _DriverStorageError("snapshot_persistence_failed")
                        if not isinstance(turn["analysis"], dict) or type(turn["analysis"].get("ok")) is not bool:
                            raise RuntimeError("analysis returned invalid envelope")
                        try:
                            encoded_analysis = json.dumps(turn["analysis"], ensure_ascii=False, allow_nan=False).encode("utf-8")
                            if len(encoded_analysis) > 192000:
                                raise ValueError("analysis output exceeded bound")
                        except (TypeError, ValueError, UnicodeError, RecursionError):
                            turn["analysis"] = {"ok": False, "error": "invalid_analysis_output"}
                        turn["outcome"] = "analysis_ok" if turn["analysis"]["ok"] else "analysis_failed"
                    elif action == "preregister":
                        request, bindings = _resolve_rivals(value["preregister"], snapshots)
                        append("resolved_preregistration", {"request": request, "snapshot_bindings": bindings})
                        scientific_attempt_before = task.public_report()["usage"]["experiment_attempts"]
                        turn["prospective"] = task.preregister(request)
                        turn["observations"] = [r for r in task.public_records() if r["id"] in turn["prospective"]["observation_ids"]]
                        turn["outcome"] = turn["prospective"]["result"]["outcome"]
                    elif action == "finish":
                        proposal = _final(value["finish"], records, task.public_report()["results"])
                        try:
                            snapshots.seal()
                            task.finish()
                        except TaskBudgetExceeded:
                            raise
                        except Exception:
                            # The candidate's final payload has already passed
                            # validation. Failures committing it are operator
                            # failures regardless of their exception class.
                            raise _DriverStorageError("completion_persistence_failed") from None
                        write(directory / "final.json", proposal)
                        final, state, stop = proposal, "completed", "finished"
                        turn["outcome"] = "research_finished"
            except TaskBudgetExceeded:
                state, stop, terminal = "incomplete", "science_or_wall_budget", True
                turn.update(outcome="budget_exhausted", error="science_or_wall_budget")
            except PredictorInfrastructureFailed:
                infrastructure_failed("predictor_infrastructure_failure")
                terminal = True
                turn.update(outcome="operator_failure", error="predictor_infrastructure_failure")
            except PredictorInitializationUnresolved:
                state, stop, terminal = "initialization_unresolved", "predictor_initialization_unresolved", True
                turn.update(outcome="initialization_unresolved", error="predictor_initialization_unresolved")
            except CandidateExecutionFailed as error:
                state, stop, terminal = "invalid_action", "candidate_prediction_failed", True
                # ProspectiveTask has already sanitized this private exception.
                # Reclassifying its underscored label would lose timeout/import
                # categories, so accept only the known bounded labels.
                kinds = {"candidate_timeout", "blocked_or_missing_import", "blocked_operation",
                         "blocked_or_missing_file", "non_finite_candidate_value", "candidate_runtime_error",
                         "candidate_callback_schema_error", "candidate_response_too_large",
                         "candidate_worker_exit", "callback_budget_exhausted"}
                kind = str(error) if str(error) in kinds else "candidate_runtime_error"
                turn.update(outcome="candidate_prediction_failed", error=kind)
            except (ValueError, TypeError, KeyError, UnicodeError, RecursionError):
                turn.update(outcome="invalid_action", error="invalid_" + (action or "research") + "_action")
                terminal = action in ("experiments", "preregister") or task.public_report()["status"] != "active"
                if (scientific_attempt_before is not None and task.public_report()["status"] == "failed" and
                        task.public_report()["usage"]["experiment_attempts"] > scientific_attempt_before):
                    infrastructure_failed("scientific_operator_error")
                    terminal = True
                    turn.update(outcome="operator_failure", error="scientific_operator_error")
                elif terminal:
                    state, stop = "invalid_action", "invalid_scientific_action"
            except Exception:
                infrastructure_failed("action_execution_failed")
                terminal = True
                turn.update(outcome="operator_failure", error="action_execution_failed")
            history.append(turn)
            append("research_action_result", turn)
            write(directory / "history.json", history, replace=True)
            if terminal or state == "completed" or task.public_report()["status"] != "active":
                break
    except TaskBudgetExceeded:
        state, stop = "incomplete", "science_or_wall_budget"
    except Exception:
        infrastructure_failed("driver_execution_failed")
        if journal is not None:
            try:
                append("driver_failed", {"error": "driver_execution_failed"})
            except _DriverStorageError:
                pass
    finally:
        # Each capability closes once even if another cleanup action raises.
        for label, callback in (("analysis_close", analysis.close if analysis else None),
                                ("snapshot_seal", snapshots.seal if snapshots else None)):
            if callback is not None:
                try:
                    callback()
                except Exception:
                    cleanup_errors.append(label)
                    infrastructure_failed("cleanup_failed")
        scientific = None
        if task is not None:
            try:
                if task.public_report()["status"] == "active":
                    reason = "invalid_action" if state == "invalid_action" else "model_transport_error" if stop == "model_transport_error" else "model_budget" if stop in {"model_budget", "wall_budget", "science_or_wall_budget"} else "driver_stopped"
                    task.close(reason)
                scientific = task.public_report()
            except Exception:
                cleanup_errors.append("scientific_task_close")
                infrastructure_failed("cleanup_failed")
                try:
                    scientific = task.public_report()
                except Exception:
                    pass
        try:
            catalog = snapshots.catalog() if snapshots else []
        except Exception:
            catalog = []
            cleanup_errors.append("snapshot_catalog")
            infrastructure_failed("cleanup_failed")
        report = {"protocol": PROTOCOL, "episode_id": manifest["episode_id"], "environment": manifest["environment"],
                  "status": state, "stop_reason": stop, "infrastructure_failure": infrastructure,
                  "failure_attribution": "infrastructure" if infrastructure else "unresolved" if state == "initialization_unresolved" else "model" if state == "invalid_action" else None,
                  "requested_model": manifest["requested_model"], "provider_reported_models": sorted(models),
                  "source_sha256": manifest["source_sha256"], "manifest_sha256": manifest["sha256"],
                  "rounds": rounds, "history": history, "final": final, "usage": usage,
                  "analysis_seconds_remaining": analysis_remaining, "cleanup_errors": cleanup_errors,
                  "model_snapshots": catalog, "scientific_task": scientific,
                  "score": None, "discovery_depth_certified": False,
                  "mechanism_identified": False, "elapsed_seconds": time.monotonic() - started}
        try:
            if journal is not None:
                append("research_closed", {"status": state, "report_sha256": digest(report)})
            write(directory / "report.json", report)
        except _DriverStorageError:
            report.update(status="failed", stop_reason="artifact_persistence_failed", infrastructure_failure="artifact_persistence_failed",
                          failure_attribution="infrastructure")
            # Preserve the partial directory and the in-memory failure report.
            # No overwrite, repair, restarted task, or repeated experiment.
    return report


def _main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    freeze = sub.add_parser("freeze")
    freeze.add_argument("--episode", required=True)
    freeze.add_argument("--environment", choices=ENVIRONMENTS, required=True)
    freeze.add_argument("--seed", type=int, required=True)
    freeze.add_argument("--profile", default="open_discovery")
    freeze.add_argument("--limits", help="JSON object containing driver and/or science overrides")
    freeze.add_argument("--output", required=True)
    run = sub.add_parser("run")
    for name in ("manifest", "model-config", "ledger", "directory"):
        run.add_argument("--" + name, required=True)
    args = parser.parse_args(argv)
    if args.command == "freeze":
        changes = json.loads(Path(args.limits).read_text()) if args.limits else {}
        if set(changes) - {"driver", "science"}:
            raise ValueError("unknown manifest limit section")
        manifest = create_manifest(args.episode, args.environment, args.seed, profile=args.profile,
                                   limits=changes.get("driver"), science_limits=changes.get("science"))
        _atomic_json(Path(args.output), manifest)
        print(json.dumps({"status": "frozen", "manifest_sha256": manifest["sha256"], "model_requests": 0}))
        return 0
    from sle.llm import LLMConfig
    from .ledger import CampaignLedger
    from .transport import CampaignClient
    manifest = json.loads(Path(args.manifest).read_text())
    validate_manifest(manifest)
    if not Path(args.ledger).is_file():
        raise ValueError("research runner requires an existing shared attempt ledger")
    ledger = CampaignLedger(args.ledger)
    if ledger.summary()["remaining_attempts"] < manifest["limits"]["rounds"]:
        raise ValueError("shared ledger cannot cover this frozen research run")
    raw = json.loads(Path(args.model_config).read_text())
    config = LLMConfig.from_dict(raw.get("llm", raw))
    def client_factory(directory):
        return CampaignClient(config, directory, ledger, manifest["episode_id"],
                              max_attempts=manifest["limits"]["rounds"], active_limit=8, rpm=60)
    report = run_research(manifest, args.directory, client_factory)
    print(json.dumps({key: report[key] for key in ("episode_id", "status", "stop_reason", "score")}))
    return 0 if report["status"] == "completed" else 1


def main(argv=None):
    try:
        return _main(argv)
    except Exception as error:
        print(json.dumps({"status": "failed", "error": type(error).__name__}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

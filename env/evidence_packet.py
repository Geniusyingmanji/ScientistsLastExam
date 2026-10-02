"""Read-only, allowlisted public-interaction packets; never execute candidates.

Only stdlib imports are intentional. This module does not import a runner,
world, scorer, sandbox, SDK, or a prospective replay function.
"""
import argparse
from copy import deepcopy
import hashlib
import json
import math
import os
from pathlib import Path
import re


PROTOCOL = "sle-public-evidence-packet-0.1"
MAX_BYTES = 128 * 1024 * 1024
IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,199}\Z")
N, T, B, J = "number", "text", "boolean", "candidate_json"


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def digest(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                            allow_nan=False).encode("utf-8"))


def request_digest(value):
    """AuditedWorldClient's UTF-8 request hash differs from report ASCII JSON."""
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                            ensure_ascii=False, allow_nan=False).encode("utf-8"))


def strict_json(raw):
    """Reject duplicate keys, NaN, overflow, trailing text and invalid UTF-8."""
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result

    def number(text):
        value = float(text)
        if not math.isfinite(value):
            raise ValueError("nonfinite JSON")
        return value

    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", errors="strict")
    if type(raw) is not str or len(raw.encode("utf-8")) > MAX_BYTES:
        raise ValueError("invalid JSON size or encoding")
    value = json.loads(raw, object_pairs_hook=pairs, parse_float=number,
                       parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite JSON")))
    json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8")
    return value


def _project(value, schema, *, exact=False):
    """Positive field/type schema. Unknown envelope fields are never copied.

    J is allowed only at candidate-authored analysis.result, not at an operator
    container. Scientific free-form JSON/text/code is deliberately not redacted.
    """
    if schema == J:
        return strict_json(json.dumps(value, allow_nan=False))
    if schema == N:
        if type(value) not in (int, float) or not math.isfinite(value):
            raise ValueError("expected finite number")
    elif schema == T:
        if type(value) is not str:
            raise ValueError("expected string")
        value.encode("utf-8")
    elif schema == B:
        if type(value) is not bool:
            raise ValueError("expected boolean")
    elif isinstance(schema, list):
        if type(value) is not list:
            raise ValueError("expected array")
        return [_project(item, schema[0], exact=exact) for item in value]
    elif isinstance(schema, tuple):
        if value is None:
            return None
        return _project(value, schema[0], exact=exact)
    elif isinstance(schema, dict):
        if type(value) is not dict or (exact and set(value) - set(schema)):
            raise ValueError("unsupported object schema")
        return {key: _project(value[key], rule, exact=exact)
                for key, rule in schema.items() if key in value}
    else:
        raise ValueError("unknown schema")
    return value


def _id(value):
    if type(value) is not str or IDENTIFIER.fullmatch(value) is None:
        raise ValueError("invalid identifier")
    return value


ECOLOGY = {"initial": {key: N for key in ("A", "B", "C", "nutrient")},
           "temperature_c": N, "times_h": [N],
           "events": [{"time_h": N, "feed": N, "temperature_c": N,
                       "deplete": {"channel": T, "fraction": N}}]}
SPECS = {
    "microecology": ECOLOGY, "microecology_causal": ECOLOGY,
    "coupled_oscillators": {"times": [N], "initial_position": [N], "initial_velocity": [N],
        "mass_add": [N], "damping_add": [N], "cut_edges": [[T]], "clamp": [T],
        "drive": ({"node": T, "amplitude": N, "frequency": N, "phase": N},)},
    "heat_transport": {"times": [N], "probes": [N], "initial_temperature": N,
        "boundary_temperatures": [N], "ambient_temperature": N, "cooling": N, "flow": N,
        "heaters": [{"position": N, "power": N, "width": N}]},
    "reaction_kinetics": {"initial_mM": [N], "temperature_k": N, "times_s": [N],
        "interventions": [{"kind": T, "time_s": N, "temperature_k": N, "amounts_mM": [N]}]},
    "gene_regulation": {"initial_expression": [N], "initial_drive": [N], "times_h": [N],
        "interventions": [{"kind": T, "time_h": N, "drive": [N]}]},
    "ising_spin": {"temperatures": [N], "external_field": [N],
        "clamp": {key: N for key in "ABCDEF"}, "suppress_bonds": [{"nodes": [T], "fraction": N}]},
    "hysteresis_material": {"reset": T, "preparation": [{"duration": N, "field": N}],
        "protocol": [{"time": N, "field": N}], "times": [N]},
    "orbital_dynamics": {"position": [N], "velocity": [N], "times": [N],
        "impulses": [{"time": N, "delta_v": [N]}]},
    "pattern_formation": {"length": N, "drive": N, "times": [N],
        "initial": {"mean": N, "modes": [{"mode": N, "amplitude": N, "phase": N}]}},
    "electrical_impedance": {"frequencies_hz": [N], "source_ohm": N, "load_ohm": N, "amplitude_v": N},
}
AXIS = {
    "microecology": "times_h", "microecology_causal": "times_h",
    "coupled_oscillators": "times", "heat_transport": "times",
    "reaction_kinetics": "times_s", "gene_regulation": "times_h",
    "ising_spin": "temperatures", "hysteresis_material": "times",
    "orbital_dynamics": "times", "pattern_formation": "times",
    "electrical_impedance": "frequencies_hz",
}
# The research runner's inert numeric test fixture is an explicit parser schema,
# not a registered scientific world and never a candidate performance result.
SPECS["prospective_fixture"] = {"drive": N, "times": [N]}
AXIS["prospective_fixture"] = "times"
SNAPSHOT = {"name": T, "version": T, "sha256": T}
READOUT = {"row": N, "channel": T}
OBSERVATION = {"axis": [N], "channels": [T], "values": [[N]]}
FINISH = {"explanation": T, "evidence_ids": [T], "test_ids": [T]}
PUBLIC_CONTRACT = {"environment": T, "world_version": T, "axis_field": T,
                   "channels": [T], "scales": [N], "noise_std": [N], "noise_mean_bias_bound": [N]}
DESIGN = {key: N for key in ("variance_bound_per_replicate", "mean_bias_bound", "confidence_radius",
    "separation_margin", "target_separation_margin", "hard_tolerance_max", "discrimination_tolerance_max")}
DESIGN.update(predicted_readouts=[N], planned_separation=B, wide_tolerance=[B])
PROSPECTIVE_RESULT = {"test_id": T, "scope": T, "design": DESIGN, "mean_readout": N,
    "confidence_interval": [N], "alpha": N, "replicate_readouts": [N],
    "candidates": [{"id": T, "predicted_readout": N, "tolerance_band": [N],
                    "refuted_on_readout": B, "within_tolerance_on_readout": B,
                    "not_refuted_is_not_adequacy": B}],
    "outcome": T, "predictive_discrimination_supported": B,
    "supported_candidate": (T,), "counterexample_candidate_ids": [T]}


def _spec(value, environment):
    result = _project(value, SPECS[environment], exact=True)
    if AXIS[environment] not in result:
        raise ValueError("missing observation axis")
    return result


def _record(value, environment):
    if type(value) is not dict:
        raise ValueError("invalid observation record")
    result = {"id": _id(value["id"]), "spec": _spec(value["spec"], environment),
              "observation": _project(value["observation"], OBSERVATION)}
    observation = result["observation"]
    if (set(observation) != set(OBSERVATION) or not observation["channels"]
            or len(set(observation["channels"])) != len(observation["channels"])
            or observation["axis"] != result["spec"][AXIS[environment]]
            or len(observation["values"]) != len(observation["axis"])
            or any(len(row) != len(observation["channels"]) for row in observation["values"])):
        raise ValueError("observation matrix/axis mismatch")
    return result


def _request_schema(environment):
    return {"profile": T, "scope": T, "rivals": [{"id": T, "rationale": T,
        "evidence_ids": [T], "tolerance": N, "predictor_code": T, "model_snapshot": SNAPSHOT}],
        "experiments": [{"id": T, "role": T, "spec": SPECS[environment]}],
        "readout": [dict(READOUT, experiment_id=T, weight=N)], "replicates": N,
        "revision_of": (T,), "change_note": T}


def _action(raw, environment):
    value = strict_json(raw)
    if type(value) is not dict or not isinstance(value.get("note"), str):
        raise ValueError("missing candidate note")
    # A note-only rejected turn remains useful, but does not become an action.
    if set(value) == {"note"}:
        return value, False
    choices = [name for name in ("experiments", "analyze", "submit", "preregister", "finish") if name in value]
    if len(choices) != 1 or set(value) != {"note", choices[0]}:
        raise ValueError("unsupported candidate action")
    name = choices[0]
    claim = {"id": T, "statement": T, "control": SPECS[environment], "treatment": SPECS[environment],
             "readout": READOUT, "interval": [N], "evidence_ids": [T], "scope": T}
    schemas = {"experiments": [SPECS[environment]], "analyze": {"code": T},
        "submit": {"predictor_code": T, "model_snapshot": SNAPSHOT, "claims": [claim], "explanation": T},
        "preregister": _request_schema(environment), "finish": FINISH}
    payload = _project(value[name], schemas[name], exact=True)
    # Empty/malformed candidates are evidence of a rejected action, not dispatch.
    minimum = {"experiments": None, "analyze": {"code"}, "submit": {"claims", "explanation"},
               "preregister": {"profile", "scope", "rivals", "experiments", "readout", "replicates", "revision_of", "change_note"},
               "finish": set(FINISH)}
    valid = bool(payload) and (minimum[name] is None or minimum[name] <= set(payload))
    if name == "submit":
        valid = valid and bool({"predictor_code", "model_snapshot"} & set(payload))
    return {"note": value["note"], name: payload}, valid


def _analysis(value):
    result = _project(value, {"ok": B, "result": J, "stdout": T, "candidate_line": N,
                              "phase": T, "message": T})
    if "ok" not in result:
        raise ValueError("missing analysis status")
    if "error" in value:
        error = value["error"]
        result["error"] = (_project(error, T) if type(error) is str else
                           _project(error, {"candidate_failure_kind": T, "error_message": T, "timeout": N}))
    return result


def _compatible(requested, canonical):
    """Only test existing fields, never synthesize defaults or normalize controls."""
    if type(requested) is dict and type(canonical) is dict:
        return all(key in canonical and _compatible(value, canonical[key]) for key, value in requested.items())
    if type(requested) is list and type(canonical) is list:
        return len(requested) == len(canonical) and all(_compatible(a, b) for a, b in zip(requested, canonical))
    return requested == canonical


def _driver_bindings(entries, head, actions, environment):
    """Check local journal content/sequence; it is not an external time anchor."""
    if type(entries) is not list or type(head) is not dict:
        raise ValueError("invalid driver journal")
    previous, current, result = None, None, {}
    for sequence, entry in enumerate(entries, 1):
        if (entry.get("protocol") != "sle-prospective-runner-0.1" or entry.get("sequence") != sequence
                or entry.get("previous_sha256") != previous
                or digest({k: v for k, v in entry.items() if k != "sha256"}) != entry.get("sha256")):
            raise ValueError("driver journal chain mismatch")
        previous = entry["sha256"]
        kind, payload = entry["kind"], entry["payload"]
        if kind == "research_action":
            number = payload.get("round")
            current = number if number in actions and payload.get("action") == actions[number] else None
        elif kind == "resolved_preregistration":
            if current is None or current in result or "preregister" not in actions[current]:
                raise ValueError("unbound driver resolution")
            raw = actions[current]["preregister"]
            request = _project(payload["request"], _request_schema(environment), exact=True)
            bindings = payload["snapshot_bindings"]
            by_id = {item["rival_id"]: item["binding"] for item in bindings}
            if len(by_id) != len(bindings) or len(raw["rivals"]) != len(request["rivals"]):
                raise ValueError("ambiguous snapshot resolution")
            canonical = deepcopy(raw)
            public_bindings = []
            for rival, resolved in zip(canonical["rivals"], request["rivals"]):
                if "model_snapshot" not in rival:
                    continue
                reference = rival.pop("model_snapshot")
                binding = by_id[rival["id"]]
                if (any(reference[k] != binding[k] for k in SNAPSHOT)
                        or binding["bound_source_sha256"] != sha256(resolved["predictor_code"].encode("utf-8"))):
                    raise ValueError("snapshot reference or bound source mismatch")
                rival["predictor_code"] = resolved["predictor_code"]
                public_bindings.append({"rival_id": rival["id"],
                    "binding": _project(binding, dict(SNAPSHOT, bound_source_sha256=T))})
            if canonical != request:
                raise ValueError("driver changed candidate scientific request")
            result[current] = {"request": request, "snapshot_bindings": public_bindings}
        elif kind == "research_action_result":
            current = None
    if head.get("sequence") != len(entries) or head.get("sha256") != previous:
        raise ValueError("driver journal head mismatch")
    return result


def _public_contexts(events, rounds):
    """Read only sent chat messages; authenticate against report and request hashes."""
    contexts = {}
    for event in events:
        if type(event) is not dict or event.get("event") != "started":
            continue
        try:
            request = event["request"]
            if request_digest(request) != event["request_sha256"]:
                continue
            messages = request["messages"]
            if (type(messages) is not list or len(messages) != 2
                    or any(type(message) is not dict for message in messages)
                    or [m.get("role") for m in messages] != ["system", "user"]):
                continue
            system = _project(messages[0]["content"], T)
            prompt = strict_json(messages[1]["content"])
            number = prompt["round"]
            rows = [r for r in rounds if type(r) is dict and r.get("round") == number]
            if (type(number) is not int or len(rows) != 1 or digest(prompt) != rows[0].get("prompt_sha256")
                    or digest(system) != rows[0].get("system_sha256") or type(prompt["problem"]) is not dict):
                continue
            # The original problem is intentionally a public scientific payload,
            # not an operator envelope. Do not substitute current world.describe.
            context = {"system": system, "problem": _project(prompt["problem"], J)}
            contexts.setdefault(number, []).append(context)
        except (KeyError, ValueError, TypeError, UnicodeError, OverflowError, RecursionError):
            continue
    return {number: values[0] for number, values in contexts.items() if len(values) == 1}


def _registration(test, response, request, environment, resolved=None):
    """Bind sealed content, not chronology; no predictor/verdict recomputation."""
    registration = test["registration"]
    expected = response["seal_sha256"]
    if (registration["test_id"] != response["test_id"] or registration["seal_sha256"] != expected
            or digest({k: v for k, v in registration.items() if k != "seal_sha256"}) != expected):
        raise ValueError("registration seal does not match report")
    projected = _project(registration, _request_schema(environment))
    # A snapshot's bound source needs the matching local driver journal; source
    # reconstruction/execution is deliberately outside this reader's authority.
    comparable = resolved["request"] if resolved else request
    if not _compatible(comparable, projected):
        raise ValueError("registration not bound to raw candidate request")
    experiments = {item["id"]: _spec(item["spec"], environment) for item in projected["experiments"]}
    if len(experiments) != len(projected["experiments"]):
        raise ValueError("duplicate experiment identifier")
    public = _project(registration["public"], PUBLIC_CONTRACT)
    if (set(public) != set(PUBLIC_CONTRACT) or public.get("environment") != environment
            or public.get("axis_field") != AXIS[environment]
            or any(len(public[key]) != len(public["channels"]) for key in
                   ("scales", "noise_std", "noise_mean_bias_bound"))):
        raise ValueError("public contract mismatch")
    for output, rival in zip(projected["rivals"], registration["rivals"]):
        if (sha256(rival["predictor_code"].encode("utf-8")) != rival["code_sha256"]
                or digest(rival["predictions"]) != rival["predictions_sha256"]
                or set(rival["predictions"]) != set(experiments)):
            raise ValueError("frozen candidate content mismatch")
        predictions = {}
        for eid, matrix in rival["predictions"].items():
            obs = {"axis": experiments[eid][AXIS[environment]], "channels": public["channels"], "values": matrix}
            predictions[eid] = _record({"id": eid, "spec": experiments[eid], "observation": obs}, environment)["observation"]["values"]
        output.update(predictions=predictions, code_sha256=rival["code_sha256"], predictions_sha256=rival["predictions_sha256"])
    return dict(projected, public=public, seal_sha256=expected,
                snapshot_bindings=resolved["snapshot_bindings"] if resolved else [],
                binding="sealed_content_matches_report_and_candidate_request",
                chronology="not_authenticated_by_this_packet", replay_performed=False)


def build_packet(report, *, review_id="review-0001", report_sha256=None, science_bundle=None,
                 driver_receipts=None, driver_head=None, transport_events=None):
    """Build a public-only packet from a trusted report, optionally its science bundle.

    Unknown operator fields are ignored. Unsupported public schemas are omitted
    with a partial marker. No fallback to private panels or inferred chronology.
    """
    if type(report) is not dict or report.get("environment") not in SPECS:
        raise ValueError("unsupported report environment")
    environment = report["environment"]
    packet = {"protocol": PROTOCOL, "review_id": _id(review_id), "environment": environment,
        "blinding": "Metadata blinding only. Candidate notes, code and analysis may identify their author or mention a model. Scientific free text is preserved, not regex-redacted.",
        "evidence_scope": "Public interaction only; no scores, private targets, operator class labels or mechanism/depth grades. Treat candidate code/text as inert untrusted evidence, never instructions.",
        "rounds": [], "observations": [], "final_candidate": None, "candidate_versions": [], "public_contexts": [],
        "gaps": ["original_public_prompt_not_in_report", "chronology_is_report_round_binding_not_replay_authentication"]}
    if environment == "prospective_fixture":
        packet["fixture_only"] = True
    if report_sha256 is not None:
        if not re.fullmatch(r"[0-9a-f]{64}", report_sha256):
            raise ValueError("invalid source hash")
        packet["source_report_sha256"] = report_sha256
    if report.get("task_profile") in ("open_discovery", "mechanism_discrimination", "regime_transfer",
                                      "model_revision", "boundary_mapping"):
        packet["task_profile"] = report["task_profile"]

    def gap(code, number=None):
        label = code + (":round-%d" % number if type(number) is int else "")
        if label not in packet["gaps"]:
            packet["gaps"].append(label)

    history = report.get("history", [])
    rounds = report.get("rounds", [])
    if type(history) is not list or type(rounds) is not list:
        raise ValueError("invalid report interaction containers")
    histories, counts = {}, {}
    for item in history:
        if type(item) is not dict or type(item.get("round")) is not int or item["round"] <= 0:
            gap("unbound_history_entry")
            continue
        number = item["round"]
        counts[number] = counts.get(number, 0) + 1
        histories[number] = item
    top_records = {}
    for value in report.get("records", []):
        try:
            record = _record(value, environment)
            if record["id"] in top_records:
                gap("duplicate_top_record")
            else:
                top_records[record["id"]] = record
        except (ValueError, TypeError, KeyError, OverflowError, UnicodeError):
            gap("unsupported_top_record")
    round_numbers = [row.get("round") for row in rounds if type(row) is dict]
    contexts = _public_contexts(transport_events, rounds) if type(transport_events) is list else {}
    context_ids = {}
    seen, bound = set(), {}
    previous = 0
    tests = {}
    resolved = {}
    if driver_receipts is not None:
        try:
            candidates = {}
            for row in rounds:
                if type(row) is dict and type(row.get("round")) is int and round_numbers.count(row["round"]) == 1:
                    candidates[row["round"]] = _action(row["response"], environment)[0]
            resolved = _driver_bindings(driver_receipts, driver_head, candidates, environment)
        except (ValueError, TypeError, KeyError, OverflowError, UnicodeError):
            gap("driver_resolution_journal_binding_failed")
    if science_bundle is not None:
        try:
            for test in science_bundle["prospective"]["tests"]:
                tid = test.get("test_id")
                if tid in tests:
                    tests[tid] = None
                else:
                    tests[tid] = test
        except (TypeError, KeyError):
            gap("unsupported_science_bundle")
    for raw_round in rounds:
        if type(raw_round) is not dict or type(raw_round.get("round")) is not int or raw_round["round"] <= 0:
            gap("unbound_round_entry")
            continue
        number = raw_round["round"]
        unique = round_numbers.count(number) == 1
        if number <= previous:
            gap("nonmonotonic_or_duplicate_rounds")
        previous = number
        seen.add(number)
        row = {"round": number, "candidate_response": None, "response_state": "unavailable", "observation_ids": []}
        if number in contexts:
            context = contexts[number]
            key = digest(context)
            if key not in context_ids:
                context_ids[key] = "public-context-%04d" % (len(context_ids) + 1)
                packet["public_contexts"].append(dict(context, id=context_ids[key],
                    binding="original_transport_request_user_and_system_hashes_match_report"))
            row["public_context_id"] = context_ids[key]
        elif transport_events is not None:
            gap("original_public_context_binding_unavailable", number)
        raw = raw_round.get("response")
        if type(raw) is str:
            try:
                row["response_sha256"] = sha256(raw.encode("utf-8"))
                row["candidate_response"], valid = _action(raw, environment)
                row["response_state"] = "parsed" if valid else "parsed_but_incomplete_action"
                if not valid:
                    gap("incomplete_action_schema", number)
            except (ValueError, TypeError, KeyError, OverflowError, UnicodeError, RecursionError):
                row["response_state"] = "strict_parse_or_public_schema_failed"
                gap("candidate_response_not_exported", number)
        else:
            gap("candidate_response_missing", number)
        event = histories.get(number) if counts.get(number) == 1 and unique else None
        action = row["candidate_response"] or {}
        if event is None:
            gap("history_round_binding_missing_or_ambiguous", number)
        else:
            row["history_binding"] = "explicit_unique_round_field"
            if type(event.get("note")) is str:
                row["research_note"] = event["note"]
                if action and event["note"] != action.get("note"):
                    gap("candidate_history_note_mismatch", number)
            if type(event.get("outcome")) is str:
                # Outcome is a public action result, not the episode score/status.
                row["public_action_outcome"] = event["outcome"]
            if "analysis" in event:
                try:
                    if "analyze" not in action:
                        raise ValueError("analysis not bound to analysis action")
                    row["analysis"] = _analysis(event["analysis"])
                except (ValueError, TypeError, UnicodeError, OverflowError):
                    gap("analysis_binding_or_schema_failed", number)
            observations = event.get("observations", [])
            if type(observations) is not list:
                observations = []
                gap("invalid_observation_container", number)
            if observations and not ({"experiments", "preregister"} & set(action)):
                gap("observation_action_binding_missing", number)
            for observation_index, value in enumerate(observations):
                try:
                    record = _record(value, environment)
                    rid = record["id"]
                    if rid in bound:
                        gap("duplicate_observation_round_binding", number)
                        continue
                    if rid in top_records and record != top_records[rid]:
                        gap("history_top_record_mismatch", number)
                        continue
                    proposed = action.get("experiments", [])
                    if "preregister" in action:
                        proposed = [item["spec"] for item in action["preregister"].get("experiments", []) if "spec" in item]
                        spec_matches = any(_compatible(item, record["spec"]) for item in proposed)
                    else:
                        spec_matches = (observation_index < len(proposed)
                                        and _compatible(proposed[observation_index], record["spec"]))
                    if not spec_matches:
                        gap("observation_request_spec_binding_unverified", number)
                    bound[rid] = number
                    row["observation_ids"].append(rid)
                    packet["observations"].append(dict(record, round=number,
                        binding="explicit_history_observation" if spec_matches else "history_round_only_request_spec_unverified"))
                except (ValueError, TypeError, KeyError, OverflowError, UnicodeError):
                    gap("unsupported_history_observation", number)
            if "prospective" in event:
                try:
                    response = event["prospective"]
                    if "preregister" not in action:
                        raise ValueError("missing preregistration action")
                    prospective = {"test_id": _id(response["test_id"]),
                        "seal_sha256": _project(response["seal_sha256"], T),
                        "observation_ids": [_id(v) for v in response["observation_ids"]],
                        "result": _project(response["result"], PROSPECTIVE_RESULT)}
                    if prospective["result"].get("test_id") != prospective["test_id"]:
                        raise ValueError("test mismatch")
                    if set(prospective["observation_ids"]) != set(row["observation_ids"]):
                        gap("prospective_observation_binding_incomplete", number)
                    row["prospective"] = prospective
                    test = tests.get(prospective["test_id"])
                    if test is None:
                        gap("full_sealed_predictions_unavailable", number)
                    else:
                        try:
                            prospective["sealed_public_registration"] = _registration(test, response, action["preregister"], environment, resolved.get(number))
                        except (ValueError, TypeError, KeyError, OverflowError, UnicodeError):
                            gap("sealed_registration_binding_failed", number)
                except (ValueError, TypeError, KeyError, OverflowError, UnicodeError):
                    gap("prospective_result_binding_or_schema_failed", number)
            if "submit" in action and event.get("outcome") == "submission_frozen":
                packet["final_candidate"] = {"round": number, "submission": deepcopy(action["submit"]),
                                              "binding": "candidate_submit_and_round_freeze_outcome"}
            if "finish" in action and event.get("outcome") == "research_finished":
                packet["final_candidate"] = {"round": number, "finish": deepcopy(action["finish"]),
                                              "binding": "candidate_finish_and_round_finish_outcome"}
            if "preregister" in action:
                row["candidate_lineage"] = _project(action["preregister"], {"revision_of": (T,), "change_note": T,
                    "rivals": [{"id": T, "evidence_ids": [T], "model_snapshot": SNAPSHOT}]})
        packet["rounds"].append(row)
    for number in histories:
        if number not in seen:
            gap("history_without_response_round", number)
            # Keep public data as explicitly unbound, never invent a missing
            # response or attach it to an adjacent model turn.
            for value in histories[number].get("observations", []):
                try:
                    record = _record(value, environment)
                    if record["id"] not in top_records and record["id"] not in bound:
                        top_records[record["id"]] = record
                except (ValueError, TypeError, KeyError, OverflowError, UnicodeError):
                    gap("unsupported_unbound_history_observation")
    for rid, record in top_records.items():
        if rid not in bound:
            packet["observations"].append(dict(record, round=None, binding="unbound_report_record"))
            gap("unbound_public_records")
    for value in report.get("model_snapshots", []):
        try:
            item = _project(value, dict(SNAPSHOT, has_predictor_code=B))
            if not set(SNAPSHOT) <= set(item):
                raise ValueError("incomplete snapshot receipt")
            packet["candidate_versions"].append(item)
        except (ValueError, TypeError, UnicodeError):
            gap("unsupported_snapshot_receipt")
    if packet["candidate_versions"]:
        gap("snapshot_catalog_has_no_creation_round_or_full_parameter_bodies")
    if packet["final_candidate"] is None:
        gap("no_final_candidate_bound_to_a_round")
    if packet["rounds"] and all("public_context_id" in row for row in packet["rounds"]):
        packet["gaps"].remove("original_public_prompt_not_in_report")
    packet["completeness"] = "partial" if packet["gaps"] else "complete_public_evidence"
    # Strict serialization is a final JSON safety gate, never code validation.
    return strict_json(json.dumps(packet, ensure_ascii=False, allow_nan=False))


def write_packet(report_path, output_path, *, review_id="review-0001", science_bundle_path=None,
                 driver_receipts_path=None, transport_path=None):
    """Exclusive new output, content-hash check of every input before/after."""
    report_path, output_path = Path(report_path), Path(output_path)
    paths = [report_path] + ([Path(science_bundle_path)] if science_bundle_path else [])
    transport_index = len(paths) if transport_path else None
    if transport_path:
        paths.append(Path(transport_path))
    journal_offset = len(paths)
    if driver_receipts_path:
        root = Path(driver_receipts_path)
        entries = sorted(root.glob("[0-9][0-9][0-9][0-9][0-9][0-9].json"))
        if any(path.name != "%06d.json" % i for i, path in enumerate(entries, 1)):
            raise ValueError("driver receipt filenames are not sequential")
        paths.extend(entries + [root/"head.json"])
    if any(path.resolve() == output_path.resolve() for path in paths):
        raise ValueError("output must not replace an input")
    originals = [path.read_bytes() for path in paths]
    values = [[strict_json(line) for line in data.splitlines() if line.strip()] if index == transport_index
              else strict_json(data) for index, data in enumerate(originals)]
    packet = build_packet(values[0], review_id=review_id, report_sha256=sha256(originals[0]),
                          science_bundle=values[1] if science_bundle_path else None,
                          driver_receipts=values[journal_offset:-1] if driver_receipts_path else None,
                          driver_head=values[-1] if driver_receipts_path else None,
                          transport_events=values[transport_index] if transport_index is not None else None)
    if any(path.read_bytes() != original for path, original in zip(paths, originals)):
        raise ValueError("input changed during packet build")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(str(output_path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        json.dump(packet, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
    return {"protocol": PROTOCOL, "review_id": review_id, "source_report_sha256": sha256(originals[0]),
            "packet_sha256": sha256(output_path.read_bytes()), "completeness": packet["completeness"],
            "rounds": len(packet["rounds"]), "public_observations": len(packet["observations"]),
            "input_hashes_unchanged": True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--review-id", default="review-0001")
    parser.add_argument("--science-bundle", type=Path)
    parser.add_argument("--driver-receipts", type=Path)
    parser.add_argument("--transport", type=Path, help="Existing model-transport.jsonl; sent public problem/system only")
    args = parser.parse_args()
    print(json.dumps(write_packet(args.report, args.output, review_id=args.review_id,
                                 science_bundle_path=args.science_bundle, driver_receipts_path=args.driver_receipts,
                                 transport_path=args.transport), indent=2))


if __name__ == "__main__":
    main()

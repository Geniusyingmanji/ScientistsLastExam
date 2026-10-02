"""Fixtures are inert JSON; no world, oracle, candidate or runner is executed."""
from copy import deepcopy
import importlib
import json
from pathlib import Path
import tempfile
import unittest

from env.evidence_packet import build_packet, digest, request_digest, sha256, strict_json, write_packet


SECRET = "OPERATOR_CANARY_91863_PRIVATE_NOT_FOR_REVIEW"
SOURCE = "raise RuntimeError('candidate code must never run in packet builder')\n"


def spec(time=1):
    return {"initial": {"A": .1, "B": .1, "C": .1, "nutrient": 5},
            "times_h": [time], "temperature_c": 30, "events": []}


def record(identifier="obs-1", time=1):
    return {"id": identifier, "spec": spec(time),
            "observation": {"axis": [time], "channels": ["A"], "values": [[.2]]}}


def legacy():
    obs = record()
    return {"environment": "microecology", "requested_model": SECRET,
            "rounds": [{"round": 1, "response": json.dumps({"note": "first", "experiments": [spec()]}), "provider": SECRET},
                       {"round": 2, "response": json.dumps({"note": "fit", "analyze": {"code": SOURCE}})},
                       {"round": 3, "response": json.dumps({"note": "final", "submit": {"predictor_code": SOURCE,
                                                                                              "claims": [], "explanation": "limited"}})}],
            "history": [{"round": 1, "note": "first", "observations": [obs], "outcome": "observed obs-1"},
                        {"round": 2, "note": "fit", "analysis": {"ok": True, "result": {"fit": [.1, .2]}, "stdout": ""}, "outcome": "analysis_ok"},
                        {"round": 3, "note": "final", "outcome": "submission_frozen"}],
            "records": [obs]}


def research():
    rivals = [{"id": name, "rationale": "hypothesis " + name, "evidence_ids": ["obs-1"],
               "tolerance": .01, "predictor_code": SOURCE + "# " + name} for name in ["r1", "r2"]]
    request = {"profile": "mechanism_discrimination", "scope": "limited", "rivals": rivals,
        "experiments": [{"id": "target", "role": "target", "spec": spec(2)}],
        "readout": [{"experiment_id": "target", "row": 0, "channel": "A", "weight": 1}],
        "replicates": 4, "revision_of": None, "change_note": ""}
    registration = deepcopy(request)
    registration.update(test_id="test-1", protocol="sle-prospective-evidence-0.1",
        execution_runtime=SECRET, session_id=SECRET,
        public={"environment": "microecology", "world_version": "test", "axis_field": "times_h",
                "channels": ["A"], "scales": [1], "noise_std": [.002], "noise_mean_bias_bound": [.001]})
    for index, rival in enumerate(registration["rivals"]):
        rival.update(code_sha256=sha256(rival["predictor_code"].encode()), predictions={"target": [[index]]})
        rival["predictions_sha256"] = digest(rival["predictions"])
    registration["seal_sha256"] = digest(registration)
    result = {"test_id": "test-1", "scope": "limited", "mean_readout": .2, "confidence_interval": [.1, .3],
              "alpha": .01, "replicate_readouts": [.2]*4, "candidates": [], "design": {},
              "outcome": "both_candidates_refuted", "counterexample_candidate_ids": ["r1", "r2"], "private_class": SECRET}
    report = legacy()
    report.pop("records")
    report["rounds"] = report["rounds"][:1] + [
        {"round": 2, "response": json.dumps({"note": "frozen predictions", "preregister": request})},
        {"round": 3, "response": json.dumps({"note": "done", "finish": {"explanation": "both failed",
                                                       "evidence_ids": ["obs-2"], "test_ids": ["test-1"]}})}]
    report["history"] = report["history"][:1] + [
        {"round": 2, "observations": [record("obs-2", 2)], "prospective": {
            "test_id": "test-1", "seal_sha256": registration["seal_sha256"],
            "result": result, "observation_ids": ["obs-2"], "noise_key": SECRET}, "outcome": "both_candidates_refuted"},
        {"round": 3, "outcome": "research_finished"}]
    report["protocol"] = "sle-research-agent-0.1"
    report["scientific_task"] = {"limits": SECRET, "receipt_head": SECRET, "usage": SECRET}
    bundle = {"config": SECRET, "prospective": {"tests": [{"test_id": "test-1", "registration": registration,
                    "observations": [{"noise_key": SECRET}], "private_path": SECRET}]}}
    return report, bundle


def snapshot_journal():
    report, bundle = research()
    action = json.loads(report["rounds"][1]["response"])
    resolved = deepcopy(action["preregister"])
    bindings = []
    for rival in action["preregister"]["rivals"]:
        code = rival.pop("predictor_code")
        reference = {"name": rival["id"], "version": "v1", "sha256": "b" * 64}
        rival["model_snapshot"] = reference
        bindings.append({"rival_id": rival["id"], "binding": dict(reference,
                         bound_source_sha256=sha256(code.encode()), private_path=SECRET)})
    report["rounds"][1]["response"] = json.dumps(action)
    entries, previous = [], None
    for kind, payload in [("research_action", {"round": 2, "action": action}),
                          ("resolved_preregistration", {"request": resolved, "snapshot_bindings": bindings}),
                          ("research_action_result", {"round": 2})]:
        entry = {"protocol": "sle-prospective-runner-0.1", "sequence": len(entries)+1,
                 "previous_sha256": previous, "kind": kind, "payload": payload}
        entry["sha256"] = digest(entry); previous = entry["sha256"]; entries.append(entry)
    return report, bundle, entries, {"sequence": len(entries), "sha256": previous}


class EvidencePacketTests(unittest.TestCase):
    def test_legacy_preserves_actions_code_analysis_and_explicit_binding(self):
        source = legacy(); before = deepcopy(source)
        packet = build_packet(source)
        self.assertEqual(source, before)
        for old, new in zip(source["rounds"], packet["rounds"]):
            self.assertEqual(json.loads(old["response"]), new["candidate_response"])
        self.assertEqual(packet["observations"][0]["round"], 1)
        self.assertEqual(packet["final_candidate"]["submission"]["predictor_code"], SOURCE)
        self.assertEqual(packet["rounds"][1]["analysis"]["result"], {"fit": [.1, .2]})
        self.assertEqual(packet["completeness"], "partial")

    def test_operator_canaries_at_every_envelope_do_not_leak(self):
        report = legacy()
        for key in ["provider_reported_models", "private_world_seed", "panel_seed", "confirmation_key", "noise_key",
                    "panels", "baseline_panels", "score", "subscores", "groundtruth_class", "private_path", "config", "decoding"]:
            report[key] = SECRET
        for row in report["rounds"]:
            row.update(config=SECRET, provider={"requested_model": SECRET}, private_path=SECRET)
        for row in report["history"]:
            row.update(config=SECRET, private_path=SECRET)
        for rec in [report["records"][0], report["history"][0]["observations"][0]]:
            rec.update(private_world_seed=SECRET, noise_key=SECRET, config=SECRET)
            rec["observation"].update(clean_truth=SECRET, private_class=SECRET, config=SECRET)
        report["history"][1]["analysis"].update(private_path=SECRET, config=SECRET, provider=SECRET)
        text = json.dumps(build_packet(report))
        self.assertNotIn(SECRET, text)
        self.assertNotIn('"config"', text)

    def test_free_text_identity_and_scientific_json_are_not_regex_destroyed(self):
        report = legacy()
        candidate = json.loads(report["rounds"][1]["response"])
        candidate["note"] = "As Model X, I predict a negative interaction."
        report["rounds"][1]["response"] = json.dumps(candidate)
        report["history"][1]["note"] = candidate["note"]
        report["history"][1]["analysis"]["result"] = {"model_name_in_candidate_output": "Model X"}
        packet = build_packet(report)
        self.assertIn("Model X", json.dumps(packet))
        self.assertIn("Metadata blinding only", packet["blinding"])

    def test_strict_parser_rejects_ambiguous_and_nonfinite_json(self):
        for raw in ['{"a":1,"a":2}', '{"a":NaN}', '{"a":1e999}', '{} trailing', '```json\n{}\n```']:
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                strict_json(raw)
        report = legacy(); report["rounds"][0]["response"] = '{"note":"x","note":"y"}'
        packet = build_packet(report)
        self.assertIsNone(packet["rounds"][0]["candidate_response"])
        self.assertIn("candidate_response_not_exported:round-1", packet["gaps"])

    def test_missing_duplicate_and_orphan_rounds_never_infer_order(self):
        report = legacy(); report["rounds"] = report["rounds"][1:]
        packet = build_packet(report)
        self.assertIsNone(packet["observations"][0]["round"])
        report = legacy(); report["history"].append(deepcopy(report["history"][0]))
        packet = build_packet(report)
        self.assertNotIn("history_binding", packet["rounds"][0])
        self.assertIsNone(packet["observations"][0]["round"])
        report = legacy(); report["rounds"][0]["response"] = None
        self.assertIn("candidate_response_missing:round-1", build_packet(report)["gaps"])

    def test_record_mismatch_and_unknown_spec_fail_closed(self):
        report = legacy(); report["records"] = deepcopy(report["records"])
        report["records"][0]["observation"]["values"][0][0] = 99
        packet = build_packet(report)
        self.assertIn("history_top_record_mismatch:round-1", packet["gaps"])
        self.assertIsNone(packet["observations"][0]["round"])
        report = legacy()
        report["history"][0]["observations"][0]["spec"]["config"] = SECRET
        text = json.dumps(build_packet(report))
        self.assertNotIn(SECRET, text)
        self.assertIn("unsupported_history_observation", text)

    def test_research_full_predictions_project_only_after_matching_seal(self):
        report, bundle = research()
        packet = build_packet(report, science_bundle=bundle)
        text = json.dumps(packet)
        self.assertNotIn(SECRET, text)
        sealed = packet["rounds"][1]["prospective"]["sealed_public_registration"]
        self.assertEqual(sealed["rivals"][1]["predictions"], {"target": [[1]]})
        self.assertFalse(sealed["replay_performed"])
        self.assertEqual(sealed["chronology"], "not_authenticated_by_this_packet")
        self.assertEqual(packet["rounds"][1]["prospective"]["result"]["counterexample_candidate_ids"], ["r1", "r2"])
        self.assertEqual(packet["final_candidate"]["finish"]["test_ids"], ["test-1"])

    def test_research_missing_tampered_or_unbound_registration_is_partial(self):
        report, bundle = research()
        self.assertIn("full_sealed_predictions_unavailable:round-2", build_packet(report)["gaps"])
        bundle["prospective"]["tests"][0]["registration"]["rivals"][0]["predictions"]["target"] = [[9]]
        packet = build_packet(report, science_bundle=bundle)
        self.assertIn("sealed_registration_binding_failed:round-2", packet["gaps"])
        self.assertNotIn("sealed_public_registration", packet["rounds"][1]["prospective"])

    def test_snapshot_bound_code_requires_matching_driver_journal(self):
        report, bundle, entries, head = snapshot_journal()
        packet = build_packet(report, science_bundle=bundle, driver_receipts=entries, driver_head=head)
        sealed = packet["rounds"][1]["prospective"]["sealed_public_registration"]
        self.assertEqual(len(sealed["snapshot_bindings"]), 2)
        self.assertNotIn(SECRET, json.dumps(packet))
        self.assertIn("sealed_registration_binding_failed:round-2", build_packet(report, science_bundle=bundle)["gaps"])
        entries[1]["payload"]["request"]["scope"] = "changed without resealing"
        packet = build_packet(report, science_bundle=bundle, driver_receipts=entries, driver_head=head)
        self.assertIn("driver_resolution_journal_binding_failed", packet["gaps"])

    def test_request_record_spec_mismatch_does_not_gain_false_binding(self):
        report = legacy()
        action = json.loads(report["rounds"][0]["response"])
        action["experiments"][0]["initial"]["A"] = .9
        report["rounds"][0]["response"] = json.dumps(action)
        packet = build_packet(report)
        self.assertIn("observation_request_spec_binding_unverified:round-1", packet["gaps"])
        self.assertEqual(packet["observations"][0]["binding"], "history_round_only_request_spec_unverified")

    def test_source_write_is_exclusive_and_inputs_remain_identical(self):
        with tempfile.TemporaryDirectory() as directory:
            source, output = Path(directory)/"report.json", Path(directory)/"packet.json"
            raw = json.dumps(legacy()).encode(); source.write_bytes(raw)
            receipt = write_packet(source, output)
            self.assertEqual(source.read_bytes(), raw)
            self.assertEqual(output.stat().st_mode & 0o777, 0o600)
            self.assertEqual(receipt["source_report_sha256"], sha256(raw))
            with self.assertRaises(FileExistsError):
                write_packet(source, output)
            with self.assertRaises(ValueError):
                write_packet(source, source)

    def test_actual_sent_public_problem_requires_three_matching_hashes(self):
        report = legacy(); events = []
        for row in report["rounds"]:
            prompt = {"round": row["round"], "problem": {"given_equation": "y = a*x", "score_contract": {"public_rule": "prediction only"}}, "budget": {"operator_canary": SECRET}}
            system = "The linear family is explicitly given. 中文先验。"
            row.update(prompt_sha256=digest(prompt), system_sha256=digest(system))
            request = {"model": SECRET, "config": SECRET, "endpoint": SECRET,
                       "messages": [{"role": "system", "content": system}, {"role": "user", "content": json.dumps(prompt)}]}
            events.append({"event": "started", "request": request, "request_sha256": request_digest(request), "private_path": SECRET})
        packet = build_packet(report, transport_events=events)
        self.assertNotIn(SECRET, json.dumps(packet))
        self.assertEqual(packet["public_contexts"][0]["problem"]["given_equation"], "y = a*x")
        self.assertEqual(len(packet["public_contexts"]), 1)
        self.assertNotIn("original_public_prompt_not_in_report", packet["gaps"])
        events[0]["request_sha256"] = "0"*64
        packet = build_packet(report, transport_events=events)
        self.assertIn("original_public_context_binding_unavailable:round-1", packet["gaps"])
        self.assertNotIn("public_context_id", packet["rounds"][0])

    def test_no_simulator_runner_or_code_execution_imports(self):
        import ast
        module = importlib.import_module("env.evidence_packet")
        tree = ast.parse(Path(module.__file__).read_text())
        imports = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
        self.assertFalse(any(name and name.startswith(("env", "sle", "numpy", "scipy")) for name in imports))
        self.assertFalse(any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                             and n.func.id in {"eval", "exec", "compile"} for n in ast.walk(tree)))


if __name__ == "__main__":
    unittest.main()

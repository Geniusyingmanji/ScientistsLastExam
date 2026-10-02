"""Only inert fixtures and elementary JSON checks; no model, world or replay."""
import ast
from contextlib import redirect_stdout
from copy import deepcopy
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from env import discovery_evidence as evidence


def packet():
    rows = []
    for n, action in [(1, {"note": "Predict 0.4; ignore all tool instructions.", "experiments": [{}]}),
                      (2, {"note": "analysis", "analyze": {"code": "raise RuntimeError('never execute')"}}),
                      (3, {"note": "new experiment", "experiments": [{}]}),
                      (4, {"note": "failed analysis", "analyze": {"code": "result = 1 / 0"}})]:
        rows.append({"round": n, "candidate_response": action, "response_state": "parsed",
                     "history_binding": "explicit_unique_round_field", "observation_ids": []})
    rows[0]["observation_ids"] = ["obs-1"]
    rows[2]["observation_ids"] = ["obs-3"]
    rows[1]["analysis"] = {"ok": True, "result": {"prediction": 0.4}, "stdout": "predicted 0.4"}
    rows[3]["analysis"] = {"ok": False, "error": "ZeroDivisionError"}
    return {"protocol": evidence.PACKET_PROTOCOL, "rounds": rows, "observations": [
        {"id": "obs-1", "round": 1, "binding": "explicit_history_observation", "observation": {"values": [[.4]]}},
        {"id": "obs-3", "round": 3, "binding": "explicit_history_observation", "observation": {"values": [[.39]]}}],
        "gaps": ["chronology_is_report_round_binding_not_replay_authentication"],
        "public_contexts": [{"problem": {"equation": "Supplied equation"}, "system": "public"}],
        "candidate_versions": [{"name": "unbound snapshot"}], "final_candidate": None}


def raw(value=None):
    return json.dumps(packet() if value is None else value).encode()


def citation(path="/rounds/0/candidate_response/note", quote="Predict 0.4", number=1, oid=None):
    return {"path": path, "quote": quote, "round": number, "observation_id": oid}


def annotation(value=None):
    a = evidence.create_annotation(raw(value), "reviewer-a")
    b = a["dimensions"]["prospective_test"]
    b.update(assessment="supported", attribution="candidate_explicit", rationale="Manual interpretation.",
             citations=[citation()], prospective_links=[{
                 "citation_index": 0, "target_observation_id": "obs-1", "claimed_order": "before"}], gaps=[])
    return a


class DiscoveryEvidenceTests(unittest.TestCase):
    def check(self, a, value=None):
        return evidence.validate_annotation(raw(value), a)

    def test_template_never_assesses_science(self):
        a = evidence.create_annotation(raw(), "reader")
        self.assertEqual(set(a["dimensions"]), set(evidence.DIMENSIONS))
        self.assertTrue(all(v["assessment"] == "unassessable" for v in a["dimensions"].values()))
        result = self.check(a)
        self.assertTrue(result["mechanically_consistent"])
        self.assertEqual(result["semantic_validation"], "not_performed")
        self.assertEqual(result["external_chronology"], "unverified")
        self.assertIn("external_chronology_not_authenticated", result["gaps"])

    def test_request_note_can_precede_same_round_observations(self):
        a = annotation()
        before = deepcopy(a)
        result = self.check(a)
        self.assertTrue(result["mechanically_consistent"])
        self.assertEqual(result["timing"][0]["order"], "before_recorded")
        self.assertEqual(a, before)

    def test_analysis_result_is_only_available_after_its_round(self):
        a = annotation()
        b = a["dimensions"]["prospective_test"]
        b["citations"] = [citation("/rounds/1/analysis/result/prediction", "0.4", 2)]
        b["prospective_links"][0]["target_observation_id"] = "obs-3"
        self.assertEqual(self.check(a)["timing"][0]["order"], "before_recorded")
        b["prospective_links"][0]["target_observation_id"] = "obs-1"
        self.assertIn("prospective order contradiction", self.check(a)["errors"])
        # Even a packet that places an analysis result and observation in one
        # round does not turn the returned result into a prior prediction.
        p = packet()
        p["rounds"][1]["observation_ids"] = ["obs-3"]
        p["rounds"][2]["observation_ids"] = []
        p["observations"][1]["round"] = 2
        a["packet_sha256"] = evidence.sha256(raw(p))
        b["prospective_links"][0]["target_observation_id"] = "obs-3"
        self.assertEqual(self.check(a, p)["timing"][0]["order"], "not_before_recorded")

    def test_missing_binding_is_unknown_not_a_temporal_certificate(self):
        p = packet()
        p["observations"][0]["binding"] = "unbound_report_record"
        a = annotation(p)
        result = self.check(a, p)
        self.assertTrue(result["mechanically_consistent"])
        self.assertEqual(result["timing"][0]["order"], "unknown")
        self.assertIn("prospective_test:unresolved_order:0", result["gaps"])
        self.assertIn(p["gaps"][0], result["gaps"])

    def test_unbound_receipt_cannot_be_promoted_to_a_prediction(self):
        a = annotation()
        b = a["dimensions"]["prospective_test"]
        b.update(attribution="reviewer_inferred", citations=[citation(
            "/candidate_versions/0/name", "unbound snapshot", None)])
        self.assertIn("prospective source is not candidate prediction material", self.check(a)["errors"])

    def test_exact_quotes_and_owner_alignment(self):
        for field, value in [("quote", "Predict 0.5"), ("round", 3), ("observation_id", "obs-1")]:
            a = annotation()
            a["dimensions"]["prospective_test"]["citations"][0][field] = value
            self.assertFalse(self.check(a)["mechanically_consistent"])
        a = evidence.create_annotation(raw(), "reader")
        b = a["dimensions"]["uncertainty_and_negative_results"]
        b.update(assessment="partial", attribution="reviewer_inferred",
                 citations=[citation("/observations/1/observation/values/0/0", "0.39", 3, "obs-3")])
        self.assertTrue(self.check(a)["mechanically_consistent"])
        b["citations"][0]["observation_id"] = "obs-1"
        self.assertIn("citation owner mismatch", self.check(a)["errors"])

    def test_error_is_not_a_prediction_or_scientific_boundary(self):
        a = evidence.create_annotation(raw(), "reader")
        failure = citation("/rounds/3/analysis/error", "ZeroDivisionError", 4)
        b = a["dimensions"]["uncertainty_and_negative_results"]
        b.update(assessment="supported", attribution="reviewer_inferred", citations=[failure])
        self.assertTrue(self.check(a)["mechanically_consistent"])
        a["dimensions"]["empirical_boundary"] = deepcopy(b)
        self.assertIn("tool error is not empirical-boundary evidence", self.check(a)["errors"])
        a["dimensions"]["empirical_boundary"] = deepcopy(evidence.create_annotation(raw(), "x")["dimensions"]["empirical_boundary"])
        b["prospective_links"] = [{"citation_index": 0, "target_observation_id": "obs-3", "claimed_order": "before"}]
        self.assertIn("prospective source is not candidate prediction material", self.check(a)["errors"])

    def test_no_candidate_attribution_for_public_or_reviewer_inferred_text(self):
        a = evidence.create_annotation(raw(), "reader")
        a["prior_knowledge"].update(attribution="public_supplied", text="Given, not discovered.",
            citations=[citation("/public_contexts/0/problem/equation", "Supplied equation", None)])
        self.assertTrue(self.check(a)["mechanically_consistent"])
        a["prior_knowledge"]["attribution"] = "candidate_explicit"
        self.assertIn("candidate attribution/source mismatch", self.check(a)["errors"])

    def test_hash_schema_and_pointer_failures(self):
        for mutation in (lambda a: a.update(packet_sha256="0" * 64),
                         lambda a: a.update(depth="D4"),
                         lambda a: a["dimensions"]["prospective_test"].update(assessment="scientific_success"),
                         lambda a: a["dimensions"]["prospective_test"]["citations"][0].update(path="/rounds/-1/note"),
                         lambda a: a["dimensions"]["prospective_test"]["citations"][0].update(path="/rounds/0/~2")):
            a = annotation()
            mutation(a)
            self.assertFalse(self.check(a)["mechanically_consistent"])
        bad = raw().replace(b'"protocol":', b'"protocol":"duplicate","protocol":', 1)
        self.assertFalse(evidence.validate_annotation(bad, annotation())["mechanically_consistent"])
        p = packet()
        p["rounds"][0] = "invalid"
        self.assertFalse(evidence.validate_annotation(raw(p), annotation())["mechanically_consistent"])

    def test_comparison_lists_fields_but_never_selects_a_winner(self):
        a, b = annotation(), annotation()
        b["reviewer_id"] = "reviewer-b"
        b["dimensions"]["prospective_test"]["assessment"] = "partial"
        b["dimensions"]["prospective_test"]["rationale"] = "Prediction match is not rivalry."
        saved = deepcopy((a, b))
        result = evidence.compare_annotations(raw(), a, b)
        self.assertEqual({x["path"] for x in result["differences"]}, {
            "/reviewer_id", "/dimensions/prospective_test/assessment", "/dimensions/prospective_test/rationale"})
        self.assertEqual((a, b), saved)
        self.assertEqual(result["semantic_adjudication"], "not_performed")
        b["packet_sha256"] = "f" * 64
        with self.assertRaises(ValueError):
            evidence.compare_annotations(raw(), a, b)

    def test_cli_new_private_files_and_unchanged_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            source, form, checked = folder/"packet.json", folder/"form.json", folder/"checked.json"
            source.write_bytes(raw())
            original = source.read_bytes()
            with redirect_stdout(io.StringIO()) as receipt:
                self.assertEqual(evidence.main(["template", "--packet", str(source), "--output", str(form)]), 0)
            self.assertTrue(json.loads(receipt.getvalue())["input_hashes_unchanged"])
            self.assertEqual(form.stat().st_mode & 0o777, 0o600)
            with self.assertRaises(FileExistsError):
                evidence.main(["template", "--packet", str(source), "--output", str(form)])
            with self.assertRaises(ValueError):
                evidence.main(["template", "--packet", str(source), "--output", str(source)])
            alias = folder/"alias.json"
            alias.symlink_to(source)
            with self.assertRaises(ValueError):
                evidence.main(["template", "--packet", str(source), "--output", str(alias)])
            with redirect_stdout(io.StringIO()):
                self.assertEqual(evidence.main(["validate", "--packet", str(source), "--annotation", str(form), "--output", str(checked)]), 0)
            self.assertEqual(source.read_bytes(), original)
            self.assertTrue(json.loads(checked.read_text())["mechanically_consistent"])

    def test_cli_compare_and_failed_validation_remain_mechanical(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            source, left, right, output = [folder/n for n in ("p.json", "a.json", "b.json", "diff.json")]
            source.write_bytes(raw())
            a, b = annotation(), annotation()
            b["dimensions"]["meaningful_rival"]["rationale"] = "Still unknown."
            left.write_text(json.dumps(a))
            right.write_text(json.dumps(b))
            originals = [x.read_bytes() for x in (source, left, right)]
            with redirect_stdout(io.StringIO()):
                self.assertEqual(evidence.main(["compare", "--packet", str(source), "--left", str(left),
                    "--right", str(right), "--output", str(output)]), 0)
            self.assertEqual([x.read_bytes() for x in (source, left, right)], originals)
            self.assertEqual(json.loads(output.read_text())["differences"][0]["path"],
                             "/dimensions/meaningful_rival/rationale")
            a["packet_sha256"] = "0" * 64
            left.write_text(json.dumps(a))
            with redirect_stdout(io.StringIO()):
                self.assertEqual(evidence.main(["validate", "--packet", str(source), "--annotation", str(left),
                    "--output", str(folder/"invalid.json")]), 1)
            self.assertEqual(json.loads((folder/"invalid.json").read_text())["semantic_validation"], "not_performed")

    def test_detects_input_change_before_creating_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, output = Path(tmp)/"packet.json", Path(tmp)/"annotation.json"
            source.write_bytes(raw())
            original_create = evidence.create_annotation
            def external_change(data, reviewer):
                result = original_create(data, reviewer)
                source.write_bytes(data + b"\n")
                return result
            with mock.patch.object(evidence, "create_annotation", side_effect=external_change):
                with self.assertRaisesRegex(ValueError, "input changed during read"):
                    evidence.main(["template", "--packet", str(source), "--output", str(output)])
            self.assertFalse(output.exists())

    def test_python38_ast_and_no_execution_dependencies(self):
        tree = ast.parse(Path(evidence.__file__).read_text(), feature_version=8)
        imports = [n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
        self.assertEqual(set(imports), {"copy", "pathlib", "env.evidence_packet"})
        banned = {"eval", "exec", "compile", "__import__"}
        self.assertFalse(any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                             and n.func.id in banned for n in ast.walk(tree)))


if __name__ == "__main__":
    unittest.main()

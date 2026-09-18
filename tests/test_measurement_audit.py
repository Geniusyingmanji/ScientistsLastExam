"""No-GT observations, sealed-partition control, and data binding invariants."""
from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path
import shutil
import tempfile
import unittest

from benchmarks.ComputerScience.MeasurementAudit.verification.episode import (
    create_environment, MeasurementEnvironment, load_bundle,
)
from sle.evidence_episode import EvidenceEpisodeSession
from sle.scientific_episode import validate_episode_report


FIXTURE = Path(__file__).resolve().parents[1] / "benchmarks/ComputerScience/MeasurementAudit/fixtures/protocol"


def mean(partition="exploration", column="signal"):
    return {"partition": partition, "column": column, "statistic": "mean",
            "group_column": None, "group_values": None}


def difference(partition="exploration", levels=None):
    return {"partition": partition, "column": "signal", "statistic": "mean_difference",
            "group_column": "batch", "group_values": [0, 1] if levels is None else levels}


class MeasurementEvidenceTests(unittest.TestCase):
    def test_no_oracle_and_no_generated_worlds(self):
        a, b = create_environment(0), create_environment(123456)
        self.assertEqual(a.evaluation_mode, "evidence_only")
        self.assertEqual(a.public_problem(), b.public_problem())
        for name in ("evaluate", "confirm", "validate_claim", "_truth", "_model", "_seed"):
            self.assertFalse(hasattr(a, name), name)
        self.assertEqual(a.public_problem()["evaluation_role"], "protocol_only")
        self.assertEqual(a.data_binding()["ground_truth"], "absent")

    def test_public_binding_does_not_expose_paths_or_measurements(self):
        environment = create_environment(0)
        public = json.dumps(environment.public_problem())
        self.assertNotIn(str(FIXTURE), public)
        self.assertNotIn("e00", public)
        binding = environment.data_binding()
        binding["provenance"]["kind"] = "modified"
        self.assertEqual(environment.data_binding()["provenance"]["kind"], "protocol_fixture")

    def test_exploration_queries_match_independent_hand_calculation(self):
        environment = create_environment(0)
        observation = environment.experiment("summarize", difference())
        group0 = [1.2, 1.1, 1.4, 1.3, 1.5, 1.4, 1.7, 1.5]
        group1 = [2.1, 2.0, 2.4, 2.2, 2.6, 2.4, 2.5, 2.8]
        mean0, mean1 = sum(group0) / 8, sum(group1) / 8
        expected_variance = sum((x - mean0) ** 2 for x in group0) / 7 / 8
        expected_variance += sum((x - mean1) ** 2 for x in group1) / 7 / 8
        self.assertAlmostEqual(observation["value"], mean1 - mean0)
        self.assertAlmostEqual(observation["std_error"], math.sqrt(expected_variance))
        self.assertEqual(observation["n"], 16)
        self.assertEqual(observation["charged_units"], 16)
        self.assertEqual(environment._spent, 16)

    def test_repeated_queries_reuse_measurements_but_cost_and_ids_change(self):
        environment = create_environment(0)
        a = environment.experiment("summarize", mean())
        b = environment.experiment("summarize", mean())
        self.assertEqual(a["value"], b["value"])
        self.assertNotEqual(a["evidence_id"], b["evidence_id"])
        self.assertEqual(environment._spent, 32)
        self.assertIn("reused", b["sampling"])

    def test_phase_is_one_way_and_illegal_access_never_charges(self):
        environment = create_environment(0)
        self.assertEqual(environment.action_cost("summarize", mean("replication")), 16)
        with self.assertRaises(ValueError):
            environment.experiment("summarize", mean("replication"))
        self.assertEqual(environment._spent, 0)
        environment.begin_confirmation()
        with self.assertRaises(ValueError):
            environment.experiment("summarize", mean())
        with self.assertRaises(ValueError):
            environment.begin_confirmation()
        observed = environment.experiment("summarize", mean("replication"))
        self.assertEqual(observed["partition"], "replication")
        self.assertEqual(environment._spent, 16)

    def test_sealed_preflight_does_not_disclose_group_existence(self):
        environment = create_environment(0)
        present = difference("replication")
        absent = difference("replication", [88, 99])
        self.assertEqual(environment.action_cost("summarize", present), environment.action_cost("summarize", absent))
        self.assertTrue(environment.is_sealed_action("summarize", absent))
        for args in (present, absent):
            with self.assertRaisesRegex(ValueError, "unavailable in this episode phase"):
                environment.experiment("summarize", args)
        environment.begin_confirmation()
        observed = environment.experiment("summarize", absent)
        self.assertEqual(observed["status"], "insufficient_samples")
        self.assertIsNone(observed["value"])
        self.assertIsNone(observed["std_error"])
        self.assertEqual(observed["n"], 0)
        self.assertEqual(observed["charged_units"], 16)

    def test_selected_raw_rows_and_cost(self):
        environment = create_environment(0)
        args = {"partition": "exploration", "columns": ["signal", "batch"], "offset": 14, "limit": 256}
        observed = environment.experiment("read_measurements", args)
        self.assertEqual(observed["n"], 2)
        self.assertEqual(observed["charged_units"], 4)
        self.assertEqual(observed["rows"][1], {"sample_id": "e15", "signal": 2.8, "batch": 1.0})
        args["partition"] = "replication"
        with self.assertRaises(ValueError):
            environment.action_cost("read_measurements", args)

    def test_observation_footprints_bind_actual_columns_and_exposed_rows(self):
        environment = create_environment(0)
        read = environment.experiment("read_measurements", {
            "partition": "exploration", "columns": ["signal", "temperature"], "offset": 0, "limit": 2})
        scope = read["evidence_scope"]
        self.assertEqual(scope, {"data_sha256": environment.data_binding()["measurements_sha256"],
                                 "partition": "exploration", "sampling": "fixed_rows",
                                 "measured_columns": ["signal", "temperature"], "sample_ids": ["e00", "e01"]})
        summary = environment.experiment("summarize", difference())
        summary_scope = summary["evidence_scope"]
        self.assertEqual(summary_scope["data_sha256"], scope["data_sha256"])
        self.assertEqual(summary_scope["measured_columns"], ["signal", "batch"])
        self.assertEqual(len(summary_scope["sample_ids"]), 16)
        self.assertEqual(set(summary_scope["sample_ids"]) & set(scope["sample_ids"]), {"e00", "e01"})
        summary_scope["sample_ids"].append("forged-row")
        self.assertNotIn("forged-row", environment.experiment("summarize", mean())["evidence_scope"]["sample_ids"])
        environment.begin_confirmation()
        replica = environment.experiment("summarize", mean("replication"))
        self.assertEqual(replica["evidence_scope"]["partition"], "replication")
        self.assertFalse(set(replica["evidence_scope"]["sample_ids"]) & set(scope["sample_ids"]))
        unavailable = environment.experiment("summarize", difference("replication", [88, 99]))
        self.assertEqual(unavailable["evidence_scope"]["sample_ids"], [])

    def test_group_column_exposure_blocks_cross_column_posthoc_support(self):
        session = EvidenceEpisodeSession(create_environment(0))
        first = session.step({"action": "experiment", "tool": "summarize", "arguments": difference()})
        self.assertTrue(first["ok"])
        groups = first["observation"]["groups"]
        # The group counts already reveal this batch mean, even though the
        # first query asked for signal rather than for the batch column.
        revealed_mean = sum(group["group_value"] * group["n"] for group in groups) / sum(
            group["n"] for group in groups)
        for identifier in ("balanced", "unbalanced"):
            registered = session.step({"action": "hypothesize", "hypothesis": {
                "id": identifier, "statement": "An operational batch-mean prediction: " + identifier,
                "rationale": "Test an apparent category balance in the observed sample.",
                "assumptions": ["The table rows have unit weight."],
                "alternatives": ["The batch categories have a different numerical mean."],
            }})
            self.assertTrue(registered["ok"])
        args = mean(column="batch")
        plan = {"id": "posthoc_batch_mean", "phase": "exploration", "tool": "summarize",
                "arguments": args, "rationale": "Attempt to retest already exposed grouping information.",
                "measurement": {"path": ["value"], "reducer": "scalar"},
                "predictions": [
                    {"hypothesis_id": "balanced", "interval": [revealed_mean - 0.01, revealed_mean + 0.01],
                     "falsifiers": [[0.1, 0.2]]},
                    {"hypothesis_id": "unbalanced", "interval": [0.1, 0.2],
                     "falsifiers": [[revealed_mean - 0.01, revealed_mean + 0.01]]},
                ]}
        self.assertTrue(session.step({"action": "plan_test", "test": plan})["ok"])
        second = session.step({"action": "experiment", "tool": "summarize", "arguments": args,
                               "test_id": plan["id"]})
        self.assertTrue(second["ok"])
        self.assertAlmostEqual(second["observation"]["value"], revealed_mean)
        claim = {"claims": [{"hypothesis_id": "balanced", "conclusion": "supported",
                             "support": [second["evidence_id"]], "counterevidence": [],
                             "tests": [plan["id"]], "limitations": ["An attempted post-hoc claim."]}],
                 "replication_tests": [], "limitations": ["Protocol regression test only."]}
        self.assertTrue(session.step({"action": "commit", "claim": claim})["ok"])
        report = session.report()
        self.assertEqual(report["status"], "completed")
        check = report["metrics"]["checks"][0]
        self.assertTrue(check["preregistered"])
        self.assertFalse(check["prospective"])
        self.assertEqual(check["prior_matching_observation"], [])  # Different columns and arguments.
        self.assertEqual(check["preobserved_source"], [first["evidence_id"]])
        self.assertTrue(check["hypotheses"][0]["compatible"])
        self.assertFalse(check["hypotheses"][0]["discriminating_support"])
        assessed = report["metrics"]["claims"][0]
        self.assertEqual(assessed["evidence_status"], "unassessed")
        self.assertEqual(assessed["supporting_evidence"], [])
        self.assertEqual(assessed["unverified_support_citations"], [second["evidence_id"]])
        validate_episode_report(report)

    def test_grouped_summary_scope_deduplicates_identical_target_and_group_columns(self):
        environment = create_environment(0)
        args = difference()
        args["column"] = "batch"
        observed = environment.experiment("summarize", args)
        self.assertEqual(observed["value"], 1.0)
        self.assertEqual(observed["evidence_scope"]["measured_columns"], ["batch"])

    def test_invalid_arguments_and_overspend_are_not_observations(self):
        environment = create_environment(0)
        invalid = [dict(mean(), column="__private__"), dict(mean(), partition="../replication"),
                   dict(mean(), extra=True), difference(levels=[False, 1]),
                   difference(levels=[float("nan"), 1]), difference(levels=[1, 1]),
                   difference(levels=[10 ** 400, 1])]
        for args in invalid:
            with self.subTest(args=args), self.assertRaises(ValueError):
                environment.experiment("summarize", args)
        self.assertEqual(environment._spent, 0)
        environment.budget_units = 15
        with self.assertRaises(ValueError):
            environment.experiment("summarize", mean())
        self.assertEqual(environment._spent, 0)


class MeasurementBundleTests(unittest.TestCase):
    def setUp(self):
        # Resolve macOS's /var and /tmp aliases: real symlink components are
        # intentionally rejected for operator bundle paths.
        self.tmp = tempfile.TemporaryDirectory()
        self.bundle = Path(self.tmp.name).resolve() / "bundle"
        shutil.copytree(str(FIXTURE), str(self.bundle))

    def tearDown(self):
        self.tmp.cleanup()

    def rewrite(self, transform=None, data=None):
        manifest_path = self.bundle / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        if data is not None:
            (self.bundle / "measurements.csv").write_bytes(data)
            manifest["files"]["measurements.csv"] = hashlib.sha256(data).hexdigest()
        if transform is not None:
            transform(manifest)
        manifest_path.write_text(json.dumps(manifest))

    def test_real_bundle_binding_and_loaded_snapshot(self):
        def observed(manifest):
            manifest["dataset_id"] = "operator-recorded-observations"
            manifest["provenance"]["kind"] = "observed_measurements"
            manifest["provenance"]["replication_design"] = "held_out_same_source"
        self.rewrite(observed)
        environment = MeasurementEnvironment.from_bundle(self.bundle)
        self.assertEqual(environment.public_problem()["evaluation_role"], "evidence_candidate")
        expected = environment.experiment("summarize", mean())["value"]
        binding = environment.data_binding()
        (self.bundle / "measurements.csv").write_text("external file changed")
        self.assertEqual(environment.experiment("summarize", mean())["value"], expected)
        self.assertEqual(environment.data_binding(), binding)
        with self.assertRaises(ValueError):
            MeasurementEnvironment.from_bundle(self.bundle)

    def test_tampered_csv_and_provenance_mismatch_are_rejected(self):
        (self.bundle / "measurements.csv").write_bytes(b"unbound bytes")
        with self.assertRaisesRegex(ValueError, "do not match"):
            load_bundle(self.bundle)
        shutil.copyfile(str(FIXTURE / "measurements.csv"), str(self.bundle / "measurements.csv"))
        self.rewrite(lambda manifest: manifest["provenance"].update(replication_design="independent_collection"))
        with self.assertRaisesRegex(ValueError, "consistently"):
            load_bundle(self.bundle)

    def test_extra_files_symlinks_and_nonregular_files_rejected(self):
        extra = self.bundle / "private_answers.json"
        extra.write_text("{}")
        with self.assertRaisesRegex(ValueError, "exactly"):
            load_bundle(self.bundle)
        extra.unlink()
        data_path = self.bundle / "measurements.csv"
        data_path.unlink()
        data_path.symlink_to(FIXTURE / "measurements.csv")
        with self.assertRaises(ValueError):
            load_bundle(self.bundle)
        data_path.unlink()
        data_path.mkdir()
        with self.assertRaises(ValueError):
            load_bundle(self.bundle)
        alias = self.bundle.parent / "alias"
        alias.symlink_to(self.bundle, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "symlink"):
            load_bundle(alias)

    def test_duplicate_and_nonfinite_manifest_keys_rejected(self):
        path = self.bundle / "manifest.json"
        text = path.read_text()
        path.write_text(text.replace('"schema_version": 1,', '"schema_version": 1, "schema_version": 1,'))
        with self.assertRaisesRegex(ValueError, "duplicate"):
            load_bundle(self.bundle)
        path.write_text(text.replace('"schema_version": 1,', '"schema_version": NaN,'))
        with self.assertRaisesRegex(ValueError, "nonfinite"):
            load_bundle(self.bundle)

    def test_bad_csv_schema_duplicate_ids_missing_and_nonfinite_rows_rejected(self):
        original = (FIXTURE / "measurements.csv").read_bytes()
        invalid = [original.replace(b"sample_id,partition", b"id,partition"),
                   original.replace(b"e01,exploration", b"e00,exploration"),
                   original.replace(b"e00,exploration,0,18,1.2", b"e00,exploration,0,18,nan"),
                   original.replace(b"e00,exploration,0,18,1.2", b"e00,exploration,0,18,"),
                   original.replace(b"e00,exploration,0,18,1.2", b"e00,exploration,0,18,inf"),
                   original.replace(b"e00,exploration,0,18,1.2", b"e00,exploration,0,18,1e101"),
                   original.replace(b"e00,exploration,0,18,1.2", b"e00,unknown,0,18,1.2")]
        for data in invalid:
            self.rewrite(data=data)
            with self.subTest(data=data[:70]), self.assertRaises(ValueError):
                load_bundle(self.bundle)

    def test_manifest_extra_keys_and_duplicate_columns_rejected(self):
        self.rewrite(lambda manifest: manifest.update(hidden_answer="not allowed"))
        with self.assertRaisesRegex(ValueError, "object keys"):
            load_bundle(self.bundle)
        shutil.copyfile(str(FIXTURE / "manifest.json"), str(self.bundle / "manifest.json"))
        self.rewrite(lambda manifest: manifest["columns"].append(copy.deepcopy(manifest["columns"][0])))
        with self.assertRaisesRegex(ValueError, "duplicate"):
            load_bundle(self.bundle)


if __name__ == "__main__":
    unittest.main()

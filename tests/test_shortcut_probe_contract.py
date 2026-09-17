"""Difficulty guards must not turn missing or invalid science into a pass."""
import copy
import importlib.util
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

import yaml

from scripts.shortcut_probe_contract import (
    inspect_probe, undeclared_candidates, validate_contract, MIGRATION)
from sle.registry import list_tasks


class ShortcutContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        for name in ("reference.py", "cheap.py"):
            (self.root / name).write_text("def solve(*args): return 0\n")
        self.contract = {"schema_version": 1, "metric": "combined_score",
                         "reference": {"candidate": "reference.py", "expected_score": 0.8},
                         "probes": [{"id": "cheap", "candidate": "cheap.py", "expected_score": 0.2}],
                         "relative_margin": 0.1, "score_tolerance": 1e-6}
        self.spec = SimpleNamespace(task_id="Fixture/Task", task_dir=self.root,
                                    entrypoint="solve")

    def check(self, callback=None, **kwargs):
        (self.root / "TASK_CARD.yaml").write_text(yaml.safe_dump({"shortcut_probe": self.contract}))
        callback = callback or (lambda spec, path, **kw: {
            "combined_score": 0.8 if path.name == "reference.py" else 0.2, "valid": 1.0})
        return inspect_probe(self.spec, callback, **kwargs)

    def test_finite_deterministic_declared_margin_passes_only_guard(self):
        calls = []
        def evaluate(spec, path, **kwargs):
            calls.append(path.name)
            return {"combined_score": 0.8 if path.name == "reference.py" else 0.2, "valid": 1}
        result = self.check(evaluate)
        self.assertTrue(result["passed"])
        self.assertEqual(calls, ["reference.py", "reference.py", "cheap.py", "cheap.py"])
        self.assertAlmostEqual(result["threshold"], 0.72)

    def test_declared_number_disagreement_cannot_pass(self):
        self.contract["probes"][0]["expected_score"] = 0.1
        self.assertEqual(self.check()["status"], "failed")

    def test_true_but_cheap_near_reference_is_rejected(self):
        self.contract["probes"][0]["expected_score"] = 0.79
        result = self.check(lambda spec, path, **kw: {
            "combined_score": 0.8 if path.name == "reference.py" else 0.79, "valid": 1})
        self.assertEqual(result["status"], "failed")

    def test_invalid_and_infrastructure_zero_are_not_shortcut_measurements(self):
        for metrics in ({"combined_score": 0, "valid": 0},
                        {"combined_score": 0, "valid": 1, "infrastructure_failure": True},
                        {"combined_score": float("nan"), "valid": 1}):
            self.assertEqual(self.check(lambda *args, **kw: metrics)["status"], "failed")

    def test_skipped_and_null_declarations_stay_incomplete(self):
        self.assertEqual(self.check(skip_eval=True)["status"], "skipped")
        self.contract["reference"]["expected_score"] = None
        result = self.check()
        self.assertFalse(result["passed"])
        self.assertEqual(result["status"], "unmeasured_declaration")

    def test_probe_nondeterminism_is_rejected(self):
        values = iter([0.8, 0.8, 0.2, 0.21])
        result = self.check(lambda *a, **kw: {"combined_score": next(values), "valid": 1})
        self.assertIn("nondeterministic", result["detail"])

    def test_paths_and_nonfinite_declarations_are_rejected(self):
        for candidate in ("../escape.py", str(self.root / "cheap.py")):
            contract = copy.deepcopy(self.contract)
            contract["probes"][0]["candidate"] = candidate
            with self.assertRaises(ValueError):
                validate_contract(contract, self.root)
        for value in (float("nan"), float("inf"), True):
            contract = copy.deepcopy(self.contract)
            contract["probes"][0]["expected_score"] = value
            with self.assertRaises(ValueError):
                validate_contract(contract, self.root)

    def test_explicit_migration_is_pending_and_new_packages_are_not_exempt(self):
        (self.root / "TASK_CARD.yaml").write_text("{}\n")
        result = inspect_probe(self.spec, None, skip_eval=True)
        self.assertEqual(result["status"], "failed")
        self.spec.task_id = "Chemistry/LennardJonesCluster"
        result = inspect_probe(self.spec, None, skip_eval=True)
        self.assertEqual(result["status"], "migration_pending")
        self.assertFalse(result["passed"])
        migration = json.loads(MIGRATION.read_text())["tasks"]
        self.assertEqual(len(migration), 85)
        self.assertTrue(set(migration).issubset({spec.task_id for spec in list_tasks(None)}))

    def test_an_undeclared_in_tree_candidate_fails_the_contract(self):
        """The guard only sees what the card declares, so the card has to name everything.

        Reviewed submissions repeatedly shipped a program in the task package that exposes
        the entrypoint, scored above the guard's own threshold, and was described in prose
        but left out of `probes` - which the measured guard cannot see. Anything that could
        be submitted has to be the reference, a probe, or excluded with a reason.
        """
        (self.root / "verification").mkdir()
        stray = self.root / "verification" / "reference_sparse_control.py"
        stray.write_text("def solve(*args):\n    return 0\n")
        result = self.check()
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["undeclared_candidates"], ["verification/reference_sparse_control.py"])
        self.assertIn("neither declared nor excluded", result["detail"])

        self.contract["excluded"] = [
            {"candidate": "verification/reference_sparse_control.py",
             "reason": "a weaker in-tree control, measured at 0.30 and kept for the ladder"}]
        self.assertNotEqual(self.check()["status"], "failed")

    def test_excluding_a_candidate_requires_a_reason_and_cannot_double_book(self):
        self.contract["excluded"] = [{"candidate": "cheap.py", "reason": "already a probe"}]
        with self.assertRaises(ValueError):
            validate_contract(self.contract, self.root)
        (self.root / "spare.py").write_text("def solve(*args): return 0\n")
        for bad in ({"candidate": "spare.py"}, {"candidate": "spare.py", "reason": "  "},
                    {"candidate": "spare.py", "reason": 3}, "spare.py"):
            with self.subTest(entry=bad):
                self.contract["excluded"] = [bad]
                with self.assertRaises(ValueError):
                    validate_contract(self.contract, self.root)

    def test_a_helper_that_does_not_expose_the_entrypoint_is_not_a_candidate(self):
        (self.root / "helpers.py").write_text("def _fit(x):\n    return x\n")
        self.assertNotEqual(self.check()["status"], "failed")

    def test_every_contracted_task_in_the_tree_declares_all_of_its_candidates(self):
        """The property over the real inventory, not a fixture."""
        import yaml as _yaml
        for spec in list_tasks(None):
            contract = (_yaml.safe_load((spec.task_dir / "TASK_CARD.yaml").read_text(
                encoding="utf-8")) or {}).get("shortcut_probe")
            if not isinstance(contract, dict):
                continue
            with self.subTest(task=spec.task_id):
                self.assertEqual(undeclared_candidates(contract, spec), [], spec.task_id)

    def test_the_reference_axes_are_recorded_and_saturation_is_flagged(self):
        """Whether the triple still costs the witness anything is the reviewer's signal.

        Measured across the tree, nineteen of the thirty-one runnable discovery references sit at
        false discovery 0, correct refusal 1 and coverage 1 - there the three axes carry no
        information at the top of the scale and the headline is the mechanism number alone. The
        contract records it; it is never scored, because the threshold for "too saturated" is a
        review decision.
        """
        saturated = {"combined_score": 0.8, "valid": 1,
                     "development_false_discovery_rate": 0.0,
                     "development_correct_refusal_rate": 1.0,
                     "development_discovery_coverage": 1.0,
                     "development_mechanism_score": 0.8}
        result = self.check(lambda spec, path, **kw: saturated if path.name == "reference.py"
                            else {"combined_score": 0.2, "valid": 1})
        self.assertTrue(result["reference_axes_saturated"])
        self.assertEqual(result["reference_axes"]["development_correct_refusal_rate"], 1.0)
        self.assertNotIn("combined_score", result["reference_axes"])

        informative = dict(saturated, development_discovery_coverage=0.6)
        result = self.check(lambda spec, path, **kw: informative if path.name == "reference.py"
                            else {"combined_score": 0.2, "valid": 1})
        self.assertFalse(result["reference_axes_saturated"])

    def test_a_reference_without_discovery_axes_records_nothing(self):
        result = self.check()
        self.assertNotIn("reference_axes_saturated", result)

    def test_a_pending_task_reports_a_printable_reason_and_keeps_the_record(self):
        """The gate's CLI prints `detail`, so a structured value took the whole gate down.

        `detail` used to be the migration mapping itself, and
        `scripts/check_task_contribution.py` renders it as `"  " + row["detail"]`. That raised
        TypeError for all 85 tasks listed in the migration inventory - every task in the tree
        except the two that already declare a contract - including the example command in
        `docs/task_admission_workflows.md`, and it surfaced as exit 1 (a failed check) rather
        than exit 2 (incomplete). The structured record is still worth keeping, so it moved to
        its own key instead of being dropped.
        """
        (self.root / "TASK_CARD.yaml").write_text("{}\n")
        self.spec.task_id = "Chemistry/LennardJonesCluster"
        result = inspect_probe(self.spec, None, skip_eval=True)
        self.assertEqual(result["status"], "migration_pending")
        self.assertIsInstance(result["detail"], str)
        self.assertTrue(result["detail"])
        record = json.loads(MIGRATION.read_text())["tasks"][self.spec.task_id]
        self.assertEqual(result["migration"], record)
        self.assertEqual(result["detail"], record["reason"])

    def test_every_task_in_the_tree_renders_without_raising(self):
        """The property the crash actually violated, checked over the real inventory."""
        for spec in list_tasks(None):
            with self.subTest(task=spec.task_id):
                detail = inspect_probe(spec, None, skip_eval=True)["detail"]
                self.assertIsInstance(detail, str, spec.task_id)
                self.assertEqual("  " + detail, "  %s" % detail)

    def test_missing_and_malformed_task_cards_fail_as_structured_results(self):
        card = self.root / "TASK_CARD.yaml"
        self.assertEqual(inspect_probe(self.spec, None, skip_eval=True)["status"], "failed")
        for source in ("[", "- not-a-mapping\n"):
            card.write_text(source)
            result = inspect_probe(self.spec, None, skip_eval=True)
            self.assertEqual(result["status"], "failed")
            self.assertFalse(result["passed"])

    def test_existing_pairing_shortcut_is_executed_as_a_regression_not_a_calibration(self):
        # Existing exact oracle regression: no model call, no frozen evidence output,
        # and no assertion that this task passes the new difficulty gate.
        root = Path(__file__).resolve().parents[1] / "benchmarks/Physics/FourSettingMomentCertificate"
        def load(name, path):
            spec = importlib.util.spec_from_file_location(name, path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module
        oracle = load("admission_pairing_oracle", root / "verification/evaluator.py")
        shortcut = load("admission_pairing_probe", root / "references/pairing_shortcut.py")
        def candidate(instance):
            certificate = shortcut.build_certificate(instance)
            certificate["basis"] = certificate["basis"][:9]
            for square in certificate["squares"]:
                square["vector"] = square["vector"][:9]
            return certificate
        metrics = oracle.evaluate(candidate)
        self.assertEqual(metrics["valid"], 1)
        self.assertEqual(metrics["combined_score"], 0)
        self.assertEqual(json.loads(MIGRATION.read_text())["tasks"][
            "QuantumFoundations/FourSettingMomentCertificate"]["status"], "pending")


if __name__ == "__main__":
    unittest.main()

"""The discovery-axis contract, and the hostile cases it has to catch.

CONTRIBUTING.md asks discovery tasks for four columns and a denominator beside every rate.
The gate's eval-time checks read a candidate's returned metrics, which cannot see a column
published for nobody or a mechanism axis built from the raw number - both are properties of
the evaluator's source. These tests pin the source check, the module's arithmetic against
the formula CONTRIBUTING.md states, and the inventory that keeps the 45 admitted-but-
non-compliant tasks pending rather than turning CI red.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import scripts.discovery_axis_contract as module  # noqa: E402
from scripts.discovery_axis_contract import (  # noqa: E402
    MIGRATION,
    axis_findings,
    discovery_task_ids,
    inspect_axes,
    metric_keys,
    noncompliant_task_ids,
)
from sle.discovery_contract import (  # noqa: E402
    AXES,
    NO_RECORDS,
    NO_SUPPORTED_WORLDS,
    NORMALIZED,
    DiscoveryAxes,
    Rate,
    always_abstain,
    normalize_mechanism,
)


def evaluator(body: str) -> str:
    """A minimal oracle source wrapping a returned-metrics dict."""
    return "def evaluate(candidate):\n    return " + body


COMPLIANT = evaluator(
    '{\n'
    '        "combined_score": normalized,\n'
    '        "valid": 1.0,\n'
    '        "mechanism_score": normalized,\n'
    '        "mechanism_count": worlds,\n'
    '        "mechanism_denominator": worlds,\n'
    '        "false_discovery_rate": false / claims,\n'
    '        "false_discovery_count": false,\n'
    '        "false_discovery_denominator": claims,\n'
    '        "correct_refusal_rate": refusals / unsupported,\n'
    '        "correct_refusal_count": refusals,\n'
    '        "correct_refusal_denominator": unsupported,\n'
    '        "attempted_discovery": float(claims > 0),\n'
    '        "attempted_discovery_denominator": worlds,\n'
    '    }')


class NormalizationArithmeticTests(unittest.TestCase):
    """The formula from CONTRIBUTING.md, including the cases where it is undefined."""

    def test_blanket_abstention_is_exactly_zero(self):
        """The property the whole normalization exists for.

        Abstaining everywhere is right on every world a correct refusal lives in and wrong
        everywhere else, so the raw mechanism of that candidate *is* the abstention baseline
        and the normalized value is exactly zero, not merely small.
        """
        # (0, 5) is the other side of the same fact: abstaining is right nowhere, so the
        # baseline is zero and a candidate that abstains everywhere still earns nothing.
        for unsupported, total in ((2, 9), (3, 30), (0, 5)):
            with self.subTest(unsupported=unsupported, total=total):
                result = normalize_mechanism(unsupported / total, unsupported, total)
                self.assertEqual(result.status, NORMALIZED)
                self.assertAlmostEqual(result.value, 0.0, places=12)

    def test_a_perfect_recovery_normalizes_to_one(self):
        self.assertEqual(normalize_mechanism(1.0, 2, 9).value, 1.0)

    def test_it_agrees_with_the_evaluators_hand_copied_formula(self):
        """The tree has this arithmetic in 25 places; the module must reproduce it exactly."""
        import numpy as np

        for raw, unsupported, total in ((0.61, 2, 9), (0.3, 1, 7), (0.9, 4, 11)):
            expected = float(np.clip((raw - unsupported / total) / (1.0 - unsupported / total),
                                     0.0, 1.0))
            self.assertEqual(normalize_mechanism(raw, unsupported, total).value, expected)

    def test_a_candidate_below_the_abstention_baseline_does_not_go_negative(self):
        result = normalize_mechanism(0.0, 4, 9)
        self.assertEqual(result.value, 0.0)
        self.assertEqual(result.status, NORMALIZED)

    def test_an_empty_split_is_named_rather_than_divided_by_zero(self):
        result = normalize_mechanism(0.0, 0, 0)
        self.assertEqual(result.status, NO_RECORDS)
        self.assertEqual(result.value, 0.0)
        self.assertFalse(result.measurable)

    def test_a_split_with_no_supported_world_is_named_not_scored_one(self):
        """Every candidate that abstains is perfect here, so the axis says nothing.

        Reporting the mathematical 1.0 would read as "recovered the mechanism" when nothing
        was recovered, which is worse than the division by zero it replaces.
        """
        result = normalize_mechanism(1.0, 5, 5)
        self.assertEqual(result.status, NO_SUPPORTED_WORLDS)
        self.assertEqual(result.value, 0.0)
        self.assertFalse(result.measurable)

    def test_an_impossible_baseline_is_rejected(self):
        with self.assertRaises(ValueError):
            always_abstain(4, 3)


class RateTests(unittest.TestCase):
    def test_a_rate_cannot_be_built_without_its_denominator(self):
        with self.assertRaises(TypeError):
            Rate(numerator=1.0)  # type: ignore[call-arg]

    def test_a_zero_denominator_yields_no_value_not_zero(self):
        """`0/0` is not a measurement, and `0.0` is a measurement of nothing."""
        rate = Rate(numerator=0.0, denominator=0.0)
        self.assertIsNone(rate.value)
        self.assertFalse(rate.readable)

    def test_a_numerator_above_its_denominator_is_rejected(self):
        with self.assertRaises(ValueError):
            Rate(numerator=5.0, denominator=3.0)


class DiscoveryAxesConstructionTests(unittest.TestCase):
    @staticmethod
    def _axes(**overrides):
        values = dict(
            mechanism=Rate(numerator=5.49, denominator=9),
            false_discovery=Rate(numerator=0.0, denominator=7),
            refusal=Rate(numerator=2.0, denominator=2),
            attempted=Rate(numerator=7.0, denominator=9),
        )
        values.update(overrides)
        return DiscoveryAxes(**values)

    def test_every_axis_is_required(self):
        """No partial construction: the contract cannot be half-satisfied."""
        for missing in AXES:
            values = dict(mechanism=Rate(1.0, 9), false_discovery=Rate(0.0, 9),
                          refusal=Rate(1.0, 2), attempted=Rate(7.0, 9))
            del values[missing]
            with self.subTest(missing=missing), self.assertRaises(TypeError):
                DiscoveryAxes(**values)

    def test_the_published_block_carries_every_rate_and_its_count(self):
        metrics = self._axes().as_metrics()
        for axis, suffix in (("false_discovery", "false_discovery_denominator"),
                             ("refusal", "correct_refusal_denominator"),
                             ("attempted", "attempted_discovery_denominator")):
            self.assertIn(suffix, metrics, axis)
        self.assertIn("mechanism_denominator", metrics)

    def test_the_mechanism_rate_published_is_the_normalized_one(self):
        """The defect this module exists to stop.

        Seven evaluators publish the raw mean under `mechanism_score` while `combined_score`
        uses the normalized value, so a blanket abstainer reports its free credit on the
        axis. The envelope must publish the value the headline was computed from.
        """
        metrics = self._axes().as_metrics()
        expected = self._axes().normalized_mechanism.value
        self.assertEqual(metrics["mechanism_score"], expected)
        self.assertEqual(metrics["normalized_mechanism"], expected)
        self.assertNotAlmostEqual(metrics["mechanism_score"], metrics["raw_mechanism"])

    def test_split_prefixes_apply_to_every_published_key(self):
        metrics = self._axes().as_metrics(prefix="heldout_")
        for key in ("heldout_mechanism_score", "heldout_mechanism_denominator",
                    "heldout_false_discovery_denominator",
                    "heldout_correct_refusal_denominator",
                    "heldout_attempted_discovery_denominator"):
            self.assertIn(key, metrics)

    def test_a_blanket_abstainer_envelope_scores_exactly_zero(self):
        """The end-to-end property: abstain on all nine worlds, two of them unsupported."""
        axes = self._axes(mechanism=Rate(numerator=2.0, denominator=9))
        metrics = axes.as_metrics()
        self.assertEqual(metrics["mechanism_score"], 0.0)
        self.assertEqual(metrics["raw_mechanism"], metrics["always_abstain"])

    def test_problems_names_what_is_unreadable(self):
        axes = self._axes(refusal=Rate(numerator=0.0, denominator=0))
        self.assertTrue(any("refusal has no denominator" in p for p in axes.problems()))
        self.assertEqual(self._axes().problems(), [])

    def test_problems_names_a_split_with_nothing_to_recover(self):
        axes = self._axes(mechanism=Rate(numerator=9.0, denominator=9),
                          refusal=Rate(numerator=9.0, denominator=9))
        self.assertTrue(any(NO_SUPPORTED_WORLDS in p for p in axes.problems()))


class SourceContractTests(unittest.TestCase):
    def test_a_compliant_evaluator_passes(self):
        self.assertEqual(axis_findings(COMPLIANT)["problems"], [])
        self.assertEqual(axis_findings(COMPLIANT)["undocumented_rates"], [])

    def test_rates_with_no_denominator_are_caught(self):
        """A rate is unreadable without the count it is a rate of."""
        source = evaluator(
            '{"mechanism_score": m, "false_discovery_rate": f, '
            '"correct_refusal_rate": r, "attempted_discovery": a}')
        findings = axis_findings(source)
        self.assertEqual(len(findings["undocumented_rates"]), 4)
        self.assertIn("attempted_discovery", findings["undocumented_rates"])

    def test_a_rate_at_one_split_is_not_covered_by_a_count_at_another(self):
        """Heldout and development have different world counts.

        A shared count is the same defect as none: the reader cannot tell which denominator
        the heldout rate was divided by.
        """
        source = evaluator(
            '{"development_false_discovery_rate": f, '
            '"development_false_discovery_denominator": n, '
            '"heldout_false_discovery_rate": h, '
            '"mechanism_score": m, "mechanism_denominator": n, '
            '"correct_refusal_rate": r, "correct_refusal_denominator": n, '
            '"attempted_discovery": a, "attempted_discovery_denominator": n}')
        findings = axis_findings(source)
        self.assertEqual(findings["undocumented_rates"], ["heldout_false_discovery_rate"])

    def test_a_missing_attempted_column_is_caught(self):
        source = evaluator(
            '{"mechanism_score": m, "mechanism_denominator": n, '
            '"false_discovery_rate": f, "false_discovery_denominator": n, '
            '"correct_refusal_rate": r, "correct_refusal_denominator": n}')
        findings = axis_findings(source)
        self.assertTrue(any("attempted-discovery" in p for p in findings["problems"]), findings)

    def test_coverage_counts_as_the_attempted_column(self):
        """A coverage of zero over the worlds that admit a claim is never having attempted."""
        source = evaluator(
            '{"mechanism_score": m, "mechanism_denominator": n, '
            '"false_discovery_rate": f, "false_discovery_denominator": n, '
            '"correct_refusal_rate": r, "correct_refusal_denominator": n, '
            '"discovery_coverage": c, "discovery_denominator": n}')
        self.assertEqual(axis_findings(source)["problems"], [])

    def test_axes_collapsed_onto_one_number_are_caught(self):
        """`combined_score` is the headline; the triple has to be recoverable without it."""
        source = evaluator(
            '{"mechanism_score": combined, "mechanism_denominator": n, '
            '"false_discovery_rate": combined, "false_discovery_denominator": n, '
            '"correct_refusal_rate": combined, "correct_refusal_denominator": n, '
            '"attempted_discovery": a, "attempted_discovery_denominator": n}')
        findings = axis_findings(source)
        self.assertTrue(any("same expression" in p for p in findings["problems"]), findings)

    def test_a_shared_placeholder_literal_is_not_a_collapsed_axis(self):
        """The tree publishes literal 0.0/1.0 placeholders; those are not one number in three."""
        source = evaluator(
            '{"mechanism_score": 0.0, "mechanism_denominator": n, '
            '"false_discovery_rate": 0.0, "false_discovery_denominator": n, '
            '"correct_refusal_rate": 1.0, "correct_refusal_denominator": n, '
            '"attempted_discovery": 0.0, "attempted_discovery_denominator": n}')
        self.assertEqual(axis_findings(source)["problems"], [])

    def test_a_mechanism_axis_bound_to_the_raw_value_is_caught(self):
        source = evaluator(
            '{"mechanism_score": dev["raw_mechanism"], "mechanism_denominator": n, '
            '"false_discovery_rate": f, "false_discovery_denominator": n, '
            '"correct_refusal_rate": r, "correct_refusal_denominator": n, '
            '"attempted_discovery": a, "attempted_discovery_denominator": n}')
        findings = axis_findings(source)
        self.assertTrue(any("raw mechanism" in p for p in findings["problems"]), findings)

    def test_a_raw_companion_key_is_not_mistaken_for_the_axis(self):
        """`development_raw_mechanism` names the pre-normalization number, not a second axis."""
        source = evaluator(
            '{"mechanism_score": m, "mechanism_denominator": n, '
            '"development_raw_mechanism": raw, '
            '"false_discovery_rate": f, "false_discovery_denominator": n, '
            '"correct_refusal_rate": r, "correct_refusal_denominator": n, '
            '"attempted_discovery": a, "attempted_discovery_denominator": n}')
        findings = axis_findings(source)
        self.assertEqual(findings["problems"], [])
        self.assertNotIn("development_raw_mechanism", findings["rates"]["mechanism"])

    def test_keys_built_dynamically_are_still_seen_to_be_absent(self):
        """A key the static reader cannot resolve is not counted as published."""
        keys = metric_keys("def evaluate(c):\n    return {f'{split}_mechanism_score': m}\n")
        self.assertEqual(axis_findings(
            "def evaluate(c):\n    return {f'{split}_mechanism_score': m}\n")["problems"],
            axis_findings(evaluator('{}'))["problems"])

    def test_a_nested_summary_beside_the_payload_is_read_as_published(self):
        """A known over-acceptance, pinned so a later reader does not mistake it for a bug.

        The tree's dominant shape computes a per-split summary and spreads it into the
        returned dict (``**{split: value for ...}``). Resolving that spread is the same
        static-analysis problem as `eval`, so the reader accepts a key anywhere in the
        verification source rather than only in a returned literal. A nested summary that is
        never returned therefore passes this check while its payload omits the axis.

        Two things bound the cost: the inventory cannot shrink for such a task, and the
        eval-time check in the gate sees the real returned metrics and fails a candidate
        that does not publish the axes it claims. Widening this to a whole-payload dataflow
        analysis is not worth its failure modes for a guard whose false-accept direction is
        already covered.
        """
        source = (
            "def _split(records):\n"
            "    return {'mechanism_score': m, 'mechanism_denominator': n, "
            "'false_discovery_rate': f, 'false_discovery_denominator': n, "
            "'correct_refusal_rate': r, 'correct_refusal_denominator': n, "
            "'attempted_discovery': a, 'attempted_discovery_denominator': n}\n"
            "\n"
            "def evaluate(candidate):\n"
            "    return {'combined_score': 0.0, 'valid': 1.0}\n"
        )
        self.assertEqual(axis_findings(source)["problems"], [])

    def test_the_real_inventory_is_exactly_the_non_compliant_set(self):
        """Pin the inventory to the tree, so a fix cannot leave a stale pending entry.

        This is the shrink-only property: a task removed from the inventory because its
        evaluator was fixed must pass the check, and a task that regresses is neither in the
        inventory nor compliant, so it fails.
        """
        document = json.loads(MIGRATION.read_text(encoding="utf-8"))
        pending = set(document["tasks"])
        self.assertEqual(sorted(pending), noncompliant_task_ids())
        self.assertTrue(pending < set(discovery_task_ids()),
                        "at least one discovery task must already comply")
        for task_id, entry in document["tasks"].items():
            with self.subTest(task=task_id):
                self.assertEqual(entry["status"], "pending")
                self.assertTrue(entry["reason"].strip())

    def test_the_policy_says_listing_is_not_a_pass(self):
        document = json.loads(MIGRATION.read_text(encoding="utf-8"))
        self.assertEqual(document["schema_version"], 1)
        self.assertIn("never a pass", document["policy"])
        self.assertTrue(document["inventory_revision"])


class InspectionVerdictTests(unittest.TestCase):
    """`inspect_axes` must not fail open: only a listed task is pending."""

    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "verification").mkdir()
        self.spec = SimpleNamespace(task_id="Fixture/Task", task_dir=self.root)

    def write(self, source):
        (self.root / "verification" / "evaluator.py").write_text(source, encoding="utf-8")

    def test_an_unlisted_non_compliant_task_fails(self):
        """A new package that omits the fourth column must be rejected, not listed."""
        self.write(evaluator(
            '{"mechanism_score": m, "mechanism_denominator": n, '
            '"false_discovery_rate": f, "false_discovery_denominator": n, '
            '"correct_refusal_rate": r, "correct_refusal_denominator": n}'))
        result = inspect_axes(self.spec)
        self.assertEqual(result["status"], "failed")
        self.assertFalse(result["passed"])
        self.assertIsInstance(result["detail"], str)

    def test_an_unlisted_compliant_task_passes(self):
        self.write(COMPLIANT)
        result = inspect_axes(self.spec)
        self.assertEqual(result["status"], "passed")
        self.assertTrue(result["passed"])

    def test_a_listed_task_is_pending_and_never_passes(self):
        self.write(evaluator('{"combined_score": 0.0, "valid": 1.0}'))
        with mock.patch.object(module, "_migration_record",
                               return_value={"status": "pending", "reason": "legacy"}):
            result = module.inspect_axes(self.spec)
        self.assertEqual(result["status"], "migration_pending")
        self.assertFalse(result["passed"], "a listed task must never read as passing")
        self.assertEqual(result["detail"], "legacy")

    def test_the_real_inventory_does_not_hide_a_new_non_compliant_package(self):
        """A fixture id is not in the inventory, so the verdict is `failed`."""
        self.write(evaluator('{"combined_score": 0.0, "valid": 1.0}'))
        self.assertEqual(inspect_axes(self.spec)["status"], "failed")

    def test_an_empty_verification_directory_fails(self):
        self.write("")
        self.assertEqual(inspect_axes(self.spec)["status"], "failed")


class GateIntegrationTests(unittest.TestCase):
    """The gate must report pending as incomplete, never as passed."""

    @staticmethod
    def _run(task_id):
        import scripts.check_task_contribution as gate
        report = gate.check_task(task_id, skip_eval=True)
        row = next((r for r in report["checks"] if r["check"] == "discovery_axis_contract"),
                   None)
        return report, row

    def test_a_non_discovery_task_has_no_contract_row(self):
        report, row = self._run("Algorithm/MatrixMultiplicationRank")
        self.assertIsNone(row)

    def test_a_pending_task_reports_pending_not_passed(self):
        report, row = self._run("PopulationGenetics/DemographicSFS")
        self.assertIsNone(row["ok"])
        self.assertEqual(row["status"], "migration_pending")
        self.assertIsInstance(row["detail"], str)
        self.assertFalse(report["passed"])
        self.assertEqual(report["status"], "incomplete")
        self.assertNotIn("failed", report["phases"].values())
        # Pending is not an exemption from the rest of the gate, either.
        self.assertEqual(report["phases"]["runtime"], "incomplete")

    def test_a_compliant_task_passes_the_contract_row(self):
        _, row = self._run("Sensors/IMUBiasCalibration")
        self.assertIs(row["ok"], True)

    def test_the_contract_row_reads_source_so_it_is_present_under_skip_eval(self):
        """The only form that runs where the candidate sandbox does not."""
        report, row = self._run("MaterialsScience/PhaseDiagramDiscovery")
        self.assertIn(row["status"], {"migration_pending", "passed", "failed"})
        self.assertTrue(any(r["check"] == "discovery_axis_contract" for r in report["checks"]))

    def test_the_structural_phase_is_untouched_by_a_pending_axis_contract(self):
        """The inventory must not turn a passing structural phase into an incomplete one.

        `test_task_contribution_gate` pins that PhaseDiagramDiscovery and the wave-2
        packages pass the structural half; putting the source check in that phase would make
        every task admitted before the requirement fail a check it never had.
        """
        report, _ = self._run("MaterialsScience/PhaseDiagramDiscovery")
        self.assertEqual(report["phases"]["structural"], "passed")


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import importlib.util
import json
import tempfile
import textwrap
import unittest
from pathlib import Path

import numpy as np

from sle.evaluate import evaluate_candidate
from sle.metric_visibility import search_visible_metrics
from sle.registry import find_task
from _sandbox_tools import skip_unless_sandbox  # noqa: E402


ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT / "benchmarks/Chemistry/CatalystDeactivationLab"
CALIBRATION = ROOT / "scripts/calibrate_catalyst_deactivation_lab.py"
ADMISSION = ROOT / "scripts/audit_candidate_wave7.py"


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ORACLE = _load(TASK / "verification/evaluator.py", "catalyst_lab_oracle")


class CatalystDeactivationLabTests(unittest.TestCase):
    def evaluate_source(self, source, timeout=90):
        spec = find_task(
            "Catalysis/CatalystDeactivationLab", include_uncertified=True
        )
        with tempfile.TemporaryDirectory() as tmp:
            candidate = Path(tmp) / "candidate.py"
            candidate.write_text(textwrap.dedent(source), encoding="utf-8")
            return evaluate_candidate(spec, candidate, timeout_s=timeout)

    def test_closed_form_matches_independent_midpoint_quadrature(self):
        rng = np.random.default_rng(491)
        for _ in range(12):
            values = (
                float(rng.uniform(0.65, 1.0)),
                float(rng.uniform(5.65, 6.35)),
                float(rng.uniform(55.0, 72.0)),
                float(rng.uniform(0.007, 0.018)),
                float(rng.uniform(*ORACLE.TEMPERATURE_BOUNDS)),
                float(rng.uniform(*ORACLE.CONCENTRATION_BOUNDS)),
                float(rng.uniform(*ORACLE.DURATION_BOUNDS)),
            )
            exact = ORACLE._closed_form_reaction(*values)
            independent = ORACLE._numerical_reaction(*values)
            self.assertAlmostEqual(exact[1], independent[1], places=12)
            self.assertLess(abs(exact[0] - independent[0]), 3e-9)

    def test_exact_retry_is_idempotent_and_batch_completes_out_of_order(self):
        laboratory = ORACLE._StatefulLaboratory(
            ORACLE._make_world(ORACLE.DEVELOPMENT_SPECS[0])
        )
        problem = laboratory.public_problem()
        coupon = problem["coupon_ids"][0]
        reaction = {
            "request_id": "slow-reaction",
            "kind": "reaction",
            "lab_state_version": 0,
            "coupon_id": coupon,
            "coupon_state_version": 0,
            "temperature_k": 445.0,
            "feed_concentration": 0.25,
            "duration_min": 15.0,
        }
        response = laboratory.experiment([
            reaction,
            {"request_id": "quick-blank", "kind": "blank",
             "lab_state_version": 0},
            {"request_id": "quick-standard", "kind": "standard",
             "lab_state_version": 0},
        ])
        self.assertEqual(laboratory.physical_acts, 3)
        self.assertEqual(laboratory.out_of_order_batch_count, 1)
        self.assertNotEqual(response["events"][0]["request_id"], "slow-reaction")
        cached = laboratory.experiment([reaction])
        self.assertEqual(laboratory.physical_acts, 3)
        self.assertEqual(laboratory.exact_retry_count, 1)
        self.assertEqual(
            cached["events"][0]["event_id"],
            next(event["event_id"] for event in response["events"]
                 if event["request_id"] == "slow-reaction"),
        )

    def test_reaction_irreversibly_updates_coupon_lineage(self):
        laboratory = ORACLE._StatefulLaboratory(
            ORACLE._make_world(ORACLE.DEVELOPMENT_SPECS[1])
        )
        problem = laboratory.public_problem()
        coupon = problem["coupon_ids"][0]
        lab_version = 0
        coupon_version = 0
        signals = []
        parent = None
        for index in range(3):
            response = laboratory.experiment([{
                "request_id": "cycle-%d" % index,
                "kind": "reaction",
                "lab_state_version": lab_version,
                "coupon_id": coupon,
                "coupon_state_version": coupon_version,
                "temperature_k": 535.0,
                "feed_concentration": 0.90,
                "duration_min": 6.0,
            }])
            event = response["events"][0]
            self.assertEqual(event["coupon_parent_event_id"], parent)
            parent = event["event_id"]
            lab_version = response["lab_state_version"]
            coupon_version = response["coupon_state_versions"][coupon]
            signals.append(event["raw_signal"])
        self.assertEqual(coupon_version, 3)
        self.assertEqual(response["coupon_remaining_uses"][coupon], 0)
        self.assertGreater(signals[0], signals[-1])

    @skip_unless_sandbox("bwrap")  # exercises the candidate sandbox; skipped only where none can exist
    def test_stale_parent_conflicting_retry_and_exhaustion_fail_closed(self):
        for mode in ("stale", "conflict", "exhaust"):
            with self.subTest(mode=mode):
                result = self.evaluate_source(
                    """
                    def investigate_catalyst(problem, experiment):
                        coupon = problem['coupon_ids'][0]
                        version = problem['lab_state_version']
                        coupon_version = problem['coupon_state_versions'][coupon]
                        first = {'request_id':'x','kind':'reaction',
                                 'lab_state_version':version,
                                 'coupon_id':coupon,
                                 'coupon_state_version':coupon_version,
                                 'temperature_k':500.0,
                                 'feed_concentration':0.5,
                                 'duration_min':5.0}
                        response = experiment([first])
                        try:
                            if %r == 'stale':
                                second = {'request_id':'y','kind':'blank',
                                          'lab_state_version':version}
                                experiment([second])
                            elif %r == 'conflict':
                                changed = dict(first)
                                changed['duration_min'] = 6.0
                                experiment([changed])
                            else:
                                lab = response['lab_state_version']
                                cv = response['coupon_state_versions'][coupon]
                                for i in range(3):
                                    nxt = {'request_id':'z'+str(i),'kind':'reaction',
                                           'lab_state_version':lab,
                                           'coupon_id':coupon,
                                           'coupon_state_version':cv,
                                           'temperature_k':500.0,
                                           'feed_concentration':0.5,
                                           'duration_min':5.0}
                                    response = experiment([nxt])
                                    lab = response['lab_state_version']
                                    cv = response['coupon_state_versions'][coupon]
                        except Exception:
                            pass
                        return {'log10_preexponential':6.0,
                                'activation_energy_kj_mol':60.0,
                                'deactivation_rate_per_min':0.012,
                                'gain_drift_per_event':0.0,
                                'offset_drift_per_event':0.0,
                                'operating_policy':{'temperature_k':500.0,
                                  'feed_concentration':0.5,'duration_min':8.0},
                                'confidence':0.0,'abstain':True,
                                'evidence_event_ids':[response['events'][0]['event_id']],
                                'final_lab_state_version':response['lab_state_version'],
                                'final_coupon_state_versions':response['coupon_state_versions']}
                    """ % (mode, mode)
                )
                self.assertEqual(result["valid"], 0.0, result)
                self.assertEqual(result["combined_score"], 0.0, result)
                expected = {
                    "stale": "stale_parent",
                    "conflict": "conflicting_retry",
                    "exhaust": "sample_exhausted",
                }[mode]
                self.assertTrue(all(
                    row["failure_kind"] == expected
                    for row in result["per_world"][:5]
                ))

    @skip_unless_sandbox("bwrap")  # exercises the candidate sandbox; skipped only where none can exist
    def test_concurrent_same_coupon_and_overbudget_fail_closed_when_caught(self):
        for mode in ("concurrent", "overbudget"):
            with self.subTest(mode=mode):
                result = self.evaluate_source(
                    """
                    def investigate_catalyst(problem, experiment):
                        try:
                            if %r == 'concurrent':
                                coupon = problem['coupon_ids'][0]
                                common = {'kind':'reaction','lab_state_version':0,
                                  'coupon_id':coupon,'coupon_state_version':0,
                                  'temperature_k':500.0,'feed_concentration':0.5,
                                  'duration_min':5.0}
                                one = dict(common); one['request_id'] = 'one'
                                two = dict(common); two['request_id'] = 'two'
                                experiment([one, two])
                            else:
                                lab = 0
                                response = None
                                for i in range(13):
                                    response = experiment([{'request_id':'b'+str(i),
                                      'kind':'blank','lab_state_version':lab}])
                                    lab = response['lab_state_version']
                        except Exception:
                            pass
                        response = locals().get('response')
                        coupon_versions = problem['coupon_state_versions'] if response is None else response['coupon_state_versions']
                        lab = problem['lab_state_version'] if response is None else response['lab_state_version']
                        evidence = ['placeholder'] if response is None else [response['events'][0]['event_id']]
                        return {'log10_preexponential':6.0,
                                'activation_energy_kj_mol':60.0,
                                'deactivation_rate_per_min':0.012,
                                'gain_drift_per_event':0.0,
                                'offset_drift_per_event':0.0,
                                'operating_policy':{'temperature_k':500.0,
                                  'feed_concentration':0.5,'duration_min':8.0},
                                'confidence':0.0,'abstain':True,
                                'evidence_event_ids':evidence,
                                'final_lab_state_version':lab,
                                'final_coupon_state_versions':coupon_versions}
                    """ % mode
                )
                self.assertEqual(result["valid"], 0.0, result)
                expected = (
                    "concurrent_sample_conflict"
                    if mode == "concurrent" else "budget_exceeded"
                )
                self.assertTrue(all(
                    row["failure_kind"] == expected
                    for row in result["per_world"][:5]
                ))

    def test_public_events_expose_lineage_but_not_truth_or_calibration_state(self):
        laboratory = ORACLE._StatefulLaboratory(
            ORACLE._make_world(ORACLE.DEVELOPMENT_SPECS[2])
        )
        problem = laboratory.public_problem()
        coupon = problem["coupon_ids"][0]
        response = laboratory.experiment([{
            "request_id": "public-reaction",
            "kind": "reaction",
            "lab_state_version": 0,
            "coupon_id": coupon,
            "coupon_state_version": 0,
            "temperature_k": 500.0,
            "feed_concentration": 0.5,
            "duration_min": 5.0,
        }])
        event = response["events"][0]
        required = {
            "event_id", "scheduled_lab_state_version",
            "execution_parent_lab_state_version", "post_lab_state_version",
            "coupon_id", "scheduled_coupon_state_version",
            "coupon_parent_event_id", "post_coupon_state_version",
            "calibration_id", "calibration_parent_event_id", "raw_signal",
        }
        self.assertTrue(required.issubset(event))
        rendered = json.dumps(event, sort_keys=True).lower()
        for forbidden in (
            "true_product", "post_activity", "gain_base", "gain_drift",
            "offset_base", "offset_drift", "log10_a", "activation_energy",
            "d_ref", "site_fraction",
        ):
            self.assertNotIn(forbidden, rendered)

    @skip_unless_sandbox("bwrap")  # exercises the candidate sandbox; skipped only where none can exist
    def test_nonfinite_submission_fails_closed(self):
        result = self.evaluate_source(
            """
            import numpy as np
            def investigate_catalyst(problem, experiment):
                response = experiment([{'request_id':'blank','kind':'blank',
                    'lab_state_version':problem['lab_state_version']}])
                return {'log10_preexponential':np.nan,
                        'activation_energy_kj_mol':60.0,
                        'deactivation_rate_per_min':0.012,
                        'gain_drift_per_event':0.0,
                        'offset_drift_per_event':0.0,
                        'operating_policy':{'temperature_k':500.0,
                          'feed_concentration':0.5,'duration_min':8.0},
                        'confidence':0.0,'abstain':True,
                        'evidence_event_ids':[response['events'][0]['event_id']],
                        'final_lab_state_version':response['lab_state_version'],
                        'final_coupon_state_versions':response['coupon_state_versions']}
            """
        )
        self.assertEqual(result["valid"], 0.0, result)
        self.assertEqual(
            result["candidate_failure_kind"], "non_finite_candidate_value"
        )
        self.assertNotIn("per_world", result)

    @skip_unless_sandbox("bwrap")  # exercises the candidate sandbox; skipped only where none can exist
    def test_baseline_is_valid_zero_and_metrics_are_sealed(self):
        spec = find_task(
            "Catalysis/CatalystDeactivationLab", include_uncertified=True
        )
        metrics = evaluate_candidate(spec, spec.initial_program_path, timeout_s=90)
        self.assertEqual(metrics["valid"], 1.0, metrics)
        self.assertEqual(metrics["combined_score"], 0.0, metrics)
        self.assertEqual(metrics["candidate_instance_call_count"], 8)
        self.assertEqual(metrics["candidate_instance_valid_rate"], 1.0)
        visible = search_visible_metrics(metrics)
        for key in (
            "robustness_score", "heldout_policy_score",
            "development_mechanism_score", "development_lineage_score",
            "duplicate_physical_act_count", "per_world",
        ):
            self.assertNotIn(key, visible)

    def test_reference_has_headroom_transfer_refusal_and_state_coverage(self):
        metrics = ORACLE.evaluate(ORACLE._reference_agent)
        self.assertGreater(metrics["combined_score"], 0.85)
        self.assertLess(metrics["combined_score"], 0.995)
        self.assertGreater(metrics["heldout_policy_score"], 0.85)
        self.assertGreater(metrics["robustness_score"], 0.75)
        self.assertGreater(metrics["heldout_robustness_score"], 0.75)
        self.assertEqual(metrics["development_supported_claim_coverage"], 1.0)
        self.assertEqual(metrics["heldout_supported_claim_coverage"], 1.0)
        self.assertEqual(metrics["development_unsupported_refusal_rate"], 1.0)
        self.assertEqual(metrics["heldout_unsupported_refusal_rate"], 1.0)
        self.assertEqual(metrics["development_false_discovery_rate"], 0.0)
        self.assertEqual(metrics["heldout_false_discovery_rate"], 0.0)
        self.assertEqual(metrics["duplicate_physical_act_count"], 0)
        self.assertEqual(metrics["stale_parent_attempt_count"], 0)
        self.assertEqual(metrics["development_mean_physical_acts"], 12.0)
        self.assertEqual(metrics["development_mean_exact_retries"], 1.0)
        self.assertGreater(metrics["development_mean_out_of_order_batches"], 0.0)

    def test_truth_nominal_is_one_and_shift_is_distinct(self):
        differences = []
        for index, spec in enumerate(
            ORACLE.DEVELOPMENT_SPECS + ORACLE.HELDOUT_SPECS
        ):
            record = ORACLE._evaluate_truth_world(spec, index=index)
            self.assertEqual(record["joint_quality"], 1.0)
            self.assertTrue(0.0 <= record["robust_joint_quality"] <= 1.0)
            if spec[1] == "in_library":
                differences.append(
                    abs(record["joint_quality"] - record["robust_joint_quality"])
                )
        self.assertGreater(max(differences), 0.02)

    @skip_unless_sandbox("bwrap")  # exercises the candidate sandbox; skipped only where none can exist
    def test_all_worlds_get_fresh_candidate_processes(self):
        result = self.evaluate_source(
            """
            import os
            module_counter = 0
            def investigate_catalyst(problem, experiment):
                global module_counter
                module_counter += 1
                seen = os.path.exists('/tmp/catalyst-world-state')
                with open('/tmp/catalyst-world-state','w') as handle:
                    handle.write('seen')
                if module_counter != 1 or seen:
                    raise RuntimeError('candidate state leaked across worlds')
                response = experiment([{'request_id':'blank','kind':'blank',
                    'lab_state_version':problem['lab_state_version']}])
                return {'log10_preexponential':6.0,
                        'activation_energy_kj_mol':60.0,
                        'deactivation_rate_per_min':0.012,
                        'gain_drift_per_event':0.0,
                        'offset_drift_per_event':0.0,
                        'operating_policy':{'temperature_k':500.0,
                          'feed_concentration':0.5,'duration_min':8.0},
                        'confidence':0.0,'abstain':True,
                        'evidence_event_ids':[response['events'][0]['event_id']],
                        'final_lab_state_version':response['lab_state_version'],
                        'final_coupon_state_versions':response['coupon_state_versions']}
            """
        )
        self.assertEqual(result["valid"], 1.0, result)
        self.assertEqual(result["candidate_instance_call_count"], 8)

    def test_public_contract_does_not_expose_hidden_truth_or_splits(self):
        public = "\n".join(
            (TASK / path).read_text(encoding="utf-8")
            for path in (
                "Task.md", "solution.py", "frontier_eval/constraints.txt",
            )
        ).lower()
        for forbidden in (
            "18401", "28403", "development_specs", "heldout_specs",
            "shift_log10_a", "site_fraction", "gain_step", "_reference_agent",
        ):
            self.assertNotIn(forbidden, public)

    @skip_unless_sandbox("bwrap")  # exercises the candidate sandbox; skipped only where none can exist
    def test_calibration_and_admission_gates_execute(self):
        calibration = _load(CALIBRATION, "catalyst_lab_calibration_test").calibrate()
        self.assertTrue(calibration["execution_passed"], calibration)
        self.assertTrue(calibration["independent_integral_checks"]["passed"])
        self.assertTrue(calibration["state_machine_checks"]["passed"])
        self.assertGreater(
            calibration["truth_blind_reference"]["combined_score"], 0.85
        )
        admission = _load(ADMISSION, "catalyst_lab_admission_test").audit()
        self.assertTrue(admission["execution_passed"], admission)
        self.assertEqual(admission["summary"]["recommended_candidate_count"], 1)
        self.assertEqual(admission["summary"]["recommended_quarantine_count"], 0)


if __name__ == "__main__":
    unittest.main()

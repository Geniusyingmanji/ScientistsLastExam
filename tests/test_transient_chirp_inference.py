import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT / "benchmarks" / "Physics" / "TransientChirpInference"

def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

class TransientChirpInferenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ev = load(TASK / "verification" / "evaluator.py", "chirp_ev")
        cls.base = load(TASK / "solution.py", "chirp_base")
        cls.ref = load(TASK / "verification" / "reference_solver.py", "chirp_ref")

    def test_baseline_is_valid_and_zero(self):
        x = self.ev.evaluate(self.base.infer_transient)
        self.assertEqual(x["valid"], 1.0)
        self.assertEqual(x["combined_score"], 0.0)

    def test_reference_is_deterministic(self):
        a = self.ev.evaluate(self.ref.infer_transient)
        b = self.ev.evaluate(self.ref.infer_transient)
        self.assertEqual(a, b)
        self.assertGreater(a["combined_score"], 0.75)
        self.assertEqual(a["development_false_discovery_rate"], 0.0)
        self.assertEqual(a["development_correct_refusal_rate"], 1.0)

    def test_blanket_abstention_is_zero(self):
        def abstain(problem, observe):
            rows = [observe(float(t), "H1") for t in problem["candidate_times"][:6]]
            return {"abstain": True, "confidence": .5, "evidence_query_ids": [r["query_id"] for r in rows]}
        self.assertEqual(self.ev.evaluate(abstain)["combined_score"], 0.0)

    def test_duplicate_query_fails_closed(self):
        def duplicate(problem, observe):
            observe(0.0, "H1"); observe(0.0, "H1")
        self.assertEqual(self.ev.evaluate(duplicate)["valid"], 0.0)

    def test_world_families_present(self):
        kinds = {w["kind"] for w in self.ev.DEVELOPMENT_WORLDS}
        self.assertEqual(kinds, {"chirp", "line", "glitch", "ambiguous"})

    def test_noise_cannot_identify_any_family(self):
        for worlds in (self.ev.DEVELOPMENT_WORLDS, self.ev.HELDOUT_WORLDS):
            self.assertEqual({w["noise"] for w in worlds}, {self.ev.NOISE_SIGMA})

    def test_chirp_and_line_sign_counts_overlap(self):
        for worlds in (self.ev.DEVELOPMENT_WORLDS, self.ev.HELDOUT_WORLDS):
            features = {kind: set() for kind in ("chirp", "line")}
            for world in worlds:
                if world["kind"] not in features:
                    continue
                values = np.array([self.ev._strain(world, t, "H1") for t in range(12)])
                counts = tuple(int(np.sum(np.diff(np.signbit(part)))) for part in (values[:6], values[6:]))
                features[world["kind"]].add(counts)
            self.assertTrue(features["chirp"] & features["line"])

    def test_line_slope_is_scored_and_wrong_labels_get_no_parameter_credit(self):
        world = {"kind": "line", "f0": 0.12, "slope": 0.0, "amplitude": 0.6}
        good = {"abstain": False, "model": "line", "frequency": 0.12, "slope": 0.0,
                "amplitude": 0.6, "event_time": 9.0, "confidence": 0.8}
        right = self.ev._score(world, good)
        wrong_slope = self.ev._score(world, good | {"slope": 0.02})
        wrong_label = self.ev._score(world, good | {"model": "chirp"})
        self.assertAlmostEqual(right["science_score"] - wrong_slope["science_score"], 0.25)
        self.assertEqual(wrong_label["science_score"], 0.0)
        self.assertEqual(wrong_label["parameter_score"], 0.0)
        self.assertAlmostEqual(wrong_label["confidence_score"], 0.2)

    def test_denominators_and_actual_attempted_discovery(self):
        def abstain(problem, observe):
            ids = [observe(t, "H1")["query_id"] for t in problem["candidate_times"][:6]]
            return {"abstain": True, "confidence": 0.7, "evidence_query_ids": ids}
        result = self.ev.evaluate(abstain)
        for split, worlds in (("development", self.ev.DEVELOPMENT_WORLDS), ("heldout", self.ev.HELDOUT_WORLDS)):
            supported = sum(w["kind"] != "ambiguous" for w in worlds)
            self.assertEqual(result[split + "_mechanism_denominator"], supported)
            self.assertEqual(result[split + "_correct_refusal_denominator"], len(worlds) - supported)
            self.assertEqual(result[split + "_false_discovery_denominator"], 0)
            self.assertEqual(result[split + "_attempted_discovery"], 0)
            self.assertEqual(result[split + "_discovery_coverage"], 0)
        baseline = self.ev.evaluate(self.base.infer_transient)
        self.assertEqual(baseline["development_attempted_discovery"], 1)
        self.assertEqual(baseline["development_discovery_coverage"], 1)

    def test_model_accuracy_is_not_composite_score(self):
        worlds = ({"kind": "line"}, {"kind": "chirp"}, {"kind": "glitch"}, {"kind": "ambiguous"})
        def evaluated(candidate, w):
            supported = w["kind"] != "ambiguous"
            return {"supported": supported, "claimed": w["kind"] != "glitch",
                    "model_correct": w["kind"] == "line", "false_discovery": w["kind"] in {"chirp", "ambiguous"},
                    "correct_refusal": False, "science_score": 0.2 if w["kind"] == "line" else 0,
                    "parameter_score": 0, "amplitude_score": 0, "confidence_score": 0}, True, 6
        with patch.object(self.ev, "DEVELOPMENT_WORLDS", worlds), \
             patch.object(self.ev, "HELDOUT_WORLDS", worlds), \
             patch.object(self.ev, "_evaluate_one", side_effect=evaluated):
            result = self.ev.evaluate(None)
        self.assertEqual(result["development_mechanism_score"], 1 / 3)
        self.assertEqual(result["development_discovery_coverage"], 2 / 3)
        self.assertEqual(result["development_false_discovery_rate"], 2 / 3)
        self.assertNotEqual(result["development_mechanism_score"], result["development_science_score"])

    def test_malformed_matrix_and_key_parity(self):
        good = self.ev.evaluate(self.base.infer_transient)
        changes = [{"model": "bad"}, {"frequency_slope": -1}, {"frequency_slope": float("nan")},
                   {"amplitude": 2}, {"event_time": 19}, {"event_time": float("inf")},
                   {"confidence": -1}, {"confidence": float("nan")}, {"abstain": "yes"},
                   {"evidence_query_ids": []}, {"evidence_query_ids": ["fake"] * 6}]
        for change in changes:
            def candidate(problem, observe):
                return self.base.infer_transient(problem, observe) | change
            result = self.ev.evaluate(candidate)
            self.assertEqual(result["valid"], 0)
            self.assertEqual(result["combined_score"], 0)
            self.assertEqual(set(result), set(good))

    def test_retuned_sign_probe_stays_below_reference(self):
        calibration = load(TASK / "verification/calibrate.py", "chirp_probe_test")
        # Best development-selected member of the registered 1,620-policy grid.
        candidate = calibration.sign_count_policy(12, 0.28, 0.08, 0.05, 0, 0.006)
        probe = self.ev.evaluate(candidate)
        reference = self.ev.evaluate(self.ref.infer_transient)
        for key in ("combined_score", "robustness_score"):
            self.assertGreater(reference[key] - probe[key], 0.1)

    def test_morphology_grid_witness_stays_below_reference(self):
        calibration = load(TASK / "verification/calibrate.py", "chirp_morphology_test")
        candidate = calibration.morphology_policy(15, 0.10, 0.10, 2, 0.006)
        probe = self.ev.evaluate(candidate)
        reference = self.ev.evaluate(self.ref.infer_transient)
        for key in ("combined_score", "robustness_score"):
            self.assertGreater(reference[key] - probe[key], 0.10)

    def test_lookup_morphology_family_stays_below_reference(self):
        calibration = load(TASK / "verification/calibrate.py", "chirp_lookup_morphology_test")
        probe = self.ev.evaluate(calibration.lookup_morphology_policy(
            16, 0.08, 0.08, 7, (0.0, 0.006, 0.018, 0.028, 0.028), 1))
        reference = self.ev.evaluate(self.ref.infer_transient)
        self.assertAlmostEqual(probe["combined_score"], 0.6611830494930327)
        self.assertAlmostEqual(probe["robustness_score"], 0.5563081267357214)
        for key in ("combined_score", "robustness_score"):
            self.assertGreater(reference[key] - probe[key], 0.12)

    def test_reset_session_hook_is_called_before_every_world(self):
        baseline = self.base.infer_transient
        class Counter:
            calls = 0
            resets = 0
            def reset_session(self):
                self.calls = 0
                self.resets += 1
            def __call__(self, problem, observe):
                self.calls += 1
                if self.calls != 1:
                    raise RuntimeError("cross-world state")
                return baseline(problem, observe)
        candidate = Counter()
        self.assertEqual(self.ev.evaluate(candidate)["valid"], 1)
        self.assertEqual(candidate.resets, len(self.ev.DEVELOPMENT_WORLDS) + len(self.ev.HELDOUT_WORLDS))

if __name__ == "__main__": unittest.main()

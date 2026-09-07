import importlib.util
import unittest
from pathlib import Path

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
        self.assertGreater(a["combined_score"], 0.8)
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

if __name__ == "__main__": unittest.main()

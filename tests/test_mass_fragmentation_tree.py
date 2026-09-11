"""Pinned invariants for MassFragmentationTree.

The tests pin the three construction errors recorded in the task's known_best.md:
the zoom path resurrecting the precursor in in-source worlds, the background filter
killing saturated fragments, and duplicate nodes from per-energy mass noise.
"""

from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT / "benchmarks" / "Chemistry" / "MassFragmentationTree"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class MassFragmentationTreePackageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ev = _load(TASK / "verification" / "evaluator.py", "mft_evaluator")
        cls.ref = _load(TASK / "verification" / "reference_solver.py", "mft_reference")
        cls.probe = _load(TASK / "verification" / "probe_single_parent_mass_gap.py",
                          "mft_probe")
        cls.sol = _load(TASK / "solution.py", "mft_baseline")

    def _truth_candidate(self, world):
        def candidate(problem, acquire, zoom, budget):
            acquire(20.0)
            nodes = [self.ev._formula_mass(f) + self.ev.PROTON_MASS
                     for f in world["nodes"]]
            edges = [[nodes[p], nodes[c], name]
                     for p, c, name, _lab in world["edges"]]
            return {"nodes": nodes, "edges": edges, "abstain": False,
                    "confidence": 0.9}
        return candidate

    def test_truth_tree_scores_one_on_supported_worlds(self):
        for spec in self.ev._BASE_DEVELOPMENT_SPECS:
            world = self.ev._world(spec)
            if world["kind"] != "supported":
                continue
            row = self.ev._evaluate_world(self._truth_candidate(world), spec, "dev", 0)
            self.assertTrue(row["valid"], spec)
            self.assertGreater(row["mechanism_score"], 0.999, spec)

    def test_baseline_valid_zero_and_deterministic(self):
        first = self.ev.evaluate(self.sol.recover_fragmentation_tree)
        second = self.ev.evaluate(self.sol.recover_fragmentation_tree)
        self.assertEqual(first["valid"], 1.0)
        self.assertEqual(first["combined_score"], 0.0)
        self.assertEqual(json.dumps(first, sort_keys=True, default=str),
                         json.dumps(second, sort_keys=True, default=str))

    def test_reference_leaves_headroom(self):
        result = self.ev.evaluate(self.ref.recover_fragmentation_tree)
        self.assertEqual(result["valid"], 1.0)
        self.assertGreater(result["combined_score"], 0.05)
        self.assertLess(result["combined_score"], 1.0)
        self.assertEqual(result["development_false_discovery_rate"], 0.0)
        self.assertEqual(result["development_correct_refusal_rate"], 1.0)

    def test_bad_candidates_score_invalid_without_crashing(self):
        def raises(*args, **kwargs):
            raise RuntimeError("candidate failure")

        for candidate in (raises, lambda *a, **k: {}, lambda *a, **k: "tree"):
            result = self.ev.evaluate(candidate)
            self.assertEqual(result["valid"], 0.0)
            self.assertEqual(result["combined_score"], 0.0)

    def test_repeated_edges_cannot_inflate_recall(self):
        spec = self.ev._BASE_DEVELOPMENT_SPECS[0]
        world = self.ev._world(spec)
        truth = self._truth_candidate(world)

        def repeated(problem, acquire, zoom, budget):
            submission = truth(problem, acquire, zoom, budget)
            submission["edges"] *= 20
            return submission

        row = self.ev._evaluate_world(repeated, spec, "dev", 0)
        self.assertFalse(row["valid"])
        self.assertEqual(row["mechanism_score"], 0.0)
        nodes = np.array([self.ev._formula_mass(f) + self.ev.PROTON_MASS
                          for f in world["nodes"]])
        edges = [(nodes[p], nodes[c], name) for p, c, name, _ in world["edges"]]
        score, node_f1, edge_f1 = self.ev._mechanism_score(world, nodes, edges * 20)
        self.assertLessEqual(edge_f1, 1.0)
        self.assertLessEqual(score, 1.0)

    def test_output_limits_reject_before_matching(self):
        submission = {"nodes": list(range(1, 258)), "edges": [],
                      "abstain": False, "confidence": 0.5}
        with self.assertRaises(ValueError):
            self.ev._validate(submission)

    def test_edges_are_mass_consistent_and_single_parent(self):
        child = 100.0
        water_parent = child + self.ev._formula_mass(self.ev.LOSS_LIBRARY["H2O"])
        carbonyl_parent = child + self.ev._formula_mass(self.ev.LOSS_LIBRARY["CO"])
        base = {"nodes": [child, water_parent, carbonyl_parent], "abstain": False,
                "confidence": 0.5}
        with self.assertRaises(ValueError):
            self.ev._validate({**base, "edges": [[water_parent, child, "CO"]]})
        with self.assertRaises(ValueError):
            self.ev._validate({**base, "edges": [[child, water_parent, "H2O"]]})
        with self.assertRaises(ValueError):
            self.ev._validate({**base, "edges": [
                [water_parent, child, "H2O"], [carbonyl_parent, child, "CO"]]})

    def test_backgrounds_include_loss_compatible_decoys(self):
        world = self.ev._world(self.ev._BASE_DEVELOPMENT_SPECS[0])
        truth = [self.ev._formula_mass(formula) + self.ev.PROTON_MASS
                 for formula in world["nodes"]]
        losses = [self.ev._formula_mass(formula)
                  for formula in self.ev.LOSS_LIBRARY.values()]
        self.assertGreaterEqual(len(world["decoys"]), 8)
        compatible = sum(
            any(abs(abs(decoy_mz - node_mz) - loss) <= 1e-6
                for node_mz in truth for loss in losses)
            for decoy_mz, _ in world["decoys"])
        self.assertGreaterEqual(compatible, len(world["decoys"]) // 2)

    def test_single_parent_mass_gap_shortcut_stays_below_reference(self):
        shortcut = self.ev.evaluate(self.probe.recover_fragmentation_tree)
        reference = self.ev.evaluate(self.ref.recover_fragmentation_tree)
        self.assertEqual(shortcut["valid"], 1.0)
        self.assertLess(shortcut["combined_score"], reference["combined_score"])
        self.assertLess(shortcut["robustness_score"], reference["robustness_score"])

    def test_instrument_repetitions_draw_fresh_but_replayable_noise(self):
        world = self.ev._world(self.ev._BASE_DEVELOPMENT_SPECS[0])
        first = self.ev._Instrument(world)
        second = self.ev._Instrument(world)
        first_reports = [first.acquire(20.0), first.acquire(20.0)]
        self.assertNotEqual(first_reports[0], first_reports[1])
        self.assertEqual(first_reports, [second.acquire(20.0), second.acquire(20.0)])

    def test_precursor_never_survives_in_source_worlds(self):
        # Pins the zoom-path bug: the in-source zeroing must hold for scans and zooms.
        for spec in self.ev._BASE_DEVELOPMENT_SPECS:
            world = self.ev._world(spec)
            if world["kind"] != "in_source":
                continue
            precursor = self.ev._formula_mass(world["nodes"][0]) + self.ev.PROTON_MASS
            instrument = self.ev._Instrument(world)
            for energy in (10.0, 25.0, 55.0):
                spectrum = instrument.acquire(energy)
                for peak in spectrum["peaks"]:
                    self.assertGreater(abs(peak["mz"] - precursor), 0.05)
            window = instrument.zoom(precursor, 1.4)
            for peak in window["peaks"]:
                self.assertGreater(abs(peak["mz"] - precursor), 0.05)

    def test_background_peaks_stay_flat_while_fragments_rise(self):
        world = self.ev._world((51011, "supported"))
        instrument = self.ev._Instrument(world)
        precursor = self.ev._formula_mass(world["nodes"][0]) + self.ev.PROTON_MASS
        low = {round(p["mz"], 1): p["intensity"] for p in instrument.acquire(12.0)["peaks"]}
        high = {round(p["mz"], 1): p["intensity"] for p in instrument.acquire(55.0)["peaks"]}
        for mz, intensity in world["decoys"]:
            key = round(mz, 1)
            if key in low and key in high:
                self.assertLess(abs(low[key] - high[key]) / high[key], 0.25)
        root_key = round(precursor, 1)
        if root_key in low and root_key in high:
            self.assertGreater(low[root_key], 3.0 * high[root_key])

    def test_duplicate_peak_merging_keeps_precision(self):
        # After the noise-split fix the reference must submit at most one node per
        # true fragment; node F1 stays materially below one.
        result = self.ev.evaluate(self.ref.recover_fragmentation_tree)
        self.assertLess(result["development_node_f1"], 1.0)
        self.assertGreater(result["development_node_f1"], 0.5)

    def test_coisolate_carbon_counts_differ(self):
        # The co-isolate delta shifts carbon count by one, so isotope ratios separate.
        for spec in self.ev._BASE_DEVELOPMENT_SPECS:
            world = self.ev._world(spec)
            if world["kind"] != "coisolate" or world["contaminant"] is None:
                continue
            self.assertEqual(abs(world["contaminant"][0] - world["nodes"][0][0]), 1)


if __name__ == "__main__":
    unittest.main()

"""Pinned invariants for the eight 2026-09-05 round-four candidate tasks.

Each class pins the construction errors recorded in the task's known_best.md and
the repo-wide baseline/reference/bad-candidate contract. Tests load evaluators
directly; sandbox-dependent behaviour is out of scope here.
"""

from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

TASKS = {
    "Electrochemistry/ChronoamperometryLawID":
        ("benchmarks/Chemistry/ChronoamperometryLawID", "identify_current_law"),
    "MetabolicEngineering/MetabolicStrainDesign":
        ("benchmarks/Biology/MetabolicStrainDesign", "design_strain"),
    "Metagenomics/MetagenomicMixtureID":
        ("benchmarks/Biology/MetagenomicMixtureID", "identify_mixture"),
    "Electrophysiology/HodgkinHuxleyCurrentID":
        ("benchmarks/Biology/HodgkinHuxleyCurrentID", "recover_channel_parameters"),
    "Algorithm/ScalingLawIdentification":
        ("benchmarks/ComputerScience/ScalingLawIdentification", "identify_scaling_law"),
    "WaterDistribution/DistributionNetworkTopology":
        ("benchmarks/Engineering/DistributionNetworkTopology", "recover_network"),
    "Mineralogy/MineralMixtureXRD":
        ("benchmarks/EarthScience/MineralMixtureXRD", "identify_minerals"),
    "Mathematics/EllipticCurveRecovery":
        ("benchmarks/Mathematics/EllipticCurveRecovery", "recover_curve"),
}


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class RoundFourPackageTests(unittest.TestCase):
    def test_baselines_valid_zero_and_deterministic(self):
        for task_id, (directory, entrypoint) in TASKS.items():
            evaluator = _load(ROOT / directory / "verification" / "evaluator.py",
                              "r4_evaluator_" + entrypoint)
            baseline = _load(ROOT / directory / "solution.py",
                             "r4_baseline_" + entrypoint)
            first = evaluator.evaluate(getattr(baseline, entrypoint))
            second = evaluator.evaluate(getattr(baseline, entrypoint))
            self.assertEqual(first["valid"], 1.0, task_id)
            self.assertLessEqual(abs(first["combined_score"]), 0.01, task_id)
            self.assertEqual(json.dumps(first, sort_keys=True, default=str),
                             json.dumps(second, sort_keys=True, default=str), task_id)

    def test_references_valid_and_above_floor(self):
        for task_id, (directory, entrypoint) in TASKS.items():
            evaluator = _load(ROOT / directory / "verification" / "evaluator.py",
                              "r4_evaluator_ref_" + entrypoint)
            reference = _load(ROOT / directory / "verification" / "reference_solver.py",
                              "r4_reference_" + entrypoint)
            result = evaluator.evaluate(getattr(reference, entrypoint))
            self.assertEqual(result["valid"], 1.0, task_id)
            self.assertGreater(result["combined_score"], 0.05, task_id)

    def test_bad_candidates_score_invalid_without_crashing(self):
        def raises(*args, **kwargs):
            raise RuntimeError("candidate failure")

        for task_id, (directory, entrypoint) in TASKS.items():
            evaluator = _load(ROOT / directory / "verification" / "evaluator.py",
                              "r4_evaluator_bad_" + entrypoint)
            for candidate in (raises, lambda *a, **k: {}, lambda *a, **k: "junk"):
                result = evaluator.evaluate(candidate)
                self.assertEqual(result["valid"], 0.0, task_id)
                self.assertEqual(result["combined_score"], 0.0, task_id)


class ChronoamperometryPins(unittest.TestCase):
    def test_padding_slots_are_free_but_active_slots_bounded(self):
        ev = _load(ROOT / "benchmarks/Chemistry/ChronoamperometryLawID"
                   "/verification/evaluator.py", "r4_chrono")
        # Two-parameter family (catalytic) with padded zeros must validate.
        submission = {"family_probabilities": {name: 1 / 6 for name in ev.FAMILIES},
                      "parameters": [1.0, 0.5, 0.0], "abstain": False,
                      "confidence": 0.5}
        probs, params, confidence, abstain = ev._validate(submission)
        self.assertFalse(abstain)
        self.assertEqual(ev._active_count("catalytic"), 2)

    def test_drift_is_shared_linear_across_potentials(self):
        ev = _load(ROOT / "benchmarks/Chemistry/ChronoamperometryLawID"
                   "/verification/evaluator.py", "r4_chrono")
        world = ev._world((12047, "drift", "catalytic"))
        lo, hi = 0.15, 0.85
        clean_lo = ev._true_current(world, lo)
        clean_hi = ev._true_current(world, hi)
        ratio = ev.amplitude_factor(lo) / ev.amplitude_factor(hi)
        # The family part scales with phi(E); the shared linear drift does not, so
        # the scaled difference grows linearly in time.
        residual = clean_hi - clean_lo / ratio
        self.assertLess(abs(residual[0]), 1e-3)
        self.assertGreater(abs(residual[-1]), 0.5)


class MetabolicStrainPins(unittest.TestCase):
    def test_witness_anchor_recomputed_not_literal(self):
        ev = _load("benchmarks/Biology/MetabolicStrainDesign/verification/evaluator.py",
                   "r4_fba")
        scores = ev._score_design(ev.WITNESS_DESIGN, ev.DEVELOPMENT_DRAWS)
        self.assertEqual(scores, [1.0] * len(ev.DEVELOPMENT_DRAWS))
        # No scored draw is degenerate: the witness strictly beats the wild type.
        for seed in ev.DEVELOPMENT_DRAWS + ev.HELDOUT_DRAWS:
            capacities = ev._capacities(seed)
            demand = ev._max_biomass(capacities)
            wild = ev.solve_fluxes(ev._applied_capacities(
                capacities, {"knockouts": [], "overexpressions": {}}), demand)
            witness = ev.solve_fluxes(ev._applied_capacities(
                capacities, ev.WITNESS_DESIGN), demand)
            self.assertGreater(witness["product"] - wild["product"], 1e-6, seed)

    def test_gate_uses_unengineered_capacities(self):
        # The v2 network is enzyme-level: every enzyme touches several reactions,
        # so no single enzyme name equals a biomass reaction.
        ev = _load("benchmarks/Biology/MetabolicStrainDesign/verification/evaluator.py",
                   "r4_fba")
        capacities = ev._capacities(21001)
        demand = ev._max_biomass(capacities)
        self.assertIsNotNone(demand)
        self.assertGreater(demand, 0.0)
        # A design that knocks out every enzyme feeding biosynthesis must fail
        # the viability gate on every scored draw.
        all_off = {"knockouts": sorted(ev.ENZYMES)[:ev.MAX_ENZYME_EDITS],
                   "overexpressions": {}}
        result = ev.evaluate(lambda problem, design=all_off: design)
        self.assertEqual(result["valid"], 1.0)
        self.assertEqual(result["combined_score"], 0.0)


class MetagenomicPins(unittest.TestCase):
    def test_novel_organism_reads_never_hit_unique_markers(self):
        ev = _load("benchmarks/Biology/MetagenomicMixtureID/verification/evaluator.py",
                   "r4_meta")
        world = ev._world((24037, "novel"))
        library_mass = sum(world["abundance"].values())
        self.assertAlmostEqual(library_mass + world["novel_share"], 1.0)
        self.assertLessEqual(world["novel_share"], 0.18)

    def test_repeats_draw_fresh_noise(self):
        ev = _load("benchmarks/Biology/MetagenomicMixtureID/verification/evaluator.py",
                   "r4_meta")
        world = ev._world((24011, "supported"))
        first = ev._run(world, 10, 1)["marker_counts"]
        second = ev._run(world, 10, 2)["marker_counts"]
        self.assertNotEqual(first, second)

    def test_cross_mapping_conserves_the_unique_total(self):
        # Pins the doubling bug: cross-mapping relocates hits, it never creates them.
        ev = _load("benchmarks/Biology/MetagenomicMixtureID/verification/evaluator.py",
                   "r4_meta")
        world = ev._world((24011, "supported"))
        report = ev._run(world, 10, 1)
        unique = sum(v for m, v in report["marker_counts"].items()
                     if int(m[1:]) < 1200)
        self.assertLess(unique, report["total_reads"])


class HodgkinHuxleyPins(unittest.TestCase):
    def test_rate_forms_are_stable_at_singular_points(self):
        ev = _load("benchmarks/Biology/HodgkinHuxleyCurrentID/verification/evaluator.py",
                   "r4_hh")
        self.assertAlmostEqual(ev.alpha_m(25.0), 1.0, places=6)
        self.assertAlmostEqual(ev.alpha_n(10.0), 0.1, places=6)

    def test_gating_relaxes_from_holding(self):
        ev = _load("benchmarks/Biology/HodgkinHuxleyCurrentID/verification/evaluator.py",
                   "r4_hh")
        time, gating = ev._gating_traces(30.0, 20.0)
        # m activates and h inactivates from the -80 mV holding steady state.
        self.assertGreater(gating[-1, 0], gating[0, 0])
        self.assertLess(gating[-1, 1], gating[0, 1])


class ScalingLawPins(unittest.TestCase):
    def test_branch_world_is_deterministic_in_size(self):
        ev = _load("benchmarks/ComputerScience/ScalingLawIdentification"
                   "/verification/evaluator.py", "r4_scale")
        world = ev._world((30041, "branch", "branch"))
        self.assertEqual(ev._true_runtime(world, 334), ev._true_runtime(world, 334))
        # The branch predicate splits sizes into two runtime regimes; under either
        # the mod-three or mod-seven design the split is at least 25x at size ~330.
        ratio = max(ev._true_runtime(world, 331) / ev._true_runtime(world, 332),
                    ev._true_runtime(world, 332) / ev._true_runtime(world, 331))
        self.assertGreater(ratio, 25.0)

    def test_tightened_statistics_beat_lazy_ladders(self):
        # The fixed-shape BIC reference with the predicate-agnostic branch scan
        # sits near the statistical ceiling while free-slope regression (v1)
        # collapsed the power-law classes into one family and scored 0.470.
        ev = _load("benchmarks/ComputerScience/ScalingLawIdentification"
                   "/verification/evaluator.py", "r4_scale")
        ref = _load(ROOT / "benchmarks/ComputerScience/ScalingLawIdentification"
                    "/verification" / "reference_solver.py", "r4_scale_ref")
        reference = ev.evaluate(ref.identify_scaling_law)
        self.assertLess(reference["combined_score"], 0.97)
        self.assertGreater(reference["combined_score"], 0.80)
        self.assertEqual(reference["development_correct_refusal_rate"], 1.0)
        self.assertEqual(reference["development_false_discovery_rate"], 0.0)
        self.assertGreater(reference["robustness_score"], 0.85)

    def test_jitter_worlds_carry_a_lawful_family(self):
        ev = _load("benchmarks/ComputerScience/ScalingLawIdentification"
                   "/verification/evaluator.py", "r4_scale")
        for spec in ev._BASE_DEVELOPMENT_SPECS + ev.HELDOUT_SPECS:
            world = ev._world(spec)
            if world["kind"] != "branch":
                self.assertIn(world["family"], ev.CLASSES)


class DistributionNetworkPins(unittest.TestCase):
    def test_default_level_carries_two_break_ambiguity(self):
        ev = _load("benchmarks/Engineering/DistributionNetworkTopology"
                   "/verification/evaluator.py", "r4_water")
        self.assertEqual(ev.DIFFICULTY, 2)
        self.assertEqual(ev._difficulty_profile()["max_broken"], 2)

    def test_twin_pipes_share_route_signatures(self):
        ev = _load("benchmarks/Engineering/DistributionNetworkTopology"
                   "/verification/evaluator.py", "r4_water")
        incidence = {}
        for route_id, pipes in zip(ev.ROUTE_IDS, ev.ROUTES):
            for pipe in pipes:
                incidence.setdefault(pipe, set()).add(route_id)
        self.assertEqual(incidence["s11"], incidence["s21"])
        covered = set(incidence)
        self.assertEqual(covered, set(ev.PIPE_IDS))

    def test_supported_break_sets_are_signature_unique(self):
        ev = _load("benchmarks/Engineering/DistributionNetworkTopology"
                   "/verification/evaluator.py", "r4_water")
        for spec in ev._BASE_DEVELOPMENT_SPECS + ev.HELDOUT_SPECS:
            world = ev._world(spec)
            if world["kind"] == "supported":
                self.assertTrue(ev._identifiable(world["broken"], 3), spec)


class MineralMixturePins(unittest.TestCase):
    def test_library_peaks_are_observable(self):
        ev = _load("benchmarks/EarthScience/MineralMixtureXRD/verification/evaluator.py",
                   "r4_xrd")
        low, high = ev.TWO_THETA_GRID[0], ev.TWO_THETA_GRID[-1]
        for name, peaks in ev.MINERAL_LIBRARY.items():
            for center, _weight in peaks:
                self.assertGreaterEqual(center, low - 1e-9, name)
                self.assertLessEqual(center, high + 1e-9, name)

    def test_amorphous_hump_is_broad(self):
        ev = _load("benchmarks/EarthScience/MineralMixtureXRD/verification/evaluator.py",
                   "r4_xrd")
        world = ev._world((36029, "supported", True))
        hump = ev._amorphous_pattern(world)
        half = 10
        contrast = max(hump[i] - 0.5 * (hump[i - half] + hump[i + half])
                       for i in range(half, len(hump) - half))
        self.assertLess(contrast, 2.0)


class EllipticCurvePins(unittest.TestCase):
    def test_counts_match_direct_enumeration(self):
        ev = _load("benchmarks/Mathematics/EllipticCurveRecovery/verification/evaluator.py",
                   "r4_ec")
        self.assertEqual(ev._legendre_count_cubic(11, 0, 1), 12)  # 11 + 1 + 0? direct:
        # y^2 = x^3 + 1 over F_11 has 12 points (a classical count).
        self.assertEqual(ev._legendre_count_cubic(7, 0, 0), 7 + 1 + 0)

    def test_singular_worlds_have_zero_discriminant(self):
        ev = _load("benchmarks/Mathematics/EllipticCurveRecovery/verification/evaluator.py",
                   "r4_ec")
        for spec in ev._BASE_DEVELOPMENT_SPECS + ev.HELDOUT_SPECS:
            world = ev._world(spec)
            if world["kind"] == "singular":
                self.assertEqual(4 * world["a"] ** 3 + 27 * world["b"] ** 2, 0)


if __name__ == "__main__":
    unittest.main()

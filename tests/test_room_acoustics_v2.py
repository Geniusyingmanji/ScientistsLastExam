from __future__ import annotations

import importlib.util
import json
import math
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

import numpy as np

from frontier_science.evaluate import evaluate_candidate
from frontier_science.metric_visibility import search_visible_metrics
from frontier_science.registry import find_task


ROOT = Path(__file__).resolve().parent.parent


def _oracle():
    path = (
        ROOT / "benchmarks/Engineering/RoomImpulseResponse/verification/evaluator.py"
    )
    spec = importlib.util.spec_from_file_location("room_acoustics_v2_test", path)
    if spec is None or spec.loader is None:
        raise ImportError("cannot load room-acoustics evaluator")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _independent_image_paths(room, source, receiver, maximum_order):
    """Independent finite image lattice and interval-crossing wall counter."""
    axes = []
    for coordinate in range(3):
        rows = []
        length = float(room[coordinate])
        for cell in range(-int(maximum_order), int(maximum_order) + 1):
            for sign in (1.0, -1.0):
                image = 2.0 * cell * length + sign * float(source[coordinate])
                low = min(float(receiver[coordinate]), image)
                high = max(float(receiver[coordinate]), image)
                crossed = tuple(
                    index for index in range(
                        math.floor(low / length) + 1,
                        math.ceil(high / length),
                    )
                )
                low_hits = sum(index % 2 == 0 for index in crossed)
                high_hits = sum(index % 2 != 0 for index in crossed)
                if low_hits + high_hits <= int(maximum_order):
                    rows.append((image, low_hits, high_hits))
        axes.append(rows)
    records = []
    for xrow in axes[0]:
        for yrow in axes[1]:
            for zrow in axes[2]:
                counts = (xrow[1], xrow[2], yrow[1], yrow[2], zrow[1], zrow[2])
                if sum(counts) <= int(maximum_order):
                    distance = float(np.linalg.norm(
                        np.asarray((xrow[0], yrow[0], zrow[0]))
                        - np.asarray(receiver, dtype=float)
                    ))
                    records.append((distance, counts, sum(counts)))
    records.sort(key=lambda row: (row[2], row[0], row[1]))
    return records


class RoomAcousticsV2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.oracle = _oracle()

    def test_reference_witnesses_are_valid_nontrivial_and_sealed(self):
        oracle = self.oracle
        baseline = oracle.evaluate(lambda problem: oracle._weak_baseline_design(problem))
        nominal = oracle.evaluate(lambda problem: oracle.reference_policy(problem))
        robust = oracle.evaluate(lambda problem: oracle.reference_policy(problem, True))

        self.assertTrue(oracle.ROOM_ACOUSTICS_V2)
        self.assertEqual(len(oracle.DEVELOPMENT_INSTANCES), 4)
        self.assertEqual(len(oracle.HELDOUT_INSTANCES), 2)
        self.assertEqual(baseline["valid"], 1.0)
        self.assertEqual(baseline["combined_score"], 0.0)
        self.assertEqual(baseline["robustness_score"], 0.0)
        self.assertEqual(baseline["heldout_policy_score"], 0.0)
        self.assertEqual(baseline["heldout_robustness_score"], 0.0)
        self.assertGreater(baseline["development_nominal_utility"], 0.50)
        self.assertLess(baseline["development_nominal_utility"], 0.70)

        self.assertEqual(nominal["valid"], 1.0)
        self.assertAlmostEqual(nominal["combined_score"], 1.0)
        self.assertAlmostEqual(nominal["heldout_policy_score"], 1.0)
        self.assertGreater(nominal["robustness_score"], 0.70)
        self.assertGreater(nominal["heldout_robustness_score"], 0.50)
        self.assertEqual(robust["valid"], 1.0)
        self.assertAlmostEqual(robust["robustness_score"], 1.0)
        self.assertAlmostEqual(robust["heldout_robustness_score"], 1.0)
        self.assertGreater(robust["combined_score"], 0.70)
        self.assertGreater(robust["heldout_policy_score"], 0.45)
        self.assertTrue(all(row["valid"] for row in nominal["per_instance"]))
        self.assertTrue(all(row["valid"] for row in robust["per_instance"]))
        for instance in oracle.INSTANCES:
            self.assertGreater(
                instance["nominal_reference"]["utility"],
                instance["baseline_nominal"]["utility"] + 1.0e-4,
            )
            self.assertGreater(
                instance["robust_reference_utility"],
                instance["baseline_robust_utility"] + 1.0e-4,
            )

        visible = search_visible_metrics(nominal)
        for key in (
            "robustness_score", "heldout_policy_score",
            "development_nominal_utility", "development_proxy_utility",
            "development_proxy_exact_gap", "per_instance",
        ):
            self.assertNotIn(key, visible)

    def test_image_lattice_matches_independent_path_enumeration(self):
        oracle = self.oracle
        instance = oracle.INSTANCES[0]
        problem = instance["problem"]
        room = problem["room_dimensions_m"]
        source = instance["nominal_reference_design"][:3]
        receiver = problem["receiver_positions_m"][3]
        for order in (0, 1, 2, 4):
            distance, counts, orders = oracle._image_paths(
                room, source, receiver, order
            )
            actual = sorted(
                (round(float(d), 12), tuple(map(int, c)), int(o))
                for d, c, o in zip(distance, counts, orders)
            )
            expected = sorted(
                (round(row[0], 12), row[1], row[2])
                for row in _independent_image_paths(
                    room, source, receiver, order
                )
            )
            self.assertEqual(actual, expected)
            self.assertEqual(int(np.sum(orders == 0)), 1)
            self.assertTrue(np.all(distance > 0.0))

    def test_first_order_paths_match_six_analytic_reflections(self):
        oracle = self.oracle
        instance = oracle.INSTANCES[1]
        room = np.asarray(instance["problem"]["room_dimensions_m"])
        source = np.asarray(instance["nominal_reference_design"][:3])
        receiver = np.asarray(instance["problem"]["receiver_positions_m"][0])
        distance, counts, orders = oracle._image_paths(room, source, receiver, 1)
        self.assertEqual(len(distance), 7)
        self.assertEqual(int(np.sum(orders == 0)), 1)
        self.assertEqual(int(np.sum(orders == 1)), 6)
        self.assertEqual(
            {tuple(row) for row in counts[orders == 1]},
            {tuple(np.eye(6, dtype=int)[index]) for index in range(6)},
        )

    def test_absorption_and_eyring_decay_are_physical_and_monotone(self):
        oracle = self.oracle
        for instance in oracle.INSTANCES:
            problem = instance["problem"]
            room = problem["room_dimensions_m"]
            zero = np.zeros(6)
            maximum = (
                np.asarray(problem["surface_areas_m2"])
                * np.asarray(problem["maximum_treatment_fraction_by_surface"])
            )
            maximum *= min(
                1.0,
                float(problem["maximum_treatment_area_m2"])
                / max(float(np.sum(maximum)), 1.0e-12),
            )
            untreated, _ = oracle._effective_absorption(problem, zero, room)
            treated, _ = oracle._effective_absorption(problem, maximum, room)
            self.assertTrue(np.all(treated >= untreated))
            untreated_rt = oracle._reverberation_time(room, untreated)
            treated_rt = oracle._reverberation_time(room, treated)
            self.assertTrue(np.all(np.isfinite(untreated_rt)))
            self.assertTrue(np.all(treated_rt > 0.0))
            self.assertTrue(np.all(treated_rt <= untreated_rt))

    def test_all_paths_have_nonnegative_finite_energy(self):
        oracle = self.oracle
        for instance in oracle.INSTANCES:
            problem = instance["problem"]
            design = instance["nominal_reference_design"]
            room, source, receivers, sound_speed = oracle._shifted_geometry(
                problem, design, None
            )
            absorption, _ = oracle._effective_absorption(
                problem, design[3:], room
            )
            row = oracle._receiver_band_energies(
                room, source, receivers[0], sound_speed, absorption, 10
            )
            for key in ("early_energy", "late_energy", "total_energy"):
                values = np.asarray(row[key])
                self.assertTrue(np.all(np.isfinite(values)))
                self.assertTrue(np.all(values >= 0.0))
            self.assertGreaterEqual(row["path_count"], 1500)

    def test_malformed_nonfinite_and_out_of_bound_designs_fail_closed(self):
        oracle = self.oracle

        def valid(problem):
            return oracle._weak_baseline_design(problem)

        def over_budget(problem):
            value = valid(problem)
            value[3:] = float(problem["maximum_treatment_area_m2"])
            return value

        def bad_source(problem):
            value = valid(problem)
            value[0] = float(problem["source_position_bounds_m"][0][0]) - 0.1
            return value

        factories = (
            lambda problem: valid(problem)[:-1],
            lambda problem: np.full(9, np.nan),
            lambda problem: np.full(9, np.inf),
            lambda problem: valid(problem).astype(complex) + 1j * 0.001,
            lambda problem: valid(problem).astype(str),
            lambda problem: -np.ones(9),
            over_budget,
            bad_source,
        )
        for factory in factories:
            metrics = oracle.evaluate(factory)
            self.assertEqual(metrics["valid"], 0.0)
            self.assertEqual(metrics["combined_score"], 0.0)
            self.assertEqual(metrics["feasibility_rate"], 0.0)
            self.assertTrue(all(
                not row["valid"] for row in metrics["per_instance"]
            ))

    def test_public_problem_hides_split_references_and_shifts(self):
        oracle = self.oracle
        forbidden = {
            "name", "split", "shift", "reference", "baseline_design",
            "nominal_reference_family", "robust_reference_family",
        }
        for instance in oracle.INSTANCES:
            problem = instance["problem"]
            self.assertTrue(forbidden.isdisjoint(problem))
            self.assertEqual(tuple(problem["design_fields"]), oracle.DESIGN_FIELDS)

    def test_all_six_rooms_get_fresh_process_and_tmpfs(self):
        spec = find_task("Acoustics/RoomImpulseResponse", include_uncertified=True)
        source = textwrap.dedent("""
            import os
            import numpy as np

            module_counter = 0

            def design_room(problem):
                global module_counter
                module_counter += 1
                tmp_seen = os.path.exists('/tmp/room-acoustics-state')
                with open('/tmp/room-acoustics-state', 'w') as handle:
                    handle.write(str(module_counter))
                imported_counter = getattr(np, '_room_acoustics_counter', 0)
                np._room_acoustics_counter = imported_counter + 1
                bounds = np.asarray(problem['source_position_bounds_m'], dtype=float)
                source = np.mean(bounds, axis=1)
                area = np.asarray(problem['surface_areas_m2'], dtype=float)
                cap = area * np.asarray(
                    problem['maximum_treatment_fraction_by_surface'], dtype=float
                )
                treatment = 0.25 * cap
                limit = float(problem['maximum_treatment_area_m2'])
                if treatment.sum() > limit:
                    treatment *= limit / treatment.sum()
                if module_counter != 1 or tmp_seen or imported_counter != 0:
                    return np.full(9, np.nan)
                return np.concatenate((source, treatment))
        """)
        with tempfile.TemporaryDirectory() as tmp:
            candidate = Path(tmp) / "candidate.py"
            candidate.write_text(source, encoding="utf-8")
            metrics = evaluate_candidate(spec, candidate, timeout_s=90)
        self.assertEqual(metrics["valid"], 1.0)
        self.assertEqual(metrics["candidate_instance_call_count"], 6)
        self.assertEqual(metrics["candidate_instance_valid_rate"], 1.0)
        self.assertTrue(all(row["valid"] for row in metrics["per_instance"]))

    def test_legacy_driver_uses_v2_entrypoint(self):
        task = ROOT / "benchmarks/Engineering/RoomImpulseResponse"
        with tempfile.TemporaryDirectory() as tmp:
            metrics_path = Path(tmp) / "metrics.json"
            process = subprocess.run(
                [
                    sys.executable,
                    str(task / "frontier_eval/run_eval.py"),
                    "--candidate", str(task / "solution.py"),
                    "--metrics-out", str(metrics_path),
                ],
                cwd=str(ROOT),
                check=False,
                capture_output=True,
                text=True,
                timeout=60,
            )
            metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        self.assertEqual(process.returncode, 0)
        self.assertEqual(metrics["valid"], 1.0)
        self.assertEqual(metrics["combined_score"], 0.0)
        self.assertEqual(metrics["raw_score"], 0.0)
        self.assertNotIn("error_message", metrics)


if __name__ == "__main__":
    unittest.main()

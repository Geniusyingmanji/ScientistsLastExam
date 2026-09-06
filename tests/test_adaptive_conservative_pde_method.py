from __future__ import annotations

import hashlib
import importlib.util
import itertools
import json
import math
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

from sle.evaluate import evaluate_candidate
from sle.frontier import load_frozen_wave
from sle.registry import find_task

ROOT = Path(__file__).resolve().parents[1]
TASK_DIR = ROOT / "benchmarks" / "ComputerScience" / "AdaptiveConservativePDEMethod"
# Cross-platform snapshot regression tolerances, aligned with the independently implemented
# finite-volume replay below. These are not a theorem about every hardware or libm implementation.
RAW_REPLAY_ATOL = 2.0e-6
# RAW_REPLAY_ATOL / the roughly 0.54 anchor scale, rounded upward.
NORMALIZED_REPLAY_ATOL = 4.0e-6


def _load(name: str, path: Path):
    module_spec = importlib.util.spec_from_file_location(name, path)
    assert module_spec is not None and module_spec.loader is not None
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    return module


class AdaptiveConservativePDEMethodTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.evaluator = _load(
            "adaptive_conservative_pde_evaluator",
            TASK_DIR / "verification" / "evaluator.py",
        )
        cls.baseline = _load("adaptive_conservative_pde_baseline", TASK_DIR / "solution.py")
        cls.reference = _load(
            "adaptive_conservative_pde_reference",
            TASK_DIR / "verification" / "reference_method.py",
        )

    def test_metadata_records_uncalibrated_on_ramp_status(self) -> None:
        metadata = yaml.safe_load(
            (TASK_DIR / "frontier_eval" / "metadata.yaml").read_text(encoding="utf-8")
        )
        card = yaml.safe_load((TASK_DIR / "TASK_CARD.yaml").read_text(encoding="utf-8"))

        self.assertEqual(metadata["difficulty"], "on_ramp")
        self.assertEqual(
            card["lineage"]["calibration_evidence_status"],
            "missing",
        )
        self.assertEqual(card["lineage"]["calibrator_model_ids"], [])

    def test_baseline_and_reference_are_exact_score_anchors(self) -> None:
        panel = self.evaluator._load_panel()
        self.assertEqual(self.evaluator._weak_method(), panel["baseline_method"])
        self.assertEqual(self.evaluator._reference_method(), panel["reference_method"])
        baseline = self.evaluator.evaluate(self.baseline.design_finite_volume_method)
        reference = self.evaluator.evaluate(self.reference.design_finite_volume_method)

        self.assertEqual(baseline["valid"], 1.0)
        self.assertAlmostEqual(baseline["combined_score"], 0.0, places=12)
        self.assertEqual(reference["valid"], 1.0)
        self.assertAlmostEqual(reference["combined_score"], 1.0, places=12)
        self.assertAlmostEqual(
            baseline["development_raw_utility"],
            0.43067750623620715,
            delta=RAW_REPLAY_ATOL,
        )
        self.assertAlmostEqual(
            reference["development_raw_utility"],
            0.9705475629120707,
            delta=RAW_REPLAY_ATOL,
        )
        self.assertAlmostEqual(
            baseline["heldout_raw_utility"],
            0.4476810274372647,
            delta=RAW_REPLAY_ATOL,
        )
        self.assertAlmostEqual(
            reference["heldout_raw_utility"],
            0.9720236479726634,
            delta=RAW_REPLAY_ATOL,
        )
        self.assertGreater(
            reference["development_accuracy_score"],
            baseline["development_accuracy_score"],
        )
        self.assertGreater(
            reference["development_raw_utility"], baseline["development_raw_utility"]
        )
        self.assertLess(reference["development_max_conservation_error"], 1.0e-10)
        self.assertEqual(len(reference["frontier_records"]), 1)

    def test_a_nontrivial_legal_method_can_score_above_reference(self) -> None:
        stronger = {
            "reconstruction": "weno3",
            "limiter": "superbee",
            "riemann_solver": "godunov",
            "time_integrator": "ssprk3",
            "cells": 192,
            "cfl": 0.85,
            "sensor_threshold": 0.10,
            "shock_blend": 1.0,
            "flux_dissipation": 1.0,
        }

        metrics = self.evaluator.evaluate(lambda _problem: dict(stronger))

        self.assertEqual(metrics["valid"], 1.0)
        self.assertAlmostEqual(
            metrics["combined_score"],
            1.0020711846674135,
            delta=NORMALIZED_REPLAY_ATOL,
        )
        self.assertAlmostEqual(
            metrics["development_raw_utility"],
            0.9716657334958534,
            delta=RAW_REPLAY_ATOL,
        )
        self.assertAlmostEqual(
            metrics["heldout_raw_utility"],
            0.9727754615669326,
            delta=RAW_REPLAY_ATOL,
        )

    def test_reference_capabilities_survive_ablation(self) -> None:
        problem = self.evaluator._public_problem()
        reference_method = self.reference.design_finite_volume_method(problem)
        reference = self.evaluator.evaluate(lambda _problem: dict(reference_method))
        ablations = {
            "no_sensor_blend": {**reference_method, "shock_blend": 0.0},
            "late_sensor": {**reference_method, "sensor_threshold": 0.95},
            "no_weno3": {**reference_method, "reconstruction": "muscl"},
            "coarser_grid": {**reference_method, "cells": 128},
            "lower_order_time": {**reference_method, "time_integrator": "ssprk2"},
            "joint_solver_dissipation": {
                **reference_method,
                "riemann_solver": "rusanov",
                "flux_dissipation": 1.5,
            },
        }
        expected_scores = {
            "no_sensor_blend": 0.978249778223279,
            "late_sensor": 0.9941973588725147,
            "no_weno3": 0.9736842597282943,
            "coarser_grid": 0.9904203552318088,
            "lower_order_time": 0.9852571499756683,
            "joint_solver_dissipation": 0.9960049630406164,
        }

        for name, method in ablations.items():
            with self.subTest(name=name):
                metrics = self.evaluator.evaluate(lambda _problem, value=method: dict(value))
                self.assertEqual(metrics["valid"], 1.0)
                self.assertLess(
                    metrics["development_raw_utility"],
                    reference["development_raw_utility"],
                )
                self.assertAlmostEqual(
                    metrics["combined_score"],
                    expected_scores[name],
                    delta=NORMALIZED_REPLAY_ATOL,
                )

    def test_432_nonadaptive_shortcut_grid_stays_below_reference(self) -> None:
        worlds = [
            world
            for world in self.evaluator._load_panel()["worlds"]
            if world["split"] == "development"
        ]
        methods = itertools.chain(
            itertools.product(
                ("muscl",),
                ("minmod", "mc", "van_leer", "superbee", "central"),
                ("euler", "ssprk2", "ssprk3"),
                (96, 128, 192),
                (0.55, 0.70, 0.85, 0.95),
                ("godunov", "rusanov"),
            ),
            itertools.product(
                ("weno3",),
                ("minmod",),
                ("euler", "ssprk2", "ssprk3"),
                (96, 128, 192),
                (0.55, 0.70, 0.85, 0.95),
                ("godunov", "rusanov"),
            ),
        )
        best = (-math.inf, None)
        count = 0
        for reconstruction, limiter, integrator, cells, cfl, solver in methods:
            method = {
                "reconstruction": reconstruction,
                "limiter": limiter,
                "riemann_solver": solver,
                "time_integrator": integrator,
                "cells": cells,
                "cfl": cfl,
                "sensor_threshold": 0.5,
                "shock_blend": 0.0,
                "flux_dissipation": 1.1 if solver == "rusanov" else 1.0,
            }
            rows = [self.evaluator._run_world(method, world) for world in worlds]
            raw = self.evaluator._aggregate(rows)["raw_utility"]
            best = max(best, (raw, method), key=lambda item: item[0])
            count += 1

        self.assertEqual(count, 432)
        self.assertAlmostEqual(
            best[0], 0.9643685859747075, delta=RAW_REPLAY_ATOL
        )
        self.assertEqual(
            best[1],
            {
                "reconstruction": "muscl",
                "limiter": "mc",
                "riemann_solver": "godunov",
                "time_integrator": "ssprk3",
                "cells": 192,
                "cfl": 0.85,
                "sensor_threshold": 0.5,
                "shock_blend": 0.0,
                "flux_dissipation": 1.0,
            },
        )
        self.assertLess(best[0], self.evaluator._anchors()[1])

    def test_48_point_local_grid_matches_the_ledger_incumbent(self) -> None:
        worlds = [
            world
            for world in self.evaluator._load_panel()["worlds"]
            if world["split"] == "development"
        ]
        best = (-math.inf, None)
        for cfl, threshold in itertools.product(
            (0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90),
            (0.05, 0.10, 0.15, 0.20, 0.25, 0.30),
        ):
            method = {
                **self.evaluator._reference_method(),
                "cfl": cfl,
                "sensor_threshold": threshold,
            }
            rows = [self.evaluator._run_world(method, world) for world in worlds]
            raw = self.evaluator._aggregate(rows)["raw_utility"]
            best = max(best, (raw, method), key=lambda item: item[0])

        self.assertAlmostEqual(
            best[0], 0.9716657334958534, delta=RAW_REPLAY_ATOL
        )
        self.assertEqual(best[1]["cfl"], 0.85)
        self.assertEqual(best[1]["sensor_threshold"], 0.10)
        metrics = self.evaluator.evaluate(lambda _problem: dict(best[1]))
        spec = find_task(
            "ScientificComputing/AdaptiveConservativePDEMethod",
            include_uncertified=True,
        )
        wave = load_frozen_wave(spec)
        assert wave is not None
        cell = wave.cells["conservative-scalar-law-method"]
        self.assertEqual(metrics["frontier_records"][0]["value"], best[0])
        self.assertAlmostEqual(
            cell["reference_value"], best[0], delta=RAW_REPLAY_ATOL
        )

    def test_inactive_coordinates_share_one_canonical_identity(self) -> None:
        reference = self.evaluator._reference_method()
        weno_without_fallback = {**reference, "shock_blend": 0.0}
        changed_weno = {
            **weno_without_fallback,
            "limiter": "central",
            "sensor_threshold": 0.95,
        }
        minmod_muscl = {
            **reference,
            "reconstruction": "muscl",
            "limiter": "minmod",
            "sensor_threshold": 0.02,
            "shock_blend": 0.2,
        }
        changed_minmod = {
            **minmod_muscl,
            "sensor_threshold": 0.95,
            "shock_blend": 1.0,
        }
        self.assertEqual(
            self.evaluator._canonical_method_id(weno_without_fallback),
            self.evaluator._canonical_method_id(changed_weno),
        )
        self.assertEqual(
            self.evaluator._canonical_method_id(minmod_muscl),
            self.evaluator._canonical_method_id(changed_minmod),
        )

    def test_signed_zero_has_one_payload_identity_and_frontier_record(self) -> None:
        positive_zero = {
            **self.evaluator._reference_method(),
            "shock_blend": 0.0,
        }
        negative_zero = {
            **positive_zero,
            "shock_blend": -0.0,
        }

        self.assertEqual(
            self.evaluator._canonical_payload(positive_zero),
            self.evaluator._canonical_payload(negative_zero),
        )
        self.assertEqual(
            self.evaluator._canonical_method_id(positive_zero),
            self.evaluator._canonical_method_id(negative_zero),
        )
        self.assertEqual(
            self.evaluator.evaluate(lambda _problem: dict(positive_zero))["frontier_records"],
            self.evaluator.evaluate(lambda _problem: dict(negative_zero))["frontier_records"],
        )

    def test_periodic_and_open_cases_obey_discrete_flux_balance(self) -> None:
        problem = self.evaluator._public_problem()
        method = self.evaluator._normalize_method(
            self.reference.design_finite_volume_method(problem), problem
        )

        for world in self.evaluator._load_panel()["worlds"]:
            result = self.evaluator._run_world(method, world)
            self.assertLess(result["conservation_error"], 1.0e-10, world["id"])
            self.assertTrue(math.isfinite(result["l1_error"]), world["id"])

    def test_ninety_dsl_grid_points_conserve_one_step(self) -> None:
        combinations = itertools.product(
            ("constant", "muscl", "weno3"),
            ("minmod", "mc", "van_leer", "superbee", "central"),
            ("rusanov", "godunov"),
            ("euler", "ssprk2", "ssprk3"),
        )
        count = 0
        canonical_methods = set()
        for reconstruction, limiter, solver, integrator in combinations:
            method = self.evaluator._normalize_method(
                {
                    "reconstruction": reconstruction,
                    "limiter": limiter,
                    "riemann_solver": solver,
                    "time_integrator": integrator,
                    "cells": 32,
                    "cfl": 0.4,
                    "sensor_threshold": 0.3,
                    "shock_blend": 0.7,
                    "flux_dissipation": 1.1,
                }
            )
            canonical_methods.add(self.evaluator._canonical_payload(method))
            for world in self.evaluator._load_panel()["worlds"]:
                state = self.evaluator._cell_averages(world, method["cells"], 0.0)
                speed = self.evaluator._speed_bound(world)
                dt = method["cfl"] / (method["cells"] * speed)
                updated, boundary_flux, _stages = self.evaluator._advance(
                    state, dt, method, world
                )
                balance = float(updated.mean() - state.mean())
                if world["boundary"] == "fixed":
                    balance += boundary_flux
                self.assertLess(
                    abs(balance),
                    1.0e-13,
                    (reconstruction, limiter, solver, integrator, world["id"]),
                )
            count += 1
        self.assertEqual(count, 90)
        self.assertEqual(len(canonical_methods), 66)

    def test_analytic_cell_average_targets_have_exact_domain_mass(self) -> None:
        def domain_mass(world, time):
            initial = world["initial"]
            kind = initial["kind"]
            if world["equation"] == "advection":
                if kind in {"sine", "multisine"}:
                    return float(initial["offset"])
                if kind == "top_hat":
                    width = float(initial["right"] - initial["left"])
                    return float(initial["low"] + (initial["high"] - initial["low"]) * width)
                if kind == "gaussian":
                    width = float(initial["width"])
                    pulse_mass = (
                        2.0
                        * width
                        * math.sqrt(math.pi / 2.0)
                        * math.erf(0.5 / (math.sqrt(2.0) * width))
                    )
                    return float(
                        initial["low"]
                        + (initial["high"] - initial["low"]) * pulse_mass
                    )
                self.fail("unsupported periodic initial condition")

            left = float(initial["left"])
            right = float(initial["right"])
            location = float(initial["location"])
            if time == 0.0:
                front = min(max(location, 0.0), 1.0)
                return left * front + right * (1.0 - front)
            if left > right:
                front = min(max(location + 0.5 * (left + right) * time, 0.0), 1.0)
                return left * front + right * (1.0 - front)

            fan_left = location + left * time
            fan_right = location + right * time
            lower_length = min(max(fan_left, 0.0), 1.0)
            upper_length = 1.0 - min(max(fan_right, 0.0), 1.0)
            middle_left = min(max(fan_left, 0.0), 1.0)
            middle_right = min(max(fan_right, 0.0), 1.0)
            fan_mass = (
                0.5 * (middle_right**2 - middle_left**2)
                - location * (middle_right - middle_left)
            ) / time
            return left * lower_length + fan_mass + right * upper_length

        for world in self.evaluator._load_panel()["worlds"]:
            for time in (0.0, float(world["final_time"])):
                with self.subTest(world=world["id"], time=time):
                    averages = self.evaluator._cell_averages(world, 32, time)
                    self.assertAlmostEqual(
                        float(averages.mean()), domain_mass(world, time), places=14
                    )

    def test_analytic_targets_match_independent_adaptive_quadrature(self) -> None:
        np = __import__("numpy")
        quad = __import__("scipy.integrate", fromlist=["quad"]).quad

        def breakpoints(world, time):
            initial = world["initial"]
            if world["equation"] == "advection":
                shift = float(world["speed"]) * time
                if initial["kind"] == "top_hat":
                    return (
                        (float(initial["left"]) + shift) % 1.0,
                        (float(initial["right"]) + shift) % 1.0,
                    )
                if initial["kind"] == "gaussian":
                    return (((float(initial["center"]) + shift) % 1.0 + 0.5) % 1.0,)
                return ()
            left = float(initial["left"])
            right = float(initial["right"])
            location = float(initial["location"])
            if time == 0.0 or left > right:
                return (location + (0.5 * (left + right) * time if time else 0.0),)
            return (location + left * time, location + right * time)

        for world in self.evaluator._load_panel()["worlds"]:
            for cells in (7, 31):
                dx = 1.0 / cells
                for time in (0.0, float(world["final_time"]) / 3.0, float(world["final_time"])):
                    targets = self.evaluator._cell_averages(world, cells, time)
                    for index, target in enumerate(targets):
                        lower = index * dx
                        upper = (index + 1) * dx
                        points = [
                            point for point in breakpoints(world, time)
                            if lower < point < upper
                        ]
                        integral, _error = quad(
                            lambda x, current_world=world, current_time=time: float(
                                self.evaluator._exact_value(
                                    np.asarray([x]), current_world, current_time
                                )[0]
                            ),
                            lower,
                            upper,
                            points=points,
                            epsabs=1.0e-13,
                            epsrel=1.0e-13,
                            limit=200,
                        )
                        self.assertAlmostEqual(
                            float(target), integral / dx, places=11
                        )

    def test_discontinuous_target_cell_averages_match_closed_forms(self) -> None:
        worlds = {world["id"]: world for world in self.evaluator._load_panel()["worlds"]}
        np = __import__("numpy")
        np.testing.assert_allclose(
            self.evaluator._cell_averages(worlds["dev-advection-top-hat"], 4, 0.0),
            [0.102, 0.9, 0.186, -0.15],
            rtol=0.0,
            atol=1.0e-14,
        )
        np.testing.assert_allclose(
            self.evaluator._cell_averages(worlds["dev-burgers-shock"], 4, 0.24),
            [1.0, 0.76, 0.0, 0.0],
            rtol=0.0,
            atol=1.0e-14,
        )
        np.testing.assert_allclose(
            self.evaluator._cell_averages(
                worlds["heldout-burgers-rarefaction"], 4, 0.21
            ),
            [-0.35, -0.18026428571428574, 0.716264285714286, 0.85],
            rtol=0.0,
            atol=1.0e-14,
        )

    def test_independent_fv_replay_agrees_on_all_evidence_methods(self) -> None:
        independent_path = TASK_DIR / "verification" / "independent_fv_crosscheck.py"
        source = independent_path.read_text(encoding="utf-8")
        self.assertNotIn("verification.evaluator", source)
        self.assertNotIn("evaluation_panel", source)
        independent = _load("adaptive_conservative_pde_independent", independent_path)

        reference = self.evaluator._reference_method()
        methods = {
            "baseline": self.evaluator._weak_method(),
            "reference": reference,
            "incumbent": {
                **reference,
                "cfl": 0.85,
                "sensor_threshold": 0.10,
            },
            "no_sensor_blend": {**reference, "shock_blend": 0.0},
            "late_sensor": {**reference, "sensor_threshold": 0.95},
            "no_weno3": {**reference, "reconstruction": "muscl"},
            "coarser_grid": {**reference, "cells": 128},
            "lower_order_time": {**reference, "time_integrator": "ssprk2"},
            "joint_solver_dissipation": {
                **reference,
                "riemann_solver": "rusanov",
                "flux_dissipation": 1.5,
            },
        }
        independent_raw = {}
        for name, method in methods.items():
            with self.subTest(method=name):
                primary = self.evaluator.evaluate(lambda _problem, value=method: dict(value))
                replay = independent.evaluate_method(dict(method))
                self.assertEqual(
                    [row["id"] for row in replay["per_world"]],
                    [row["id"] for row in primary["per_world"]],
                )
                for primary_row, replay_row in zip(primary["per_world"], replay["per_world"]):
                    self.assertAlmostEqual(
                        replay_row["l1_error"],
                        primary_row["l1_error"],
                        delta=2.0e-9,
                    )
                    self.assertLess(replay_row["conservation_error"], 1.0e-12)
                    self.assertLess(primary_row["conservation_error"], 1.0e-12)
                    self.assertEqual(replay_row["work_units"], primary_row["work_units"])
                    self.assertAlmostEqual(
                        replay_row["raw_utility"],
                        primary_row["raw_utility"],
                        delta=2.0e-6,
                    )
                self.assertAlmostEqual(
                    replay["development_raw_utility"],
                    primary["development_raw_utility"],
                    delta=2.0e-6,
                )
                self.assertAlmostEqual(
                    replay["heldout_raw_utility"],
                    primary["heldout_raw_utility"],
                    delta=2.0e-6,
                )
                independent_raw[name] = replay["development_raw_utility"]

        self.assertLess(independent_raw["baseline"], independent_raw["reference"])
        self.assertLess(independent_raw["reference"], independent_raw["incumbent"])
        for name in (
            "no_sensor_blend",
            "late_sensor",
            "no_weno3",
            "coarser_grid",
            "lower_order_time",
            "joint_solver_dissipation",
        ):
            self.assertLess(independent_raw[name], independent_raw["reference"])

    def test_malformed_invalid_and_overbudget_methods_fail_closed(self) -> None:
        problem = self.evaluator._public_problem()
        valid = self.baseline.design_finite_volume_method(problem)
        cases = [
            lambda _problem: None,
            lambda _problem: "method",
            lambda _problem: [],
            lambda _problem: {},
            lambda _problem: {key: value for key, value in valid.items() if key != "cfl"},
            lambda _problem: {**valid, "unknown": 1},
            lambda _problem: {**valid, "cells": True},
            lambda _problem: {**valid, "cells": 33},
            lambda _problem: {**valid, "cfl": float("nan")},
            lambda _problem: {**valid, "cfl": float("inf")},
            lambda _problem: {**valid, "shock_blend": -0.1},
            lambda _problem: {**valid, "time_integrator": "rk4"},
            lambda _problem: {**valid, "limiter": "unlimited"},
            lambda _problem: {**valid, "riemann_solver": "hllc"},
            lambda _problem: {
                **valid,
                "reconstruction": "muscl",
                "riemann_solver": "godunov",
                "time_integrator": "ssprk3",
                "cells": 192,
                "cfl": 0.08,
            },
        ]

        for candidate in cases:
            with self.subTest(candidate=candidate):
                metrics = self.evaluator.evaluate(candidate)
                self.assertEqual(metrics["valid"], 0.0)
                self.assertEqual(metrics["combined_score"], 0.0)
                self.assertEqual(metrics["frontier_records"], [])

    def test_reference_is_independently_runnable_through_black_box_runner(self) -> None:
        spec = find_task(
            "ScientificComputing/AdaptiveConservativePDEMethod",
            include_uncertified=True,
        )
        metrics = evaluate_candidate(
            spec,
            TASK_DIR / "verification" / "reference_method.py",
            timeout_s=120,
        )
        self.assertEqual(metrics["valid"], 1.0)
        self.assertAlmostEqual(metrics["combined_score"], 1.0, places=12)

    def test_ten_malformed_shapes_fail_closed_through_the_sandbox(self) -> None:
        spec = find_task(
            "ScientificComputing/AdaptiveConservativePDEMethod",
            include_uncertified=True,
        )
        expressions = (
            "None",
            "'method'",
            "[]",
            "{}",
            "{**VALID, 'unknown': 1}",
            "{**VALID, 'cells': True}",
            "{**VALID, 'cells': 33}",
            "{key: value for key, value in VALID.items() if key != 'cfl'}",
            "{**VALID, 'shock_blend': -0.1}",
            "{**VALID, 'time_integrator': 'rk4'}",
        )
        valid = repr(self.baseline.design_finite_volume_method(self.evaluator._public_problem()))
        for index, expression in enumerate(expressions):
            with self.subTest(index=index), tempfile.TemporaryDirectory() as temporary:
                candidate = Path(temporary) / "candidate.py"
                candidate.write_text(
                    f"VALID = {valid}\n\n"
                    "def design_finite_volume_method(problem):\n"
                    f"    return {expression}\n",
                    encoding="utf-8",
                )
                metrics = evaluate_candidate(spec, candidate, timeout_s=30)
                self.assertNotIn("infrastructure_failure", metrics)
                self.assertEqual(metrics["valid"], 0.0)
                self.assertEqual(metrics["combined_score"], 0.0)

    def test_evaluation_is_deterministic(self) -> None:
        first = self.evaluator.evaluate(self.reference.design_finite_volume_method)
        second = self.evaluator.evaluate(self.reference.design_finite_volume_method)
        self.assertEqual(first, second)

    def test_candidate_proxy_sessions_are_reset_between_panel_worlds(self) -> None:
        source = """
import os
import numpy as np

COUNTER = 0

def design_finite_volume_method(problem):
    global COUNTER
    COUNTER += 1
    marker = '/tmp/adaptive-pde-state-marker'
    leaked = COUNTER != 1 or os.path.exists(marker) or hasattr(np, '_adaptive_pde_marker')
    with open(marker, 'w', encoding='utf-8') as handle:
        handle.write('state')
    np._adaptive_pde_marker = True
    method = {
        'reconstruction': 'constant',
        'limiter': 'minmod',
        'riemann_solver': 'rusanov',
        'time_integrator': 'euler',
        'cells': 32,
        'cfl': 0.45,
        'sensor_threshold': 0.5,
        'shock_blend': 1.0,
        'flux_dissipation': 1.15,
    }
    if leaked:
        method['leaked_state'] = True
    return method
"""
        spec = find_task(
            "ScientificComputing/AdaptiveConservativePDEMethod",
            include_uncertified=True,
        )
        with tempfile.NamedTemporaryFile("w", suffix=".py", encoding="utf-8") as handle:
            handle.write(source)
            handle.flush()
            metrics = evaluate_candidate(spec, Path(handle.name), timeout_s=90)

        self.assertEqual(metrics["valid"], 1.0)
        self.assertAlmostEqual(metrics["combined_score"], 0.0, places=12)
        self.assertEqual(metrics["candidate_world_call_count"], 7)

    def test_standalone_runner_does_not_import_candidate_into_oracle_process(self) -> None:
        source = """
import sys

def design_finite_volume_method(problem):
    leaked = 'evaluator' in sys.modules or any(
        'verification/evaluator.py' in str(getattr(module, '__file__', ''))
        for module in tuple(sys.modules.values())
    )
    method = {
        'reconstruction': 'constant',
        'limiter': 'minmod',
        'riemann_solver': 'rusanov',
        'time_integrator': 'euler',
        'cells': 32,
        'cfl': 0.45,
        'sensor_threshold': 0.5,
        'shock_blend': 1.0,
        'flux_dissipation': 1.15,
    }
    if leaked:
        method['same_process_oracle'] = True
    return method
"""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            candidate = root / "candidate.py"
            metrics_path = root / "metrics.json"
            candidate.write_text(source, encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(TASK_DIR / "frontier_eval" / "run_eval.py"),
                    "--candidate",
                    str(candidate),
                    "--metrics-out",
                    str(metrics_path),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )
            metrics = json.loads(metrics_path.read_text(encoding="utf-8"))

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(metrics["valid"], 1.0, metrics)
        self.assertAlmostEqual(metrics["combined_score"], 0.0, places=12)
        self.assertEqual(metrics["candidate_world_call_count"], 7)

    def test_wave_contract_hashes_and_frontier_record_bind_to_method(self) -> None:
        spec = find_task(
            "ScientificComputing/AdaptiveConservativePDEMethod",
            include_uncertified=True,
        )
        wave = load_frozen_wave(spec)
        self.assertIsNotNone(wave)
        assert wave is not None
        self.assertEqual(
            wave.task_family_id, "ScientificComputing/AdaptiveConservativePDEMethod"
        )
        self.assertEqual(wave.wave_id, "scalar-law-panel-v1")

        metrics = self.evaluator.evaluate(self.reference.design_finite_volume_method)
        problem = self.evaluator._public_problem()
        method = self.evaluator._normalize_method(
            self.reference.design_finite_volume_method(problem), problem
        )
        expected_id = self.evaluator._canonical_method_id(method)
        record = metrics["frontier_records"][0]
        self.assertEqual(record["canonical_id"], expected_id)
        self.assertEqual(record["value"], metrics["development_raw_utility"])

        contract = wave.cells["conservative-scalar-law-method"]["semantic_contract"]
        baseline_raw, reference_raw = self.evaluator._anchors()
        cell = wave.cells["conservative-scalar-law-method"]
        self.assertAlmostEqual(
            cell["reference_value"],
            0.9716657334958534,
            places=12,
        )
        self.assertAlmostEqual(
            cell["credit_scale"],
            reference_raw - baseline_raw,
            delta=RAW_REPLAY_ATOL,
        )
        self.assertLess(2.0 * RAW_REPLAY_ATOL, cell["minimum_delta"])
        for path_key, hash_key in (
            ("canonicalizer_path", "canonicalizer_sha256"),
            ("evidence_predicate_path", "evidence_predicate_sha256"),
            ("evaluation_panel_path", "evaluation_panel_sha256"),
            ("oracle_path", "oracle_sha256"),
        ):
            data = (TASK_DIR / contract[path_key]).read_bytes()
            self.assertEqual(hashlib.sha256(data).hexdigest(), contract[hash_key])


if __name__ == "__main__":
    unittest.main()

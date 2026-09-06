"""Behavioral tests for process-to-microstructure-to-property design."""
from __future__ import annotations

import copy
import importlib.util
import json
import math
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT / "benchmarks/Chemistry/ProcessMicrostructurePropertyDesign"
sys.path.insert(0, str(ROOT))

from sle.evaluate import evaluate_candidate
from sle.frontier import load_frozen_wave
from sle.spec import load_task_spec


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _quantize(problem, row):
    quantized = {}
    for field in problem["process_fields"]:
        low, high = problem["bounds"][field]
        resolution = problem["manufacturing_resolutions"][field]
        bin_index = round((row[field] - low) / resolution)
        quantized[field] = min(max(low + bin_index * resolution, low), high)
    return quantized


def _latin_hypercube(problem, size):
    multipliers = (1, 73, 127, 181, 239)
    offsets = (0, 19, 43, 71, 101)
    rows = []
    for index in range(size):
        row = {}
        for field, multiplier, offset in zip(
            problem["process_fields"], multipliers, offsets
        ):
            low, high = problem["bounds"][field]
            unit = ((multiplier * index + offset) % size + 0.5) / size
            row[field] = low + unit * (high - low)
        rows.append(_quantize(problem, row))
    return rows


def _shortcut_grid_441(problem):
    bounds = problem["bounds"]
    rows = []
    for blend_index in range(21):
        for temperature_index in range(21):
            rows.append(_quantize(problem, {
                "blend_fraction_b": bounds["blend_fraction_b"][0]
                + blend_index / 20 * (
                    bounds["blend_fraction_b"][1]
                    - bounds["blend_fraction_b"][0]
                ),
                "anneal_temperature": bounds["anneal_temperature"][0]
                + temperature_index / 20 * (
                    bounds["anneal_temperature"][1]
                    - bounds["anneal_temperature"][0]
                ),
                "anneal_time": bounds["anneal_time"][0],
                "cooling_rate": bounds["cooling_rate"][1],
                "draw_ratio": bounds["draw_ratio"][0],
            }))
    return rows


def _shortcut_grid_343(problem, varying_fields):
    bounds = problem["bounds"]
    rows = []
    for first_index in range(7):
        for second_index in range(7):
            for third_index in range(7):
                row = {
                    "blend_fraction_b": 0.50,
                    "anneal_temperature": 0.45,
                    "anneal_time": 12.0,
                    "cooling_rate": 2.1,
                    "draw_ratio": 2.5,
                }
                for field, index in zip(
                    varying_fields,
                    (first_index, second_index, third_index),
                ):
                    low, high = bounds[field]
                    row[field] = low + index / 6 * (high - low)
                rows.append(_quantize(problem, row))
    return rows


def _greedy_development_archive(evaluator, pool, size=20):
    objective_rows = [
        [evaluator._properties(world, process)["objectives"] for process in pool]
        for world in evaluator.DEVELOPMENT_WORLDS
    ]
    selected = []
    remaining = list(range(len(pool)))
    for _ in range(size):
        best = max(
            remaining,
            key=lambda candidate: sum(
                evaluator._hypervolume_3d([
                    objective_rows[world_index][index]
                    for index in selected + [candidate]
                ])
                for world_index in range(len(evaluator.DEVELOPMENT_WORLDS))
            ),
        )
        selected.append(best)
        remaining.remove(best)
    return [pool[index] for index in selected]


def _refine_with_development_oracle(evaluator, problem, rows, passes=2):
    """Red-team the public witness with evaluator-aware coordinate exchange."""
    fields = problem["process_fields"]
    rows = [dict(row) for row in rows]
    objective_cache = {}

    def objectives(row):
        key = tuple(row[field] for field in fields)
        if key not in objective_cache:
            objective_cache[key] = tuple(
                evaluator._properties(world, row)["objectives"]
                for world in evaluator.DEVELOPMENT_WORLDS
            )
        return objective_cache[key]

    def development_hypervolume(archive):
        values = [objectives(row) for row in archive]
        return sum(
            evaluator._hypervolume_3d([
                objective_row[world_index] for objective_row in values
            ])
            for world_index in range(len(evaluator.DEVELOPMENT_WORLDS))
        ) / len(evaluator.DEVELOPMENT_WORLDS)

    best_hypervolume = development_hypervolume(rows)
    for _ in range(passes):
        for row_index in range(len(rows)):
            for field in fields:
                low, high = problem["bounds"][field]
                best_row = rows[row_index]
                for point_index in range(11):
                    trial = _quantize(problem, {
                        **rows[row_index],
                        field: low + point_index / 10 * (high - low),
                    })
                    trial_key = tuple(trial[name] for name in fields)
                    if any(
                        index != row_index
                        and tuple(row[name] for name in fields) == trial_key
                        for index, row in enumerate(rows)
                    ):
                        continue
                    trial_rows = list(rows)
                    trial_rows[row_index] = trial
                    hypervolume = development_hypervolume(trial_rows)
                    if hypervolume > best_hypervolume:
                        best_row = trial
                        best_hypervolume = hypervolume
                rows[row_index] = best_row
    return rows


class ProcessMicrostructurePropertyDesignTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.evaluator = _load(TASK / "verification/evaluator.py", "process_structure_oracle")
        cls.baseline = _load(TASK / "solution.py", "process_structure_baseline")
        cls.reference = _load(
            TASK / "verification/reference_process_archive.py",
            "process_structure_reference",
        )

    def test_public_contract_exposes_nested_surrogate_inputs(self):
        task_text = (TASK / "Task.md").read_text(encoding="utf-8")

        self.assertIn('problem["constituent_properties"]["reduced_modulus"]', task_text)
        self.assertIn('problem["constituent_properties"]["reduced_permeability"]', task_text)
        self.assertIn('problem["reference_search"]["proxy_parameters"]', task_text)
        self.assertIn('problem["reference_search"]["objective_normalization"]', task_text)

        problem = self.evaluator._problem(self.evaluator.DEVELOPMENT_WORLDS[0])
        self.assertEqual(
            set(problem["constituent_properties"]),
            {"reduced_modulus", "reduced_permeability"},
        )
        self.assertEqual(len(problem["constituent_properties"]["reduced_modulus"]), 2)
        self.assertIsInstance(problem["reference_search"]["proxy_parameters"], dict)
        self.assertEqual(
            set(problem["reference_search"]["objective_normalization"]),
            {"specific_modulus", "barrier_index", "process_energy_maximum", "clip"},
        )

    def test_shipped_process_archive_is_legal_and_normalized_to_zero(self):
        result = self.evaluator.evaluate(self.baseline.design_process_archive)
        self.assertEqual(result["valid"], 1.0)
        self.assertAlmostEqual(result["combined_score"], 0.0, places=12)
        self.assertEqual(result["development_feasibility_rate"], 1.0)

    def test_more_verified_pareto_points_can_earn_strict_continuous_gain(self):
        def intermediate(problem):
            reference = self.evaluator._reference_policy(problem)["processes"]
            return {"processes": reference[:8]}

        baseline = self.evaluator.evaluate(self.baseline.design_process_archive)
        middle = self.evaluator.evaluate(intermediate)
        reference = self.evaluator.evaluate(self.evaluator._reference_policy)
        self.assertGreater(middle["combined_score"], baseline["combined_score"])
        self.assertGreater(reference["combined_score"], middle["combined_score"])
        self.assertAlmostEqual(reference["combined_score"], 1.0, places=12)

    def test_sealed_process_and_material_shifts_are_reported_separately(self):
        result = self.evaluator.evaluate(self.evaluator._reference_policy)
        self.assertIn("development_shifted_hypervolume_score", result)
        self.assertIn("heldout_hypervolume_score", result)
        self.assertIn("heldout_shifted_hypervolume_score", result)
        self.assertTrue(all(
            len(row["raw_shifted_hypervolumes"]) == 3
            for row in result["per_instance"]
        ))
        self.assertTrue(any(
            any(abs(value - row["raw_hypervolume"]) > 1.0e-12
                for value in row["raw_shifted_hypervolumes"])
            for row in result["per_instance"]
        ))
        self.assertEqual(result["combined_score"], result["development_hypervolume_score"])

    def test_artifact_must_be_a_manufacturable_process_not_an_image(self):
        def image_artifact(problem):
            processes = [dict(row) for row in self.evaluator._weak_archive(problem)]
            processes[0]["microstructure_image"] = [[0.0, 1.0], [1.0, 0.0]]
            return {"processes": processes}

        result = self.evaluator.evaluate(image_artifact)
        self.assertEqual(result["valid"], 0.0)
        self.assertEqual(result["combined_score"], 0.0)

    def test_at_least_ten_malformed_shapes_fail_closed(self):
        def nonfinite(problem):
            rows = [dict(row) for row in self.evaluator._weak_archive(problem)]
            rows[0]["anneal_time"] = math.nan
            return {"processes": rows}

        def out_of_bounds(problem):
            rows = [dict(row) for row in self.evaluator._weak_archive(problem)]
            rows[0]["draw_ratio"] = 100.0
            return {"processes": rows}

        def raises(_problem):
            raise RuntimeError("candidate bug")

        def duplicates(problem):
            row = dict(self.evaluator._weak_archive(problem)[0])
            return {"processes": [dict(row) for _ in range(4)]}

        def extra_top(problem):
            return {"processes": self.evaluator._weak_archive(problem), "extra": 1}

        def too_few(problem):
            return {"processes": self.evaluator._weak_archive(problem)[:3]}

        def too_many(problem):
            row = self.evaluator._weak_archive(problem)[0]
            return {"processes": [{**row, "blend_fraction_b": 0.15 + 0.005 * i}
                                  for i in range(21)]}

        def row_not_mapping(problem):
            rows = self.evaluator._weak_archive(problem)
            rows[0] = None
            return {"processes": rows}

        def missing_field(problem):
            rows = self.evaluator._weak_archive(problem)
            del rows[0]["draw_ratio"]
            return {"processes": rows}

        def extra_field(problem):
            rows = self.evaluator._weak_archive(problem)
            rows[0]["image"] = []
            return {"processes": rows}

        def boolean_value(problem):
            rows = self.evaluator._weak_archive(problem)
            rows[0]["anneal_time"] = True
            return {"processes": rows}

        candidates = (
            lambda _problem: None,
            lambda _problem: {},
            lambda _problem: {"processes": None},
            extra_top,
            too_few,
            too_many,
            row_not_mapping,
            missing_field,
            extra_field,
            boolean_value,
            nonfinite,
            out_of_bounds,
            duplicates,
            raises,
        )
        for candidate in candidates:
            with self.subTest(candidate=candidate):
                result = self.evaluator.evaluate(candidate)
                self.assertEqual(result["valid"], 0.0)
                self.assertEqual(result["combined_score"], 0.0)
        self.assertGreaterEqual(len(candidates), 10)

    def test_manufacturing_resolution_deduplicates_near_identical_recipes(self):
        def near_duplicates(problem):
            rows = [dict(row) for row in self.evaluator._weak_archive(problem)]
            rows[1] = dict(rows[0])
            rows[1]["blend_fraction_b"] += 0.001
            return {"processes": rows}

        result = self.evaluator.evaluate(near_duplicates)
        self.assertEqual(result["valid"], 0.0)
        self.assertEqual(result["combined_score"], 0.0)

    def test_simple_high_b_corner_no_longer_dominates_reference(self):
        def high_b_corner(_problem):
            return {"processes": [
                {
                    "blend_fraction_b": value,
                    "anneal_temperature": 0.45,
                    "anneal_time": 0.5,
                    "cooling_rate": 4.0,
                    "draw_ratio": 1.0,
                }
                for value in (0.82, 0.83, 0.84, 0.85)
            ]}

        corner = self.evaluator.evaluate(high_b_corner)
        reference = self.evaluator.evaluate(self.evaluator._reference_policy)
        self.assertLess(corner["combined_score"], reference["combined_score"])

    def test_441_two_coordinate_shortcut_stays_below_reference(self):
        problem = self.evaluator._problem(self.evaluator.DEVELOPMENT_WORLDS[0])
        pool = _shortcut_grid_441(problem)
        self.assertEqual(len(pool), 441)
        shortcut = _greedy_development_archive(self.evaluator, pool)
        result = self.evaluator.evaluate(lambda _problem: {"processes": shortcut})
        self.assertEqual(result["valid"], 1.0)
        self.assertLess(result["combined_score"], 1.0)

    def test_three_343_point_low_dimensional_shortcuts_stay_below_reference(self):
        problem = self.evaluator._problem(self.evaluator.DEVELOPMENT_WORLDS[0])
        shortcut_axes = (
            ("blend_fraction_b", "anneal_time", "draw_ratio"),
            ("blend_fraction_b", "cooling_rate", "draw_ratio"),
            ("blend_fraction_b", "anneal_temperature", "draw_ratio"),
        )
        for axes in shortcut_axes:
            with self.subTest(axes=axes):
                pool = _shortcut_grid_343(problem, axes)
                self.assertEqual(len(pool), 343)
                self.assertEqual(len({tuple(row.values()) for row in pool}), 343)
                shortcut = _greedy_development_archive(self.evaluator, pool)
                result = self.evaluator.evaluate(
                    lambda _problem, shortcut=shortcut: {"processes": shortcut}
                )
                self.assertEqual(result["valid"], 1.0)
                self.assertLess(result["combined_score"], 0.95)

    def test_larger_public_proxy_pool_is_on_the_reference_platform(self):
        def larger_pool(problem):
            expanded = copy.deepcopy(problem)
            expanded["reference_search"]["pool_size"] = 2048
            return self.reference.design_process_archive(expanded)

        result = self.evaluator.evaluate(larger_pool)
        self.assertEqual(result["valid"], 1.0)
        self.assertGreaterEqual(result["combined_score"], 0.99)
        self.assertLessEqual(result["combined_score"], 1.005)

    def test_lazy_reference_selection_matches_exhaustive_greedy(self):
        problem = copy.deepcopy(
            self.evaluator._problem(self.evaluator.DEVELOPMENT_WORLDS[0])
        )
        problem["reference_search"]["pool_size"] = 128
        pool = self.reference._candidate_pool(problem)
        objectives = [
            self.reference._proxy_objectives(problem, row) for row in pool
        ]
        selected = []
        remaining = list(range(len(pool)))
        for _ in range(problem["reference_search"]["archive_size"]):
            best = max(
                remaining,
                key=lambda candidate: self.reference._hypervolume_3d([
                    objectives[index] for index in selected + [candidate]
                ]),
            )
            selected.append(best)
            remaining.remove(best)
        self.assertEqual(
            self.reference._select_archive_indices(
                objectives, problem["reference_search"]["archive_size"]
            ),
            selected,
        )

    def test_uncapped_score_has_evaluator_aware_headroom(self):
        problem = self.evaluator._problem(self.evaluator.DEVELOPMENT_WORLDS[0])
        reference = self.evaluator._reference_policy(problem)["processes"]
        refined = _refine_with_development_oracle(
            self.evaluator, problem, reference
        )
        result = self.evaluator.evaluate(
            lambda _problem: {"processes": refined}
        )
        self.assertEqual(result["valid"], 1.0)
        self.assertGreater(result["combined_score"], 1.004)
        self.assertEqual(result["heldout_feasibility_rate"], 1.0)

    def test_reference_is_stronger_than_each_single_factor_ablation(self):
        problem = self.evaluator._problem(self.evaluator.DEVELOPMENT_WORLDS[0])
        bounds = problem["bounds"]
        reference = self.evaluator._reference_policy(problem)["processes"]
        ablations = {
            "no_draw": ("draw_ratio", bounds["draw_ratio"][0]),
            "short_time": ("anneal_time", bounds["anneal_time"][0]),
            "fast_cooling": ("cooling_rate", bounds["cooling_rate"][1]),
            "single_low_temperature": (
                "anneal_temperature", bounds["anneal_temperature"][0]
            ),
        }
        for name, (field, value) in ablations.items():
            with self.subTest(ablation=name):
                rows = [
                    _quantize(problem, {**row, field: value})
                    for row in reference
                ]
                result = self.evaluator.evaluate(
                    lambda _problem, rows=rows: {"processes": rows}
                )
                self.assertEqual(result["valid"], 1.0)
                self.assertLess(result["combined_score"], 0.90)

    def test_crystallization_matches_frozen_mobility_limited_completion(self):
        world = self.evaluator.DEVELOPMENT_WORLDS[0]
        process = {
            "blend_fraction_b": 0.50,
            "anneal_temperature": 0.62,
            "anneal_time": 6.0,
            "cooling_rate": 0.8,
            "draw_ratio": 2.2,
        }
        parameters = self.evaluator.MODEL_PARAMETERS["properties"]
        temperature = process["anneal_temperature"]
        equilibrium = 1.0 / (
            1.0 + math.exp(
                parameters["crystallinity_equilibrium_temperature_coefficient"]
                * (
                    temperature
                    - parameters[
                        "crystallinity_equilibrium_temperature_reference"
                    ]
                )
                + parameters["crystallinity_equilibrium_cooling_coefficient"]
                * process["cooling_rate"]
            )
        )
        effective_time = (
            process["anneal_time"]
            + parameters["crystallization_effective_time_cooling_coefficient"]
            / process["cooling_rate"]
        )
        expected = equilibrium * (
            1.0 - math.exp(
                -parameters["crystallization_rate_constant"]
                * world["mobility_scale"]
                * effective_time
                * math.exp(
                    -parameters["crystallization_activation_energy"]
                    / (
                        temperature
                        + parameters["crystallization_temperature_offset"]
                    )
                )
            )
        )
        observed = self.evaluator._properties(world, process)["crystallinity"]
        self.assertAlmostEqual(observed, expected, places=14)
        slower_world = {**world, "mobility_scale": world["mobility_scale"] * 0.5}
        slower = self.evaluator._properties(slower_world, process)["crystallinity"]
        self.assertLess(slower, observed)

    def test_candidate_session_is_reset_between_every_world(self):
        evaluator = self.evaluator

        class StatefulCandidate:
            def __init__(self):
                self.calls = 0
                self.resets = 0

            def __call__(self, problem):
                self.calls += 1
                return {"processes": evaluator._weak_archive(problem)}

            def reset_session(self):
                self.resets += 1

        candidate = StatefulCandidate()
        self.evaluator.evaluate(candidate)
        self.assertEqual(candidate.calls, 6)
        self.assertEqual(candidate.resets, 5)

    def test_raw_hypervolume_emits_a_quantized_archive_frontier_record(self):
        result = self.evaluator.evaluate(self.evaluator._reference_policy)
        self.assertIs(result["frontier_record_emitted"], True)
        self.assertEqual(len(result["frontier_records"]), 1)
        record = result["frontier_records"][0]
        self.assertEqual(record["value"], result["development_raw_hypervolume"])
        self.assertIn(":panel:sha256:", record["canonical_id"])

    def test_frontier_record_requires_legal_heldout_transfer(self):
        def development_only(problem):
            modulus_b = problem["constituent_properties"]["reduced_modulus"][1]
            if modulus_b in (6.0, 4.7):
                return None
            return self.evaluator._reference_policy(problem)

        result = self.evaluator.evaluate(development_only)

        self.assertEqual(result["valid"], 1.0)
        self.assertAlmostEqual(result["combined_score"], 1.0, places=12)
        self.assertEqual(result["heldout_feasibility_rate"], 0.0)
        self.assertIs(result["frontier_record_emitted"], False)
        self.assertEqual(result["frontier_records"], [])

    def test_machine_readable_panel_is_the_evaluator_source(self):
        panel = json.loads((
            TASK / "frontier_eval/contracts/evaluation_panel_v1.json"
        ).read_text(encoding="utf-8"))
        self.assertEqual(self.evaluator.PROCESS_FIELDS, tuple(panel["process_fields"]))
        self.assertEqual(
            self.evaluator.HYPERVOLUME_REFERENCE_POINT,
            tuple(panel["hypervolume_reference_point"]),
        )
        self.assertEqual(
            [dict(world) for world in self.evaluator.WORLDS],
            panel["worlds"],
        )
        self.assertEqual(
            [dict(shift) for shift in self.evaluator.SHIFT_SPECS],
            panel["shift_specs"],
        )
        self.assertEqual(self.evaluator.MODEL_PARAMETERS, panel["model_parameters"])
        self.assertEqual(self.evaluator.BASELINE_POLICY, panel["baseline_policy"])
        self.assertEqual(self.evaluator.REFERENCE_SEARCH, panel["reference_search"])
        self.assertEqual(
            self.evaluator.FRONTIER_PROMOTION,
            panel["frontier_promotion"],
        )
        self.assertEqual(
            panel["model_parameters"]["properties"]["draw_modulus_gain"],
            0.35,
        )
        self.assertEqual(
            panel["model_parameters"]["properties"]["draw_permeability_penalty"],
            0.20,
        )
        self.assertEqual(
            panel["model_parameters"]["properties"][
                "crystallization_activation_energy"
            ],
            7.0,
        )
        self.assertEqual(
            panel["model_parameters"]["properties"][
                "crystallization_rate_constant"
            ],
            700.0,
        )
        self.assertEqual(
            panel["model_parameters"]["properties"][
                "crystallinity_equilibrium_cooling_coefficient"
            ],
            0.30,
        )
        self.assertEqual(
            panel["objective_normalization"]["process_energy"]["maximum"],
            7.5,
        )
        problem = self.evaluator._problem(self.evaluator.DEVELOPMENT_WORLDS[0])
        names = panel["reference_search"]["proxy_parameter_names"]
        self.assertEqual(
            problem["reference_search"]["proxy_parameters"],
            {
                name: panel["model_parameters"]["properties"][name]
                for name in names
            },
        )
        self.assertEqual(
            problem["reference_search"]["pool_size"],
            panel["reference_search"]["pool_size"],
        )

    def test_standalone_runner_keeps_oracle_out_of_candidate_modules(self):
        candidate_source = '''
import sys


def design_process_archive(problem):
    leaked = any(
        name == "evaluator"
        or "/verification/evaluator.py" in str(getattr(module, "__file__", ""))
        for name, module in sys.modules.items()
    )
    bounds = problem["bounds"]
    low, high = bounds["blend_fraction_b"]
    processes = [
        {
            "blend_fraction_b": low + index / 3.0 * (high - low),
            "anneal_temperature": bounds["anneal_temperature"][1],
            "anneal_time": bounds["anneal_time"][0],
            "cooling_rate": bounds["cooling_rate"][1],
            "draw_ratio": bounds["draw_ratio"][0],
        }
        for index in range(4)
    ]
    result = {"processes": processes}
    if leaked:
        result["oracle_leak"] = True
    return result
'''
        with TemporaryDirectory() as temporary_directory:
            candidate_path = Path(temporary_directory) / "candidate.py"
            metrics_path = Path(temporary_directory) / "metrics.json"
            candidate_path.write_text(candidate_source, encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(TASK / "frontier_eval/run_eval.py"),
                    "--candidate",
                    str(candidate_path),
                    "--metrics-out",
                    str(metrics_path),
                ],
                cwd=TASK,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
            self.assertEqual(metrics["valid"], 1.0)
            self.assertEqual(metrics["combined_score"], 0.0)

    def test_wave_hashes_load_and_baseline_uses_isolated_candidate_protocol(self):
        spec = load_task_spec(TASK)
        wave = load_frozen_wave(spec)
        self.assertEqual(wave.wave_id, "reduced-process-property-pareto-v1")
        self.assertEqual(
            wave.cells["process-property-pareto-hypervolume"]["reference_value"],
            self.evaluator._anchors()["development"]["reference"],
        )
        metrics = evaluate_candidate(spec, TASK / "solution.py", timeout_s=20)
        self.assertNotIn("infrastructure_failure", metrics)
        self.assertEqual(metrics["valid"], 1.0)
        self.assertEqual(metrics["combined_score"], 0.0)

    def test_independent_reference_runs_through_frontier_runner(self):
        source = (
            TASK / "verification/reference_process_archive.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("import evaluator", source)
        self.assertNotIn("evaluation_panel", source)
        self.assertNotIn("evaluator._properties", source)
        reference = _load(
            TASK / "verification/reference_process_archive.py",
            "process_public_reference",
        )
        problem = self.evaluator._problem(self.evaluator.DEVELOPMENT_WORLDS[0])
        pool = reference._candidate_pool(problem)
        self.assertEqual(len(pool), 1024)
        self.assertEqual(len({tuple(row.values()) for row in pool}), 1024)
        first = reference.design_process_archive(problem)
        second = reference.design_process_archive(problem)
        self.assertEqual(first, second)
        spec = load_task_spec(TASK)
        metrics = evaluate_candidate(
            spec,
            TASK / "verification/reference_process_archive.py",
            timeout_s=20,
        )
        self.assertNotIn("infrastructure_failure", metrics)
        self.assertEqual(metrics["valid"], 1.0)
        self.assertAlmostEqual(metrics["combined_score"], 1.0, places=12)


if __name__ == "__main__":
    unittest.main()

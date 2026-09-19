from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

import numpy as np

from sle.certification import certification_status, load_certification
from sle.evaluate import INVALID_SCORE, evaluate_candidate
from sle.metric_visibility import search_visible_metrics
from sle.registry import discover_task_dirs, find_task, list_tasks
from _sandbox_tools import skip_unless_sandbox  # noqa: E402


def load_oracle(task_id: str):
    spec = find_task(task_id, include_uncertified=True)
    path = spec.task_dir / "verification/evaluator.py"
    module_spec = importlib.util.spec_from_file_location("test_oracle_" + spec.task_dir.name, path)
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    return module


class CertificationPolicyTests(unittest.TestCase):
    def test_default_registry_is_certified_only(self):
        tasks = list_tasks()
        # Two of the seven - SpinGlassGroundState and PoissonSolver2D - were retired along with
        # the other saturated tasks. Certification says the task is sound; it says nothing about
        # whether the task still has room left to measure anything.
        self.assertEqual(len(tasks), 5)
        self.assertTrue(all(certification_status(s.task_id) == "certified" for s in tasks))
        # Fifteen tasks retired: every model had reached their cap, so the score could no
        # longer separate two searchers. Tasks scoring above 1.0 stayed - on an uncapped task
        # that is the intended result rather than saturation.
        # 58: PTA + Bose + quinary hull on top of CrowdedSpectrum, Survivorship,
        # AMOC, LookElsewhere and the five Wave-0 constructions (55).
        # Computed: the inventory is whatever the registry discovers.
        self.assertEqual(len(list_tasks(None)), len(discover_task_dirs()))
        self.assertEqual(
            certification_status("ProteinEngineering/ProteinStabilityDesign"),
            "candidate",
        )
        self.assertEqual(
            certification_status("MaterialsScience/AlloyHardnessOptimization"),
            "candidate",
        )

    def test_manifest_explicitly_covers_inventory(self):
        inventory_ids = {spec.task_id for spec in list_tasks(None)}
        manifest_ids = set(load_certification()["tasks"])
        self.assertEqual(manifest_ids, inventory_ids)

    def test_the_clone_group_is_gone_rather_than_quarantined(self):
        """Four near-duplicate trig tasks were quarantined; they have since been deleted.

        Quarantine kept them visible as defect evidence. They met none of the benchmark's nine
        standards, and two of the nine tasks removed alongside them were not natural science at
        all, so the set was removed rather than preserved. This guard now checks the removal held
        instead of checking the quarantine.
        """
        records = load_certification()["tasks"]
        clone_ids = {k for k, v in records.items()
                     if v.get("duplicate_group") == "generic_trig_8d_v1"}
        self.assertEqual(clone_ids, set())
        # Discovery quarantine records live on main; none belong to this optimization inventory.
        self.assertEqual({task for task, record in records.items()
                          if record.get("status") == "quarantined"}, set())

    def test_certified_tasks_have_stable_citation_ids(self):
        records = load_certification()["tasks"]
        for spec in list_tasks():
            ids = records[spec.task_id].get("citation_ids", [])
            self.assertTrue(ids, spec.task_id)
            self.assertTrue(all(":" in identifier for identifier in ids), spec.task_id)


class ScientificInvariantTests(unittest.TestCase):
    def test_lennard_jones_rigid_motion_invariance(self):
        oracle = load_oracle("Chemistry/LennardJonesCluster")
        rng = np.random.default_rng(3)
        x = rng.normal(size=(13, 3))
        q, _ = np.linalg.qr(rng.normal(size=(3, 3)))
        y = x @ q + np.array([4.0, -2.0, 1.5])
        self.assertAlmostEqual(oracle.lj_energy(x), oracle.lj_energy(y), places=9)



    def test_matrix_tensor_accepts_schoolbook_and_rejects_perturbation(self):
        oracle = load_oracle("Algorithm/MatrixMultiplicationRank")
        m = n = p = 2
        rank = m * n * p
        u = np.zeros((rank, m * n)); v = np.zeros((rank, n * p)); w = np.zeros((m * p, rank))
        r = 0
        for i in range(m):
            for k in range(n):
                for j in range(p):
                    u[r, i*n+k] = v[r, k*p+j] = w[i*p+j, r] = 1
                    r += 1
        self.assertTrue(oracle.verify_decomposition(u, v, w, m, n, p)[0])
        u[0, 0] += 0.1
        self.assertFalse(oracle.verify_decomposition(u, v, w, m, n, p)[0])

    def test_cap_verifier_accepts_hypercube_and_rejects_line(self):
        oracle = load_oracle("Mathematics/CapSet")
        cube = [[(x >> i) & 1 for i in range(4)] for x in range(16)]
        self.assertTrue(oracle.verify_cap(cube, 4)[0])
        self.assertFalse(oracle.verify_cap([[0, 0], [1, 0], [2, 0]], 2)[0])

    def test_circle_packing_geometry(self):
        oracle = load_oracle("Optimization/CirclePacking")
        centers = np.array([[1, 1], [3, 1], [1, 3], [3, 3]], dtype=float)
        self.assertTrue(oracle.check_packing(4, centers, 4)["valid"])
        centers[1] = [2.5, 1]
        self.assertFalse(oracle.check_packing(4, centers, 4)["valid"])

    def test_thin_film_zero_thickness_matches_bare_interface(self):
        oracle = load_oracle("Photonics/MultilayerThinFilm")
        spectrum = oracle._reflectance_spectrum([0], [0.0])
        self.assertTrue(np.allclose(spectrum, oracle._R_BARE, atol=1e-12))































    def test_truss_v2_topology_references_and_metric_sealing(self):
        oracle = load_oracle("StructuralEngineering/TrussWeightMinimization")
        self.assertEqual(len(oracle.DEVELOPMENT_INSTANCES), 4)
        self.assertEqual(len(oracle.HELDOUT_INSTANCES), 2)
        for instance in oracle.INSTANCES:
            undirected = [
                tuple(sorted(map(int, pair))) for pair in instance["members"]
            ]
            self.assertEqual(len(undirected), len(set(undirected)))
            baseline = oracle._scenario_analysis(
                instance, instance["baseline_areas"]
            )
            nominal = oracle._scenario_analysis(
                instance, instance["nominal_reference_areas"]
            )
            self.assertTrue(baseline["feasible"])
            self.assertTrue(nominal["feasible"])
            for loads in instance["load_cases"]:
                mechanics = oracle._case_analysis(
                    instance, instance["baseline_areas"], loads
                )
                self.assertLessEqual(
                    mechanics["stiffness_symmetry_error"], 1e-10
                )
                self.assertLessEqual(
                    mechanics["force_equilibrium_error_lbs"], 1e-6
                )
            self.assertTrue(all(
                oracle._scenario_analysis(
                    instance, instance["baseline_areas"], shift, shift["name"]
                )["feasible"]
                for shift in oracle.SHIFT_SPECS
            ))
            self.assertTrue(all(
                oracle._scenario_analysis(
                    instance, instance["robust_reference_areas"], shift,
                    shift["name"],
                )["feasible"]
                for shift in oracle.SHIFT_SPECS
            ))
            self.assertTrue(any(
                not oracle._scenario_analysis(
                    instance, instance["nominal_reference_areas"], shift,
                    shift["name"],
                )["feasible"]
                for shift in oracle.SHIFT_SPECS
            ))

        def all_max(_nodes, members, _fixed, _loads, _modulus, _density,
                    _tension, _compression, _displacement, _area_min, area_max,
                    _inertia):
            return np.full(len(members), area_max)

        metrics = oracle.evaluate(all_max)
        self.assertEqual(metrics["valid"], 1.0)
        self.assertEqual(metrics["combined_score"], 0.0)
        self.assertEqual(metrics["mean_shifted_case_feasibility_rate"], 1.0)
        shown = search_visible_metrics(metrics)
        self.assertNotIn("robustness_score", shown)
        self.assertNotIn("heldout_policy_score", shown)
        self.assertNotIn("per_instance", shown)

    def test_truss_v2_nonfinite_bounds_and_nominal_infeasibility_fail_closed(self):
        oracle = load_oracle("StructuralEngineering/TrussWeightMinimization")
        nonfinite = oracle.evaluate(
            lambda _nodes, members, *_args: np.full(len(members), np.nan)
        )
        outside = oracle.evaluate(
            lambda _nodes, members, *_args: np.full(len(members), -1.0)
        )
        minimum = oracle.evaluate(
            lambda _nodes, members, _fixed, _loads, _modulus, _density,
            _tension, _compression, _displacement, area_min, _area_max,
            _inertia: np.full(len(members), area_min)
        )
        for metrics in (nonfinite, outside, minimum):
            self.assertEqual(metrics["valid"], 0.0)
            self.assertEqual(metrics["combined_score"], 0.0)
            self.assertTrue(all(
                not row["valid"] for row in metrics["per_instance"]
            ))



    def test_heat_exchanger_v2_references_physics_and_metric_sealing(self):
        oracle = load_oracle("Thermodynamics/HeatExchangerDesign")
        self.assertEqual(len(oracle.DEVELOPMENT_INSTANCES), 4)
        self.assertEqual(len(oracle.HELDOUT_INSTANCES), 2)
        for instance in oracle.INSTANCES:
            baseline = oracle._baseline_archive(instance["problem"])
            nominal = oracle.REFERENCE_ARCHIVES[instance["name"]]
            robust = oracle.ROBUST_REFERENCE_ARCHIVES[instance["name"]]
            self.assertEqual(nominal.shape, (oracle.MAX_ARCHIVE_SIZE, 5))
            self.assertEqual(robust.shape, (oracle.MAX_ARCHIVE_SIZE, 5))
            self.assertTrue(np.array_equal(
                nominal,
                oracle._reference_archive(instance, "nominal"),
            ))
            anchors = oracle.CALIBRATED_ANCHORS[instance["name"]]
            self.assertGreater(
                anchors["reference_exact_hypervolume"],
                anchors["baseline_exact_hypervolume"],
            )
            self.assertGreater(
                anchors["reference_proxy_hypervolume"],
                anchors["baseline_proxy_hypervolume"],
            )
            _, baseline_exact, baseline_shifts = oracle._evaluate_archive(
                instance, baseline
            )
            _, nominal_exact, _ = oracle._evaluate_archive(instance, nominal)
            _, robust_exact, robust_shifts = oracle._evaluate_archive(instance, robust)
            self.assertTrue(all(row["feasible"] for row in baseline_exact))
            self.assertTrue(all(row["feasible"] for row in nominal_exact))
            self.assertTrue(all(row["feasible"] for row in robust_exact))
            self.assertTrue(all(
                all(row["feasible"] for row in records)
                for records in baseline_shifts + robust_shifts
            ))
            self.assertLessEqual(max(
                row["boundary_residual_k"]
                for records in (baseline_exact, nominal_exact, robust_exact)
                for row in records
            ), 1e-5)

            # Adding a dominated duplicate cannot improve two-objective hypervolume.
            records = list(nominal_exact)
            dominated = dict(records[0])
            dominated["heat_duty_w"] = 0.5 * records[0]["heat_duty_w"]
            dominated["annualized_cost_usd"] = 2.0 * records[0]["annualized_cost_usd"]
            augmented = records + [dominated, dict(records[0])]
            self.assertAlmostEqual(
                oracle._hypervolume(instance, records),
                oracle._hypervolume(instance, augmented),
                places=12,
            )

        def baseline_policy(problem):
            return oracle._baseline_archive(problem)

        metrics = oracle.evaluate(baseline_policy)
        self.assertEqual(metrics["valid"], 1.0)
        self.assertEqual(metrics["combined_score"], 0.0)
        self.assertEqual(metrics["feasibility_rate"], 1.0)
        shown = search_visible_metrics(metrics)
        for key in (
            "development_proxy_score", "heldout_exact_score",
            "robustness_score", "development_false_promotion_rate",
            "development_proxy_exact_rank_correlation", "per_instance",
        ):
            self.assertNotIn(key, shown)

    def test_heat_exchanger_v2_malformed_archives_fail_closed(self):
        oracle = load_oracle("Thermodynamics/HeatExchangerDesign")

        def invalid_policy(kind):
            def policy(problem):
                archive = oracle._baseline_archive(problem).copy()
                if kind == "nonfinite":
                    archive[0, 0] = np.nan
                elif kind == "wrong_shape":
                    return archive[:, :4]
                elif kind == "too_short":
                    return archive[:3]
                elif kind == "out_of_bounds":
                    archive[:, 0] = -1.0
                elif kind == "nonintegral":
                    archive[:, 2] += 0.5
                elif kind == "not_divisible":
                    archive[:, 4] = 4.0
                    archive[:, 2] = 25.0
                else:
                    raise AssertionError(kind)
                return archive
            return policy

        for kind in (
            "nonfinite", "wrong_shape", "too_short", "out_of_bounds",
            "nonintegral", "not_divisible",
        ):
            metrics = oracle.evaluate(invalid_policy(kind))
            self.assertEqual(metrics["valid"], 0.0, kind)
            self.assertEqual(metrics["combined_score"], 0.0, kind)
            self.assertTrue(all(
                not row["valid"] for row in metrics["per_instance"]
            ), kind)





    def test_neutron_diffusion_operator_is_symmetric_and_reference_is_reproducible(self):
        oracle = load_oracle("NuclearEngineering/NeutronDiffusionCriticality")
        uniform = np.full(oracle.N_ZONES, oracle.AVG_ENRICH_MAX)
        k_uniform = oracle._compute_keff(uniform)
        k_reference = oracle._compute_keff(oracle.REFERENCE_LOADING)
        self.assertAlmostEqual(float(np.mean(oracle.REFERENCE_LOADING)),
                               oracle.AVG_ENRICH_MAX, places=12)
        self.assertAlmostEqual(k_uniform, 0.9841790542, places=8)
        self.assertAlmostEqual(k_reference, 1.0591815191, places=8)
        self.assertAlmostEqual(k_reference - k_uniform, 0.0750024649, places=8)

        _, _, _, _, diffusion, absorption, _ = oracle._cross_sections(
            np.repeat(oracle.REFERENCE_LOADING,
                      oracle.N_MESH // oracle.N_ZONES)
        )
        h = oracle.SLAB_WIDTH / (oracle.N_MESH + 1)
        interface = 2 * diffusion[:-1] * diffusion[1:] / (
            diffusion[:-1] + diffusion[1:]
        )
        left = np.concatenate(([diffusion[0]], interface))
        right = np.concatenate((interface, [diffusion[-1]]))
        matrix = np.diag((left + right) / h**2 + absorption)
        matrix += np.diag(-interface / h**2, 1)
        matrix += np.diag(-interface / h**2, -1)
        self.assertTrue(np.allclose(matrix, matrix.T, atol=1e-14))



    def test_pendulum_down_is_stable_and_upright_is_unstable(self):
        oracle = load_oracle("ControlTheory/InvertedPendulumSwingUp")
        plant = oracle._plant_tuple()
        step = 1e-6

        def acceleration(theta):
            state = np.array([0.0, 0.0, theta, 0.0])
            return oracle.cart_pole_derivative(state, 0.0, plant)[3]

        down_derivative = (acceleration(step) - acceleration(-step)) / (2 * step)
        upright_derivative = (
            acceleration(np.pi + step) - acceleration(np.pi - step)
        ) / (2 * step)
        self.assertLess(down_derivative, 0.0)
        self.assertGreater(upright_derivative, 0.0)

    def test_pendulum_rk4_preserves_hanging_equilibrium(self):
        oracle = load_oracle("ControlTheory/InvertedPendulumSwingUp")
        state = np.zeros(4)
        for _ in range(100):
            state = oracle._rk4_step(state, 0.0, oracle._plant_tuple())
        self.assertTrue(np.allclose(state, np.zeros(4), atol=1e-12))


if __name__ == "__main__":
    unittest.main()

"""Independent numerical and public-boundary checks for the climate apparatus."""

import copy
import json
import os
from pathlib import Path
import time
import unittest

import numpy as np
from scipy.integrate import solve_ivp

from env.climate_response.baseline import baseline
from env.climate_response.kernel import Kernel, STRATA, generate
from env.climate_response.protocol import example, validate_spec
from env.climate_response.world import World


def independent_reference(parameters, spec):
    """Flux-form DOP853, independent of kernel matrix assembly and RK4."""
    capacity = np.asarray(parameters["capacities"])
    conductance = np.asarray(parameters["exchanges"])
    state = np.zeros(len(capacity))
    rows = []
    total_nfev = 0
    for year, forcing in enumerate(spec["forcing_w_m2"], 1):
        def rhs(t, temperatures):
            flux = np.zeros(len(capacity))
            flux[0] = (parameters["forcing_scale"]*forcing - parameters["feedback"]*temperatures[0]
                       - parameters["curvature"]*temperatures[0]**3)
            for edge in range(len(conductance)):
                transported = conductance[edge]*(temperatures[edge]-temperatures[edge+1])
                flux[edge] -= transported
                flux[edge+1] += transported
            return flux/capacity
        result = solve_ivp(rhs, (0, 1), state, method="DOP853", rtol=2e-12, atol=2e-13)
        if not result.success or result.nfev > 10000:
            raise AssertionError("reference failed or exceeded planned interval budget")
        total_nfev += result.nfev
        state = result.y[:, -1]
        if year in spec["times_years"]:
            uptake = parameters["forcing_scale"]*forcing - parameters["feedback"]*state[0] - parameters["curvature"]*state[0]**3
            rows.append([state[0], uptake])
    return np.asarray(rows), total_nfev


class ClimateNumericalTests(unittest.TestCase):
    def test_independent_reference_extrema_and_convergence(self):
        start = time.monotonic()
        histories = {"zero": [0.0]*160, "alternating_extrema": [-1.0, 8.0]*80,
                     "pulse_recovery": [8.0]*40+[0.0]*80+[-1.0]*40}
        diagnostics = []
        for seed, stratum in zip((73101, 73102, 73103), STRATA):
            parameters = generate(seed, stratum)
            kernel = Kernel(parameters)
            for name, forcing in histories.items():
                spec = validate_spec({"forcing_w_m2": forcing})
                computed, _ = kernel.trajectory(spec)
                reference, nfev = independent_reference(parameters, spec)
                error = float(np.max(np.abs(computed-reference)))
                self.assertLess(error, 1e-5)
                if name == "zero":
                    self.assertEqual(float(np.max(np.abs(computed))), 0.0)
                row = {"seed": seed, "stratum": stratum, "history": name, "years": 160,
                       "max_absolute_error": error, "reference_rhs_calls": nfev}
                if stratum == "state_dependent_feedback" and name != "zero":
                    refined, _ = kernel.trajectory(spec, substeps=40)
                    refined_error = float(np.max(np.abs(refined-reference)))
                    self.assertLess(refined_error, error/8)
                    row["refined_max_absolute_error"] = refined_error
                diagnostics.append(row)
        self.assertLess(time.monotonic()-start, 180)
        destination = os.environ.get("SLE_CLIMATE_DIAGNOSTICS")
        if destination:
            Path(destination).write_text(json.dumps({"checks": diagnostics, "wall_seconds": time.monotonic()-start,
                "reference_trajectories": 9, "kernel_trajectories": 11,
                "noise_std": [.06, .14], "acceptance_absolute": 1e-5}, indent=2)+"\n")

    def test_conservative_energy_exchange(self):
        for stratum in STRATA:
            kernel = Kernel(generate(73101, stratum))
            state = np.linspace(-.8, 2.3, len(kernel.capacities))
            for forcing in (-1, 0, 8):
                stored_derivative = float(kernel.capacities @ kernel.derivative(state, forcing))
                self.assertAlmostEqual(stored_derivative, kernel.radiative(state, forcing), places=12)

    def test_linear_superposition_and_switch_convention(self):
        world = World(73101, _operator_stratum="two_layer")
        first = [2.0]*20+[0.0]*20
        second = [0.0]*10+[1.0]*30
        a = np.asarray(world.run({"forcing_w_m2": first})["values"])
        b = np.asarray(world.run({"forcing_w_m2": second})["values"])
        combined = np.asarray(world.run({"forcing_w_m2": (np.asarray(first)+second).tolist()})["values"])
        np.testing.assert_allclose(a+b, combined, atol=1e-12)
        p = world._kernel
        self.assertAlmostEqual(a[19, 1], 2*p.forcing_scale-p.feedback*a[19, 0], places=12)
        self.assertAlmostEqual(a[20, 1], -p.feedback*a[20, 0], places=12)


class ClimatePublicTests(unittest.TestCase):
    def test_invariance_fresh_reset_noise_and_subsampling(self):
        spec = example()
        world = World(73101)
        clean = world.run(spec)
        noisy = world.run(spec, noise_key="development-a")
        self.assertEqual(noisy, world.run(spec, noise_key="development-a"))
        self.assertNotEqual(noisy, world.run(spec, noise_key="development-b"))
        self.assertEqual(clean, world.run(spec))
        all_rows = world.run({"forcing_w_m2": spec["forcing_w_m2"]})
        self.assertEqual(clean["values"], [all_rows["values"][year-1] for year in spec["times_years"]])
        self.assertEqual(set(clean), {"axis", "channels", "values"})
        for stratum in STRATA:
            self.assertEqual(world.describe(), World(73102, _operator_stratum=stratum).describe())
        for private_word in ("capacities", "curvature", "two_layer", "three_layer", "73101"):
            self.assertNotIn(private_word, json.dumps(world.describe()))

    def test_validation_panels_and_cost(self):
        world = World(73102)
        invalid = [{}, {"forcing_w_m2": []}, {"forcing_w_m2": [True]},
                   {"forcing_w_m2": [float("nan")]}, {"forcing_w_m2": [8.1]},
                   {"forcing_w_m2": [1]*161}, {"forcing_w_m2": [1], "seed": 2},
                   {"forcing_w_m2": [1]*3, "times_years": [1, 1, 3]},
                   {"forcing_w_m2": [1]*3, "times_years": [1.5, 3]},
                   {"forcing_w_m2": [1]*3, "times_years": [0, 3]},
                   {"forcing_w_m2": [1]*3, "times_years": [1, 2]}]
        for spec in invalid:
            with self.assertRaises(ValueError):
                world.validate(spec)
        for kind in ("development", "conditions", "interventions"):
            panel = world.panel(83001, kind, count=4)
            self.assertEqual(panel, world.panel(83001, kind, count=4))
            self.assertTrue(all(world.validate(spec) == spec for spec in panel))
        self.assertEqual(world.cost({"forcing_w_m2": [8]*160}), 184)
        for noise_key in (1, True, [], "x"*257):
            with self.assertRaises(ValueError):
                world.run(example(), noise_key=noise_key)

    def test_public_data_baseline(self):
        world = World(73103)
        spec = example()
        self.assertEqual(np.asarray(baseline([], spec)).shape, (len(spec["times_years"]), 2))
        record = {"spec": spec, "observation": world.run(spec, noise_key="baseline")}
        self.assertEqual(baseline([record], spec), record["observation"]["values"])
        malformed = copy.deepcopy(record)
        malformed["observation"]["channels"] = ["private"]
        with self.assertRaises(ValueError):
            baseline([malformed], spec)


if __name__ == "__main__":
    unittest.main()

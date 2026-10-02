import copy
import importlib.util
import json
import pathlib
import unittest
from unittest import mock

import numpy as np
from scipy.integrate import solve_ivp
from scipy.sparse import diags

from env.heat_transport.world import CHANNELS, World, baseline


ROOT = pathlib.Path(__file__).resolve().parents[1]


def experiment():
    return json.loads((ROOT / "examples" / "experiment.json").read_text())


class HeatPhysicsTests(unittest.TestCase):
    def test_uniform_equilibrium_and_zero_time(self):
        world = World(8)
        spec = experiment()
        spec.update(heaters=[], flow=1.0, cooling=3.0)
        np.testing.assert_allclose(world.run(spec)["values"], 20.0, atol=2e-11)
        spec.update(initial_temperature=73.0, boundary_temperatures=[0.0, 80.0])
        self.assertEqual(world.run(spec)["values"][0], [73.0] * 3)

    def test_continuum_uniform_slab_cooling(self):
        # Separation-of-variables solution with zero Dirichlet endpoints.
        world = World(1)
        world._diffusivity_left = world._diffusivity_right = 0.023
        spec = experiment()
        spec.update(heaters=[], flow=0.0, cooling=0.0, initial_temperature=40.0,
                    boundary_temperatures=[0.0, 0.0], times=[0.5, 2.0, 8.0, 20.0])
        modes = np.arange(1, 601, 2, dtype=float)
        exact = (4.0 * 40.0 / np.pi *
                 np.exp(-0.023 * np.pi**2 * np.outer(spec["times"], modes**2)).dot(
                     np.sin(np.pi * np.outer(modes, spec["probes"])) / modes[:, None]))
        np.testing.assert_allclose(world.run(spec)["values"], exact, atol=0.006, rtol=0.001)

    def test_layered_steady_conduction_matches_resistance_formula(self):
        world = World(2)
        world._diffusivity_left, world._diffusivity_right = 0.06, 0.04
        world._interface = 0.473  # Off-grid interface exercises harmonic face resistance.
        spec = experiment()
        spec.update(heaters=[], flow=0.0, cooling=0.0, initial_temperature=25.0,
                    boundary_temperatures=[10.0, 40.0], times=[30.0], probes=[0.21, 0.53, 0.82])
        x = np.asarray(spec["probes"])
        resistance = np.minimum(x, 0.473) / 0.06 + np.maximum(x - 0.473, 0.0) / 0.04
        exact = 10.0 + 30.0 * resistance / (0.473 / 0.06 + (1.0 - 0.473) / 0.04)
        np.testing.assert_allclose(world.run(spec)["values"][0], exact, atol=0.0002)

    def test_independent_flux_ode_integrator(self):
        world = World(3)
        world._interface = 0.47  # Grid-aligned material interface.
        spec = experiment()
        spec.update(flow=-0.9, cooling=2.3, initial_temperature=35.0,
                    boundary_temperatures=[10.0, 30.0], ambient_temperature=15.0,
                    times=[0.0, 0.15, 1.3, 5.0, 19.0], probes=[0.12, 0.47, 0.88])
        dx = 1.0 / world._intervals
        full_x = np.linspace(0.0, 1.0, world._intervals + 1)
        interior_x = full_x[1:-1]
        face_x = (full_x[1:] + full_x[:-1]) / 2.0
        diffusivity = np.where(face_x < world._interface, world._diffusivity_left,
                               world._diffusivity_right)
        source = sum(h["power"] * np.exp(-0.5 * ((interior_x - h["position"]) / h["width"])**2)
                     for h in spec["heaters"])

        def rhs(time, interior):
            full = np.r_[spec["boundary_temperatures"][0], interior,
                         spec["boundary_temperatures"][1]]
            flux = diffusivity * np.diff(full) / dx
            advection = spec["flow"] * world._flow_gain * (full[2:] - full[:-2]) / (2.0 * dx)
            return (np.diff(flux) / dx - advection - spec["cooling"] * world._loss *
                    (interior - spec["ambient_temperature"]) + source)

        n = len(interior_x)
        solution = solve_ivp(rhs, (0.0, 19.0), np.full(n, 35.0), t_eval=spec["times"],
                             method="BDF", rtol=2e-9, atol=2e-10,
                             jac_sparsity=diags([np.ones(n-1), np.ones(n), np.ones(n-1)], [-1, 0, 1]))
        self.assertTrue(solution.success)
        expected = [np.interp(spec["probes"], interior_x, row) for row in solution.y.T]
        np.testing.assert_allclose(world.run(spec)["values"], expected, atol=2e-6, rtol=2e-7)

    def test_maximum_principle_and_heater_monotonicity(self):
        world = World(10)
        spec = experiment()
        spec.update(heaters=[], flow=1.0, cooling=3.0, initial_temperature=80.0,
                    boundary_temperatures=[0.0, 0.0], ambient_temperature=0.0,
                    times=[0.0, 0.01, 0.1, 1.0, 5.0, 30.0])
        values = np.asarray(world.run(spec)["values"])
        self.assertGreaterEqual(values.min(), -1e-8)
        self.assertLessEqual(values.max(), 80.0 + 1e-8)
        spec["heaters"] = [{"position": 0.5, "power": 8.0, "width": 0.2}]
        hot = np.asarray(world.run(spec)["values"])
        self.assertTrue(np.all(hot >= values - 1e-8))


class HeatContractTests(unittest.TestCase):
    def test_validation_canonicalization_and_bounded_work(self):
        world = World(0)
        source = experiment()
        source["times"] = tuple(source["times"])
        validated = world.validate(source)
        self.assertIsInstance(validated["times"], list)
        self.assertEqual(world.cost(source), 1)
        original = copy.deepcopy(validated)
        validated["heaters"][0]["power"] = 0
        self.assertEqual(world.validate(source), original)
        invalid_fields = {
            "times": [[], [1.0, 1.0], [2.0, 1.0], [-0.1], [30.1], [float("nan")],
                      [0.0] * 26, [True], [10**1000], "1,2"],
            "probes": [[0.2, 0.5], [0.2, 0.5, 0.5], [0.04, 0.5, 0.9], [0.2, 0.5, 0.96]],
            "initial_temperature": [-1, 81, float("inf"), True, "20", None],
            "boundary_temperatures": [[20], [20, 20, 20], [20, float("nan")]],
            "ambient_temperature": [-1, 41], "flow": [-1.01, 1.01, False],
            "cooling": [-0.01, 3.01],
            "heaters": [None, [{"position": 0.3, "power": 1.0}],
                        [{"position": 0.3, "power": 1.0, "width": 0.039}],
                        [{"position": 0.3, "power": 1.0, "width": 0.201}],
                        [{"position": 0.3, "power": 8.1, "width": 0.08}],
                        [{"position": 0.3, "power": 7.0, "width": 0.08}] * 2,
                        [{"position": 0.3, "power": 1.0, "width": 0.08}] * 4]}
        for field, invalids in invalid_fields.items():
            for value in invalids:
                bad = copy.deepcopy(source)
                bad[field] = value
                with self.subTest(field=field, value=str(value)[:60]), self.assertRaises(ValueError):
                    world.run(bad)
        for bad in [None, [], dict(source, extra=1), {k: v for k, v in source.items() if k != "flow"}]:
            with self.assertRaises(ValueError):
                world.cost(bad)
        before = world.run(source)
        with self.assertRaises(ValueError):
            world.run(dict(source, flow=2))
        self.assertEqual(world.run(source), before)

    def test_reproducibility_and_independent_noise(self):
        spec = experiment()
        world = World(27)
        clean = world.run(spec)
        self.assertEqual(clean, World(27).run(spec))
        self.assertNotEqual(clean["values"], World(28).run(spec)["values"])
        first = world.run(spec, noise_key="replicate-1")
        self.assertEqual(first, world.run(spec, noise_key="replicate-1"))
        self.assertEqual(first, World(27).run(spec, noise_key="replicate-1"))
        self.assertNotEqual(first["values"], world.run(spec, noise_key="replicate-2")["values"])
        self.assertNotEqual(first["values"], clean["values"])
        for key in [2, [], "a" * 257]:
            with self.assertRaises(ValueError):
                world.run(spec, noise_key=key)
        for seed in [True, -1, 2**63, 1.5, "1"]:
            with self.assertRaises(ValueError):
                World(seed)

    def test_public_private_separation(self):
        first, second = World(71), World(72)
        self.assertEqual(first.describe(), second.describe())
        description = first.describe()
        self.assertEqual(description["scales"], [20.0] * 3)
        self.assertEqual(description["noise_std"], [0.04] * 3)
        for example in description["examples"]:
            first.validate(example)
        result = first.run(experiment(), noise_key="public")
        self.assertEqual(set(result), {"axis", "channels", "values"})
        self.assertEqual(result["channels"], list(CHANNELS))
        self.assertEqual(result["axis"], experiment()["times"])
        self.assertFalse(any(key.startswith("_") for key in description))
        json.dumps(description, allow_nan=False)
        json.dumps(result, allow_nan=False)
        manifest = json.loads((ROOT / "world.json").read_text())
        self.assertEqual(manifest["version"], first.version)
        self.assertEqual(manifest["agent_public_files"], [])

    def test_panels_are_valid_deterministic_and_conditioned(self):
        world = World(11)
        for kind in ("development", "conditions", "interventions"):
            panel = world.panel(9, kind, count=8)
            self.assertEqual(panel, world.panel(9, kind, count=8))
            self.assertEqual(panel, World(999).panel(9, kind, count=8))
            self.assertNotEqual(panel, world.panel(10, kind, count=8))
            for spec in panel:
                self.assertEqual(spec, world.validate(spec))
                self.assertTrue(np.isfinite(world.run(spec)["values"]).all())
        paired = world.panel(9, "interventions", 6)
        expected_fields = ["flow", "cooling", "heaters"]
        for pair, expected in enumerate(expected_fields):
            differences = [key for key in paired[2 * pair] if paired[2 * pair][key] != paired[2 * pair + 1][key]]
            self.assertEqual(differences, [expected])
        for count in [0, 65, True, 1.5]:
            with self.assertRaises(ValueError):
                world.panel(1, "conditions", count)
        with self.assertRaises(ValueError):
            world.panel(-1, "conditions")
        with self.assertRaises(ValueError):
            world.panel(1, "secret")

    def test_baseline_uses_public_records_and_predictor_example(self):
        world = World(4)
        spec = experiment()
        empty = np.asarray(baseline([], spec))
        self.assertEqual(empty.shape, (len(spec["times"]), 3))
        self.assertTrue(np.isfinite(empty).all())
        observation = world.run(spec)
        records = [{"spec": spec, "observation": observation}]
        with mock.patch("env.heat_transport.world.World", side_effect=AssertionError("hidden access")):
            np.testing.assert_allclose(baseline(records, spec), observation["values"], atol=1e-10)
            changed = copy.deepcopy(spec)
            changed.update(times=[0, 0.75, 7.0, 25.0], probes=[0.1, 0.4, 0.9])
            prediction = np.asarray(baseline(records, changed))
            self.assertEqual(prediction.shape, (4, 3))
            self.assertTrue(np.isfinite(prediction).all())
        broken = {"spec": spec, "observation": dict(observation, values=[[float("nan")]])}
        self.assertEqual(baseline([None, {}, broken], spec), empty.tolist())
        with self.assertRaises(ValueError):
            baseline({}, spec)
        location = importlib.util.spec_from_file_location("heat_public_predictor", ROOT / "examples" / "public_predictor.py")
        module = importlib.util.module_from_spec(location)
        location.loader.exec_module(module)
        self.assertEqual(np.shape(module.predict(spec)), (len(spec["times"]), 3))


if __name__ == "__main__":
    unittest.main()

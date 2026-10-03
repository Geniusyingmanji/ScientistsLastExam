"""Probability enumeration, shared-state sampling and interface checks."""

import itertools
import json
import os
from pathlib import Path
import time
import unittest

import numpy as np

from env.field_ecology.baseline import baseline
from env.field_ecology.kernel import Kernel, STRATA, generate
from env.field_ecology.protocol import example, validate_spec
from env.field_ecology.world import World


def enumerate_histories(psi, detection):
    """Independent finite sample-space integration over occupancy and visits."""
    mean = np.zeros(3)
    second = np.zeros((3,3))
    mass = 0.0
    for occupied in (False,True):
        for history in itertools.product((False,True),repeat=len(detection)):
            probability = psi if occupied else 1-psi
            for hit,p in zip(history,detection):
                chance = p if occupied else 0.0
                probability *= chance if hit else 1-chance
            value = np.asarray([history[0],any(history),all(history)],float)
            mass += probability
            mean += probability*value
            second += probability*np.outer(value,value)
    return mean,second-np.outer(mean,mean),mass


class EcologyProbabilityTests(unittest.TestCase):
    def test_exact_history_enumeration_and_variance_bound(self):
        diagnostics = []
        for seed,stratum in zip((74101,74102,74103),STRATA):
            kernel = Kernel(generate(seed,stratum))
            for visits in (["rapid"],["intensive","rapid"],["rapid","rapid","intensive"]):
                spec = validate_spec({"habitat_values":[-1.6,0,1.6],"visits":visits})
                psi,detection = kernel.probabilities(spec)
                computed = kernel.expectations(psi,detection)
                for i,h in enumerate(spec["habitat_values"]):
                    expected,covariance,mass = enumerate_histories(psi[i],detection[i])
                    self.assertAlmostEqual(mass,1,places=14)
                    np.testing.assert_allclose(computed[i],expected,atol=3e-16)
                    self.assertTrue(np.all(np.diag(covariance)/64 <= .0625**2+1e-15))
                    diagnostics.append({"seed":seed,"stratum":stratum,"habitat":h,"visits":visits,
                                        "mean":expected.tolist(),"panel_covariance":(covariance/64).tolist()})
        self.diagnostics = diagnostics
        destination = os.environ.get("SLE_ECOLOGY_ENUMERATION")
        if destination:
            Path(destination).write_text(json.dumps({"enumerated_conditions":27,"results":diagnostics},indent=2)+"\n")

    def test_degenerate_probability_limits_and_shared_occupancy(self):
        psi = np.asarray([0,.3,1.0])
        perfect = np.ones((3,3))
        np.testing.assert_array_equal(Kernel.expectations(psi,perfect),np.column_stack([psi]*3))
        np.testing.assert_array_equal(Kernel.expectations(psi,np.zeros((3,3))),np.zeros((3,3)))
        sampled = Kernel.sample(psi,perfect,np.random.default_rng(75001))
        np.testing.assert_array_equal(sampled[:,0],sampled[:,1])
        np.testing.assert_array_equal(sampled[:,0],sampled[:,2])
        self.assertTrue(0<sampled[1,0]<1)
        self.assertEqual(sampled[0,0],0)
        self.assertEqual(sampled[2,0],1)

    def test_predeclared_monte_carlo_mean_and_covariance(self):
        start = time.monotonic()
        world = World(74102,_operator_stratum="curved_occupancy")
        spec = {"habitat_values":[0.0],"visits":["rapid","rapid","intensive"]}
        psi,detection = world._kernel.probabilities(spec)
        exact,covariance,_ = enumerate_histories(psi[0],detection[0])
        covariance /= 64
        samples = np.asarray([world.run(spec,noise_key="mc-%04d" % i)["values"][0] for i in range(512)])
        error = np.abs(samples.mean(axis=0)-exact)
        covariance_error = np.abs(np.cov(samples,rowvar=False,ddof=1)-covariance)
        self.assertTrue(np.all(error<.014))
        self.assertTrue(np.all(covariance_error<.0005))
        self.assertTrue(np.all(samples[:,2]<=samples[:,0]))
        self.assertTrue(np.all(samples[:,0]<=samples[:,1]))
        np.testing.assert_array_equal(samples*64,np.round(samples*64))
        self.assertLess(time.monotonic()-start,120)
        destination = os.environ.get("SLE_ECOLOGY_MONTE_CARLO")
        if destination:
            Path(destination).write_text(json.dumps({"independent_panels":512,"sites_per_panel":64,
                "habitat":0.0,"visits":spec["visits"],"seed":74102,"stratum":"curved_occupancy",
                "exact_mean":exact.tolist(),"empirical_mean":samples.mean(axis=0).tolist(),
                "maximum_mean_error":float(error.max()),"exact_panel_covariance":covariance.tolist(),
                "empirical_panel_covariance":np.cov(samples,rowvar=False,ddof=1).tolist(),
                "maximum_covariance_error":float(covariance_error.max()),
                "mean_tolerance":.014,"covariance_tolerance":.0005,
                "all_sampled_fractions":samples.tolist(),"wall_seconds":time.monotonic()-start},indent=2)+"\n")


class EcologyPublicTests(unittest.TestCase):
    def test_public_invariance_noise_keys_and_reset(self):
        world = World(74101)
        spec = example()
        clean = world.run(spec)
        observed = world.run(spec,noise_key="a")
        self.assertEqual(observed,world.run(spec,noise_key="a"))
        self.assertNotEqual(observed,world.run(spec,noise_key="b"))
        self.assertEqual(clean,world.run(spec))
        self.assertEqual(set(observed),{"axis","channels","values"})
        for stratum in STRATA:
            self.assertEqual(world.describe(),World(74103,_operator_stratum=stratum).describe())
        single = world.run({"habitat_values":[0.0],"visits":["rapid"]},noise_key="one-visit")
        self.assertEqual(len(set(single["values"][0])),1)
        description = json.dumps(world.describe())
        for private in ("occupancy_intercept","occupancy_curvature","detection_slope","74101"):
            self.assertNotIn(private,description)
        self.assertIn("not additive Gaussian",description)

    def test_validation_panels_and_cost(self):
        world = World(74103)
        invalid = [{}, {"habitat_values":[],"visits":["rapid"]},
                   {"habitat_values":[True],"visits":["rapid"]},
                   {"habitat_values":[float("nan")],"visits":["rapid"]},
                   {"habitat_values":[-1.61],"visits":["rapid"]},
                   {"habitat_values":[0,0],"visits":["rapid"]},
                   {"habitat_values":[0],"visits":[]},
                   {"habitat_values":[0],"visits":["rapid"]*4},
                   {"habitat_values":[0],"visits":["perfect"]},
                   {"habitat_values":[0],"visits":["rapid"],"site_id":1}]
        for spec in invalid:
            with self.assertRaises(ValueError):
                world.validate(spec)
        for kind in ("development","conditions","interventions"):
            panel = world.panel(75101,kind,3)
            self.assertEqual(panel,world.panel(75101,kind,3))
            for spec in panel:
                self.assertEqual(world.validate(spec),spec)
        self.assertEqual(world.cost({"habitat_values":np.linspace(-1.6,1.6,24).tolist(),"visits":["intensive"]*3}),148)
        for noise_key in (1,True,[],"x"*257):
            with self.assertRaises(ValueError):
                world.run(example(),noise_key=noise_key)

    def test_public_baseline(self):
        world = World(74103)
        spec = example()
        prediction = baseline([],spec)
        self.assertEqual(np.asarray(prediction).shape,(5,3))
        record = {"spec":spec,"observation":world.run(spec,noise_key="baseline")}
        self.assertEqual(baseline([record],spec),record["observation"]["values"])
        other = {"habitat_values":[0.0],"visits":["intensive"]}
        self.assertEqual(baseline([record],other),[[.5,.5,.5]])


if __name__ == "__main__":
    unittest.main()

"""Bounded independent numerical checks for the synthetic phase laboratory."""
import copy
import json
import math
import unittest
import numpy as np
from scipy.integrate import quad, solve_ivp
from scipy.optimize import linprog
from env.phase_equilibria.kernel import Kernel, STRUCTURES, gaussian_pattern, generate
from env.phase_equilibria.protocol import describe, example
from env.phase_equilibria.world import World, baseline


class PhaseEquilibriaTests(unittest.TestCase):
    def test_mass_balance_and_convex_energy(self):
        largest_mass_error, largest_energy_error = 0., 0.
        for seed in (71, 72, 73):
            for structure in STRUCTURES:
                kernel = Kernel(generate(seed, structure))
                p = kernel.p
                for x in np.linspace(0, 1, 11):
                    for preparation in ('quenched', 'powder_blend'):
                        weights, amorphous = kernel.populations(x, 13., preparation)
                        largest_mass_error = max(largest_mass_error,
                                                 abs(weights.sum()+amorphous-1),
                                                 abs(weights.dot(p['compositions'])+amorphous*x-x))
                        self.assertTrue(np.all(weights >= -1e-15))
                        self.assertGreaterEqual(amorphous, 0)
                # Independently optimize mass and composition constraints, not the adjacent-pair formula.
                for x in (.03, .25, .57, .94):
                    optimum = linprog(p['energies'], A_eq=np.vstack([np.ones(len(p['compositions'])), p['compositions']]),
                                      b_eq=[1, x], bounds=(0, None), method='highs')
                    self.assertTrue(optimum.success)
                    error = abs(kernel.equilibrium_weights(x).dot(p['energies'])-optimum.fun)
                    largest_energy_error = max(largest_energy_error, error)
        # Dense composition check on one prespecified fixture.
        kernel = Kernel(generate(71, 'two_intermediates'))
        for x in np.linspace(0, 1, 101):
            weights = kernel.equilibrium_weights(x)
            self.assertAlmostEqual(weights.sum(), 1, places=14)
            self.assertAlmostEqual(weights.dot(kernel.p['compositions']), x, places=14)
        self.assertLess(largest_mass_error, 1e-14)
        self.assertLess(largest_energy_error, 1e-12)
        print(json.dumps({'check': 'conserved_mixture_vs_linear_program', 'max_mass_error': largest_mass_error,
                          'max_energy_error': largest_energy_error, 'linear_programs': 36}))

    def test_relaxation_against_independent_ode(self):
        kernel = Kernel(generate(72, 'one_intermediate'))
        x, target_times = .47, np.linspace(0, 120, 31)
        rates = np.array(kernel.rates(x))
        solution = solve_ivp(lambda t, y: -rates*y, [0, 120], [1., 1.], t_eval=target_times,
                             rtol=2e-11, atol=2e-13, method='DOP853')
        self.assertTrue(solution.success)
        weight = kernel.p['slow_weight']
        independent = (1-weight)*solution.y[0]+weight*solution.y[1]
        analytic = np.array([kernel.residual_fraction(x, t) for t in target_times])
        error = float(np.max(np.abs(independent-analytic)))
        self.assertLess(error, 2e-10)
        self.assertTrue(np.all(np.diff(analytic) <= 0))
        self.assertGreater(analytic[-1], 0.)
        print(json.dumps({'check': 'relaxation_vs_DOP853', 'max_fraction_error': error,
                          'ode_integrations': 1, 'finite_time_residual': float(analytic[-1])}))

    def test_peak_integral_reference(self):
        centers, widths, heights = np.array([25., 57.]), np.array([.5, .9]), np.array([.4, .8])
        numerical, error = quad(lambda angle: float(gaussian_pattern([angle], centers, heights, widths)[0]),
                                10, 90, points=[25, 57], epsabs=1e-11)
        expected = math.sqrt(2*math.pi)*float(heights.dot(widths))
        self.assertLess(abs(numerical-expected), 1e-10)
        print(json.dumps({'check': 'Gaussian_area_vs_quadrature', 'area_error': abs(numerical-expected),
                          'quad_error_estimate': error, 'quadratures': 1}))

    def test_endpoint_and_time_zero_limits(self):
        kernel = Kernel(generate(73, 'two_intermediates'))
        for x in (0., 1.):
            initial, _ = kernel.populations(x, 0, 'powder_blend')
            final, _ = kernel.populations(x, 120, 'powder_blend')
            np.testing.assert_allclose(initial, final, atol=1e-15)
        weights, amorphous = kernel.populations(.4, 0, 'quenched')
        np.testing.assert_array_equal(weights, np.zeros(len(weights)))
        self.assertEqual(amorphous, 1.)
        weights, amorphous = kernel.populations(.4, 0, 'powder_blend')
        self.assertEqual(amorphous, 0.)
        np.testing.assert_allclose(weights, [.6, 0., 0., .4], atol=1e-15)

    def test_measurement_noise_resolution_and_loading(self):
        world = World(71)
        spec = world.validate(example())
        obs = world.run(spec)
        clean = np.array(obs['values'])
        dense = dict(spec, angles_deg=np.linspace(10, 90, 241).tolist())
        np.testing.assert_array_equal(clean, np.array(world.run(dense)['values'])[::3])
        empty = np.array(world.run(dict(spec, loading=0))['values'])
        half = np.array(world.run(dict(spec, loading=.5))['values'])
        np.testing.assert_allclose(half, (clean+empty)/2, atol=1e-15)
        self.assertEqual(world.run(spec, noise_key='rep-1'), world.run(spec, noise_key='rep-1'))
        self.assertNotEqual(world.run(spec, noise_key='rep-1'), world.run(spec, noise_key='rep-2'))
        self.assertEqual(world.run(spec), obs)
        self.assertNotEqual(world.run(spec, noise_key='rep-1'), obs)
        other_blank = world.run(dict(spec, loading=0, composition=.99, hold_time=120, preparation='quenched'))
        np.testing.assert_array_equal(other_blank['values'], empty)
        # No clipping: use enough independent cell readouts to test the stated scale, not exact RNG output.
        noise = []
        for i in range(12):
            noise.extend((np.array(world.run(dense, noise_key='variance-%d' % i)['values'])-
                          np.array(world.run(dense)['values'])).ravel())
        self.assertLess(abs(np.mean(noise)), .0003)
        self.assertTrue(.0027 < np.std(noise) < .0033)
        print(json.dumps({'check': 'noise_cells', 'cells': len(noise), 'mean': float(np.mean(noise)),
                          'standard_deviation': float(np.std(noise))}))

    def test_validation_contract_baseline_and_panels(self):
        world = World(71)
        self.assertEqual(world.describe(), World(73, _operator_stratum='two_intermediates').describe())
        description = json.dumps(describe())
        for forbidden in ('tau_fast', 'tau_slow', 'rate_curve', 'one_intermediate', 'energies'):
            self.assertNotIn(forbidden, description)
        spec = world.validate(example())
        self.assertEqual(spec, world.validate(spec))
        obs = world.run(spec)
        records = [{'spec': spec, 'observation': obs}]
        self.assertEqual(baseline(records, spec), obs['values'])
        self.assertEqual(np.asarray(baseline([], spec)).shape, (81, 1))
        malformed = [dict(spec, composition=True), dict(spec, hold_time=float('nan')),
                     dict(spec, angles_deg=[10, 10]), dict(spec, angles_deg=[]),
                     dict(spec, preparation='unknown'), dict(spec, loading=1.01),
                     dict(spec, private_seed=1), dict(spec, angles_deg=list(np.linspace(10, 90, 242)))]
        for bad in malformed:
            with self.assertRaises(ValueError):
                world.run(bad)
        with self.assertRaises(ValueError):
            World(True)
        with self.assertRaises(ValueError):
            world.run(spec, noise_key=0)
        bad_record = copy.deepcopy(records)
        bad_record[0]['observation']['values'][0][0] = float('inf')
        with self.assertRaises(ValueError):
            baseline(bad_record, spec)
        for kind in ('development', 'conditions', 'interventions'):
            panel = world.panel(101, kind, 3)
            self.assertEqual(panel, world.panel(101, kind, 3))
            for query in panel:
                self.assertEqual(query, world.validate(query))
                values = np.array(world.run(query)['values'])
                self.assertTrue(np.isfinite(values).all())
                self.assertEqual(values.shape, (161, 1))
        extreme = dict(spec, angles_deg=np.linspace(10, 90, 241).tolist(), hold_time=120)
        self.assertEqual(world.cost(extreme), 51)
        self.assertTrue(np.isfinite(world.run(extreme)['values']).all())


if __name__ == '__main__':
    unittest.main()

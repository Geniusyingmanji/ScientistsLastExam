"""Independent loss, assumption-routing, exact-randomization and FWER checks."""
import json
import math
from pathlib import Path
import unittest
from unittest.mock import patch

import numpy as np

from env import claim_protocol_diagnostics as diagnostic


class FutureClaimDiagnosticsTest(unittest.TestCase):
    def test_raw_loss_is_not_display_transform_or_significance_filter(self):
        self.assertEqual(diagnostic.raw_interval_loss([-1., 1.], 0.), 2.)
        self.assertEqual(diagnostic.raw_interval_loss([-1., 1.], 2.), 22.)
        self.assertEqual(diagnostic.raw_interval_loss([-2., 2.], 4., scale=2.), 22.)
        for args in (([1, -1], 0), ([0, 1], float('nan')), ([True, 1], 0)):
            with self.assertRaises(ValueError):
                diagnostic.raw_interval_loss(*args)

    def evidence(self, treatment, **kwargs):
        settings = dict(noise_model='gaussian', sigma_control=1., sigma_treatment=1., method='sign_flip')
        settings.update(kwargs)
        return diagnostic.slot_evidence([0.] * 8, treatment, **settings)

    def test_sign_flip_exact_small_support_zero_and_ties(self):
        self.assertEqual(self.evidence([1.] * 8)['raw_p_value'], 2 / 256)
        self.assertEqual(self.evidence([0.] * 8)['raw_p_value'], 1.)
        self.assertEqual(self.evidence([1.] + [0.] * 7)['raw_p_value'], 1.)
        x = [1., .2, -.1, 2., 3., -.4, 1.2, .9]
        p = self.evidence(x)['raw_p_value']
        self.assertEqual(self.evidence([-v for v in x])['raw_p_value'], p)
        self.assertEqual(self.evidence([100 * v for v in x])['raw_p_value'], p)

    def test_exact_conditional_null_superuniform_over_every_sign_assignment(self):
        # Includes a clipped point mass. Enumerate the null law independently.
        import itertools
        magnitude = np.array([0., 0., .2, .4, .7, .8, 1.1, 1.5])
        all_rows = np.array([magnitude * sign for sign in itertools.product([-1, 1], repeat=8)])
        p = diagnostic._sign_flip_many(all_rows)
        for cutoff in (.0078125, .01666666667, .025, .05, .1, .5, 1.):
            self.assertLessEqual(float(np.mean(p <= cutoff)), cutoff + 1e-12)

    def test_gaussian_known_sigma_and_conservative_bound(self):
        exact = self.evidence([1.] * 8, method='known_gaussian')['raw_p_value']
        self.assertAlmostEqual(exact, 0.04550026389635844)
        conservative = self.evidence([1.] * 8, method='gaussian_lipschitz')['raw_p_value']
        self.assertAlmostEqual(conservative, 2 * math.exp(-2))
        self.assertGreaterEqual(conservative, exact)
        self.assertEqual(self.evidence([1.] * 8, method='gaussian_lipschitz', noise_model='zero_clipped_gaussian')['raw_p_value'], conservative)

    def test_invalid_noise_assumptions_do_not_fall_back_to_t_or_normal(self):
        for settings in (dict(method='known_gaussian', noise_model='zero_clipped_gaussian'),
                         dict(method='sign_flip', sigma_treatment=2.),
                         dict(noise_model='unknown'), dict(method='student_t'),
                         dict(sigma_control=0.), dict(sigma_treatment=True)):
            with self.assertRaises(ValueError):
                self.evidence([1.] * 8, **settings)
        with self.assertRaises(ValueError):
            self.evidence([-1.] * 8, noise_model='zero_clipped_gaussian')
        with self.assertRaises(ValueError):
            self.evidence([1.] * 7)

    def test_holm_three_slots_keeps_missing_slots_and_stepdown(self):
        self.assertEqual(diagnostic.holm_three_slots([])['rejected'], [False] * 3)
        one = diagnostic.holm_three_slots([.02])
        self.assertEqual(one['raw_p_values_padded'], [.02, 1., 1.])
        self.assertEqual(one['holm_adjusted_p_values'], [.06, 1., 1.])
        self.assertEqual(one['rejected'], [False] * 3)
        full = diagnostic.holm_three_slots([.03, .01, .02])
        np.testing.assert_allclose(full['holm_adjusted_p_values'], [.04, .03, .04])
        self.assertEqual(full['rejected'], [True] * 3)
        self.assertEqual(diagnostic.holm_three_slots([.001, .03, .04])['rejected'], [True, False, False])
        for p in ([.01] * 4, [float('nan')], [-.1], [True]):
            with self.assertRaises(ValueError):
                diagnostic.holm_three_slots(p)

    def test_holm_perfect_dependence_on_uniform_null(self):
        # A deterministic grid, no independence assumption among the slots.
        u = (np.arange(6000) + .5) / 6000
        p = np.repeat(u[:, None], 3, axis=1)
        adj = diagnostic._holm_many(p)
        self.assertLessEqual(float(np.mean(np.any(adj <= .05, axis=1))), .05)
        for row in ([.04, .01, .02], [.01, 1., 1.]):
            np.testing.assert_allclose(diagnostic._holm_many(np.array([row]))[0], diagnostic.holm_three_slots(row)['holm_adjusted_p_values'])

    def test_finite_simulation_replays_and_accounts_cells(self):
        a = diagnostic.development_calibration(episodes=8, seed=17)
        b = diagnostic.development_calibration(episodes=8, seed=17)
        self.assertEqual(a['cells'], b['cells'])
        self.assertEqual(a['gaussian_interval_loss_fixed_grid'], b['gaussian_interval_loss_fixed_grid'])
        self.assertEqual(a['planned_cells'], a['completed_cells'])
        self.assertEqual(a['completed_cells'], 16)
        self.assertEqual(a['failures'], [])
        for cell in a['cells']:
            null_slots = 2 if cell['selection'] == 'two_null_one_alternative' else 3
            self.assertEqual(cell['methods']['sign_flip']['null_slot_rejection_at_0.05']['denominator'], 8 * null_slots)
            if cell['noise_model'] == 'zero_clipped_gaussian':
                self.assertNotIn('known_gaussian', cell['methods'])
        self.assertLess(a['gaussian_interval_loss_fixed_grid'][1]['analytic_expected_raw_loss'], a['gaussian_interval_loss_fixed_grid'][0]['analytic_expected_raw_loss'])
        self.assertLess(a['gaussian_interval_loss_fixed_grid'][1]['analytic_expected_raw_loss'], a['gaussian_interval_loss_fixed_grid'][2]['analytic_expected_raw_loss'])
        json.dumps(a, allow_nan=False)

    def test_failures_retained_and_run_size_bounded(self):
        with patch.object(diagnostic, '_cell', side_effect=RuntimeError('deliberate test failure')):
            result = diagnostic.development_calibration(episodes=1)
        self.assertEqual(result['status'], 'completed_with_failures')
        self.assertEqual(len(result['failures']), 16)
        self.assertEqual(result['completed_cells'], 0)
        for count in (True, 0, 10001):
            with self.assertRaises(ValueError):
                diagnostic.development_calibration(episodes=count)

    def test_diagnostic_has_no_pilot_or_world_import(self):
        import ast
        tree = ast.parse(Path(diagnostic.__file__).read_text())
        imports = [n.module or '' for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
        self.assertFalse(any('scoring' in name or 'world' in name or 'runner' in name for name in imports))


if __name__ == '__main__':
    unittest.main()

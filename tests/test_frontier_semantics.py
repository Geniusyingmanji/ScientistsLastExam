"""Schema-only alias counterexamples: no simulators, hidden parameters or API."""
import copy
import json
import unittest
from env.frontier_semantics import eligible_target, readout_key


class FrontierReadoutTests(unittest.TestCase):
    def test_molecular_batch_reordering_and_extension(self):
        a = [[0., 0., 0.], [3., 0., 0.], [0., 3., 0.]]
        b = [[0., 0., 0.], [3.2, 0., 0.], [0., 3.2, 0.]]
        first = {'configuration_ids': [0], 'configurations': [a], 'temperature_k': 450.}
        second = {'configuration_ids': [0, 1], 'configurations': [b, a], 'temperature_k': 450.}
        key = readout_key('molecular_forces', first, 0, 'energy_ev')
        self.assertEqual(key, readout_key('molecular_forces', second, 1, 'energy_ev'))
        self.assertNotEqual(key, readout_key('molecular_forces', second, 0, 'energy_ev'))
        self.assertNotEqual(key, readout_key('molecular_forces', dict(first, temperature_k=600), 0, 'energy_ev'))
        self.assertTrue(eligible_target('molecular_forces', first, 0, 'energy_ev'))

    def test_climate_future_forcing_and_sampling_alias(self):
        first = {'times_years': [1, 5, 10], 'forcing_w_m2': [4.]*10}
        longer = {'times_years': [5, 12], 'forcing_w_m2': [4.]*10+[0., 0.]}
        key = readout_key('climate_response', first, 1, 'surface_temperature_anomaly_k')
        self.assertEqual(key, readout_key('climate_response', longer, 0, 'surface_temperature_anomaly_k'))
        altered = copy.deepcopy(longer)
        altered['forcing_w_m2'][4] = 3.
        self.assertNotEqual(key, readout_key('climate_response', altered, 0, 'surface_temperature_anomaly_k'))

    def test_catalyst_prefix_and_calibration_clock(self):
        reaction = {'kind': 'reaction', 'coupon_id': 'A', 'temperature_k': 500., 'feed_concentration': 1., 'duration_min': 2.}
        first = {'event_indices': [1, 2], 'events': [reaction, {'kind': 'standard'}]}
        longer = {'event_indices': [1, 2, 3], 'events': [reaction, {'kind': 'standard'}, {'kind': 'blank'}]}
        key = readout_key('catalyst_aging', first, 0, 'measured_signal')
        self.assertEqual(key, readout_key('catalyst_aging', longer, 0, 'measured_signal'))
        altered = copy.deepcopy(first)
        altered['events'][0]['duration_min'] = 3.
        self.assertNotEqual(key, readout_key('catalyst_aging', altered, 0, 'measured_signal'))
        self.assertEqual(readout_key('catalyst_aging', first, 1, 'measured_signal'),
                         readout_key('catalyst_aging', altered, 1, 'measured_signal'))
        self.assertNotEqual(readout_key('catalyst_aging', first, 1, 'measured_signal'),
                            readout_key('catalyst_aging', {'event_indices': [1], 'events': [{'kind': 'standard'}]}, 0, 'measured_signal'))
        self.assertFalse(eligible_target('catalyst_aging', longer, 2, 'measured_signal'))
        self.assertTrue(eligible_target('catalyst_aging', first, 1, 'measured_signal'))

    def test_field_visit_semantics_and_habitat_batch(self):
        first = {'habitat_values': [0.], 'visits': ['rapid', 'intensive']}
        bigger = {'habitat_values': [-1., 0., 1.], 'visits': ['rapid', 'rapid', 'intensive']}
        key = readout_key('field_ecology', first, 0, 'first_visit_detection')
        self.assertEqual(key, readout_key('field_ecology', bigger, 1, 'first_visit_detection'))
        permuted = dict(first, visits=['intensive', 'rapid'])
        self.assertNotEqual(key, readout_key('field_ecology', permuted, 0, 'first_visit_detection'))
        for channel in ('any_visit_detection', 'all_visits_detection'):
            self.assertEqual(readout_key('field_ecology', first, 0, channel), readout_key('field_ecology', permuted, 0, channel))
            self.assertNotEqual(readout_key('field_ecology', first, 0, channel), readout_key('field_ecology', bigger, 1, channel))
        one = dict(first, visits=['rapid'])
        self.assertEqual(key, readout_key('field_ecology', one, 0, 'any_visit_detection'))
        self.assertEqual(key, readout_key('field_ecology', one, 0, 'all_visits_detection'))
        self.assertTrue(eligible_target('field_ecology', one, 0, 'first_visit_detection'))

    def test_phase_blank_alias_and_measured_preparation(self):
        first = {'composition': .2, 'hold_time': 0., 'preparation': 'powder_blend', 'loading': 0., 'angles_deg': [20., 30.]}
        changed = dict(first, composition=.8, hold_time=120., preparation='quenched', angles_deg=[30.])
        self.assertEqual(readout_key('phase_equilibria', first, 1, 'intensity'), readout_key('phase_equilibria', changed, 0, 'intensity'))
        self.assertFalse(eligible_target('phase_equilibria', first, 0, 'intensity'))
        loaded = dict(first, loading=1.)
        self.assertTrue(eligible_target('phase_equilibria', loaded, 0, 'intensity'))
        self.assertNotEqual(readout_key('phase_equilibria', loaded, 0, 'intensity'),
                            readout_key('phase_equilibria', dict(loaded, composition=.3), 0, 'intensity'))
        self.assertNotEqual(readout_key('phase_equilibria', loaded, 0, 'intensity'),
                            readout_key('phase_equilibria', dict(loaded, preparation='quenched'), 0, 'intensity'))

    def test_fail_closed_and_detached_keys(self):
        spec = {'event_indices': [1], 'events': [{'kind': 'reaction', 'coupon_id': 'A', 'temperature_k': 500., 'feed_concentration': 1., 'duration_min': 2.}]}
        key = readout_key('catalyst_aging', spec, 0, 'measured_signal')
        json.dumps(key, allow_nan=False)
        key['controls']['event_prefix'][0]['temperature_k'] = 600.
        self.assertEqual(spec['events'][0]['temperature_k'], 500.)
        for args in [('unknown', spec, 0, 'measured_signal'), ('catalyst_aging', spec, True, 'measured_signal'),
                     ('catalyst_aging', spec, 2, 'measured_signal'), ('catalyst_aging', spec, 0, 'unknown')]:
            with self.assertRaises(ValueError):
                readout_key(*args)


if __name__ == '__main__':
    unittest.main()

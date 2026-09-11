"""Independent expected-count and noiseless inverse checks for the adaptive witness."""
import copy
import importlib.util
from pathlib import Path
import numpy as np
import pytest

TASK = Path(__file__).resolve().parents[1]/'benchmarks/Physics/DarkMatterRecoilAttribution'


def load(name):
    spec = importlib.util.spec_from_file_location(name, TASK/'verification'/(name+'.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ORACLE, REFERENCE = load('evaluator'), load('reference_profile')


@pytest.mark.parametrize('kind,power', [('contact', 0), ('q2', 2)])
def test_reference_expected_counts_match_independent_oracle(kind, power):
    world = ORACLE.make_world(184, kind)
    x = np.r_[np.log(world['mass']), world['ratio'], world['weights'], world['background'], world['gain']]
    prediction = REFERENCE.unit_means(world['problem'], x, power)
    np.testing.assert_allclose(prediction[:, :18], world['rates'], rtol=1e-13)
    background = ORACLE.bin_widths(world['energy'])*(world['background'][:, None]*np.exp(-world['energy']/32)+1.5)
    np.testing.assert_allclose(prediction[:, 18:36], 8*world['gain'][:, None]*background, rtol=1e-13)
    np.testing.assert_allclose(prediction[:, 36], 100*world['gain'])


@pytest.mark.parametrize('kind,power', [('contact', 0), ('q2', 2)])
def test_adaptive_reference_recovers_noiseless_mass_with_charged_pilot(kind, power):
    world = ORACLE.make_world(184, kind)
    x = np.r_[np.log(world['mass']), world['ratio'], world['weights'], world['background'], world['gain']]
    mean = REFERENCE.unit_means(world['problem'], x, power)
    requests = []
    def expected_experiment(request):
        requests.append(dict(request))
        target, units = request['target'], request['units']
        assert type(units) is int and units > 0
        assert sum(r['units'] for r in requests) <= 12
        return dict(target=target, units=units, counts=(units*mean[target, :18]).tolist(),
                    background_counts=(units*mean[target, 18:36]).tolist(),
                    calibration_counts=float(units*mean[target, 36]))
    answer = REFERENCE.infer_recoil(copy.deepcopy(world['problem']), expected_experiment)
    assert requests[:3] == [{'target': t, 'units': 1} for t in range(3)]
    assert sum(r['units'] for r in requests) == 12
    ORACLE.validate(answer)
    observations = []
    for target in range(3):
        units = sum(r['units'] for r in requests if r['target'] == target)
        observations.append(dict(units=units, counts=units*mean[target, :18],
                                 background_counts=units*mean[target, 18:36],
                                 calibration_counts=units*mean[target, 36]))
    fits, _ = REFERENCE.fit_observations(world['problem'], observations)
    assert fits[0][1] == kind
    assert np.exp(fits[0][2][0]) == pytest.approx(world['mass'], rel=1e-3)
    if answer.get('abstain'):
        # Expected counts remove sampling error, not finite-exposure uncertainty:
        # a near-equivalent other law may still fail the stated evidence threshold.
        assert min(f[0] for f in fits if f[1] != kind)-fits[0][0] < 6
    else:
        assert answer['model'] == kind
        assert answer['mass_gev'] == pytest.approx(world['mass'], rel=1e-3)

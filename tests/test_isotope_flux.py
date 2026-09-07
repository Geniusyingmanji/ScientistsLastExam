"""Independent model checks for the second biology wave."""
import importlib.util
import itertools
from pathlib import Path
import numpy as np
import pytest
ROOT = Path(__file__).resolve().parents[1]

def module(name):
    path = ROOT / 'benchmarks/Biology' / name / 'verification/evaluator.py'
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

@pytest.mark.parametrize('bad', [None, [], {}, {'abstain': True}, {'abstain': 1, 'fluxes': {}, 'confidence': 0.5}, {'abstain': False, 'fluxes': {}, 'confidence': 0.5}, {'abstain': True, 'fluxes': {}, 'confidence': float('inf')}, {'abstain': False, 'fluxes': {'net': True, 'exchange_total': 1}, 'confidence': 0.5}, {'abstain': False, 'fluxes': {'net': [1], 'exchange_total': 1}, 'confidence': 0.5}, {'abstain': False, 'fluxes': {'net': 2, 'exchange_total': 1}, 'confidence': 0.5}, {'abstain': False, 'fluxes': {'net': 1, 'exchange_total': -1}, 'confidence': 0.5}, {'abstain': False, 'fluxes': {'net': 1, 'exchange_total': 1, 'x1': 0.5}, 'confidence': 0.5}])
def test_isotope_bad(bad):
    assert module('IsotopeFluxIdentifiability')._parse(bad) is None

def test_isotope_reduced_mass_balance_and_conservation():
    from scipy.integrate import solve_ivp
    m = module('IsotopeFluxIdentifiability')
    p = m._problem()
    v, x = (0.35, 0.8)

    def rhs(t, y):
        q = 1 - np.exp(-2 * v * t)
        source = np.array([(1 - q) ** 2, 2 * q * (1 - q), q * q])
        return np.r_[(v * source + x * y[3:] - (v + x) * y[:3]) / 1.5, (v + x) * (y[:3] - y[3:]) / 2]
    times = p['sampling_times']
    independent = solve_ivp(rhs, (0, 16), [1, 0, 0, 1, 0, 0], t_eval=times, rtol=1e-10, atol=1e-12).y.T.reshape(-1, 2, 3)
    full = m.isotopomers(p, v, x, 1, times)
    assert np.all(full >= -1e-09) and np.allclose(full.sum(axis=2), 1)
    assert np.allclose(m.distributions(p, v, x, 1, times), independent, atol=2e-08)
    for x1 in [0, 0.1, 0.8]:
        flux = [2 * v, v, v + x, x1, x - x1, v]
        assert np.allclose(np.array(p['stoichiometry']) @ flux, 0)
    assert np.allclose(m.distributions(p, 0, 0, 1, times), m.distributions(p, 0, 2, 1, times))

def test_isotope_reference_and_budget():
    m = module('IsotopeFluxIdentifiability')
    out = m.reference(m._problem(), m._Lab(0))
    assert not out['abstain'] and m._mechanism(0, out) > 0.5
    assert m.reference(m._problem(), m._Lab(1))['abstain']
    lab = m._Lab(0)
    lab('full', list(range(6)))
    with pytest.raises(RuntimeError):
        lab('full', [0])
    assert lab.violated
    assert m.evaluate(lambda p, t: dict(abstain=True, fluxes={}, confidence=0.5))['combined_score'] == 0

@pytest.mark.parametrize('name', ['IsotopeFluxIdentifiability'])
def test_discovery_all_claims_without_evidence_do_not_earn_refusal(name):
    m = module(name)
    if name == 'SingleMoleculeKinetics':
        output = dict(abstain=False, rates=[1, 1], efficiencies=[0.5, 0.5], confidence=1.0)
    else:
        output = dict(abstain=False, fluxes=dict(net=0.0, exchange_total=0.0), confidence=1.0)
    result = m.evaluate(lambda p, lab: output)
    assert result['development_correct_refusal_rate'] == 0
    assert result['development_false_discovery_count'] > 0
    assert result['development_claim_count'] > result['development_false_discovery_count']
    assert result['combined_score'] == 0

def test_isotope_caught_overbudget_and_unsorted_queries():
    m = module('IsotopeFluxIdentifiability')

    def caught(p, trace):
        trace('full', list(range(6)))
        try:
            trace('half', [0])
        except RuntimeError:
            pass
        return dict(abstain=True, fluxes={}, confidence=0.5)
    result = m.evaluate(caught)
    assert result['valid'] == 0 and result['combined_score'] == 0
    a = m._Lab(0)('full', [2, 0, 1])
    b = m._Lab(0)('full', [0, 1, 2])
    assert a['counts'] == [b['counts'][2], b['counts'][0], b['counts'][1]]

@pytest.mark.parametrize('name', ['IsotopeFluxIdentifiability'])
def test_wave2_subprocess_determinism(name):
    import os, subprocess, sys
    script = "import importlib.util,json\nfrom pathlib import Path\nname=NAME\np=Path('benchmarks/Biology')/name\ndef load(path):\n s=importlib.util.spec_from_file_location('loaded',path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m\nm=load(p/'verification/evaluator.py');b=load(p/'solution.py')\nentry=(p/'frontier_eval/entrypoint.txt').read_text().strip()\nprint(json.dumps(m.evaluate(getattr(b,entry)),sort_keys=True,allow_nan=False))\n".replace('NAME', repr(name))
    outputs = [subprocess.check_output([sys.executable, '-c', script], cwd=ROOT, env={**os.environ, 'PYTHONHASHSEED': str(seed), 'OPENBLAS_NUM_THREADS': '1'}, text=True) for seed in (1, 7)]
    assert outputs[0] == outputs[1]

@pytest.mark.parametrize('name', ['IsotopeFluxIdentifiability'])
def test_reference_calibration_and_legal_zero_baseline(name):
    m = module(name)

    def load_file(filename):
        spec = importlib.util.spec_from_file_location('calibration_candidate', ROOT / 'benchmarks/Biology' / name / filename)
        candidate = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(candidate)
        return candidate
    entry = (ROOT / 'benchmarks/Biology' / name / 'frontier_eval/entrypoint.txt').read_text().strip()
    baseline = m.evaluate(getattr(load_file('solution.py'), entry))
    reference = m.evaluate(getattr(load_file('references/reference.py'), entry))
    assert baseline['valid'] == reference['valid'] == 1
    assert baseline['combined_score'] == 0
    assert 0.5 <= reference['combined_score'] <= 0.8

def test_precision_endpoints_and_geometry_perfect_witness():
    isotope = module('IsotopeFluxIdentifiability')
    v, x = isotope.SPECS[0]
    assert isotope._mechanism(0, dict(fluxes=dict(net=v, exchange_total=x))) == 1
    assert isotope._mechanism(0, dict(fluxes=dict(net=v * 1.025, exchange_total=x * 1.025))) == pytest.approx(0, abs=1e-12)

@pytest.mark.parametrize('name,values,keys', [('IsotopeFluxIdentifiability', ('full', [0]), ('tracer_id', 'time_ids'))])
@pytest.mark.parametrize('bad_call', ['missing', 'extra', 'unknown', 'duplicate'])
def test_caught_callback_binding_errors_permanently_invalidate(name, values, keys, bad_call):
    m = module(name)

    def misuse(lab):
        if bad_call == 'missing':
            lab(values[0])
        elif bad_call == 'extra':
            lab(*values, None)
        elif bad_call == 'unknown':
            lab(unexpected_keyword=True)
        else:
            lab(*values, **{keys[0]: values[0]})
    lab = m._Lab(0)
    with pytest.raises(TypeError):
        misuse(lab)
    assert lab.violated and lab.spent == lab.calls == 0

    def caught(problem, callback):
        try:
            misuse(callback)
        except TypeError:
            pass
        callback(**dict(zip(keys, values)))
        if name == 'SingleMoleculeKinetics':
            return dict(abstain=True, rates=[], efficiencies=[], confidence=0.5)
        return dict(abstain=True, fluxes={}, confidence=0.5)
    result = m.evaluate(caught)
    assert result['valid'] == result['combined_score'] == 0
    assert all((not row['valid'] for row in result['per_world']))

@pytest.mark.parametrize('name,values,keys', [('IsotopeFluxIdentifiability', ('full', [2, 0, 1]), ('tracer_id', 'time_ids'))])
def test_callback_keyword_and_mixed_arguments_preserve_observations(name, values, keys):
    m = module(name)
    positional, keyword, mixed = [m._Lab(0) for _ in range(3)]
    expected = positional(*values)
    assert keyword(**dict(zip(keys, values))) == expected
    assert mixed(values[0], **{keys[1]: values[1]}) == expected
    assert not any((lab.violated for lab in (positional, keyword, mixed)))

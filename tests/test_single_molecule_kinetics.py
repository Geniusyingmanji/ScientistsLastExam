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

@pytest.mark.parametrize('bad', [None, [], {}, {'abstain': True}, {'abstain': 1, 'rates': [], 'efficiencies': [], 'confidence': 0.5}, {'abstain': True, 'rates': [1, 1], 'efficiencies': [], 'confidence': 0.5}, {'abstain': False, 'rates': [1, 1], 'efficiencies': [0.2, 0.8], 'confidence': float('nan')}, {'abstain': False, 'rates': [[1], [1]], 'efficiencies': [0.2, 0.8], 'confidence': 0.5}, {'abstain': False, 'rates': [True, 1], 'efficiencies': [0.2, 0.8], 'confidence': 0.5}, {'abstain': False, 'rates': [0, 1], 'efficiencies': [0.2, 0.8], 'confidence': 0.5}, {'abstain': False, 'rates': [1, 1], 'efficiencies': [0.2, 2], 'confidence': 0.5}, {'abstain': True, 'rates': [], 'efficiencies': [], 'confidence': 2}])
def test_kinetics_bad(bad):
    assert module('SingleMoleculeKinetics')._parse(bad) is None

def test_kinetics_transition_and_label_symmetry():
    m = module('SingleMoleculeKinetics')
    a, b, dt = (0.7, 1.4, 0.2)
    off = a / (a + b) * (1 - np.exp(-(a + b) * dt))
    assert m.transition([a, b], dt)[0, 1] == pytest.approx(off)
    assert m.transition([a, b], dt).sum(axis=1) == pytest.approx([1, 1])
    o = dict(rates=[a, b], efficiencies=[0.18, 0.78])
    assert m._mechanism(0, o) == 1
    assert m._mechanism(0, dict(rates=[b, a], efficiencies=[0.78, 0.18])) == 1

def test_kinetics_alias_emissions_and_budget():
    m = module('SingleMoleculeKinetics')
    for index in (1, 2):
        assert m.SPECS[index][3:] == (0.5, 0.5)
    lab = m._Lab(0)
    lab(0.4, 400)
    with pytest.raises(RuntimeError):
        lab(0.1, 400)
    assert lab.violated and lab.spent == 1600

    def caught(p, observe):
        for _ in range(2):
            try:
                observe(0.4, 400)
            except RuntimeError:
                pass
        return dict(abstain=True, rates=[], efficiencies=[], confidence=0.5)
    assert m.evaluate(caught)['valid'] == 0
    assert m.evaluate(lambda p, o: dict(abstain=True, rates=[], efficiencies=[], confidence=0.5))['combined_score'] == 0

def test_kinetics_reference_recovers_and_refuses():
    m = module('SingleMoleculeKinetics')
    out = m.reference(m._problem(), m._Lab(0))
    assert not out['abstain'] and m._mechanism(0, out) > 0.65
    assert m.reference(m._problem(), m._Lab(2))['abstain']

@pytest.mark.parametrize('name', ['SingleMoleculeKinetics'])
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

@pytest.mark.parametrize('name', ['SingleMoleculeKinetics'])
def test_wave2_subprocess_determinism(name):
    import os, subprocess, sys
    script = "import importlib.util,json\nfrom pathlib import Path\nname=NAME\np=Path('benchmarks/Biology')/name\ndef load(path):\n s=importlib.util.spec_from_file_location('loaded',path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m\nm=load(p/'verification/evaluator.py');b=load(p/'solution.py')\nentry=(p/'frontier_eval/entrypoint.txt').read_text().strip()\nprint(json.dumps(m.evaluate(getattr(b,entry)),sort_keys=True,allow_nan=False))\n".replace('NAME', repr(name))
    outputs = [subprocess.check_output([sys.executable, '-c', script], cwd=ROOT, env={**os.environ, 'PYTHONHASHSEED': str(seed), 'OPENBLAS_NUM_THREADS': '1'}, text=True) for seed in (1, 7)]
    assert outputs[0] == outputs[1]

@pytest.mark.parametrize('name', ['SingleMoleculeKinetics'])
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
    kinetics = module('SingleMoleculeKinetics')
    _, a, b, e0, e1 = kinetics.SPECS[0]
    exact = dict(rates=[a, b], efficiencies=[e0, e1])
    shifted = dict(rates=[a * np.exp(0.05), b * np.exp(0.05)], efficiencies=[e0, e1])
    assert kinetics._mechanism(0, exact) == 1
    assert kinetics._mechanism(0, shifted) == pytest.approx(0.5)

@pytest.mark.parametrize('name,values,keys', [('SingleMoleculeKinetics', (0.1, 400), ('exposure', 'length'))])
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

@pytest.mark.parametrize('name,values,keys', [('SingleMoleculeKinetics', (0.1, 400), ('exposure', 'length'))])
def test_callback_keyword_and_mixed_arguments_preserve_observations(name, values, keys):
    m = module(name)
    positional, keyword, mixed = [m._Lab(0) for _ in range(3)]
    expected = positional(*values)
    assert keyword(**dict(zip(keys, values))) == expected
    assert mixed(values[0], **{keys[1]: values[1]}) == expected
    assert not any((lab.violated for lab in (positional, keyword, mixed)))

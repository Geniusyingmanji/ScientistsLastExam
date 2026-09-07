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

@pytest.mark.parametrize('bad', [None, [], {}, {'coordinates': None}, {'coordinates': []}, {'coordinates': [[0, 0, 0]]}, {'coordinates': [[0, 0]] * 24}, {'coordinates': [[True, 0, 0]] * 24}, {'coordinates': [[float('nan'), 0, 0]] * 24}, {'coordinates': [[251, 0, 0]] * 24}, {'coordinates': [[[0], 0, 0]] * 24}, {'coordinates': [[0, 0, 0]] * 24, 'loss': 0}])
def test_geometry_bad(bad):
    m = module('ProteinDistanceGeometry')
    p, _ = m._world(0)
    assert m._score_output(0, p, bad) == (0.0, False)

def test_geometry_witness_rigid_invariance_chirality_and_collapse():
    m = module('ProteinDistanceGeometry')
    p, xyz = m._world(0)
    assert m.loss(p, xyz) < 1e-15
    rng = np.random.default_rng(15)
    rotation = np.linalg.qr(rng.normal(size=(3, 3)))[0]
    rotation[:, 0] *= np.linalg.det(rotation)
    assert m.loss(p, xyz @ rotation + [3, 4, 5]) < 1e-15
    mirror = xyz.copy()
    mirror[:, 0] *= -1
    assert m.loss(p, mirror) > 0.1
    assert m.loss(p, xyz * 0.5) > 0.1
    assert m.loss(p, np.zeros_like(xyz)) > 1
    row = p['stereocenters'][0]
    a, b, c, d = xyz[row['atoms']]
    assert row['sign'] * np.linalg.det(np.stack([b - a, c - a, d - a])) / 3.8 ** 3 >= row['minimum_volume']

@pytest.mark.parametrize('name', ['ProteinDistanceGeometry'])
@pytest.mark.parametrize('candidate', ['solution.py', 'references/reference.py'])
def test_wave2_subprocess_determinism(name, candidate):
    import os, subprocess, sys
    script = "import importlib.util,json\nfrom pathlib import Path\nname=NAME\np=Path('benchmarks/Biology')/name\ndef load(path):\n s=importlib.util.spec_from_file_location('loaded',path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m\nm=load(p/'verification/evaluator.py');b=load(p/CANDIDATE)\nentry=(p/'frontier_eval/entrypoint.txt').read_text().strip()\nprint(json.dumps(m.evaluate(getattr(b,entry)),sort_keys=True,allow_nan=False))\n".replace('NAME', repr(name)).replace('CANDIDATE', repr(candidate))
    outputs = [subprocess.check_output([sys.executable, '-c', script], cwd=ROOT, env={**os.environ, 'PYTHONHASHSEED': str(seed), 'OPENBLAS_NUM_THREADS': '1', 'OMP_NUM_THREADS': '1', 'MKL_NUM_THREADS': '1'}, text=True) for seed in (1, 7)]
    assert outputs[0] == outputs[1]

@pytest.mark.parametrize('name', ['ProteinDistanceGeometry'])
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
    geometry = module('ProteinDistanceGeometry')
    p, xyz = geometry._world(0)
    score, valid = geometry._score_output(0, p, dict(coordinates=xyz.tolist()))
    assert valid and score == pytest.approx(1)
    assert geometry._score_output(0, p, dict(coordinates=np.zeros_like(xyz).tolist()))[0] < 0.01

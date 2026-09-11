"""Reproduce the pre-revision PR 72 scoring failure without changing the frozen source.

Run from the repository root. Old evaluator/reference bytes come from git, and the
current audit supplies the completed four-way probe. These are builder measurements,
not secure candidate/model calibration. The exact constant bound grants true class
labels explicitly and must not be described as a legal zero-query candidate.
"""
import hashlib
import json
import platform
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import scipy

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.audit_dark_matter_recoil import load, constant_mass_bound, shortcut_probe

REVISION = 'a222b59254538c9d7f5cc9183bfecf9f31456242'
PREFIX = 'benchmarks/Physics/DarkMatterRecoilAttribution/verification/'


def main():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp)
        (path / 'verification').mkdir()
        hashes = {}
        for name in ['evaluator.py', 'reference_profile.py']:
            source = subprocess.check_output(['git', 'show', REVISION + ':' + PREFIX + name], cwd=ROOT)
            (path / 'verification' / name).write_bytes(source)
            hashes[name] = hashlib.sha256(source).hexdigest()
        evaluator = load(path / 'verification/evaluator.py')
        reference = load(path / 'verification/reference_profile.py')
        report = {'source_revision': REVISION, 'source_sha256': hashes,
                  'environment': {'python': sys.version, 'platform': platform.platform(), 'numpy': np.__version__, 'scipy': scipy.__version__},
                  'scope': 'in-process builder reproduction of reviewed source; not secure calibration'}
        report['reference'] = evaluator.evaluate(reference.infer_recoil)
        evaluator.normalized_score = lambda values: max(0, (float(np.mean(values)) - .2) / .8)
        evaluator.SPLIT_SEEDS = {'development': 731500, 'heldout': 941700}
        kinds = ['contact', 'q2'] * 3 + ['none'] * 2 + ['unsupported'] * 2
        def worlds(split):
            return [evaluator.make_world(evaluator.SPLIT_SEEDS[split] + i * 101, kind) for i, kind in enumerate(kinds)]
        report['constant_mass'] = {}
        for split in evaluator.SPLIT_SEEDS:
            rows = worlds(split)
            answers = [reference.infer_recoil(w['problem'], evaluator.Campaign(w)) for w in rows]
            report['constant_mass'][split] = {
                'with_reference_decisions': constant_mass_bound(evaluator, rows, answers),
                'with_perfect_decisions': constant_mass_bound(evaluator, rows)}
        # Add only builder adapters for the old fixed mixture to the temporary copy.
        with (path / 'verification/evaluator.py').open('a') as stream:
            stream.write('''\nZERO_UTILITY = .2
SPLIT_SEEDS = {'development': 731500, 'heldout': 941700}
def normalized_score(values):
    return max(0, (float(np.mean(values)) - .2) / .8)
def split_worlds(split):
    kinds = ['contact', 'q2'] * 3 + ['none'] * 2 + ['unsupported'] * 2
    for i, kind in enumerate(kinds):
        yield make_world(SPLIT_SEEDS[split] + i * 101, kind)
''')
        class Spec:
            task_dir = path
        report['four_way_probe'] = shortcut_probe(Spec())
        print(json.dumps(report, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()

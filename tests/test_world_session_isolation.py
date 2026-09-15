"""Real sandbox regression for independent scientific-world boundaries.

These are engineering fixtures, not task difficulty measurements. The trusted adapter sends a
fixed state probe (and two test-owned RPC callbacks) to a real CandidateProxy, records its state,
and supplies a constant refusal to the original world scorer. No score is asserted or published.
Each split task exercises one actual development and one actual held-out world; InterventionalSCM
exercises its six independent worlds. This avoids running expensive reference solvers to test
process isolation. Same-world calls must retain state; every next world must start fresh.
"""
from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

from _sandbox_tools import skip_unless_sandbox
from sle.secure_eval import CandidateProxy

ROOT = Path(__file__).resolve().parents[1]
PROBE = '''
import os
counter = 0
def probe(callback):
    global counter
    counter += 1
    first = counter
    previous = getattr(os, '_world_probe_imported', 0)
    marker = '/tmp/world_session_fixture'
    seen = os.path.exists(marker)
    os._world_probe_imported = previous + 1
    with open(marker, 'w') as handle:
        handle.write(str(first))
    preserved = True
    for token in (11, 23):
        preserved = preserved and callback(token) == token + 1
        preserved = preserved and counter == first and os._world_probe_imported == previous + 1
        with open(marker) as handle:
            preserved = preserved and handle.read() == str(first)
    return [first, seen, previous, preserved]
'''

# (package, original world boundary, collection names). All are independent top-level instances;
# scoring shifted physical cases of the same submitted design is deliberately outside this list.
CASES = (
    ('Biology/EnzymeKineticsLaw', 'world', 'DEVELOPMENT_WORLDS', 'HELDOUT_WORLDS'),
    ('Biology/OccupancyDetectionDesign', 'world', 'DEVELOPMENT_WORLDS', 'HELDOUT_WORLDS'),
    ('Chemistry/NMRSpectrumFitting', 'instance', 'DEVELOPMENT_INSTANCES', 'HELDOUT_INSTANCES'),
    ('Chemistry/PhaseDiagramDiscovery', 'world', 'DEVELOPMENT_WORLDS', 'HELDOUT_WORLDS'),
    ('Chemistry/ReactionMechanismFitting', 'world', 'DEVELOPMENT_SPECS', 'HELDOUT_SPECS'),
    ('Chemistry/SpinSystemInference', 'split', 'development_worlds', 'sealed_worlds'),
    ('ComputerScience/GraphFromDistances', 'split', 'development_worlds', 'sealed_worlds'),
    ('ComputerScience/InterventionalSCM', 'evaluate', None, None),
    ('EarthScience/ForcedSignalAttribution', 'world', 'DEVELOPMENT_WORLDS', 'HELDOUT_WORLDS'),
    ('EarthScience/GravityInversion', 'world', 'DEVELOPMENT_SPECS', 'HELDOUT_SPECS'),
    ('EarthScience/UPbConcordiaInference', 'world', 'DEVELOPMENT_WORLDS', 'HELDOUT_WORLDS'),
    ('Engineering/HeatExchangerDesign', 'instance', 'DEVELOPMENT_INSTANCES', 'HELDOUT_INSTANCES'),
    ('Engineering/ModalDamageAttribution', 'world', 'DEVELOPMENT_WORLDS', 'HELDOUT_WORLDS'),
    ('EarthScience/ChronologyAssimilation', 'world', 'DEVELOPMENT_SPECS', 'HELDOUT_SPECS'),
    ('Engineering/TrussWeightMinimization', 'instance', 'DEVELOPMENT_INSTANCES', 'HELDOUT_INSTANCES'),
    ('Mathematics/BlackBoxGroupIdentification', 'world', 'DEVELOPMENT_WORLDS', 'HELDOUT_WORLDS'),
    ('Mathematics/SequenceLawRecovery', 'split', 'development_worlds', 'sealed_worlds'),
    ('Physics/DiscrepantMeasurements', 'world', 'DEVELOPMENT_WORLDS', 'HELDOUT_WORLDS'),
    ('Physics/HamiltonianLearning', 'split', 'development_worlds', 'sealed_worlds'),
    ('Physics/HiddenCouplingNetwork', 'world', 'DEVELOPMENT_WORLDS', 'HELDOUT_WORLDS'),
    ('Physics/RadialVelocityPlanets', 'split', 'development_worlds', 'sealed_worlds'),
)


def _load(package):
    path = ROOT / 'benchmarks' / package / 'verification/evaluator.py'
    name = 'world_session_fixture_' + package.replace('/', '_')
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class _ObservedProxy:
    def __init__(self, worker):
        self.worker = worker
        self.observations = []
        self.resets = 0
        self.callbacks = 0

    def reset_session(self):
        self.worker.reset_session()
        self.resets += 1

    def _echo(self, value):
        self.callbacks += 1
        return value + 1

    def __call__(self, *unused_world_inputs, **unused_world_options):
        self.observations.append(self.worker(self._echo))
        return {'abstain': True}


def _exercise(test, case):
    package, kind, dev_name, held_name = case
    oracle = _load(package)
    with tempfile.TemporaryDirectory() as tmp:
        candidate = Path(tmp)/'probe.py'
        candidate.write_text(PROBE)
        with CandidateProxy(candidate, 'probe', timeout_s=60) as worker:
            # Also require the first world to discard an already-used worker.
            test.assertEqual(worker(lambda value: value + 1), [1, False, 0, True])
            observed = _ObservedProxy(worker)
            if kind == 'evaluate':
                oracle.evaluate(observed)
                expected = len(oracle.WORLD_SEEDS)
            else:
                for split, collection_name in (('development', dev_name), ('heldout', held_name)):
                    collection = getattr(oracle, collection_name)
                    worlds = collection() if callable(collection) else collection
                    test.assertTrue(worlds, package + ' ' + split)
                    if kind == 'world':
                        oracle._evaluate_world(observed, worlds[0], split, 0)
                    elif kind == 'instance':
                        oracle._score_instance(observed, worlds[0])
                    elif kind == 'split':
                        oracle._score_split(observed, [worlds[0]])
                    else:
                        test.fail('unknown boundary kind')
                expected = 2
    test.assertEqual(len(observed.observations), expected)
    test.assertEqual(observed.observations, [[1, False, 0, True]] * expected,
                     'candidate module/import/tmpfs state crossed a scientific world boundary')
    test.assertEqual(observed.resets, expected, 'one reset per world, never per in-world callback')
    test.assertEqual(observed.callbacks, expected * 2)


@skip_unless_sandbox('bwrap')
class WorldSessionIsolationTests(unittest.TestCase):
    pass


def _test(case):
    def test(self):
        _exercise(self, case)
    return test


for _case in CASES:
    setattr(WorldSessionIsolationTests, 'test_' + _case[0].split('/')[-1], _test(_case))


if __name__ == '__main__':
    unittest.main()

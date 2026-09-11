"""Scientific and adversarial invariants for Neuroscience/NeuralReportAttribution."""
import copy
import importlib.util
import math
import json
import platform
import sys
from types import SimpleNamespace
from pathlib import Path
import numpy as np
import pytest
from scipy.integrate import quad
from scipy.linalg import expm
from sle.metric_visibility import search_visible_metrics
ROOT = Path(__file__).resolve().parents[1]

def load(path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
MODULE = load(ROOT / 'benchmarks/Biology/NeuralReportAttribution/verification/evaluator.py')


def test_public_problem_is_identical_across_worlds_and_splits():
    kinds = ['recurrent', 'report_only'] * 3 + ['none'] * 2 + ['unsupported'] * 2
    problems = [MODULE.make_world(base + i * 113, kind)['problem']
                for base in (381900, 527300) for i, kind in enumerate(kinds)]
    problems.extend(MODULE.make_world(seed, kind)['problem']
                    for seed in range(20) for kind in set(kinds))
    assert all(problem == problems[0] for problem in problems)


@pytest.mark.parametrize('failing_split', ['development', 'heldout'])
def test_validation_feedback_does_not_reveal_heldout_failures(monkeypatch, failing_split):
    # Trusted test injection, not a candidate using an unavailable split identifier.
    original = MODULE.score_world

    def reject_selected(world, answer):
        split = 'development' if world['seed'] < 527300 else 'heldout'
        return original(world, {'model': 'invalid'} if split == failing_split else answer)

    baseline = search_visible_metrics(MODULE.evaluate(lambda *_: {'abstain': True}))
    monkeypatch.setattr(MODULE, 'score_world', reject_selected)
    result = MODULE.evaluate(lambda *_: {'abstain': True})
    assert result[failing_split + '_valid_rate'] == 0
    assert result[failing_split + '_correct_refusal_rate'] == 0
    if failing_split == 'heldout':
        assert search_visible_metrics(result) == baseline
    else:
        assert result['valid'] == result['feasibility_rate'] == 0


@pytest.mark.parametrize('returncode', [0, 2])
def test_wrapper_forwards_timeout_and_preserves_failure(monkeypatch, tmp_path, returncode):
    wrapper = load(ROOT / 'benchmarks/Biology/NeuralReportAttribution/frontier_eval/run_eval.py')
    output = tmp_path / 'metrics.json'
    output.write_text('stale')
    seen = []
    def launch(command, **kwargs):
        seen.append((command, kwargs))
        if returncode == 0:
            output.write_text('{"combined_score": 0, "valid": 1}')
        return SimpleNamespace(returncode=returncode, stdout='')
    monkeypatch.setattr(wrapper.subprocess, 'run', launch)
    assert wrapper.main(['--candidate', str(tmp_path / 'candidate.py'),
                         '--metrics-out', str(output), '--timeout', '47']) == returncode
    command, kwargs = seen[0]
    assert command[1].endswith('sle/frontier_eval_entrypoint.py')
    assert command[command.index('--timeout')+1] == '47.0'
    assert command[command.index('--task')+1] == 'Neuroscience/NeuralReportAttribution'
    assert output.exists() == (returncode == 0)


def test_algebraic_probes_respect_acquisition_costs():
    probe = load(ROOT / 'benchmarks/Biology/NeuralReportAttribution/verification/algebraic_probe.py')
    for kind in ('recurrent', 'report_only', 'none', 'unsupported'):
        world = MODULE.make_world(72, kind)
        for candidate, units in ((probe.infer_circuit, 8), (probe.null_or_refuse, 3)):
            lab = MODULE.Campaign(world)
            answer = candidate(copy.deepcopy(world['problem']), lab)
            MODULE.validate(answer)
            assert lab.used == units and not lab.violated
            if units == 3:
                assert answer.get('abstain') or answer['model'] == 'none'

def test_neural_transfer_matches_time_domain_integral():
    w = MODULE.make_world(42, 'recurrent')
    (omega, report) = (0.5, 0)
    a = MODULE.dynamics(w['parameters'], report)
    integral = np.empty((4, 4), complex)
    for i in range(4):
        for j in range(4):
            integral[i, j] = quad(lambda t: expm(a * t)[i, j] * math.cos(omega * t), 0, 35)[0] - 1j * quad(lambda t: expm(a * t)[i, j] * math.sin(omega * t), 0, 35)[0]
    (c, b, d, tau) = w['instruments'][report]
    expected = c @ integral @ b / (1 + 1j * omega * tau[:, None]) + d
    assert np.allclose(MODULE.transfer(w, report, omega), expected, atol=1e-09)

def test_report_feedback_gate_and_readout_sidepath_are_distinct():
    w = MODULE.make_world(32, 'report_only')
    a0 = MODULE.dynamics(w['parameters'], 0)
    a1 = MODULE.dynamics(w['parameters'], 1)
    assert a0[1, 2] == a1[1, 2] == 0
    assert a0[1, 3] == 0 < a1[1, 3]
    ideal = np.linalg.inv(1j * 0.5 * np.eye(4) - a0)
    assert ideal[1, 2] == 0
    assert abs(MODULE.transfer(w, 0, 0.5)[1, 2]) > 0.0001

@pytest.mark.parametrize('kind', ['recurrent', 'report_only', 'none', 'unsupported'])
def test_neural_realizations_stable(kind):
    seeds = list(range(20)) + [base + i * 113 for base in (381900, 527300) for i in range(10)]
    for seed in seeds:
        w = MODULE.make_world(seed, kind)
        for report in (0, 1):
            a = MODULE.dynamics(w['parameters'], report, kind == 'unsupported')
            assert np.max(np.linalg.eigvals(a).real) < 0

def test_counter_seeded_batch_and_query_order_equivalence():
    w = MODULE.make_world(23, 'recurrent')
    (a, b) = (MODULE.Campaign(w), MODULE.Campaign(w))
    request = {'kind': 'response', 'report': 0, 'frequency': 2, 'units': 2}
    batch = a(request)
    first = b(dict(request, units=1))
    b(dict(request, units=1, report=1))
    second = b(dict(request, units=1))
    for key in ('real', 'imag'):
        assert np.allclose(batch[key], (np.array(first[key]) + second[key]) / 2, atol=1e-15)
    assert first != second
BAD = [None, {}, [], 'model', {'abstain': 1}, {'confidence': float('nan')}, {'model': []}, {'model': 'invalid'}, {'abstain': False, 'confidence': True}, {'abstain': True, 'confidence': float('inf')}, {'abstain': True, 'confidence': -1}, {'model': 'recurrent', 'feedback': float('nan'), 'report_feedback': 0.5}, {'model': 'recurrent', 'feedback': True, 'report_feedback': 0.5}, {'model': 'report_only', 'feedback': 0.1, 'report_feedback': 0.5}]

@pytest.mark.parametrize('module', [MODULE])
@pytest.mark.parametrize('answer', BAD)
def test_malformed_answers_do_not_crash_or_gain_refusal_credit(module, answer):
    result = module.evaluate(lambda *args: answer)
    assert result['combined_score'] == result['valid'] == 0
    assert result['development_correct_refusal_rate'] == 0
    assert all((not r['valid'] for r in result['per_instance']))

@pytest.mark.parametrize('module', [MODULE])
def test_exceptions_are_sanitized(module):

    def candidate(*args):
        raise RuntimeError('candidate-controlled-token-do-not-echo')
    result = module.evaluate(candidate)
    assert result['valid'] == result['combined_score'] == 0
    assert 'candidate-controlled' not in str(result)

@pytest.mark.parametrize('module', [MODULE])
def test_caught_overbudget_is_sticky(module):

    def candidate(problem, experiment):
        req = {'kind': 'response', 'report': 0, 'frequency': 0, 'units': problem['budget_units'] + 1}
        try:
            experiment(req)
        except ValueError:
            pass
        return {'abstain': True}
    result = module.evaluate(candidate)
    assert result['valid'] == result['combined_score'] == 0

@pytest.mark.parametrize('module', [MODULE])
def test_degenerate_strategies_and_global_rng_independence(module):
    for answer in ({'abstain': True}, {'model': 'none'}):
        first = module.evaluate(lambda *args: answer)
        np.random.seed(777)
        np.random.random(1000)
        second = module.evaluate(lambda *args: answer)
        assert first == second
        assert first['combined_score'] == 0 and first['valid'] == 1
        assert first['development_claim_count'] == 0
        assert first['development_false_discovery_rate'] == 0
        visible = search_visible_metrics(first)
        assert not any((k.startswith('heldout') or 'refusal' in k for k in visible))
        assert 'per_instance' not in visible

def test_correct_law_wrong_parameter_not_reclassified_as_false_discovery():
    w = MODULE.make_world(72, 'recurrent')
    row = MODULE.score_world(w, {'model': 'recurrent', 'feedback': 1.2, 'report_feedback': 1.2})
    assert row['mechanism'] == 0 and row['false_claim'] is False


@pytest.mark.parametrize('answer', [{'abstain': True}, {'model': 'none'},
                                  {'model': 'recurrent', 'feedback': 1., 'report_feedback': 1.}, {}])
def test_diagnostic_rates_recompute_from_published_counts(answer):
    metrics = MODULE.evaluate(lambda *_: answer)
    for split in ('development', 'heldout'):
        rows = [r for r in metrics['per_instance'] if r['split'] == split]
        counts = {
            'false_discovery_count': sum(r['false_claim'] for r in rows),
            'claim_count': sum(r['claim'] for r in rows),
            'correct_refusal_count': sum(r['correct_refusal'] for r in rows),
            'refusal_world_count': sum(r['kind'] == 'unsupported' for r in rows),
            'supported_claim_count': sum(r['claim'] for r in rows if r['kind'] in ('recurrent', 'report_only')),
            'supported_world_count': sum(r['kind'] in ('recurrent', 'report_only') for r in rows),
            'none_correct_count': sum(r['model'] == 'none' for r in rows if r['kind'] == 'none'),
            'none_world_count': sum(r['kind'] == 'none' for r in rows),
            'valid_world_count': sum(r['valid'] for r in rows),
            'world_count': len(rows), 'experiment_units_sum': sum(r['units'] for r in rows),
        }
        for name, value in counts.items():
            assert metrics[split+'_'+name] == value
        for rate, numerator, denominator in (
            ('false_discovery_rate', 'false_discovery_count', 'claim_count'),
            ('correct_refusal_rate', 'correct_refusal_count', 'refusal_world_count'),
            ('discovery_coverage', 'supported_claim_count', 'supported_world_count'),
            ('none_correct_rate', 'none_correct_count', 'none_world_count'),
            ('valid_rate', 'valid_world_count', 'world_count'),
            ('mean_units', 'experiment_units_sum', 'world_count'),
        ):
            want = counts[numerator]/counts[denominator] if counts[denominator] else 0
            assert metrics[split+'_'+rate] == pytest.approx(want, abs=1e-10)
        assert not any(split+'_'+name in search_visible_metrics(metrics) for name in counts)

def test_oracle_ceiling_recomputable_without_reference_score_literal():
    for (module, kinds) in ((MODULE, ['recurrent', 'report_only', 'none', 'unsupported']),):
        for kind in kinds:
            w = module.make_world(512, kind)
            answer = {'model': kind}
            if kind == 'unsupported':
                answer = {'abstain': True}
            elif kind != 'none':
                answer.update(feedback=w['parameters']['edges'][-2], report_feedback=w['parameters']['edges'][-1])
            assert module.score_world(w, answer)['mechanism'] == 1

@pytest.mark.parametrize('module', [MODULE])
def test_mutating_public_problem_cannot_raise_budget(module):

    def candidate(problem, experiment):
        problem['budget_units'] = 10 ** 9
        try:
            experiment({'kind': 'response', 'report': 0, 'frequency': 0, 'units': 999})
        except ValueError:
            pass
        return {'abstain': True}
    assert module.evaluate(candidate)['valid'] == 0

@pytest.mark.parametrize('module', [MODULE])
def test_world_boundaries_reset_candidate_session_including_split(module):

    class StatefulProxy:
        resets = 0
        calls = 0

        def reset_session(self):
            self.resets += 1

        def __call__(self, problem, experiment):
            assert self.resets == self.calls
            self.calls += 1
            return {'abstain': True}
    candidate = StatefulProxy()
    result = module.evaluate(candidate)
    assert result['valid'] == 1
    assert candidate.calls == 20 and candidate.resets == 19

@pytest.mark.skipif(platform.system() != 'Linux', reason='Bubblewrap requires Linux')
@pytest.mark.parametrize('task,entry', [('Neuroscience/NeuralReportAttribution', 'infer_circuit')])
def test_secure_worlds_cannot_share_globals_or_tmpfs(task, entry, tmp_path):
    from sle.evaluate import evaluate_candidate
    from sle.registry import find_task
    path = tmp_path / 'candidate.py'
    path.write_text(f"from pathlib import Path\nseen = False\ndef {entry}(problem, experiment):\n    global seen\n    marker = Path('/tmp/previous_world')\n    if seen or marker.exists():\n        return []\n    seen = True\n    marker.write_text('visited')\n    return {{'model': 'none'}}\n")
    result = evaluate_candidate(find_task(task, include_uncertified=True), path, timeout_s=60)
    assert result['valid'] == 1 and result['combined_score'] == 0
    assert result['development_valid_rate'] == result['heldout_valid_rate'] == 1

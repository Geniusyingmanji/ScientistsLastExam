"""Trusted faults must not be published as scientific outcomes by any adapter."""
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from sle import upstream_evaluator
from sle.evaluate import evaluate_candidate
from sle.runtime_identity import TrustedRuntime
from sle.metric_visibility import (
    EvaluationInfrastructureError, load_full_metrics, require_healthy_evaluations,
    search_visible_metrics, store_full_metrics,
)
from sle.registry import find_task


FAULT = {'combined_score': -1e18, 'valid': 0.0, 'infrastructure_failure': 1.0,
         'error_message': 'hidden evaluator fixture: private source and labels'}


def test_faults_cannot_cross_visibility_or_sidecar_boundary(tmp_path):
    candidate = tmp_path / 'candidate.py'
    candidate.write_text('x = 1\n')
    with pytest.raises(EvaluationInfrastructureError):
        search_visible_metrics(FAULT)
    with pytest.raises(EvaluationInfrastructureError):
        store_full_metrics(tmp_path / 'private', candidate, FAULT)
    assert not (tmp_path / 'private').exists()


def test_upstream_fault_is_private_and_cannot_be_retried_as_a_scientific_outcome(tmp_path):
    candidate = tmp_path / 'candidate.py'
    candidate.write_text('x = 1\n')
    private = tmp_path / 'private'
    runtime = TrustedRuntime(
        executable='python3',
        descriptor={'fingerprint_sha256': 'a' * 64},
    )
    with patch.object(upstream_evaluator, 'find_task', return_value=SimpleNamespace(task_dir=tmp_path)), \
         patch.object(upstream_evaluator, 'resolve_trusted_runtime', return_value=runtime), \
         patch.object(upstream_evaluator, 'evaluate_candidate', return_value=FAULT) as evaluator:
        upstream_evaluator.configure('D/T', 1, str(private), runtime.fingerprint_sha256)
        try:
            with pytest.raises(EvaluationInfrastructureError, match='^trusted evaluation infrastructure failure$') as caught:
                upstream_evaluator.evaluate(str(candidate))
            import traceback
            public_trace = ''.join(traceback.format_exception(caught.type, caught.value, caught.tb))
            assert 'private source and labels' not in public_trace
            evaluator.return_value = {'combined_score': .9, 'valid': 1.0}
            with pytest.raises(EvaluationInfrastructureError):
                upstream_evaluator.evaluate(str(candidate))
            assert evaluator.call_count == 1
        finally:
            upstream_evaluator.configure('', 300, '')
    assert not list(private.glob('*.json'))
    assert list((private / 'infrastructure_failures').glob('*.json'))
    with pytest.raises(EvaluationInfrastructureError):
        require_healthy_evaluations(private)


def test_shinka_fault_removes_stale_scores_and_has_no_public_diagnostics(tmp_path, capsys):
    for name in ('metrics.json', 'correct.json'):
        (tmp_path / name).write_text('{"combined_score":1}')
    with patch.object(upstream_evaluator, 'evaluate', side_effect=RuntimeError('hidden evaluator detail')):
        assert upstream_evaluator.shinka_main('candidate.py', str(tmp_path)) == 2
    captured = capsys.readouterr()
    assert captured.out == '' and 'hidden' not in captured.err
    assert not list(tmp_path.glob('*.json'))


@pytest.mark.parametrize('mode', ['bad_json', 'nonfinite', 'outer_timeout', 'process_exit'])
def test_trusted_driver_failures_are_infrastructure_not_candidate_scores(tmp_path, mode, capsys):
    candidate = tmp_path / 'candidate.py'
    candidate.write_text('def build_capset(n): return []\n')
    spec = find_task('CapSet')

    def popen(command, **kwargs):
        result = Path(command[command.index('--result') + 1])
        if mode == 'bad_json':
            result.write_text('not valid JSON; hidden evaluator detail')
        elif mode == 'nonfinite':
            result.write_text('{"combined_score":NaN,"valid":1}')
        process = SimpleNamespace(pid=12345, returncode=2 if mode == 'process_exit' else 0,
                                  wait=lambda: None)

        def communicate(**kwargs):
            if mode == 'outer_timeout':
                raise subprocess.TimeoutExpired(command, 3)
            return None, 'hidden evaluator detail'

        process.communicate = communicate
        return process

    runtime = TrustedRuntime(
        executable='python3',
        descriptor={'fingerprint_sha256': 'a' * 64},
    )
    with patch('sle.evaluate.resolve_trusted_runtime', return_value=runtime), \
         patch('sle.evaluate.subprocess.Popen', side_effect=popen), \
         patch('sle.evaluate.os.killpg'):
        result = evaluate_candidate(spec, candidate, timeout_s=1)
    assert result['infrastructure_failure'] == 1
    assert 'candidate_failure_kind' not in result
    assert 'hidden' not in json.dumps(result)
    with pytest.raises(EvaluationInfrastructureError):
        search_visible_metrics(result)


def test_untrusted_error_text_is_not_search_feedback():
    full = {'combined_score': 0, 'valid': 0, 'error_message': 'world seed=42; private label'}
    assert 'private label' not in json.dumps(search_visible_metrics(full))


def test_abmcts_fault_cannot_be_told_to_treequest_or_resumed(tmp_path):
    from sle.algorithms import abmcts_backend
    with patch.object(abmcts_backend, 'evaluate_candidate', return_value=FAULT):
        with pytest.raises(EvaluationInfrastructureError):
            abmcts_backend._evaluate_for_search(
                object(), tmp_path/'candidate.py', 1, tmp_path/'private', object(),
            )
    with pytest.raises(EvaluationInfrastructureError):
        require_healthy_evaluations(tmp_path/'private')


def test_sidecar_concurrent_writers_cannot_overwrite_disagreement(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    candidate = tmp_path / 'candidate.py'
    candidate.write_text('x = 1\n')
    barrier = Barrier(2)
    import os
    original_link = os.link

    def synchronized_link(*args, **kwargs):
        barrier.wait(timeout=5)
        return original_link(*args, **kwargs)

    def write(score):
        try:
            store_full_metrics(tmp_path / 'private', candidate, {'combined_score': score, 'valid': 1})
            return 'stored'
        except RuntimeError:
            return 'conflict'

    with patch('sle.metric_visibility.os.link', side_effect=synchronized_link), ThreadPoolExecutor(2) as pool:
        outcomes = list(pool.map(write, [.2, .8]))
    assert sorted(outcomes) == ['conflict', 'stored']
    assert load_full_metrics(tmp_path / 'private', 'x = 1\n')['combined_score'] in (.2, .8)


def test_conflicting_upstream_sidecar_is_sticky_infrastructure_failure(tmp_path):
    candidate = tmp_path / 'candidate.py'
    candidate.write_text('x = 1\n')
    private = tmp_path / 'private'
    runtime = TrustedRuntime('python3', {'fingerprint_sha256': 'a' * 64})
    first = {'combined_score': .5, 'valid': 1.0, 'heldout_mechanism_score': .1}
    second = {**first, 'heldout_mechanism_score': .9}
    with patch.object(upstream_evaluator, 'find_task', return_value=SimpleNamespace(task_dir=tmp_path)), \
         patch.object(upstream_evaluator, 'resolve_trusted_runtime', return_value=runtime), \
         patch.object(upstream_evaluator, 'evaluate_candidate', side_effect=[first, second]) as evaluator:
        upstream_evaluator.configure('D/T', 1, str(private), runtime.fingerprint_sha256)
        try:
            assert upstream_evaluator.evaluate(str(candidate)) == {'combined_score': .5, 'valid': 1.0}
            with pytest.raises(EvaluationInfrastructureError, match='^trusted evaluation infrastructure failure$'):
                upstream_evaluator.evaluate(str(candidate))
            with pytest.raises(EvaluationInfrastructureError):
                upstream_evaluator.evaluate(str(candidate))
            assert evaluator.call_count == 2
        finally:
            upstream_evaluator.configure('', 300, '')
    with pytest.raises(EvaluationInfrastructureError):
        require_healthy_evaluations(private)

"""Exercise the shared CLI against a disposable subprocess evaluator."""
import json
import sys

import pytest

from sle.frontier_eval_entrypoint import run


@pytest.mark.parametrize('fail', [False, True])
def test_cli_runs_evaluator_and_writes_metrics_from_another_directory(tmp_path, monkeypatch, fail):
    root = tmp_path / 'project'
    package = root / 'sle'
    package.mkdir(parents=True)
    (package / '__init__.py').write_text('')
    (package / '__main__.py').write_text(
        'import json, sys\n'
        'from pathlib import Path\n'
        'assert sys.argv[1:4] == ["eval", "--task", "Example/Task"]\n'
        'assert "--allow-uncertified" in sys.argv\n'
        'candidate = Path(sys.argv[sys.argv.index("--candidate")+1])\n'
        'assert candidate.is_absolute() and candidate.read_text() == "candidate"\n'
        'assert sys.argv[sys.argv.index("--timeout")+1] == "7.0"\n'
        + ('print("ModuleNotFoundError: example_dependency", file=sys.stderr)\nraise SystemExit(2)\n' if fail else
           'print(json.dumps({"combined_score": .6, "valid": 1, "detail": 3}))\n')
    )
    outside = tmp_path / 'outside'
    outside.mkdir()
    (outside / 'candidate.py').write_text('candidate')
    monkeypatch.chdir(outside)
    monkeypatch.setattr(sys, 'argv', ['run_eval.py', '--candidate', 'candidate.py',
                                    '--metrics-out', 'metrics.json', '--timeout', '7'])
    assert run('Example/Task', root) == 0
    metrics = json.loads((outside / 'metrics.json').read_text())
    if fail:
        assert metrics['valid'] == 0 and metrics['combined_score'] < 0
        assert metrics['error_message'] == ('RuntimeError: sle eval exited 2: '
                                            'ModuleNotFoundError: example_dependency')
    else:
        assert metrics == dict(combined_score=.6, raw_score=.6, valid=1, detail=3)


@pytest.fixture
def invocation(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, 'argv', ['run_eval.py', '--candidate', 'candidate.py',
                                    '--metrics-out', 'metrics.json'])
    return tmp_path


@pytest.mark.parametrize('output', [
    'not json', 'null', '[]', '[["valid", 1], ["broken"]]',
    '{"valid": 1}', '{"combined_score": 1}',
    '{"combined_score": NaN, "valid": 1}',
    '{"combined_score": 1, "valid": true}',
])
def test_malformed_metrics_fail_closed(invocation, monkeypatch, output):
    import subprocess
    monkeypatch.setattr(subprocess, 'run', lambda *a, **k:
                        subprocess.CompletedProcess(a, 0, stdout=output, stderr=''))
    assert run('Example/Task', invocation) == 0
    metrics = json.loads((invocation / 'metrics.json').read_text())
    assert metrics['valid'] == 0 and metrics['combined_score'] < 0
    assert ': ' in metrics['error_message']


def test_failure_keeps_only_stderr_tail(invocation, monkeypatch):
    import subprocess
    stderr = 'discarded-prefix' + 'x' * 500 + ' useful diagnostic\n'
    monkeypatch.setattr(subprocess, 'run', lambda *a, **k:
                        subprocess.CompletedProcess(a, 17, stdout='', stderr=stderr))
    run('Example/Task', invocation)
    metrics = json.loads((invocation / 'metrics.json').read_text())
    assert metrics['error_message'] == 'RuntimeError: sle eval exited 17: ' + stderr.strip()[-500:]


@pytest.mark.parametrize('kind', ['timeout', 'launch'])
def test_subprocess_exception_keeps_message(invocation, monkeypatch, kind):
    import subprocess
    error = subprocess.TimeoutExpired(['sle', 'eval'], 123) if kind == 'timeout' else OSError('launch denied')
    def fail(*args, **kwargs):
        raise error
    monkeypatch.setattr(subprocess, 'run', fail)
    run('Example/Task', invocation)
    metrics = json.loads((invocation / 'metrics.json').read_text())
    assert metrics['valid'] == 0
    assert metrics['error_message'] == '%s: %s' % (type(error).__name__, error)


@pytest.mark.parametrize('timeout', ['nan', 'inf', '0', '-1'])
def test_invalid_timeout_does_not_launch(invocation, monkeypatch, timeout):
    import subprocess
    monkeypatch.setattr(sys, 'argv', sys.argv + ['--timeout', timeout])
    def forbidden(*args, **kwargs):
        pytest.fail('invalid timeout must not launch a subprocess')
    monkeypatch.setattr(subprocess, 'run', forbidden)
    run('Example/Task', invocation)
    metrics = json.loads((invocation / 'metrics.json').read_text())
    assert metrics['valid'] == 0
    assert metrics['error_message'] == 'ValueError: timeout must be finite and positive'


def test_report_write_failure_has_nonzero_exit(invocation, monkeypatch, capsys):
    import subprocess
    monkeypatch.setattr(subprocess, 'run', lambda *a, **k:
                        subprocess.CompletedProcess(a, 0, stdout='{"combined_score": 0, "valid": 1}', stderr=''))
    (invocation / 'metrics.json').mkdir()
    assert run('Example/Task', invocation) == 1
    captured = capsys.readouterr()
    assert 'cannot write metrics: IsADirectoryError:' in captured.err
    assert not captured.out

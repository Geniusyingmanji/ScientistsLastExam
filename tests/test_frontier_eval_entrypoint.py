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
        + ('raise SystemExit(2)\n' if fail else
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
        assert metrics['error_message'] == 'RuntimeError'
    else:
        assert metrics == dict(combined_score=.6, raw_score=.6, valid=1, detail=3)

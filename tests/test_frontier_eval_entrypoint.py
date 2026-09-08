"""Black-box tests for the standard-library CLI and trusted/public split."""
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "sle/frontier_eval_entrypoint.py"


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "project"
    package = root / "sle"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("")
    shutil.copy(ROOT / "sle/metric_visibility.py", package / "metric_visibility.py")
    (package / "__main__.py").write_text('''import json, os, sys
from pathlib import Path
assert sys.argv[1:4] == ["eval", "--task", "Example/Task"]
assert sys.argv[sys.argv.index("--timeout")+1] == os.environ.get("EXPECTED_TIMEOUT", "41.0")
assert not any(k in os.environ for k in ("DEMO_API_KEY", "OTHER_TOKEN", "AUTHORIZATION", "DB_PASSWORD"))
if os.environ.get("FAKE_EXIT"):
    print("/hidden/evaluator.py:9 secret-source-line", file=sys.stderr)
    raise SystemExit(int(os.environ["FAKE_EXIT"]))
print(os.environ.get("FAKE_RESPONSE", '{"combined_score":0.6,"valid":1,"detail":3,"heldout_score":0.8}'))
''')
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "candidate.py").write_text("candidate")
    return root, outside


def invoke(project, **env):
    root, outside = project
    return subprocess.run(
        [sys.executable, str(HELPER), "--task", "Example/Task", "--root", str(root),
         "--timeout", env.pop("deadline", "41"), "--candidate", "candidate.py",
         "--metrics-out", "metrics.json", "--full-metrics-dir", str(root / "private")],
        cwd=outside, env={**os.environ, **env}, capture_output=True, text=True,
    )


def test_public_metrics_exclude_oracle_only_values_and_strip_credentials(project):
    result = invoke(project, DEMO_API_KEY="must-not-pass", OTHER_TOKEN="must-not-pass",
                    AUTHORIZATION="must-not-pass", DB_PASSWORD="must-not-pass")
    assert result.returncode == 0, result.stderr
    root, outside = project
    public = json.loads((outside / "metrics.json").read_text())
    assert public == dict(combined_score=.6, valid=1, raw_score=.6)
    assert json.loads(result.stdout) == public
    digest = hashlib.sha256(b"candidate").hexdigest()
    full = json.loads((root / "private" / (digest + ".json")).read_text())
    assert full['detail'] == 3 and full['heldout_score'] == .8


@pytest.mark.parametrize('payload', [
    '{"infrastructure_failure":1,"error_message":"/hidden/evaluator.py:9 secret-source-line"}',
    'not json', '[]', '{"valid":1}', '{"combined_score":NaN,"valid":1}',
])
def test_infrastructure_and_malformed_results_never_publish_a_score(project, payload):
    root, outside = project
    (outside / "metrics.json").write_text('{"combined_score":1,"valid":1}')
    result = invoke(project, FAKE_RESPONSE=payload)
    assert result.returncode == 2 and result.stdout == ''
    assert not (outside / "metrics.json").exists()
    assert 'secret-source-line' not in result.stderr
    assert (root / "private/last_infrastructure_failure.json").exists()


def test_nonzero_evaluator_exit_keeps_details_only_in_private_diagnostic(project):
    result = invoke(project, FAKE_EXIT='17')
    root, outside = project
    assert result.returncode == 2 and not result.stdout
    assert '/hidden' not in result.stderr and 'secret-source-line' not in result.stderr
    private = json.loads((root / "private/last_infrastructure_failure.json").read_text())
    assert private['returncode'] == 17 and 'secret-source-line' in private['stderr']
    assert not (outside / "metrics.json").exists()


def test_candidate_failure_has_safe_useful_category(project):
    result = invoke(project, FAKE_RESPONSE=json.dumps(dict(
        combined_score=-1e18, valid=0, candidate_failure_kind='blocked_or_missing_import',
        error_message='/hidden/evaluator.py:9 secret-source-line')))
    root, outside = project
    assert result.returncode == 0
    public = json.loads(result.stdout)
    assert public['error_message'] == 'candidate invalid: blocked_or_missing_import'
    full = json.loads(next((root / "private").glob('*.json')).read_text())
    assert full['trusted_error_message'].startswith('/hidden')
    assert full['error_message'] == public['error_message']


def test_import_failure_is_no_score_infrastructure_failure(project):
    root, outside = project
    (root / 'sle/metric_visibility.py').write_text('raise RuntimeError("secret-source-line")')
    result = invoke(project)
    assert result.returncode == 2 and not result.stdout
    assert 'loading trusted evaluation support' in result.stderr
    assert 'secret-source-line' not in result.stderr
    assert not (outside / 'metrics.json').exists()


@pytest.mark.parametrize('deadline', ['nan', 'inf', '0', '-1'])
def test_invalid_deadline_never_scores(project, deadline):
    result = invoke(project, deadline=deadline)
    assert result.returncode == 2 and not result.stdout
    assert not (project[1] / 'metrics.json').exists()


def test_explicit_task_deadline_reaches_sle_eval(project):
    result = invoke(project, deadline='720', EXPECTED_TIMEOUT='720.0')
    assert result.returncode == 0, result.stderr


def test_metrics_write_failure_never_prints_a_score(project):
    (project[1] / 'metrics.json').mkdir()
    result = invoke(project)
    assert result.returncode == 2 and not result.stdout


def test_sidecar_mismatch_is_infrastructure_failure(project):
    assert invoke(project).returncode == 0
    result = invoke(project, FAKE_RESPONSE='{"combined_score":0.7,"valid":1}')
    assert result.returncode == 2 and not result.stdout
    assert not (project[1] / 'metrics.json').exists()


def test_generator_emits_standard_library_wrapper_and_handles_broken_helper(project):
    from scripts.gen_task import RUN_EVAL_TEMPLATE
    root, outside = project
    wrapper = root / 'benchmarks/Physics/Example/frontier_eval/run_eval.py'
    wrapper.parent.mkdir(parents=True)
    wrapper.write_text(RUN_EVAL_TEMPLATE.format(task_id='Example/Task', timeout=41.0))
    shutil.copy(HELPER, root / 'sle/frontier_eval_entrypoint.py')
    args = [sys.executable, str(wrapper), '--candidate', 'candidate.py', '--metrics-out', 'metrics.json']
    p = subprocess.run(args, cwd=outside, capture_output=True, text=True)
    assert p.returncode == 0, p.stderr
    assert json.loads(p.stdout)['combined_score'] == .6
    (root / 'sle/frontier_eval_entrypoint.py').write_text('this is invalid syntax secret_source_line')
    p = subprocess.run(args, cwd=outside, capture_output=True, text=True)
    assert p.returncode == 2 and not p.stdout
    assert 'secret_source_line' not in p.stderr
    assert not (outside / 'metrics.json').exists()


def test_generator_renders_complete_task_budget(tmp_path):
    from scripts.gen_task import create_task
    task = create_task(dict(domain='Physics', task='Example', difficulty='hard',
                            eval_time_seconds=720, task_md='Example', baseline_code='def solve(p): return {}',
                            evaluator_code='def evaluate(solve): return {}'), repo=tmp_path)
    source = (task / 'frontier_eval/run_eval.py').read_text()
    compile(source, str(task), 'exec')
    assert "TASK_ID = 'Physics/Example'" in source
    assert 'EVAL_TIMEOUT_S = 720.0' in source
    assert 'importlib' not in source and '{{' not in source


def test_outer_timeout_does_not_become_candidate_score(project, monkeypatch):
    from sle.frontier_eval_entrypoint import run
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired('hidden-command', 161, stderr=b'secret-source-line')
    monkeypatch.setattr(subprocess, 'run', timeout)
    root, outside = project
    result = run('Example/Task', root, 41, ['--candidate', str(outside/'candidate.py'),
                 '--metrics-out', str(outside/'metrics.json')])
    assert result == 2 and not (outside/'metrics.json').exists()

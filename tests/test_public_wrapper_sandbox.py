"""Exercise a real task wrapper and oracle; no candidate or evaluator mocks."""
import json
import os
import subprocess
import sys
from pathlib import Path

from _sandbox_tools import skip_unless_sandbox
from sle.evaluate import evaluate_candidate
from sle.metric_visibility import SEARCH_VISIBLE_KEYS, search_visible_metrics
from sle.registry import find_task


@skip_unless_sandbox("bwrap")
def test_capset_wrapper_isolates_module_initialization(tmp_path):
    spec = find_task("Mathematics/CapSet", include_uncertified=True)
    marker = tmp_path / "host_marker"
    candidate = tmp_path / "candidate.py"
    oracle = spec.task_dir / "verification/evaluator.py"
    candidate.write_text(
        "import os\n"
        "if os.environ.get('SLE_ISOLATION_CANARY'):\n"
        "    raise RuntimeError('host environment visible')\n"
        "try:\n"
        "    open(%r).read()\n"
        "except OSError:\n"
        "    pass\n"
        "else:\n"
        "    raise RuntimeError('oracle visible')\n"
        "try:\n"
        "    open(%r, 'w').write('candidate escaped')\n"
        "except OSError:\n"
        "    pass\n"
        "else:\n"
        "    raise RuntimeError('host writable')\n"
        % (str(oracle), str(marker))
        + spec.initial_program_path.read_text()
    )
    output = tmp_path / "metrics.json"
    completed = subprocess.run(
        [sys.executable, str(spec.task_dir / "frontier_eval/run_eval.py"),
         "--candidate", str(candidate), "--metrics-out", str(output), "--timeout", "30"],
        env={**os.environ, "SLE_ISOLATION_CANARY": "artificial_fixture_value"},
        text=True, capture_output=True, timeout=180,
    )
    assert completed.returncode == 0, completed.stderr
    public = json.loads(output.read_text())
    assert public["valid"] == 1.0, public
    assert not marker.exists()
    assert set(public) <= set(SEARCH_VISIBLE_KEYS)
    assert json.loads(completed.stdout) == public
    assert "artificial_fixture_value" not in completed.stdout + completed.stderr
    expected = evaluate_candidate(spec, spec.initial_program_path, timeout_s=30)
    assert public == search_visible_metrics(expected)

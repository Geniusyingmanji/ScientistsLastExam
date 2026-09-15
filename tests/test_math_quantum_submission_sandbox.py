"""Real sandbox integration checks for the three PR36 candidate resources."""
import json
import os
import subprocess
import sys

import pytest

from _sandbox_tools import skip_unless_sandbox
from sle.evaluate import evaluate_candidate
from sle.metric_visibility import SEARCH_VISIBLE_KEYS, search_visible_metrics
from sle.registry import find_task


TASKS = [
    ("Mathematics/ChowlaCosineCertificate", "build_certificate"),
    ("QuantumFoundations/DephrasureCodeDesign", "design_code"),
    ("QuantumFoundations/MutuallyUnbiasedBases6", "build_bases"),
]


@skip_unless_sandbox("bwrap")
@pytest.mark.parametrize("task_id,entrypoint", TASKS)
def test_public_wrapper_preserves_isolation_and_filters_metrics(tmp_path, task_id, entrypoint):
    spec = find_task(task_id, include_uncertified=True)
    marker = tmp_path / "host_marker"
    candidate = tmp_path / "candidate.py"
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
        % (str(spec.task_dir / "verification/evaluator.py"), str(marker))
        + spec.initial_program_path.read_text()
    )
    output = tmp_path / "metrics.json"
    completed = subprocess.run(
        [sys.executable, str(spec.task_dir / "frontier_eval/run_eval.py"),
         "--candidate", str(candidate), "--metrics-out", str(output), "--timeout", "60"],
        env={**os.environ, "SLE_ISOLATION_CANARY": "artificial_fixture_value"},
        text=True, capture_output=True, timeout=210,
    )
    assert completed.returncode == 0, completed.stderr
    public = json.loads(output.read_text())
    assert public["valid"] == 1, public
    assert public["combined_score"] == 0, public
    assert not marker.exists()
    assert set(public) <= set(SEARCH_VISIBLE_KEYS)
    assert json.loads(completed.stdout) == public
    assert "artificial_fixture_value" not in completed.stdout + completed.stderr
    expected = evaluate_candidate(spec, spec.initial_program_path, timeout_s=60)
    assert public == search_visible_metrics(expected)


@skip_unless_sandbox("bwrap")
@pytest.mark.parametrize("task_id,entrypoint", TASKS[:2])
def test_real_candidate_module_state_is_reset_per_world(tmp_path, task_id, entrypoint):
    spec = find_task(task_id, include_uncertified=True)
    candidate = tmp_path / "stateful.py"
    candidate.write_text(spec.initial_program_path.read_text() + "\n"
                         + "_original = " + entrypoint + "\n_calls = 0\n"
                         + "def " + entrypoint + "(problem):\n"
                         + "    global _calls\n    _calls += 1\n"
                         + "    if _calls != 1:\n        raise RuntimeError('world state survived')\n"
                         + "    return _original(problem)\n")
    result = evaluate_candidate(spec, candidate, timeout_s=60)
    assert result["valid"] == 1, result
    assert result["combined_score"] == 0, result

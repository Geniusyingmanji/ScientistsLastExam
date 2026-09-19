"""The optimization branch contains optimization packages and their current manifests."""
import json
from pathlib import Path

import yaml

from sle.certification import certification_status, load_certification
from sle.registry import list_tasks

ROOT = Path(__file__).resolve().parents[1]


def test_current_inventory_is_explicitly_optimization_only():
    tasks = list_tasks(None)
    assert len(tasks) == 42
    assert all(task.metadata.get("scientific_role") == "optimization" for task in tasks)
    assert sum(certification_status(task.task_id) == "certified" for task in tasks) == 5
    ids = {task.task_id for task in tasks}
    assert set(load_certification()["tasks"]) == ids
    taxonomy = yaml.safe_load((ROOT / "sle/conf/exam_taxonomy.yaml").read_text())
    assert set(taxonomy["tasks"]) == ids
    assert all(row["form"] == "optimization" for row in taxonomy["tasks"].values())
    versions = yaml.safe_load((ROOT / "sle/task_versions.yaml").read_text())
    assert set(versions["tasks"]) <= ids


def test_discovery_episode_entrypoints_are_not_exposed_on_this_branch():
    from sle.cli import main
    import contextlib
    import io

    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        try:
            main(["--help"])
        except SystemExit as stopped:
            assert stopped.code == 0
    assert "episode" not in output.getvalue()
    assert not (ROOT / "benchmarks/ComputerScience/MeasurementAudit").exists()
    assert not (ROOT / "sle/evidence_episode.py").exists()


def test_required_admission_test_modules_remain_present():
    required = json.loads((ROOT / ".github/required_admission_tests.json").read_text())
    assert required
    for identifier in required:
        path = ROOT / "tests" / (identifier.split('.')[1] + ".py")
        assert path.is_file(), identifier

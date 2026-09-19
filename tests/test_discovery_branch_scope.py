"""Discovery branch inventories and historical exclusions must be explicit."""
import json
import subprocess
from pathlib import Path

import yaml

from sle.certification import certification_status, load_certification
from sle.registry import list_tasks
from sle.scientific_episode import PILOTS

ROOT = Path(__file__).resolve().parents[1]


def test_current_inventory_contains_discovery_packages_without_promoting_certification():
    tasks = list_tasks(None)
    assert tasks
    assert all(task.metadata.get("scientific_role") == "discovery" for task in tasks)
    assert all(certification_status(task.task_id) != "certified" for task in tasks)
    assert list_tasks() == []
    ids = {task.task_id for task in tasks}
    assert set(load_certification()["tasks"]) == ids
    taxonomy = yaml.safe_load((ROOT / "sle/conf/exam_taxonomy.yaml").read_text())
    assert set(taxonomy["tasks"]) == ids
    assert all(row["form"] == "discovery" for row in taxonomy["tasks"].values())
    versions = yaml.safe_load((ROOT / "sle/task_versions.yaml").read_text())
    assert set(versions["tasks"]) <= ids


def test_branch_scope_is_exact_and_archives_only_optimization_at_the_recorded_split():
    scope = yaml.safe_load((ROOT / "sle/conf/branch_scope.yaml").read_text())
    retained = scope["retained_task_ids"]
    archived = scope["archived_task_ids"]
    assert scope["role"] == "discovery"
    assert len(retained) == len(set(retained))
    assert len(archived) == len(set(archived))
    assert set(retained) == {task.task_id for task in list_tasks(None)}
    assert set(retained).isdisjoint(archived)
    assert set(scope["episode_task_ids"]) == set(PILOTS)
    assert set(scope["episode_task_ids"]).isdisjoint(retained)
    assert set(scope["episode_task_ids"]).isdisjoint(archived)
    base = yaml.safe_load(subprocess.check_output(
        ["git", "show", scope["split_base"] + ":sle/conf/exam_taxonomy.yaml"],
        cwd=ROOT, text=True))
    assert set(archived) == {
        name for name, row in base["tasks"].items() if row["form"] == "optimization"
    }


def test_discovery_episode_and_required_admission_checks_remain_available():
    assert (ROOT / "sle/evidence_episode.py").is_file()
    for relative in PILOTS.values():
        assert (ROOT / "benchmarks" / relative / "verification/episode.py").is_file()
    required = json.loads((ROOT / ".github/required_admission_tests.json").read_text())
    assert required
    for identifier in required:
        path = ROOT / "tests" / (identifier.split("::", 1)[0].split(".")[1] + ".py")
        assert path.is_file(), identifier

"""Which recorded task hashes are the same task.

Reports refuse to compare runs made against different versions of a task, because comparing
across a task edit reports the edit as a model difference. Keyed on the raw `task_package_sha256`
that guard is far too strict: a declarative line added to every task's card moved every hash, and
the hash used to include the task's own `runs/` output, so merely running a task changed its
recorded identity. Twenty tasks looked edited; sixteen were untouched.

`scripts/build_task_version_equivalence.py` settles this from git history and writes
`task_versions.yaml`. This reads it back. An unknown hash maps to itself, so a task with no entry
behaves exactly as it did before - the table can only ever merge versions it has evidence for.
"""
from __future__ import annotations

from pathlib import Path

import yaml

TABLE_PATH = Path(__file__).resolve().parent / "task_versions.yaml"

_TABLE: dict[tuple[str, str], str] | None = None


def _load(path: Path | None = None) -> dict[tuple[str, str], str]:
    table: dict[tuple[str, str], str] = {}
    source = path or TABLE_PATH
    if not source.is_file():
        return table
    try:
        document = yaml.safe_load(source.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return table
    for task, entry in (document.get("tasks") or {}).items():
        for group in entry.get("classes") or []:
            for version in group.get("versions") or []:
                table[(str(task), str(version))] = str(group.get("id") or version)
    return table


def version_class(task: str, sha: str, path: Path | None = None) -> str:
    """The identity to compare on: an equivalence class where one is known, else the hash.

    Falling back to the hash rather than to a shared "unknown" bucket is deliberate. Two hashes
    nobody has established anything about are not thereby the same task, and pooling them would
    reintroduce exactly the error the guard exists to prevent.
    """
    global _TABLE
    if path is not None:
        return _load(path).get((task, sha), sha)
    if _TABLE is None:
        _TABLE = _load()
    return _TABLE.get((task, sha), sha)

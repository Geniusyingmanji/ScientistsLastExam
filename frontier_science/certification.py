"""Machine-readable scientific task certification policy."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

MANIFEST_PATH = Path(__file__).with_name("certification.yaml")
VALID_STATUSES = {"certified", "candidate", "quarantined"}


@lru_cache(maxsize=1)
def load_certification() -> dict[str, Any]:
    data = yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8")) or {}
    if data.get("schema_version") != 1 or not isinstance(data.get("tasks"), dict):
        raise ValueError("invalid certification manifest")
    for task_id, record in data["tasks"].items():
        if not isinstance(task_id, str) or not isinstance(record, dict):
            raise ValueError("invalid certification task record")
        if record.get("status") not in VALID_STATUSES or not record.get("reason"):
            raise ValueError("invalid certification status/reason for %s" % task_id)
    return data


def certification_record(task_id: str) -> dict[str, Any]:
    record = load_certification()["tasks"].get(task_id)
    if record is None:
        return {"status": "candidate", "reason": "not yet reviewed against certification gates"}
    return dict(record)


def certification_status(task_id: str) -> str:
    return str(certification_record(task_id)["status"])

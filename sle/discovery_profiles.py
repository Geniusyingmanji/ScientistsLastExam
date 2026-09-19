"""Shared profile interface for historical evidence and the trusted recorder.

The optimization branch has no registered discovery pilots. Discovery profiles
and their task adapters are maintained on main; empty registries never imply
that an optimization task was assessed for discovery.
"""
from __future__ import annotations

import copy
import hashlib
from pathlib import Path

import yaml


PILOTS = {}


# Source reviewed for these labels; a later task edit requires a new review.
REVIEWED_SOURCES = {}

def profile_for(spec):
    """Return declarations and the explicit extent of static inspection."""
    card_path = spec.task_dir / "TASK_CARD.yaml"
    card = yaml.safe_load(card_path.read_text()) if card_path.is_file() else {}
    pilot = PILOTS.get(spec.task_id)
    source_paths = [spec.task_dir / "Task.md", card_path,
                    spec.task_dir / "verification/evaluator.py"]
    source_hashes = {str(p.relative_to(spec.task_dir)): hashlib.sha256(p.read_bytes()).hexdigest()
                     for p in source_paths if p.is_file()}
    assessment = "not_assessed"
    if pilot:
        assessment = "source_inspected" if source_hashes == REVIEWED_SOURCES[spec.task_id] else "source_changed"
    inspected = pilot if assessment == "source_inspected" else None
    return {
        "schema_version": 1,
        "task_id": spec.task_id,
        "discipline": spec.discipline,
        "assessment_status": assessment,
        "scientific_question": (card or {}).get("scientific_question"),
        "artifact": (card or {}).get("artifact"),
        "openness": inspected["openness"] if inspected else None,
        "claim_types": list(inspected["claim_types"]) if inspected else [],
        "given": inspected["given"] if inspected else None,
        "unknown": inspected["unknown"] if inspected else None,
        "verification": list(inspected["verification"]) if inspected else [],
        "world_type": "simulation" if inspected else "not_assessed",
        "novelty_scope": "benchmark_rediscovery" if inspected else "not_assessed",
        "field_novelty": "not_established",
        "independent_scientific_review": "pending",
        "process_recording": "trusted_callback_and_submission" if pilot else "not_instrumented",
        "limitations": inspected["limitations"] if inspected else "Requires claim and verifier review; labels are not inferred from task kind.",
        "source_sha256": source_hashes,
    }


def pilot_contract(task_id):
    return copy.deepcopy(PILOTS.get(task_id))

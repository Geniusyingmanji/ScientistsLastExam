#!/usr/bin/env python3
"""Build a conservative, evidence-bound maturity ledger for every task.

Certification, scientific release readiness, external validation, and long-horizon
measurement readiness answer different questions.  This audit keeps those gates
separate and refuses to promote old calibration reports after a task contract changed
unless a committed migration audit explicitly replayed the retained evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable, Optional

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sle.certification import certification_record  # noqa: E402
from sle.benchmark_layout import task_path  # noqa: E402
from sle.provenance import (  # noqa: E402
    SOURCE_SCOPE,
    finalize_report_trust,
    source_provenance,
)
from sle.registry import list_tasks  # noqa: E402
from scripts.audit_tasks import _task_card_issues  # noqa: E402


SCHEMA_VERSION = 1
BINDING_STATES = {
    "current_contract_bound",
    "migration_replayed",
    "historical_only",
    "unbound",
}
ADMISSIBLE_STATUSES = {"certified", "candidate"}
REVIEW_COMPLETE_VALUES = {
    "complete",
    "completed",
    "passed",
    "approved",
    "externally_reviewed",
}
EXTERNAL_VALIDATION_VALUES = {
    "complete",
    "completed",
    "passed",
    "validated",
    "independently_validated",
}
PROVENANCE_CLASSES = {
    "known_answer",
    "procedural",
    "public_data_replay",
    "prospective",
}
GLOBAL_REPORTS = {
    "certification": "experiments/task_certification_audit_2026-08-15_v66.json",
    "secure_baseline": "experiments/secure_baseline_determinism_2026-08-15_v48.json",
    "security": "experiments/security_audit_2026-07-26_v47.json",
    "full_test_suite": "experiments/full_test_suite_2026-07-26_v23.json",
    "cross_task_calibration": "experiments/science_calibration_summary_2026-07-26_v31.json",
    "runtime_migration": "experiments/trusted_context_runtime_migration_audit_2026-07-26_v1.json",
    "alloy_migration": "experiments/alloy_hash_order_migration_audit_2026-07-26.json",
    "track_f_search": "experiments/track_f_search_2026-07-26_v1.json",
    "track_f_confirmation": "experiments/track_f_confirmation_2026-07-26_v1.json",
    "track_f_analysis": "experiments/track_f_analysis_2026-07-26_v1.json",
    "quarantined_reaudit": (
        "experiments/quarantined_task_admission_audit_2026-08-15_v2.json"
    ),
}
EVIDENCE_PATTERNS = (
    "experiments/gpt55*.json",
    "experiments/feedback_pilot*.json",
    "experiments/feedback_measurement_pilot*.json",
    "experiments/track_f_*.json",
    "experiments/*calibration*.json",
    "experiments/*admission_audit*.json",
    "experiments/*crosscheck*.json",
    "experiments/*migration_audit*.json",
    "experiments/neutron_diffusion_anchor*.json",
)
TASK_CONTRACT_PATHS = (
    "Task.md",
    "solution.py",
    "verification/evaluator.py",
    "frontier_eval",
)


def _git(args: list[str], *, check: bool = False) -> str:
    result = subprocess.run(
        ["git", *args], cwd=str(ROOT), text=True,
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
    )
    if check and result.returncode:
        raise RuntimeError("git command failed: git %s" % " ".join(args))
    return result.stdout.rstrip("\r\n") if result.returncode == 0 else ""


def _git_commit_exists(revision: str) -> bool:
    return subprocess.run(
        ["git", "cat-file", "-e", "%s^{commit}" % revision],
        cwd=str(ROOT), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    ).returncode == 0


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _tracked_json_paths(
    required_reports: Iterable[str] = GLOBAL_REPORTS.values(),
) -> list[Path]:
    tracked = set(_git(["ls-files", "experiments/*.json"], check=True).splitlines())
    selected = set(required_reports)
    for pattern in EVIDENCE_PATTERNS:
        selected.update(str(path.relative_to(ROOT)) for path in ROOT.glob(pattern))
    return [ROOT / name for name in sorted(selected & tracked) if (ROOT / name).is_file()]


def _load_json(path: Path) -> Optional[dict[str, Any]]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def _walk_task_ids(value: Any, inventory_ids: set[str]) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            if key in {"task", "task_id"} and isinstance(child, str):
                if child in inventory_ids:
                    found.add(child)
            elif key == "tasks" and isinstance(child, list):
                found.update(
                    item for item in child
                    if isinstance(item, str) and item in inventory_ids
                )
            found.update(_walk_task_ids(child, inventory_ids))
    elif isinstance(value, list):
        for child in value:
            found.update(_walk_task_ids(child, inventory_ids))
    return found


def _kind(path: Path) -> str:
    name = path.name
    if name.startswith("task_certification_audit"):
        return "certification"
    if name.startswith("secure_baseline_determinism"):
        return "secure_baseline"
    if "migration_audit" in name:
        return "migration"
    if "crosscheck" in name:
        return "independent_numerical_crosscheck"
    if "admission_audit" in name:
        return "admission"
    if "confirmation" in name:
        return "fresh_confirmation"
    if "analysis" in name:
        return "analysis"
    if name.startswith("gpt55") or name.startswith("feedback_") or name.startswith("track_f_search"):
        return "model_run"
    if "calibration" in name or "anchor" in name:
        return "calibration"
    return "other"


def _task_contract_bases(task_id: str) -> tuple[str, ...]:
    domain, task = task_id.split("/", 1)
    canonical = task_path(Path("benchmarks"), domain, task).as_posix()
    legacy = "benchmarks/%s" % task_id
    return tuple(dict.fromkeys((canonical, legacy)))


@lru_cache(maxsize=None)
def _contract_tree(revision: str, task_id: str) -> tuple[tuple[str, str], ...]:
    """Return task-relative runtime paths and blob ids, independent of layout."""

    bases = _task_contract_bases(task_id)
    result = subprocess.run(
        ["git", "ls-tree", "-r", revision, "--", *bases],
        cwd=str(ROOT), text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
    )
    if result.returncode:
        return ()
    grouped: dict[str, dict[str, str]] = {base: {} for base in bases}
    for line in result.stdout.splitlines():
        if "\t" not in line:
            continue
        metadata, name = line.split("\t", 1)
        fields = metadata.split()
        if len(fields) < 3:
            continue
        for base in bases:
            prefix = base + "/"
            if not name.startswith(prefix):
                continue
            relative = name[len(prefix):]
            if (
                relative in {"Task.md", "solution.py", "verification/evaluator.py"}
                or relative.startswith("frontier_eval/")
            ):
                grouped[base][relative] = fields[2]
            break
    populated = [entries for entries in grouped.values() if entries]
    if len(populated) != 1:
        return ()
    return tuple(sorted(populated[0].items()))


def _contract_equal(left_revision: str, right_revision: str, task_id: str) -> bool:
    if not left_revision or not right_revision:
        return False
    left = _contract_tree(left_revision, task_id)
    return bool(left) and left == _contract_tree(right_revision, task_id)


def _contract_sha256(task_dir: Path) -> str:
    digest = hashlib.sha256()
    paths: list[Path] = []
    for suffix in TASK_CONTRACT_PATHS:
        path = task_dir / suffix
        if path.is_dir():
            paths.extend(
                child for child in path.rglob("*")
                if child.is_file() and "__pycache__" not in child.parts
            )
        elif path.is_file():
            paths.append(path)
    card = task_dir / "TASK_CARD.yaml"
    if card.is_file():
        paths.append(card)
    for path in sorted(set(paths)):
        relative = path.relative_to(task_dir).as_posix().encode("utf-8")
        payload = path.read_bytes()
        digest.update(len(relative).to_bytes(4, "big"))
        digest.update(relative)
        digest.update(len(payload).to_bytes(8, "big"))
        digest.update(payload)
    return digest.hexdigest()


def _migration_contracts(documents: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    contracts: list[dict[str, Any]] = []

    runtime = documents.get(GLOBAL_REPORTS["runtime_migration"], {})
    runtime_contract = runtime.get("source_contract") or {}
    runtime_replay = runtime.get("retained_artifact_replay") or {}
    runtime_tasks = sorted({
        row.get("task") for row in runtime_replay.get("artifact_instances", [])
        if isinstance(row, dict) and isinstance(row.get("task"), str)
    })
    if (
        runtime.get("trusted_evidence") is True
        and runtime_replay.get("passed") is True
        and runtime_contract.get("passed") is True
    ):
        contracts.append({
            "audit": GLOBAL_REPORTS["runtime_migration"],
            "base_revision": runtime_contract.get("base_revision"),
            "target_revision": runtime_contract.get("audited_revision"),
            "tasks": runtime_tasks,
        })

    alloy = documents.get(GLOBAL_REPORTS["alloy_migration"], {})
    alloy_contract = alloy.get("source_contract") or {}
    alloy_conclusion = alloy.get("conclusion") or {}
    if (
        alloy.get("trusted_evidence") is True
        and alloy_conclusion.get("migration_accepted") is True
        and alloy_contract.get("passed") is True
        and isinstance(alloy.get("task"), str)
    ):
        contracts.append({
            "audit": GLOBAL_REPORTS["alloy_migration"],
            "base_revision": alloy_contract.get("input_source_revision"),
            "target_revision": alloy_contract.get("audited_target_revision"),
            "tasks": [alloy["task"]],
        })
    return contracts


def _binding_state(
    source_revision: str,
    task_id: str,
    head_revision: str,
    migrations: list[dict[str, Any]],
) -> tuple[str, Optional[str]]:
    if not source_revision or not _git_commit_exists(source_revision):
        return "unbound", None
    if _contract_equal(source_revision, head_revision, task_id):
        return "current_contract_bound", None
    for migration in migrations:
        base = migration.get("base_revision")
        target = migration.get("target_revision")
        if task_id not in migration.get("tasks", []) or not base or not target:
            continue
        if (
            _contract_equal(source_revision, base, task_id)
            and _contract_equal(target, head_revision, task_id)
        ):
            return "migration_replayed", str(migration["audit"])
    return "historical_only", None


def _evidence_ref(
    path: Path,
    document: dict[str, Any],
    task_id: str,
    head_revision: str,
    migrations: list[dict[str, Any]],
) -> dict[str, Any]:
    provenance = document.get("source_provenance") or {}
    source_revision = str(provenance.get("git_revision") or "")
    binding, migration_audit = _binding_state(
        source_revision, task_id, head_revision, migrations
    )
    return {
        "kind": _kind(path),
        "path": str(path.relative_to(ROOT)),
        "sha256": _sha256(path),
        "created_at": document.get("created_at") or document.get("completed_at"),
        "source_revision": source_revision or None,
        "trusted_evidence": document.get("trusted_evidence") is True,
        "execution_passed": document.get("execution_passed") is True,
        "contract_binding": binding,
        "migration_audit": migration_audit,
        "evidence_scope": document.get("evidence_scope"),
    }


def _card_state(task_dir: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    path = task_dir / "TASK_CARD.yaml"
    if path.is_file():
        card = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        card_sha256 = _sha256(path)
    else:
        card = {}
        card_sha256 = None
    review = card.get("review") if isinstance(card.get("review"), dict) else {}
    domain_status = str(review.get("domain") or "not_declared")
    domain_review_complete = domain_status.lower() in REVIEW_COMPLETE_VALUES
    external_status = str(review.get("external_validation") or "not_declared")
    external_validation_complete = external_status.lower() in EXTERNAL_VALIDATION_VALUES

    lineage = card.get("lineage") if isinstance(card.get("lineage"), dict) else {}
    required_lineage = (
        "builder_model_ids",
        "builder_scaffolds",
        "calibration_runs",
        "frozen_before_eval",
    )
    lineage_declared = all(key in lineage for key in required_lineage)
    builder_ids = lineage.get("builder_model_ids")
    builder_scaffolds = lineage.get("builder_scaffolds")
    lineage_complete = bool(
        lineage.get("status") == "complete"
        and lineage.get("frozen_before_eval") is True
        and isinstance(builder_ids, list) and builder_ids
        and isinstance(builder_scaffolds, list) and builder_scaffolds
        and all("unknown" not in str(value).lower() for value in builder_ids)
        and all("unknown" not in str(value).lower() for value in builder_scaffolds)
    )

    provenance = card.get("provenance") if isinstance(card.get("provenance"), dict) else {}
    provenance_class = str(provenance.get("class") or "undeclared")
    novelty_risk = card.get("novelty_risk")
    novelty_risk_declared = novelty_risk not in (None, "", [], {})

    searchable = json.dumps({
        "normalization": card.get("normalization"),
        "invariants": card.get("invariants"),
        "known_shortcuts": card.get("known_shortcuts"),
    }, sort_keys=True).lower()
    generalization_terms = [
        term for term in ("held-out", "heldout", "sealed", "shift", "procedural", "fresh")
        if term in searchable
    ]
    return card, {
        "path": str(path.relative_to(ROOT)),
        "sha256": card_sha256,
        "schema_issues": _task_card_issues(path),
        "domain_review_status": domain_status,
        "domain_review_complete": domain_review_complete,
        "external_validation_status": external_status,
        "external_validation_complete": external_validation_complete,
        "builder_lineage_declared": lineage_declared,
        "builder_lineage_complete": lineage_complete,
        "missing_builder_lineage_fields": [
            key for key in required_lineage if lineage.get(key) in (None, "", [], {})
        ],
        "provenance_class": provenance_class,
        "provenance_class_declared": provenance_class in PROVENANCE_CLASSES,
        "novelty_risk_declared": novelty_risk_declared,
        "generalization_declared": bool(generalization_terms),
        "generalization_terms": generalization_terms,
    }


def _trusted_document(document: dict[str, Any]) -> bool:
    return document.get("trusted_evidence") is True and document.get("execution_passed") is True


def _run_events(run: dict[str, Any]) -> list[dict[str, Any]]:
    snapshot = run.get("trajectory_snapshot")
    if isinstance(snapshot, dict) and isinstance(snapshot.get("events"), list):
        return [event for event in snapshot["events"] if isinstance(event, dict)]
    trajectory = run.get("trajectory")
    if isinstance(trajectory, list):
        return [event for event in trajectory if isinstance(event, dict)]
    return []


def _finite_score(value: Any) -> Optional[float]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) and number > -1.0e17 else None


def _model_run_records(
    documents: dict[str, dict[str, Any]],
    inventory_ids: set[str],
    head_revision: str,
    migrations: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    records: dict[str, list[dict[str, Any]]] = defaultdict(list)
    seen: set[tuple[str, str]] = set()
    for relative, document in documents.items():
        runs = document.get("runs")
        if not _trusted_document(document) or not isinstance(runs, list):
            continue
        config = document.get("config") if isinstance(document.get("config"), dict) else {}
        budget = config.get("budget")
        for index, run in enumerate(runs):
            if not isinstance(run, dict) or run.get("task") not in inventory_ids:
                continue
            task_id = str(run["task"])
            workdir = str(run.get("workdir") or "")
            identity = (task_id, workdir or "%s#%d" % (relative, index))
            if identity in seen:
                continue
            seen.add(identity)
            source_revision = str((document.get("source_provenance") or {}).get("git_revision") or "")
            binding, migration_audit = _binding_state(
                source_revision, task_id, head_revision, migrations
            )
            events = _run_events(run)
            best = _finite_score(run.get("best"))
            if best is None and events:
                best = max(
                    (score for score in (_finite_score(event.get("best_score")) for event in events)
                     if score is not None),
                    default=None,
                )
            records[task_id].append({
                "report": relative,
                "report_sha256": _sha256(ROOT / relative),
                "source_revision": source_revision or None,
                "contract_binding": binding,
                "migration_audit": migration_audit,
                "cohort": relative,
                "workdir": workdir or None,
                "feedback_mode": str(run.get("feedback_mode") or "unknown"),
                "algorithm": run.get("algorithm"),
                "seed": run.get("seed"),
                "proposal_budget": budget,
                "baseline_score": _finite_score(run.get("baseline")),
                "best_score": best,
                "error": run.get("error"),
                "events": events,
            })
    return records


def _score_summary(values: Iterable[float]) -> Optional[dict[str, Any]]:
    numbers = list(values)
    if not numbers:
        return None
    mean = sum(numbers) / len(numbers)
    return {
        "n": len(numbers),
        "mean": mean,
        "minimum": min(numbers),
        "maximum": max(numbers),
    }


def _proposal_trajectory_health(runs: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize observed proposal validity and floor/ceiling mass.

    These are descriptive run diagnostics, not estimates of a provider-side
    first-valid probability.  The Azure endpoint does not expose generation
    seeds, and most task/condition cells currently contain only one run.
    """

    proposal_event_count = 0
    valid_proposal_event_count = 0
    runs_with_proposals = 0
    runs_with_valid_proposals = 0
    first_valid_scores: list[float] = []
    best_scores: list[float] = []
    for run in runs:
        proposals = []
        for event in run.get("events", []):
            try:
                step = int(event.get("step", 0))
            except (TypeError, ValueError):
                continue
            if step < 1:
                continue
            proposals.append(event)
        if proposals:
            runs_with_proposals += 1
        proposal_event_count += len(proposals)
        valid = []
        for event in proposals:
            score = _finite_score(event.get("score"))
            if event.get("valid") is True and score is not None:
                valid.append(score)
        valid_proposal_event_count += len(valid)
        if valid:
            runs_with_valid_proposals += 1
            first_valid_scores.append(valid[0])
        best = _finite_score(run.get("best_score"))
        if best is not None:
            best_scores.append(best)

    run_count = len(runs)
    floor_threshold = 0.01
    ceiling_threshold = 0.95
    return {
        "run_count": run_count,
        "runs_with_proposals": runs_with_proposals,
        "runs_with_valid_proposals": runs_with_valid_proposals,
        "observed_first_valid_run_rate": (
            runs_with_valid_proposals / run_count if run_count else None
        ),
        "proposal_event_count": proposal_event_count,
        "valid_proposal_event_count": valid_proposal_event_count,
        "observed_valid_proposal_rate": (
            valid_proposal_event_count / proposal_event_count
            if proposal_event_count else None
        ),
        "first_valid_score": _score_summary(first_valid_scores),
        "best_score": _score_summary(best_scores),
        "floor_threshold": floor_threshold,
        "ceiling_threshold": ceiling_threshold,
        "best_at_or_below_floor_count": sum(
            score <= floor_threshold for score in best_scores
        ),
        "best_at_or_above_ceiling_count": sum(
            score >= ceiling_threshold for score in best_scores
        ),
    }


def _measurement_state(runs: list[dict[str, Any]]) -> dict[str, Any]:
    usable = [
        run for run in runs
        if run["contract_binding"] in {"current_contract_bound", "migration_replayed"}
        and run.get("error") in (None, "")
    ]
    historical = [run for run in runs if run not in usable]

    def selected(mode: str, budget: int) -> list[dict[str, Any]]:
        return [
            run for run in usable
            if run.get("feedback_mode") == mode and run.get("proposal_budget") == budget
        ]

    b1 = selected("normal", 1)
    b3 = selected("normal", 3)
    blind3 = selected("selection_blind", 3)

    cohort_counts: dict[str, Counter[str]] = defaultdict(Counter)
    for run in usable:
        if run.get("proposal_budget") == 3:
            cohort_counts[str(run["cohort"])][str(run["feedback_mode"])] += 1
    matched = []
    for cohort, counts in cohort_counts.items():
        replicate_count = min(counts["normal"], counts["selection_blind"])
        if replicate_count:
            matched.append({
                "cohort": cohort,
                "normal_count": counts["normal"],
                "selection_blind_count": counts["selection_blind"],
                "matched_replicate_count": replicate_count,
            })
    matched.sort(key=lambda row: (-row["matched_replicate_count"], row["cohort"]))

    gains: list[float] = []
    gain_rows = []
    for run in b3:
        proposal_events = []
        for event in run.get("events", []):
            if int(event.get("step", 0)) < 1 or event.get("valid") is not True:
                continue
            score = _finite_score(event.get("score"))
            if score is not None:
                proposal_events.append((int(event["step"]), score))
        if len(proposal_events) < 2:
            continue
        first_score = proposal_events[0][1]
        later_best = max(score for _, score in proposal_events[1:])
        gain = later_best - first_score
        gains.append(gain)
        gain_rows.append({
            "report": run["report"],
            "seed": run.get("seed"),
            "first_valid_proposal_score": first_score,
            "later_best_score": later_best,
            "later_gain": gain,
        })

    return {
        "current_or_migrated_run_count": len(usable),
        "historical_or_unbound_run_count": len(historical),
        "normal_budget_one": _score_summary(
            run["best_score"] for run in b1 if run.get("best_score") is not None
        ),
        "normal_budget_three": _score_summary(
            run["best_score"] for run in b3 if run.get("best_score") is not None
        ),
        "selection_blind_budget_three": _score_summary(
            run["best_score"] for run in blind3 if run.get("best_score") is not None
        ),
        "proposal_trajectory_health": {
            "normal_budget_one": _proposal_trajectory_health(b1),
            "normal_budget_three": _proposal_trajectory_health(b3),
            "selection_blind_budget_three": _proposal_trajectory_health(blind3),
        },
        "matched_control_cohorts": matched[:3],
        "maximum_matched_control_replicates": (
            matched[0]["matched_replicate_count"] if matched else 0
        ),
        "post_first_valid_gain": {
            "run_count": len(gains),
            "mean": (sum(gains) / len(gains)) if gains else None,
            "maximum": max(gains) if gains else None,
            "material_gain_threshold": 0.05,
            "material_gain_count": sum(gain >= 0.05 for gain in gains),
            "runs": gain_rows[:10],
        },
        "observed_budget_one_at_or_above_0_95": bool(
            b1 and any(
                run.get("best_score") is not None and run["best_score"] >= 0.95
                for run in b1
            )
        ),
    }


def _fresh_confirmation_tasks(
    documents: dict[str, dict[str, Any]], inventory_ids: set[str],
    head_revision: str, migrations: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = defaultdict(list)
    relative = GLOBAL_REPORTS["track_f_confirmation"]
    document = documents.get(relative, {})
    if not _trusted_document(document):
        return result
    counts = Counter(
        row.get("task") for row in document.get("panel_audits", [])
        if isinstance(row, dict) and row.get("task") in inventory_ids
        and isinstance(row.get("audit"), dict) and row["audit"].get("passed") is True
    )
    source_revision = str((document.get("source_provenance") or {}).get("git_revision") or "")
    for task_id, panel_count in counts.items():
        binding, migration_audit = _binding_state(
            source_revision, task_id, head_revision, migrations
        )
        result[task_id].append({
            "path": relative,
            "sha256": _sha256(ROOT / relative),
            "source_revision": source_revision,
            "contract_binding": binding,
            "migration_audit": migration_audit,
            "fresh_panel_count": panel_count,
            "deterministic_replay": (
                (document.get("completion") or {}).get("stochastic_artifacts") == 0
                and (document.get("completion") or {}).get("incomplete_or_infrastructure_failed_evaluations") == 0
            ),
        })
    return result


def _global_ref(relative: str, document: dict[str, Any]) -> dict[str, Any]:
    path = ROOT / relative
    return {
        "path": relative,
        "sha256": _sha256(path),
        "source_revision": (document.get("source_provenance") or {}).get("git_revision"),
        "trusted_evidence": document.get("trusted_evidence") is True,
        "execution_passed": document.get("execution_passed") is True,
        "trust_decision": document.get("trust_decision"),
    }


def _gate(passed: bool, blockers: list[str]) -> dict[str, Any]:
    unique = list(dict.fromkeys(blockers))
    return {"passed": bool(passed and not unique), "blockers": unique}


def _current_full_suite_issues(
    document: dict[str, Any], head_revision: str
) -> list[str]:
    provenance = document.get("source_provenance") or {}
    suite_revision = str(provenance.get("git_revision") or "")
    source_changes = _git([
        "diff", "--name-only", suite_revision, head_revision,
        "--", *SOURCE_SCOPE,
    ]) if suite_revision and _git_commit_exists(suite_revision) else ""
    suite_is_ancestor = bool(
        suite_revision
        and subprocess.run(
            ["git", "merge-base", "--is-ancestor", suite_revision, head_revision],
            cwd=str(ROOT), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        ).returncode == 0
    )
    if not (
        _trusted_document(document)
        and document.get("unittest_ok") is True
        and int(document.get("test_count", 0)) > 0
        and provenance.get("source_tree_dirty") is False
        and suite_is_ancestor
        and source_changes == ""
    ):
        return ["full test suite is not trusted and bound to the audited revision"]
    return []


def build_report(full_test_suite: Optional[str] = None) -> dict[str, Any]:
    global_reports = dict(GLOBAL_REPORTS)
    if full_test_suite is not None:
        global_reports["full_test_suite"] = str(full_test_suite)
    specs = list_tasks(None)
    inventory_ids = {spec.task_id for spec in specs}
    head_revision = _git(["rev-parse", "HEAD"], check=True)
    documents: dict[str, dict[str, Any]] = {}
    for path in _tracked_json_paths(global_reports.values()):
        document = _load_json(path)
        if document is not None:
            documents[str(path.relative_to(ROOT))] = document

    missing_global = [name for name in global_reports.values() if name not in documents]
    migrations = _migration_contracts(documents)
    model_runs = _model_run_records(documents, inventory_ids, head_revision, migrations)
    fresh = _fresh_confirmation_tasks(documents, inventory_ids, head_revision, migrations)

    evidence_by_task: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for relative, document in documents.items():
        if not _trusted_document(document):
            continue
        path = ROOT / relative
        for task_id in _walk_task_ids(document, inventory_ids):
            evidence_by_task[task_id].append(
                _evidence_ref(path, document, task_id, head_revision, migrations)
            )

    baseline_document = documents.get(GLOBAL_REPORTS["secure_baseline"], {})
    baseline_rows = {
        row.get("task"): row for row in baseline_document.get("tasks", [])
        if isinstance(row, dict) and row.get("task") in inventory_ids
    }
    certification_document = documents.get(GLOBAL_REPORTS["certification"], {})
    certification_rows = {
        row.get("task"): row for row in certification_document.get("tasks", [])
        if isinstance(row, dict) and row.get("task") in inventory_ids
    }
    quarantine_document = documents.get(
        GLOBAL_REPORTS["quarantined_reaudit"], {}
    )
    quarantine_source = str(
        (quarantine_document.get("source_provenance") or {}).get(
            "git_revision"
        ) or ""
    )
    quarantine_rows = {
        row.get("task"): row
        for row in quarantine_document.get("records", [])
        if isinstance(row, dict) and row.get("task") in inventory_ids
    }

    task_records = []
    for spec in specs:
        task_id = spec.task_id
        certification = certification_record(task_id)
        raw_card, card = _card_state(spec.task_dir)
        measurement = _measurement_state(model_runs.get(task_id, []))
        evidence = evidence_by_task.get(task_id, [])
        evidence.sort(key=lambda row: (
            {"current_contract_bound": 0, "migration_replayed": 1,
             "historical_only": 2, "unbound": 3}[row["contract_binding"]],
            row["kind"], row["path"],
        ))
        evidence_summary = Counter(row["contract_binding"] for row in evidence)
        by_kind: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in evidence:
            by_kind[row["kind"]].append(row)

        baseline = baseline_rows.get(task_id)
        baseline_binding = "unbound"
        baseline_migration = None
        if baseline is not None:
            baseline_source = str(
                (baseline_document.get("source_provenance") or {}).get("git_revision") or ""
            )
            baseline_binding, baseline_migration = _binding_state(
                baseline_source, task_id, head_revision, migrations
            )
        track_f_baseline_fallback = bool(
            task_id in fresh
            and measurement["current_or_migrated_run_count"] >= 48
            and all(item["deterministic_replay"] for item in fresh[task_id])
        )
        baseline_passed = bool(
            baseline is not None
            and baseline_binding in {"current_contract_bound", "migration_replayed"}
            and baseline.get("deterministic") is True
            and baseline.get("valid_all") is True
            and baseline.get("fail_closed_all") is True
            and baseline.get("infrastructure_failure") is False
        ) or track_f_baseline_fallback

        quarantine_row = quarantine_rows.get(task_id)
        quarantine_binding = "unbound"
        quarantine_migration = None
        if quarantine_row is not None:
            quarantine_binding, quarantine_migration = _binding_state(
                quarantine_source, task_id, head_revision, migrations
            )
        quarantine_reaudit_passed = bool(
            certification.get("status") == "quarantined"
            and _trusted_document(quarantine_document)
            and quarantine_row is not None
            and quarantine_binding in {
                "current_contract_bound", "migration_replayed",
            }
            and quarantine_row.get("certification_status") == "quarantined"
            and quarantine_row.get("defect_reproduced") is True
            and quarantine_row.get("meets_internal_benchmark_standard") is False
            and quarantine_row.get("recommendation")
            == "retain_quarantine_until_substantive_rebuild"
        )

        calibration_evidence = [
            row for row in evidence
            if row["kind"] in {
                "admission", "analysis", "calibration",
                "independent_numerical_crosscheck", "model_run",
            }
            and row["contract_binding"] in {"current_contract_bound", "migration_replayed"}
        ]
        fresh_current = [
            row for row in fresh.get(task_id, [])
            if row["contract_binding"] in {"current_contract_bound", "migration_replayed"}
            and row["deterministic_replay"]
        ]

        internal_blockers = []
        if certification.get("status") not in ADMISSIBLE_STATUSES:
            internal_blockers.append("certification_status_is_quarantined")
        if card["schema_issues"]:
            internal_blockers.append("task_card_schema_failed")
        cert_row = certification_rows.get(task_id)
        if cert_row is None or cert_row.get("issues"):
            internal_blockers.append("current_certification_record_failed")
        if not baseline_passed:
            internal_blockers.append("no_current_or_migration_replayed_deterministic_baseline")
        internal = _gate(not internal_blockers, internal_blockers)

        release_blockers = []
        if not internal["passed"]:
            release_blockers.append("internal_science_admission_failed")
        if not card["domain_review_complete"]:
            release_blockers.append("external_domain_review_pending")
        if not card["builder_lineage_complete"]:
            release_blockers.append("builder_and_calibrator_lineage_incomplete")
        if not card["provenance_class_declared"]:
            release_blockers.append("known_answer_procedural_or_prospective_provenance_missing")
        if not card["novelty_risk_declared"]:
            release_blockers.append("novelty_risk_missing")
        if not card["generalization_declared"]:
            release_blockers.append("heldout_sealed_or_procedural_generalization_not_declared")
        if not calibration_evidence:
            release_blockers.append("no_current_or_migration_replayed_task_calibration")
        if measurement["current_or_migrated_run_count"] == 0:
            release_blockers.append("no_current_or_migration_replayed_model_measurement")
        release = _gate(not release_blockers, release_blockers)

        external_blockers = []
        if not release["passed"]:
            external_blockers.append("open_release_ready_failed")
        if not card["external_validation_complete"]:
            external_blockers.append("independent_external_or_physical_validation_missing")
        external = _gate(not external_blockers, external_blockers)

        long_blockers = []
        if not release["passed"]:
            long_blockers.append("open_release_ready_failed")
        if measurement["maximum_matched_control_replicates"] < 3:
            long_blockers.append("fewer_than_three_matched_normal_selection_blind_replicates")
        if not fresh_current:
            long_blockers.append("fresh_postcommit_confirmation_missing")
        long_horizon = (
            raw_card.get("long_horizon")
            if isinstance(raw_card.get("long_horizon"), dict) else {}
        )
        if long_horizon.get("measurement_health_passed") is not True:
            long_blockers.append("measurement_health_gate_not_passed")
        if long_horizon.get("material_headroom_after_2h") is not True:
            long_blockers.append("material_post_2h_headroom_not_demonstrated")
        long_ready = _gate(not long_blockers, long_blockers)

        task_records.append({
            "task": task_id,
            "certification_status": certification.get("status"),
            "certification_reason": certification.get("reason"),
            "difficulty": spec.metadata.get("difficulty"),
            "oracle_type": spec.metadata.get("oracle_type"),
            "science_metric": spec.metadata.get("science_metric"),
            "current_contract_sha256": _contract_sha256(spec.task_dir),
            "task_card": card,
            "baseline_evidence": {
                "path": GLOBAL_REPORTS["secure_baseline"] if baseline is not None else None,
                "contract_binding": baseline_binding,
                "migration_audit": baseline_migration,
                "deterministic": baseline.get("deterministic") if baseline else None,
                "valid_all": baseline.get("valid_all") if baseline else None,
                "fail_closed_all": baseline.get("fail_closed_all") if baseline else None,
                "infrastructure_failure": baseline.get("infrastructure_failure") if baseline else None,
                "track_f_current_fallback": track_f_baseline_fallback,
                "passed": baseline_passed,
            },
            "quarantine_reaudit": {
                "path": (
                    GLOBAL_REPORTS["quarantined_reaudit"]
                    if quarantine_row is not None else None
                ),
                "contract_binding": quarantine_binding,
                "migration_audit": quarantine_migration,
                "defect_reproduced": (
                    quarantine_row.get("defect_reproduced")
                    if quarantine_row else None
                ),
                "meets_internal_benchmark_standard": (
                    quarantine_row.get("meets_internal_benchmark_standard")
                    if quarantine_row else None
                ),
                "recommendation": (
                    quarantine_row.get("recommendation")
                    if quarantine_row else None
                ),
                "passed": quarantine_reaudit_passed,
            },
            "evidence_binding_counts": {
                state: evidence_summary.get(state, 0) for state in sorted(BINDING_STATES)
            },
            "evidence": {
                kind: rows[:5] for kind, rows in sorted(by_kind.items())
            },
            "model_measurement": measurement,
            "fresh_confirmation": fresh_current,
            "gates": {
                "internal_science_admission": internal,
                "open_release_ready": release,
                "externally_validated": external,
                "long_horizon_ready": long_ready,
            },
        })

    gate_names = (
        "internal_science_admission",
        "open_release_ready",
        "externally_validated",
        "long_horizon_ready",
    )
    gate_counts = {
        gate: sum(record["gates"][gate]["passed"] for record in task_records)
        for gate in gate_names
    }
    status_counts = Counter(record["certification_status"] for record in task_records)
    coverage = {
        "valid_task_card_count": sum(not row["task_card"]["schema_issues"] for row in task_records),
        "current_baseline_count": sum(row["baseline_evidence"]["passed"] for row in task_records),
        "current_model_measurement_count": sum(
            row["model_measurement"]["current_or_migrated_run_count"] > 0
            for row in task_records
        ),
        "normal_budget_one_task_count": sum(
            row["model_measurement"]["normal_budget_one"] is not None for row in task_records
        ),
        "normal_budget_three_task_count": sum(
            row["model_measurement"]["normal_budget_three"] is not None for row in task_records
        ),
        "selection_blind_budget_three_task_count": sum(
            row["model_measurement"]["selection_blind_budget_three"] is not None
            for row in task_records
        ),
        "matched_control_at_least_three_task_count": sum(
            row["model_measurement"]["maximum_matched_control_replicates"] >= 3
            for row in task_records
        ),
        "fresh_confirmation_task_count": sum(bool(row["fresh_confirmation"]) for row in task_records),
        "domain_review_complete_task_count": sum(
            row["task_card"]["domain_review_complete"] for row in task_records
        ),
        "builder_lineage_declared_task_count": sum(
            row["task_card"]["builder_lineage_declared"] for row in task_records
        ),
        "builder_lineage_complete_task_count": sum(
            row["task_card"]["builder_lineage_complete"] for row in task_records
        ),
        "provenance_class_declared_task_count": sum(
            row["task_card"]["provenance_class_declared"] for row in task_records
        ),
        "novelty_risk_declared_task_count": sum(
            row["task_card"]["novelty_risk_declared"] for row in task_records
        ),
        "observed_budget_one_at_or_above_0_95_task_count": sum(
            row["model_measurement"]["observed_budget_one_at_or_above_0_95"]
            for row in task_records
        ),
        "declared_post_2h_headroom_task_count": sum(
            "material_post_2h_headroom_not_demonstrated"
            not in row["gates"]["long_horizon_ready"]["blockers"]
            for row in task_records
        ),
        "current_quarantine_defect_reproduction_count": sum(
            row["quarantine_reaudit"]["passed"] for row in task_records
        ),
    }

    issues = []
    if missing_global:
        issues.append("missing required global reports: %s" % ", ".join(missing_global))
    if full_test_suite is not None:
        issues.extend(_current_full_suite_issues(
            documents.get(global_reports["full_test_suite"], {}),
            head_revision,
        ))
    if len(task_records) != len(inventory_ids):
        issues.append("task record count does not match inventory")
    if sum(status_counts.values()) != len(task_records):
        issues.append("status counts do not match task records")
    if any(
        binding not in BINDING_STATES
        for row in task_records for binding in row["evidence_binding_counts"]
    ):
        issues.append("unknown evidence binding state")
    if gate_counts["internal_science_admission"] != (
        status_counts.get("certified", 0) + status_counts.get("candidate", 0)
    ):
        issues.append("internal admission count diverges from audited nonquarantined risk set")
    current_quarantined = {
        row["task"] for row in task_records
        if row["certification_status"] == "quarantined"
    }
    if not _trusted_document(quarantine_document):
        issues.append("quarantined task reaudit is missing or untrusted")
    if set(quarantine_rows) != current_quarantined:
        issues.append("quarantined task reaudit coverage differs from current manifest")
    quarantine_summary = quarantine_document.get("summary") or {}
    if not (
        quarantine_summary.get("manifest_quarantined_count")
        == len(current_quarantined)
        and quarantine_summary.get("audited_count")
        == len(current_quarantined)
        and quarantine_summary.get("reproduced_defect_count")
        == len(current_quarantined)
        and quarantine_summary.get("meets_internal_benchmark_standard_count") == 0
    ):
        issues.append("quarantined task reaudit summary is inconsistent")
    if coverage["current_quarantine_defect_reproduction_count"] != len(
        current_quarantined
    ):
        issues.append("not every quarantined task has current reproduced defect evidence")

    report: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "trust_status": "TRUSTED_TASK_MATURITY_LEDGER",
        "evidence_scope": (
            "CONSERVATIVE_TASK_MATURITY_AND_EVIDENCE_BINDING_AUDIT_NOT_EXTERNAL_"
            "DOMAIN_REVIEW_PHYSICAL_VALIDATION_LONG_HORIZON_RESULT_OR_AUTONOMOUS_DISCOVERY_EVIDENCE"
        ),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_provenance": source_provenance(ROOT),
        "environment": {"python": sys.version, "platform": platform.platform()},
        "policy": {
            "binding_states": sorted(BINDING_STATES),
            "current_contract_scope": list(TASK_CONTRACT_PATHS),
            "tracked_reports_only": True,
            "required_current_full_test_suite": (
                global_reports["full_test_suite"]
                if full_test_suite is not None else None
            ),
            "internal_science_admission": [
                "certified or candidate status",
                "valid task card and current certification record",
                "current-contract or migration-replayed deterministic valid fail-closed baseline",
            ],
            "open_release_ready": [
                "internal science admission",
                "completed external domain review",
                "builder/calibrator lineage and freeze declaration",
                "known-answer/procedural/public-data/prospective provenance and novelty-risk declaration",
                "held-out, sealed, shifted, procedural or fresh generalization declaration",
                "current-contract or migration-replayed task calibration and model measurement",
            ],
            "externally_validated": [
                "open release ready",
                "explicit independent external, high-fidelity, field or physical validation",
            ],
            "long_horizon_ready": [
                "open release ready",
                "at least three matched normal and selection-blind repetitions",
                "fresh post-commit confirmation",
                "passed measurement-health gate",
                "demonstrated material headroom after two hours",
            ],
            "important_limits": [
                "A single budget-one score at or above 0.95 is an observed saturation warning, not a population estimate.",
                "Single-seed budget-one/budget-three/blind runs are calibration evidence, not feedback-causal evidence.",
                "Internal certification and a complete task card are not external scientific validation.",
                "Fresh procedural simulator replay is not laboratory or physical confirmation.",
            ],
        },
        "head_revision": head_revision,
        "global_evidence": {
            key: _global_ref(relative, documents[relative])
            for key, relative in global_reports.items() if relative in documents
        },
        "migration_contracts": migrations,
        "inventory_count": len(task_records),
        "status_counts": {
            status: status_counts.get(status, 0)
            for status in ("certified", "candidate", "quarantined")
        },
        "gate_counts": gate_counts,
        "evidence_coverage": coverage,
        "issues": issues,
        "tasks": task_records,
    }
    finalize_report_trust(report, not issues)
    return report


def render_markdown(report: dict[str, Any]) -> str:
    gates = report["gate_counts"]
    coverage = report["evidence_coverage"]
    lines = [
        "# Task maturity ledger",
        "",
        "Generated from tracked, trusted reports at source revision `%s`. Evidence is task-contract" % report["head_revision"],
        "bound as `current_contract_bound`, `migration_replayed`, `historical_only`, or `unbound`.",
        "Maturity gates are cumulative policy claims, not synonyms for registry status.",
        "",
        "## Current counts",
        "",
        "| Gate | Passed | Meaning |",
        "|---|---:|---|",
        "| Internal science admission | %d | Runnable internal risk set with card, certification and baseline gates |" % gates["internal_science_admission"],
        "| Open release ready | %d | Adds domain review, lineage, provenance/novelty and current measurement gates |" % gates["open_release_ready"],
        "| Externally validated | %d | Adds explicit independent external/high-fidelity/physical validation |" % gates["externally_validated"],
        "| Long-horizon ready | %d | Adds repeated controls, fresh confirmation, measurement health and post-2h headroom |" % gates["long_horizon_ready"],
        "",
        "Registry status remains `%d certified / %d candidate / %d quarantined`; it is not a maturity count." % (
            report["status_counts"]["certified"], report["status_counts"]["candidate"],
            report["status_counts"]["quarantined"],
        ),
        "",
        "## Evidence coverage",
        "",
        "| Evidence | Tasks |",
        "|---|---:|",
        "| Valid task card | %d |" % coverage["valid_task_card_count"],
        "| Current/migration-safe baseline | %d |" % coverage["current_baseline_count"],
        "| Current/migration-safe model measurement | %d |" % coverage["current_model_measurement_count"],
        "| Normal budget-one | %d |" % coverage["normal_budget_one_task_count"],
        "| Normal budget-three | %d |" % coverage["normal_budget_three_task_count"],
        "| Selection-blind budget-three | %d |" % coverage["selection_blind_budget_three_task_count"],
        "| Matched controls with at least three repetitions | %d |" % coverage["matched_control_at_least_three_task_count"],
        "| Fresh post-commit confirmation | %d |" % coverage["fresh_confirmation_task_count"],
        "| Completed external domain review | %d |" % coverage["domain_review_complete_task_count"],
        "| Builder/calibrator lineage declared | %d |" % coverage["builder_lineage_declared_task_count"],
        "| Builder/calibrator lineage complete | %d |" % coverage["builder_lineage_complete_task_count"],
        "| Provenance class declared | %d |" % coverage["provenance_class_declared_task_count"],
        "| Novelty risk declared | %d |" % coverage["novelty_risk_declared_task_count"],
        "| Declared material post-2h headroom | %d |" % coverage["declared_post_2h_headroom_task_count"],
        "| Current/migration-safe quarantine defect reproduction | %d |" % coverage["current_quarantine_defect_reproduction_count"],
        "",
        "## Per-task audit",
        "",
        "`b1/b3/blind` are current-contract or explicitly migration-replayed run counts. `controls` is",
        "the largest matched normal/selection-blind cohort; it does not turn local seed labels into",
        "paired provider randomness. `fresh` means frozen post-search procedural confirmation, not a lab test.",
        "",
        "| Task | Status | Internal | b1 | b3 | blind | controls | fresh | budget-one >=0.95 | First release blockers |",
        "|---|---|:---:|---:|---:|---:|---:|:---:|:---:|---|",
    ]
    for row in report["tasks"]:
        measurement = row["model_measurement"]
        blocker_text = "; ".join(row["gates"]["open_release_ready"]["blockers"][:3]) or "none"
        lines.append(
            "| %s | %s | %s | %d | %d | %d | %d | %s | %s | %s |" % (
                row["task"], row["certification_status"],
                "yes" if row["gates"]["internal_science_admission"]["passed"] else "no",
                (measurement["normal_budget_one"] or {}).get("n", 0),
                (measurement["normal_budget_three"] or {}).get("n", 0),
                (measurement["selection_blind_budget_three"] or {}).get("n", 0),
                measurement["maximum_matched_control_replicates"],
                "yes" if row["fresh_confirmation"] else "no",
                "yes" if measurement["observed_budget_one_at_or_above_0_95"] else "no",
                blocker_text.replace("_", " "),
            )
        )

    repeated = [
        row["task"] for row in report["tasks"]
        if row["model_measurement"]["maximum_matched_control_replicates"] >= 3
    ]
    fresh_tasks = [row["task"] for row in report["tasks"] if row["fresh_confirmation"]]
    missing_model = [
        row["task"] for row in report["tasks"]
        if row["certification_status"] in ADMISSIBLE_STATUSES
        and row["model_measurement"]["current_or_migrated_run_count"] == 0
    ]
    saturation = [
        row["task"] for row in report["tasks"]
        if row["model_measurement"]["observed_budget_one_at_or_above_0_95"]
    ]
    lines.extend([
        "",
        "## Immediate implications",
        "",
        "- Repeated matched-control evidence currently covers: %s." % (", ".join(repeated) or "none"),
        "- Fresh confirmation currently covers: %s." % (", ".join(fresh_tasks) or "none"),
        "- Admissible tasks without current/migration-safe model measurement: %s." % (", ".join(missing_model) or "none"),
        "- Tasks with at least one observed current budget-one score >=0.95: %s. This is a warning, not a reliable saturation rate." % (", ".join(saturation) or "none"),
        "- No task can inherit external validation or long-horizon readiness from internal registry status.",
        "",
        "The machine-readable JSON is authoritative for full blockers, evidence hashes, source revisions,",
        "contract binding states and migration-audit links.",
        "",
    ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    parser.add_argument("--markdown-output", type=Path)
    parser.add_argument(
        "--full-test-suite",
        help="require this tracked passing suite to match the audited revision",
    )
    args = parser.parse_args()
    report = build_report(full_test_suite=args.full_test_suite)
    rendered = json.dumps(report, indent=2, allow_nan=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    if args.markdown_output:
        args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
        args.markdown_output.write_text(render_markdown(report), encoding="utf-8")
    print(json.dumps({
        "inventory_count": report["inventory_count"],
        "status_counts": report["status_counts"],
        "gate_counts": report["gate_counts"],
        "evidence_coverage": report["evidence_coverage"],
        "issues": report["issues"],
        "execution_passed": report["execution_passed"],
        "trusted_evidence": report["trusted_evidence"],
    }, indent=2))
    return 0 if report["execution_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

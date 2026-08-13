#!/usr/bin/env python3
"""Build the fixed Track F preregistration from trusted design artifacts.

This builder runs only on a clean source revision.  It binds the exact model
condition, task contracts, precision plan, fresh-panel public commitment,
pre-search verification reports, balanced Williams schedule, fixed stopping
rule and the byte hash of the final analyzer.  The output contains no model or
confirmation outcomes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sle.algorithms.common import (  # noqa: E402
    atomic_write_text,
    llm_condition_sha256,
    runtime_source_sha256,
    task_contract_sha256,
)
from sle.config import load_llm_client  # noqa: E402
from sle.provenance import source_provenance  # noqa: E402
from sle.registry import find_task  # noqa: E402


TASKS = (
    "DynamicalSystems/ActiveLawDiscovery",
    "Optics/DiffractionGratingDesign",
)
MODES = (
    "normal", "score_only", "delayed_replay", "selection_blind",
)
WILLIAMS_ROWS = (
    (0, 1, 3, 2),
    (1, 2, 0, 3),
    (2, 3, 1, 0),
    (3, 0, 2, 1),
)
ANALYZER = ROOT / "scripts" / "analyze_track_f_confirmation.py"


def _sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _relative_or_absolute(path: Path) -> str:
    resolved = Path(path).expanduser().resolve()
    try:
        return str(resolved.relative_to(ROOT))
    except ValueError:
        return str(resolved)


def condition_schedule(
    replicates: list[int], randomization_seed: int,
) -> list[dict[str, Any]]:
    if (
        not replicates
        or len(set(replicates)) != len(replicates)
        or not isinstance(randomization_seed, int)
        or isinstance(randomization_seed, bool)
    ):
        raise ValueError("invalid Williams schedule inputs")
    row_indices = [index % len(WILLIAMS_ROWS) for index in range(len(replicates))]
    random.Random(randomization_seed).shuffle(row_indices)
    return [
        {
            "replicate_identifier": replicate,
            "feedback_modes": [MODES[position] for position in WILLIAMS_ROWS[row]],
        }
        for replicate, row in zip(replicates, row_indices)
    ]


def _load(path: Path, label: str) -> dict[str, Any]:
    try:
        document = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("cannot load %s" % label) from exc
    if not isinstance(document, dict):
        raise ValueError("%s must be a JSON object" % label)
    return document


def _trusted_report(
    path: Path, label: str, revision: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    document = _load(path, label)
    provenance = document.get("source_provenance") or {}
    if not (
        document.get("schema_version") == 1
        and document.get("execution_passed") is True
        and document.get("trusted_evidence") is True
        and document.get("passed") is True
        and provenance.get("source_tree_dirty") is False
        and provenance.get("git_revision") == revision
    ):
        raise ValueError("%s is not trusted evidence on the frozen revision" % label)
    return document, {
        "path": _relative_or_absolute(path),
        "sha256": _sha256(path),
        "bytes": len(Path(path).read_bytes()),
    }


def build(
    *,
    precision_path: Path,
    commitment_path: Path,
    full_suite_path: Path,
    security_path: Path,
    certification_path: Path,
    smoke_path: Path,
    search_report_path: Path,
    search_work_root: Path,
    condition_order_randomization_seed: int,
    confirmation_randomization_seed: int,
    search_block_workers: int,
    confirmation_workers: int,
    llm_config: str | None,
) -> dict[str, Any]:
    provenance = source_provenance(ROOT)
    if not (
        provenance.get("git_available") is True
        and provenance.get("source_tree_dirty") is False
    ):
        raise ValueError("Track F preregistration requires a clean source revision")
    if (
        not isinstance(search_block_workers, int)
        or isinstance(search_block_workers, bool)
        or search_block_workers < 1
        or not isinstance(confirmation_workers, int)
        or isinstance(confirmation_workers, bool)
        or confirmation_workers < 1
    ):
        raise ValueError("Track F worker counts must be positive integers")
    revision = provenance["git_revision"]
    precision, precision_binding = _trusted_report(
        precision_path, "precision plan", revision
    )
    full_suite, full_suite_binding = _trusted_report(
        full_suite_path, "full test suite", revision
    )
    security, security_binding = _trusted_report(
        security_path, "security audit", revision
    )
    certification, certification_binding = _trusted_report(
        certification_path, "certification audit", revision
    )
    commitment = _load(commitment_path, "public confirmation commitment")
    fixed_n = precision.get("fixed_balanced_blocks_per_condition")
    precision_design = precision.get("design") or {}
    if not (
        isinstance(fixed_n, int)
        and not isinstance(fixed_n, bool)
        and fixed_n > 0
        and fixed_n % 4 == 0
        and precision.get("scheduled_search_cells")
        == len(TASKS) * len(MODES) * fixed_n
        and precision.get("scheduled_model_proposals")
        == len(TASKS) * len(MODES) * fixed_n * 3
        and precision_design.get("primary_task") == TASKS[0]
        and precision_design.get("primary_contrast")
        == "normal_minus_selection_blind"
        and precision_design.get("primary_horizon")
        == "common_total_token_horizon"
        and precision_design.get("primary_fresh_confirmation_axis")
        == "confirmation_normalized_mechanism_score"
        and precision_design.get("secondary_stress_test_task") == TASKS[1]
        and precision_design.get("secondary_fresh_confirmation_axis")
        == "confirmation_robustness_score"
        and precision_design.get("provider_draw_assumption")
        == "independent_unpaired"
        and precision_design.get("same_local_identifier_is_paired_seed") is False
        and precision_design.get("confirmatory_primary_hypothesis_count") == 1
        and certification.get("inventory_count") == 59
        and certification.get("status_counts")
        == {"certified": 7, "candidate": 43, "quarantined": 9}
        and full_suite.get("unittest_ok") is True
        and int(full_suite.get("test_count", 0)) > 0
        and int(security.get("test_count", 0)) > 0
    ):
        raise ValueError("Track F design prerequisites differ from the fixed protocol")
    task_rows = []
    commitment_tasks = {
        row.get("task"): row
        for row in (commitment.get("source_binding") or {}).get("tasks") or []
    }
    for task in TASKS:
        spec = find_task(task, include_uncertified=True)
        row = commitment_tasks.get(task) or {}
        contract = task_contract_sha256(spec)
        if row.get("task_contract_sha256") != contract:
            raise ValueError("confirmation commitment task contract differs")
        task_rows.append({
            "task": task,
            "task_contract_sha256": contract,
            "confirmation_generator": row.get("generator"),
            "confirmation_world_count": row.get("world_count"),
            "scientific_role": (
                "fresh active mechanism recovery, prediction, false discovery and unsupported-model refusal"
                if task == TASKS[0]
                else "fresh RCWA material/wavelength/angle/fabrication robustness stress test"
            ),
        })
    expected_blocks = len(TASKS) * fixed_n
    public_blocks = commitment.get("blocks") or []
    public_keys = [
        (row.get("task"), row.get("replicate_id")) for row in public_blocks
    ]
    expected_public_keys = {
        (task, replicate) for task in TASKS for replicate in range(fixed_n)
    }
    task_binding_index = commitment_tasks
    private_digest = commitment.get("private_manifest_sha256")
    if not (
        commitment.get("schema_version") == 1
        and commitment.get("commitment_version") == 1
        and commitment.get("purpose")
        == "track_f_fresh_confirmation_context_commitment"
        and commitment.get("block_count") == expected_blocks
        and len(public_blocks) == expected_blocks
        and len(set(public_keys)) == len(public_keys)
        and set(public_keys) == expected_public_keys
        and len(commitment_tasks) == len(TASKS)
        and set(commitment_tasks) == set(TASKS)
        and isinstance(private_digest, str)
        and len(private_digest) == 64
        and all(character in "0123456789abcdef" for character in private_digest)
        and all(
            isinstance(row.get("context_sha256"), str)
            and len(row["context_sha256"]) == 64
            and all(
                character in "0123456789abcdef"
                for character in row["context_sha256"]
            )
            and isinstance(row.get("context_utf8_bytes"), int)
            and not isinstance(row.get("context_utf8_bytes"), bool)
            and row["context_utf8_bytes"] > 0
            and row.get("generator")
            == task_binding_index[row["task"]]["generator"]
            and row.get("world_count")
            == task_binding_index[row["task"]]["world_count"]
            and isinstance(row.get("panel_id"), str)
            and bool(row["panel_id"])
            for row in public_blocks
        )
        and (commitment.get("source_binding") or {}).get("git_revision") == revision
        and (commitment.get("source_binding") or {}).get("runtime_source_sha256")
        == runtime_source_sha256()
        and (commitment.get("source_provenance") or {}).get("source_tree_dirty")
        is False
    ):
        raise ValueError("public confirmation commitment differs from the fixed cohort")
    replicates = list(range(fixed_n))
    schedule = condition_schedule(
        replicates, condition_order_randomization_seed
    )
    llm = load_llm_client(llm_config)
    llm_hash = llm_condition_sha256(llm)
    endpoint_hash = hashlib.sha256(
        llm.config.base_url.encode("utf-8")
    ).hexdigest()
    commitment_binding = {
        "path": _relative_or_absolute(commitment_path),
        "sha256": _sha256(commitment_path),
        "bytes": len(Path(commitment_path).read_bytes()),
        "private_manifest_sha256": commitment["private_manifest_sha256"],
        "private_manifest_utf8_bytes": commitment[
            "private_manifest_utf8_bytes"
        ],
        "block_count": commitment["block_count"],
    }
    return {
        "schema_version": 1,
        "preregistration_version": 1,
        "purpose": "track_f_feedback_confirmatory_study",
        "frozen_at_utc": datetime.now(timezone.utc).isoformat(),
        "claim_limit": (
            "specific_active_law_procedural_feedback_primary_with_diffraction_"
            "secondary_not_general_physical_or_autonomous_discovery_evidence"
        ),
        "frozen_source": {
            "revision": revision,
            "runtime_source_sha256": runtime_source_sha256(),
            "source_scope": provenance.get("source_scope"),
            "source_change_rule": (
                "Any later change under source_provenance SOURCE_SCOPE invalidates "
                "the frozen cohort; descendant evidence is accepted only when the "
                "SOURCE_SCOPE diff is empty."
            ),
        },
        "model_condition": {
            "llm_condition_sha256": llm_hash,
            "wire": llm.config.wire,
            "endpoint_sha256": endpoint_hash,
            "model": llm.config.model,
            "max_output_tokens": llm.config.max_output_tokens,
            "temperature": llm.config.temperature,
            "reasoning_effort": llm.config.reasoning_effort,
            "timeout_seconds": llm.config.timeout_seconds,
            "server_side_seed_control": False,
            "replicate_identifier_scope": (
                "local Python/random ordering only; equal identifiers do not pair "
                "provider-side model draws"
            ),
        },
        "precision_plan": precision_binding,
        "confirmation_commitment": commitment_binding,
        "analysis_implementation": {
            "path": str(ANALYZER.relative_to(ROOT)),
            "sha256": _sha256(ANALYZER),
            "bytes": len(ANALYZER.read_bytes()),
        },
        "design": {
            "tasks": task_rows,
            "algorithm": "greedy_rewrite",
            "feedback_modes": list(MODES),
            "replicate_identifiers": replicates,
            "fixed_blocks_per_condition": fixed_n,
            "condition_order": "balanced_williams",
            "condition_order_randomization_seed": (
                condition_order_randomization_seed
            ),
            "condition_order_schedule": schedule,
            "proposal_budget": 3,
            "evaluator_timeout_seconds": 300.0,
            "scheduled_cell_count": len(TASKS) * len(MODES) * fixed_n,
            "scheduled_model_proposals": len(TASKS) * len(MODES) * fixed_n * 3,
            "confirmation_replays_per_artifact": 2,
            "confirmation_randomization_seed": confirmation_randomization_seed,
            "search_block_workers": search_block_workers,
            "search_parallelism_unit": "task_algorithm_replicate",
            "search_within_block_conditions": (
                "serial_in_condition_order_schedule"
            ),
            "confirmation_workers": confirmation_workers,
            "confirmation_worker_isolation": "spawn_process",
            "confirmation_look_assignment": "planned_order_before_dispatch",
            "confirmation_endpoint_count": (
                len(TASKS) * len(MODES) * fixed_n * 2
            ),
            "confirmation_endpoints": [
                "full_proposal_horizon", "common_total_token_horizon",
            ],
        },
        "analysis": {
            "primary_task": TASKS[0],
            "primary_condition": "normal",
            "primary_control": "selection_blind",
            "primary_contrast": "normal_minus_selection_blind",
            "primary_endpoint": "common_total_token_horizon",
            "primary_axis": "confirmation_normalized_mechanism_score",
            "statistical_test": "two_sided_independent_welch_t",
            "two_sided_alpha": precision_design["two_sided_alpha"],
            "confirmatory_primary_hypothesis_count": 1,
            "minimum_important_difference": precision_design[
                "minimum_important_difference"
            ],
            "mde_role": "power_target_not_additional_significance_threshold",
            "provider_draw_assumption": "independent_unpaired",
            "candidate_invalid_score": 0.0,
            "secondary_task": TASKS[1],
            "secondary_axis": "confirmation_robustness_score",
            "secondary_inference": "descriptive_stress_test_only",
            "other_conditions_and_full_horizon": (
                "descriptive_secondary_no_multiplicity_claim"
            ),
            "cross_task_score": None,
        },
        "failure_retry_and_stopping": {
            "fixed_sample": True,
            "sample_size_adaptation": False,
            "interim_efficacy_or_futility_analysis": False,
            "outcome_based_early_stopping": False,
            "search_risk_set": "all 384 cells",
            "candidate_invalidity": (
                "terminal scientific outcome retained at normalized score floor zero"
            ),
            "infrastructure_failure": (
                "retained attempt; retry only the same cell/evaluation with resume"
            ),
            "stochastic_confirmation_artifact": (
                "quarantined and blocks confirmatory analysis"
            ),
            "missing_or_tampered_artifact": "fail closed",
        },
        "prerequisites": {
            "full_test_suite": full_suite_binding,
            "security_audit": security_binding,
            "certification_audit": certification_binding,
            "protocol_smoke": {
                "path": _relative_or_absolute(smoke_path),
                "task": "Chemistry/LennardJonesCluster",
                "budget": 0,
                "replicate_identifiers": [0, 1, 2, 3],
                "feedback_modes": list(MODES),
                "condition_order": "balanced_williams",
                "condition_order_randomization_seed": (
                    condition_order_randomization_seed
                ),
                "condition_order_schedule": condition_schedule(
                    [0, 1, 2, 3], condition_order_randomization_seed
                ),
                "block_workers": search_block_workers,
                "scheduled_cell_count": 16,
                "required": (
                    "trusted clean-source report with exact preregistration hash "
                    "binding before any nonzero-budget search cell"
                ),
            },
        },
        "execution": {
            "search_report": _relative_or_absolute(search_report_path),
            "search_work_root": _relative_or_absolute(search_work_root),
            "search_command": [
                "python3", "scripts/batch_evolve.py", "--all", "--tasks",
                ",".join(TASKS), "--algorithms", "greedy_rewrite",
                "--feedback-modes", ",".join(MODES), "--seeds",
                ",".join(str(value) for value in replicates), "--budget", "3",
                "--timeout", "300", "--condition-order-design",
                "balanced_williams", "--condition-order-randomization-seed",
                str(condition_order_randomization_seed), "--preregistration",
                "<this_preregistration>", "--workdir",
                _relative_or_absolute(search_work_root), "--block-workers",
                str(search_block_workers), "--output",
                _relative_or_absolute(search_report_path),
            ],
            "order": [
                "commit preregistration and public commitment",
                "run and verify protocol smoke",
                "run all fixed search cells without reading private contexts",
                "run post-search fresh confirmation",
                "run the frozen final analyzer",
            ],
            "protocol_smoke_command": [
                "python3", "scripts/batch_evolve.py", "--all", "--tasks",
                "Chemistry/LennardJonesCluster", "--algorithms",
                "greedy_rewrite", "--feedback-modes", ",".join(MODES),
                "--seeds", "0,1,2,3", "--budget", "0", "--timeout", "300",
                "--condition-order-design", "balanced_williams",
                "--condition-order-randomization-seed",
                str(condition_order_randomization_seed), "--preregistration",
                "<this_preregistration>", "--workdir", "<smoke_work_root>",
                "--block-workers", str(search_block_workers), "--output",
                _relative_or_absolute(smoke_path),
            ],
            "confirmation_command": [
                "python3", "scripts/run_track_f_confirmation.py",
                "--preregistration", "<this_preregistration>",
                "--search-report", _relative_or_absolute(search_report_path),
                "--private-contexts", "<private_context_manifest>",
                "--public-commitment", _relative_or_absolute(commitment_path),
                "--workers", str(confirmation_workers), "--output",
                "<confirmation_report>",
            ],
        },
        "claims_before_outcomes": {
            "feedback_effect_identified": False,
            "population_effect_estimated": False,
            "cross_task_general_effect_identified": False,
            "independent_physical_validation_completed": False,
            "autonomous_scientific_discovery_demonstrated": False,
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--precision", type=Path, required=True)
    parser.add_argument("--commitment", type=Path, required=True)
    parser.add_argument("--full-suite", type=Path, required=True)
    parser.add_argument("--security", type=Path, required=True)
    parser.add_argument("--certification", type=Path, required=True)
    parser.add_argument("--smoke", type=Path, required=True)
    parser.add_argument("--search-report", type=Path, required=True)
    parser.add_argument("--search-work-root", type=Path, required=True)
    parser.add_argument(
        "--condition-order-randomization-seed", type=int, required=True
    )
    parser.add_argument("--confirmation-randomization-seed", type=int, required=True)
    parser.add_argument("--search-block-workers", type=int, required=True)
    parser.add_argument("--confirmation-workers", type=int, required=True)
    parser.add_argument("--llm-config", default=None)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    output = args.output.expanduser().resolve()
    if output.exists():
        raise SystemExit("refusing to overwrite a Track F preregistration")
    try:
        document = build(
            precision_path=args.precision.expanduser().resolve(),
            commitment_path=args.commitment.expanduser().resolve(),
            full_suite_path=args.full_suite.expanduser().resolve(),
            security_path=args.security.expanduser().resolve(),
            certification_path=args.certification.expanduser().resolve(),
            smoke_path=args.smoke.expanduser().resolve(),
            search_report_path=args.search_report.expanduser().resolve(),
            search_work_root=args.search_work_root.expanduser().resolve(),
            condition_order_randomization_seed=(
                args.condition_order_randomization_seed
            ),
            confirmation_randomization_seed=args.confirmation_randomization_seed,
            search_block_workers=args.search_block_workers,
            confirmation_workers=args.confirmation_workers,
            llm_config=args.llm_config,
        )
    except (OSError, ValueError, TypeError, KeyError) as exc:
        raise SystemExit(str(exc)) from exc
    output.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(output, json.dumps(document, indent=2, allow_nan=False) + "\n")
    print(json.dumps({
        "output": str(output),
        "frozen_revision": document["frozen_source"]["revision"],
        "fixed_blocks_per_condition": document["design"][
            "fixed_blocks_per_condition"
        ],
        "scheduled_search_cells": document["design"]["scheduled_cell_count"],
        "scheduled_model_proposals": document["design"][
            "scheduled_model_proposals"
        ],
        "confirmation_blocks": document["confirmation_commitment"][
            "block_count"
        ],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

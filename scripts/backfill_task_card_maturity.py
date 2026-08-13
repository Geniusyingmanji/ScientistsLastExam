#!/usr/bin/env python3
"""One-time, fail-closed schema-v2 backfill for nonquarantined task cards.

The backfill records what is known without inventing historical builder metadata.
Legacy builder/scaffold identities remain explicit unknown sentinels, calibration
artifacts are selected from the trusted maturity ledger, and all long-horizon gates
remain false until dedicated experiments are run.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sle.certification import certification_status  # noqa: E402
from sle.registry import list_tasks  # noqa: E402


DEFAULT_LEDGER = ROOT / "experiments/task_maturity_audit_2026-07-26_v1.json"

PUBLIC_DATA_REPLAY = {
    "Electrochemistry/ElectrolyteConductivityDesign",
    "MaterialsScience/AlloyHardnessOptimization",
    "ProteinEngineering/ProteinStabilityDesign",
    "Turbulence/RANSCalibration",
}

KNOWN_ANSWER = {
    "Algorithm/MatrixMultiplicationRank",
    "BayesianInference/OptimalExperimentDesign",
    "Chemistry/LennardJonesCluster",
    "ControlTheory/InvertedPendulumSwingUp",
    "DynamicalSystems/LyapunovControl",
    "FluidDynamics/LidDrivenCavity",
    "Geophysics/SeismicInversion",
    "Mathematics/CapSet",
    "NuclearEngineering/NeutronDiffusionCriticality",
    "Optimization/CirclePacking",
    "Photonics/MultilayerThinFilm",
    "Physics/SpinGlassGroundState",
    "QuantumChemistry/HartreeFockSCF",
    "ScientificComputing/PoissonSolver2D",
    "SignalProcessing/SparseRecovery",
}

FRESH_PROCEDURAL_CONFIRMATION = {
    "DynamicalSystems/ActiveLawDiscovery",
    "Optics/DiffractionGratingDesign",
}


def _load_ledger(path: Path) -> dict[str, dict[str, Any]]:
    document = json.loads(path.read_text(encoding="utf-8"))
    if document.get("trusted_evidence") is not True or document.get("execution_passed") is not True:
        raise ValueError("maturity ledger must be trusted and passed")
    rows = document.get("tasks")
    if not isinstance(rows, list):
        raise ValueError("maturity ledger tasks are missing")
    return {str(row["task"]): row for row in rows}


def _provenance(task_id: str) -> dict[str, Any]:
    if task_id in PUBLIC_DATA_REPLAY:
        provenance_class = "public_data_replay"
        target_source = (
            "Hash-bound public dataset replay whose source and finite records were available "
            "before evaluation."
        )
        novelty_level = "high"
        novelty_rationale = (
            "The public data and finite candidate landscape may occur in pretraining or external "
            "sources; memorization and benchmark-specific retrieval cannot be excluded."
        )
    elif task_id in KNOWN_ANSWER:
        provenance_class = "known_answer"
        target_source = (
            "Published or repository-visible fixed targets, reference values, or standard solution "
            "families available before evaluation."
        )
        novelty_level = "high"
        novelty_rationale = (
            "Success may reproduce a known numerical method, design pattern, or published target; "
            "it is reconstruction/optimization evidence rather than a novel scientific discovery."
        )
    else:
        provenance_class = "procedural"
        target_source = (
            "Repository-visible deterministic simulator or generator with development and "
            "held-out, shifted, or misspecified instances."
        )
        novelty_level = "medium"
        novelty_rationale = (
            "Specific parameters may be held out, but the task family, simulator, and scaffold are "
            "visible and builder-model independence has not been established."
        )
    return {
        "provenance": {
            "class": provenance_class,
            "target_source": target_source,
            "task_contract_public_before_evaluation": True,
            "fresh_confirmation_status": (
                "local_fresh_procedural_panels_available"
                if task_id in FRESH_PROCEDURAL_CONFIRMATION
                else "not_completed"
            ),
        },
        "novelty_risk": {
            "level": novelty_level,
            "rationale": novelty_rationale,
        },
    }


def _evidence_paths(row: dict[str, Any]) -> tuple[list[str], str]:
    candidates: list[tuple[int, str]] = []
    binding_rank = {
        "current_contract_bound": 0,
        "migration_replayed": 1,
        "historical_only": 2,
        "unbound": 3,
    }
    kind_rank = {
        "model_run": 0,
        "analysis": 1,
        "calibration": 2,
        "admission": 3,
        "independent_numerical_crosscheck": 4,
    }
    for kind, items in (row.get("evidence") or {}).items():
        if kind not in kind_rank or not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict) or not isinstance(item.get("path"), str):
                continue
            binding = str(item.get("contract_binding") or "unbound")
            rank = binding_rank.get(binding, 3) * 10 + kind_rank[kind]
            candidates.append((rank, item["path"]))
    paths = []
    for _, path in sorted(candidates):
        if path not in paths:
            paths.append(path)
        if len(paths) == 3:
            break
    bindings = row.get("evidence_binding_counts") or {}
    if int(bindings.get("current_contract_bound", 0)) + int(bindings.get("migration_replayed", 0)):
        status = "current_or_migration_replayed"
    elif int(bindings.get("historical_only", 0)):
        status = "historical_only"
    else:
        status = "missing"
    return paths, status


def _metadata(task_id: str, row: dict[str, Any]) -> dict[str, Any]:
    paths, evidence_status = _evidence_paths(row)
    calibrator_models = (
        ["azure-responses:gpt-5.5"]
        if any("gpt55" in path or "feedback_" in path or "track_f_search" in path for path in paths)
        else []
    )
    result = _provenance(task_id)
    result.update({
        "lineage": {
            "status": "incomplete_legacy",
            "builder_model_ids": ["unknown_legacy_builder"],
            "builder_scaffolds": ["unknown_legacy_scaffold"],
            "calibrator_model_ids": calibrator_models,
            "calibration_runs": paths,
            "calibration_evidence_status": evidence_status,
            "edits_triggered_by_model": (
                "Not exhaustively reconstructed; use the task certification reason, dated "
                "calibration analyses, and Git history as the retained record."
            ),
            "shortcut_discoverer": "mixed_automated_red_team_and_gpt5.5_calibration",
            "frozen_before_eval": False,
            "freeze_timestamp": None,
        },
        "construction_audit": {
            "status": "incomplete_legacy",
            "author_domain": "unknown_legacy",
            "reviewer_domain": "pending_external",
            "expert_hours": None,
            "red_team_rounds": None,
            "oracle_disagreement_status": "not_quantified",
            "independent_recomputation_status": "see_task_invariants_and_calibration_evidence",
        },
        "long_horizon": {
            "status": "not_tested",
            "measurement_health_passed": False,
            "material_headroom_after_2h": False,
            "evidence": [],
        },
    })
    return result


def backfill(ledger_path: Path, *, check_only: bool = False) -> list[str]:
    ledger = _load_ledger(ledger_path)
    changed = []
    specs = [
        spec for spec in list_tasks(None)
        if certification_status(spec.task_id) != "quarantined"
    ]
    if len(specs) != 50:
        raise ValueError("expected exactly 50 nonquarantined tasks")
    for spec in specs:
        if spec.task_id not in ledger:
            raise ValueError("task missing from maturity ledger: %s" % spec.task_id)
        path = spec.task_dir / "TASK_CARD.yaml"
        text = path.read_text(encoding="utf-8")
        card = yaml.safe_load(text) or {}
        if card.get("schema_version") == 2:
            required = {
                "provenance", "novelty_risk", "lineage",
                "construction_audit", "long_horizon",
            }
            if not required.issubset(card):
                metadata = _metadata(spec.task_id, ledger[spec.task_id])
                for key, value in metadata.items():
                    if key not in card:
                        card[key] = value
                if "freeze_timestamp" not in card.get("lineage", {}):
                    card["lineage"]["freeze_timestamp"] = None
                updated = yaml.safe_dump(
                    card, sort_keys=False, allow_unicode=True, width=1000000,
                )
                if not check_only:
                    path.write_text(updated, encoding="utf-8")
                changed.append(str(path.relative_to(ROOT)))
            elif "freeze_timestamp" not in card.get("lineage", {}):
                card["lineage"]["freeze_timestamp"] = None
                updated = yaml.safe_dump(
                    card, sort_keys=False, allow_unicode=True, width=1000000,
                )
                if not check_only:
                    path.write_text(updated, encoding="utf-8")
                changed.append(str(path.relative_to(ROOT)))
            continue
        if card.get("schema_version") != 1:
            raise ValueError("unexpected task-card schema: %s" % spec.task_id)
        if any(key in card for key in (
            "provenance", "novelty_risk", "lineage", "construction_audit", "long_horizon"
        )):
            raise ValueError("task card already contains maturity metadata: %s" % spec.task_id)
        metadata = yaml.safe_dump(
            _metadata(spec.task_id, ledger[spec.task_id]),
            sort_keys=False,
            allow_unicode=True,
            width=1000000,
        )
        updated = text.replace("schema_version: 1\n", "schema_version: 2\n", 1)
        updated = updated.rstrip() + "\n" + metadata
        if not check_only:
            path.write_text(updated, encoding="utf-8")
        changed.append(str(path.relative_to(ROOT)))
    return changed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER)
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    changed = backfill(args.ledger.resolve(), check_only=args.check_only)
    print(json.dumps({"changed_count": len(changed), "paths": changed}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

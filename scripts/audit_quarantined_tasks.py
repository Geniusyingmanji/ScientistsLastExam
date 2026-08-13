#!/usr/bin/env python3
"""Reproduce the material defects for every currently quarantined task.

The certification inventory deliberately keeps defective packages for provenance.  A
quarantine label alone is not evidence that the defect still exists, so this audit binds
the manifest's complete quarantine set to executable adversarial checks.  If a task is
added to or removed from quarantine without updating the checks, the audit fails closed.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import importlib.util
import json
import math
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sle.certification import load_certification  # noqa: E402
from sle.provenance import (  # noqa: E402
    finalize_report_trust,
    source_provenance,
)
from sle.registry import find_task  # noqa: E402
from scripts import audit_candidate_wave4 as wave4  # noqa: E402
from scripts.audit_tasks import _normalized_oracle  # noqa: E402


REPRODUCED_WAVE4_CHECKS: dict[str, Callable[[], dict[str, Any]]] = {
    "Biomechanics/ProstheticJointDesign": wave4._prosthetic_joint,
    "Combustion/FlameSpeedOptimization": wave4._flame_speed,
    "FluidMechanics/StokesShapeDrag": wave4._stokes_drag,
    "InventoryManagement/MultiEchelonStock": wave4._inventory,
    "Transportation/TrafficSignalTiming": wave4._traffic,
}

WAVE4_FAILED_STANDARD_AXES = {
    "Biomechanics/ProstheticJointDesign": [
        "scientific_semantics", "oracle_fidelity", "optimization_integrity",
    ],
    "Combustion/FlameSpeedOptimization": [
        "oracle_fidelity", "openness_headroom", "optimization_continuity",
    ],
    "FluidMechanics/StokesShapeDrag": [
        "scientific_semantics", "oracle_fidelity", "optimization_integrity",
    ],
    "InventoryManagement/MultiEchelonStock": [
        "scientific_semantics", "oracle_fidelity", "generalization",
    ],
    "Transportation/TrafficSignalTiming": [
        "scientific_semantics", "oracle_fidelity", "optimization_integrity",
    ],
}

GENERIC_CLONE_TASKS = {
    "CrystalGrowth/CzochralskiProcess": {
        "entrypoint": "optimize_czochralski",
        "claimed_model": "one-dimensional moving-boundary Stefan heat equation",
    },
    "Electromagnetics/WaveguideModeSolver": {
        "entrypoint": "design_waveguide",
        "claimed_model": "TE/TM transcendental waveguide eigenmode solver",
    },
    "Geomechanics/TunnelSupportDesign": {
        "entrypoint": "design_support",
        "claimed_model": "plane-strain FEM with Mohr-Coulomb failure",
    },
    "Optoelectronics/LaserCavityDesign": {
        "entrypoint": "design_cavity",
        "claimed_model": "round-trip gain/loss and ABCD mode stability",
    },
}

REQUIRED_CERTIFICATION_METADATA = {
    "science_metric", "reference_baseline", "reference_sota", "citation",
}


def _oracle(task_id: str):
    path = (
        find_task(task_id, include_uncertified=True).task_dir
        / "verification/evaluator.py"
    )
    spec = importlib.util.spec_from_file_location(
        "quarantined_task_audit_" + task_id.replace("/", "_"), path,
    )
    if spec is None or spec.loader is None:
        raise ImportError("cannot load evaluator for %s" % task_id)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _source_structure(path: Path) -> dict[str, Any]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    defined_functions = sorted(
        node.name for node in tree.body if isinstance(node, ast.FunctionDef)
    )
    imported_names: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            imported_names.update(alias.asname or alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported_names.update(alias.asname or alias.name for alias in node.names)
    loaded_names = {
        node.id for node in ast.walk(tree)
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
    }
    return {
        "defined_functions": defined_functions,
        "unused_solver_imports": sorted(
            {"minimize_scalar", "solve_ivp"} & (imported_names - loaded_names)
        ),
        "has_instance_or_split_declarations": any(
            marker in name.upper()
            for name in loaded_names | {
                target.id
                for node in ast.walk(tree)
                if isinstance(node, (ast.Assign, ast.AnnAssign))
                for target in (
                    node.targets if isinstance(node, ast.Assign) else [node.target]
                )
                if isinstance(target, ast.Name)
            }
            for marker in ("INSTANCE", "DEVELOPMENT", "HELDOUT", "SHIFT", "WORLD")
        ),
    }


def _generic_clone_record(
    task_id: str,
    config: dict[str, str],
    expected_fingerprint: str,
) -> dict[str, Any]:
    spec = find_task(task_id, include_uncertified=True)
    evaluator_path = spec.task_dir / "verification/evaluator.py"
    oracle = _oracle(task_id)
    target = np.array([
        0.7 + 0.3 * np.sin(index * 0.5)
        for index in range(oracle.N_PARAMS)
    ])

    baseline = oracle.evaluate(lambda count: np.zeros(count))
    embedded_target = oracle.evaluate(lambda _count: target.copy())
    with np.errstate(all="ignore"):
        nonfinite = oracle.evaluate(
            lambda count: np.full(count, np.nan)
        )

    fingerprint = hashlib.sha256(
        _normalized_oracle(evaluator_path).encode("utf-8")
    ).hexdigest()
    structure = _source_structure(evaluator_path)
    contract_entrypoint = (
        spec.task_dir / "frontier_eval/entrypoint.txt"
    ).read_text(encoding="utf-8").strip()
    missing_metadata = sorted(
        REQUIRED_CERTIFICATION_METADATA - set(spec.metadata)
    )
    defect_reproduced = bool(
        fingerprint == expected_fingerprint
        and structure["defined_functions"] == ["_forward_model", "evaluate"]
        and structure["unused_solver_imports"]
        == ["minimize_scalar", "solve_ivp"]
        and not structure["has_instance_or_split_declarations"]
        and contract_entrypoint == config["entrypoint"]
        and spec.metadata.get("oracle_type") == "physical_sim"
        and not (spec.task_dir / "TASK_CARD.yaml").is_file()
        and missing_metadata == sorted(REQUIRED_CERTIFICATION_METADATA)
        and baseline["valid"] == 1.0
        and baseline["combined_score"] == 0.0
        and embedded_target["valid"] == 1.0
        and embedded_target["combined_score"] == 1.0
        and nonfinite["valid"] == 1.0
        and nonfinite["combined_score"] == 1.0
        and not math.isfinite(float(nonfinite["objective"]))
    )
    return {
        "task": task_id,
        "certification_status": "quarantined",
        "meets_internal_benchmark_standard": False,
        "recommendation": "retain_quarantine_until_substantive_rebuild",
        "audit_kind": "generic_cross_domain_oracle_clone_reproduction",
        "defect": (
            "The claimed %s is not implemented. The evaluator is the same fixed "
            "eight-variable trigonometric objective used by three unrelated domains, "
            "contains an embedded full-score vector, has no procedural/held-out/sealed "
            "axis, and accepts NaN at full score." % config["claimed_model"]
        ),
        "failed_standard_axes": [
            "scientific_semantics",
            "oracle_fidelity",
            "generalization",
            "optimization_integrity",
            "evidence_integrity",
        ],
        "entrypoint": config["entrypoint"],
        "contract_entrypoint": contract_entrypoint,
        "declared_oracle_type": spec.metadata.get("oracle_type"),
        "normalized_oracle_sha256": fingerprint,
        "same_as_generic_clone_group": fingerprint == expected_fingerprint,
        "defined_functions": structure["defined_functions"],
        "unused_solver_imports": structure["unused_solver_imports"],
        "has_instance_or_split_declarations": structure[
            "has_instance_or_split_declarations"
        ],
        "task_card_present": (spec.task_dir / "TASK_CARD.yaml").is_file(),
        "missing_certification_metadata": missing_metadata,
        "parameter_count": int(oracle.N_PARAMS),
        "baseline_score": float(baseline["combined_score"]),
        "embedded_target_score": float(embedded_target["combined_score"]),
        "nonfinite_score": float(nonfinite["combined_score"]),
        "nonfinite_valid": bool(nonfinite["valid"]),
        "nonfinite_objective_is_finite": math.isfinite(
            float(nonfinite["objective"])
        ),
        "defect_reproduced": defect_reproduced,
    }


def _wave4_record(task_id: str, check: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    original = check()
    reproduced = bool(
        original.get("task") == task_id
        and original.get("admission") == "quarantine"
        and original.get("passed") is True
    )
    retained = {
        key: value for key, value in original.items()
        if key not in {"admission", "passed"}
    }
    retained.update({
        "certification_status": "quarantined",
        "meets_internal_benchmark_standard": False,
        "recommendation": "retain_quarantine_until_substantive_rebuild",
        "audit_kind": "reproduced_adversarial_oracle_failure",
        "failed_standard_axes": WAVE4_FAILED_STANDARD_AXES[task_id],
        "defect_reproduced": reproduced,
    })
    return retained


def audit() -> dict[str, Any]:
    manifest = load_certification()
    manifest_quarantined = {
        task_id for task_id, record in manifest["tasks"].items()
        if record.get("status") == "quarantined"
    }
    covered = set(REPRODUCED_WAVE4_CHECKS) | set(GENERIC_CLONE_TASKS)

    generic_fingerprints = {
        task_id: hashlib.sha256(
            _normalized_oracle(
                find_task(task_id, include_uncertified=True).task_dir
                / "verification/evaluator.py"
            ).encode("utf-8")
        ).hexdigest()
        for task_id in GENERIC_CLONE_TASKS
    }
    unique_generic_fingerprints = set(generic_fingerprints.values())
    expected_fingerprint = next(iter(unique_generic_fingerprints))

    records = [
        _wave4_record(task_id, check)
        for task_id, check in REPRODUCED_WAVE4_CHECKS.items()
    ] + [
        _generic_clone_record(task_id, config, expected_fingerprint)
        for task_id, config in GENERIC_CLONE_TASKS.items()
    ]
    records.sort(key=lambda row: row["task"])

    missing_checks = sorted(manifest_quarantined - covered)
    stale_checks = sorted(covered - manifest_quarantined)
    execution_passed = bool(
        not missing_checks
        and not stale_checks
        and len(unique_generic_fingerprints) == 1
        and len(records) == len(manifest_quarantined)
        and all(row["defect_reproduced"] for row in records)
        and all(
            row["meets_internal_benchmark_standard"] is False
            for row in records
        )
    )
    report = {
        "schema_version": 1,
        "trust_status": "TRUSTED_QUARANTINED_TASK_REAUDIT",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_provenance": source_provenance(ROOT),
        "environment": {"python": sys.version, "platform": platform.platform()},
        "policy": {
            "meaning": (
                "A reproduced defect proves that quarantine remains warranted; it does "
                "not validate the task as benchmark-admissible."
            ),
            "required_coverage": "all manifest tasks whose status is quarantined",
        },
        "manifest_quarantined_tasks": sorted(manifest_quarantined),
        "missing_checks": missing_checks,
        "stale_checks": stale_checks,
        "generic_clone_group": {
            "tasks": sorted(GENERIC_CLONE_TASKS),
            "unique_normalized_oracle_count": len(unique_generic_fingerprints),
            "normalized_oracle_sha256": expected_fingerprint,
        },
        "records": records,
        "summary": {
            "manifest_quarantined_count": len(manifest_quarantined),
            "audited_count": len(records),
            "reproduced_defect_count": sum(
                row["defect_reproduced"] for row in records
            ),
            "meets_internal_benchmark_standard_count": sum(
                row["meets_internal_benchmark_standard"] for row in records
            ),
            "recommended_retain_quarantine_count": sum(
                row["recommendation"]
                == "retain_quarantine_until_substantive_rebuild"
                for row in records
            ),
        },
    }
    finalize_report_trust(report, execution_passed)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = audit()
    rendered = json.dumps(report, indent=2, allow_nan=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if report["execution_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Build a portable cross-task summary from trusted science calibrations.

Batch reports keep raw trajectories under the git-ignored ``runs/`` tree. This
script validates those trajectories and freezes the scalar science metrics,
candidate lineage hashes, and source hashes needed for cross-task auditing.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from frontier_science.protocol import compact_trajectory_snapshot, load_trajectory  # noqa: E402
from frontier_science.provenance import finalize_report_trust, source_provenance  # noqa: E402


DEFAULT_REPORTS = (
    "experiments/gpt55_oed_v2_b1_2026-07-21.json",
    "experiments/gpt55_pendulum_v2_contract_b1_2026-07-21.json",
    "experiments/gpt55_pendulum_v2_b3_2026-07-21.json",
    "experiments/gpt55_gate_v2_b1_2026-07-21.json",
    "experiments/gpt55_gate_v2_b3_2026-07-21.json",
    "experiments/gpt55_active_law_b1_2026-07-21.json",
    "experiments/gpt55_active_law_b3_2026-07-21.json",
    "experiments/gpt55_opf_v2_b1_2026-07-21.json",
    "experiments/gpt55_opf_v2_b3_2026-07-21.json",
    "experiments/gpt55_truss_v2_b1_2026-07-21.json",
    "experiments/gpt55_truss_v2_b3_2026-07-21.json",
    "experiments/gpt55_antenna_v2_b1_2026-07-21.json",
    "experiments/gpt55_antenna_v2_b3_2026-07-21.json",
    "experiments/gpt55_nmr_v2_b1_2026-07-22.json",
    "experiments/gpt55_nmr_v2_b3_2026-07-22.json",
    "experiments/gpt55_heat_exchanger_v2_b1_2026-07-22.json",
    "experiments/gpt55_heat_exchanger_v2_b3_2026-07-22.json",
    "experiments/gpt55_reaction_v2_b1_2026-07-22.json",
    "experiments/gpt55_reaction_v2_b3_2026-07-22.json",
    "experiments/gpt55_gravity_v2_b1_2026-07-22.json",
    "experiments/gpt55_gravity_v2_b3_2026-07-22.json",
    "experiments/gpt55_ocean_v2_b1_2026-07-22.json",
    "experiments/gpt55_ocean_v2_b3_2026-07-22.json",
    "experiments/gpt55_radiative_v2_b1_2026-07-22.json",
    "experiments/gpt55_radiative_v2_b3_2026-07-22.json",
    "experiments/gpt55_low_thrust_v2_b1_2026-07-22.json",
    "experiments/gpt55_low_thrust_v2_b3_2026-07-22.json",
    "experiments/gpt55_cavity_v2_b1_2026-07-22.json",
    "experiments/gpt55_cavity_v2_b3_2026-07-22.json",
    "experiments/gpt55_climate_v2_b1_2026-07-22.json",
    "experiments/gpt55_climate_v2_b3_2026-07-22.json",
    "experiments/gpt55_absorber_v2_b1_2026-07-23.json",
    "experiments/gpt55_absorber_v2_b3_2026-07-23.json",
    "experiments/gpt55_distillation_v2_b1_2026-07-23.json",
    "experiments/gpt55_distillation_v2_b3_2026-07-23.json",
    "experiments/gpt55_hartree_fock_v2_b1_2026-07-23.json",
    "experiments/gpt55_hartree_fock_v2_b3_2026-07-23.json",
    "experiments/gpt55_room_acoustics_v2_b1_2026-07-23.json",
    "experiments/gpt55_room_acoustics_v2_b3_2026-07-23.json",
    "experiments/gpt55_convection_diffusion_v2_b1_2026-07-23.json",
    "experiments/gpt55_convection_diffusion_v2_b3_2026-07-23.json",
    "experiments/gpt55_seismic_wave_v2_b1_2026-07-24.json",
    "experiments/gpt55_seismic_wave_v2_b3_2026-07-24.json",
    "experiments/gpt55_rankine_v2_b1_2026-07-24.json",
    "experiments/gpt55_rankine_v2_b3_2026-07-24.json",
    "experiments/gpt55_mosfet_v2_b1_2026-07-24.json",
    "experiments/gpt55_mosfet_v2_b3_2026-07-24.json",
    "experiments/gpt55_rans_v2_b1_2026-07-24.json",
    "experiments/gpt55_rans_v2_b3_2026-07-24.json",
    "experiments/gpt55_gene_network_v1_b1_2026-07-24.json",
    "experiments/gpt55_gene_network_v1_b3_2026-07-24.json",
    "experiments/gpt55_rna_inverse_v1_b1_2026-07-24.json",
    "experiments/gpt55_rna_inverse_v1_b3_2026-07-24.json",
    "experiments/gpt55_protein_stability_v1_b1_2026-07-25.json",
    "experiments/gpt55_protein_stability_v1_b3_2026-07-25.json",
    "experiments/gpt55_electrolyte_conductivity_v1_b1_2026-07-25.json",
    "experiments/gpt55_electrolyte_conductivity_v1_b3_2026-07-25.json",
    "experiments/gpt55_demographic_sfs_v2_b1_2026-07-25.json",
    "experiments/gpt55_demographic_sfs_v2_b3_2026-07-25.json",
    "experiments/gpt55_calorimeter_v2_b1_2026-07-25.json",
    "experiments/gpt55_calorimeter_v2_b3_2026-07-25.json",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def summarize_report(path: Path) -> dict[str, Any]:
    path = path.resolve()
    document = json.loads(path.read_text(encoding="utf-8"))
    provenance = document.get("source_provenance") or {}
    if document.get("trusted_evidence") is not True or document.get("passed") is not True:
        raise ValueError("input report is not trusted and passed: %s" % path)
    if provenance.get("source_tree_dirty") is not False:
        raise ValueError("input report has dirty source provenance: %s" % path)
    runs = document.get("runs")
    if not isinstance(runs, list) or len(runs) != 1 or runs[0].get("error"):
        raise ValueError("expected exactly one successful calibration run: %s" % path)
    run = runs[0]
    trajectory_path = Path(run["workdir"]) / "trajectory.jsonl"
    events = load_trajectory(trajectory_path)
    summary = run.get("summary") or {}
    if int(events[-1]["oracle_calls"]) != int(run.get("evaluated", -1)):
        raise ValueError("evaluated count disagrees with trajectory: %s" % path)
    if int(events[-1]["oracle_calls"]) != int(summary.get("oracle_calls", -1)):
        raise ValueError("oracle-call count disagrees with trajectory: %s" % path)
    if abs(float(summary.get("best_score")) - float(run["best"])) > 1e-12:
        raise ValueError("best score disagrees with run summary: %s" % path)

    snapshot = compact_trajectory_snapshot(trajectory_path)

    return {
        "report": str(path.relative_to(ROOT)),
        "report_sha256": _sha256(path),
        "trajectory_sha256": snapshot["trajectory_sha256"],
        "source_revision": provenance["git_revision"],
        "task": run["task"],
        "algorithm": run["algorithm"],
        "feedback_mode": run["feedback_mode"],
        "seed": int(run["seed"]),
        "proposal_budget": int(document["config"]["budget"]),
        "baseline_score": run["baseline"],
        "best_score": run["best"],
        "accepted_proposals": int(run["accepted"]),
        "oracle_calls": int(run["evaluated"]),
        "trajectory_event_count": len(events),
        "llm": summary.get("llm", {}),
        "feedback_scope": summary.get("feedback_scope"),
        "trajectory": snapshot["events"],
    }


def build_report(paths: list[Path]) -> dict[str, Any]:
    records = [summarize_report(path) for path in paths]
    report: dict[str, Any] = {
        "schema_version": 1,
        "trust_status": "TRUSTED_DERIVED_EVIDENCE",
        "evidence_scope": "SINGLE_SEED_CALIBRATION_NOT_CAUSAL_OR_POPULATION_EVIDENCE",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_provenance": source_provenance(ROOT),
        "environment": {"python": sys.version, "platform": platform.platform()},
        "input_count": len(records),
        "normal_condition_count": len(records),
        "task_count": len({record["task"] for record in records}),
        "records": records,
        "limitations": [
            "Each model condition has one seed; no confidence interval or causal feedback claim is supported.",
            "Budget-one and budget-three runs are independent calibrations, not prefixes of one trajectory.",
            "Only top-level scalar metrics are copied; report and raw-trajectory hashes bind omitted details.",
            "Sealed metric semantics remain task-specific and must not be averaged into one science score.",
        ],
    }
    execution_passed = bool(
        len(paths) == len(DEFAULT_REPORTS)
        and len(records) == len(paths)
        and {record["report"] for record in records} == set(DEFAULT_REPORTS)
        and all(record["feedback_mode"] == "normal" for record in records)
        and all(record["algorithm"] == "greedy_rewrite" for record in records)
    )
    finalize_report_trust(report, execution_passed)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    parser.add_argument("reports", nargs="*", type=Path)
    args = parser.parse_args()
    paths = args.reports or [ROOT / name for name in DEFAULT_REPORTS]
    report = build_report(paths)
    text = json.dumps(report, indent=2, allow_nan=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0 if report["execution_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Build the frozen ElectrolyteConductivityDesign replay from the Zenodo CSV.

The source file contains 5,035 temperature rows from 504 experiment IDs, not
5,035 independent formulations.  This builder preserves that hierarchy.  It
uses complete pre-January-2022 experiment series to construct a public proxy
surface and reserves two later, non-overlapping experimental campaigns as the
candidate pool.  Within each candidate formulation the first two independent
experiment IDs are the charged discovery assay and the next two are sealed,
equal-count confirmation replicates.  Any further repeats are retained only as
audit evidence.
"""

from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path


SCHEMA_VERSION = 1
BUILDER_VERSION = "electrolyte-conductivity-design-v1"
SOURCE_SIZE = 39_235_727
SOURCE_MD5 = "f84cfeb764e5d4db22cdb8b1253a0935"
SOURCE_SHA256 = "22b3445590b2d3a5c3ce48c9f784ca8af795dc66181eb0efc347efe31849c994"
TEMPERATURES_C = tuple(float(value) for value in range(-30, 61, 10))
COMPONENTS = ("PC", "EC", "EMC", "LiPF_6")
TARGET_CAMPAIGNS = ("18012022", "19012022")
DISCOVERY_REPLICATES = 2
CONFIRMATION_REPLICATES = 2
BATCH_SIZE = 3
ASSAY_BUDGET = 8


def _digest(path: Path, name: str) -> str:
    hasher = hashlib.new(name)
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _finite(value: str, field: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("non-finite %s" % field)
    return number


def _cell_constant(value: str) -> tuple[float, float]:
    parsed = ast.literal_eval(value)
    if not isinstance(parsed, tuple) or len(parsed) != 2:
        raise ValueError("invalid cell constant tuple")
    cell, standard_deviation = (float(parsed[0]), float(parsed[1]))
    if not math.isfinite(cell) or not math.isfinite(standard_deviation):
        raise ValueError("non-finite cell constant")
    return cell, standard_deviation


def _read_rows(path: Path) -> list[dict]:
    if path.stat().st_size != SOURCE_SIZE:
        raise ValueError("unexpected Zenodo CSV size")
    if _digest(path, "md5") != SOURCE_MD5:
        raise ValueError("unexpected Zenodo CSV MD5")
    if _digest(path, "sha256") != SOURCE_SHA256:
        raise ValueError("unexpected Zenodo CSV SHA-256")

    rows = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter=";")
        for line_number, raw in enumerate(reader, 2):
            # The first two records carry symbol and unit metadata.
            if raw.get("label") in {"symbol", "unit"}:
                continue
            cell, cell_sd = _cell_constant(raw["cell_constant,_standard_deviation"])
            row = {
                "line_number": int(line_number),
                "label": int(raw["label"]),
                "experiment_id": str(raw["experimentID"]),
                "temperature_c": _finite(raw["temperature"], "temperature"),
                "composition_g": {
                    key: _finite(raw[key], key) for key in COMPONENTS
                },
                "cell_constant_cm_inv": cell,
                "cell_constant_sd_cm_inv": cell_sd,
                "conductivity_s_cm": _finite(
                    raw["EIS_conductivity"], "EIS_conductivity"
                ),
                "resistance_ohm": _finite(raw["EIS_resistance"], "EIS_resistance"),
                "eis_rmse": _finite(raw["EIS_RMSE"], "EIS_RMSE"),
                "eis_fit_evaluation": _finite(
                    raw["EIS_fitEvaluation"], "EIS_fitEvaluation"
                ),
                "eis_chi_square": _finite(raw["EIS_chiSquare"], "EIS_chiSquare"),
                "arrhenius_activation_energy": _finite(
                    raw["Arrhenius_activationEnergy"],
                    "Arrhenius_activationEnergy",
                ),
                "arrhenius_r2": _finite(raw["Arrhenius_R2"], "Arrhenius_R2"),
                "arrhenius_mse": _finite(raw["Arrhenius_MSE"], "Arrhenius_MSE"),
            }
            if abs(cell / row["resistance_ohm"] - row["conductivity_s_cm"]) > 2e-15:
                raise ValueError("conductivity identity mismatch on line %d" % line_number)
            rows.append(row)
    if len(rows) != 5035:
        raise ValueError("expected 5,035 temperature records")
    if len({row["label"] for row in rows}) != 5035:
        raise ValueError("source labels are not unique")
    return rows


def _composition_key(row: dict) -> tuple[float, ...]:
    return tuple(float(row["composition_g"][key]) for key in COMPONENTS)


def _campaign(experiment_id: str) -> str:
    pieces = experiment_id.split("_")
    if len(pieces) < 4:
        raise ValueError("unexpected experiment identifier")
    return pieces[1]


def _complete_experiments(rows: list[dict]) -> dict[str, tuple[dict, ...]]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        grouped[row["experiment_id"]].append(row)
    if len(grouped) != 504:
        raise ValueError("expected 504 experiment IDs")

    complete = {}
    for experiment_id, values in grouped.items():
        ordered = tuple(sorted(values, key=lambda row: row["temperature_c"]))
        if tuple(row["temperature_c"] for row in ordered) != TEMPERATURES_C:
            continue
        if len({_composition_key(row) for row in ordered}) != 1:
            raise ValueError("composition changed within experiment")
        complete[experiment_id] = ordered
    if len(complete) != 499:
        raise ValueError("expected 499 complete ten-temperature experiments")
    return complete


def _curve_record(experiment_id: str, rows: tuple[dict, ...]) -> dict:
    first = rows[0]
    fields = (
        "conductivity_s_cm",
        "resistance_ohm",
        "cell_constant_cm_inv",
        "cell_constant_sd_cm_inv",
        "eis_rmse",
        "eis_fit_evaluation",
        "eis_chi_square",
    )
    record = {
        "experiment_id": experiment_id,
        "campaign": _campaign(experiment_id),
        "source_line_numbers": [int(row["line_number"]) for row in rows],
    }
    for field in fields:
        record[field] = [float(row[field]) for row in rows]
    for field in ("arrhenius_activation_energy", "arrhenius_r2", "arrhenius_mse"):
        values = [float(row[field]) for row in rows]
        if max(values) - min(values) > 1e-12:
            raise ValueError("Arrhenius field changes within experiment")
        record[field] = values[0]
    # A second independent calculation from the temperature series must reproduce
    # MADAP's Arrhenius R2 and MSE.  The activation-energy conversion is checked in
    # the calibration script with NumPy because the source unit label is inconsistent.
    return record


def _ratios(key: tuple[float, ...]) -> dict[str, float]:
    pc, ec, emc, salt = key
    solvent = pc + ec
    if solvent <= 0 or emc <= 0:
        raise ValueError("invalid formulation denominator")
    return {
        "pc_in_cyclic_carbonates": pc / solvent,
        "salt_to_cyclic_carbonates": salt / solvent,
        "cyclic_carbonates_to_emc": solvent / emc,
    }


def build(path: Path) -> dict:
    rows = _read_rows(path)
    complete = _complete_experiments(rows)
    by_composition: dict[tuple[float, ...], list[str]] = defaultdict(list)
    for experiment_id, values in complete.items():
        by_composition[_composition_key(values[0])].append(experiment_id)

    target_keys = []
    source_keys = []
    for key, experiment_ids in by_composition.items():
        campaigns = {_campaign(value) for value in experiment_ids}
        if campaigns & set(TARGET_CAMPAIGNS):
            if not campaigns <= set(TARGET_CAMPAIGNS):
                raise ValueError("source/target formulation overlap")
            if len(experiment_ids) >= DISCOVERY_REPLICATES + CONFIRMATION_REPLICATES:
                target_keys.append(key)
        else:
            source_keys.append(key)
    target_keys.sort()
    source_keys.sort()
    if len(target_keys) != 23 or len(source_keys) != 85:
        raise ValueError("unexpected source/target formulation counts")
    if set(target_keys) & set(source_keys):
        raise ValueError("source and target formulations overlap")

    source_formulations = []
    for index, key in enumerate(source_keys):
        experiment_ids = sorted(by_composition[key])
        curves = [complete[value] for value in experiment_ids]
        mean_curve = []
        for offset, temperature in enumerate(TEMPERATURES_C):
            values = [curve[offset]["conductivity_s_cm"] for curve in curves]
            mean_curve.append(sum(values) / len(values))
        source_formulations.append({
            "id": "S%03d" % index,
            "composition_g": dict(zip(COMPONENTS, key)),
            "ratios": _ratios(key),
            "experiment_ids": experiment_ids,
            "replicate_count": len(experiment_ids),
            "mean_conductivity_s_cm": mean_curve,
        })

    candidates = []
    target_experiment_count = 0
    for index, key in enumerate(target_keys):
        experiment_ids = sorted(by_composition[key])
        target_experiment_count += len(experiment_ids)
        repeats = [
            _curve_record(experiment_id, complete[experiment_id])
            for experiment_id in experiment_ids
        ]
        candidates.append({
            "id": "F%02d" % index,
            "composition_g": dict(zip(COMPONENTS, key)),
            "ratios": _ratios(key),
            "replicate_count": len(repeats),
            "discovery_replicates": repeats[:DISCOVERY_REPLICATES],
            "confirmation_replicates": repeats[
                DISCOVERY_REPLICATES:
                DISCOVERY_REPLICATES + CONFIRMATION_REPLICATES
            ],
            "audit_replicates": repeats[
                DISCOVERY_REPLICATES + CONFIRMATION_REPLICATES:
            ],
        })
    if target_experiment_count != 141:
        raise ValueError("expected 141 complete target-campaign repeats")

    source_ids = {
        value for row in source_formulations for value in row["experiment_ids"]
    }
    target_ids = {
        repeat["experiment_id"]
        for row in candidates
        for field in (
            "discovery_replicates", "confirmation_replicates", "audit_replicates"
        )
        for repeat in row[field]
    }
    if source_ids & target_ids or len(source_ids) != 358 or len(target_ids) != 141:
        raise ValueError("experiment lineage partition mismatch")

    return {
        "schema_version": SCHEMA_VERSION,
        "builder_version": BUILDER_VERSION,
        "source": {
            "article": {
                "title": "Conductivity experiments for electrolyte formulations and their automated analysis",
                "doi": "10.1038/s41597-023-01936-3",
                "journal": "Scientific Data",
                "volume": "10",
                "article_number": "43",
                "license": "CC-BY-4.0",
            },
            "dataset": {
                "title": "Dataset of 5035 Conductivity Experiments for Lithium-Ion Battery Electrolyte Formulations at Various Temperatures",
                "doi": "10.5281/zenodo.7244939",
                "filename": "Conductivtiy_experiment.csv",
                "size_bytes": SOURCE_SIZE,
                "md5": SOURCE_MD5,
                "sha256": SOURCE_SHA256,
                "license": "CC-BY-4.0",
            },
            "method_papers": [
                {
                    "doi": "10.1002/batt.202200228",
                    "title": "One-Shot Active Learning for Globally Optimal Battery Electrolyte Conductivity",
                },
                {
                    "doi": "10.1002/cmtd.202200008",
                    "title": "Data-Driven Analysis of High-Throughput Experiments on Liquid Battery Electrolyte Formulations",
                },
                {
                    "doi": "10.1039/D2DD00027J",
                    "title": "Learning the laws of lithium-ion transport in electrolytes using symbolic regression",
                },
            ],
            "upstream_analysis_repository": {
                "url": "https://github.com/BIG-MAP/electrolyte_optimization_one_shot_active_learning",
                "commit": "74ca52a0673cd33a313cfcfaad6bc271baa8ad0d",
            },
        },
        "contract": {
            "temperatures_c": list(TEMPERATURES_C),
            "source_complete_experiment_count": len(source_ids),
            "source_formulation_count": len(source_formulations),
            "candidate_complete_experiment_count": len(target_ids),
            "candidate_formulation_count": len(candidates),
            "target_campaigns": list(TARGET_CAMPAIGNS),
            "discovery_replicates_per_assay": DISCOVERY_REPLICATES,
            "confirmation_replicates_per_candidate": CONFIRMATION_REPLICATES,
            "batch_size": BATCH_SIZE,
            "assay_budget": ASSAY_BUDGET,
            "proxy": "degree-three ridge regression in log conductivity over public formulation ratios, fitted separately at each temperature with alpha 0.01",
        },
        "source_formulations": source_formulations,
        "candidates": candidates,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("csv", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    document = build(args.csv)
    rendered = json.dumps(
        document, indent=2, sort_keys=True, allow_nan=False, ensure_ascii=True
    ) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8")
    print(json.dumps({
        "output": str(args.output),
        "sha256": hashlib.sha256(rendered.encode("utf-8")).hexdigest(),
        "source_formulations": len(document["source_formulations"]),
        "candidate_formulations": len(document["candidates"]),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

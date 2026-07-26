#!/usr/bin/env python3
"""Build the frozen AlloyHardnessOptimization replay from the MPEA CSV.

The source is a literature compilation, so CSV rows are not independent alloy
experiments.  This builder keeps complete DOI studies together, collapses only
exact composition/process duplicates within one DOI, fits a historical public
proxy from studies published through 2016, and reserves every eligible 2018--
2019 study series as a later optimization world.  It never downloads data and
accepts only the exact Figshare v9 file.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np


SCHEMA_VERSION = 1
BUILDER_VERSION = "alloy-hardness-optimization-v1"
SOURCE_SIZE = 332_126
SOURCE_MD5 = "6d29eb6018157b863ca0033ccec936d5"
SOURCE_SHA256 = "c5504d93fd324d1be26cf814d0694ee9ee95578d68a0b38aba6813b939fa2c5d"
UPSTREAM_COMMIT = "d31e2510cccc3fb9e79d43ad62652f64ef8c2c5e"

SOURCE_MAX_YEAR = 2016
TARGET_MIN_YEAR = 2018
MIN_ELEMENTS = 4
MIN_WORLD_CANDIDATES = 4
ROOM_TEMPERATURE_C = 25.0
RIDGE_ALPHA_GRID = (0.1, 1.0, 10.0, 100.0, 1000.0)
BATCH_SIZE = 3
ASSAY_BUDGET = 2

FORMULA_TOKEN = re.compile(r"([A-Z][a-z]?)(\d+(?:\.\d*)?|\.\d+)")
HV_FIELD = "PROPERTY: HV"
PROCESS_FIELD = "PROPERTY: Processing method"
TEMPERATURE_FIELD = "PROPERTY: Test temperature ($^\\circ$C)"
MICROSTRUCTURE_FIELD = "PROPERTY: Microstructure"
DOI_FIELD = "REFERENCE: doi"
YEAR_FIELD = "REFERENCE: year"
TITLE_FIELD = "REFERENCE: title"


def _digest(path: Path, name: str) -> str:
    hasher = hashlib.new(name)
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(block)
    return hasher.hexdigest()


def _finite(value: str, field: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("non-numeric %s" % field) from exc
    if not math.isfinite(number):
        raise ValueError("non-finite %s" % field)
    return number


def _parse_formula(value: str) -> dict[str, float]:
    compact = str(value).replace(" ", "")
    amounts: dict[str, float] = {}
    position = 0
    for match in FORMULA_TOKEN.finditer(compact):
        if match.start() != position:
            raise ValueError("unsupported formula token in %s" % value)
        element, raw_amount = match.groups()
        amount = _finite(raw_amount, "formula amount")
        if amount <= 0.0:
            raise ValueError("formula amount must be positive")
        amounts[element] = amounts.get(element, 0.0) + amount
        position = match.end()
    if position != len(compact) or not amounts:
        raise ValueError("could not parse complete formula: %s" % value)
    total = sum(amounts.values())
    return {
        element: float(amount / total)
        for element, amount in sorted(amounts.items())
    }


def _composition_key(composition: dict[str, float]) -> tuple[tuple[str, float], ...]:
    return tuple((element, round(value, 12))
                 for element, value in sorted(composition.items()))


def _read_rows(path: Path) -> tuple[list[dict], int]:
    path = Path(path)
    if path.stat().st_size != SOURCE_SIZE:
        raise ValueError("unexpected MPEA CSV size")
    if _digest(path, "md5") != SOURCE_MD5:
        raise ValueError("unexpected MPEA CSV MD5")
    if _digest(path, "sha256") != SOURCE_SHA256:
        raise ValueError("unexpected MPEA CSV SHA-256")

    retained = []
    total_rows = 0
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for line_number, raw in enumerate(reader, 2):
            total_rows += 1
            hardness = str(raw[HV_FIELD]).strip()
            if not hardness:
                continue
            composition = _parse_formula(raw["FORMULA"])
            temperature = str(raw[TEMPERATURE_FIELD]).strip()
            process = str(raw[PROCESS_FIELD]).strip()
            if (
                len(composition) < MIN_ELEMENTS
                or not process
                or not temperature
                or _finite(temperature, "test temperature") != ROOM_TEMPERATURE_C
            ):
                continue
            doi = str(raw[DOI_FIELD]).strip().lower()
            title = str(raw[TITLE_FIELD]).strip()
            if not doi:
                raise ValueError("retained row lacks DOI")
            year = int(raw[YEAR_FIELD])
            retained.append({
                "source_line_number": int(line_number),
                "doi": doi,
                "year": year,
                "title": title,
                "reported_formula": str(raw["FORMULA"]).strip(),
                "composition": composition,
                "composition_key": _composition_key(composition),
                "processing_method": process,
                "reported_microstructure": (
                    str(raw[MICROSTRUCTURE_FIELD]).strip() or "UNREPORTED"
                ),
                "hardness_hv": _finite(hardness, "Vickers hardness"),
            })
    if total_rows != 1_545:
        raise ValueError("expected 1,545 MPEA data rows")
    if len(retained) != 358:
        raise ValueError("expected 358 eligible room-temperature hardness rows")
    return retained, total_rows


def _aggregate_recipes(rows: list[dict]) -> list[dict]:
    grouped: dict[tuple, list[dict]] = defaultdict(list)
    for row in rows:
        grouped[(
            row["doi"], row["composition_key"], row["processing_method"]
        )].append(row)

    recipes = []
    for (doi, composition_key, process), values in grouped.items():
        if len({row["year"] for row in values}) != 1:
            raise ValueError("DOI has inconsistent publication year")
        if len({row["title"] for row in values}) != 1:
            raise ValueError("DOI has inconsistent title")
        hardness = [float(row["hardness_hv"]) for row in values]
        recipes.append({
            "doi": doi,
            "year": int(values[0]["year"]),
            "title": values[0]["title"],
            "reported_formula": min(row["reported_formula"] for row in values),
            "composition": dict(composition_key),
            "processing_method": process,
            "hardness_hv": float(sum(hardness) / len(hardness)),
            "within_study_min_hv": float(min(hardness)),
            "within_study_max_hv": float(max(hardness)),
            "within_study_row_count": len(values),
            "source_line_numbers": sorted(
                int(row["source_line_number"]) for row in values
            ),
            "reported_microstructures": sorted({
                row["reported_microstructure"] for row in values
            }),
        })
    return sorted(recipes, key=lambda row: (
        row["doi"], tuple(row["composition"].items()), row["processing_method"]
    ))


def _feature_names(elements: tuple[str, ...], processes: tuple[str, ...]) -> tuple[str, ...]:
    names = ["fraction_%s" % element for element in elements]
    names += ["fraction_squared_%s" % element for element in elements]
    names += [
        "element_count_scaled", "mixing_entropy_scaled", "maximum_fraction"
    ]
    names += ["process_%s" % process for process in processes]
    return tuple(names)


def _features(rows: list[dict], elements: tuple[str, ...],
              processes: tuple[str, ...]) -> np.ndarray:
    matrix = []
    for row in rows:
        fractions = np.asarray([
            float(row["composition"].get(element, 0.0)) for element in elements
        ])
        entropy = -sum(value * math.log(value)
                       for value in fractions if value > 0.0)
        feature = list(fractions) + list(fractions * fractions)
        feature += [
            len(row["composition"]) / 10.0,
            entropy / 3.0,
            float(np.max(fractions)),
        ]
        feature += [
            float(row["processing_method"] == process) for process in processes
        ]
        matrix.append(feature)
    return np.asarray(matrix, dtype=float)


def _ridge_predict(train: list[dict], target: list[dict],
                   elements: tuple[str, ...], processes: tuple[str, ...],
                   alpha: float) -> np.ndarray:
    design = _features(train, elements, processes)
    target_design = _features(target, elements, processes)
    mean = np.mean(design, axis=0)
    scale = np.std(design, axis=0)
    active = scale > 1.0e-12
    standardized = (design[:, active] - mean[active]) / scale[active]
    standardized_target = (
        target_design[:, active] - mean[active]
    ) / scale[active]
    source_counts = Counter(row["doi"] for row in train)
    weights = np.asarray([1.0 / source_counts[row["doi"]] for row in train])
    weights /= np.mean(weights)
    x = np.column_stack((np.ones(len(train)), standardized))
    z = np.column_stack((np.ones(len(target)), standardized_target))
    y = np.asarray([row["hardness_hv"] for row in train])
    penalty = np.eye(x.shape[1])
    penalty[0, 0] = 0.0
    coefficients = np.linalg.solve(
        x.T @ (weights[:, None] * x) + float(alpha) * penalty,
        x.T @ (weights * y),
    )
    return z @ coefficients


def _select_ridge_alpha(source: list[dict], elements: tuple[str, ...],
                        processes: tuple[str, ...]) -> tuple[float, list[dict]]:
    studies = sorted({row["doi"] for row in source})
    records = []
    for alpha in RIDGE_ALPHA_GRID:
        study_mse = []
        study_mae = []
        for doi in studies:
            train = [row for row in source if row["doi"] != doi]
            test = [row for row in source if row["doi"] == doi]
            predicted = _ridge_predict(
                train, test, elements, processes, alpha
            )
            observed = np.asarray([row["hardness_hv"] for row in test])
            errors = predicted - observed
            study_mse.append(float(np.mean(errors ** 2)))
            study_mae.append(float(np.mean(abs(errors))))
        records.append({
            "alpha": float(alpha),
            "equal_study_weight_rmse_hv": float(math.sqrt(np.mean(study_mse))),
            "equal_study_weight_mae_hv": float(np.mean(study_mae)),
            "heldout_study_count": len(studies),
        })
    selected = min(
        records, key=lambda row: (row["equal_study_weight_rmse_hv"], row["alpha"])
    )
    return float(selected["alpha"]), records


def _fit_proxy(source: list[dict], target: list[dict]) -> tuple[np.ndarray, dict]:
    elements = tuple(sorted({
        element for row in source for element in row["composition"]
    }))
    processes = tuple(sorted({row["processing_method"] for row in source}))
    target_elements = {
        element for row in target for element in row["composition"]
    }
    if not target_elements.issubset(elements):
        raise ValueError("target contains an element absent from historical source")
    if not {row["processing_method"] for row in target}.issubset(processes):
        raise ValueError("target contains an unseen processing method")
    alpha, cross_validation = _select_ridge_alpha(
        source, elements, processes
    )
    predictions = _ridge_predict(
        source, target, elements, processes, alpha
    )
    if not np.all(np.isfinite(predictions)):
        raise ValueError("historical proxy produced non-finite predictions")
    names = _feature_names(elements, processes)
    source_feature_scale = np.std(
        _features(source, elements, processes), axis=0
    )
    active = source_feature_scale > 1.0e-12
    metadata = {
        "kind": (
            "ridge regression over elemental fractions, squared fractions, "
            "composition descriptors and processing indicators"
        ),
        "alpha": alpha,
        "alpha_grid": list(RIDGE_ALPHA_GRID),
        "alpha_selection": (
            "minimum equal-study-weight leave-one-DOI-out RMSE on historical "
            "proxy records only; ties choose the smaller alpha"
        ),
        "historical_leave_one_doi_out": cross_validation,
        "study_weighting": "each DOI has equal total regression weight",
        "elements": list(elements),
        "processing_methods": list(processes),
        "feature_names": list(names),
        "active_feature_names": [
            name for name, keep in zip(names, active) if keep
        ],
    }
    return predictions, metadata


def _split_map(dois: list[str]) -> dict[str, str]:
    ranked = sorted(
        dois,
        key=lambda doi: hashlib.sha256(
            ("doi:" + doi).encode("utf-8")
        ).hexdigest(),
    )
    return {
        doi: ("development" if index < 8 else "heldout")
        for index, doi in enumerate(ranked)
    }


def _public_candidate_id(world_id: str, index: int) -> str:
    digest = hashlib.sha256(
        (world_id + "|candidate|%d" % index).encode("utf-8")
    ).hexdigest()
    return "A-" + digest[:12]


def build(path: Path) -> dict:
    eligible_rows, total_rows = _read_rows(path)
    recipes = _aggregate_recipes(eligible_rows)
    historical_pool = [
        row for row in recipes if row["year"] <= SOURCE_MAX_YEAR
    ]
    later_by_doi: dict[str, list[dict]] = defaultdict(list)
    for row in recipes:
        if row["year"] >= TARGET_MIN_YEAR:
            later_by_doi[row["doi"]].append(row)
    target_dois = sorted(
        doi for doi, values in later_by_doi.items()
        if len(values) >= MIN_WORLD_CANDIDATES
        and not ({element for row in values for element in row["composition"]}
                 - {element for item in historical_pool
                    for element in item["composition"]})
    )
    if (len(historical_pool) != 205
            or len({row["doi"] for row in historical_pool}) != 44):
        raise ValueError("unexpected historical pool size")
    if len(target_dois) != 13:
        raise ValueError("expected thirteen eligible later-study worlds")

    target = [row for doi in target_dois for row in later_by_doi[doi]]
    target_recipe_keys = {
        (_composition_key(row["composition"]), row["processing_method"])
        for row in target
    }
    # An exact recipe measured by another DOI is reserved for source-held
    # confirmation.  It must not also teach the historical proxy.
    confirmation = [
        row for row in recipes
        if row["doi"] not in target_dois
        and (_composition_key(row["composition"]), row["processing_method"])
        in target_recipe_keys
    ]
    source = [
        row for row in historical_pool
        if (_composition_key(row["composition"]), row["processing_method"])
        not in target_recipe_keys
    ]
    if len(source) != 197 or len({row["doi"] for row in source}) != 44:
        raise ValueError("unexpected leakage-free historical source size")
    if len(confirmation) != 9:
        raise ValueError("unexpected independent confirmation size")
    predictions, proxy_metadata = _fit_proxy(source, target)
    for row, prediction in zip(target, predictions):
        row["proxy_hardness_hv"] = float(prediction)

    exact_recipe_sources: dict[tuple, list[dict]] = defaultdict(list)
    for row in confirmation:
        exact_recipe_sources[(
            _composition_key(row["composition"]), row["processing_method"]
        )].append(row)

    splits = _split_map(target_dois)
    worlds = []
    target_line_numbers = set()
    for world_index, doi in enumerate(target_dois):
        values = sorted(later_by_doi[doi], key=lambda row: (
            tuple(row["composition"].items()), row["processing_method"]
        ))
        world_id = "study-%02d" % world_index
        candidates = []
        for candidate_index, row in enumerate(values):
            target_line_numbers.update(row["source_line_numbers"])
            confirmations = []
            key = (_composition_key(row["composition"]), row["processing_method"])
            for other in exact_recipe_sources[key]:
                if other["doi"] == doi:
                    continue
                confirmations.append({
                    "doi": other["doi"],
                    "year": int(other["year"]),
                    "hardness_hv": float(other["hardness_hv"]),
                    "within_study_row_count": int(other["within_study_row_count"]),
                    "source_line_numbers": list(other["source_line_numbers"]),
                })
            candidates.append({
                "id": _public_candidate_id(world_id, candidate_index),
                "reported_formula": row["reported_formula"],
                "composition": row["composition"],
                "processing_method": row["processing_method"],
                "proxy_hardness_hv": float(row["proxy_hardness_hv"]),
                "study_hardness_hv": float(row["hardness_hv"]),
                "within_study_min_hv": float(row["within_study_min_hv"]),
                "within_study_max_hv": float(row["within_study_max_hv"]),
                "within_study_row_count": int(row["within_study_row_count"]),
                "source_line_numbers": list(row["source_line_numbers"]),
                "reported_microstructures": list(row["reported_microstructures"]),
                "independent_exact_recipe_confirmations": sorted(
                    confirmations, key=lambda item: (item["year"], item["doi"])
                ),
            })
        worlds.append({
            "id": world_id,
            "split": splits[doi],
            "source_doi": doi,
            "source_year": int(values[0]["year"]),
            "source_title": values[0]["title"],
            "candidate_count": len(candidates),
            "candidates": candidates,
        })
    if sum(world["split"] == "development" for world in worlds) != 8:
        raise ValueError("expected eight development worlds")
    if sum(world["split"] == "heldout" for world in worlds) != 5:
        raise ValueError("expected five held-out worlds")

    source_line_numbers = {
        line for row in source for line in row["source_line_numbers"]
    }
    if source_line_numbers & target_line_numbers:
        raise ValueError("historical and target source lines overlap")
    if {row["doi"] for row in source} & set(target_dois):
        raise ValueError("historical and target DOI groups overlap")
    source_recipe_keys = {
        (_composition_key(row["composition"]), row["processing_method"])
        for row in source
    }
    if source_recipe_keys & target_recipe_keys:
        raise ValueError("historical proxy and target exact recipes overlap")

    source_records = [{
        key: row[key] for key in (
            "doi", "year", "title", "reported_formula", "composition",
            "processing_method", "hardness_hv", "within_study_min_hv",
            "within_study_max_hv", "within_study_row_count",
            "source_line_numbers", "reported_microstructures",
        )
    } for row in source]
    return {
        "schema_version": SCHEMA_VERSION,
        "builder_version": BUILDER_VERSION,
        "source": {
            "article": {
                "title": "Expanded dataset of mechanical properties and observed phases of multi-principal element alloys",
                "doi": "10.1038/s41597-020-00768-9",
                "journal": "Scientific Data",
                "year": 2020,
                "volume": "7",
                "article_number": "430",
                "license": "CC-BY-4.0",
            },
            "dataset": {
                "title": "Expanded dataset of mechanical properties and observed phases of multi-principal element alloys",
                "doi": "10.6084/m9.figshare.12642953.v9",
                "filename": "MPEA_dataset.csv",
                "size_bytes": SOURCE_SIZE,
                "md5": SOURCE_MD5,
                "sha256": SOURCE_SHA256,
                "license": "CC-BY-4.0",
            },
            "upstream_repository": {
                "url": "https://github.com/CitrineInformatics/MPEA_dataset",
                "commit": UPSTREAM_COMMIT,
                "license": "Apache-2.0",
            },
            "lineage_note": (
                "The dataset is a literature compilation. DOI groups, not CSV rows, "
                "are the study-level independence unit; exact recipe duplicates are "
                "averaged only within one DOI."
            ),
        },
        "contract": {
            "total_csv_row_count": total_rows,
            "eligible_raw_row_count": len(eligible_rows),
            "historical_max_year": SOURCE_MAX_YEAR,
            "target_min_year": TARGET_MIN_YEAR,
            "room_temperature_c": ROOM_TEMPERATURE_C,
            "minimum_elements": MIN_ELEMENTS,
            "minimum_candidates_per_world": MIN_WORLD_CANDIDATES,
            "historical_pool_recipe_count": len(historical_pool),
            "historical_proxy_recipe_count": len(source),
            "historical_study_count": len({row["doi"] for row in source}),
            "reserved_confirmation_recipe_count": len(confirmation),
            "reserved_confirmation_study_count": len({
                row["doi"] for row in confirmation
            }),
            "target_world_count": len(worlds),
            "target_recipe_count": sum(len(world["candidates"]) for world in worlds),
            "development_world_count": sum(
                world["split"] == "development" for world in worlds
            ),
            "heldout_world_count": sum(
                world["split"] == "heldout" for world in worlds
            ),
            "batch_size": BATCH_SIZE,
            "assay_budget": ASSAY_BUDGET,
            "proxy": proxy_metadata,
            "target_selection_rule": (
                "all DOI studies from 2018 onward with at least four unique "
                "room-temperature recipes, reported processing, at least four "
                "elements, and no element absent from the historical vocabulary"
            ),
            "world_split_rule": (
                "sort normalized citation identifiers by SHA-256('doi:' + "
                "lowercase DOI); assign the first eight development and the "
                "remaining five heldout"
            ),
        },
        "historical_source_recipes": source_records,
        "reserved_confirmation_recipes": [{
            key: row[key] for key in (
                "doi", "year", "title", "reported_formula", "composition",
                "processing_method", "hardness_hv", "within_study_min_hv",
                "within_study_max_hv", "within_study_row_count",
                "source_line_numbers", "reported_microstructures",
            )
        } for row in confirmation],
        "worlds": worlds,
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
                "historical_proxy_recipes": len(
                    document["historical_source_recipes"]
                ),
                "reserved_confirmation_recipes": len(
                    document["reserved_confirmation_recipes"]
                ),
        "worlds": len(document["worlds"]),
        "target_recipes": sum(
            len(world["candidates"]) for world in document["worlds"]
        ),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

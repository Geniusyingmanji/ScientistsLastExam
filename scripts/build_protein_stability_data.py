#!/usr/bin/env python3
"""Build the frozen ProteinStabilityDesign landscapes from ProteinGym v1.3.

The builder deliberately requires the complete official reference table plus the
processed and raw substitution archives.  It never downloads data.  Exact source
hashes are checked before any CSV is parsed so a same-name upstream replacement
cannot silently change the benchmark.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import re
import zipfile
from collections import Counter, defaultdict
from pathlib import Path


SCHEMA_VERSION = 1
BUILDER_VERSION = "protein-stability-design-v1"
REFERENCE_SHA256 = "a8f498011532a74aa9fe556a50555a75e928c5837d19c06a87592ae04049b308"
PROCESSED_SHA256 = "3a83766254ac9ac9984ec25cb73c6e010ea4418f5e35f143933e6b6e6473b921"
RAW_SHA256 = "6d83b16585de2b71b67ae1985193b9eec2e01804784286c515ff276b5372e412"
PROTEINGYM_COMMIT = "144fe22b07dfaeec2b366f2346203a9838a55b4c"

# Positions are one-based here because the source mutation strings are one-based.
# The generated runtime contract also includes explicit zero-based positions.
WORLD_SPECS = (
    ("SPTN1_CHICK_Tsuboyama_2023_1TUD", (12, 49), "development"),
    ("UBE4B_HUMAN_Tsuboyama_2023_3L1X", (39, 41), "development"),
    ("CUE1_YEAST_Tsuboyama_2023_2MYX", (41, 46), "development"),
    ("RCRO_LAMBD_Tsuboyama_2023_1ORC", (36, 52), "development"),
    ("NUSA_ECOLI_Tsuboyama_2023_1WCL", (42, 60), "development"),
    ("VILI_CHICK_Tsuboyama_2023_1YU5", (28, 59), "heldout"),
    ("RBP1_HUMAN_Tsuboyama_2023_2KWH", (9, 12), "heldout"),
    ("CSN4_MOUSE_Tsuboyama_2023_1UFM", (14, 55), "heldout"),
)

MUTATION_RE = re.compile(r"^([ACDEFGHIKLMNPQRSTVWY])(\d+)([ACDEFGHIKLMNPQRSTVWY])$")
AA_ALPHABET = set("ACDEFGHIKLMNPQRSTVWY")
MAX_RELIABLE_DELTA_G_95CI = 0.5
DUMMY_DELTA_G_ABS_BOUND = 14.0


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _require_hash(path: Path, expected: str, label: str) -> None:
    observed = _sha256(path)
    if observed != expected:
        raise ValueError(
            "%s SHA-256 mismatch: expected %s, observed %s" %
            (label, expected, observed)
        )


def _read_zip_csv(archive: zipfile.ZipFile, member: str) -> list[dict[str, str]]:
    try:
        binary = archive.open(member)
    except KeyError as exc:
        raise ValueError("missing archive member: " + member) from exc
    with binary:
        text = io.TextIOWrapper(binary, encoding="utf-8-sig", newline="")
        return [dict(row) for row in csv.DictReader(text)]


def _parse_mutations(value: str) -> tuple[tuple[str, int, str], ...]:
    if not isinstance(value, str) or not value:
        raise ValueError("empty mutation token")
    parsed = []
    for token in value.split(":"):
        match = MUTATION_RE.fullmatch(token)
        if match is None:
            raise ValueError("unsupported mutation token: " + token)
        parsed.append((match.group(1), int(match.group(2)), match.group(3)))
    if len({position for _, position, _ in parsed}) != len(parsed):
        raise ValueError("mutation changes one position more than once: " + value)
    return tuple(parsed)


def _finite(value: str, field: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("non-numeric %s" % field) from exc
    if not math.isfinite(result):
        raise ValueError("non-finite %s" % field)
    return result


def _mutation_sequence(wild_type: str,
                       mutations: tuple[tuple[str, int, str], ...]) -> str:
    sequence = list(wild_type)
    for before, one_based, after in mutations:
        index = one_based - 1
        if not 0 <= index < len(sequence):
            raise ValueError("mutation position outside reference sequence")
        if sequence[index] != before:
            raise ValueError("mutation wild-type residue disagrees with reference")
        sequence[index] = after
    return "".join(sequence)


def _infer_wild_type(rows: list[dict[str, str]]) -> str:
    inferred = set()
    for row in rows:
        mutations = _parse_mutations(row["mutant"])
        sequence = list(row["mutated_sequence"])
        if not sequence or any(residue not in AA_ALPHABET for residue in sequence):
            raise ValueError("invalid processed amino-acid sequence")
        for before, one_based, after in mutations:
            index = one_based - 1
            if not 0 <= index < len(sequence) or sequence[index] != after:
                raise ValueError("processed sequence disagrees with mutation token")
            sequence[index] = before
        inferred.add("".join(sequence))
    if len(inferred) != 1:
        raise ValueError("processed assay does not imply one reference sequence")
    return inferred.pop()


def _mean_raw(rows: list[dict[str, str]], field: str) -> float:
    if not rows:
        raise ValueError("cannot aggregate an empty raw record set")
    values = [_finite(row[field], field) for row in rows]
    return float(sum(values) / len(values))


def _maximum_raw(rows: list[dict[str, str]], field: str) -> float:
    if not rows:
        raise ValueError("cannot aggregate an empty raw record set")
    return float(max(_finite(row[field], field) for row in rows))


def _raw_records_are_reliable(rows: list[dict[str, str]]) -> tuple[bool, str]:
    """Apply the paper's per-variant protease-readout quality criteria.

    The supplement states that impossible protease-specific delta-G estimates are
    replaced by dummy values and marks 95% confidence intervals wider than
    0.5 kcal/mol as lower confidence.  A duplicated amino-acid construct is admitted
    only when every source row passes, because averaging cannot repair an unreliable
    independent protease readout.
    """
    try:
        for row in rows:
            delta_t = _finite(row["deltaG_t"], "deltaG_t")
            delta_c = _finite(row["deltaG_c"], "deltaG_c")
            if (abs(delta_t) >= DUMMY_DELTA_G_ABS_BOUND
                    or abs(delta_c) >= DUMMY_DELTA_G_ABS_BOUND):
                return False, "dummy_protease_delta_g"
            for field in ("deltaG_95CI", "deltaG_t_95CI", "deltaG_c_95CI"):
                width = _finite(row[field], field)
                if width < 0.0 or width > MAX_RELIABLE_DELTA_G_95CI:
                    return False, "low_confidence_delta_g"
    except ValueError:
        return False, "nonfinite_raw_readout"
    return True, "reliable"


def _reference_rows(path: Path) -> dict[str, dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    result = {}
    for row in rows:
        identifier = row.get("DMS_id", "")
        if identifier:
            if identifier in result:
                raise ValueError("duplicate DMS_id in reference table: " + identifier)
            result[identifier] = dict(row)
    return result


def _build_world(identifier: str, positions: tuple[int, int], split: str,
                 reference: dict[str, str], processed: list[dict[str, str]],
                 raw: list[dict[str, str]]) -> dict:
    if not processed or not raw:
        raise ValueError("empty source table for " + identifier)
    wild_type = _infer_wild_type(processed)
    if wild_type != reference.get("target_seq"):
        raise ValueError("reference target sequence mismatch for " + identifier)
    if int(reference.get("seq_len", "-1")) != len(wild_type):
        raise ValueError("reference sequence length mismatch for " + identifier)
    if int(reference.get("DMS_total_number_mutants", "-1")) != len(processed):
        raise ValueError("processed row count mismatch for " + identifier)
    if reference.get("raw_DMS_phenotype_name") != "ddG_ML_float":
        raise ValueError("unexpected raw phenotype for " + identifier)
    if int(reference.get("raw_DMS_directionality", "0")) != 1:
        raise ValueError("unexpected phenotype direction for " + identifier)

    singles: dict[tuple[int, str], float] = {}
    for row in processed:
        mutations = _parse_mutations(row["mutant"])
        if len(mutations) != 1:
            continue
        before, position, after = mutations[0]
        if position not in positions:
            continue
        if wild_type[position - 1] != before:
            raise ValueError("single-mutant token disagrees with wild type")
        key = (position, after)
        score = _finite(row["DMS_score"], "DMS_score")
        if key in singles and singles[key] != score:
            raise ValueError("duplicate single-mutant score")
        singles[key] = score

    raw_by_sequence_and_mutation: dict[tuple[str, str], list[dict[str, str]]] = (
        defaultdict(list)
    )
    for row in raw:
        sequence = row.get("aa_seq", "")
        mutation = row.get("mut_type", "")
        if sequence and mutation:
            raw_by_sequence_and_mutation[(sequence, mutation)].append(row)

    candidates = []
    exclusions = Counter()
    seen_sequences = set()
    for row in processed:
        mutations = _parse_mutations(row["mutant"])
        if len(mutations) != 2 or {item[1] for item in mutations} != set(positions):
            continue
        by_position = {position: (before, after) for before, position, after in mutations}
        ordered_mutations = tuple(
            (by_position[position][0], position, by_position[position][1])
            for position in positions
        )
        sequence = _mutation_sequence(wild_type, ordered_mutations)
        if sequence != row["mutated_sequence"]:
            raise ValueError("double-mutant sequence mismatch for " + identifier)
        residues = tuple(by_position[position][1] for position in positions)
        try:
            additive = sum(singles[(position, residue)]
                           for position, residue in zip(positions, residues))
        except KeyError:
            exclusions["missing_single_mutation_proxy"] += 1
            continue
        raw_matches = raw_by_sequence_and_mutation.get((sequence, row["mutant"]), [])
        if not raw_matches:
            exclusions["missing_raw_sequence_mutation_match"] += 1
            continue
        reliable, reliability_reason = _raw_records_are_reliable(raw_matches)
        if not reliable:
            exclusions[reliability_reason] += 1
            continue
        try:
            aggregates = {
                "ddG_ML_float": _mean_raw(raw_matches, "ddG_ML_float"),
                "deltaG_t": _mean_raw(raw_matches, "deltaG_t"),
                "deltaG_c": _mean_raw(raw_matches, "deltaG_c"),
                # Conservatively retain the widest interval across duplicate constructs.
                "deltaG_95CI": _maximum_raw(raw_matches, "deltaG_95CI"),
                "deltaG_t_95CI": _maximum_raw(raw_matches, "deltaG_t_95CI"),
                "deltaG_c_95CI": _maximum_raw(raw_matches, "deltaG_c_95CI"),
            }
        except ValueError:
            exclusions["nonfinite_raw_readout"] += 1
            continue
        processed_score = _finite(row["DMS_score"], "DMS_score")
        # ProteinGym averages duplicate experimental constructs with the same amino-acid
        # sequence.  Requiring exact reconstruction prevents picking an arbitrary replicate.
        if abs(aggregates["ddG_ML_float"] - processed_score) > 1.0e-12:
            exclusions["processed_raw_aggregate_mismatch"] += 1
            continue
        if sequence in seen_sequences:
            raise ValueError("duplicate candidate amino-acid sequence")
        seen_sequences.add(sequence)
        candidates.append({
            "mutation": row["mutant"],
            "residues": list(residues),
            "sequence": sequence,
            "additive_proxy": float(additive),
            "stability_ddg": processed_score,
            "trypsin_delta_g": aggregates["deltaG_t"],
            "chymotrypsin_delta_g": aggregates["deltaG_c"],
            "combined_delta_g_95ci": aggregates["deltaG_95CI"],
            "trypsin_delta_g_95ci": aggregates["deltaG_t_95CI"],
            "chymotrypsin_delta_g_95ci": aggregates["deltaG_c_95CI"],
            "raw_replicate_count": len(raw_matches),
        })
    candidates.sort(key=lambda row: (tuple(row["residues"]), row["mutation"]))
    if len(candidates) < 300:
        raise ValueError("fewer than 300 complete double mutants for " + identifier)
    if not exclusions:
        exclusions["none"] = 0
    if len(singles) < 30:
        raise ValueError("incomplete single-mutant proxy for " + identifier)
    if len({row["additive_proxy"] for row in candidates}) < 20:
        raise ValueError("degenerate additive proxy for " + identifier)
    true_order = [row["sequence"] for row in sorted(
        candidates, key=lambda row: (-row["stability_ddg"], row["mutation"])
    )[:8]]
    proxy_order = [row["sequence"] for row in sorted(
        candidates, key=lambda row: (-row["additive_proxy"], row["mutation"])
    )[:8]]
    if true_order == proxy_order:
        raise ValueError("additive proxy exactly recovers the top batch for " + identifier)

    proxy_rows = []
    for position in positions:
        scores = {
            residue: score for (observed_position, residue), score in singles.items()
            if observed_position == position
            and any(row["residues"][positions.index(position)] == residue
                    for row in candidates)
        }
        proxy_rows.append({
            "position_one_based": position,
            "position_zero_based": position - 1,
            "wild_type_residue": wild_type[position - 1],
            "scores": dict(sorted(scores.items())),
        })
    return {
        "id": identifier,
        "split": split,
        "wild_type_sequence": wild_type,
        "positions_one_based": list(positions),
        "positions_zero_based": [position - 1 for position in positions],
        "single_mutation_proxy": proxy_rows,
        "candidate_count": len(candidates),
        "source_processed_row_count": len(processed),
        "source_raw_row_count": len(raw),
        "excluded_double_mutants": dict(sorted(exclusions.items())),
        "candidates": candidates,
    }


def build(reference_csv: Path, processed_zip: Path, raw_zip: Path) -> dict:
    reference_csv = Path(reference_csv)
    processed_zip = Path(processed_zip)
    raw_zip = Path(raw_zip)
    _require_hash(reference_csv, REFERENCE_SHA256, "ProteinGym reference table")
    _require_hash(processed_zip, PROCESSED_SHA256, "ProteinGym processed archive")
    _require_hash(raw_zip, RAW_SHA256, "ProteinGym raw archive")
    references = _reference_rows(reference_csv)
    worlds = []
    with zipfile.ZipFile(processed_zip) as processed_archive, zipfile.ZipFile(raw_zip) as raw_archive:
        for identifier, positions, split in WORLD_SPECS:
            if identifier not in references:
                raise ValueError("missing ProteinGym reference row: " + identifier)
            processed_member = "DMS_ProteinGym_substitutions/%s.csv" % identifier
            raw_member = "substitutions_raw_DMS/%s.csv" % identifier
            worlds.append(_build_world(
                identifier, positions, split, references[identifier],
                _read_zip_csv(processed_archive, processed_member),
                _read_zip_csv(raw_archive, raw_member),
            ))
    return {
        "schema_version": SCHEMA_VERSION,
        "builder_version": BUILDER_VERSION,
        "source": {
            "article": {
                "doi": "10.1038/s41586-023-06328-6",
                "title": "Mega-scale experimental analysis of protein folding stability in biology and design",
                "journal": "Nature",
                "year": 2023,
                "volume": "620",
                "pages": "434-444",
                "license": "CC-BY-4.0",
            },
            "proteingym": {
                "dataset_doi": "10.5281/zenodo.15293562",
                "version": "1.3",
                "repository": "https://github.com/OATML-Markslab/ProteinGym",
                "repository_commit": PROTEINGYM_COMMIT,
                "repository_license": "MIT",
            },
            "files": {
                "reference_table": {
                    "name": "DMS_substitutions.csv",
                    "sha256": REFERENCE_SHA256,
                },
                "processed_archive": {
                    "name": "DMS_ProteinGym_substitutions_v1.3.zip",
                    "sha256": PROCESSED_SHA256,
                },
                "raw_archive": {
                    "name": "substitutions_raw_DMS_v1.3.zip",
                    "sha256": RAW_SHA256,
                },
            },
            "retrieval_note": (
                "The frozen local archives were acquired from the ProteinGym download "
                "endpoint with curl --insecure after its TLS chain failed verification; "
                "the builder accepts them only at the exact hashes above."
            ),
            "reliability_note": (
                "The paper supplement states that impossible protease-specific delta-G "
                "estimates receive dummy values and labels 95% confidence intervals wider "
                "than 0.5 kcal/mol as lower confidence. Every retained raw replicate has "
                "finite non-dummy trypsin/chymotrypsin delta-G and all combined and "
                "protease-specific interval widths at or below 0.5 kcal/mol."
            ),
            "supplementary_methods_url": (
                "https://static-content.springer.com/esm/art%3A10.1038%2F"
                "s41586-023-06328-6/MediaObjects/41586_2023_6328_MOESM1_ESM.pdf"
            ),
            "supplementary_methods_sha256": (
                "7f8cea1118862735235984f477cd23ad900e0034aa5894dddbf11c0ade5aeb26"
            ),
        },
        "contract": {
            "batch_size": 8,
            "assay_budget": 12,
            "diversity_weight": 0.25,
            "public_assay_fields": ["stability_ddg", "combined_delta_g_95ci"],
            "sealed_readouts": ["trypsin_delta_g", "chymotrypsin_delta_g"],
            "maximum_reliable_delta_g_95ci": MAX_RELIABLE_DELTA_G_95CI,
            "dummy_delta_g_absolute_bound": DUMMY_DELTA_G_ABS_BOUND,
        },
        "worlds": worlds,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference-csv", type=Path, required=True)
    parser.add_argument("--processed-zip", type=Path, required=True)
    parser.add_argument("--raw-zip", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    document = build(args.reference_csv, args.processed_zip, args.raw_zip)
    rendered = json.dumps(
        document, indent=2, sort_keys=True, allow_nan=False, ensure_ascii=True
    ) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8")
    print(json.dumps({
        "output": str(args.output),
        "sha256": hashlib.sha256(rendered.encode("utf-8")).hexdigest(),
        "world_count": len(document["worlds"]),
        "candidate_counts": {
            row["id"]: row["candidate_count"] for row in document["worlds"]
        },
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

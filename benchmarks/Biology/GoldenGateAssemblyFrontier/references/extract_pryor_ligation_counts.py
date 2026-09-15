"""Rebuild the frozen sparse ligation table from Pryor et al. PLOS XLSX files.

Download the four source workbooks from the URLs in ``SOURCES`` without renaming them, then run:

    python extract_pryor_ligation_counts.py \
      --xlsx-dir /path/to/downloads --mirror-dir /path/to/omega-csv \
      --output /tmp/pryor_ligation_counts_v1.json --receipt /tmp/receipt.json

The mirror is optional and is used only as a cell-for-cell cross-check. It comes from the fixed
OMEGA commit recorded below; no OMEGA implementation code is imported or copied.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import json
from pathlib import Path
from xml.etree import ElementTree
from zipfile import ZipFile

XML_NAMESPACE = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
OMEGA_COMMIT = "160be2f"
SOURCES = (
    {
        "condition": "BsaI-HFv2",
        "supplement": "s001",
        "xlsx_name": "goldengate_pryor_s001.xlsx",
        "xlsx_sha256": "320dd058f3ca6372768c7ddfe9cda2a2ea2a076c4f86dd08587d8f295aae1d15",
        "mirror_name": "s001_bsai_cycling.csv",
        "mirror_sha256": "7d5d36ff9d21f3ca92b89d061fde2a9ae4dbec7b8787db0f5a9480efbf25d708",
    },
    {
        "condition": "BsmBI-v2",
        "supplement": "s002",
        "xlsx_name": "goldengate_pryor_s002.xlsx",
        "xlsx_sha256": "7c444e99e5e4d245461a892e8543a35c84987f93abcee7098de9d9d817237e94",
        "mirror_name": "s002_bsmbi_cycling.csv",
        "mirror_sha256": "6b22f2a3b6fbc601faea06a6a8c59292f753925b2a398575f8333c987c562fb7",
    },
    {
        "condition": "Esp3I",
        "supplement": "s003",
        "xlsx_name": "goldengate_pryor_s003.xlsx",
        "xlsx_sha256": "1557e62cfa4f89cd021420b75e145dae2f453ecf26dcca340a8c29008736ea66",
        "mirror_name": "s003_esp3i_cycling.csv",
        "mirror_sha256": "1888a07d2ff1044583ea0528cdba66b0248c1f4d37e5ad7c29ddef3850a98cf2",
    },
    {
        "condition": "BbsI-HF",
        "supplement": "s004",
        "xlsx_name": "goldengate_pryor_s004.xlsx",
        "xlsx_sha256": "56143bb445e6d84bba646429402e0948793395269cc5d8ba0e80962c0cac6492",
        "mirror_name": "s004_bbsi_cycling.csv",
        "mirror_sha256": "d7b35aecc0d3e57839ec3315a13796a38bf818c7a1304022afa65d4b72f2c87f",
    },
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _reverse_complement(sequence: str) -> str:
    return sequence.translate(str.maketrans("ACGT", "TGCA"))[::-1]


def _parse_xlsx(path: Path) -> list[list[str]]:
    with ZipFile(path) as archive:
        shared_root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
        shared = [
            "".join(node.text or "" for node in item.iter(XML_NAMESPACE + "t"))
            for item in shared_root.findall(XML_NAMESPACE + "si")
        ]
        sheet = ElementTree.fromstring(archive.read("xl/worksheets/sheet1.xml"))
    dimension = sheet.find(XML_NAMESPACE + "dimension")
    if dimension is None or dimension.attrib.get("ref") != "A1:IW257":
        raise ValueError("source workbook is not the expected 256 by 256 matrix")
    rows = []
    for row in sheet.iter(XML_NAMESPACE + "row"):
        values = []
        for cell in row.findall(XML_NAMESPACE + "c"):
            value = cell.find(XML_NAMESPACE + "v")
            text = "" if value is None else value.text or ""
            if cell.attrib.get("t") == "s":
                text = shared[int(text)]
            values.append(text)
        rows.append(values)
    return rows


def _parse_csv(path: Path) -> list[list[str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.reader(handle))


def _validated_matrix(rows: list[list[str]]) -> dict[str, dict[str, int]]:
    if len(rows) != 257 or any(len(row) != 257 for row in rows):
        raise ValueError("source table dimensions differ")
    expected = ["".join(chars) for chars in itertools.product("ACGT", repeat=4)]
    header = rows[0][1:]
    labels = [row[0] for row in rows[1:]]
    if rows[0][0] != "Overhang" or header != expected:
        raise ValueError("source column orientation differs")
    if labels != [_reverse_complement(overhang) for overhang in header]:
        raise ValueError("source row orientation differs")
    matrix = {}
    for row in rows[1:]:
        values = [int(value) for value in row[1:]]
        if any(value < 0 for value in values):
            raise ValueError("source table contains a negative count")
        matrix[row[0]] = dict(zip(header, values))
    return matrix


def rebuild(xlsx_dir: Path, mirror_dir: Path | None = None) -> tuple[dict, dict]:
    overhangs = ["".join(chars) for chars in itertools.product("ACGT", repeat=4)]
    canonical = [value for value in overhangs if value < _reverse_complement(value)][
        ::5
    ]
    subset = sorted(
        set(canonical + [_reverse_complement(value) for value in canonical])
    )
    output = {
        "schema_version": 1,
        "source": {
            "article": "Pryor et al., PLOS ONE 15:e0238592 (2020)",
            "doi": "10.1371/journal.pone.0238592",
            "license": "CC BY 4.0",
            "derivation": (
                "Exact integer cells for 24 deterministic reverse-complement classes and both "
                "orientations, builder-extracted directly from PLOS S1-S4 XLSX; absent sparse "
                "entries are zero."
            ),
            "orientation": (
                "Rows are 5-prime overhangs; columns are ligation partners; the correct partner "
                "of row s is reverse_complement(s)."
            ),
        },
        "canonical_overhangs": canonical,
        "conditions": {},
    }
    receipt_rows = []
    for source in SOURCES:
        xlsx_path = xlsx_dir / source["xlsx_name"]
        if _sha256(xlsx_path) != source["xlsx_sha256"]:
            raise ValueError(f"source hash differs for {source['supplement']}")
        rows = _parse_xlsx(xlsx_path)
        matrix = _validated_matrix(rows)
        mirror_match = None
        if mirror_dir is not None:
            mirror_path = mirror_dir / source["mirror_name"]
            if _sha256(mirror_path) != source["mirror_sha256"]:
                raise ValueError(f"mirror hash differs for {source['supplement']}")
            mirror_rows = _parse_csv(mirror_path)
            mirror_match = rows == mirror_rows
            if not mirror_match:
                raise ValueError(f"mirror cells differ for {source['supplement']}")
        sparse = {
            f"{left}>{right}": matrix[left][right]
            for left in subset
            for right in subset
            if matrix[left][right]
        }
        url = (
            "https://journals.plos.org/plosone/article/file?id="
            f"10.1371/journal.pone.0238592.{source['supplement']}&type=supplementary"
        )
        output["conditions"][source["condition"]] = {
            "supplement": source["supplement"],
            "url": url,
            "xlsx_sha256": source["xlsx_sha256"],
            "counts": sparse,
        }
        receipt_rows.append(
            {
                "condition": source["condition"],
                "source_url": url,
                "source_sha256": source["xlsx_sha256"],
                "matrix_rows": 256,
                "matrix_columns": 256,
                "orientation_check": "pass",
                "mirror_commit": OMEGA_COMMIT,
                "mirror_sha256": source["mirror_sha256"],
                "mirror_exact_cell_match": mirror_match,
            }
        )
    encoded = (json.dumps(output, indent=2, sort_keys=True) + "\n").encode("utf-8")
    receipt = {
        "schema_version": 1,
        "evidence_role": "builder_source_replay_receipt",
        "builder_source_replay_status": "pass",
        "independent_source_replay_status": "pending",
        "source_tables": receipt_rows,
        "derived_output_sha256": hashlib.sha256(encoded).hexdigest(),
        "claim_limit": (
            "This records a builder replay of source hashes, dimensions, orientation, extraction, "
            "and optional fixed-mirror equality. It is not an independent scientific review."
        ),
    }
    return output, receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--xlsx-dir", type=Path, required=True)
    parser.add_argument("--mirror-dir", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    output, receipt = rebuild(args.xlsx_dir, args.mirror_dir)
    args.output.write_text(
        json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    args.receipt.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

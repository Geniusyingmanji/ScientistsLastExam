#!/usr/bin/env python3
"""Prepare an operator-private observational pilot; never print measured values.

Only the two files in bundle/ belong to MeasurementAudit. The raw download,
source-row lineage and preparation record are trusted-operator material, never
candidate inputs. This is a descriptive temporal-transfer pilot, not a truth key.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
import math
import os
from pathlib import Path
import stat
from urllib.parse import urlparse
from urllib.request import urlopen


SOURCE_PAGE = "https://archive.ics.uci.edu/dataset/381/beijing+pm2+5+data"
SOURCE_CSV = "https://archive.ics.uci.edu/ml/machine-learning-databases/00381/PRSA_data_2010.1.1-2014.12.31.csv"
LICENSE = "https://creativecommons.org/licenses/by/4.0/"
DOI = "https://doi.org/10.24432/C5JS49"
MAX_DOWNLOAD_BYTES = 4 * 1024 * 1024
SOURCE_FIELDS = ["No", "year", "month", "day", "hour", "pm2.5", "DEWP", "TEMP", "PRES", "cbwd", "Iws", "Is", "Ir"]
YEARS = tuple(range(2010, 2015))
TRANSITION = datetime(2013, 1, 1)
EMBARGO_START = TRANSITION - timedelta(days=14)
EMBARGO_END = TRANSITION + timedelta(days=14)
RULES = {
    "version": "beijing-weekly-descriptive-v1",
    "years": list(YEARS),
    "block": "Nonoverlapping 168-hour blocks anchored at January 1 of each year; no block crosses years.",
    "complete_block": "Exactly all 168 unique hourly timestamps are required; partial year-end blocks are excluded.",
    "pm_coverage_minimum_hours": 126,
    "pm_missing": "Only literal NA is missing; finite nonnegative PM values otherwise required.",
    "exclusion_priority": ["incomplete_calendar_block", "boundary_embargo", "incomplete_hourly_grid", "pm_coverage_below_126"],
    "boundary_embargo_start_inclusive": EMBARGO_START.isoformat(),
    "boundary_embargo_end_exclusive": EMBARGO_END.isoformat(),
    "boundary_rule": "Exclude the whole block if any part overlaps the 14 days on either side of 2013-01-01.",
    "partition": "2010-2012 exploration; 2013-2014 sealed replication; no random split.",
    "season": "Season of block midpoint: DJF=0, MAM=1, JJA=2, SON=3.",
    "wind_regime": "0=NW fraction>=0.5 and SE<0.5; 1=SE fraction>=0.5 and NW<0.5; 2=other, including a 50/50 tie. Denominator is all 168 hours.",
    "uncertainty": "No independence guarantee, valid population standard error, significance decision or causal interpretation is supplied.",
}
COLUMNS = [
    {"name": "year", "unit": "calendar year", "description": "Calendar year of this within-year block; not a measured scientific endpoint."},
    {"name": "season_code", "unit": "category code", "description": RULES["season"]},
    {"name": "pm_mean", "unit": "ug/m^3", "description": "Arithmetic mean of observed hourly PM2.5 in a complete 168-hour block with at least 126 observed PM hours. Missing hours are omitted, not imputed."},
    {"name": "wind_regime", "unit": "category code", "description": RULES["wind_regime"]},
]


def digest(value):
    return hashlib.sha256(value).hexdigest()


def json_bytes(value):
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")


def parse_source(raw):
    """Validate source identifiers/timestamps before applying any cleaning rule."""
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig"), newline=""), strict=True)
    if reader.fieldnames != SOURCE_FIELDS:
        raise ValueError("unexpected source CSV header")
    rows, ids, times = [], set(), set()
    for line_number, row in enumerate(reader, start=2):
        if set(row) != set(SOURCE_FIELDS) or any(value is None for value in row.values()):
            raise ValueError("invalid source row dimensions at line {}".format(line_number))
        source_id = int(row["No"])
        if source_id <= 0 or source_id in ids:
            raise ValueError("invalid or duplicate source row ID")
        when = datetime(*(int(row[k]) for k in ("year", "month", "day", "hour")))
        if when.year not in YEARS or when in times:
            raise ValueError("out-of-scope or duplicate source timestamp")
        if row["pm2.5"] == "NA":
            pm = None
        else:
            pm = float(row["pm2.5"])
            if not math.isfinite(pm) or pm < 0:
                raise ValueError("PM observations must be finite and nonnegative or NA")
        if row["cbwd"] not in {"NW", "NE", "SE", "cv"}:
            raise ValueError("unrecognized wind-direction value")
        ids.add(source_id)
        times.add(when)
        rows.append({"source_id": source_id, "source_line": line_number, "when": when,
                     "pm": pm, "wind": row["cbwd"]})
    if not rows:
        raise ValueError("source CSV has no observations")
    return sorted(rows, key=lambda row: row["when"])


def transform(raw):
    """Deterministic transformation, including private lineage and full counts.

    Values are processed only to materialize the predeclared snapshot. No
    scientific contrast, partition statistic or parameter tuning is performed.
    """
    source = parse_source(raw)
    grouped = defaultdict(list)
    for row in source:
        anchor = datetime(row["when"].year, 1, 1)
        grouped[(row["when"].year, (row["when"] - anchor).days // 7)].append(row)
    excluded_blocks, excluded_rows = Counter(), Counter()
    counts = Counter()
    lineage, output = [], []
    for year in YEARS:
        anchor, next_year = datetime(year, 1, 1), datetime(year + 1, 1, 1)
        block_count = ((next_year - anchor).days + 6) // 7
        for block_index in range(block_count):
            start = anchor + timedelta(days=7 * block_index)
            end = start + timedelta(days=7)
            hourly = grouped[(year, block_index)]
            observed_pm = [row["pm"] for row in hourly if row["pm"] is not None]
            eligible_calendar = end <= next_year
            overlaps_embargo = start < EMBARGO_END and end > EMBARGO_START
            complete_grid = len(hourly) == 168  # Unique hourly timestamps already validated.
            reason = None
            if not eligible_calendar:
                reason = "incomplete_calendar_block"
            elif overlaps_embargo:
                reason = "boundary_embargo"
            elif not complete_grid:
                reason = "incomplete_hourly_grid"
            elif len(observed_pm) < 126:
                reason = "pm_coverage_below_126"
            sample_id = "beijing-{}-w{:02d}".format(year, block_index + 1)
            partition = "exploration" if year <= 2012 else "replication"
            lineage.append({
                "sample_id": sample_id, "partition": partition,
                "start_inclusive": start.isoformat(), "end_exclusive": min(end, next_year).isoformat(),
                "retained": reason is None, "exclusion_reason": reason,
                "source_row_ids": [row["source_id"] for row in hourly],
                "source_csv_line_numbers": [row["source_line"] for row in hourly],
                "observed_pm_hour_count": len(observed_pm),
                "source_columns": ["No", "year", "month", "day", "hour", "pm2.5", "cbwd"],
                "scope": "Conservatively bind every derived cell to all listed source rows and source columns, including selection and missingness.",
            })
            if reason:
                excluded_blocks[reason] += 1
                excluded_rows[reason] += len(hourly)
                continue
            wind_counts = Counter(row["wind"] for row in hourly)
            nw, se = wind_counts["NW"] >= 84, wind_counts["SE"] >= 84
            regime = 0 if nw and not se else (1 if se and not nw else 2)
            midpoint_month = (start + timedelta(days=3, hours=12)).month
            season = (midpoint_month % 12) // 3
            output.append([sample_id, partition, year, season, math.fsum(observed_pm) / len(observed_pm), regime])
            counts[partition] += 1
            counts["retained_source_rows"] += len(hourly)
            counts["retained_pm_observed_hours"] += len(observed_pm)
            counts["retained_pm_missing_hours"] += len(hourly) - len(observed_pm)
    text = io.StringIO(newline="")
    writer = csv.writer(text, lineterminator="\n")
    writer.writerow(["sample_id", "partition"] + [column["name"] for column in COLUMNS])
    writer.writerows(output)
    data = text.getvalue().encode("utf-8")
    expected_hours = sum((datetime(year + 1, 1, 1) - datetime(year, 1, 1)).days * 24 for year in YEARS)
    counters = {
        "source_rows": len(source), "expected_calendar_hours": expected_hours,
        "missing_hourly_timestamps": expected_hours - len(source),
        "source_pm_missing_hours": sum(row["pm"] is None for row in source),
        "source_rows_by_year": {str(year): sum(row["when"].year == year for row in source) for year in YEARS},
        "calendar_blocks_considered": len(lineage),
        "retained_blocks": len(output), "partition_counts": {p: counts[p] for p in ("exploration", "replication")},
        "excluded_blocks_by_first_reason": {key: excluded_blocks[key] for key in RULES["exclusion_priority"]},
        "excluded_source_rows_by_first_reason": {key: excluded_rows[key] for key in RULES["exclusion_priority"]},
        "retained_source_rows": counts["retained_source_rows"],
        "retained_pm_observed_hours": counts["retained_pm_observed_hours"],
        "retained_pm_missing_hours": counts["retained_pm_missing_hours"],
        "fatal_invalid_rows": 0,
    }
    assert counters["source_rows"] == counts["retained_source_rows"] + sum(excluded_rows.values())
    assert counters["calendar_blocks_considered"] == len(output) + sum(excluded_blocks.values())
    return data, counters, lineage


def manifest(data, raw_hash, transform_hash):
    return {
        "schema_version": 1, "dataset_id": "uci-beijing-pm25-weekly-descriptive-v1-" + digest(data)[:16],
        "provenance": {
            "kind": "observed_measurements",
            "citation": "Chen, S. (2015). Beijing PM2.5. UCI Machine Learning Repository. {}. CC BY 4.0: {}. Source: {}.".format(DOI, LICENSE, SOURCE_PAGE),
            "collection_description": "Historical hourly PM2.5 at the US Embassy, Beijing, with weather at Beijing Capital International Airport, 2010-2014. Fixed within-year complete 168-hour blocks, >=126 nonmissing PM hours; no imputation. Whole blocks touching [2012-12-18,2013-01-15) excluded. Raw SHA-256: {}; preparation script SHA-256: {}.".format(raw_hash, transform_hash),
            "target_population": "The retained historical weekly blocks from these two Beijing measurement sites; broader temporal or geographical generalization is unverified.",
            "independence_unit": "Nonoverlapping calendar block is the sampling unit, not an established independent unit; serial dependence and seasonal confounding remain.",
            "replication_design": "held_out_same_source",
            "limitations": [
                "2010-2012 is exploration; 2013-2014 is sealed same-source temporal checking, not independent collection or prospective acquisition.",
                "This public historical dataset may be present in model training data. It cannot establish a new scientific discovery or frontier difficulty.",
                "The current pooled mean-difference tool cannot adjust for season or compare both replication years separately. This pilot tests descriptive transport only, not the full seasonal-confounding question.",
                "Do not interpret the adapter's IID standard errors as validated uncertainty for dependent weekly time series. No p value, causal effect or scientific total score is supplied.",
                "PM and wind are measured at different sites. Unmeasured emissions, trends, coverage selection and measurement error can explain apparent associations.",
                "Missing PM hours are omitted within weeks and low-coverage weeks are excluded by frozen rules; nonrandom missingness is unresolved.",
                "Every derived row is one reused block of observations. Metadata, wind regime and PM summary are dependent views, never independent samples or fresh replications.",
                "Source-row lineage is stored in the trusted private preparation record. The current broker verifies derived CSV rows/columns only and cannot enforce cross-derived or raw-source overlap from that sidecar; prospective credit requires separate review of that lineage.",
                "Protocol/evidence checks and independent scientific review must remain separate. A supported numerical prediction does not certify mechanism, novelty or scientific truth.",
            ],
        },
        "columns": COLUMNS, "files": {"measurements.csv": digest(data)},
    }


def _fetch(url):
    with urlopen(url, timeout=60) as response:
        final = urlparse(response.geturl())
        if final.scheme != "https" or final.hostname != "archive.ics.uci.edu":
            raise ValueError("source redirected outside the official HTTPS host")
        raw = response.read(MAX_DOWNLOAD_BYTES + 1)
    if not raw or len(raw) > MAX_DOWNLOAD_BYTES:
        raise ValueError("source download empty or exceeds size bound")
    return raw


def create_private_root(path):
    path = Path(path).absolute()
    if path != path.resolve():
        raise ValueError("output path must not contain symlinks")
    if path.exists():
        raise ValueError("output path already exists; never replace a prior snapshot")
    for parent in path.parents:
        if (parent / ".git").exists():
            raise ValueError("raw/sealed observations must be stored outside every Git checkout")
    if not path.parent.is_dir():
        raise ValueError("output parent must already exist")
    path.mkdir(mode=0o700)
    if stat.S_IMODE(path.stat().st_mode) != 0o700:
        raise ValueError("private root must have mode 0700")
    return path


def write_private(path, data):
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(data)


def prepare(output_path):
    root = create_private_root(output_path)
    # Persist the frozen rules before fetching observations; no data-dependent tuning.
    source_code = Path(__file__).read_bytes()
    frozen = {"rules": RULES, "columns": COLUMNS, "script_sha256": digest(source_code),
              "frozen_at_utc": datetime.now(timezone.utc).isoformat()}
    write_private(root / "frozen_rules.json", json_bytes(frozen))
    write_private(root / "preparation_script.py", source_code)
    page = _fetch(SOURCE_PAGE)
    if b"creativecommons.org/licenses/by/4.0" not in page:
        raise ValueError("official dataset page did not confirm the declared CC BY 4.0 license")
    write_private(root / "source_page.html", page)
    raw = _fetch(SOURCE_CSV)
    write_private(root / "source.csv", raw)
    data, counters, lineage = transform(raw)
    if any(counters["partition_counts"][p] < 2 for p in ("exploration", "replication")):
        raise ValueError("insufficient retained blocks for the MeasurementAudit contract")
    lineage_bytes = json_bytes({"schema_version": 1, "raw_sha256": digest(raw), "derived_sha256": digest(data), "rows": lineage})
    write_private(root / "source_lineage.json", lineage_bytes)
    bundle = root / "bundle"
    bundle.mkdir(mode=0o700)
    manifest_bytes = json_bytes(manifest(data, digest(raw), digest(source_code)))
    write_private(bundle / "manifest.json", manifest_bytes)
    write_private(bundle / "measurements.csv", data)
    report = {
        "schema_version": 1, "status": "prepared_no_scientific_result_inspected",
        "source_page": SOURCE_PAGE, "source_csv": SOURCE_CSV, "license": LICENSE,
        "downloaded_at_utc": datetime.now(timezone.utc).isoformat(),
        "rules": RULES, "counters": counters,
        "hashes": {"source_csv_sha256": digest(raw), "source_page_sha256": digest(page),
                   "script_sha256": digest(source_code), "frozen_rules_sha256": digest(json_bytes(frozen)),
                   "source_lineage_sha256": digest(lineage_bytes), "measurements_sha256": digest(data),
                   "manifest_sha256": digest(manifest_bytes)},
        "lineage_enforcement": "sidecar_only_not_enforced_by_current_broker",
        "scientific_result": "not_assessed", "ground_truth": "absent",
        "warning": "Preparation counters describe selection/coverage only. Neither sealed values nor contrasts are included here. Raw data and full lineage must never be exposed to candidates.",
    }
    write_private(root / "preparation.json", json_bytes(report))
    return {"bundle": str(bundle), "hashes": report["hashes"], "counters": counters,
            "scientific_result": "not_assessed", "ground_truth": "absent"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="New canonical absolute private directory outside Git; never reused.")
    args = parser.parse_args()
    print(json.dumps(prepare(args.output), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

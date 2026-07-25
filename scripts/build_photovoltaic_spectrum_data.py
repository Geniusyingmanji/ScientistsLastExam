#!/usr/bin/env python3
"""Build the hash-bound ASTM G173 spectrum bundle used by the PV task.

The upstream copy is distributed by pvlib-python under BSD-3-Clause.  The
builder verifies the exact v0.13.1 bytes before converting the CSV to a compact
JSON record.  It is intentionally a build-time network tool; benchmark runtime
never uses the network.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


UPSTREAM_COMMIT = "6b9476b90892bd05726b237d9098f7536568a43a"
UPSTREAM_URL = (
    "https://raw.githubusercontent.com/pvlib/pvlib-python/"
    + UPSTREAM_COMMIT
    + "/pvlib/data/ASTMG173.csv"
)
UPSTREAM_SHA256 = "91964ac23c0ec82dbbda4a7f160a5f5faf551dfe18ffae7e2446d74b57ee7859"


def sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def download() -> bytes:
    request = urllib.request.Request(
        UPSTREAM_URL, headers={"User-Agent": "frontier-science-data-builder/1"}
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        payload = response.read()
    if sha256(payload) != UPSTREAM_SHA256:
        raise ValueError("ASTM G173 upstream hash mismatch")
    return payload


def build(payload: bytes) -> dict:
    text = payload.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO("\n".join(text.splitlines()[1:])))
    rows = []
    for row in reader:
        rows.append([
            float(row["wavelength"]),
            float(row["extraterrestrial"]),
            float(row["global"]),
            float(row["direct"]),
        ])
    if len(rows) != 2002 or rows[0][0] != 280.0 or rows[-1][0] != 4000.0:
        raise ValueError("unexpected ASTM G173 row grid")
    return {
        "schema_version": 1,
        "dataset": "ASTM G173-03 reference spectra derived from SMARTS v2.9.2",
        "columns": [
            "wavelength_nm",
            "extraterrestrial_w_m2_nm",
            "global_tilt_w_m2_nm",
            "direct_normal_w_m2_nm",
        ],
        "rows": rows,
        "source_provenance": {
            "upstream_project": "pvlib-python",
            "upstream_release": "v0.13.1",
            "upstream_commit": UPSTREAM_COMMIT,
            "upstream_url": UPSTREAM_URL,
            "upstream_sha256": UPSTREAM_SHA256,
            "license": "BSD-3-Clause",
            "license_url": (
                "https://github.com/pvlib/pvlib-python/blob/"
                + UPSTREAM_COMMIT
                + "/LICENSE"
            ),
            "citation_ids": [
                "doi:10.21105/joss.00884",
                "doi:10.1002/pip.1156",
            ],
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--retrieved-at",
        default="2026-07-25T14:37:02.771987+00:00",
        help="frozen retrieval timestamp retained in the deterministic bundle",
    )
    args = parser.parse_args()
    document = build(download())
    document["source_provenance"]["retrieved_at"] = args.retrieved_at
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(document, separators=(",", ":"), allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "row_count": len(document["rows"]),
        "upstream_sha256": document["source_provenance"]["upstream_sha256"],
        "output": str(args.output.resolve()),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

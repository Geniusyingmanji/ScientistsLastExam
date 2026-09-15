"""Host-side redesign diagnostic; does not modify or score the frozen task.

Run with the four original, prefetched XLSX files named by the source extractor:
    uv run python benchmarks/Biology/GoldenGateAssemblyFrontier/references/audit_full_panel.py \
        --xlsx-dir /path/to/workbooks --output /tmp/full-panel-audit.json

This evaluates a hypothetical 120-class panel using the existing public-input-only
beam search. It is an in-process builder experiment, not a sandbox or model draw.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import itertools
import json
import time
from pathlib import Path

TASK = Path(__file__).resolve().parents[1]


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def audit(xlsx_dir):
    extractor = _load(
        "panel_source", TASK / "references/extract_pryor_ligation_counts.py"
    )
    oracle = _load("panel_oracle", TASK / "verification/evaluator.py")
    reference = _load("panel_reference", TASK / "verification/reference_solver.py")
    words = ["".join(chars) for chars in itertools.product("ACGT", repeat=4)]
    classes = [word for word in words if word < extractor._reverse_complement(word)]
    conditions, sources = {}, []
    for source in extractor.SOURCES:
        path = xlsx_dir / source["xlsx_name"]
        digest = extractor._sha256(path)
        if digest != source["xlsx_sha256"]:
            raise ValueError(f"source hash differs: {path.name}")
        matrix = extractor._validated_matrix(extractor._parse_xlsx(path))
        conditions[source["condition"]] = {
            f"{left}>{right}": count
            for left, row in matrix.items()
            for right, count in row.items()
            if count
        }
        sources.append({"supplement": source["supplement"], "sha256": digest})
    results = []
    for profile in oracle._DEVELOPMENT_PROFILES + oracle._HELDOUT_PROFILES:
        problem = oracle._public_problem(profile)
        problem["canonical_overhangs"] = classes
        for name, condition in problem["conditions"].items():
            condition["ligation_counts"] = conditions[name]
        start = time.monotonic()
        result = reference._search(problem, beam_width=8, refinement_passes=4)
        artifact = reference._build(problem, result)
        value, error = oracle._validate(problem, artifact)
        if error is not None or value != result[0]:
            raise ValueError(
                f"assembly verification failed for {profile['id']}: {error}"
            )
        results.append(
            {
                "instance": profile["id"],
                "log_fidelity": value,
                "reaches_probability_upper_bound": value == 0.0,
                "seconds": time.monotonic() - start,
                "artifact": artifact,
            }
        )
    return {
        "evidence_role": "builder_in_process_redesign_diagnostic",
        "canonical_class_count": len(classes),
        "sources": sources,
        "code_sha256": {
            str(path.relative_to(TASK)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (
                Path(__file__).resolve(),
                TASK / "references/extract_pryor_ligation_counts.py",
                TASK / "verification/evaluator.py",
                TASK / "verification/reference_solver.py",
            )
        },
        "method": {"beam_width": 8, "refinement_passes": 4},
        "claim_limit": "Hypothetical expanded panel; no frozen-task scores, sandbox or model calibration.",
        "results": results,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--xlsx-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    args.output.write_text(
        json.dumps(audit(args.xlsx_dir), indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()

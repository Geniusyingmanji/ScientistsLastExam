"""Fixed construction screen: complete reference, all legacy rungs and 1120 strategies.

This imports the oracle in-process for a bounded construction audit. It is not a
sandbox run, model calibration, certification, or scientific-admission decision.
The separately declared standalone candidates must pass the real sandbox gate.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import itertools
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from sle.provenance import source_provenance

TASK = ROOT / "benchmarks/Biology/LDMismatchFineMapping"
HERE = Path(__file__).resolve().parent


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def measured(evaluator, name, candidate):
    started = time.monotonic()
    metrics = evaluator.evaluate(candidate)
    return {"name": name, "elapsed_seconds": time.monotonic() - started,
            "all_worlds_valid": all(r["valid"] for r in metrics["per_instance"]),
            "metrics": metrics}


def global_gap(world):
    """Independently enumerate every equal-size competitor, including joint swaps."""
    causal = world["causal"] or world["unresolved_causal"]
    k = len(causal)
    configs = np.asarray(list(itertools.combinations(range(len(world["z"])), k)))
    R, z = world["R"], world["z"]
    matrices = R[configs[:, :, None], configs[:, None, :]] + 1e-9 * np.eye(k)
    rhs = z[configs]
    fits = np.einsum("ij,ij->i", rhs, np.linalg.solve(matrices, rhs[:, :, None])[:, :, 0])
    own = float(z[causal] @ np.linalg.solve(R[np.ix_(causal, causal)] + 1e-9 * np.eye(k), z[causal]))
    excluded = {tuple(sorted(causal))}
    if world["duplicate"] is not None:
        i, j = world["duplicate"]
        excluded.add(tuple(sorted(i + j - v if v in (i, j) else v for v in causal)))
    alternatives = np.array([tuple(c) not in excluded for c in configs])
    return {"competitor_count": int(alternatives.sum()),
            "gap_to_best_other_configuration": own - float(fits[alternatives].max())}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=False)
    provenance = source_provenance(ROOT)
    if not provenance["git_available"] or provenance["source_tree_dirty"] is not False:
        raise SystemExit("requires a known clean source tree")
    evaluator = load(TASK / "verification/evaluator.py", "ld_admission_evaluator")
    # The legacy construction helpers import `evaluator`; share this exact cache.
    sys.modules["evaluator"] = evaluator
    probe = load(HERE / "probe.py", "ld_admission_probe")
    ablation = load(HERE / "ablation.py", "ld_admission_ablation")
    reference = load(TASK / "verification/reference_masking_aware.py", "ld_admission_complete")
    ranked = load(TASK / "verification/shortcut_ranked_rows.py", "ld_admission_ranked")
    grid = list(itertools.product(probe.LD, probe.MODEL, probe.REFUSAL, probe.EFFECTS))
    planned = {"schema_version": 1, "scope": "IN_PROCESS_CONSTRUCTION_SCREEN_ONLY",
               "source_provenance": provenance, "grid_count": len(grid),
               "grid": [list(item) for item in grid],
               "ablation_names": [name for name, _ in ablation.RUNGS],
               "world_specs": list(evaluator.DEVELOPMENT_WORLDS + evaluator.HELDOUT_WORLDS),
               "trusted_scientific_evidence": False, "scientific_admission": "not_assessed"}
    (args.output_dir / "plan.json").write_text(json.dumps(planned, indent=2))
    started = time.monotonic()
    cold_started = time.monotonic()
    worlds = [evaluator._world(spec) for spec in planned["world_specs"]]
    cold_seconds = time.monotonic() - cold_started
    print("Constructed %d worlds in %.3fs" % (len(worlds), cold_seconds), flush=True)
    construction = []
    for world in worlds:
        public = json.dumps(evaluator._public_problem(world), sort_keys=True).encode()
        construction.append({"kind": world["kind"], "seed": world["seed"],
                             "attempt": world["attempt"], "noise_draw": world["draw"],
                             "public_problem_sha256": hashlib.sha256(public).hexdigest(),
                             "single_swap_gap": world["gap"], **global_gap(world)})
    (args.output_dir / "construction.json").write_text(json.dumps(construction, indent=2))
    rungs = [("complete_masking_aware_reference", reference.fine_map),
             ("standalone_ranked_rows_shortcut", ranked.fine_map), *ablation.RUNGS]
    ablations = []
    with (args.output_dir / "ablations.jsonl").open("x") as stream:
        for name, candidate in rungs:
            row = measured(evaluator, name, candidate)
            ablations.append(row)
            stream.write(json.dumps(row) + "\n")
            stream.flush()
    rows = []
    with (args.output_dir / "grid.jsonl").open("x") as stream:
        for i, (ld, model, refusal, effects) in enumerate(grid):
            name = "%s|%s|%s|%s" % (ld, model, refusal, effects)
            row = measured(evaluator, name, probe.make_strategy(ld, model, refusal, effects))
            row.update({"cell_index": i, "ld": ld, "model": model,
                        "refusal": refusal, "effects": effects})
            rows.append(row)
            stream.write(json.dumps(row) + "\n")
            stream.flush()
            if (i + 1) % 100 == 0:
                print("Completed %d/%d grid cells" % (i + 1, len(grid)), flush=True)
    valid = [r for r in rows if r["all_worlds_valid"]]
    compact = lambda r: {k: r[k] for k in ("name", "all_worlds_valid", "metrics")}
    summary = {"schema_version": 1, "scope": planned["scope"],
               "source_provenance": provenance, "cold_world_seconds": cold_seconds,
               "elapsed_seconds": time.monotonic() - started,
               "planned_grid_cells": len(grid), "executed_grid_cells": len(rows),
               "fully_valid_grid_cells": len(valid),
               "best_grid": compact(max(rows, key=lambda r: r["metrics"]["combined_score"])),
               "best_fully_valid_grid": compact(max(valid, key=lambda r: r["metrics"]["combined_score"])) if valid else None,
               "ablations": [compact(r) for r in ablations],
               "global_competitor_gaps": construction,
               "trusted_scientific_evidence": False, "scientific_admission": "not_assessed"}
    (args.output_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps({"executed_grid_cells": len(rows), "fully_valid_grid_cells": len(valid),
                      "reference": ablations[0]["metrics"]["combined_score"],
                      "best_grid": summary["best_grid"]["metrics"]["combined_score"],
                      "elapsed_seconds": summary["elapsed_seconds"]}), flush=True)


if __name__ == "__main__":
    main()

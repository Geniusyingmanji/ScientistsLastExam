"""Recompute method probes; this is not frontier-model calibration."""
from __future__ import annotations

import argparse
import importlib.util
import json
import platform
import time
from pathlib import Path

TASK = Path(__file__).resolve().parents[1]


def load(relative, name):
    spec = importlib.util.spec_from_file_location(name, TASK / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    evaluator = load("verification/evaluator.py", "sorting_evaluator")
    probes = load("verification/shortcut_probes.py", "sorting_probes")
    search = load("verification/reference_search.py", "sorting_search")
    lookup = load("verification/reference_reconstruction.py", "sorting_lookup")
    methods = [
        ("batcher", probes.batcher),
        ("pruned_batcher", probes.pruned_batcher),
        ("window_grid", probes.window_grid),
        ("window_grid_pruned", probes.window_grid_pruned),
        ("insertion", probes.insertion),
        ("published_lookup", lookup.build_network),
        ("prefix_search", search.build_network),
        ("search_no_uphill", lambda n: search.search_network(n, max_extra=0)),
    ]
    rows = {}
    for name, candidate in methods:
        started = time.monotonic()
        result = evaluator.evaluate(candidate)
        result["wall_seconds"] = time.monotonic() - started
        rows[name] = result
        print(name, result["combined_score"],
              [row.get("size") for row in result["per_n"]], flush=True)
    report = {"platform": platform.platform(),
              "scope": "method_diagnostics_not_calibration", "rows": rows}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()

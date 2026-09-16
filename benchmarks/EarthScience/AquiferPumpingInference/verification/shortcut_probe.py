"""Low-dimensional summary-statistic shortcut sweep."""
from __future__ import annotations

import itertools
import json

import numpy as np

import evaluator


def _candidate(leak_cut, boundary_cut, curvature_cut, radius_count):
    def solve(problem, measure):
        rows = []
        radii = problem["observation_radii_m"][:radius_count]
        times = problem["observation_times_s"][1:5]
        for radius in radii:
            for time in times:
                rows.append(measure(radius, time))
        by_radius = {r: [x["drawdown_m"] for x in rows if x["radius_m"] == r] for r in radii}
        early_ratio = by_radius[radii[-1]][0] / max(by_radius[radii[0]][0], 1e-9)
        late_growth = by_radius[radii[0]][-1] / max(by_radius[radii[0]][-2], 1e-9)
        middle = np.asarray(by_radius[radii[len(radii) // 2]], dtype=float)
        curvature = abs(float(middle[-1] - 2 * middle[-2] + middle[-3])) / max(float(middle[-1]), 1e-9)
        if early_ratio < leak_cut:
            diagnosis = "leaky_aquifer"
        elif late_growth < boundary_cut:
            diagnosis = "recharge_boundary"
        elif curvature > curvature_cut:
            diagnosis = "dual_porosity"
        else:
            diagnosis = "confined"
        return {
            "diagnosis": diagnosis,
            "transmissivity_m2_s": 0.002,
            "storativity": 0.001,
            "predicted_drawdown_m": [0.0 for _ in problem["prediction_contexts"]],
            "confidence": 0.55,
            "abstain": diagnosis != "confined",
            "evidence_measurement_ids": [row["measurement_id"] for row in rows],
        }
    return solve


def main():
    best = None
    count = 0
    for values in itertools.product((0.01, 0.03, 0.08, 0.16),
                                    (1.25, 1.6, 2.1, 3.0),
                                    (0.02, 0.06, 0.14, 0.30),
                                    (3, 4, 5)):
        count += 1
        result = evaluator.evaluate(_candidate(*values))
        if best is None or result["combined_score"] > best["combined_score"]:
            best = {"settings": values, **result}
    print(json.dumps({"strategies": count, "best": best}, indent=2))


if __name__ == "__main__":
    main()

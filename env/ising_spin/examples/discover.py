"""Fit public moments, then check frozen predictions on fresh preparations."""

import argparse
import json
from itertools import combinations
from pathlib import Path

import numpy as np

from env.ising_spin import World, baseline
from env.ising_spin.world import NODES, PAIRS, _fit_public_model


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()
    world = World(args.seed)
    plan = json.loads(Path(__file__).with_name("experiments.json").read_text())
    records = [
        {"spec": spec, "observation": world.run(spec, noise_key="exploration-%03d" % i)}
        for i, spec in enumerate(plan)
    ]
    coefficients = _fit_public_model(records)
    report = {
        "description": "Operator-written public-data learning demonstration, not an agent benchmark result.",
        "exploration_experiments": len(records),
        "exploration_cost": sum(world.cost(spec) for spec in plan),
        "estimated_local_fields": coefficients[:6].tolist(),
        "estimated_couplings": {NODES[i] + "-" + NODES[j]: float(k) for (i, j), k in zip(PAIRS, coefficients[6:])},
    }
    triangles = []
    for nodes in combinations(range(6), 3):
        edges = list(combinations(nodes, 2))
        values = [float(coefficients[6 + PAIRS.index(pair)]) for pair in edges]
        if min(abs(value) for value in values) > 0.15 and np.prod(np.sign(values)) < 0:
            triangles.append([NODES[i] for i in nodes])
    report["candidate_frustrated_triangles_from_fitted_couplings"] = triangles
    report["triangle_scope"] = "Estimates based on noisy moments; no automatic mechanism verification or confidence interval."
    for kind in ("conditions", "interventions"):
        panel = world.panel(314159, kind)
        predictions = [baseline(records, spec) for spec in panel]
        residuals = []
        for spec, predicted in zip(panel, predictions):
            actual = np.asarray(world.run(spec)["values"])
            residuals.extend((np.asarray(predicted) - actual).ravel().tolist())
        report[kind + "_rmse"] = float(np.sqrt(np.mean(np.asarray(residuals) ** 2)))
    strongest = int(np.argmax(np.abs(coefficients[6:])))
    i, j = PAIRS[strongest]
    control = {"temperatures": [1.0]}
    treatment = {"temperatures": [1.0], "suppress_bonds": [{"nodes": [NODES[i], NODES[j]], "fraction": 1.0}]}
    predicted_effect = baseline(records, treatment)[0][6 + strongest] - baseline(records, control)[0][6 + strongest]
    fresh_effect = world.run(treatment)["values"][0][6 + strongest] - world.run(control)["values"][0][6 + strongest]
    report["illustrative_bond_suppression_effect"] = {
        "control": control,
        "treatment": treatment,
        "readout": {"row": 0, "channel": "c_" + NODES[i] + "_" + NODES[j]},
        "predicted_treatment_minus_control": predicted_effect,
        "fresh_clean_treatment_minus_control": fresh_effect,
        "scope": "This pair correlation and temperature only; does not itself establish a frustrated cycle or phase transition.",
    }
    print(json.dumps(report, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()

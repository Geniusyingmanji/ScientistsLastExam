"""Small trusted demonstration with fitting confined to public observations."""

import argparse
import json
from pathlib import Path

import numpy as np

from env.coupled_oscillators import World, baseline
from env.coupled_oscillators.world import NODES, PAIRS, _fit_public_coefficients


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()
    world = World(args.seed)
    specs = json.loads(Path(__file__).with_name("experiments.json").read_text())
    records = [
        {"spec": spec, "observation": world.run(spec, noise_key="exploration-%03d" % i)}
        for i, spec in enumerate(specs)
    ]
    grounding, drag, springs = _fit_public_coefficients(records)
    report = {
        "description": "Operator-written public-data demonstration, not an agent benchmark result.",
        "exploration_experiments": len(records),
        "exploration_cost": sum(world.cost(spec) for spec in specs),
        "estimated_grounding_N_per_m": grounding.tolist(),
        "estimated_drag_N_s_per_m": drag.tolist(),
        "estimated_pair_stiffness_N_per_m": {
            NODES[i] + "-" + NODES[j]: float(k) for (i, j), k in zip(PAIRS, springs)
        },
    }
    # Freeze every prediction before requesting its fresh clean target.
    for kind in ("conditions", "interventions"):
        panel = world.panel(314159, kind)
        predictions = [baseline(records, spec) for spec in panel]
        residuals = []
        for spec, prediction in zip(panel, predictions):
            actual = np.asarray(world.run(spec)["values"])
            mask = np.asarray(spec["times"]) > 0
            residuals.extend(((np.asarray(prediction)[mask] - actual[mask]) / world.scales).ravel().tolist())
        report[kind + "_postinitial_normalized_rmse"] = float(np.sqrt(np.mean(np.asarray(residuals) ** 2)))
    # Choose an illustrative paired effect using only the fitted public model.
    pair_index = int(np.argmax(springs))
    i, j = PAIRS[pair_index]
    initial = [0.0] * 4
    initial[i] = 0.8
    control = {"times": [1.4], "initial_position": initial}
    treatment = dict(control, cut_edges=[[NODES[i], NODES[j]]])
    predicted_effect = baseline(records, treatment)[0][j] - baseline(records, control)[0][j]
    verified_effect = world.run(treatment)["values"][0][j] - world.run(control)["values"][0][j]
    report["illustrative_effect"] = {
        "control": control,
        "treatment": treatment,
        "readout": {"row": 0, "channel": "x_" + NODES[j]},
        "predicted_treatment_minus_control_m": predicted_effect,
        "fresh_clean_treatment_minus_control_m": verified_effect,
        "scope": "Only this pair, preparation, readout and time; no automatic graph-certification claim.",
    }
    print(json.dumps(report, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()

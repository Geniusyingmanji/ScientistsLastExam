"""Cheap legitimate probe: eight random cubic seeds without shape search."""

import numpy as np


def search_crystals(problem, relax_structure):
    n = int(problem["atom_count"])
    low, high = problem["cell_volume_bounds"]
    rows = []
    for index in range(3):
        volume = low + (index + 1) / 9.0 * (high - low)
        length = volume ** (1.0 / 3.0)
        rng = np.random.default_rng(811 + 31 * n + index)
        coords = rng.random((n, 3))
        for i in range(n):
            for _ in range(200):
                if all(np.linalg.norm(((coords[i] - coords[j] + 0.5) % 1.0 - 0.5) * length) >= 0.48
                       for j in range(i)):
                    break
                coords[i] = rng.random(3)
        rows.append(relax_structure({"cell_lengths": [length] * 3,
                                     "fractional_coordinates": coords.tolist()}))
    return {"candidate_ids": [row["candidate_id"] for row in rows]}

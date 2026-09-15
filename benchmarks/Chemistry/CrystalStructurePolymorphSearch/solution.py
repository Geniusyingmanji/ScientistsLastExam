"""Weak but legal three-seed crystal search."""

import numpy as np


def _seed(problem, index):
    n = int(problem["atom_count"])
    low, high = problem["cell_volume_bounds"]
    volume = low + (0.25 + 0.12 * index) * (high - low)
    base = volume ** (1.0 / 3.0)
    shapes = ((1.0, 1.0, 1.0), (1.10, 0.95, 0.957), (0.94, 1.11, 0.958))
    shape = np.asarray(shapes[index], dtype=float)
    shape /= np.prod(shape) ** (1.0 / 3.0)
    rng = np.random.default_rng(1729 + 97 * n + index)
    coords = rng.random((n, 3))
    lengths = base * shape
    for i in range(n):
        for _ in range(200):
            if all(np.linalg.norm(((coords[i] - coords[j] + 0.5) % 1.0 - 0.5) * lengths) >= 0.48
                   for j in range(i)):
                break
            coords[i] = rng.random(3)
    return {"cell_lengths": lengths.tolist(), "fractional_coordinates": coords.tolist()}


def search_crystals(problem, relax_structure):
    records = [relax_structure(_seed(problem, index)) for index in range(3)]
    return {"candidate_ids": [row["candidate_id"] for row in records]}

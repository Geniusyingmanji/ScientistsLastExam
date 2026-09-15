"""Truth-blind deterministic 24-start crystal search witness."""

import hashlib
import itertools
import numpy as np


def _seed(problem, index):
    n = int(problem["atom_count"])
    low, high = problem["cell_volume_bounds"]
    volume = low + (0.12 + 0.76 * ((index * 0.61803398875) % 1.0)) * (high - low)
    base = volume ** (1.0 / 3.0)
    phase = 2.0 * np.pi * ((index * 0.41421356237) % 1.0)
    shape = np.exp(0.11 * np.array([np.sin(phase), np.sin(phase + 2.094), np.sin(phase + 4.189)]))
    shape /= np.prod(shape) ** (1.0 / 3.0)
    token = problem["formula"] + "|" + str(index)
    seed = int(hashlib.sha256(token.encode()).hexdigest()[:8], 16)
    rng = np.random.default_rng(seed)
    coords = rng.random((n, 3))
    lengths = base * shape
    for i in range(n):
        for _ in range(300):
            if all(np.linalg.norm(((coords[i] - coords[j] + 0.5) % 1.0 - 0.5) * lengths) >= 0.48
                   for j in range(i)):
                break
            coords[i] = rng.random(3)
    return {"cell_lengths": lengths.tolist(), "fractional_coordinates": coords.tolist()}


def _fingerprint(problem, structure):
    lengths = np.asarray(structure["cell_lengths"], dtype=float)
    coords = np.asarray(structure["fractional_coordinates"], dtype=float)
    distances = []
    species = problem["species"]
    for i in range(len(coords)):
        for j in range(i):
            delta = (coords[i] - coords[j] + 0.5) % 1.0 - 0.5
            pair = "".join(sorted((species[i], species[j])))
            distances.append((pair, np.linalg.norm(delta * lengths) /
                               np.prod(lengths) ** (1.0 / 3.0)))
    return np.asarray([value for _, value in sorted(distances)])


def _cubic_seed(problem, index):
    n = int(problem["atom_count"])
    low, high = problem["cell_volume_bounds"]
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
    return {"cell_lengths": [length] * 3, "fractional_coordinates": coords.tolist()}


def _utility(problem, rows):
    best = min(row["enthalpy_per_atom"] for row in rows)
    eligible = [row for row in rows if row["enthalpy_per_atom"] <=
                best + problem["energy_window_per_atom"]]
    diversity = 0.0
    if len(eligible) > 1:
        fingerprints = [_fingerprint(problem, row["relaxed_structure"]) for row in eligible]
        diversity = np.mean([
            np.sqrt(np.mean((left - right) ** 2))
            for i, left in enumerate(fingerprints) for right in fingerprints[:i]
        ])
    return -best + 0.15 * diversity


def search_crystals(problem, relax_structure):
    budget = int(problem["relaxation_budget_calls"])
    seeds = [_cubic_seed(problem, index) for index in range(8)]
    seeds.extend(_seed(problem, index) for index in range(budget - 8))
    records = [relax_structure(seed) for seed in seeds]
    selected = max(itertools.combinations(records, 3),
                   key=lambda group: _utility(problem, group))
    return {"candidate_ids": [row["candidate_id"] for row in selected]}

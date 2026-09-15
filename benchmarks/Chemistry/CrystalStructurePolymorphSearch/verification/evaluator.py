"""Trusted periodic binary-crystal search oracle with deterministic local relaxation."""

from __future__ import annotations

import hashlib
import itertools
import math
from collections.abc import Mapping
from functools import lru_cache

import numpy as np
from scipy.optimize import minimize


CRYSTAL_STRUCTURE_POLYMORPH_SEARCH_V1 = True
CALL_BUDGET = 24
RETURN_COUNT = 3
TRANSLATIONS = np.asarray(
    [(i, j, k) for i in (-2, -1, 0, 1, 2)
     for j in (-2, -1, 0, 1, 2) for k in (-2, -1, 0, 1, 2)],
    dtype=float,
)


def _world(name, split, species, epsilon, sigma, pressure, volume_bounds):
    return {
        "name": name, "split": split, "species": tuple(species),
        "epsilon": np.asarray(epsilon, dtype=float),
        "sigma": np.asarray(sigma, dtype=float),
        "pressure": float(pressure), "volume_bounds": tuple(volume_bounds),
    }


WORLDS = (
    _world("d0", "development", (0, 0, 1, 1), ((1.0, 1.35), (1.35, 0.80)),
           ((1.00, 0.92), (0.92, 1.08)), 0.04, (7.5, 18.0)),
    _world("d1", "development", (0, 0, 0, 0, 1, 1), ((0.90, 1.45), (1.45, 0.72)),
           ((1.02, 0.88), (0.88, 1.10)), 0.08, (10.0, 24.0)),
    _world("d2", "development", (0, 0, 1, 1, 1, 1), ((0.78, 1.40), (1.40, 1.02)),
           ((1.08, 0.90), (0.90, 1.00)), 0.12, (10.0, 24.0)),
    _world("h0", "heldout", (0, 0, 0, 1, 1), ((1.08, 1.28), (1.28, 0.86)),
           ((0.98, 0.91), (0.91, 1.06)), 0.06, (8.5, 21.0)),
    _world("h1", "heldout", (0, 0, 1, 1, 1), ((0.84, 1.50), (1.50, 0.76)),
           ((1.05, 0.87), (0.87, 1.12)), 0.10, (8.5, 21.0)),
)


def _formula(species):
    a = species.count(0)
    b = species.count(1)
    return "A%dB%d" % (a, b)


def _problem(world):
    return {
        "formula": _formula(world["species"]),
        "species": ["A" if value == 0 else "B" for value in world["species"]],
        "atom_count": len(world["species"]),
        "pair_epsilon": world["epsilon"].tolist(),
        "pair_sigma": world["sigma"].tolist(),
        "external_pressure_reduced": world["pressure"],
        "cell_volume_bounds": list(world["volume_bounds"]),
        "cell_length_bounds": [1.5, 4.5],
        "cell_aspect_ratio_limit": 2.2,
        "minimum_seed_separation": 0.42,
        "local_relaxation_model": "periodic shifted 12-6 binary Lennard-Jones plus P*V",
        "relaxation_budget_calls": CALL_BUDGET,
        "required_polymorph_count": RETURN_COUNT,
        "energy_window_per_atom": 0.40,
    }


def _finite(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float, np.integer, np.floating)):
        raise ValueError(name + " must be numeric")
    value = float(value)
    if not math.isfinite(value):
        raise ValueError(name + " must be finite")
    return value


def _normalize_structure(structure, world):
    if not isinstance(structure, Mapping) or set(structure) != {
        "cell_lengths", "fractional_coordinates"
    }:
        raise ValueError("structure has the wrong fields")
    lengths = structure["cell_lengths"]
    coords = structure["fractional_coordinates"]
    if not isinstance(lengths, (list, tuple)) or len(lengths) != 3:
        raise ValueError("cell_lengths must have length three")
    lengths = np.asarray([_finite(v, "cell length") for v in lengths], dtype=float)
    if np.any(lengths < 1.5) or np.any(lengths > 4.5):
        raise ValueError("cell length is outside the public bounds")
    volume = float(np.prod(lengths))
    if not world["volume_bounds"][0] <= volume <= world["volume_bounds"][1]:
        raise ValueError("cell volume is outside the public bounds")
    if float(np.max(lengths) / np.min(lengths)) > 2.2:
        raise ValueError("cell aspect ratio exceeds the public limit")
    if not isinstance(coords, (list, tuple)) or len(coords) != len(world["species"]):
        raise ValueError("fractional_coordinates has the wrong atom count")
    array = np.asarray(coords, dtype=float)
    if array.shape != (len(world["species"]), 3) or not np.all(np.isfinite(array)):
        raise ValueError("fractional_coordinates must be a finite N by 3 array")
    array %= 1.0
    for i in range(len(array)):
        for j in range(i):
            delta = (array[i] - array[j] + 0.5) % 1.0 - 0.5
            if float(np.linalg.norm(delta * lengths)) < 0.42:
                raise ValueError("seed atoms are too close")
    return lengths, array


def _enthalpy(world, lengths, coords):
    n = len(world["species"])
    ii = np.repeat(np.arange(n), n * len(TRANSLATIONS))
    jj = np.tile(np.repeat(np.arange(n), len(TRANSLATIONS)), n)
    translations = np.tile(TRANSLATIONS, (n * n, 1))
    keep = ~((ii == jj) & np.all(translations == 0.0, axis=1))
    ii, jj, translations = ii[keep], jj[keep], translations[keep]
    delta = (coords[jj] + translations - coords[ii]) * lengths
    distances = np.linalg.norm(delta, axis=1)
    species = np.asarray(world["species"], dtype=int)
    sigma = world["sigma"][species[ii], species[jj]]
    epsilon = world["epsilon"][species[ii], species[jj]]
    cutoff = 2.5 * sigma
    within = distances < cutoff
    safe = np.maximum(distances[within], 0.35 * sigma[within])
    sr6 = (sigma[within] / safe) ** 6
    cutoff_sr6 = (sigma[within] / cutoff[within]) ** 6
    shifted = 4.0 * epsilon[within] * (
        sr6 * sr6 - sr6 - cutoff_sr6 * cutoff_sr6 + cutoff_sr6
    )
    total = 0.5 * float(np.sum(shifted))
    volume = float(np.prod(lengths))
    return float(total + world["pressure"] * volume)


def _relax(world, structure):
    lengths, coords = _normalize_structure(structure, world)
    base = coords[0].copy()
    relative = (coords[1:] - base + 0.5) % 1.0 - 0.5
    log_lengths = np.log(lengths)
    centered = log_lengths - float(np.mean(log_lengths))
    x0 = np.r_[relative.ravel(), math.log(float(np.prod(lengths))), centered[:2]]
    low_volume, high_volume = world["volume_bounds"]

    def decode(x):
        rel = x[:-3].reshape((-1, 3))
        frac = np.vstack([np.zeros(3), rel]) % 1.0
        log_volume, shape_0, shape_1 = x[-3:]
        shape = np.asarray([shape_0, shape_1, -shape_0 - shape_1])
        cell = np.exp(log_volume / 3.0 + shape)
        return cell, frac

    def objective(x):
        cell, frac = decode(x)
        return _enthalpy(world, cell, frac)

    bounds = [(-0.75, 0.75)] * (3 * (len(coords) - 1)) + [
        (math.log(low_volume), math.log(high_volume)), (-0.12, 0.12), (-0.12, 0.12)
    ]
    result = minimize(objective, x0, method="L-BFGS-B", bounds=bounds,
                      options={"maxiter": 25, "ftol": 1.0e-9, "maxls": 20})
    relaxed_lengths, relaxed_coords = decode(result.x)
    volume = float(np.prod(relaxed_lengths))
    if not low_volume - 1e-5 <= volume <= high_volume + 1e-5:
        raise ValueError("local relaxation ended outside volume bounds")
    if float(np.max(relaxed_lengths) / np.min(relaxed_lengths)) > 2.2 + 1e-5:
        raise ValueError("local relaxation ended outside aspect bound")
    value = _enthalpy(world, relaxed_lengths, relaxed_coords) / len(world["species"])
    if not math.isfinite(value):
        raise ValueError("non-finite relaxed enthalpy")
    return {
        "cell_lengths": relaxed_lengths.tolist(),
        "fractional_coordinates": relaxed_coords.tolist(),
    }, float(value)


def _fingerprint(world, structure):
    lengths = np.asarray(structure["cell_lengths"], dtype=float)
    coords = np.asarray(structure["fractional_coordinates"], dtype=float)
    values = []
    for i in range(len(coords)):
        for j in range(i):
            delta = (coords[i] - coords[j] + 0.5) % 1.0 - 0.5
            distance = float(np.linalg.norm(delta * lengths))
            pair = world["species"][i] + world["species"][j]
            values.append((pair, distance / float(np.prod(lengths)) ** (1.0 / 3.0)))
    return np.asarray([value for _, value in sorted(values)], dtype=float)


def _utility(world, records):
    enthalpies = [row["enthalpy_per_atom"] for row in records]
    best = min(enthalpies)
    eligible = [row for row in records if row["enthalpy_per_atom"] <= best + 0.40]
    diversity = 0.0
    if len(eligible) > 1:
        fingerprints = [_fingerprint(world, row["relaxed_structure"]) for row in eligible]
        distances = [float(np.sqrt(np.mean((a - b) ** 2)))
                     for i, a in enumerate(fingerprints) for b in fingerprints[:i]]
        diversity = float(np.mean(distances))
    return float(-best + 0.15 * diversity), best, diversity, len(eligible)


class _Laboratory:
    def __init__(self, world):
        self.world = world
        self.calls = 0
        self.failure = None
        self.records = {}

    def relax_structure(self, structure):
        if self.calls >= CALL_BUDGET:
            self.failure = self.failure or "budget_exceeded"
            raise ValueError("relaxation budget exceeded")
        try:
            relaxed, enthalpy = _relax(self.world, structure)
        except Exception:
            self.failure = self.failure or "invalid_relaxation_query"
            raise
        self.calls += 1
        candidate_id = "crystal-%02d" % self.calls
        row = {"candidate_id": candidate_id, "enthalpy_per_atom": enthalpy,
               "relaxed_structure": relaxed}
        self.records[candidate_id] = row
        return {**row, "budget_cost": 1, "remaining_budget": CALL_BUDGET - self.calls}


def _evaluate_world(search_crystals, world, index):
    if hasattr(search_crystals, "reset_session"):
        search_crystals.reset_session()
    lab = _Laboratory(world)
    try:
        answer = search_crystals(_problem(world), lab.relax_structure)
        if lab.failure is not None:
            raise ValueError("callback contract was violated")
        if not isinstance(answer, Mapping) or set(answer) != {"candidate_ids"}:
            raise ValueError("submission must contain exactly candidate_ids")
        ids = answer["candidate_ids"]
        if not isinstance(ids, (list, tuple)) or len(ids) != RETURN_COUNT:
            raise ValueError("candidate_ids must contain exactly three IDs")
        if any(not isinstance(v, str) for v in ids) or len(set(ids)) != RETURN_COUNT:
            raise ValueError("candidate_ids must be distinct text")
        if not set(ids).issubset(lab.records):
            raise ValueError("candidate_ids must come from this callback session")
        utility, best, diversity, polymorphs = _utility(world, [lab.records[v] for v in ids])
    except Exception:
        return {"world_index": index, "split": world["split"], "valid": False,
                "utility": -1.0e6, "best_enthalpy_per_atom": 1.0e6,
                "polymorph_diversity": 0.0, "low_energy_polymorph_count": 0,
                "calls": lab.calls, "failure_kind": lab.failure or "invalid_submission"}
    return {"world_index": index, "split": world["split"], "valid": True,
            "utility": utility, "best_enthalpy_per_atom": best,
            "polymorph_diversity": diversity, "low_energy_polymorph_count": polymorphs,
            "calls": lab.calls, "failure_kind": None}


def _baseline_seed(world, index):
    n = len(world["species"])
    volume = world["volume_bounds"][0] + (0.25 + 0.12 * (index % 4)) * (
        world["volume_bounds"][1] - world["volume_bounds"][0]
    )
    base = volume ** (1.0 / 3.0)
    shapes = ((1.0, 1.0, 1.0), (1.10, 0.95, 0.957), (0.94, 1.11, 0.958))
    shape = np.asarray(shapes[index % len(shapes)])
    shape /= float(np.prod(shape)) ** (1.0 / 3.0)
    lengths = base * shape
    rng = np.random.default_rng(1729 + 97 * n + index)
    coords = rng.random((n, 3))
    # Rejection repair creates valid public seeds without seeing any relaxed energy.
    for i in range(n):
        for _ in range(200):
            if all(np.linalg.norm(((coords[i] - coords[j] + 0.5) % 1.0 - 0.5) * lengths) >= 0.48
                   for j in range(i)):
                break
            coords[i] = rng.random(3)
    return {"cell_lengths": lengths.tolist(), "fractional_coordinates": coords.tolist()}


def _baseline_records(world):
    return [dict(_zip_id(i + 1), **_record_from_relax(world, _baseline_seed(world, i)))
            for i in range(3)]


def _zip_id(index):
    return {"candidate_id": "anchor-%02d" % index}


def _record_from_relax(world, structure):
    relaxed, enthalpy = _relax(world, structure)
    return {"enthalpy_per_atom": enthalpy, "relaxed_structure": relaxed}


def _reference_seed(world, index):
    n = len(world["species"])
    low, high = world["volume_bounds"]
    volume = low + (0.12 + 0.76 * ((index * 0.61803398875) % 1.0)) * (high - low)
    base = volume ** (1.0 / 3.0)
    phase = 2.0 * np.pi * ((index * 0.41421356237) % 1.0)
    shape = np.exp(0.11 * np.asarray([
        np.sin(phase), np.sin(phase + 2.094), np.sin(phase + 4.189)
    ]))
    shape /= float(np.prod(shape)) ** (1.0 / 3.0)
    token = _formula(world["species"]) + "|" + str(index)
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


def _cubic_seed(world, index):
    n = len(world["species"])
    low, high = world["volume_bounds"]
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


def _reference_records(world):
    seeds = [_cubic_seed(world, i) for i in range(8)]
    seeds.extend(_reference_seed(world, i) for i in range(CALL_BUDGET - 8))
    records = [dict(_zip_id(i + 1), **_record_from_relax(world, seed))
               for i, seed in enumerate(seeds)]
    return list(max(itertools.combinations(records, RETURN_COUNT),
                    key=lambda group: _utility(world, group)[0]))


@lru_cache(maxsize=1)
def _anchors():
    result = {}
    for world in WORLDS:
        baseline = _utility(world, _baseline_records(world))[0]
        reference = _utility(world, _reference_records(world))[0]
        if reference <= baseline + 0.05:
            raise RuntimeError("crystal reference lacks material headroom")
        result[world["name"]] = (baseline, reference)
    return result


def _split_metrics(rows):
    scores = []
    for row in rows:
        world = WORLDS[row["world_index"]]
        baseline, reference = _anchors()[world["name"]]
        scores.append(max((row["utility"] - baseline) / (reference - baseline), 0.0)
                      if row["valid"] else 0.0)
    return {
        "score": float(np.mean(scores)),
        "mean_enthalpy": float(np.mean([row["best_enthalpy_per_atom"] for row in rows])),
        "mean_diversity": float(np.mean([row["polymorph_diversity"] for row in rows])),
        "mean_polymorph_count": float(np.mean([row["low_energy_polymorph_count"] for row in rows])),
        "mean_calls": float(np.mean([row["calls"] for row in rows])),
    }


def evaluate(search_crystals):
    rows = [_evaluate_world(search_crystals, world, i) for i, world in enumerate(WORLDS)]
    dev = _split_metrics([row for row in rows if row["split"] == "development"])
    hold = _split_metrics([row for row in rows if row["split"] == "heldout"])
    valid = float(all(row["valid"] for row in rows))
    return {
        "combined_score": dev["score"] if valid else 0.0,
        "valid": valid,
        "development_mean_best_enthalpy_per_atom": dev["mean_enthalpy"],
        "development_mean_polymorph_diversity": dev["mean_diversity"],
        "development_mean_low_energy_polymorph_count": dev["mean_polymorph_count"],
        "development_mean_relaxation_calls": dev["mean_calls"],
        "heldout_policy_score": hold["score"],
        "heldout_mean_best_enthalpy_per_atom": hold["mean_enthalpy"],
        "heldout_mean_polymorph_diversity": hold["mean_diversity"],
        "per_world": rows,
    }

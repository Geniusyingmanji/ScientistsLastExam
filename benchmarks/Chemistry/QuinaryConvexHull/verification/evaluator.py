"""Frozen oracle for QuinaryConvexHull (hidden from the agent).

A five-element catalog of integer compositions is public. Formation energies are an analytic
mixing-plus-well model, not a live MLIP. E_f < 0 is not a hull vertex: points a few meV above
the lower envelope must not be claimed, non-reproducing (glass) energies must be refused, and
an empty hull (unaries only) must not grow extra stables. This is not a 1-D XRD phase diagram
and not a stick-library species assignment.
"""
from __future__ import annotations

import itertools
import math
import re

import numpy as np
from scipy.optimize import linprog

N_ATOMS = 3
N_ELEM = 5
ELEMENTS = "ABCDE"
RELAX_BUDGET = 42
GLASS_TOLERANCE = 0.018
HULL_TOLERANCE = 1e-6
NEAR_HULL_LIFT = 0.012

PUBLIC_PROBLEM = {
    "elements": list(ELEMENTS),
    "n_atoms": N_ATOMS,
    "relax_budget_calls": RELAX_BUDGET,
    "max_claimed_stables": 8,
    "energy_unit": "eV_per_atom",
    "measurement_model": (
        "relax(name) returns a formation energy for a catalog composition; a repeat is a "
        "new draw of the same laboratory"
    ),
    "hull_note": (
        "a thermodynamically stable compound is a lower-convex-hull vertex besides the "
        "unaries; E_f < 0 is not that test"
    ),
    "abstain_when": (
        "energies do not reproduce under replication, or no unique hull is supported"
    ),
}


def _compositions():
    names = []
    comps = []
    for counts in itertools.product(range(N_ATOMS + 1), repeat=N_ELEM - 1):
        last = N_ATOMS - sum(counts)
        if last < 0:
            continue
        full = counts + (last,)
        name = "".join("%s%d" % (el, n) for el, n in zip(ELEMENTS, full))
        names.append(name)
        comps.append(np.array(full, dtype=float) / float(N_ATOMS))
    return names, np.asarray(comps)


CATALOG_NAMES, CATALOG_COMPS = _compositions()
NAME_INDEX = {name: i for i, name in enumerate(CATALOG_NAMES)}
UNARY_NAMES = [
    name for name, x in zip(CATALOG_NAMES, CATALOG_COMPS) if float(np.max(x)) >= 1.0 - 1e-12
]


def public_problem():
    return {
        "catalog": list(CATALOG_NAMES),
        "elements": list(ELEMENTS),
        "n_atoms": N_ATOMS,
        "relax_budget_calls": RELAX_BUDGET,
        "max_claimed_stables": 8,
        "energy_unit": PUBLIC_PROBLEM["energy_unit"],
        "measurement_model": PUBLIC_PROBLEM["measurement_model"],
        "hull_note": PUBLIC_PROBLEM["hull_note"],
        "abstain_when": PUBLIC_PROBLEM["abstain_when"],
    }


def parse_composition(name):
    match = re.fullmatch("".join("(%s)(\\d+)" % el for el in ELEMENTS), name)
    if not match:
        raise ValueError("name is not a catalog composition")
    counts = [int(match.group(2 * i + 2)) for i in range(N_ELEM)]
    if sum(counts) != N_ATOMS:
        raise ValueError("composition does not sum to n_atoms")
    return np.array(counts, dtype=float) / float(N_ATOMS)


def _wells_for(spec):
    wells = []
    for center, depth, width in spec.get("wells", ()):
        wells.append((np.asarray(center, dtype=float), float(depth), float(width)))
    return wells


def _base_energy(x, wells):
    mix = 0.16 * (1.0 - float(np.dot(x, x)))
    well_e = 0.0
    for center, depth, width in wells:
        well_e += depth * math.exp(-float(np.sum((x - center) ** 2)) / width)
    return mix - well_e


def _all_base_energies(wells):
    return np.array([_base_energy(x, wells) for x in CATALOG_COMPS], dtype=float)


def _lower_energy(energies, comps, index, support):
    others = [j for j in support if j != index]
    if len(others) < 2:
        return None
    a_eq = np.vstack([comps[others].T[:4], np.ones(len(others))])
    b_eq = np.append(comps[index][:4], 1.0)
    result = linprog(
        np.asarray(energies)[others],
        A_eq=a_eq,
        b_eq=b_eq,
        bounds=(0.0, None),
        method="highs",
    )
    if not result.success:
        return None
    return float(result.fun)


def hull_vertices(energies, comps=None, skip=None):
    comps = CATALOG_COMPS if comps is None else comps
    n = len(energies)
    skip = set() if skip is None else set(skip)
    vertices = []
    for i in range(n):
        if i in skip:
            continue
        hull_e = _lower_energy(energies, comps, i, [j for j in range(n) if j != i])
        if hull_e is None or float(energies[i]) <= hull_e + HULL_TOLERANCE:
            vertices.append(i)
    return vertices


def _decorate_near_hull(energies):
    """Place off-hull catalog points 8 meV/atom above the envelope, still E_f < 0."""
    decorated = np.array(energies, dtype=float, copy=True)
    verts = hull_vertices(decorated)
    for i in range(len(decorated)):
        if i in verts:
            continue
        hull_e = _lower_energy(decorated, CATALOG_COMPS, i, verts)
        if hull_e is not None and hull_e < -0.016:
            decorated[i] = hull_e + NEAR_HULL_LIFT
    return decorated


_ENERGY_CACHE = {}


def _frozen_energies(spec):
    if spec["kind"] == "glass":
        return None
    key = (spec["kind"], spec["seed"])
    if key not in _ENERGY_CACHE:
        energies = _all_base_energies(_wells_for(spec))
        if spec["kind"] in ("hull", "near_hull"):
            energies = _decorate_near_hull(energies)
        _ENERGY_CACHE[key] = energies
    return _ENERGY_CACHE[key]


def _truth(spec):
    if spec["kind"] == "glass":
        return None
    verts = hull_vertices(_frozen_energies(spec))
    stables = [CATALOG_NAMES[i] for i in verts if CATALOG_NAMES[i] not in UNARY_NAMES]
    return sorted(stables)


def _energy_draw(spec, name, call_index):
    rng = np.random.default_rng((int(spec["seed"]), 9, call_index, NAME_INDEX[name]))
    if spec["kind"] == "glass":
        return float(rng.uniform(-0.14, 0.16))
    energy = float(_frozen_energies(spec)[NAME_INDEX[name]])
    return float(energy + 0.0007 * rng.normal())


class _Lab:
    def __init__(self, spec):
        self.spec = spec
        self.used = 0
        self.violated = False
        self.calls = 0

    def relax(self, name):
        if name not in NAME_INDEX:
            raise ValueError("name is not in catalog")
        if self.used >= RELAX_BUDGET:
            self.violated = True
            raise RuntimeError("relax budget exhausted")
        self.used += 1
        self.calls += 1
        return _energy_draw(self.spec, name, self.calls)


def _validate_submission(submission):
    if not isinstance(submission, dict):
        raise ValueError("submission must be a mapping")
    abstain = submission.get("abstain", False)
    if not isinstance(abstain, bool):
        raise ValueError("abstain must be a boolean")
    confidence = float(submission.get("confidence", 0.0))
    if not math.isfinite(confidence):
        raise ValueError("confidence must be finite")
    if not 0.0 <= confidence <= 1.0:
        raise ValueError("confidence must lie in [0, 1]")
    if abstain:
        return [], confidence, True
    stables = submission.get("stable")
    if stables is None:
        raise ValueError("stable names are required unless abstaining")
    if not isinstance(stables, (list, tuple)):
        raise ValueError("stable must be a list of catalog names")
    if len(stables) > 8:
        raise ValueError("too many claimed stables")
    names = []
    seen = set()
    for item in stables:
        if item not in NAME_INDEX:
            raise ValueError("claimed name is not in catalog")
        if item in UNARY_NAMES:
            continue
        if item in seen:
            raise ValueError("duplicate claimed name")
        seen.add(item)
        names.append(item)
    return sorted(names), confidence, False


def _metrics(spec, claimed, abstain):
    row = {
        "mechanism_score": 0.0,
        "correct_refusal": False,
        "false_discovery": False,
        "set_correct": False,
    }
    if spec["kind"] == "glass":
        row.update({
            "mechanism_score": 1.0 if abstain else 0.0,
            "correct_refusal": bool(abstain),
            "false_discovery": not abstain,
        })
        return row
    true = _truth(spec)
    if abstain:
        return row
    correct = list(claimed) == list(true)
    row.update({
        "mechanism_score": 1.0 if correct else 0.0,
        "set_correct": correct,
    })
    return row


DEVELOPMENT_WORLDS = (
    {"kind": "hull", "seed": 61001, "wells": (
        ((2.0 / 3.0, 1.0 / 3.0, 0.0, 0.0, 0.0), 0.30, 0.014),
        ((0.0, 0.0, 1.0 / 3.0, 1.0 / 3.0, 1.0 / 3.0), 0.32, 0.018),
    )},
    {"kind": "hull", "seed": 61002, "wells": (
        ((2.0 / 3.0, 1.0 / 3.0, 0.0, 0.0, 0.0), 0.28, 0.014),
        ((0.0, 0.0, 0.0, 2.0 / 3.0, 1.0 / 3.0), 0.32, 0.014),
    )},
    {"kind": "near_hull", "seed": 61003, "wells": (
        ((1.0 / 3.0, 1.0 / 3.0, 1.0 / 3.0, 0.0, 0.0), 0.36, 0.022),
        ((2.0 / 3.0, 0.0, 0.0, 1.0 / 3.0, 0.0), 0.27, 0.016),
    )},
    {"kind": "empty", "seed": 62001, "wells": ()},
    {"kind": "glass", "seed": 63001, "wells": ()},
    {"kind": "glass", "seed": 63002, "wells": ()},
)

HELDOUT_WORLDS = (
    {"kind": "hull", "seed": 71001, "wells": (
        ((0.0, 1.0 / 3.0, 1.0 / 3.0, 1.0 / 3.0, 0.0), 0.33, 0.018),
        ((1.0 / 3.0, 0.0, 0.0, 0.0, 2.0 / 3.0), 0.29, 0.014),
    )},
    {"kind": "near_hull", "seed": 71002, "wells": (
        ((1.0 / 3.0, 1.0 / 3.0, 0.0, 1.0 / 3.0, 0.0), 0.35, 0.020),
        ((0.0, 0.0, 2.0 / 3.0, 0.0, 1.0 / 3.0), 0.28, 0.015),
    )},
    {"kind": "empty", "seed": 72001, "wells": ()},
    {"kind": "glass", "seed": 73001, "wells": ()},
    {"kind": "glass", "seed": 73002, "wells": ()},
)

ROW_KEYS = ("mechanism_score", "correct_refusal", "false_discovery", "set_correct")


def _evaluate_world(recover_hull, spec, split, index):
    lab = _Lab(spec)
    problem = public_problem()
    true = _truth(spec)
    base = {
        "split": split,
        "world_index": int(index),
        "kind": spec["kind"],
        "relax_calls": 0,
        "n_true_stables": 0 if true is None else len(true),
    }
    try:
        submission = recover_hull(problem, lab.relax)
        claimed, confidence, abstain = _validate_submission(submission)
        if lab.violated:
            raise RuntimeError("relax budget exceeded")
        metrics = _metrics(spec, claimed, abstain)
        row = dict(base)
        row.update({key: metrics[key] for key in ROW_KEYS})
        row.update({
            "valid": True,
            "abstained": bool(abstain),
            "claimed_count": len(claimed),
            "confidence": round(confidence, 6),
            "confidence_calibration_score": round(
                1.0 - (confidence - metrics["mechanism_score"]) ** 2, 6
            ),
            "relax_calls": lab.used,
        })
        row["mechanism_score"] = round(float(row["mechanism_score"]), 6)
        return row
    except Exception as exc:  # noqa: BLE001
        row = dict(base)
        row.update({key: (0.0 if key.endswith("_score") else False) for key in ROW_KEYS})
        row.update({
            "valid": False,
            "reason": "%s: %s" % (type(exc).__name__, exc),
            "abstained": True,
            "claimed_count": 0,
            "confidence": 0.0,
            "confidence_calibration_score": 0.0,
            "relax_calls": lab.used,
        })
        return row


def _split_summary(records):
    determinable = [r for r in records if r["kind"] != "glass"]
    unsupported = [r for r in records if r["kind"] == "glass"]
    raw = float(np.mean([r["mechanism_score"] for r in records]))
    always_abstain = len(unsupported) / len(records)
    normalized = float(np.clip((raw - always_abstain) / (1.0 - always_abstain), 0.0, 1.0))
    return {
        "normalized_mechanism": normalized,
        "raw_mechanism": raw,
        "signal_recovery_rate": float(np.mean([r["mechanism_score"] for r in determinable])),
        "false_discovery_rate": float(np.mean([r["false_discovery"] for r in unsupported])),
        "correct_refusal_rate": float(np.mean([r["correct_refusal"] for r in unsupported])),
        "discovery_coverage": float(np.mean([not r["abstained"] for r in determinable])),
        "confidence_calibration": float(np.mean([r["confidence_calibration_score"] for r in records])),
        "mean_relax_calls": float(np.mean([r["relax_calls"] for r in records])),
        "valid_count": sum(bool(r["valid"]) for r in records),
        "world_count": len(records),
    }


def _evaluate_specs(recover_hull, specs, split, *, reset_before_first=False):
    records = []
    for index, spec in enumerate(specs):
        if (index or reset_before_first) and hasattr(recover_hull, "reset_session"):
            recover_hull.reset_session()
        records.append(_evaluate_world(recover_hull, spec, split, index))
    return records


def evaluate(recover_hull):
    development = _evaluate_specs(recover_hull, DEVELOPMENT_WORLDS, "development")
    heldout = _evaluate_specs(
        recover_hull, HELDOUT_WORLDS, "heldout", reset_before_first=True
    )
    dev = _split_summary(development)
    held = _split_summary(heldout)
    return {
        "combined_score": dev["normalized_mechanism"],
        "valid": 1.0 if dev["valid_count"] > 0 else 0.0,
        "feasibility_rate": dev["valid_count"] / dev["world_count"],
        "raw_score": dev["normalized_mechanism"],
        "development_mechanism_score": dev["normalized_mechanism"],
        "development_raw_mechanism": dev["raw_mechanism"],
        "development_signal_recovery_rate": dev["signal_recovery_rate"],
        "development_false_discovery_rate": dev["false_discovery_rate"],
        "development_correct_refusal_rate": dev["correct_refusal_rate"],
        "development_discovery_coverage": dev["discovery_coverage"],
        "development_confidence_calibration": dev["confidence_calibration"],
        "development_mean_relax_calls": dev["mean_relax_calls"],
        "heldout_mechanism_score": held["normalized_mechanism"],
        "heldout_signal_recovery_rate": held["signal_recovery_rate"],
        "heldout_false_discovery_rate": held["false_discovery_rate"],
        "heldout_correct_refusal_rate": held["correct_refusal_rate"],
        "heldout_discovery_coverage": held["discovery_coverage"],
        "per_instance": development + heldout,
    }

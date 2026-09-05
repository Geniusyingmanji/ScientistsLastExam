"""Deterministic focal-mechanism stress inversion oracle.

A cluster of earthquakes reports both nodal planes of every focal mechanism, unlabelled
and noisy. Under the Wallace-Bott assumption (slip parallels the resolved shear
traction), the plane choice per event is a two-fold ambiguity and the stress tensor is
the shared hidden structure. The candidate may re-analyze a budgeted subset at tighter
uncertainty, then reports the principal stress axes, the shape ratio and one plane
choice per event — or refuses when the catalog is a mixture of stress regimes or carries
no coherent deviatoric signal at all.
"""

from __future__ import annotations

import hashlib
import math

import numpy as np

DIFFICULTY = 1

_DIFFICULTY_LADDER = {
    1: {"coarse_sigma_deg": 4.0, "fine_sigma_deg": 1.2, "shear_floor": 0.18},
    2: {"coarse_sigma_deg": 6.0, "fine_sigma_deg": 1.8, "shear_floor": 0.16},
    3: {"coarse_sigma_deg": 8.5, "fine_sigma_deg": 2.6, "shear_floor": 0.14},
}

EVENT_COUNT = 48
REANALYSIS_BUDGET = 16
REANALYSIS_COST = 1

_BASE_DEVELOPMENT_SPECS = (
    (33011, "supported"), (33017, "supported"), (33023, "supported"),
    (33029, "supported"), (33031, "supported"),
    (33037, "mixed"), (33041, "mixed"),
    (33047, "incoherent"),
)
HELDOUT_SPECS = (
    (43007, "supported"), (43013, "supported"), (43019, "supported"),
    (43023, "mixed"), (43029, "incoherent"),
)


def _difficulty_profile(level=None):
    level = DIFFICULTY if level is None else int(level)
    if level not in _DIFFICULTY_LADDER:
        raise ValueError("difficulty %d has no measured profile" % level)
    return _DIFFICULTY_LADDER[level]


def _angles_from_axis(axis):
    """(trend, plunge) in degrees for a unit axis."""
    x, y, z = axis / np.linalg.norm(axis)
    plunge = math.degrees(math.asin(max(-1.0, min(1.0, z))))
    trend = math.degrees(math.atan2(y, x)) % 360.0
    return trend, plunge


def _axis_from_angles(trend_deg, plunge_deg):
    tr, pl = math.radians(trend_deg), math.radians(plunge_deg)
    return np.asarray((math.cos(tr) * math.cos(pl),
                       math.sin(tr) * math.cos(pl), math.sin(pl)))


def _stress_tensor(sigma1_axis, sigma3_axis, ratio):
    """Deviatoric tensor with eigenvalues 1, 1-R, 0 on the given axes."""
    e1 = sigma1_axis / np.linalg.norm(sigma1_axis)
    e3 = sigma3_axis / np.linalg.norm(sigma3_axis)
    e3 = e3 - e1 * (e1 @ e3)
    e3 /= np.linalg.norm(e3)
    e2 = np.cross(e3, e1)
    return 1.0 * np.outer(e1, e1) + (1.0 - ratio) * np.outer(e2, e2)


def _plane_from_normal_slip(normal, slip):
    """(strike, dip, rake) degrees via the Aki-Richards plane geometry.

    With n = (-sin(d) sin(s), -sin(d) cos(s), cos(d)), the in-plane basis is the
    strike direction (cos s, -sin s, 0) and the up-dip direction
    (cos(d) sin(s), cos(d) cos(s), sin(d)); rake is the slip angle from strike.
    """
    normal = normal / np.linalg.norm(normal)
    dip = math.degrees(math.acos(max(-1.0, min(1.0, normal[2]))))
    strike = math.degrees(math.atan2(-normal[0], -normal[1])) % 360.0
    tr, dipr = math.radians(strike), math.radians(dip)
    cos_lam = slip[0] * math.cos(tr) - slip[1] * math.sin(tr)
    sin_lam = slip[2] / max(math.sin(dipr), 1e-12)
    lam = math.degrees(math.atan2(sin_lam, cos_lam))
    rake = ((lam + 180.0) % 360.0) - 180.0
    return strike, dip, rake


def _sample_stress(rng):
    trend1, plunge1 = float(rng.uniform(0, 360)), float(rng.uniform(5, 80))
    e1 = _axis_from_angles(trend1, plunge1)
    # sigma3 lies in the plane perpendicular to sigma1.
    azimuth = float(rng.uniform(0, 2 * math.pi))
    reference = np.cross(e1, (0.0, 0.0, 1.0))
    if np.linalg.norm(reference) < 1e-6:
        reference = np.cross(e1, (0.0, 1.0, 0.0))
    reference /= np.linalg.norm(reference)
    second = np.cross(e1, reference)
    e3 = math.cos(azimuth) * reference + math.sin(azimuth) * second
    e3 /= np.linalg.norm(e3)
    ratio = float(rng.uniform(0.15, 0.85))
    return e1, e3, ratio


def _shear(tensor, normal):
    traction = tensor @ normal
    normal_stress = float(normal @ traction)
    shear = traction - normal_stress * normal
    return shear


def _sample_events(rng, tensor, count, shear_floor):
    events = []
    guard = 0
    while len(events) < count and guard < 100 * count:
        guard += 1
        z = rng.uniform(-1, 1)
        phi = rng.uniform(0, 2 * math.pi)
        r = math.sqrt(1 - z * z)
        normal = np.asarray((r * math.cos(phi), r * math.sin(phi), z))
        shear = _shear(tensor, normal)
        magnitude = float(np.linalg.norm(shear))
        scale = float(np.linalg.norm(tensor))
        if magnitude < shear_floor * scale:
            continue
        slip = shear / magnitude
        events.append((normal, slip))
    return events


def _perturb_plane(rng, strike, dip, rake, sigma_deg):
    noisy = (strike + rng.normal(0, sigma_deg),
             dip + rng.normal(0, sigma_deg),
             rake + rng.normal(0, 2.0 * sigma_deg))
    dip = min(max(noisy[1], 5.0), 89.0)
    return [float(noisy[0] % 360.0), float(dip), float(((noisy[2] + 180.0) % 360.0) - 180.0)]


def _world(spec):
    seed, kind = spec
    profile = _difficulty_profile()
    rng = np.random.default_rng(int(seed))
    e1, e3, ratio = _sample_stress(rng)
    tensor = _stress_tensor(e1, e3, ratio)
    if kind == "supported":
        events = _sample_events(rng, tensor, EVENT_COUNT, profile["shear_floor"])
    elif kind == "mixed":
        f1, f3, fr = _sample_stress(rng)
        second_tensor = _stress_tensor(f1, f3, fr)
        first = _sample_events(rng, tensor, EVENT_COUNT // 2 + 4,
                               profile["shear_floor"])
        second = _sample_events(rng, second_tensor, EVENT_COUNT - len(first),
                                profile["shear_floor"])
        events = first + second
    else:
        events = []
        while len(events) < EVENT_COUNT:
            z = rng.uniform(-1, 1)
            phi = rng.uniform(0, 2 * math.pi)
            r = math.sqrt(1 - z * z)
            normal = np.asarray((r * math.cos(phi), r * math.sin(phi), z))
            slip = rng.normal(size=3)
            slip -= normal * (normal @ slip)
            norm = np.linalg.norm(slip)
            if norm < 1e-6:
                continue
            events.append((normal, slip / norm))
    catalog = []
    assignments = []
    reanalyzed_draw = {}
    for index, (normal, slip) in enumerate(events):
        fault = _plane_from_normal_slip(normal, slip)
        auxiliary = _plane_from_normal_slip(slip, normal)
        swap = bool(rng.random() < 0.5)
        planes = [fault, auxiliary] if not swap else [auxiliary, fault]
        assignments.append(1 if swap else 0)
        coarse = [_perturb_plane(rng, *plane, profile["coarse_sigma_deg"])
                  for plane in planes]
        fine = [_perturb_plane(rng, *plane, profile["fine_sigma_deg"])
                for plane in planes]
        reanalyzed_draw[index] = fine
        catalog.append({"id": index,
                        "plane_a": coarse[0], "plane_b": coarse[1]})
    return {
        "seed": int(seed), "kind": kind, "sigma1": e1, "sigma3": e3, "ratio": ratio,
        "tensor": tensor, "events": events, "catalog": catalog,
        "assignments": assignments, "reanalyzed": reanalyzed_draw,
        "reanalyzed_ids": set(),
    }


def problem_statement(world):
    return {
        "event_count": len(world["catalog"]),
        "events": [{"id": row["id"], "plane_a": row["plane_a"],
                    "plane_b": row["plane_b"]} for row in world["catalog"]],
        "plane_convention": "strike, dip, rake in degrees (Aki-Richards); each event lists both nodal planes in arbitrary order",
        "noise_sigma_deg": _difficulty_profile()["coarse_sigma_deg"],
        "reanalysis_sigma_deg": _difficulty_profile()["fine_sigma_deg"],
        "reanalysis_budget": REANALYSIS_BUDGET,
        "reanalysis_cost": REANALYSIS_COST,
        "model_note": (
            "under the Wallace-Bott assumption slip parallels the resolved shear "
            "traction of one deviatoric stress tensor; sigma2 is the cross product of "
            "the reported axes; R = (sigma1 - sigma2)/(sigma1 - sigma3)"
        ),
    }


class _Observatory:
    """Charged interface: waveform re-analysis tightens one event's mechanisms."""

    def __init__(self, world):
        self.world = world
        self.used = 0
        self.calls = 0
        self.violated = False

    def reanalyze(self, event_id):
        try:
            if event_id not in {row["id"] for row in self.world["catalog"]}:
                self.violated = True
                raise ValueError("unknown event id")
            if event_id in self.world["reanalyzed_ids"] or \
                    self.used + REANALYSIS_COST > REANALYSIS_BUDGET:
                self.violated = True
                raise RuntimeError("event already reanalyzed or budget exceeded")
            self.used += REANALYSIS_COST
            self.calls += 1
            self.world["reanalyzed_ids"].add(event_id)
            planes = self.world["reanalyzed"][event_id]
            return {"id": event_id, "plane_a": list(planes[0]),
                    "plane_b": list(planes[1]), "budget_cost": REANALYSIS_COST}
        except Exception:
            self.violated = True
            raise


def _validate(submission, world):
    if not isinstance(submission, dict):
        raise ValueError("submission must be a mapping")
    abstain = submission.get("abstain")
    if not isinstance(abstain, (bool, np.bool_)):
        raise ValueError("abstain must be boolean")
    confidence = float(submission.get("confidence"))
    if not math.isfinite(confidence) or not 0.0 <= confidence <= 1.0:
        raise ValueError("confidence must be in [0,1]")
    if bool(abstain):
        if submission.get("sigma1") or submission.get("sigma3") \
                or submission.get("plane_assignments"):
            raise ValueError("abstention requires empty structure")
        return None, None, None, confidence, True
    sigma1 = np.asarray(submission.get("sigma1"), dtype=float).reshape(-1)
    sigma3 = np.asarray(submission.get("sigma3"), dtype=float).reshape(-1)
    if sigma1.shape != (2,) or sigma3.shape != (2,):
        raise ValueError("sigma1 and sigma3 must be (trend, plunge) degree pairs")
    if not 0.0 <= float(sigma1[0]) < 360.0 or not 0.0 <= float(sigma3[0]) < 360.0:
        raise ValueError("trend must lie in [0,360)")
    if not -90.0 <= float(sigma1[1]) <= 90.0 or not -90.0 <= float(sigma3[1]) <= 90.0:
        raise ValueError("plunge must lie in [-90,90]")
    ratio = float(submission.get("R"))
    if not math.isfinite(ratio) or not 0.0 <= ratio <= 1.0:
        raise ValueError("R must lie in [0,1]")
    assignments = np.asarray(submission.get("plane_assignments")).reshape(-1)
    if assignments.shape != (len(world["catalog"]),) or \
            np.any(~np.isin(assignments, (0, 1))):
        raise ValueError("plane_assignments must be a 0/1 row over every event")
    return sigma1, sigma3, (ratio, assignments.astype(int)), confidence, False


def _axis_cosine(predicted_axis, true_axis):
    predicted = predicted_axis / np.linalg.norm(predicted_axis)
    return abs(float(predicted @ true_axis))


def _mechanism_score(world, sigma1, sigma3, payload):
    ratio, assignments = payload
    predicted_e1 = _axis_from_angles(float(sigma1[0]), float(sigma1[1]))
    predicted_e3 = _axis_from_angles(float(sigma3[0]), float(sigma3[1]))
    c1 = _axis_cosine(predicted_e1, world["sigma1"])
    c3 = _axis_cosine(predicted_e3, world["sigma3"])
    axis_score = float(np.clip((0.5 * (c1 + c3) - 0.5) / 0.5, 0.0, 1.0))
    r_score = float(math.exp(-6.0 * abs(ratio - world["ratio"])))
    truth = np.asarray(world["assignments"])
    accuracy = float(np.mean(assignments == truth))
    plane_score = max(0.0, 2.0 * accuracy - 1.0)
    return float((axis_score * r_score * plane_score) ** (1.0 / 3.0)), axis_score, r_score, plane_score


def _empty(split, index):
    return {"split": split, "world_index": index, "valid": False, "abstained": False,
            "mechanism_score": 0.0, "axis_score": 0.0, "r_score": 0.0,
            "plane_score": 0.0, "false_discovery": False, "correct_refusal": False,
            "confidence_score": 0.0, "budget_used": 0}


def _evaluate_world(candidate, spec, split, index):
    row = _empty(split, index)
    world = _world(spec)
    observatory = _Observatory(world)
    try:
        submission = candidate(problem_statement(world), observatory.reanalyze,
                               REANALYSIS_BUDGET)
        sigma1, sigma3, payload, confidence, abstain = _validate(submission, world)
        if observatory.violated:
            raise ValueError("observatory contract violated")
        supported = world["kind"] == "supported"
        if supported and not abstain:
            mechanism, axis, r, plane = _mechanism_score(world, sigma1, sigma3, payload)
        elif supported:
            mechanism = axis = r = plane = 0.0
        else:
            correct = bool(abstain)
            mechanism = axis = r = plane = 1.0 if correct else 0.0
        target_confidence = 1.0 if (supported != abstain or (not supported and abstain)) else 0.0
        row.update({"valid": True, "abstained": abstain,
                    "mechanism_score": mechanism, "axis_score": axis,
                    "r_score": r, "plane_score": plane,
                    "false_discovery": bool(not supported and not abstain),
                    "correct_refusal": bool(not supported and abstain),
                    "confidence_score": 1.0 - (confidence - target_confidence) ** 2,
                    "budget_used": observatory.used})
    except Exception:
        pass
    return row


def _summary(rows, specs):
    supported = [r for r, s in zip(rows, specs) if s[1] == "supported"]
    unsupported = [r for r, s in zip(rows, specs) if s[1] != "supported"]
    raw = float(np.mean([r["mechanism_score"] for r in rows]))
    abstain_base = len(unsupported) / len(rows)
    return {
        "normalized": float(np.clip((raw - abstain_base) / (1.0 - abstain_base), 0.0, 1.0)),
        "raw": raw,
        "valid_count": sum(r["valid"] for r in rows),
        "axis_score": float(np.mean([r["axis_score"] for r in supported])) if supported else 0.0,
        "r_score": float(np.mean([r["r_score"] for r in supported])) if supported else 0.0,
        "plane_score": float(np.mean([r["plane_score"] for r in supported])) if supported else 0.0,
        "false_count": sum(r["false_discovery"] for r in unsupported),
        "refusal_count": sum(r["correct_refusal"] for r in unsupported),
        "attempt_count": sum(not r["abstained"] for r in supported),
        "supported_count": len(supported), "unsupported_count": len(unsupported),
    }


def evaluate(infer_stress_orientation):
    development = [_evaluate_world(infer_stress_orientation, spec, "development", i)
                   for i, spec in enumerate(_BASE_DEVELOPMENT_SPECS)]
    heldout = [_evaluate_world(infer_stress_orientation, spec, "heldout", i)
               for i, spec in enumerate(HELDOUT_SPECS)]
    dev, hold = _summary(development, _BASE_DEVELOPMENT_SPECS), _summary(heldout, HELDOUT_SPECS)
    dev_valid = dev["valid_count"] == len(development)
    hold_valid = hold["valid_count"] == len(heldout)
    return {
        "combined_score": dev["normalized"] if dev_valid else 0.0,
        "valid": 1.0 if dev_valid else 0.0,
        "feasibility_rate": dev["valid_count"] / len(development),
        "mechanism_score": dev["raw"],
        "development_axis_score": dev["axis_score"],
        "development_r_score": dev["r_score"],
        "development_plane_score": dev["plane_score"],
        "development_false_discovery_rate": dev["false_count"] / dev["unsupported_count"],
        "development_correct_refusal_rate": dev["refusal_count"] / dev["unsupported_count"],
        "development_discovery_coverage": dev["attempt_count"] / dev["supported_count"],
        "supported_world_count": dev["supported_count"],
        "unsupported_world_count": dev["unsupported_count"],
        "false_discovery_count": dev["false_count"],
        "correct_refusal_count": dev["refusal_count"],
        "robustness_score": hold["normalized"] if hold_valid else 0.0,
        "heldout_feasibility_rate": hold["valid_count"] / len(heldout),
        "heldout_false_discovery_rate": hold["false_count"] / hold["unsupported_count"],
        "heldout_correct_refusal_rate": hold["refusal_count"] / hold["unsupported_count"],
        "per_world": development + heldout,
    }

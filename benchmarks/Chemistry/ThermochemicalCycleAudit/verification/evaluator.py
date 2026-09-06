"""Deterministic thermochemical cycle audit oracle.

Seven isomers are connected by thirteen measured interconversion enthalpies. The
measurements close under Hess's law only if every instrument is honest. The candidate
reconciles the network, decides what the evidence supports -- consistency, a localized
single faulty determination, a drifting instrument, or an attribution the network cannot
resolve -- and may spend a replicate/cross-check budget to sharpen the diagnosis.
"""

from __future__ import annotations

import hashlib
import math

import numpy as np

DIFFICULTY = 1

_DIFFICULTY_LADDER = {
    1: {"sigma_multiplier": 1.00, "drift_strength": 1.00},
    2: {"sigma_multiplier": 1.25, "drift_strength": 1.35},
    3: {"sigma_multiplier": 1.55, "drift_strength": 1.75},
}

SPECIES = ("iso1", "iso2", "iso3", "iso4", "iso5", "iso6", "iso7")
INSTRUMENTS = {"bomb": 0.35, "dsc": 1.10, "eqm": 2.40}
# Fixed interconversion network (row = reaction, stoichiometry over SPECIES):
# eleven reactions spanning rank 7 plus a pendant duplicate/reverse pair (rows 11, 12)
# whose attribution is structurally underdetermined when one of them is corrupted.
REACTIONS = (
    ((-1, 1, 0, 0, 0, 0, 0), "iso1 -> iso2"),
    ((0, -1, 1, 0, 0, 0, 0), "iso2 -> iso3"),
    ((1, 0, -1, 0, 0, 0, 0), "iso3 -> iso1"),
    ((0, -1, 0, 1, 0, 0, 0), "iso2 -> iso4"),
    ((0, 0, 0, -1, 1, 0, 0), "iso4 -> iso5"),
    ((0, 1, 0, 0, -1, 0, 0), "iso5 -> iso2"),
    ((0, 0, 0, -1, 0, 1, 0), "iso4 -> iso6"),
    ((0, 0, 0, 0, 0, -1, 1), "iso6 -> iso7"),
    ((0, 0, 0, 1, 0, 0, -1), "iso7 -> iso4"),
    ((-2, 0, 1, 0, 1, 0, 0), "2 iso1 -> iso3 + iso5"),
    ((0, 0, 0, -2, 1, 0, 1), "2 iso4 -> iso5 + iso7"),
    ((0, 0, 0, 0, 0, -1, 1), "iso6 -> iso7 (duplicate determination)"),
    ((0, 0, 0, 0, 0, 1, -1), "iso7 -> iso6"),
)
MEASUREMENT_IDS = tuple("R%02d" % (index + 1) for index in range(len(REACTIONS)))
PENDANT_IDS = ("R12", "R13")
REFERENCE_STATE_OFFSETS = (44.01, 40.65, 28.05)
REPLICATE_COST = 1
CROSS_CHECK_COST = 3
BUDGET_UNITS = 6

VERDICTS = ("consistent", "single_fault", "instrument_drift", "underdetermined")

_BASE_DEVELOPMENT_SPECS = (
    (71011, "clean"), (71017, "clean"),
    (71023, "drift"), (71029, "drift"),
    (71031, "transcription"), (71037, "reference_state"),
    (71041, "underdetermined"), (71047, "underdetermined"),
)
HELDOUT_SPECS = (
    (81007, "clean"), (81013, "drift"), (81019, "transcription"),
    (81023, "reference_state"), (81029, "underdetermined"),
)


def _difficulty_profile(level=None):
    level = DIFFICULTY if level is None else int(level)
    if level not in _DIFFICULTY_LADDER:
        raise ValueError("difficulty %d has no measured profile" % level)
    return _DIFFICULTY_LADDER[level]


def _reaction_values(enthalpies):
    stoichiometry = np.asarray([row[0] for row in REACTIONS], dtype=float)
    return stoichiometry @ np.asarray(enthalpies, dtype=float)


def _world(spec):
    seed, kind = spec
    profile = _difficulty_profile()
    rng = np.random.default_rng(int(seed))
    enthalpies = rng.uniform(-250.0, 150.0, size=len(SPECIES))
    balanced = ["bomb"] * 4 + ["dsc"] * 4 + ["eqm"] * 3
    rng.shuffle(balanced)
    instruments = list(balanced)
    # The pendant pair deliberately shares one instrument class; the noisier
    # equilibrium class would blur the very ambiguity this world is about.
    pendant_instrument = instruments[7] if instruments[7] != "eqm" else "dsc"
    instruments.append(pendant_instrument)
    instruments.append(pendant_instrument)
    sigmas = np.asarray([INSTRUMENTS[name] * profile["sigma_multiplier"]
                         for name in instruments])
    truth = _reaction_values(enthalpies)
    values = truth + rng.normal(0.0, 1.0, size=len(truth)) * sigmas
    corruption = {}
    if kind == "drift":
        candidates = [name for name in INSTRUMENTS if name != pendant_instrument]
        instrument = candidates[int(rng.integers(0, len(candidates)))]
        offset = float(rng.uniform(4.0, 8.0)) * profile["drift_strength"]
        if rng.random() < 0.5:
            offset = -offset
        for index, name in enumerate(instruments):
            if name == instrument:
                values[index] += offset
        corruption = {"instrument": instrument, "offset": offset,
                      "indices": [i for i, n in enumerate(instruments) if n == instrument]}
    elif kind in ("transcription", "reference_state"):
        index = int(rng.integers(0, 11))
        if kind == "transcription":
            slip = float(rng.choice((-1.0, 1.0))) * float(rng.choice((80.0, 110.0)))
        else:
            slip = float(REFERENCE_STATE_OFFSETS[int(rng.integers(0, 3))])
            if rng.random() < 0.5:
                slip = -slip
        values[index] += slip
        corruption = {"indices": [index], "offset": slip}
    elif kind == "underdetermined":
        index = 11  # the duplicate pendant determination
        offset = float(rng.uniform(4.5, 9.0)) * profile["drift_strength"]
        if rng.random() < 0.5:
            offset = -offset
        values[index] += offset
        corruption = {"indices": [index], "offset": offset, "pendant": True}
    instrument_offsets = {name: 0.0 for name in INSTRUMENTS}
    if kind == "drift":
        instrument_offsets[corruption["instrument"]] = corruption["offset"]
    return {
        "seed": int(seed), "kind": kind, "enthalpies": enthalpies,
        "truth": truth, "values": values, "sigmas": sigmas,
        "instruments": instruments, "corruption": corruption,
        "instrument_offsets": instrument_offsets,
    }


def problem_statement(world):
    return {
        "species": list(SPECIES),
        "measurements": [
            {"id": MEASUREMENT_IDS[index],
             "reaction": REACTIONS[index][1],
             "stoichiometry": {SPECIES[j]: int(REACTIONS[index][0][j])
                               for j in range(len(SPECIES))
                               if REACTIONS[index][0][j] != 0},
             "value_kj_per_mol": float(world["values"][index]),
             "sigma_kj_per_mol": float(world["sigmas"][index]),
             "instrument": world["instruments"][index]}
            for index in range(len(REACTIONS))
        ],
        "instrument_sigma_kj_per_mol": {name: sig * _difficulty_profile()["sigma_multiplier"]
                                        for name, sig in INSTRUMENTS.items()},
        "reference_state_offsets_kj_per_mol": list(REFERENCE_STATE_OFFSETS),
        "replicate_cost": REPLICATE_COST,
        "cross_check_cost": CROSS_CHECK_COST,
        "budget_units": BUDGET_UNITS,
        "network_note": (
            "enthalpies close under Hess's law over the seven species; the pendant "
            "duplicate/reverse pair R12/R13 shares one instrument class"
        ),
    }


def _draw_rng(world, payload, count):
    digest = int.from_bytes(hashlib.sha256(payload).digest()[:4], "little")
    return np.random.default_rng(world["seed"] + digest + 61 * count)


class _Laboratory:
    """Charged interface: replicates and instrument cross-checks."""

    def __init__(self, world):
        self.world = world
        self.used = 0
        self.calls = 0
        self.violated = False
        self.replicate_index = {index: 0 for index in range(len(REACTIONS))}
        self.cross_checked = set()

    def _locate(self, measurement_id):
        if measurement_id not in MEASUREMENT_IDS:
            self.violated = True
            raise ValueError("unknown measurement id")
        return MEASUREMENT_IDS.index(measurement_id)

    def replicate(self, measurement_id):
        try:
            index = self._locate(measurement_id)
            if self.used + REPLICATE_COST > BUDGET_UNITS:
                self.violated = True
                raise RuntimeError("measurement budget exceeded")
            self.used += REPLICATE_COST
            self.calls += 1
            self.replicate_index[index] += 1
            rng = _draw_rng(self.world, ("replicate %s %d"
                                         % (measurement_id, self.replicate_index[index])).encode(),
                            self.calls)
            sigma = self.world["sigmas"][index] / math.sqrt(2.0)
            # A replicate re-runs the same instrument: random error shrinks, a
            # calibration offset does not.
            value = (self.world["truth"][index]
                     + self.world["instrument_offsets"][self.world["instruments"][index]]
                     + rng.normal(0.0, 1.0) * sigma)
            return {"id": measurement_id, "value_kj_per_mol": float(value),
                    "sigma_kj_per_mol": float(sigma),
                    "instrument": self.world["instruments"][index],
                    "budget_cost": REPLICATE_COST}
        except Exception:
            self.violated = True
            raise

    def cross_check(self, measurement_id):
        try:
            index = self._locate(measurement_id)
            if index in self.cross_checked or self.used + CROSS_CHECK_COST > BUDGET_UNITS:
                self.violated = True
                raise RuntimeError("cross-check unavailable or budget exceeded")
            self.used += CROSS_CHECK_COST
            self.calls += 1
            self.cross_checked.add(index)
            rng = _draw_rng(self.world, ("cross %s" % measurement_id).encode(), self.calls)
            sigma = 0.55 * _difficulty_profile()["sigma_multiplier"]
            value = self.world["truth"][index] + rng.normal(0.0, 1.0) * sigma
            return {"id": measurement_id, "value_kj_per_mol": float(value),
                    "sigma_kj_per_mol": float(sigma), "instrument": "reference_lab",
                    "budget_cost": CROSS_CHECK_COST}
        except Exception:
            self.violated = True
            raise


_PASSIVE_SUBMISSION = {
    "verdict": "consistent", "flagged_measurements": [], "drift_instrument": "",
    "corrected_enthalpies": {}, "confidence": 0.5,
}


def _validate(submission, world):
    if not isinstance(submission, dict):
        raise ValueError("submission must be a mapping")
    verdict = submission.get("verdict")
    if verdict not in VERDICTS:
        raise ValueError("verdict must be one of %s" % (VERDICTS,))
    flagged = submission.get("flagged_measurements")
    if not isinstance(flagged, (list, tuple)) or any(
            item not in MEASUREMENT_IDS for item in flagged):
        raise ValueError("flagged_measurements must list known measurement ids")
    flagged = list(flagged)
    if len(set(flagged)) != len(flagged):
        raise ValueError("flagged_measurements must be unique")
    instrument = submission.get("drift_instrument", "")
    if instrument and instrument not in INSTRUMENTS:
        raise ValueError("drift_instrument must be a known instrument name or empty")
    if verdict == "instrument_drift" and not instrument:
        raise ValueError("instrument_drift verdict must name an instrument")
    corrected = submission.get("corrected_enthalpies")
    if not isinstance(corrected, dict) or set(corrected) != set(MEASUREMENT_IDS):
        raise ValueError("corrected_enthalpies must map every measurement id to a value")
    values = np.asarray([float(corrected[name]) for name in MEASUREMENT_IDS])
    if np.any(~np.isfinite(values)):
        raise ValueError("corrected enthalpies must be finite")
    confidence = float(submission.get("confidence"))
    if not math.isfinite(confidence) or not 0.0 <= confidence <= 1.0:
        raise ValueError("confidence must be in [0,1]")
    return verdict, flagged, instrument, values, confidence


def _correction_score(values, world):
    errors = np.abs(values - world["truth"])
    scale = np.maximum(world["sigmas"], 0.5)
    return float(np.mean(np.exp(-errors / scale)))


def _diagnosis_scores(flagged, verdict, instrument, world, resolved):
    kind = world["kind"]
    corrupted = world["corruption"].get("indices", [])
    corrupted_ids = {MEASUREMENT_IDS[i] for i in corrupted}
    flagged_set = set(flagged)
    precision = (len(flagged_set & corrupted_ids) / len(flagged_set)) if flagged_set else 1.0
    recall = (len(flagged_set & corrupted_ids) / len(corrupted_ids)) if corrupted_ids else 1.0
    diagnosis = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    false_discovery = False
    if kind == "clean":
        verdict_correct = verdict == "consistent"
        diagnosis = 1.0 if not flagged_set else diagnosis
        false_discovery = bool(flagged_set) or verdict != "consistent"
    elif kind == "drift":
        verdict_correct = (verdict == "instrument_drift"
                           and instrument == world["corruption"]["instrument"])
    elif kind == "underdetermined":
        pendant = set(PENDANT_IDS)
        if resolved:
            # A pendant cross-check re-measures the disputed quantity directly, so a
            # localization claim is now founded and refusing it is no longer honest.
            verdict_correct = verdict == "single_fault"
        else:
            verdict_correct = verdict == "underdetermined"
            # Guessing one member of the pair without resolving information averages
            # half credit; the blameless answers flag nothing or the whole pair.
            diagnosis = (1.0 if flagged_set in (set(), pendant)
                         else 0.5 * diagnosis if flagged_set <= pendant else 0.0)
            false_discovery = bool(verdict == "single_fault" and flagged_set < pendant)
    else:
        verdict_correct = verdict == "single_fault"
    return float(verdict_correct), float(diagnosis), bool(false_discovery)


def _score(submission, world, resolved=False):
    verdict, flagged, instrument, values, confidence = _validate(submission, world)
    correction = _correction_score(values, world)
    verdict_score, diagnosis, false_discovery = _diagnosis_scores(
        flagged, verdict, instrument, world, resolved)
    passive_values = world["values"]
    passive = _correction_score(passive_values, world)
    correction_gain = ((correction - passive) / (1.0 - passive)
                       if passive < 1.0 else 0.0)
    correction_gain = float(np.clip(correction_gain, 0.0, 1.0))
    mechanism = float(0.45 * correction_gain + 0.35 * verdict_score + 0.20 * diagnosis)
    engaged = verdict != "consistent" or bool(flagged) or bool(instrument)
    if kind_refuses(world) and not engaged:
        mechanism = 0.0
    target_confidence = 1.0 if (engaged == world_needs_engagement(world)) else 0.3
    confidence_score = 1.0 - (confidence - target_confidence) ** 2
    correct_refusal = bool(world["kind"] == "underdetermined"
                           and not resolved and verdict == "underdetermined")
    return {
        "mechanism_score": mechanism,
        "correction_gain": correction_gain,
        "verdict_score": verdict_score,
        "diagnosis_score": diagnosis,
        "passive_correction": passive,
        "confidence_score": float(confidence_score),
        "false_discovery": false_discovery,
        "correct_refusal": correct_refusal,
        "engaged": bool(engaged),
    }


def kind_refuses(world):
    return world["kind"] == "underdetermined"


def world_needs_engagement(world):
    return world["kind"] != "clean"


def _passive_submission(world):
    row = dict(_PASSIVE_SUBMISSION)
    row["corrected_enthalpies"] = {name: float(world["values"][index])
                                   for index, name in enumerate(MEASUREMENT_IDS)}
    return row


def _empty(split, index):
    return {"split": split, "world_index": index, "valid": False, "engaged": False,
            "mechanism_score": 0.0, "correction_gain": 0.0, "verdict_score": 0.0,
            "diagnosis_score": 0.0, "confidence_score": 0.0,
            "false_discovery": False, "correct_refusal": False, "budget_used": 0}


def _evaluate_world(candidate, spec, split, index):
    row = _empty(split, index)
    world = _world(spec)
    lab = _Laboratory(world)
    passive = _score(_passive_submission(world), world)
    row["passive_mechanism"] = passive["mechanism_score"]
    try:
        submission = candidate(problem_statement(world), lab.replicate, lab.cross_check,
                               BUDGET_UNITS)
        if lab.violated:
            raise ValueError("laboratory contract violated")
        resolved = any(index in lab.cross_checked for index in (11, 12))
        scores = _score(submission, world, resolved=resolved)
        row.update(scores)
        row["valid"] = True
        row["budget_used"] = lab.used
    except Exception:
        pass
    return row


def _summary(rows, specs):
    raw = float(np.mean([r["mechanism_score"] for r in rows]))
    passive = float(np.mean([r.get("passive_mechanism", 0.0) for r in rows]))
    refusing = [r for r, s in zip(rows, specs) if s[1] == "underdetermined"]
    clean = [r for r, s in zip(rows, specs) if s[1] == "clean"]
    scored_for_fdr = clean + refusing
    return {
        "raw": raw, "passive": passive,
        "normalized": float(np.clip((raw - passive) / max(1.0 - passive, 1e-9), 0.0, 1.0)),
        "valid_count": sum(r["valid"] for r in rows),
        "correction_gain": float(np.mean([r["correction_gain"] for r in rows])),
        "verdict_score": float(np.mean([r["verdict_score"] for r in rows])),
        "diagnosis_score": float(np.mean([r["diagnosis_score"] for r in rows])),
        "false_count": sum(r["false_discovery"] for r in scored_for_fdr),
        "fdr_denominator": len(scored_for_fdr),
        "refusal_count": sum(r["correct_refusal"] for r in refusing),
        "refusing_count": len(refusing),
        "attempt_count": sum(r["engaged"] for r in rows if r["valid"]),
    }


def evaluate(audit_thermochemical_cycle):
    development = [_evaluate_world(audit_thermochemical_cycle, spec, "development", i)
                   for i, spec in enumerate(_BASE_DEVELOPMENT_SPECS)]
    heldout = [_evaluate_world(audit_thermochemical_cycle, spec, "heldout", i)
               for i, spec in enumerate(HELDOUT_SPECS)]
    dev, hold = _summary(development, _BASE_DEVELOPMENT_SPECS), _summary(heldout, HELDOUT_SPECS)
    dev_valid = dev["valid_count"] == len(development)
    hold_valid = hold["valid_count"] == len(heldout)
    return {
        "combined_score": dev["normalized"] if dev_valid else 0.0,
        "valid": 1.0 if dev_valid else 0.0,
        "feasibility_rate": dev["valid_count"] / len(development),
        "mechanism_score": dev["raw"],
        "passive_mechanism_score": dev["passive"],
        "development_correction_gain": dev["correction_gain"],
        "development_verdict_score": dev["verdict_score"],
        "development_diagnosis_score": dev["diagnosis_score"],
        "development_false_discovery_rate": dev["false_count"] / dev["fdr_denominator"],
        "development_correct_refusal_rate": dev["refusal_count"] / dev["refusing_count"],
        "development_discovery_coverage": dev["attempt_count"] / len(development),
        "clean_world_count": dev["fdr_denominator"],
        "refusing_world_count": dev["refusing_count"],
        "false_discovery_count": dev["false_count"],
        "correct_refusal_count": dev["refusal_count"],
        "robustness_score": hold["normalized"] if hold_valid else 0.0,
        "heldout_feasibility_rate": hold["valid_count"] / len(heldout),
        "heldout_verdict_score": hold["verdict_score"],
        "heldout_correction_gain": hold["correction_gain"],
        "heldout_false_discovery_rate": hold["false_count"] / hold["fdr_denominator"],
        "heldout_correct_refusal_rate": hold["refusal_count"] / hold["refusing_count"],
        "per_world": development + heldout,
    }

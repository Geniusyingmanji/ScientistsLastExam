"""Frozen oracle for SuperconductorTcRecord v4 (hidden from the agent).

Tc is computed by literally evaluating the public Allen-Dynes formula

    Tc = (omega_log / 1.2) * exp(-1.04*(1+lambda) / (lambda - mu_star*(1+0.62*lambda)))

from a per-family lambda(P) and omega_log(P) -- not read off a fitted curve whose only
justification is "matches these citations." Every anchor lambda is itself *solved* (via
scipy.optimize.brentq, not eyeballed) so this same public formula reproduces the cited Tc exactly
at the cited pressure; see references/known_best.md for the full derivation, which anyone can
re-run. Feasibility is a computable criterion, not a "has this been synthesized" flag: a
(family, pressure) point is dynamically implausible -- and scores 0 -- if it falls outside a
family's disclosed pressure window, or if the lambda the Allen-Dynes formula would need to reach
that Tc exceeds 3.5, the highest electron-phonon coupling constant established anywhere in this
literature (Errea et al. 2020's anharmonic-corrected value for LaH10). This is exactly what
excludes the one family that was never realized (YH10fcc): its historical proxy of 305-326 K
implies lambda=3.95 at a comparable omega_log, above every confirmed system's implied coupling --
a red flag anyone can recompute from the same public formula, not an appeal to laboratory history.

combined_score is the true Tc at the submitted point divided by the best confirmed Tc in this
literature (250 K, Drozdov et al. 2019) -- the actual headline number these papers report, not an
internally computed search-witness reward. This is a plain ratio (no baseline subtraction), so it
is trivially well-defined and uncapped: submitting a pressure where the disclosed model implies a
higher Tc than has been published scores above 1.0.

Repeated evaluation instances ("trials") vary a real, disclosed engineering constraint -- the
maximum pressure the agent's apparatus can reach -- rather than randomly perturbing the physics.
"""
from __future__ import annotations

import math

import numpy as np

INVALID = -1e18

PROBE_BUDGET = 16
PROBE_RELATIVE_NOISE = 0.05
MU_STAR = 0.10
LAMBDA_MAX_PLAUSIBLE = 3.5  # Errea et al. 2020's own anharmonic lambda=3.5 for LaH10

# -----------------------------------------------------------------------------------------------
# Real, citable (family, pressure, Tc) anchors. omega_log0 is a declared order-of-magnitude
# modeling choice (hydrides have a far higher phonon energy scale than a boride because hydrogen
# is light); lambda at each anchor is solved, not chosen, so the forward Allen-Dynes formula
# reproduces the cited Tc exactly. See references/known_best.md for the full derivation.
# -----------------------------------------------------------------------------------------------
FAMILY_SPEC = {
    "MgB2boride": dict(
        omega_log0_k=700.0, p_ceiling_gpa=0.0, window_gpa=(0.0, 0.0),
        anchors=((0.0, 39.0),),
        citation="Nagamatsu et al. 2001, Nature 410, 63, DOI 10.1038/35065039",
    ),
    "H3Shydride": dict(
        omega_log0_k=1300.0, p_ceiling_gpa=300.0, window_gpa=(110.0, 230.0),
        anchors=((155.0, 203.0),),
        citation="Drozdov et al. 2015, Nature 525, 73, DOI 10.1038/nature14964",
    ),
    "LaH10hydride": dict(
        omega_log0_k=1450.0, p_ceiling_gpa=300.0, window_gpa=(125.0, 240.0),
        anchors=((136.0, 246.0), (170.0, 250.0)),
        citation=(
            "Errea et al. 2020, Nature 578, 66, DOI 10.1038/s41586-020-1955-z (246 K at 136 GPa); "
            "Drozdov et al. 2019, Nature 569, 528, DOI 10.1038/s41586-019-1201-8 (250 K at 170 GPa)"
        ),
    ),
    "YH6hydride": dict(
        omega_log0_k=1300.0, p_ceiling_gpa=300.0, window_gpa=(140.0, 280.0),
        anchors=((237.0, 227.0),),
        citation="Kong et al. 2021, Nat. Commun. 12, 5075, DOI 10.1038/s41467-021-25372-2",
    ),
    "YH9hydride": dict(
        omega_log0_k=1300.0, p_ceiling_gpa=300.0, window_gpa=(150.0, 260.0),
        anchors=((201.0, 243.0),),
        citation="Kong et al. 2021, Nat. Commun. 12, 5075, DOI 10.1038/s41467-021-25372-2",
    ),
    "YH10fcc": dict(
        omega_log0_k=1450.0, p_ceiling_gpa=300.0, window_gpa=(240.0, 260.0),
        anchors=((250.0, 326.0),),  # the proxy's own upper bound -- never realized, see below
        citation="Liu et al. 2017, PNAS 114, 6990, DOI 10.1073/pnas.1704505114 (theoretical only)",
    ),
}
FAMILY_NAMES = tuple(FAMILY_SPEC)
KNOWN_RECORD_TC_K = 250.0  # Drozdov et al. 2019's own headline confirmed number

HISTORICAL_PROXY = {
    "MgB2boride": {"tc_range_k": (39.0, 39.0), "pressure_gpa": 0.0,
                   "note": "found experimentally first; no pre-experimental theoretical overshoot",
                   "citation": FAMILY_SPEC["MgB2boride"]["citation"]},
    "H3Shydride": {"tc_range_k": (191.0, 204.0), "pressure_gpa": 200.0,
                   "note": "harmonic prediction, made before the 2015 discovery",
                   "citation": "Duan et al. 2014, Sci. Rep. 4, 6968, DOI 10.1038/srep06968"},
    "LaH10hydride": {"tc_range_k": (257.0, 286.0), "pressure_gpa": 210.0,
                      "note": "harmonic prediction, mu_star=0.10-0.13, lambda=2.2; made before the 2019 discovery",
                      "citation": "Liu et al. 2017, PNAS 114, 6990, DOI 10.1073/pnas.1704505114"},
    "YH6hydride": {"tc_range_k": None, "pressure_gpa": None,
                    "note": "no single number asserted; measured values reported \"notably lower by ~30 K than predicted\"",
                    "citation": FAMILY_SPEC["YH6hydride"]["citation"]},
    "YH9hydride": {"tc_range_k": None, "pressure_gpa": None,
                    "note": "same qualitative ~30 K gap reported in the same paper",
                    "citation": FAMILY_SPEC["YH9hydride"]["citation"]},
    "YH10fcc": {"tc_range_k": (305.0, 326.0), "pressure_gpa": 250.0,
                "note": "sodalite-like fcc structure, theoretical prediction only",
                "citation": FAMILY_SPEC["YH10fcc"]["citation"]},
}

DEVELOPMENT_CEILINGS_GPA = (260.0,)
HELDOUT_CEILINGS_GPA = (220.0,)


def allen_dynes_tc(lam: float, omega_log_k: float, mu_star: float = MU_STAR) -> float:
    denom = lam - mu_star * (1.0 + 0.62 * lam)
    if denom <= 1e-9 or omega_log_k <= 0.0:
        return 0.0
    return (omega_log_k / 1.2) * math.exp(-1.04 * (1.0 + lam) / denom)


def _lambda_at_anchors(family: str):
    """Solve (once, at import time) the lambda that makes allen_dynes_tc reproduce each cited
    (pressure, Tc) anchor exactly, given that family's omega_log(pressure)."""
    from scipy.optimize import brentq

    spec = FAMILY_SPEC[family]
    lam_min = MU_STAR / (1.0 - 0.62 * MU_STAR) + 1e-6
    solved = []
    for pressure_gpa, tc_k in spec["anchors"]:
        omega_log_k = _omega_log_k(family, pressure_gpa)

        def f(lam, _tc=tc_k, _wl=omega_log_k):
            return allen_dynes_tc(lam, _wl) - _tc

        if f(12.0) < 0:
            raise RuntimeError("anchor Tc unreachable for %s at %s GPa" % (family, pressure_gpa))
        solved.append((pressure_gpa, float(brentq(f, lam_min + 1e-6, 12.0, xtol=1e-10))))
    return solved


def _omega_log_k(family: str, pressure_gpa: float) -> float:
    spec = FAMILY_SPEC[family]
    if spec["p_ceiling_gpa"] <= 0.0:
        return spec["omega_log0_k"]
    return spec["omega_log0_k"] * (1.0 + 0.15 * (pressure_gpa / spec["p_ceiling_gpa"]))


_LAMBDA_ANCHORS = {family: _lambda_at_anchors(family) for family in FAMILY_NAMES}


def lambda_true(family: str, pressure_gpa: float) -> float:
    """Piecewise-linear through the solved anchor lambda(s); constant when there is only one."""
    points = _LAMBDA_ANCHORS[family]
    if len(points) == 1:
        return points[0][1]
    (p0, l0), (p1, l1) = points[0], points[-1]
    slope = (l1 - l0) / (p1 - p0)
    return l0 + slope * (pressure_gpa - p0)


def dynamically_stable(family: str, pressure_gpa: float) -> bool:
    lo, hi = FAMILY_SPEC[family]["window_gpa"]
    if not (lo <= pressure_gpa <= hi):
        return False
    return lambda_true(family, pressure_gpa) <= LAMBDA_MAX_PLAUSIBLE


def tc_model(family: str, pressure_gpa: float) -> float:
    """The true, noiseless critical temperature: the public Allen-Dynes formula evaluated at this
    family's true lambda(pressure) and omega_log(pressure), gated by dynamical plausibility."""
    if not dynamically_stable(family, pressure_gpa):
        return 0.0
    lam = lambda_true(family, pressure_gpa)
    omega_log_k = _omega_log_k(family, pressure_gpa)
    return allen_dynes_tc(lam, omega_log_k)


def _feasible_families(ceiling_gpa: float):
    return [f for f, s in FAMILY_SPEC.items() if s["window_gpa"][0] <= ceiling_gpa]


def public_problem(ceiling_gpa: float):
    proxy = {family: dict(spec) for family, spec in HISTORICAL_PROXY.items()}
    return {
        "families": _feasible_families(ceiling_gpa),
        "historical_proxy": proxy,
        "apparatus_pressure_ceiling_gpa": ceiling_gpa,
        "probe_budget_calls": PROBE_BUDGET,
        "allen_dynes_formula": (
            "Tc_kelvin = (omega_log_k / 1.2) * exp(-1.04*(1+lambda) / "
            "(lambda - mu_star*(1+0.62*lambda))); mu_star = 0.10"
        ),
        "lambda_max_plausible": LAMBDA_MAX_PLAUSIBLE,
        "known_record_tc_k": KNOWN_RECORD_TC_K,
        "measurement_model": (
            "probe(family, pressure_gpa) returns one noisy draw of (lambda_hat, omega_log_k_hat) "
            "at any pressure you choose, plus an exact (no noise) dynamically_stable flag. "
            "dynamically_stable is false outside a family's real pressure window, and false "
            "wherever the implied lambda exceeds lambda_max_plausible -- this is a computable "
            "criterion you can check yourself from the same public formula, not a record of "
            "laboratory history. A repeat of the same (family, pressure_gpa) is a new draw and "
            "costs another unit of probe_budget_calls"
        ),
        "scope_note": (
            "combined_score is the true Tc at your submission (0 if not dynamically stable) "
            "divided by known_record_tc_k -- the actual best confirmed Tc in this literature, not "
            "a search-algorithm reward. pressure_gpa must be finite, >= 0, and <= "
            "apparatus_pressure_ceiling_gpa"
        ),
    }


def _baseline_choice(ceiling_gpa: float):
    """The same deterministic, proxy-only rule shipped in solution.py: trust the public
    historical-proxy prediction's own family and pressure at face value, never probing to check
    dynamical plausibility."""
    families = _feasible_families(ceiling_gpa)

    def proxy_upper(family):
        spec = HISTORICAL_PROXY[family]
        return spec["tc_range_k"][1] if spec["tc_range_k"] is not None else -1.0

    best_family = max(families, key=proxy_upper)
    pressure_gpa = min(HISTORICAL_PROXY[best_family]["pressure_gpa"], ceiling_gpa)
    return best_family, pressure_gpa


class _Lab:
    def __init__(self, ceiling_gpa: float, salt: int):
        self.ceiling_gpa = ceiling_gpa
        self.salt = salt
        self.used = 0
        self.calls = 0
        self.violated = False

    def probe(self, family, pressure_gpa):
        if family not in FAMILY_SPEC:
            raise ValueError("family is not one of problem['families']")
        pressure_gpa = float(pressure_gpa)
        if not math.isfinite(pressure_gpa) or not (0.0 <= pressure_gpa <= self.ceiling_gpa):
            raise ValueError("pressure_gpa must be within [0, apparatus_pressure_ceiling_gpa]")
        if self.used >= PROBE_BUDGET:
            self.violated = True
            raise RuntimeError("probe_budget_calls exhausted")
        self.used += 1
        self.calls += 1
        lam = lambda_true(family, pressure_gpa)
        omega_log_k = _omega_log_k(family, pressure_gpa)
        stable = dynamically_stable(family, pressure_gpa)
        rng = np.random.default_rng((self.salt, 19, self.calls))
        lam_hat = max(1e-3, lam * (1.0 + PROBE_RELATIVE_NOISE * float(rng.normal())))
        wl_hat = max(1.0, omega_log_k * (1.0 + PROBE_RELATIVE_NOISE * float(rng.normal())))
        return {
            "lambda_hat": float(lam_hat),
            "omega_log_k_hat": float(wl_hat),
            "dynamically_stable": bool(stable),
        }


def _validate_submission(submission, ceiling_gpa: float):
    if not isinstance(submission, dict):
        raise ValueError("submission must be a mapping")
    family = submission.get("family")
    if family not in FAMILY_SPEC:
        raise ValueError("family is required and must be one of problem['families']")
    pressure_gpa = float(submission.get("pressure_gpa"))
    if not math.isfinite(pressure_gpa) or not (0.0 <= pressure_gpa <= ceiling_gpa):
        raise ValueError("pressure_gpa must be finite and within [0, apparatus_pressure_ceiling_gpa]")
    predicted_tc_k = float(submission.get("predicted_tc_k"))
    if not math.isfinite(predicted_tc_k) or predicted_tc_k < 0.0:
        raise ValueError("predicted_tc_k must be a finite non-negative number")
    confidence = float(submission.get("confidence", 0.0))
    if not math.isfinite(confidence) or not 0.0 <= confidence <= 1.0:
        raise ValueError("confidence must be finite and in [0, 1]")
    return family, pressure_gpa, predicted_tc_k, confidence


def _evaluate_trial(design_superconductor, ceiling_gpa: float, split: str, index: int, salt: int):
    baseline_family, baseline_pressure = _baseline_choice(ceiling_gpa)
    baseline_tc = tc_model(baseline_family, baseline_pressure)
    lab = _Lab(ceiling_gpa, salt)
    problem = public_problem(ceiling_gpa)
    row = {
        "split": split,
        "world_index": int(index),
        "ceiling_gpa": ceiling_gpa,
        "baseline_family": baseline_family,
        "baseline_pressure_gpa": round(baseline_pressure, 2),
        "baseline_true_tc_k": round(baseline_tc, 3),
        "known_record_tc_k": KNOWN_RECORD_TC_K,
    }
    try:
        submission = design_superconductor(problem, lab.probe)
        family, pressure_gpa, predicted_tc_k, confidence = _validate_submission(submission, ceiling_gpa)
        if lab.violated:
            raise RuntimeError("probe budget exceeded")
        true_tc_k = tc_model(family, pressure_gpa)
        score = float(true_tc_k / KNOWN_RECORD_TC_K)
        calibration_error_k = abs(predicted_tc_k - true_tc_k)
        row.update({
            "valid": True,
            "family": family,
            "pressure_gpa": round(pressure_gpa, 3),
            "dynamically_stable": bool(true_tc_k > 0.0),
            "lambda_true": round(lambda_true(family, pressure_gpa), 4),
            "true_tc_k": round(true_tc_k, 3),
            "predicted_tc_k": round(predicted_tc_k, 3),
            "calibration_error_k": round(calibration_error_k, 3),
            "confidence": round(confidence, 6),
            "probe_calls": lab.used,
            "mechanism_score": score,
        })
        return row
    except Exception as exc:  # noqa: BLE001
        row.update({
            "valid": False,
            "reason": "%s: %s" % (type(exc).__name__, exc),
            "family": None,
            "true_tc_k": 0.0,
            "predicted_tc_k": 0.0,
            "calibration_error_k": None,
            "confidence": 0.0,
            "probe_calls": lab.used,
            "mechanism_score": 0.0,
        })
        return row


def _evaluate_split(design_superconductor, ceilings, split, *, reset_before_first=False):
    records = []
    for index, ceiling_gpa in enumerate(ceilings):
        if (index or reset_before_first) and hasattr(design_superconductor, "reset_session"):
            design_superconductor.reset_session()
        records.append(
            _evaluate_trial(design_superconductor, ceiling_gpa, split, index, salt=int(ceiling_gpa))
        )
    return records


def _split_summary(records):
    valid = [r for r in records if r["valid"]]
    return {
        "mean_score": float(np.mean([r["mechanism_score"] for r in records])),
        "valid_count": len(valid),
        "world_count": len(records),
        "feasibility_rate": len(valid) / len(records),
        "mean_probe_calls": float(np.mean([r["probe_calls"] for r in records])),
        "mean_calibration_error_k": (
            float(np.mean([r["calibration_error_k"] for r in valid])) if valid else None
        ),
    }


def evaluate(design_superconductor):
    development = _evaluate_split(design_superconductor, DEVELOPMENT_CEILINGS_GPA, "development")
    heldout = _evaluate_split(
        design_superconductor, HELDOUT_CEILINGS_GPA, "heldout", reset_before_first=True
    )
    dev = _split_summary(development)
    held = _split_summary(heldout)
    return {
        "combined_score": dev["mean_score"],
        "valid": 1.0 if dev["valid_count"] > 0 else 0.0,
        "feasibility_rate": dev["feasibility_rate"],
        "raw_score": dev["mean_score"],
        "development_mean_score": dev["mean_score"],
        "development_mean_probe_calls": dev["mean_probe_calls"],
        "development_mean_calibration_error_k": dev["mean_calibration_error_k"],
        "heldout_mean_score": held["mean_score"],
        "heldout_feasibility_rate": held["feasibility_rate"],
        "heldout_mean_probe_calls": held["mean_probe_calls"],
        "heldout_mean_calibration_error_k": held["mean_calibration_error_k"],
        "per_instance": development + heldout,
    }

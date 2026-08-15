"""Binary equilibrium-stage distillation design oracle, version 2.

The candidate selects tray count, feed stage, reflux ratio and distillate split.  A
deterministic Newton solve closes every light-component stage balance for a total
condenser, equilibrium trays and a partial reboiler.  Nominal development cost controls
search; interleaved held-out regimes and operating shifts remain separate diagnostics.

This is a reduced-order constant-molar-overflow model, not a replacement for a
validated rate-based process simulator or plant data.
"""

from __future__ import annotations

import copy
import math
import numbers

import numpy as np


DISTILLATION_V2 = True
BALANCE_TOLERANCE = 2.0e-8
NEWTON_TOLERANCE = 2.0e-11
MAX_NEWTON_ITERATIONS = 80
DESIGN_FIELDS = (
    "tray_count",
    "feed_stage",
    "reflux_ratio",
    "distillate_fraction",
    "feed_split_gain",
)


# Reference designs come from deterministic fixed-seed calibration searches and are
# replayable feasible witnesses, not global-optimality claims.  A one-percent reflux
# guard band separates the stored witnesses from active purity/recovery constraints.
INSTANCE_SPECS = (
    {
        "name": "dev_balanced_aromatic",
        "split": "development",
        "relative_volatility": 2.45,
        "feed_light_mole_fraction": 0.50,
        "feed_liquid_fraction": 1.00,
        "minimum_distillate_light_mole_fraction": 0.950,
        "maximum_bottoms_light_mole_fraction": 0.050,
        "minimum_light_recovery": 0.930,
        "minimum_heavy_recovery": 0.930,
        "tray_count_bounds": (8, 42),
        "cost": (120000.0, 18000.0, 330000.0),
        "nominal_reference_design": {
            "tray_count": 13, "feed_stage": 7,
            "reflux_ratio": 1.4580089137506798,
            "distillate_fraction": 0.5005830512874706,
            "feed_split_gain": 1.1111111111111112,
        },
        "robust_reference_design": {
            "tray_count": 13, "feed_stage": 7,
            "reflux_ratio": 1.736769892494782,
            "distillate_fraction": 0.49966254069571586,
            "feed_split_gain": 1.298017781185818,
        },
    },
    {
        "name": "heldout_close_boiling",
        "split": "heldout",
        "relative_volatility": 1.78,
        "feed_light_mole_fraction": 0.44,
        "feed_liquid_fraction": 0.90,
        "minimum_distillate_light_mole_fraction": 0.920,
        "maximum_bottoms_light_mole_fraction": 0.080,
        "minimum_light_recovery": 0.900,
        "minimum_heavy_recovery": 0.910,
        "tray_count_bounds": (10, 48),
        "cost": (145000.0, 22000.0, 310000.0),
        "nominal_reference_design": {
            "tray_count": 16, "feed_stage": 9,
            "reflux_ratio": 3.236393953756231,
            "distillate_fraction": 0.43050402947795935,
            "feed_split_gain": 1.1904761904761905,
        },
        "robust_reference_design": {
            "tray_count": 18, "feed_stage": 10,
            "reflux_ratio": 3.744935526915008,
            "distillate_fraction": 0.4303598421128221,
            "feed_split_gain": 1.1563716599909344,
        },
    },
    {
        "name": "dev_high_purity_light",
        "split": "development",
        "relative_volatility": 2.90,
        "feed_light_mole_fraction": 0.36,
        "feed_liquid_fraction": 1.00,
        "minimum_distillate_light_mole_fraction": 0.975,
        "maximum_bottoms_light_mole_fraction": 0.035,
        "minimum_light_recovery": 0.920,
        "minimum_heavy_recovery": 0.950,
        "tray_count_bounds": (8, 44),
        "cost": (130000.0, 19000.0, 360000.0),
        "nominal_reference_design": {
            "tray_count": 12, "feed_stage": 7,
            "reflux_ratio": 1.8575901653884223,
            "distillate_fraction": 0.3459771594831292,
            "feed_split_gain": 1.0638297872340425,
        },
        "robust_reference_design": {
            "tray_count": 13, "feed_stage": 8,
            "reflux_ratio": 2.000432312834936,
            "distillate_fraction": 0.34574506039842684,
            "feed_split_gain": 1.106793822024931,
        },
    },
    {
        "name": "dev_rich_partially_vaporized",
        "split": "development",
        "relative_volatility": 2.12,
        "feed_light_mole_fraction": 0.64,
        "feed_liquid_fraction": 0.65,
        "minimum_distillate_light_mole_fraction": 0.940,
        "maximum_bottoms_light_mole_fraction": 0.075,
        "minimum_light_recovery": 0.930,
        "minimum_heavy_recovery": 0.900,
        "tray_count_bounds": (9, 46),
        "cost": (135000.0, 21000.0, 300000.0),
        "nominal_reference_design": {
            "tray_count": 13, "feed_stage": 7,
            "reflux_ratio": 1.5937595654581844,
            "distillate_fraction": 0.6491028708911217,
            "feed_split_gain": 1.1560693641618498,
        },
        "robust_reference_design": {
            "tray_count": 14, "feed_stage": 7,
            "reflux_ratio": 1.8035192662070445,
            "distillate_fraction": 0.6498288508143049,
            "feed_split_gain": 0.8416494484484107,
        },
    },
    {
        "name": "heldout_difficult_split",
        "split": "heldout",
        "relative_volatility": 1.66,
        "feed_light_mole_fraction": 0.56,
        "feed_liquid_fraction": 0.82,
        "minimum_distillate_light_mole_fraction": 0.910,
        "maximum_bottoms_light_mole_fraction": 0.090,
        "minimum_light_recovery": 0.900,
        "minimum_heavy_recovery": 0.900,
        "tray_count_bounds": (12, 50),
        "cost": (150000.0, 23000.0, 320000.0),
        "nominal_reference_design": {
            "tray_count": 17, "feed_stage": 9,
            "reflux_ratio": 2.9557988168757406,
            "distillate_fraction": 0.5644498713181919,
            "feed_split_gain": 1.2195121951219512,
        },
        "robust_reference_design": {
            "tray_count": 21, "feed_stage": 11,
            "reflux_ratio": 3.2619559758761345,
            "distillate_fraction": 0.5648126212868618,
            "feed_split_gain": 0.7457718230954206,
        },
    },
    {
        "name": "dev_lean_warm_feed",
        "split": "development",
        "relative_volatility": 2.68,
        "feed_light_mole_fraction": 0.27,
        "feed_liquid_fraction": 0.72,
        "minimum_distillate_light_mole_fraction": 0.960,
        "maximum_bottoms_light_mole_fraction": 0.050,
        "minimum_light_recovery": 0.900,
        "minimum_heavy_recovery": 0.960,
        "tray_count_bounds": (8, 44),
        "cost": (125000.0, 20000.0, 350000.0),
        "nominal_reference_design": {
            "tray_count": 12, "feed_stage": 8,
            "reflux_ratio": 3.3047579686524976,
            "distillate_fraction": 0.2524990779363723,
            "feed_split_gain": 1.098901098901099,
        },
        "robust_reference_design": {
            "tray_count": 12, "feed_stage": 8,
            "reflux_ratio": 3.848569999149149,
            "distillate_fraction": 0.25163930133149004,
            "feed_split_gain": 0.8510817244026574,
        },
    },
)


SHIFT_SPECS = (
    {
        "name": "lower_relative_volatility",
        "relative_volatility_scale": 0.94,
        "feed_composition_delta": 0.0,
        "feed_liquid_fraction_delta": 0.0,
        "reflux_ratio_scale": 1.0,
    },
    {
        "name": "richer_feed",
        "relative_volatility_scale": 1.0,
        "feed_composition_delta": 0.025,
        "feed_liquid_fraction_delta": 0.0,
        "reflux_ratio_scale": 1.0,
    },
    {
        "name": "leaner_feed_quality_shift",
        "relative_volatility_scale": 1.0,
        "feed_composition_delta": -0.020,
        "feed_liquid_fraction_delta": -0.10,
        "reflux_ratio_scale": 1.0,
    },
    {
        "name": "reflux_derating",
        "relative_volatility_scale": 1.0,
        "feed_composition_delta": 0.0,
        "feed_liquid_fraction_delta": 0.0,
        "reflux_ratio_scale": 0.92,
    },
    {
        "name": "combined_operating_shift",
        "relative_volatility_scale": 0.96,
        "feed_composition_delta": 0.020,
        "feed_liquid_fraction_delta": 0.08,
        "reflux_ratio_scale": 0.94,
    },
)


def _public_problem(spec):
    top = float(spec["minimum_distillate_light_mole_fraction"])
    bottom = float(spec["maximum_bottoms_light_mole_fraction"])
    feed = float(spec["feed_light_mole_fraction"])
    target_split = (feed - bottom) / (top - bottom)
    return {
        "relative_volatility": float(spec["relative_volatility"]),
        "feed_light_mole_fraction": feed,
        "feed_liquid_fraction": float(spec["feed_liquid_fraction"]),
        "minimum_distillate_light_mole_fraction": top,
        "maximum_bottoms_light_mole_fraction": bottom,
        "minimum_light_recovery": float(spec["minimum_light_recovery"]),
        "minimum_heavy_recovery": float(spec["minimum_heavy_recovery"]),
        "tray_count_bounds": tuple(spec["tray_count_bounds"]),
        "reflux_ratio_bounds": (0.55, 8.0),
        "distillate_fraction_bounds": (
            max(0.08, target_split - 0.13),
            min(0.92, target_split + 0.13),
        ),
        "feed_split_gain_bounds": (0.0, 1.5),
        "annualized_fixed_cost": float(spec["cost"][0]),
        "annualized_cost_per_tray": float(spec["cost"][1]),
        "annualized_cost_per_vapour_flow": float(spec["cost"][2]),
        "feed_flow": 1.0,
        "model": "binary_constant_molar_overflow_equilibrium_stages",
        "design_fields": DESIGN_FIELDS,
    }


def _equilibrium(liquid_composition, relative_volatility):
    x = np.asarray(liquid_composition, dtype=float)
    alpha = float(relative_volatility)
    return alpha * x / (1.0 + (alpha - 1.0) * x)


def _equilibrium_derivative(liquid_composition, relative_volatility):
    x = np.asarray(liquid_composition, dtype=float)
    alpha = float(relative_volatility)
    return alpha / (1.0 + (alpha - 1.0) * x) ** 2


def _solve_tridiagonal(lower, diagonal, upper, right_hand_side):
    lower = np.asarray(lower, dtype=float).copy()
    diagonal = np.asarray(diagonal, dtype=float).copy()
    upper = np.asarray(upper, dtype=float).copy()
    rhs = np.asarray(right_hand_side, dtype=float).copy()
    count = len(diagonal)
    for index in range(1, count):
        pivot = diagonal[index - 1]
        if not np.isfinite(pivot) or abs(pivot) < 1.0e-14:
            raise ValueError("singular stage-balance Jacobian")
        factor = lower[index - 1] / pivot
        diagonal[index] -= factor * upper[index - 1]
        rhs[index] -= factor * rhs[index - 1]
    if not np.isfinite(diagonal[-1]) or abs(diagonal[-1]) < 1.0e-14:
        raise ValueError("singular stage-balance Jacobian")
    result = np.empty(count, dtype=float)
    result[-1] = rhs[-1] / diagonal[-1]
    for index in range(count - 2, -1, -1):
        pivot = diagonal[index]
        if not np.isfinite(pivot) or abs(pivot) < 1.0e-14:
            raise ValueError("singular stage-balance Jacobian")
        result[index] = (
            rhs[index] - upper[index] * result[index + 1]
        ) / pivot
    return result


def _balance_residual_and_jacobian(
    liquid, tray_count, feed_stage, reflux_ratio, distillate_fraction,
    feed_composition, feed_liquid_fraction, relative_volatility,
):
    bottoms = 1.0 - distillate_fraction
    rectifying_liquid = reflux_ratio * distillate_fraction
    rectifying_vapour = (reflux_ratio + 1.0) * distillate_fraction
    stripping_liquid = rectifying_liquid + feed_liquid_fraction
    stripping_vapour = rectifying_vapour - (1.0 - feed_liquid_fraction)
    flows = {
        "distillate_flow": distillate_fraction,
        "bottoms_flow": bottoms,
        "rectifying_liquid_flow": rectifying_liquid,
        "rectifying_vapour_flow": rectifying_vapour,
        "stripping_liquid_flow": stripping_liquid,
        "stripping_vapour_flow": stripping_vapour,
    }
    if min(flows.values()) <= 1.0e-10:
        raise ValueError("nonpositive internal or product flow")

    vapour = _equilibrium(liquid, relative_volatility)
    derivative = _equilibrium_derivative(liquid, relative_volatility)
    residual = np.zeros(tray_count + 1, dtype=float)
    lower = np.zeros(tray_count, dtype=float)
    diagonal = np.zeros(tray_count + 1, dtype=float)
    upper = np.zeros(tray_count, dtype=float)

    for zero_index in range(tray_count):
        stage = zero_index + 1
        if stage < feed_stage:
            if stage == 1:
                residual[zero_index] = (
                    rectifying_liquid * vapour[0]
                    + rectifying_vapour * vapour[1]
                    - rectifying_liquid * liquid[0]
                    - rectifying_vapour * vapour[0]
                )
                diagonal[zero_index] = (
                    (rectifying_liquid - rectifying_vapour)
                    * derivative[0] - rectifying_liquid
                )
            else:
                residual[zero_index] = (
                    rectifying_liquid * liquid[zero_index - 1]
                    + rectifying_vapour * vapour[zero_index + 1]
                    - rectifying_liquid * liquid[zero_index]
                    - rectifying_vapour * vapour[zero_index]
                )
                lower[zero_index - 1] = rectifying_liquid
                diagonal[zero_index] = (
                    -rectifying_liquid
                    - rectifying_vapour * derivative[zero_index]
                )
            upper[zero_index] = rectifying_vapour * derivative[zero_index + 1]
        elif stage == feed_stage:
            liquid_in = rectifying_liquid
            composition_in = (
                liquid[zero_index - 1] if stage > 1 else vapour[0]
            )
            residual[zero_index] = (
                liquid_in * composition_in
                + stripping_vapour * vapour[zero_index + 1]
                + feed_composition
                - stripping_liquid * liquid[zero_index]
                - rectifying_vapour * vapour[zero_index]
            )
            if stage > 1:
                lower[zero_index - 1] = liquid_in
                condenser_return_derivative = 0.0
            else:
                condenser_return_derivative = liquid_in * derivative[0]
            diagonal[zero_index] = (
                condenser_return_derivative
                -stripping_liquid
                - rectifying_vapour * derivative[zero_index]
            )
            upper[zero_index] = stripping_vapour * derivative[zero_index + 1]
        else:
            residual[zero_index] = (
                stripping_liquid * liquid[zero_index - 1]
                + stripping_vapour * vapour[zero_index + 1]
                - stripping_liquid * liquid[zero_index]
                - stripping_vapour * vapour[zero_index]
            )
            lower[zero_index - 1] = stripping_liquid
            diagonal[zero_index] = (
                -stripping_liquid
                - stripping_vapour * derivative[zero_index]
            )
            upper[zero_index] = stripping_vapour * derivative[zero_index + 1]

    residual[tray_count] = (
        stripping_liquid * liquid[tray_count - 1]
        - stripping_vapour * vapour[tray_count]
        - bottoms * liquid[tray_count]
    )
    lower[tray_count - 1] = stripping_liquid
    diagonal[tray_count] = (
        -stripping_vapour * derivative[tray_count] - bottoms
    )
    return residual, lower, diagonal, upper, flows


def _solve_column(
    design, problem, relative_volatility=None, feed_composition=None,
    feed_liquid_fraction=None, reflux_ratio_scale=1.0,
    distillate_fraction_override=None,
):
    tray_count = int(design["tray_count"])
    feed_stage = int(design["feed_stage"])
    reflux_ratio = float(design["reflux_ratio"]) * float(reflux_ratio_scale)
    distillate_fraction = float(
        design["distillate_fraction"]
        if distillate_fraction_override is None
        else distillate_fraction_override
    )
    if not 0.02 <= distillate_fraction <= 0.98:
        raise ValueError("shifted distillate fraction is physically invalid")
    alpha = float(
        problem["relative_volatility"]
        if relative_volatility is None else relative_volatility
    )
    feed = float(
        problem["feed_light_mole_fraction"]
        if feed_composition is None else feed_composition
    )
    quality = float(
        problem["feed_liquid_fraction"]
        if feed_liquid_fraction is None else feed_liquid_fraction
    )
    starts = (
        (
            max(0.55, problem["minimum_distillate_light_mole_fraction"] - 0.08),
            min(0.35, problem["maximum_bottoms_light_mole_fraction"] + 0.04),
        ),
        (0.70, 0.10),
        (0.96, 0.005),
        (feed, feed),
    )
    best = None
    for top, bottom in starts:
        liquid = np.linspace(top, bottom, tray_count + 1, dtype=float)
        iteration = 0
        for iteration in range(MAX_NEWTON_ITERATIONS):
            residual, lower, diagonal, upper, flows = (
                _balance_residual_and_jacobian(
                    liquid, tray_count, feed_stage, reflux_ratio,
                    distillate_fraction, feed, quality, alpha,
                )
            )
            maximum_residual = float(np.max(np.abs(residual)))
            if maximum_residual < NEWTON_TOLERANCE:
                break
            step = _solve_tridiagonal(lower, diagonal, upper, -residual)
            merit = float(np.dot(residual, residual))
            step_scale = 1.0
            accepted = False
            for _ in range(32):
                trial = liquid + step_scale * step
                if np.all((trial > 1.0e-10) & (trial < 1.0 - 1.0e-10)):
                    trial_residual = _balance_residual_and_jacobian(
                        trial, tray_count, feed_stage, reflux_ratio,
                        distillate_fraction, feed, quality, alpha,
                    )[0]
                    if float(np.dot(trial_residual, trial_residual)) < (
                        merit * (1.0 - 1.0e-4 * step_scale)
                    ):
                        liquid = trial
                        accepted = True
                        break
                step_scale *= 0.5
            if not accepted:
                break
        residual, _, _, _, flows = _balance_residual_and_jacobian(
            liquid, tray_count, feed_stage, reflux_ratio,
            distillate_fraction, feed, quality, alpha,
        )
        maximum_residual = float(np.max(np.abs(residual)))
        if best is None or maximum_residual < best[0]:
            best = (maximum_residual, liquid.copy(), iteration + 1, flows)
        # Retain the remaining starts as convergence fallbacks.  Once a root meets the
        # documented acceptance tolerance, extra starts do not change its accepted metrics.
        if maximum_residual < BALANCE_TOLERANCE:
            break
    if best is None or best[0] > BALANCE_TOLERANCE:
        raise ValueError("stage-balance solve did not converge")

    maximum_residual, liquid, iterations, flows = best
    vapour = _equilibrium(liquid, alpha)
    distillate_composition = float(vapour[0])
    bottoms_composition = float(liquid[-1])
    overall_balance_residual = abs(
        feed
        - distillate_fraction * distillate_composition
        - (1.0 - distillate_fraction) * bottoms_composition
    )
    if overall_balance_residual > BALANCE_TOLERANCE:
        raise ValueError("overall component balance did not close")
    light_recovery = (
        distillate_fraction * distillate_composition / max(feed, 1.0e-12)
    )
    heavy_recovery = (
        (1.0 - distillate_fraction) * (1.0 - bottoms_composition)
        / max(1.0 - feed, 1.0e-12)
    )
    annualized_cost = (
        float(problem["annualized_fixed_cost"])
        + float(problem["annualized_cost_per_tray"]) * tray_count
        + float(problem["annualized_cost_per_vapour_flow"])
        * max(flows["rectifying_vapour_flow"], flows["stripping_vapour_flow"])
    )
    feasible = bool(
        distillate_composition
        >= float(problem["minimum_distillate_light_mole_fraction"])
        and bottoms_composition
        <= float(problem["maximum_bottoms_light_mole_fraction"])
        and light_recovery >= float(problem["minimum_light_recovery"])
        and heavy_recovery >= float(problem["minimum_heavy_recovery"])
    )
    return {
        "process_feasible": feasible,
        "distillate_light_mole_fraction": distillate_composition,
        "bottoms_light_mole_fraction": bottoms_composition,
        "light_recovery": float(light_recovery),
        "heavy_recovery": float(heavy_recovery),
        "annualized_cost": float(annualized_cost),
        "maximum_stage_balance_residual": maximum_residual,
        "overall_component_balance_residual": overall_balance_residual,
        "newton_iterations": int(iterations),
        **flows,
    }


def _validate_design(value, problem):
    if not isinstance(value, dict) or set(value) != set(DESIGN_FIELDS):
        raise ValueError("design must contain exactly the five documented fields")
    values = {}
    for field in DESIGN_FIELDS:
        item = value[field]
        if isinstance(item, (bool, np.bool_)):
            raise ValueError("boolean design values are not allowed")
        if not isinstance(item, numbers.Real):
            raise ValueError("design values must be real numeric scalars")
        number = float(item)
        if not np.isfinite(number):
            raise ValueError("design values must be finite")
        values[field] = number
    for field in ("tray_count", "feed_stage"):
        if not values[field].is_integer():
            raise ValueError("tray count and feed stage must be exact integers")
        values[field] = int(values[field])
    lower_trays, upper_trays = problem["tray_count_bounds"]
    if not lower_trays <= values["tray_count"] <= upper_trays:
        raise ValueError("tray count is outside public bounds")
    if not 1 <= values["feed_stage"] <= values["tray_count"]:
        raise ValueError("feed stage is outside the installed tray range")
    lower_reflux, upper_reflux = problem["reflux_ratio_bounds"]
    if not lower_reflux <= values["reflux_ratio"] <= upper_reflux:
        raise ValueError("reflux ratio is outside public bounds")
    lower_split, upper_split = problem["distillate_fraction_bounds"]
    if not lower_split <= values["distillate_fraction"] <= upper_split:
        raise ValueError("distillate fraction is outside public bounds")
    lower_gain, upper_gain = problem["feed_split_gain_bounds"]
    if not lower_gain <= values["feed_split_gain"] <= upper_gain:
        raise ValueError("feed split gain is outside public bounds")
    return values


def _baseline_design(problem):
    from math import log

    def odds(value):
        value = min(max(float(value), 1.0e-8), 1.0 - 1.0e-8)
        return value / (1.0 - value)

    tray_count = int(problem["tray_count_bounds"][1])
    alpha = float(problem["relative_volatility"])
    feed = float(problem["feed_light_mole_fraction"])
    top = float(problem["minimum_distillate_light_mole_fraction"])
    bottom = float(problem["maximum_bottoms_light_mole_fraction"])
    upper = max(0.0, log(odds(top) / odds(feed)) / log(alpha))
    lower = max(0.0, log(odds(feed) / odds(bottom)) / log(alpha))
    feed_stage = int(round(1.0 + upper / max(upper + lower, 1.0e-12)
                           * (tray_count - 1)))
    target_split = (feed - bottom) / (top - bottom)
    minimum_split = float(problem["minimum_light_recovery"]) * feed / top
    maximum_split = 1.0 - (
        float(problem["minimum_heavy_recovery"]) * (1.0 - feed)
        / (1.0 - bottom)
    )
    if minimum_split <= maximum_split:
        target_split = min(max(target_split, minimum_split), maximum_split)
    split_bounds = problem["distillate_fraction_bounds"]
    return {
        "tray_count": tray_count,
        "feed_stage": min(max(feed_stage, 1), tray_count),
        "reflux_ratio": 0.86 * float(problem["reflux_ratio_bounds"][1]),
        "distillate_fraction": min(
            max(target_split, split_bounds[0]), split_bounds[1]
        ),
        "feed_split_gain": 1.0 / max(top - bottom, 0.20),
    }


def _shifted_metrics(design, problem, shift):
    shifted_feed = float(np.clip(
        problem["feed_light_mole_fraction"]
        + shift["feed_composition_delta"],
        0.05, 0.95,
    ))
    shifted_distillate = (
        design["distillate_fraction"]
        + design["feed_split_gain"]
        * (shifted_feed - problem["feed_light_mole_fraction"])
    )
    return {
        "name": shift["name"],
        "valid": True,
        **_solve_column(
            design,
            problem,
            relative_volatility=(
                problem["relative_volatility"]
                * shift["relative_volatility_scale"]
            ),
            feed_composition=shifted_feed,
            feed_liquid_fraction=float(np.clip(
                problem["feed_liquid_fraction"]
                + shift["feed_liquid_fraction_delta"],
                0.05, 1.0,
            )),
            reflux_ratio_scale=shift["reflux_ratio_scale"],
            distillate_fraction_override=shifted_distillate,
        ),
    }


def _safe_shifted_metrics(design, problem, shift):
    """Keep sealed off-design failures out of nominal validity and selection."""
    try:
        return _shifted_metrics(design, problem, shift)
    except Exception as exc:
        return {
            "name": shift["name"],
            "valid": False,
            "process_feasible": False,
            "reason": "%s: %s" % (type(exc).__name__, exc),
        }


def _make_instance(spec):
    instance = {"name": spec["name"], "split": spec["split"]}
    problem = _public_problem(spec)
    instance["problem"] = problem
    baseline_design = _baseline_design(problem)
    instance["baseline_design"] = baseline_design
    instance["baseline_nominal"] = _solve_column(baseline_design, problem)
    nominal_design = spec["nominal_reference_design"]
    robust_design = spec["robust_reference_design"]
    instance["nominal_reference_design"] = nominal_design
    instance["robust_reference_design"] = robust_design
    if nominal_design is not None:
        instance["nominal_reference"] = _solve_column(nominal_design, problem)
    if robust_design is not None:
        instance["robust_reference"] = _solve_column(robust_design, problem)
    return instance


INSTANCES = tuple(_make_instance(spec) for spec in INSTANCE_SPECS)
DEVELOPMENT_INSTANCES = tuple(
    instance for instance in INSTANCES if instance["split"] == "development"
)
HELDOUT_INSTANCES = tuple(
    instance for instance in INSTANCES if instance["split"] == "heldout"
)


def reference_policy(problem, robust=False):
    """Replay a stored witness for trusted calibration and invariant tests."""
    key = "robust_reference_design" if robust else "nominal_reference_design"
    for instance in INSTANCES:
        if instance["problem"] == problem:
            return copy.deepcopy(instance[key])
    raise ValueError("unknown public distillation problem")


def _normalized_cost_score(baseline_cost, reference_cost, candidate_cost):
    """Zero at the baseline, one at the reference witness, unbounded above it.

    The upper clip made the witness the best achievable score, so a better result read as exactly
    as good as the witness and the task could report nothing about a searcher that had beaten it.
    Every recorded run scored at or below one, so their scores are unchanged. The floor stays,
    because below the baseline is a worse result rather than a negative achievement.
    """
    denominator = float(baseline_cost) - float(reference_cost)
    if denominator <= 0.0:
        raise ValueError("reference does not improve baseline cost")
    return float(max((float(baseline_cost) - float(candidate_cost)) / denominator, 0.0))


def _score_instance(design_column, instance):
    try:
        problem = instance["problem"]
        design = _validate_design(
            design_column(copy.deepcopy(problem)), problem
        )
        nominal = _solve_column(design, problem)
        shifted = tuple(
            _safe_shifted_metrics(design, problem, shift)
            for shift in SHIFT_SPECS
        )
        nominal_reference = instance.get("nominal_reference")
        robust_reference = instance.get("robust_reference")
        nominal_score = 0.0
        robust_score = 0.0
        if nominal_reference is not None and nominal["process_feasible"]:
            nominal_score = _normalized_cost_score(
                instance["baseline_nominal"]["annualized_cost"],
                nominal_reference["annualized_cost"],
                nominal["annualized_cost"],
            )
        all_shifts_feasible = all(
            row["process_feasible"] for row in shifted
        )
        if robust_reference is not None and all_shifts_feasible:
            robust_score = _normalized_cost_score(
                instance["baseline_nominal"]["annualized_cost"],
                robust_reference["annualized_cost"],
                nominal["annualized_cost"],
            )
        return {
            "name": instance["name"],
            "split": instance["split"],
            "valid": True,
            "process_feasible": nominal["process_feasible"],
            "score": nominal_score,
            "robustness_score": robust_score,
            "all_shifts_feasible": all_shifts_feasible,
            "shift_feasibility_rate": float(np.mean([
                row["process_feasible"] for row in shifted
            ])),
            "design": design,
            "nominal": nominal,
            "shifted": shifted,
            "baseline_cost": instance["baseline_nominal"]["annualized_cost"],
            "nominal_reference_cost": (
                None if nominal_reference is None
                else nominal_reference["annualized_cost"]
            ),
            "robust_reference_cost": (
                None if robust_reference is None
                else robust_reference["annualized_cost"]
            ),
        }
    except Exception as exc:
        return {
            "name": instance["name"],
            "split": instance["split"],
            "valid": False,
            "process_feasible": False,
            "reason": "%s: %s" % (type(exc).__name__, exc),
            "score": 0.0,
            "robustness_score": 0.0,
            "all_shifts_feasible": False,
            "shift_feasibility_rate": 0.0,
        }


def _reset_candidate_session(design_column):
    reset = getattr(design_column, "reset_session", None)
    if callable(reset):
        reset()


def evaluate(design_column):
    records = []
    for index, instance in enumerate(INSTANCES):
        if index:
            _reset_candidate_session(design_column)
        records.append(_score_instance(design_column, instance))
    development = [row for row in records if row["split"] == "development"]
    heldout = [row for row in records if row["split"] == "heldout"]
    development_valid = sum(bool(row["valid"]) for row in development)
    heldout_valid = sum(bool(row["valid"]) for row in heldout)
    development_score = float(np.mean([row["score"] for row in development]))
    heldout_score = float(np.mean([row["score"] for row in heldout]))
    return {
        "combined_score": development_score if (
            development_valid == len(development)
        ) else 0.0,
        "valid": 1.0 if development_valid == len(development) else 0.0,
        "feasibility_rate": float(np.mean([
            row["process_feasible"] for row in development
        ])),
        "raw_score": development_score if (
            development_valid == len(development)
        ) else 0.0,
        "robustness_score": float(np.mean([
            row["robustness_score"] for row in development
        ])),
        "heldout_policy_score": heldout_score if (
            heldout_valid == len(heldout)
        ) else 0.0,
        "heldout_robustness_score": float(np.mean([
            row["robustness_score"] for row in heldout
        ])),
        "heldout_feasibility_rate": float(np.mean([
            row["process_feasible"] for row in heldout
        ])),
        "development_shift_feasibility_rate": float(np.mean([
            row["shift_feasibility_rate"] for row in development
        ])),
        "heldout_shift_feasibility_rate": float(np.mean([
            row["shift_feasibility_rate"] for row in heldout
        ])),
        "development_mean_annualized_cost": float(np.mean([
            row.get("nominal", {}).get("annualized_cost", 0.0)
            for row in development
        ])),
        "heldout_mean_annualized_cost": float(np.mean([
            row.get("nominal", {}).get("annualized_cost", 0.0)
            for row in heldout
        ])),
        "candidate_instance_call_count": len(records),
        "candidate_instance_valid_rate": float(np.mean([
            row["valid"] for row in records
        ])),
        "per_instance": records,
    }

#!/usr/bin/env python3
"""Plan Track F sample size from the frozen measurement pilot.

The endpoint exposes no server-side generation seed, so conditions are powered
as independent provider draws rather than as paired seeds.  One task-specific
primary hypothesis is defined for ActiveLaw fresh mechanism recovery.  The
Diffraction fresh-robustness panel is a high-variance secondary stress test.  The
cohort size is fixed before new runs; no future outcome enters this calculation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import statistics
import sys
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scipy import __version__ as scipy_version
from scipy.stats import nct, t


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sle.algorithms.common import atomic_write_text  # noqa: E402
from sle.provenance import (  # noqa: E402
    finalize_report_trust,
    source_provenance,
)


EXPECTED_TASKS = (
    "DynamicalSystems/ActiveLawDiscovery",
    "Optics/DiffractionGratingDesign",
)
PRIMARY_CONTRAST = "normal_minus_selection_blind"
PRIMARY_HORIZON = "common_total_token_horizon"
PRIMARY_TASK = "DynamicalSystems/ActiveLawDiscovery"
PRIMARY_PILOT_AXIS = "robustness_score"
PRIMARY_FUTURE_AXIS = "confirmation_normalized_mechanism_score"
SECONDARY_TASK = "Optics/DiffractionGratingDesign"
SECONDARY_PILOT_AXIS = "heldout_robustness_score"
SECONDARY_FUTURE_AXIS = "confirmation_robustness_score"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def exact_two_sample_power(
    *, n_per_condition: int, sigma: float, effect: float, alpha: float,
) -> float:
    if n_per_condition < 2 or sigma <= 0 or effect <= 0 or not 0 < alpha < 1:
        raise ValueError("invalid noncentral-t power inputs")
    degrees = 2 * n_per_condition - 2
    critical = float(t.ppf(1.0 - alpha / 2.0, degrees))
    noncentrality = float(effect) / (
        float(sigma) * math.sqrt(2.0 / n_per_condition)
    )
    # Boost can warn at effectively unit power when the noncentrality is very
    # large (ActiveLaw's two pilot differences are nearly identical). Suppress
    # only this local tail computation, then fail closed unless the result is a
    # finite probability.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        power = float(
            nct.cdf(-critical, degrees, noncentrality)
            + nct.sf(critical, degrees, noncentrality)
        )
    if not math.isfinite(power) or not 0.0 <= power <= 1.0:
        raise ValueError("noncentral-t power calculation returned an invalid value")
    return power


def minimum_n(
    *, sigma: float, effect: float, alpha: float, target_power: float,
    maximum_n: int = 10000,
) -> tuple[int, float]:
    if not 0 < target_power < 1:
        raise ValueError("target power must lie in (0,1)")
    # Track F uses a four-row Williams design, so n<4 is neither actionable nor
    # needed; avoiding those extreme degrees of freedom also keeps SciPy's
    # noncentral-t implementation away from an irrelevant numerical boundary.
    for n in range(4, int(maximum_n) + 1):
        power = exact_two_sample_power(
            n_per_condition=n, sigma=sigma, effect=effect, alpha=alpha
        )
        if math.isfinite(power) and power >= target_power:
            return n, power
    raise ValueError("target power not reached by maximum_n")


def _round_up(value: int, multiple: int) -> int:
    if value < 1 or multiple < 1:
        raise ValueError("rounding inputs must be positive")
    return int(math.ceil(value / multiple) * multiple)


def plan(
    pilot_path: Path,
    *,
    mde: float = 0.15,
    alpha: float = 0.05,
    target_power: float = 0.80,
    balance_multiple: int = 4,
    design_sigma: float = 0.25,
    sensitivity_sigmas: tuple[float, ...] = (0.20, 0.25, 0.30, 0.35),
) -> dict[str, Any]:
    pilot = json.loads(pilot_path.read_text(encoding="utf-8"))
    claims = pilot.get("claims") or {}
    if not (
        pilot.get("schema_version") == 1
        and pilot.get("execution_passed") is True
        and pilot.get("trusted_evidence") is True
        and pilot.get("passed") is True
        and claims.get("measurement_pipeline_calibrated") is True
        and claims.get("feedback_causal_effect_identified") is False
        and set(EXPECTED_TASKS).issubset(
            set((pilot.get("diagnostic_summaries") or {}).keys())
        )
    ):
        raise ValueError("pilot is not trusted feedback measurement evidence")
    if (
        mde <= 0
        or not 0 < alpha < 1
        or not 0 < target_power < 1
        or design_sigma <= 0
    ):
        raise ValueError("invalid design parameters")

    def diagnostic(task: str, axis: str) -> dict[str, Any]:
        differences = [
            float(row[PRIMARY_HORIZON][axis])
            for row in pilot.get("paired_descriptive_contrasts") or []
            if row.get("task") == task
            and row.get("contrast") == PRIMARY_CONTRAST
        ]
        if len(differences) < 2:
            raise ValueError("pilot lacks two differences for %s/%s" % (task, axis))
        sigma = statistics.stdev(differences)
        if not math.isfinite(sigma) or sigma <= 0:
            raise ValueError("pilot variance is unavailable for %s/%s" % (task, axis))
        raw_n, achieved = minimum_n(
            sigma=sigma, effect=mde, alpha=alpha, target_power=target_power
        )
        return {
            "axis": axis,
            "pilot_local_identifier_differences": differences,
            "pilot_n": len(differences),
            "pilot_difference_sample_sd": sigma,
            "unstable_two_identifier_diagnostic_only": True,
            "implied_independent_draw_minimum_n_per_condition": raw_n,
            "implied_power_at_minimum_n": achieved,
        }

    pilot_diagnostics = {
        PRIMARY_TASK: diagnostic(PRIMARY_TASK, PRIMARY_PILOT_AXIS),
        SECONDARY_TASK: diagnostic(SECONDARY_TASK, SECONDARY_PILOT_AXIS),
    }
    scenarios = []
    for sigma in sensitivity_sigmas:
        raw_n, achieved = minimum_n(
            sigma=float(sigma), effect=mde, alpha=alpha,
            target_power=target_power,
        )
        balanced_n = _round_up(raw_n, balance_multiple)
        scenarios.append({
            "assumed_per_condition_sd": float(sigma),
            "minimum_unrounded_n_per_condition": raw_n,
            "power_at_minimum_unrounded_n": achieved,
            "balanced_n_per_condition": balanced_n,
            "power_at_balanced_n": exact_two_sample_power(
                n_per_condition=balanced_n,
                sigma=float(sigma), effect=mde, alpha=alpha,
            ),
        })
    selected = next(
        row for row in scenarios
        if abs(row["assumed_per_condition_sd"] - design_sigma) <= 1.0e-12
    )
    fixed_n = int(selected["balanced_n_per_condition"])
    return {
        "schema_version": 1,
        "trust_status": "TRUSTED_DERIVED_EVIDENCE / DESIGN_ONLY",
        "evidence_scope": (
            "PILOT_BASED_TRACK_F_PRECISION_PLANNING_NOT_FEEDBACK_EFFECT_OR_"
            "AUTONOMOUS_DISCOVERY_EVIDENCE"
        ),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_provenance": source_provenance(ROOT),
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
            "scipy": scipy_version,
        },
        "input": {"path": str(pilot_path), "sha256": _sha256(pilot_path)},
        "design": {
            "primary_contrast": PRIMARY_CONTRAST,
            "primary_horizon": PRIMARY_HORIZON,
            "primary_task": PRIMARY_TASK,
            "primary_pilot_proxy_axis": PRIMARY_PILOT_AXIS,
            "primary_fresh_confirmation_axis": PRIMARY_FUTURE_AXIS,
            "secondary_stress_test_task": SECONDARY_TASK,
            "secondary_pilot_axis": SECONDARY_PILOT_AXIS,
            "secondary_fresh_confirmation_axis": SECONDARY_FUTURE_AXIS,
            "minimum_important_difference": mde,
            "two_sided_alpha": alpha,
            "confirmatory_primary_hypothesis_count": 1,
            "target_power": target_power,
            "power_method": "two_sided_equal_n_independent_two_sample_noncentral_t",
            "provider_draw_assumption": "independent_unpaired",
            "same_local_identifier_is_paired_seed": False,
            "design_per_condition_sd": design_sigma,
            "balance_multiple": balance_multiple,
            "sensitivity_per_condition_sds": list(sensitivity_sigmas),
        },
        "pilot_diagnostics": pilot_diagnostics,
        "design_sigma_scenarios": scenarios,
        "fixed_balanced_blocks_per_condition": fixed_n,
        "power_at_fixed_n_under_design_sigma": selected["power_at_balanced_n"],
        "scheduled_search_cells": len(EXPECTED_TASKS) * 4 * fixed_n,
        "scheduled_model_proposals": len(EXPECTED_TASKS) * 4 * fixed_n * 3,
        "fixed_sample_rule": {
            "sample_size_adaptation": False,
            "interim_efficacy_or_futility_analysis": False,
            "early_stopping_from_outcomes": False,
            "reason": (
                "the search report exposes condition-labelled trajectories and aggregates; "
                "therefore a post-stage-1 blinded variance reassessment would not be a "
                "credible operational blind"
            ),
        },
        "limitations": [
            "The pilot has only two uncontrolled local identifiers per task.",
            "The endpoint exposes no server-side seed; same-number conditions are not paired model draws.",
            "The design standard deviation is preregistered rather than estimated from two unstable pilot differences.",
            "Diffraction fresh robustness is a high-variance secondary stress test and receives no confirmatory significance claim.",
            "The sole confirmatory primary is ActiveLaw normal versus selection-blind fresh mechanism at the common-token endpoint.",
            "The design does not justify a cross-task science score or a general scientific-agent effect.",
            "Power is a design calculation, not evidence that the future effect exists.",
        ],
        "claims": {
            "fixed_sample_size_planned": True,
            "feedback_effect_identified": False,
            "population_effect_estimated": False,
            "autonomous_discovery_demonstrated": False,
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pilot", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--mde", type=float, default=0.15)
    parser.add_argument("--alpha", type=float, default=0.05)
    parser.add_argument("--target-power", type=float, default=0.80)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report = plan(
            args.pilot.expanduser().resolve(),
            mde=args.mde,
            alpha=args.alpha,
            target_power=args.target_power,
        )
    except (OSError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc
    finalize_report_trust(report, True)
    output = args.output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(output, json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(json.dumps({
        "output": str(output),
        "fixed_blocks_per_condition": report[
            "fixed_balanced_blocks_per_condition"
        ],
        "power_at_fixed_n": report["power_at_fixed_n_under_design_sigma"],
        "execution_passed": report["execution_passed"],
        "trusted_evidence": report["trusted_evidence"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Plan Track F sample size from the frozen measurement pilot.

The calculation uses the preregistered normal-minus-selection-blind block
differences, a two-sided noncentral-t power function, and a conservative
Holm/Bonferroni first-step alpha across the two task-specific primary hypotheses.
It reports stage-1 and blinded variance-reassessment options; it does not inspect
or predict any future confirmatory outcome.
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

from frontier_science.algorithms.common import atomic_write_text  # noqa: E402
from frontier_science.provenance import (  # noqa: E402
    finalize_report_trust,
    source_provenance,
)


EXPECTED_TASKS = (
    "DynamicalSystems/ActiveLawDiscovery",
    "Optics/DiffractionGratingDesign",
)
PRIMARY_CONTRAST = "normal_minus_selection_blind"
PRIMARY_HORIZON = "common_total_token_horizon"
PRIMARY_FIELD = "best_score"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def exact_two_sided_power(
    *, n: int, sigma: float, effect: float, alpha: float,
) -> float:
    if n < 2 or sigma <= 0 or effect <= 0 or not 0 < alpha < 1:
        raise ValueError("invalid noncentral-t power inputs")
    degrees = n - 1
    critical = float(t.ppf(1.0 - alpha / 2.0, degrees))
    noncentrality = float(effect) / (float(sigma) / math.sqrt(n))
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
        power = exact_two_sided_power(
            n=n, sigma=sigma, effect=effect, alpha=alpha
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
    familywise_alpha: float = 0.05,
    primary_hypothesis_count: int = 2,
    target_power: float = 0.80,
    balance_multiple: int = 4,
    variance_multipliers: tuple[float, ...] = (1.0, 1.25, 1.5),
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
        or not 0 < familywise_alpha < 1
        or primary_hypothesis_count < 1
        or not 0 < target_power < 1
    ):
        raise ValueError("invalid design parameters")
    conservative_alpha = familywise_alpha / primary_hypothesis_count
    by_task = {}
    for task in EXPECTED_TASKS:
        differences = [
            float(row[PRIMARY_HORIZON][PRIMARY_FIELD])
            for row in pilot.get("paired_descriptive_contrasts") or []
            if row.get("task") == task
            and row.get("contrast") == PRIMARY_CONTRAST
        ]
        if len(differences) < 2:
            raise ValueError("pilot lacks two differences for %s" % task)
        sigma = statistics.stdev(differences)
        if not math.isfinite(sigma) or sigma <= 0:
            raise ValueError("pilot variance is unavailable for %s" % task)
        scenarios = []
        for multiplier in variance_multipliers:
            inflated_sigma = sigma * float(multiplier)
            raw_n, achieved = minimum_n(
                sigma=inflated_sigma,
                effect=mde,
                alpha=conservative_alpha,
                target_power=target_power,
            )
            balanced_n = _round_up(raw_n, balance_multiple)
            scenarios.append({
                "variance_multiplier": float(multiplier),
                "assumed_sigma": inflated_sigma,
                "minimum_unrounded_n": raw_n,
                "power_at_minimum_unrounded_n": achieved,
                "balanced_n": balanced_n,
                "power_at_balanced_n": exact_two_sided_power(
                    n=balanced_n,
                    sigma=inflated_sigma,
                    effect=mde,
                    alpha=conservative_alpha,
                ),
            })
        by_task[task] = {
            "pilot_block_differences": differences,
            "pilot_n": len(differences),
            "pilot_sample_sd": sigma,
            "scenarios": scenarios,
        }
    most_variable_task = max(
        EXPECTED_TASKS, key=lambda task: by_task[task]["pilot_sample_sd"]
    )
    stage1_n = max(
        by_task[task]["scenarios"][0]["balanced_n"]
        for task in EXPECTED_TASKS
    )
    maximum_n = max(
        scenario["balanced_n"]
        for task in EXPECTED_TASKS
        for scenario in by_task[task]["scenarios"]
    )
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
            "primary_field": PRIMARY_FIELD,
            "minimum_important_difference": mde,
            "familywise_alpha": familywise_alpha,
            "primary_hypothesis_count": primary_hypothesis_count,
            "conservative_two_sided_alpha": conservative_alpha,
            "target_power": target_power,
            "power_method": "two_sided_one_sample_noncentral_t",
            "balance_multiple": balance_multiple,
            "variance_multipliers": list(variance_multipliers),
        },
        "task_plans": by_task,
        "most_variable_task": most_variable_task,
        "stage1_balanced_blocks_per_condition": stage1_n,
        "maximum_blinded_variance_reassessment_blocks_per_condition": maximum_n,
        "blinded_reassessment_rule": {
            "timing": "after all stage-1 blocks and before treatment labels/outcomes are analyzed",
            "variance_only": True,
            "outcome_means_or_directions_used": False,
            "method": (
                "estimate pooled within-block residual variance without condition labels; "
                "choose the smallest multiple of four reaching target power under the "
                "frozen noncentral-t function, capped at the preregistered maximum"
            ),
            "no_early_efficacy_or_futility_stop": True,
        },
        "limitations": [
            "The pilot has only two uncontrolled local identifiers per task.",
            "Pilot sample standard deviations are unstable and motivate blinded reassessment.",
            "The calculation plans task-specific normal-versus-selection-blind score contrasts; it does not justify a cross-task science score.",
            "Power is a design calculation, not evidence that the future effect exists.",
        ],
        "claims": {
            "stage1_sample_size_planned": True,
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
    parser.add_argument("--familywise-alpha", type=float, default=0.05)
    parser.add_argument("--target-power", type=float, default=0.80)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report = plan(
            args.pilot.expanduser().resolve(),
            mde=args.mde,
            familywise_alpha=args.familywise_alpha,
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
        "stage1_blocks_per_condition": report[
            "stage1_balanced_blocks_per_condition"
        ],
        "maximum_blocks_per_condition": report[
            "maximum_blinded_variance_reassessment_blocks_per_condition"
        ],
        "execution_passed": report["execution_passed"],
        "trusted_evidence": report["trusted_evidence"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

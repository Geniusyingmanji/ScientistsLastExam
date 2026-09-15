"""Development-only calibration and low-dimensional shortcut probes."""
from __future__ import annotations

import importlib.util
import itertools
from pathlib import Path


HERE = Path(__file__).resolve().parent


def _load(name):
    spec = importlib.util.spec_from_file_location(name, HERE / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


evaluator = _load("evaluator")
reference = _load("reference_solver")

FRACTION_SCHEDULES = (
    (0.00, 0.25, 0.50, 0.75, 1.00),
    (0.00, 0.20, 0.45, 0.70, 1.00),
    (0.05, 0.25, 0.50, 0.80, 1.00),
    (0.10, 0.30, 0.55, 0.80, 1.00),
    (0.00, 0.15, 0.35, 0.65, 1.00),
    (0.10, 0.25, 0.45, 0.70, 0.95),
    (0.15, 0.35, 0.55, 0.75, 0.95),
    (0.05, 0.20, 0.40, 0.65, 0.90),
)
RMS_LIMITS = (0.8, 1.0, 1.2, 1.3, 1.5)
GAP_LIMITS = (0.0, 2.0, 3.0, 6.0)
CORRELATION_LIMITS = (0.35, 0.50, 0.55, 0.80)
ALTERNATIVE_GAP_LIMITS = (-3.0, -1.5, 0.0, 3.0, 6.0, 9.0)


def _anchors(observation, fractions):
    start = max(map(int, observation["transit_numbers"])) + 1
    limit = int(observation["maximum_followup_transit_number"])
    return tuple(int(round(start + fraction * (limit - start))) for fraction in fractions)


def fitted_policy(fractions, rms_limit, gap_limit, correlation_limit,
                  alternative_gap_limit):
    def candidate(observation, measure, budget_units):
        return reference._attribute_ttv(
            observation,
            measure,
            budget_units,
            rms_limit,
            gap_limit,
            correlation_limit,
            alternative_gap_limit=alternative_gap_limit,
            anchors=_anchors(observation, fractions),
        )
    return candidate


def reference_ablation(kind):
    def candidate(observation, measure, budget_units):
        visible = dict(observation)
        if kind == "no_activity_model":
            visible["activity_period_grid"] = []
        limit = min(int(budget_units), 3) if kind == "three_followups" else int(budget_units)
        alternative_gap = -1e9 if kind == "no_out_of_family_evidence" else 6.0
        result = reference._attribute_ttv(
            visible,
            measure,
            limit,
            1.3,
            0.0,
            0.5,
            alternative_gap_limit=alternative_gap,
            anchors=(),
            model_limit=24,
            bic_temperature=0.08,
            family_floor=0.0,
            family_temperature=0.25,
            between_family_weight=4.0,
        )
        if kind == "constant_forecast" and not result.get("abstain"):
            result["next_offset_days"] = 0.0
        return result
    return candidate


def _cached_schedule(worlds, fractions):
    records = []
    for world in worlds:
        observation = evaluator._observation(world)
        ids = []
        x = list(map(float, observation["transit_numbers"]))
        y = list(map(float, observation["timing_offsets_days"]))
        for number in _anchors(observation, fractions):
            row = evaluator._experiment(world, number)
            ids.append(row["query_id"])
            x.append(float(number))
            y.append(float(row["timing_offset_days"]))
        model, gap, relative_rms, correlation = reference._diagnostics(
            observation, x, y, refine=True
        )
        alternatives = reference._misspecification_models(observation, x, y)
        alternative_gap = alternatives[0][2][0] - model[2][0]
        records.append((world, observation, ids, model, gap, relative_rms,
                        correlation, alternative_gap))
    return records


def _cached_score(records, limits):
    rms_limit, gap_limit, correlation_limit, alternative_gap_limit = limits
    rows = []
    for (world, observation, ids, model, gap, relative_rms,
         correlation, alternative_gap) in records:
        primary = (relative_rms <= rms_limit and gap >= gap_limit and
                   correlation <= correlation_limit and
                   alternative_gap >= alternative_gap_limit)
        moderate = (relative_rms <= 1.1 and gap >= 2.0 and correlation <= 0.2 and
                    alternative_gap >= 2.0)
        abstain = not (primary or moderate)
        submission = {"abstain": True} if abstain else {
            "abstain": False,
            "mechanism": model[0],
            "period": model[1],
            "pred": reference._predict(
                model[2], float(observation["forecast_transit_number"])
            ),
            "confidence": min(0.95, 0.5 + gap / 20.0),
            "ids": ids,
        }
        score, false_discovery = evaluator._score(world, submission)
        supported = world["kind"] in evaluator.MECHANISMS
        rows.append({
            "score": score,
            "design": evaluator._design_score(world, submission),
            "fd": false_discovery,
            "abstain": abstain,
            "supported": supported,
            "correct": supported and not abstain and model[0] == world["kind"],
        })
    return evaluator._aggregate(rows)["combined_score"]


def scan_fixed_schedule_family():
    caches = {fractions: _cached_schedule(evaluator.development_worlds(), fractions)
              for fractions in FRACTION_SCHEDULES}
    best = None
    for fractions, limits in itertools.product(
        FRACTION_SCHEDULES,
        itertools.product(RMS_LIMITS, GAP_LIMITS, CORRELATION_LIMITS,
                          ALTERNATIVE_GAP_LIMITS),
    ):
        score = _cached_score(caches[fractions], limits)
        row = (score, fractions, *limits)
        if best is None or score > best[0]:
            best = row
    result = evaluator.evaluate(fitted_policy(*best[1:]))
    if result["combined_score"] != best[0]:
        raise AssertionError("cached and direct fixed-schedule scores differ")
    return best, result


def main():
    best, fixed = scan_fixed_schedule_family()
    count = (len(FRACTION_SCHEDULES) * len(RMS_LIMITS) * len(GAP_LIMITS) *
             len(CORRELATION_LIMITS) * len(ALTERNATIVE_GAP_LIMITS))
    print("fixed_schedule_count", count)
    print("fixed_schedule_best", best)
    print("fixed_schedule_scores", fixed["combined_score"], fixed["robustness_score"])
    result = evaluator.evaluate(reference.attribute_ttv)
    print("reference", result["combined_score"], result["robustness_score"])
    for name in ("three_followups", "no_activity_model", "constant_forecast",
                 "no_out_of_family_evidence"):
        result = evaluator.evaluate(reference_ablation(name))
        print(name, result["combined_score"], result["robustness_score"])


if __name__ == "__main__":
    main()

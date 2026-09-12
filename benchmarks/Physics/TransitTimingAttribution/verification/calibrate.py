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


SCHEDULES = (
    (12, 24, 42, 59),
    (13, 26, 43, 59),
    (14, 28, 45, 59),
    (15, 30, 47, 59),
    (16, 32, 49, 59),
    # Neighbours of the reference's late-model-discrimination cadence.  These are kept in
    # the development-selected regression grid because moving one observation was the issue
    # reported during PR review.
    (16, 32, 48, 59),
    (16, 32, 50, 59),
    (17, 34, 51, 59),
    (18, 36, 53, 59),
    (20, 38, 55, 59),
)


def fitted_policy(schedule, rms_limit, gap_limit, correlation_limit):
    def candidate(observation, measure, budget_units):
        ids=[]; extra_x=[]; extra_y=[]
        for number in schedule[:int(budget_units)]:
            row=measure(number)
            ids.append(row["query_id"]); extra_x.append(float(number))
            extra_y.append(float(row["timing_offset_days"]))
        if len(ids)<2:
            return {"abstain":True}
        x=list(map(float,observation["transit_numbers"]))+extra_x
        y=list(map(float,observation["timing_offsets_days"]))+extra_y
        best,gap,relative_rms,correlation=reference._diagnostics(observation,x,y)
        if relative_rms>rms_limit or gap<gap_limit or correlation>correlation_limit:
            return {"abstain":True}
        return {"mechanism":best[0],"period":best[1],
                "next_offset_days":reference._predict(best[2],float(observation["forecast_transit_number"])),
                "confidence":0.8,"evidence_query_ids":ids,"abstain":False}
    return candidate


def reference_ablation(kind):
    def candidate(observation,measure,budget_units):
        visible=dict(observation)
        if kind=="no_activity_model":
            visible["activity_period_grid"]=[]
        limit=2 if kind=="half_budget" else int(budget_units)
        if kind=="never_refuse":
            result=reference._attribute_ttv(visible,measure,limit,99.0,-99.0,99.0)
        elif kind=="legacy_active_posterior":
            result=reference._attribute_ttv(visible,measure,limit,1.0,6.0,0.8,
                                            model_limit=18,bic_temperature=0.05)
        elif kind=="no_misspecification_rescue":
            result=reference._attribute_ttv(visible,measure,limit,1.0,6.0,0.8,
                                            rescue_gap=1e9)
        else:
            result=reference._attribute_ttv(visible,measure,limit,1.0,6.0,0.8)
        if kind=="constant_forecast" and not result.get("abstain"):
            result["next_offset_days"]=0.0
        return result
    return candidate


def _cached_schedule(worlds,schedule):
    records=[]
    for world in worlds:
        observation=evaluator._observation(world)
        ids=[]; extra_x=[]; extra_y=[]
        for number in schedule[:world["budget"]]:
            row=evaluator._experiment(world,number)
            ids.append(row["query_id"]); extra_x.append(float(number))
            extra_y.append(float(row["timing_offset_days"]))
        x=list(map(float,observation["transit_numbers"]))+extra_x
        y=list(map(float,observation["timing_offsets_days"]))+extra_y
        best,gap,relative_rms,correlation=reference._diagnostics(observation,x,y)
        claim={"abstain":False,"mechanism":best[0],"period":best[1],
               "pred":reference._predict(best[2],float(observation["forecast_transit_number"])),
               "confidence":0.8,"ids":ids}
        records.append((world,claim,(relative_rms,gap,correlation)))
    return records


def _cached_score(records,limits):
    rows=[]
    for world,claim,values in records:
        abstain=any(value>limit if index!=1 else value<limit
                    for index,(value,limit) in enumerate(zip(values,limits)))
        submission={"abstain":True} if abstain else claim
        score,fd=evaluator._score(world,submission)
        supported=world["kind"] in evaluator.MECHANISMS
        rows.append({"score":score,"fd":fd,"abstain":abstain,"supported":supported,
                     "correct":supported and not abstain and claim["mechanism"]==world["kind"]})
    return evaluator._aggregate(rows)["combined_score"]


def _scan(dev_cache,held_cache,rms_values,gap_values,correlation_values):
    best=None
    for schedule,rms_limit,gap_limit,correlation_limit in itertools.product(
            SCHEDULES,rms_values,gap_values,correlation_values):
        limits=(rms_limit,gap_limit,correlation_limit)
        dev=_cached_score(dev_cache[schedule],limits)
        # Preserve development-only selection and the first maximum on ties.
        row=(dev,(schedule,rms_limit,gap_limit,correlation_limit))
        if best is None or row[0]>best[0]:
            best=row
    dev,parameters=best
    held=_cached_score(held_cache[parameters[0]],parameters[1:])
    result=evaluator.evaluate(fitted_policy(*parameters))
    expected=(dev,dev,held)
    if (result["development_score"],result["combined_score"],result["robustness_score"]) != expected:
        raise AssertionError("cached and evaluator shortcut scores differ")
    return (*expected,parameters)


def main():
    dev_cache={schedule:_cached_schedule(evaluator.development_worlds(),schedule)
               for schedule in SCHEDULES}
    held_cache={schedule:_cached_schedule(evaluator.sealed_worlds(),schedule)
                for schedule in SCHEDULES}
    families={
        "family_a":((0.8,1.0,1.2,1.4,1.6),(0.0,3.0,6.0,9.0,12.0),(0.35,0.50,0.65,0.80)),
        "family_b":((0.8,1.0,1.2,1.4,1.6),(0.0,),(0.35,0.50,0.65,0.80)),
        "family_c":((99.0,),(0.0,3.0,6.0,9.0,12.0),(0.35,0.50,0.65,0.80)),
    }
    for name,axes in families.items():
        count=len(SCHEDULES)*len(axes[0])*len(axes[1])*len(axes[2])
        print(name+"_count",count)
        print(name+"_best",_scan(dev_cache,held_cache,*axes))
    reference_result=evaluator.evaluate(reference.attribute_ttv)
    print("reference",reference_result["combined_score"],reference_result["robustness_score"])
    for name in ("half_budget","no_activity_model","constant_forecast","legacy_active_posterior",
                 "no_misspecification_rescue","never_refuse"):
        result=evaluator.evaluate(reference_ablation(name))
        print(name,result["combined_score"],result["robustness_score"])


if __name__ == "__main__":
    main()

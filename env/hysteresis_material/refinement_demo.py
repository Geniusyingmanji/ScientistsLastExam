"""Bounded public-data revision after a prospective material counterexample.

This authored development policy is not a model benchmark. Its second test is
chosen from a fixed grid using only the old and revised predictions. Failed
forecasts and source-fit residuals remain in the operator evidence package.
"""
import argparse
from collections import defaultdict
import copy
import json
from pathlib import Path

import numpy as np
from scipy.optimize import least_squares

from .prospective_demo import (_cubic, comparison_request, fit_candidates,
                              predictor_code, source_specs)


def revise_cubic(records, original):
    """Use public source and counterexample measurements, never private truth."""
    grouped = defaultdict(list)
    specifications = {}
    for record in records:
        spec = record["spec"]
        if spec["preparation"] or len(spec["protocol"]) != 1:
            raise ValueError("reference revision only accepts constant-field source records")
        key = json.dumps(spec, sort_keys=True, allow_nan=False)
        grouped[key].append(np.asarray(record["observation"]["values"], dtype=float)[:, 0])
        specifications[key] = spec
    keys = sorted(grouped)
    times = sorted({t for s in specifications.values() for t in s["times"]})
    grid_index = {t: i for i, t in enumerate(times)}
    reset_values = defaultdict(list)
    for record in records:
        if record["observation"]["axis"][0] != 0.:
            raise ValueError("reference revision needs observed preparation readout")
        reset_values[record["spec"]["reset"]].append(record["observation"]["values"][0][0])
    reset = {key: float(np.mean(values)) for key, values in reset_values.items()}
    if set(reset) != {"negative", "positive"}:
        raise ValueError("reference revision needs both reset histories")
    initial = np.array([reset[specifications[key]["reset"]] for key in keys])
    fields = np.array([specifications[key]["protocol"][0]["field"] for key in keys])
    means = [np.mean(grouped[key], axis=0) for key in keys]
    positions = [[grid_index[t] for t in specifications[key]["times"][1:]] for key in keys]
    weights = [np.sqrt(len(grouped[key])) for key in keys]

    def residual(parameters):
        predicted = _cubic(parameters, initial, fields, times)
        return np.concatenate([(predicted[i, positions[i]] - means[i][1:]) * weights[i]
                               for i in range(len(keys))])

    # The old positive-linear prior is relaxed: the revised class may have one
    # stable state. This is explicit and only happens after recorded refutation.
    fitted = least_squares(residual, original["parameters"],
                           bounds=([-.2, -.08, -.4, .003, .001], [.2, .08, .4, .4, .4]),
                           max_nfev=180, ftol=1e-8, xtol=1e-8, gtol=1e-8)
    return {"kind": "cubic_memory", "parameters": fitted.x.tolist(), "reset_response": reset,
            "evidence_ids": [record["id"] for record in records],
            "optimizer_success": bool(fitted.success), "optimizer_evaluations": int(fitted.nfev),
            "weighted_residual_rmse": float(np.sqrt(np.mean(residual(fitted.x) ** 2))),
            "source_groups": len(keys),
            "prior": "revised cubic drift: linear coefficient may be negative or positive; fitted only to public source and recorded counterexample"}


def _contrast(model, field, horizon):
    initial = np.array([model["reset_response"][key] for key in ("negative", "positive")])
    values = _cubic(model["parameters"], initial, np.array([field, field]), [0., horizon])
    return float(values[1, -1] - values[0, -1])


def choose_revision_test(original, revised):
    """Finite model-only design search; no callback or World access is accepted."""
    candidates = []
    for field in (-.65, -.55, -.45, -.35, -.25, -.15, -.05, .05, .15, .25, .35, .45, .55, .65):
        for horizon in (60., 180., 600.):
            before, after = _contrast(original, field, horizon), _contrast(revised, field, horizon)
            candidates.append({"field": field, "horizon": horizon,
                               "original_contrast": before, "revised_contrast": after,
                               "prediction_separation": abs(after - before)})
    # Stable, specified ordering handles ties without choosing by target outcome.
    chosen = max(candidates, key=lambda item: item["prediction_separation"])
    return {"selection": copy.deepcopy(chosen), "grid": candidates,
            "selection_rule": "largest absolute old-versus-revised contrast over a fixed 42-design grid; no target data"}


def revision_request(first_request, first_response, revised, design):
    old = next(copy.deepcopy(rival) for rival in first_request["rivals"] if rival["id"] == "cubic_memory")
    selected = design["selection"]
    request = copy.deepcopy(first_request)
    request.update(profile="regime_transfer", revision_of=first_response["test_id"],
                   change_note="Retain the refuted cubic program unchanged. Fit a new cubic account to public source plus the counterexample, allowing a negative linear coefficient, and test it under a previously unobserved constant field.",
                   scope="Transfer of the revised response law to the selected new field and hold duration; numerical agreement does not establish a unique microscopic mechanism.")
    request["rivals"] = [old, {"id": "cubic_revision", "predictor_code": predictor_code(revised),
                               "rationale": revised["prior"], "evidence_ids": revised["evidence_ids"],
                               "tolerance": .07}]
    for experiment in request["experiments"]:
        experiment["spec"]["protocol"][0]["field"] = selected["field"]
        experiment["spec"]["times"] = [0., selected["horizon"]]
    return request


def run_demo(seed, output):
    from env.prospective_runner import ProspectiveTask, verify_directory
    output = Path(output)
    task = ProspectiveTask("hysteresis_material", seed, output,
                           limits={"max_tests": 2, "experiments": 72,
                                   "predictor_calls": 16, "wall_seconds": 900})
    source = [task.observe_source(spec) for spec in source_specs()]
    initial = fit_candidates(source)
    first_request = comparison_request(initial)
    first = task.preregister(first_request)
    revision = None
    if "cubic_memory" in first["result"]["counterexample_candidate_ids"]:
        revised = revise_cubic(task.public_records(), initial["cubic_memory"])
        design = choose_revision_test(initial["cubic_memory"], revised)
        second_request = revision_request(first_request, first, revised, design)
        # Save fit and the full model-only search before the host sees the plan.
        (output / "revision-design.json").write_text(json.dumps(
            {"revised_model": revised, "design": design}, indent=2, allow_nan=False) + "\n")
        second = task.preregister(second_request)
        revision = {"fit": revised, "design": design, "prospective": second}
    report = task.finish()
    return {"kind": "authored_development_refinement_policy_not_model_evaluation",
            "initial_fits": initial, "first_test": first, "revision": revision,
            "report": report, "replay": verify_directory(output),
            "interpretation": "All initial counterexamples remain. New data may again refute both programs or remain inconclusive. No tuning of confirmation tolerance, replication count or noise keys occurs."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = run_demo(args.seed, args.output)
    (Path(args.output) / "reference-result.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"status": result["report"]["status"],
                      "first_outcome": result["first_test"]["result"]["outcome"],
                      "revision_outcome": result["revision"]["prospective"]["result"]["outcome"] if result["revision"] else None,
                      "replayed_tests": result["replay"]["replayed_tests"]}))


if __name__ == "__main__":
    main()

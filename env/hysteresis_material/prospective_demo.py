"""Public-data reference investigator for a prospective material experiment.

This is an authored calibration policy, not a GPT result or discovery score.
It fits two deliberately different scientific priors on same-sign high-field
responses, then freezes a contrast of opposite resets at a new zero-field hold.
Only the trusted task host constructs a World; fitting receives public records.
"""
import argparse
import json
from pathlib import Path

import numpy as np
from scipy.integrate import solve_ivp
from scipy.optimize import least_squares


SOURCE_TIMES = [0., .5, 1., 2., 3., 5., 8., 12., 20., 40., 80.]


def source_specs():
    """Stay on the prepared high-field branch; reserve zero field for testing."""
    return [{"reset": reset, "preparation": [],
             "protocol": [{"time": 0., "field": sign * magnitude}],
             "times": list(SOURCE_TIMES)}
            for reset, sign in (("negative", -1), ("positive", 1))
            for magnitude in (1., 1.15, 1.3, 1.5)]


def _source_arrays(records):
    if len(records) != 8:
        raise ValueError("reference design requires its eight source records")
    expected = source_specs()
    values = []
    for record, spec in zip(records, expected):
        # The operator canonicalizes numerical types; only public values enter.
        if record["spec"] != spec:
            raise ValueError("source records do not match the fixed design")
        obs = record["observation"]
        if obs["axis"] != SOURCE_TIMES or obs["channels"] != ["response"]:
            raise ValueError("source observation contract mismatch")
        value = np.asarray(obs["values"], dtype=float)
        if value.shape != (len(SOURCE_TIMES), 1) or not np.isfinite(value).all():
            raise ValueError("invalid source observations")
        values.append(value[:, 0])
    array = np.asarray(values)
    reset = {"negative": float(array[:4, 0].mean()),
             "positive": float(array[4:, 0].mean())}
    initial = np.array([reset[r["spec"]["reset"]] for r in records])
    fields = np.array([r["spec"]["protocol"][0]["field"] for r in records])
    return array, initial, fields, reset


def _relaxation(parameters, initial, fields, times):
    offset, amplitude, slope, bias, tau = parameters
    target = offset + amplitude * np.tanh(slope * fields + bias)
    return target[:, None] + (initial - target)[:, None] * np.exp(-np.asarray(times)[None, :] / tau)


def _cubic(parameters, initial, fields, times):
    offset, drift_bias, linear, cubic, forcing = parameters
    def rhs(_time, value):
        centered = value - offset
        return drift_bias + linear * centered - cubic * centered ** 3 + forcing * fields
    solution = solve_ivp(rhs, [0., times[-1]], initial, t_eval=times,
                         method="LSODA", rtol=2e-6, atol=2e-8)
    if not solution.success or solution.y.shape != (len(initial), len(times)):
        raise ValueError("reference fit integration failed")
    return solution.y


def fit_candidates(records):
    """Fit both candidates to identical public observations; never access truth.

    Positivity of the cubic linear coefficient is a competing bistability prior,
    not a parameter inferred by inspecting the operator's hidden class. Source
    residuals are retained, so an already implausible rival cannot be concealed.
    """
    observations, initial, fields, reset = _source_arrays(records)
    definitions = {
        "relaxation": (_relaxation, [0., 1., 1.2, 0., 9.],
                       [-.2, .4, .2, -.4, 1.], [.2, 2., 4., .4, 60.]),
        "cubic_memory": (_cubic, [0., 0., .09, .09, .07],
                         [-.2, -.04, .001, .003, .001], [.2, .04, .4, .4, .4]),
    }
    result = {}
    for name, (simulator, start, low, high) in definitions.items():
        def residual(parameters):
            return (simulator(parameters, initial, fields, SOURCE_TIMES)[:, 1:] - observations[:, 1:]).ravel()
        fit = least_squares(residual, start, bounds=(low, high), max_nfev=160,
                            ftol=1e-8, xtol=1e-8, gtol=1e-8)
        residuals = residual(fit.x).reshape(len(records), -1)
        result[name] = {"kind": name, "parameters": fit.x.tolist(), "reset_response": reset,
                        "source_rmse": float(np.sqrt(np.mean(residuals ** 2))),
                        "source_rmse_by_record": np.sqrt(np.mean(residuals ** 2, axis=1)).tolist(),
                        "optimizer_success": bool(fit.success), "optimizer_evaluations": int(fit.nfev),
                        "evidence_ids": [r["id"] for r in records],
                        "prior": "authored saturating one-state relaxation" if name == "relaxation"
                                 else "authored cubic drift with positive linear coefficient"}
    return result


_PREDICTOR = '''import numpy as np
from scipy.integrate import solve_ivp
def predict(spec):
    p = MODEL["parameters"]
    y = MODEL["reset_response"][spec["reset"]]
    def flow(duration, field_at, value):
        if duration == 0: return value
        def rhs(t, state):
            h = field_at(t)
            if MODEL["kind"] == "relaxation":
                offset, amplitude, slope, bias, tau = p
                return [(offset + amplitude*np.tanh(slope*h+bias)-state[0])/tau]
            offset, drift_bias, linear, cubic, forcing = p
            z = state[0]-offset
            return [drift_bias+linear*z-cubic*z*z*z+forcing*h]
        answer = solve_ivp(rhs,[0.,duration],[value],method="LSODA",rtol=1e-7,atol=1e-9)
        if not answer.success: raise ValueError("integration failed")
        return float(answer.y[0,-1])
    for step in spec["preparation"]:
        y = flow(step["duration"],lambda t,h=step["field"]:h,y)
    knots = spec["protocol"]
    current = 0.
    output = []
    for target in spec["times"]:
        cuts = [k["time"] for k in knots if current < k["time"] < target]+[target]
        for end in cuts:
            start = current
            def field_at(dt):
                t = start+dt
                return float(np.interp(t,[k["time"] for k in knots],[k["field"] for k in knots]))
            y = flow(end-current,field_at,y)
            current = end
        output.append([y])
    return output
'''


def predictor_code(model):
    # JSON data is parsed, never interpolated as Python expressions.
    payload = {key: model[key] for key in ("kind", "parameters", "reset_response")}
    return "import json\nMODEL = json.loads(" + repr(json.dumps(payload, allow_nan=False)) + ")\n" + _PREDICTOR


def comparison_request(models):
    experiments = [{"id": reset, "role": "target",
                    "spec": {"reset": reset, "preparation": [],
                             "protocol": [{"time": 0., "field": 0.}],
                             "times": [0., 300.]}}
                   for reset in ("negative", "positive")]
    return {"profile": "mechanism_discrimination",
            "scope": "Opposite-reset response contrast after a previously unobserved 300 s zero-field hold; this does not establish infinite-time memory.",
            "rivals": [{"id": name, "predictor_code": predictor_code(model),
                        "rationale": model["prior"] + "; source RMSE=" + str(model["source_rmse"]),
                        "evidence_ids": model["evidence_ids"], "tolerance": .07}
                       for name, model in models.items()],
            "experiments": experiments,
            "readout": [{"experiment_id": "positive", "row": 1, "channel": "response", "weight": 1.},
                        {"experiment_id": "negative", "row": 1, "channel": "response", "weight": -1.}],
            "replicates": 16, "revision_of": None, "change_note": ""}


def run_demo(seed, output):
    from env.prospective_runner import ProspectiveTask, verify_directory
    output = Path(output)
    task = ProspectiveTask("hysteresis_material", seed, output,
                           limits={"max_tests": 1, "experiments": 40,
                                   "predictor_calls": 8, "wall_seconds": 900})
    records = [task.observe_source(spec) for spec in source_specs()]
    models = fit_candidates(records)
    (output / "reference-fit.json").write_text(json.dumps(models, indent=2, allow_nan=False) + "\n")
    answer = task.preregister(comparison_request(models))
    report = task.finish()
    checked = verify_directory(output)
    return {"kind": "authored_reference_policy_not_model_evaluation", "public_source_records": len(records),
            "source_fit": {k: {f: v[f] for f in ("source_rmse", "source_rmse_by_record", "optimizer_success")} for k,v in models.items()},
            "prospective": answer, "report": report, "replay": checked,
            "limits": "The two model families are authored scientific priors. A poor source fit weakens rival plausibility. Prospective discrimination does not automatically certify D3 or D4."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, required=True, help="operator-only development instance")
    parser.add_argument("--output", required=True, help="new private task directory")
    args = parser.parse_args()
    result = run_demo(args.seed, args.output)
    (Path(args.output) / "reference-result.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"kind": result["kind"], "source_fit": result["source_fit"],
                      "outcome": result["prospective"], "replay": result["replay"]}))


if __name__ == "__main__":
    main()

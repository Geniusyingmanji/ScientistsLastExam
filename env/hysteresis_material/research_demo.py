"""Zero-API authored reference through the real material research runner.

The policy knows two candidate families. It is an interface/runtime example, not
a GPT evaluation or autonomous discovery. Fitting occurs only inside the real
IsolatedAnalysis worker; this module supplies its self-contained source text.
"""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path


REFERENCE_ID = "scripted-material-reference-0.1"
DEVELOPMENT_SEEDS = (7, 46, 1439, 8743)
SOURCE_TIMES = [0., .5, 1., 2., 3., 5., 8., 12., 20., 40., 80.]
RIVALS = ("relaxation", "cubic_memory")
DRIVER_LIMITS = {"rounds": 4, "analysis_seconds": 90., "wall_seconds": 600.,
                 "max_experiments_per_turn": 8}
SCIENCE_LIMITS = {"actions": 12, "max_tests": 1, "experiments": 24,
                  "experiment_units": 2000, "predictor_calls": 8,
                  "predictor_seconds": 120., "predictor_seconds_per_call": 15.,
                  "simulation_seconds": 120., "simulation_seconds_per_call": 15.,
                  "wall_seconds": 600., "family_alpha": .05}


def source_specs():
    return [{"reset": reset, "preparation": [],
             "protocol": [{"time": 0., "field": sign * magnitude}],
             "times": list(SOURCE_TIMES)}
            for reset, sign in (("negative", -1), ("positive", 1))
            for magnitude in (1., 1.15, 1.3, 1.5)]


# MODEL is restored by the existing snapshot binder in a fresh predictor
# sandbox. There is no parameter assignment or operator import in this source.
PREDICTOR_CODE = '''import numpy as np
from scipy.integrate import solve_ivp
def predict(spec):
    p = MODEL["parameters"]
    y = MODEL["reset_response"][spec["reset"]]
    def flow(duration, field_at, value):
        if duration == 0.: return value
        def rhs(t, state):
            h = field_at(t)
            if MODEL["kind"] == "relaxation":
                offset, amplitude, slope, bias, tau = p
                return [(offset + amplitude*np.tanh(slope*h+bias)-state[0])/tau]
            offset, drift_bias, linear, cubic, forcing = p
            z = state[0]-offset
            return [drift_bias+linear*z-cubic*z*z*z+forcing*h]
        answer = solve_ivp(rhs,[0.,duration],[value],method="LSODA",rtol=1e-7,atol=1e-9)
        if not answer.success or not np.isfinite(answer.y).all():
            raise ValueError("prediction integration failed")
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
                return float(np.interp(start+dt,[k["time"] for k in knots],
                                       [k["field"] for k in knots]))
            y = flow(end-current,field_at,y)
            current = end
        output.append([y])
    return output
'''


_ANALYSIS_BODY = '''
import numpy as np
from scipy.integrate import solve_ivp
from scipy.optimize import least_squares

times = [0., .5, 1., 2., 3., 5., 8., 12., 20., 40., 80.]
specs = [{"reset": reset, "preparation": [],
          "protocol": [{"time": 0., "field": sign*magnitude}], "times": times}
         for reset, sign in (("negative", -1), ("positive", 1))
         for magnitude in (1., 1.15, 1.3, 1.5)]
if len(records) != 8:
    raise ValueError("expected exactly eight source records before testing")
observations, evidence_ids = [], []
for record, spec in zip(records, specs):
    if record["spec"] != spec:
        raise ValueError("source design mismatch")
    observation = record["observation"]
    if observation["axis"] != times or observation["channels"] != ["response"]:
        raise ValueError("source observation contract mismatch")
    value = np.asarray(observation["values"], dtype=float)
    if value.shape != (len(times), 1) or not np.isfinite(value).all():
        raise ValueError("invalid source observations")
    observations.append(value[:, 0])
    evidence_ids.append(record["id"])
if len(set(evidence_ids)) != 8:
    raise ValueError("source evidence IDs must be unique")
observations = np.asarray(observations)
reset_response = {"negative": float(observations[:4,0].mean()),
                  "positive": float(observations[4:,0].mean())}
initial = np.array([reset_response[spec["reset"]] for spec in specs])
fields = np.array([spec["protocol"][0]["field"] for spec in specs])

def relaxation(p):
    offset, amplitude, slope, bias, tau = p
    target = offset+amplitude*np.tanh(slope*fields+bias)
    return target[:,None]+(initial-target)[:,None]*np.exp(-np.array(times)[None,:]/tau)

def cubic_memory(p):
    offset, drift_bias, linear, cubic, forcing = p
    def rhs(_time, values):
        z = values-offset
        return drift_bias+linear*z-cubic*z**3+forcing*fields
    solution = solve_ivp(rhs,[0.,times[-1]],initial,t_eval=times,
                         method="LSODA",rtol=2e-6,atol=2e-8)
    if (not solution.success or solution.y.shape != observations.shape
            or not np.isfinite(solution.y).all()):
        raise ValueError("source integration failed")
    return solution.y

definitions = [
    ("relaxation", relaxation, [0.,1.,1.2,0.,9.],
     [-.2,.4,.2,-.4,1.],[.2,2.,4.,.4,60.],
     "authored saturating one-state relaxation"),
    ("cubic_memory", cubic_memory, [0.,0.,.09,.09,.07],
     [-.2,-.04,.001,.003,.001],[.2,.04,.4,.4,.4],
     "authored cubic drift with positive linear coefficient")]
models, failures = {}, {}
for name, simulator, start, low, high, prior in definitions:
    calls = [0]
    def residual(parameters):
        calls[0] += 1
        if calls[0] > 500:
            raise ValueError("finite residual evaluation allowance exhausted")
        return (simulator(parameters)[:,1:]-observations[:,1:]).ravel()
    try:
        fitted = least_squares(residual,start,bounds=(low,high),max_nfev=80,
                               ftol=1e-8,xtol=1e-8,gtol=1e-8)
        errors = residual(fitted.x).reshape(8,-1)
        diagnostic = {"source_rmse": float(np.sqrt(np.mean(errors**2))),
                      "source_rmse_by_record": np.sqrt(np.mean(errors**2,axis=1)).tolist(),
                      "optimizer_success": bool(fitted.success),
                      "optimizer_status": int(fitted.status),
                      "optimizer_evaluations": int(fitted.nfev),
                      "residual_calls": calls[0], "evidence_ids": evidence_ids,
                      "prior": prior}
        parameters = {"kind": name, "parameters": fitted.x.tolist(),
                      "reset_response": reset_response, "diagnostics": diagnostic}
        receipt = save_model(name,"v1",parameters,PREDICTOR_CODE)
        models[name] = dict(diagnostic,model_snapshot={key: receipt[key]
                            for key in ("name","version","sha256")})
    except Exception as error:
        failures[name] = {"error": type(error).__name__, "message": str(error)[:300],
                          "residual_calls": calls[0]}
result = {"identity": "authored_family_prior_not_autonomous_discovery",
          "source_records": len(records), "models": models, "failures": failures,
          "fit_scope": "Two fitted point predictors; no whole-family falsification."}
'''

# JSON string serialization embeds authored source as data, never repr/eval.
ANALYSIS_CODE = "PREDICTOR_CODE = " + json.dumps(PREDICTOR_CODE, ensure_ascii=True) + "\n" + _ANALYSIS_BODY


def _analysis_result(prompt):
    for entry in reversed(prompt["recent_results"]):
        if "analysis" in entry:
            analysis = entry["analysis"]
            if analysis.get("ok") is not True:
                raise ValueError("analysis failed; no fallback or replacement fit")
            result = analysis["result"]
            if result["failures"] or set(result["models"]) != set(RIVALS):
                raise ValueError("both frozen rival fits are required")
            return result
    raise ValueError("no public analysis result")


def comparison_request(prompt):
    fit = _analysis_result(prompt)
    catalog = {(item["name"], item["version"]): item for item in prompt["model_snapshots"]}
    rivals = []
    for name in RIVALS:
        model = fit["models"][name]
        reference = model["model_snapshot"]
        stored = catalog[(name, "v1")]
        if reference != {key: stored[key] for key in ("name", "version", "sha256")}:
            raise ValueError("analysis receipt differs from immutable snapshot catalog")
        rivals.append({"id": name, "model_snapshot": deepcopy(reference),
                       "rationale": model["prior"] + "; source RMSE=" + str(model["source_rmse"])
                       + "; optimizer_success=" + str(model["optimizer_success"])
                       + ". Authored prior and fitted point predictor only; source misfit weakens plausibility.",
                       "evidence_ids": list(model["evidence_ids"]), "tolerance": .07})
    return {"profile": "mechanism_discrimination",
            "scope": "Opposite-reset response contrast after a new 300 s zero-field hold; neither infinite-time memory nor whole-family identification.",
            "rivals": rivals,
            "experiments": [{"id": reset, "role": "target",
                             "spec": {"reset": reset, "preparation": [],
                                      "protocol": [{"time": 0., "field": 0.}], "times": [0., 300.]}}
                            for reset in ("negative", "positive")],
            "readout": [{"experiment_id": "positive", "row": 1, "channel": "response", "weight": 1.},
                        {"experiment_id": "negative", "row": 1, "channel": "response", "weight": -1.}],
            "replicates": 8, "revision_of": None, "change_note": ""}


def _finish(prompt):
    tests = prompt["scientific_task"]["results"]
    if len(tests) != 1:
        raise ValueError("finish requires exactly one actual completed test")
    result = tests[0]["result"]
    measured = {key: result[key] for key in ("mean_readout", "confidence_interval", "candidates")}
    return {"explanation": (
        "Authored reference interface demonstration. The independently observed 300 s opposite-reset "
        "zero-field contrast produced the host outcome " + result["outcome"] + ". "
        "The observed scaled contrast and frozen point predictions were "
        + json.dumps(measured, ensure_ascii=True, allow_nan=False) + ". "
        "Source-fit errors and optimizer status remain in the immutable fits and analysis record; "
        "an already poor source fit weakens rival plausibility. This compares two fitted point "
        "predictors under known author-supplied family priors. Rejecting either program does not "
        "falsify its entire mechanism family. This finite horizon does not establish infinite-time "
        "memory, unique mechanism identification, autonomous discovery, or D3/D4."),
        "evidence_ids": [item["id"] for item in prompt["observation_catalog"]],
        "test_ids": [tests[0]["test_id"]]}


class ScriptedReferenceClient:
    """Trusted deterministic policy; receives only runner prompts and identity.

    This host-side client is auditable reference code, not a network sandbox.
    It receives no manifest, World, seed or private results. The sole directory
    capability is its own raw public transport log.
    """
    client_kind = "scripted_reference"
    reference_id = REFERENCE_ID

    def __init__(self, transport_directory, reference_source_sha256):
        self.reference_source_sha256 = reference_source_sha256
        self.directory = Path(transport_directory)
        self.calls = 0
        self.last_usage, self.last_response_metadata, self.last_stop_reason = None, {}, None

    def complete(self, encoded, *, system):
        from env.prospective_runner import _atomic_json
        prompt = json.loads(encoded)
        number = self.calls + 1
        if number > 4 or prompt["round"] != number:
            raise ValueError("scripted policy has exactly four ordered actions; no retry")
        _atomic_json(self.directory / ("%02d-request.json" % number),
                     {"kind": self.client_kind, "reference_id": self.reference_id,
                      "prompt": prompt, "system": system})
        self.calls = number
        self.last_usage, self.last_response_metadata = None, {}
        self.last_stop_reason = "reference_action"
        if number == 1:
            action = {"note": "Fixed authored source design; reserve zero-field history contrast for fresh testing.",
                      "experiments": source_specs()}
        elif number == 2:
            action = {"note": "Fit two authored priors using public source records inside isolated analysis and save immutable v1 snapshots.",
                      "analyze": {"code": ANALYSIS_CODE}}
        elif number == 3:
            action = {"note": "Freeze exact snapshot receipts before independent target observations; retain imperfect source fits.",
                      "preregister": comparison_request(prompt)}
        else:
            action = {"note": "Report the actual scoped comparison, including negative or inconclusive results.",
                      "finish": _finish(prompt)}
        _atomic_json(self.directory / ("%02d-response.json" % number), action)
        return json.dumps(action, ensure_ascii=True, allow_nan=False)


def reference_source_sha256():
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def freeze_manifest(seed, episode_id):
    from env.research_runner import create_reference_manifest
    if type(seed) is not int or seed not in DEVELOPMENT_SEEDS:
        raise ValueError("reference demo is restricted to the four declared development seeds")
    return create_reference_manifest(episode_id, "hysteresis_material", seed,
                                     reference_id=REFERENCE_ID,
                                     reference_source_sha256=reference_source_sha256(),
                                     profile="mechanism_discrimination", limits=DRIVER_LIMITS,
                                     science_limits=SCIENCE_LIMITS)


def _public_summary(report, replay):
    scientific = report.get("scientific_task") or {}
    source_fit, analysis_failures = {}, []
    for turn in report.get("history", []):
        analysis = turn.get("analysis", {})
        if analysis.get("ok") is False:
            analysis_failures.append({"analysis_error": analysis.get("error", "unknown")})
        if analysis.get("ok") is True and isinstance(analysis.get("result"), dict):
            for name, failure in analysis["result"].get("failures", {}).items():
                analysis_failures.append({"candidate": name, "error": failure["error"],
                                          "residual_calls": failure["residual_calls"]})
            for name, model in analysis["result"].get("models", {}).items():
                source_fit[name] = {key: model[key] for key in (
                    "source_rmse", "source_rmse_by_record", "optimizer_success", "optimizer_status",
                    "optimizer_evaluations", "residual_calls")}
    return {"reference_id": REFERENCE_ID, "client_kind": "scripted_reference",
            "status": report["status"], "stop_reason": report["stop_reason"],
            "infrastructure_failure": report["infrastructure_failure"],
            "usage": report["usage"], "science_usage": scientific.get("usage"),
            "elapsed_seconds": report["elapsed_seconds"], "source_fit": source_fit,
            "analysis_failures": analysis_failures,
            "outcomes": [test["result"]["outcome"] for test in scientific.get("results", [])],
            "receipt_replay": replay, "score": None, "autonomous_discovery": False,
            "mechanism_identified": False, "discovery_depth_certified": False}


def run_frozen(manifest, output):
    """Operator wrapper. There is deliberately no analysis/predictor override."""
    from env.prospective_runner import _atomic_json, verify_directory
    from env.research_runner import run_research
    identity = manifest["reference"]
    if (identity["id"] != REFERENCE_ID or
            identity["source_sha256"] != reference_source_sha256()):
        raise ValueError("reference source changed after freeze")
    expected = freeze_manifest(manifest["private_world_seed"], manifest["episode_id"])
    if manifest != expected:
        raise ValueError("frozen manifest differs from the fixed development reference plan")
    # Capture only the declared code hash. Never pass the manifest to the client.
    reference_hash = identity["source_sha256"]
    report = run_research(manifest, output,
                          lambda directory: ScriptedReferenceClient(directory, reference_hash))
    replay = {"ok": False, "archive_verified": False}
    try:
        checked = verify_directory(Path(output) / "science")
        replay.update(archive_verified=True, replayed_tests=checked["replayed_tests"],
                      receipt_count=checked["receipt_count"])
        scientific = report.get("scientific_task") or {}
        results = [test["result"] for test in scientific["results"]]
        if (checked["replayed_tests"] != len(results) or checked["results"] != results or
                checked["receipt_head"] != scientific["receipt_head"]):
            raise ValueError("replay differs from the driver report")
        if report["status"] == "completed" and (
                scientific.get("status") != "completed" or len(results) != 1):
            raise ValueError("completed reference requires one completed scientific test")
        replay.update(ok=True, completed_report_verified=report["status"] == "completed")
    except Exception as error:
        replay.update(ok=False, completed_report_verified=False, error=type(error).__name__)
    summary = _public_summary(report, replay)
    _atomic_json(Path(output) / "reference-summary-public.json", summary)
    return summary


def main(argv=None):
    from env.prospective_runner import _atomic_json, _atomic_bytes
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", default="7,46,1439,8743", help="declared development subset; no repeats")
    parser.add_argument("--output", required=True, help="new private cohort directory; no reuse/resume")
    args = parser.parse_args(argv)
    seeds = [int(value) for value in args.seeds.split(",")]
    if not seeds or len(seeds) != len(set(seeds)) or any(seed not in DEVELOPMENT_SEEDS for seed in seeds):
        parser.error("select unique declared development seeds: 7,46,1439,8743")
    root = Path(args.output).absolute()
    root.mkdir(mode=0o700, parents=False)
    # Freeze every selected instance before the first source observation.
    manifests = [freeze_manifest(seed, "material-reference-%02d" % (index+1))
                 for index, seed in enumerate(seeds)]
    _atomic_json(root / "plan-private.json", {"reference_id": REFERENCE_ID, "manifests": manifests,
                 "model_api_calls": 0, "maximum_reference_actions": len(seeds)*4,
                 "maximum_observations": len(seeds)*24,
                 "noise": "Distinct host source/confirmation keys; independent noise, not common random numbers."})
    _atomic_bytes(root / "reference-source.py", Path(__file__).read_bytes())
    rows = []
    for index, manifest in enumerate(manifests):
        directory = root / ("instance-%02d" % (index+1))
        try:
            summary = run_frozen(manifest, directory)
        except Exception as error:
            # Preserve partial files, count the planned case, never rerun it.
            summary = {"reference_id": REFERENCE_ID, "status": "operator_wrapper_failed",
                       "error": type(error).__name__, "score": None,
                       "autonomous_discovery": False, "discovery_depth_certified": False}
        rows.append(dict(summary, anonymous_instance=index+1))
        _atomic_json(root / "summary-public.json", {"reference_id": REFERENCE_ID,
                     "planned_instances": len(manifests), "attempted_instances": len(rows),
                     "completed_instances": sum(row["status"] == "completed" for row in rows),
                     "verified_completed_instances": sum(row["status"] == "completed"
                         and row.get("receipt_replay", {}).get("ok") is True for row in rows),
                     "model_api_calls": 0, "rows": rows}, replace=index > 0)
    print(json.dumps({"reference_id": REFERENCE_ID, "planned_instances": len(manifests),
                      "completed_instances": sum(row["status"] == "completed" for row in rows),
                      "verified_completed_instances": sum(row["status"] == "completed"
                          and row.get("receipt_replay", {}).get("ok") is True for row in rows),
                      "statuses": [row["status"] for row in rows], "model_api_calls": 0}))
    return 0 if all(row["status"] == "completed" and row.get("receipt_replay", {}).get("ok")
                    for row in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())

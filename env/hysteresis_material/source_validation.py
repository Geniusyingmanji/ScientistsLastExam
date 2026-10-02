"""Post-hoc source-bias diagnostic for the eight frozen d1 point predictors.

No fitting, model API, target-data selection or mechanism-family assessment.
Production predictions use the existing CandidateProxy isolation boundary.
"""
import argparse
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import secrets
import sys
import time

import numpy as np
from scipy.optimize import brentq
from scipy.stats import ncx2

from env.analysis_api import bind_parameters
from env.hysteresis_material.protocol import validate_spec


PROTOCOL = "material-source-validation-0.1"
REFERENCE_ID = "scripted-material-source-validation-0.1"
EXPECTED_PLAN_SHA256 = "29ec7ce860411369a3c26446ead14518dd5e742342c4a0e07039be6d2e73b6e9"
MODELS = ("relaxation", "cubic_memory")
SEEDS = (7, 46, 1439, 8743)
TIMES = (0., .5, 1., 2., 3., 5., 8., 12., 20., 40., 80.)
SIGMA, REPLICATES, CELLS = .006, 16, 80
FAMILY_ALPHA, MODEL_ALPHA, THRESHOLD = .05, .05 / 8., 1.
PREDICTOR_CALLS, WORLD_CALLS = 128, 512
WALL_SECONDS, WORK_SECONDS, CALL_SECONDS = 1200., 1180., 15.
LAMBDA_CAP = 1e8
FROZEN_RUNTIME_SHA256 = {
    "analysis_api.py": "3962e016af618ad78f6bf0f52b65c89e8579ac5c94330fdb6d9faaf5a1c4ebf0",
    "hysteresis_material/world.py": "089d1a21d3fbcd1767c083201058342255e6ec855999e64e61eaa070d492575a",
    "hysteresis_material/protocol.py": "489c3dd67693598dd3c8aa2567f8c72d1f98643f08abe9cfd4fb086cc6beffdd",
}


class NumericalFailure(RuntimeError):
    pass


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("ascii")


def _digest(value):
    return _sha(_encoded(value))


def _read_json(path):
    def invalid(value):
        raise ValueError("nonfinite JSON constant")
    return json.loads(Path(path).read_text(), parse_constant=invalid)


def _write_new(path, value):
    # Existing operator primitive provides atomic, durable no-clobber creation.
    from env.prospective_runner import _atomic_json
    _atomic_json(path, value)


def source_specs():
    return [{"reset": reset, "preparation": [],
             "protocol": [{"time": 0., "field": sign * magnitude}],
             "times": list(TIMES)}
            for reset, sign in (("negative", -1), ("positive", 1))
            for magnitude in (1., 1.15, 1.3, 1.5)]


def _cdf(q, df, noncentrality):
    value = float(ncx2.cdf(q, df, noncentrality))
    if not math.isfinite(value) or not 0. <= value <= 1.:
        raise NumericalFailure("nonfinite_or_invalid_cdf")
    return value


def noncentrality_interval(q, df=CELLS, alpha=MODEL_ALPHA):
    """Invert CDF in lambda, with conservative truncation at lambda=0.

    This is a confidence set for a distribution parameter, not ncx2.interval().
    No independence between the eight model statistics is required by Bonferroni.
    """
    if (type(q) not in (int, float) or not math.isfinite(q) or q < 0.
            or type(df) is not int or df <= 0
            or type(alpha) not in (int, float) or not 0. < alpha < 1.):
        raise ValueError("invalid noncentrality interval input")
    at_zero = _cdf(q, df, 0.)

    def endpoint(probability):
        if at_zero <= probability:
            return 0., True
        high, previous = 1., at_zero
        for _ in range(64):
            value = _cdf(q, df, high)
            if value > previous + 1e-12:
                raise NumericalFailure("cdf_monotonicity_failure")
            if value <= probability:
                break
            if high >= LAMBDA_CAP:
                raise NumericalFailure("noncentrality_bracket_exhausted")
            previous, high = value, min(LAMBDA_CAP, high * 2.)
        else:
            raise NumericalFailure("noncentrality_bracket_iterations_exhausted")
        try:
            root = float(brentq(lambda nc: _cdf(q, df, nc) - probability,
                                0., high, xtol=1e-10, rtol=1e-12, maxiter=200))
        except NumericalFailure:
            raise
        except Exception:
            raise NumericalFailure("noncentrality_root_failure") from None
        if (not math.isfinite(root) or not 0. <= root <= LAMBDA_CAP
                or abs(_cdf(q, df, root) - probability) > 1e-9):
            raise NumericalFailure("noncentrality_root_residual_failure")
        return root, False

    lower, lower_clamped = endpoint(1. - alpha / 2.)
    upper, upper_clamped = endpoint(alpha / 2.)
    if lower > upper:
        raise NumericalFailure("inverted_noncentrality_interval")
    return {"lower": lower, "upper": upper, "cdf_at_zero": at_zero,
            "lower_boundary_clamped": lower_clamped,
            "upper_boundary_clamped": upper_clamped}


def classify_bias(lower, upper):
    if not all(math.isfinite(v) for v in (lower, upper)) or not 0. <= lower <= upper:
        raise NumericalFailure("invalid_bias_interval")
    if upper <= THRESHOLD:
        return "compatible_at_declared_tolerance"
    if lower > THRESHOLD:
        return "incompatible_at_declared_tolerance"
    return "inconclusive"


def bias_diagnostic(predictions, observations):
    """Fixed shapes: p=(8,11,1), observations=(8,16,11,1); exclude t=0."""
    p = np.asarray(predictions, dtype=float)
    y = np.asarray(observations, dtype=float)
    if (p.shape != (8, 11, 1) or y.shape != (8, 16, 11, 1)
            or not np.isfinite(p).all() or not np.isfinite(y).all()):
        raise ValueError("invalid bias diagnostic data")
    means = y.mean(axis=1)
    q = float(REPLICATES * np.sum(((p[:, 1:, 0] - means[:, 1:, 0]) / SIGMA) ** 2))
    interval = noncentrality_interval(q)
    normalized = [math.sqrt(interval[key] / (REPLICATES * CELLS)) for key in ("lower", "upper")]
    return {"Q": q, "degrees_of_freedom": CELLS, "replicates": REPLICATES,
            "sigma": SIGMA, "per_model_alpha": MODEL_ALPHA,
            "lambda_interval": [interval["lower"], interval["upper"]],
            "normalized_true_bias_rms_interval": normalized,
            "true_bias_rms_interval": [SIGMA * value for value in normalized],
            "normalized_bias_nonnegative_moment_estimate": math.sqrt(max(q - CELLS, 0.) / (REPLICATES * CELLS)),
            "boundary": {key: interval[key] for key in ("cdf_at_zero", "lower_boundary_clamped", "upper_boundary_clamped")},
            "classification": classify_bias(*normalized),
            "declared_tolerance_noise_sd": THRESHOLD,
            "estimand": "RMS bias of the frozen point predictor relative to true source-cell means, in channel-noise SD units"}


def _input_hashes(root, expected):
    root = Path(root)
    actual = {}
    for relative in sorted(expected):
        path = Path(relative)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("invalid input relative path")
        full = root / path
        if not full.is_file() or full.is_symlink():
            raise ValueError("missing or symlink source input")
        actual[relative] = _sha(full.read_bytes())
    return actual


def _load_inputs(root, plan):
    env_root = Path(__file__).parent.parent
    if any(_sha((env_root / name).read_bytes()) != expected
           for name, expected in FROZEN_RUNTIME_SHA256.items()):
        raise ValueError("frozen material world/protocol/binder changed")
    expected = plan["input_relative_sha256"]
    before = _input_hashes(root, expected)
    if before != expected:
        raise ValueError("frozen source input hash mismatch")
    cohort = _read_json(root / "plan-private.json")
    if len(cohort["manifests"]) != 4:
        raise ValueError("exactly four frozen d1 instances required")
    cases = []
    for index, seed in enumerate(SEEDS, 1):
        directory = root / ("instance-%02d" % index)
        manifest = _read_json(directory / "manifest-private.json")
        if manifest != cohort["manifests"][index-1] or manifest["private_world_seed"] != seed:
            raise ValueError("original d1 instance order mismatch")
        if manifest["reference"]["source_sha256"] != before["reference-source.py"]:
            raise ValueError("original reference source mismatch")
        source = [_read_json(directory / "science/receipts" / ("%06d.json" % (6+5*j)))
                  for j in range(8)]
        if any(row["kind"] != "source_evidence" for row in source):
            raise ValueError("expected original source evidence")
        specs = [row["payload"]["spec"] for row in source]
        if specs != source_specs() or any(validate_spec(spec) != spec for spec in specs):
            raise ValueError("original source design mismatch")
        fit = _read_json(directory / "driver-receipts/000009.json")["payload"]["analysis"]
        if not fit["ok"] or fit["result"]["failures"] or set(fit["result"]["models"]) != set(MODELS):
            raise ValueError("incomplete archived fits")
        snapshots = {}
        for name in MODELS:
            reference = fit["result"]["models"][name]["model_snapshot"]
            relative = "instance-%02d/models/%s.json" % (index, reference["sha256"])
            if relative not in before or before[relative] != reference["sha256"]:
                raise ValueError("archived snapshot bytes/hash mismatch")
            snapshot = _read_json(root / relative)
            if (snapshot["name"] != name or snapshot["version"] != "v1"
                    or snapshot["parameters"]["kind"] != name
                    or snapshot["parameters"]["diagnostics"] != {k: v for k, v in fit["result"]["models"][name].items() if k != "model_snapshot"}):
                raise ValueError("archived snapshot identity mismatch")
            # The public binder restores JSON data; it never executes the code.
            code = bind_parameters(snapshot["predictor_code"], snapshot["parameters"])
            snapshots[name] = {"snapshot_sha256": reference["sha256"],
                               "bound_source_sha256": _sha(code.encode()), "code": code}
        cases.append({"instance": index, "seed": seed, "specs": specs, "snapshots": snapshots})
    return cases, before


def _runtime_hashes():
    env_root = Path(__file__).parent.parent
    names = list(FROZEN_RUNTIME_SHA256) + ["hysteresis_material/source_validation.py"]
    return {name: _sha((env_root / name).read_bytes()) for name in names}


def _matrix(values):
    raw = np.asarray(values)
    if (raw.shape != (11, 1) or raw.dtype.kind not in "iuf"
            or not np.isfinite(raw).all() or np.any(np.abs(raw) > 1e12)):
        raise ValueError("invalid predictor or observation matrix")
    return raw.astype(float).tolist()


def _predict_isolated(path, spec, seconds):
    from sle.secure_eval import CandidateProxy
    proxy = None
    try:
        proxy = CandidateProxy(path, "predict", timeout_s=seconds, memory_mb=2048, packages=())
        return _matrix(proxy(deepcopy(spec)))
    finally:
        if proxy is not None:
            proxy.close(kill=True)


def _new_world(seed):
    from env.hysteresis_material.world import World
    return World(seed)


def _observe(world, spec, key, seconds):
    from sle.episode_deadline import call_with_deadline
    raw = call_with_deadline(lambda: world.run(deepcopy(spec), noise_key=key), seconds)
    if raw["axis"] != spec["times"] or raw["channels"] != ["response"]:
        raise ValueError("observation contract mismatch")
    return {"axis": list(spec["times"]), "channels": ["response"], "values": _matrix(raw["values"])}


def run(input_root, output, plan_path):
    """Fixed production path. No seed, fit, executor or statistical override."""
    from env.prospective_runner import PrivateJournal, _atomic_bytes
    started = time.monotonic()
    root, output, plan_path = Path(input_root).absolute(), Path(output).absolute(), Path(plan_path).absolute()
    output.mkdir(mode=0o700, parents=False)  # Never resume or overwrite.
    private = output / "private"
    private.mkdir(mode=0o700)
    candidates = private / "candidates"
    candidates.mkdir(mode=0o700)
    journal = PrivateJournal(private / "receipts")
    rows = [{"anonymous_instance": i, "status": "not_attempted", "prediction_calls": 0,
             "observation_calls": 0, "models": [{"id": name, "status": "not_evaluated"} for name in MODELS]}
            for i in range(1, 5)]
    counts = {"prediction_calls": 0, "observation_calls": 0}
    before, plan, cases, sealed, runtime_before = None, None, None, None, None
    active, status, failure, phase = None, "failed", None, "input_precheck"
    namespace = "material-source-validation-" + secrets.token_hex(24)

    def allowance():
        remaining = WORK_SECONDS - (time.monotonic() - started)
        if remaining <= 0.:
            raise TimeoutError("work_deadline_exhausted")
        return min(CALL_SECONDS, remaining)

    def event(kind, payload, *, returned=False):
        # A completed call's data must survive crossing the work deadline.
        # Recording it uses the cleanup reserve; the next call still checks
        # allowance before starting and no further work is authorized here.
        if not returned:
            allowance()
        journal.append(kind, payload)

    _write_new(private / "planned-cases.json", {"reference_id": REFERENCE_ID, "cases": deepcopy(rows),
               "planned_prediction_calls": PREDICTOR_CALLS, "planned_world_calls": WORLD_CALLS,
               "noise_namespace": namespace})
    try:
        plan_bytes = plan_path.read_bytes()
        if _sha(plan_bytes) != EXPECTED_PLAN_SHA256:
            raise ValueError("plan bytes differ from prescribed post-hoc plan")
        plan = _read_json(plan_path)
        runtime_before = _runtime_hashes()
        cases, before = _load_inputs(root, plan)
        _write_new(private / "plan.json", plan)
        _write_new(private / "input-precheck.json", {"input_sha256": before, "plan_sha256": _sha(plan_bytes),
                   "runtime_source_sha256": runtime_before})
        _atomic_bytes(private / "source-validation-source.py", Path(__file__).read_bytes())
        event("inputs_verified", {"input_hashes_sha256": _digest(before), "plan_sha256": _sha(plan_bytes)})
        phase = "predictions"
        predicted = {}
        for case in cases:
            active = case["instance"] - 1
            rows[active]["status"] = "predicting"
            by_model = {}
            for name in MODELS:
                snapshot = case["snapshots"][name]
                path = candidates / (snapshot["bound_source_sha256"] + ".py")
                _atomic_bytes(path, snapshot["code"].encode(), mode=0o444)
                values = []
                for spec_index, spec in enumerate(case["specs"]):
                    copies = []
                    for execution in range(2):
                        if counts["prediction_calls"] >= PREDICTOR_CALLS:
                            raise RuntimeError("prediction_call_limit")
                        seconds = allowance()
                        counts["prediction_calls"] += 1
                        rows[active]["prediction_calls"] += 1
                        label = {"instance": case["instance"], "model": name, "spec_index": spec_index,
                                 "execution": execution, "code_sha256": snapshot["bound_source_sha256"],
                                 "spec_sha256": _digest(spec), "attempt": counts["prediction_calls"]}
                        event("prediction_started", label)
                        value = _predict_isolated(path, spec, min(seconds, allowance()))
                        event("prediction_returned", dict(label, values=value, values_sha256=_digest(value)), returned=True)
                        copies.append(value)
                    if copies[0] != copies[1]:
                        raise ValueError("predictor_nondeterministic")
                    values.append(copies[0])
                by_model[name] = {"values": values, "snapshot_sha256": snapshot["snapshot_sha256"],
                                  "code_sha256": snapshot["bound_source_sha256"]}
            predicted[str(case["instance"])] = by_model
            rows[active]["status"] = "predictions_ready"
        if counts["prediction_calls"] != PREDICTOR_CALLS:
            raise RuntimeError("incomplete_prediction_cohort")
        sealed = {"protocol": PROTOCOL, "reference_id": REFERENCE_ID,
                  "plan_sha256": _sha(plan_bytes), "input_hashes_sha256": _digest(before),
                  "specs": source_specs(), "predictions": predicted,
                  "predictor_calls": counts["prediction_calls"], "new_observation_calls": 0}
        sealed["sha256"] = _digest(sealed)
        _write_new(private / "predictions-sealed.json", sealed)
        event("all_predictions_sealed", {"sha256": sealed["sha256"], "predictor_calls": counts["prediction_calls"], "new_observation_calls": 0})
        # World construction and observations are strictly below this durable seal.
        phase = "observations"
        for case in cases:
            active = case["instance"] - 1
            rows[active]["status"] = "observing"
            world = _new_world(case["seed"])
            if tuple(world.noise_std) != (SIGMA,) or tuple(world.channels) != ("response",):
                raise ValueError("world_noise_contract_changed")
            observations = []
            for spec_index, spec in enumerate(case["specs"]):
                replicas = []
                for replica in range(REPLICATES):
                    if counts["observation_calls"] >= WORLD_CALLS:
                        raise RuntimeError("world_call_limit")
                    seconds = allowance()
                    counts["observation_calls"] += 1
                    rows[active]["observation_calls"] += 1
                    key = "%s:%d:%d:%d" % (namespace, case["instance"], spec_index, replica)
                    label = {"instance": case["instance"], "spec_index": spec_index, "replica": replica,
                             "noise_key": key, "spec": spec, "attempt": counts["observation_calls"],
                             "prediction_seal_sha256": sealed["sha256"]}
                    event("observation_started", label)
                    observation = _observe(world, spec, key, min(seconds, allowance()))
                    event("observation_returned", dict(label, observation=observation), returned=True)
                    replicas.append(observation["values"])
                observations.append(replicas)
            _write_new(private / ("instance-%02d-observations.json" % case["instance"]),
                       {"anonymous_instance": case["instance"], "values": observations,
                        "prediction_seal_sha256": sealed["sha256"]})
            phase = "statistics"
            for model_row in rows[active]["models"]:
                allowance()
                name = model_row["id"]
                # Both models share the same fresh measurements. No old target is read.
                model_row.update(status="evaluated", **bias_diagnostic(predicted[str(case["instance"])][name]["values"], observations))
            rows[active]["status"] = "completed"
            phase = "observations"
        if counts != {"prediction_calls": PREDICTOR_CALLS, "observation_calls": WORLD_CALLS}:
            raise RuntimeError("incomplete_fixed_cohort")
        status = "completed"
    except Exception as error:
        failure = {"phase": phase, "exception_type": type(error).__name__}
        # Detailed strings remain private; arbitrary worker errors never enter public output.
        _write_new(private / "failure.json", dict(failure, message=str(error)[:2000], active_instance=None if active is None else active + 1, counts=counts))
        if active is not None:
            rows[active]["status"] = "failed"
        for row in rows:
            if row["status"] in ("not_attempted", "predictions_ready"):
                row["status"] = "not_attempted_after_failure"
    finally:
        integrity = {"checked": False, "all_unchanged": False}
        try:
            if plan is not None:
                after = _input_hashes(root, plan["input_relative_sha256"])
                runtime_after = _runtime_hashes()
                integrity = {"checked": True, "all_unchanged": after == plan["input_relative_sha256"] and runtime_after == runtime_before, "input_sha256_after": after,
                             "runtime_source_sha256_after": runtime_after, "runtime_unchanged": runtime_after == runtime_before,
                             "plan_unchanged": _sha(plan_path.read_bytes()) == EXPECTED_PLAN_SHA256}
                if not integrity["all_unchanged"] or not integrity["plan_unchanged"]:
                    status, failure = "failed", {"phase": "input_postcheck", "exception_type": "InputIntegrityFailure"}
        except Exception as error:
            status, failure = "failed", {"phase": "input_postcheck", "exception_type": type(error).__name__}
        _write_new(private / "input-postcheck.json", integrity)
    # Do not present any affirmative conclusion as valid when the run is incomplete.
    elapsed = time.monotonic() - started
    if elapsed >= WALL_SECONDS:
        status, failure = "failed", {"phase": "wall_budget", "exception_type": "TimeoutError"}
    _write_new(private / "computed-rows.json", rows)
    for row in rows:
        for model in row["models"]:
            model["conclusion_valid"] = status == "completed" and model["status"] == "evaluated"
            if not model["conclusion_valid"] and "classification" in model:
                model["classification"] = None
    report = {"protocol": PROTOCOL, "reference_id": REFERENCE_ID, "client_kind": "scripted_reference",
              "design_status": "post_hoc_development_diagnostic", "status": status,
              "failure": failure, "planned_instances": 4, "completed_instances": sum(r["status"] == "completed" for r in rows),
              "planned_models": 8, "planned_prediction_calls": PREDICTOR_CALLS,
              "planned_observation_calls": WORLD_CALLS, "counts": counts, "rows": rows,
              "conclusions_valid": status == "completed", "inputs_unchanged": integrity["all_unchanged"],
              "family_alpha": FAMILY_ALPHA, "per_model_alpha": MODEL_ALPHA,
              "family_coverage_claim": "At least 95% jointly for eight fixed point-bias parameters under the independent Gaussian cell-noise model; model statistics may be dependent.",
              "interpretation": "Compatibility means only RMS point-predictive bias <= one channel-noise SD on the selected source cells. Not exact model truth, mechanism-family adequacy or fitted-parameter uncertainty.",
              "old_review_and_p1_p2_results": "unchanged; repeated development seeds are not independent held-out worlds",
              "prediction_seal_sha256": None if sealed is None else sealed["sha256"],
              "elapsed_seconds": elapsed, "model_api_calls": 0, "requested_model": None,
              "token_usage": None, "refits": 0, "autonomous_discovery": False,
              "mechanism_identified": False, "discovery_depth_certified": False}
    _write_new(output / "summary-public.json", report)
    _write_new(private / "completion.json", {"summary_sha256": _digest(report), "receipt_head": journal.head,
               "input_postcheck_sha256": _digest(integrity), "status": status})
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="Exact archived material-research-driver-reference-d1 directory")
    parser.add_argument("--plan", required=True, help="Byte-identical fixed post-hoc plan.json")
    parser.add_argument("--output", required=True, help="New private output directory; no resume/overwrite")
    args = parser.parse_args(argv)
    report = run(args.input, args.output, args.plan)
    print(json.dumps({key: report[key] for key in ("reference_id", "status", "counts", "completed_instances", "model_api_calls")}))
    return 0 if report["status"] == "completed" else 1


if __name__ == "__main__":
    sys.exit(main())

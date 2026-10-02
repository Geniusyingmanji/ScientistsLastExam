"""Bounded operator-only calibration of the author-informed reference.

Only reserved development seeds and nested 8/16 fixed sources are accepted.
Fit JSON is published before any new held-out spec or outcome is generated.
Use processes, not threads: LSODA is not concurrently reentrant in one process.
"""

import argparse
from concurrent.futures import ProcessPoolExecutor
from copy import deepcopy
import hashlib
import json
import multiprocessing
import os
from pathlib import Path
import time

import numpy as np

from ..scoring import canonical_hash, prediction_metrics
from .baseline import baseline
from .protocol import CHANNELS, SCALES, validate_spec
from .strong_baseline import PROTOCOL, DEFAULT_LIMITS, _limits, fit, predict
from .world import World


DEVELOPMENT_SEEDS = (7,46,1439,8743)
RECORD_BUDGETS = (8,16)
SOURCE_VERSION = "fixed-author-source-0.1"


def source_specs():
    """Fixed author-informed design, identical before seeing any instance data."""
    times = [0.,1.,3.,6.,9.,12.,15.,18.,24.,36.]
    base = {"initial": {"A": .05, "B": .05, "C": .05, "nutrient": 5.},
            "temperature_c": 30., "times_h": times, "events": []}
    result = [deepcopy(base)]
    for missing in (("B",), ("C",), ("B","C")):
        spec = deepcopy(base)
        for strain in missing:
            spec["initial"][strain] = 0.
        result.append(spec)
    for peak in CHANNELS[4:]:
        spec = deepcopy(base)
        spec["events"] = [{"time_h": 12., "deplete": {"channel": peak, "fraction": .9}}]
        result.append(spec)
    spec = deepcopy(base)
    spec["events"] = [{"time_h": 18., "feed": 2.}]
    result.append(spec)
    for peak in CHANNELS[4:]:
        spec = deepcopy(base)
        spec["initial"]["C"] = 0.
        spec["events"] = [{"time_h": 9., "deplete": {"channel": peak, "fraction": .9}}]
        result.append(spec)
    for temperature in (22.,38.):
        spec = deepcopy(base)
        spec["temperature_c"] = temperature
        result.append(spec)
    for nutrient, a, b, c in ((2.,.1,.02,.1), (8.,.03,.15,.02)):
        spec = deepcopy(base)
        spec["initial"] = dict(A=a,B=b,C=c,nutrient=nutrient)
        result.append(spec)
    spec = deepcopy(base)
    spec["events"] = [{"time_h": 12., "temperature_c": 38.}, {"time_h": 24., "temperature_c": 22.}]
    result.append(spec)
    return [validate_spec(spec) for spec in result]


def _source_hash():
    directory = Path(__file__).resolve().parent
    paths = [directory/name for name in ("kernel.py", "protocol.py", "world.py", "baseline.py", "strong_baseline.py", "strong_calibration.py")]
    paths.append(directory.parent / "scoring.py")
    return canonical_hash({path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths})


def _save(path, value):
    text = json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n"
    with Path(path).open("x", encoding="utf-8") as stream:
        stream.write(text)
        stream.flush()
        os.fsync(stream.fileno())
    Path(path).chmod(0o600)


def _panel_seed(seed, kind):
    digest = hashlib.sha256((PROTOCOL + ":fresh-evaluation:%d:%s" % (seed,kind)).encode()).digest()
    return int.from_bytes(digest[:8], "big") % (2**63)


def _one(job):
    seed, count, limits, panel_count, folder, expected_source = job
    directory = Path(folder)
    directory.mkdir(mode=0o700)
    if _source_hash() != expected_source:
        raise ValueError("source changed after reference calibration freeze")
    world = World(seed)
    specs = source_specs()[:count]
    records = [{"id": "source-%02d" % index, "spec": spec,
                "observation": world.run(spec, noise_key=SOURCE_VERSION+":source-%02d" % index),
                "cost": world.cost(spec)} for index,spec in enumerate(specs)]
    _save(directory/"source-records-private.json", {"source_version": SOURCE_VERSION, "records": records})
    fit_result = fit(deepcopy(records), limits=limits)
    frozen = {"protocol": PROTOCOL, "source_sha256": expected_source,
              "source_records_sha256": canonical_hash(records), "result": fit_result}
    _save(directory/"fit-private.json", frozen)
    fit_sha256 = hashlib.sha256((directory/"fit-private.json").read_bytes()).hexdigest()
    # Evaluation starts only after the fitted model and all diagnostics are on
    # disk. Neither private structure nor peak map has been consulted to fit.
    training_hashes = {canonical_hash(spec) for spec in specs}
    queries = []
    for kind in ("conditions", "interventions"):
        for spec in world.panel(_panel_seed(seed,kind), kind, panel_count):
            if canonical_hash(spec) in training_hashes:
                raise ValueError("source/evaluation overlap")
            clean = world.run(spec)
            methods = {}
            for method in ("author_reference", "empirical_baseline"):
                try:
                    prediction = predict(fit_result["model"], spec) if method == "author_reference" else baseline(records,spec)
                    metrics = prediction_metrics(prediction, clean, SCALES)
                    methods[method] = dict(metrics, valid=True, prediction=prediction)
                except (ValueError, RuntimeError, FloatingPointError, OverflowError) as error:
                    methods[method] = {"valid": False, "score": 0., "normalized_rmse": None,
                                       "error_type": type(error).__name__}
            queries.append({"kind": kind, "spec": spec, "clean": clean, "methods": methods})
    if hashlib.sha256((directory/"fit-private.json").read_bytes()).hexdigest() != fit_sha256 or _source_hash() != expected_source:
        raise ValueError("fit/source changed during separate evaluation")
    report = {"protocol": PROTOCOL, "development_seed": seed, "record_budget": count,
              "source_cost": sum(record["cost"] for record in records), "fit_sha256": fit_sha256,
              "private_structure": world.operator_stratum(), "fit": fit_result, "queries": queries}
    _save(directory/"report-private.json", report)
    return report


def _public_summary(reports, failures, limits, planned, panel_count):
    cells = []
    for count in RECORD_BUDGETS:
        selected = [row for row in reports if row["record_budget"] == count]
        failed_jobs = sum(row["record_budget"] == count for row in failures)
        if not selected and not failed_jobs:
            continue
        for kind in ("conditions", "interventions"):
            for method in ("author_reference", "empirical_baseline"):
                metrics = [query["methods"][method] for row in selected for query in row["queries"] if query["kind"] == kind]
                errors = [item["normalized_rmse"] for item in metrics if item["valid"]]
                cells.append({"record_budget": count, "kind": kind, "method": method, "experiments": len(metrics),
                              "planned_experiments": (len(selected)+failed_jobs)*panel_count,
                              "job_failure_unavailable_experiments": failed_jobs*panel_count,
                              "valid": len(errors), "invalid": len(metrics)-len(errors),
                              "mean_nrmse": float(np.mean(errors)) if errors else None,
                              "mean_score_on_completed_jobs_including_invalid_prediction_zero": float(np.mean([item["score"] for item in metrics])) if metrics else None})
    return {"protocol": PROTOCOL, "author_informed": True, "autonomous_discovery": False,
            "planned_fits": planned, "completed_fit_reports": len(reports), "job_failures": len(failures),
            "limits_per_fit": limits, "no_model_fits": sum(row["fit"]["model"] is None for row in reports),
            "unconverged_fits": sum(not row["fit"]["converged"] for row in reports),
            "fit_cpu_seconds": [row["fit"]["usage"]["cpu_seconds"] for row in reports],
            "fit_wall_seconds": [row["fit"]["usage"]["wall_seconds"] for row in reports], "metrics": cells,
            "scope": "Reserved development calibration with known family/menu/box and a fixed author-informed source design. Failures remain visible; usable best models may be unconverged. No autonomous discovery, formal model comparison or performance-scaling claim."}


def calibrate(output, *, seeds=DEVELOPMENT_SEEDS, budgets=RECORD_BUDGETS, workers=2,
              limits=None, panel_count=4):
    if (not isinstance(seeds,(tuple,list)) or not seeds or any(type(seed) is not int or seed not in DEVELOPMENT_SEEDS for seed in seeds)
            or len(set(seeds)) != len(seeds)):
        raise ValueError("only distinct reserved development seeds are allowed")
    if (not isinstance(budgets,(tuple,list)) or not budgets or any(type(count) is not int or count not in RECORD_BUDGETS for count in budgets)
            or len(set(budgets)) != len(budgets)):
        raise ValueError("only the predeclared 8 and 16 record budgets are allowed")
    if type(workers) is not int or not 1 <= workers <= 4 or type(panel_count) is not int or not 1 <= panel_count <= 8:
        raise ValueError("workers must be 1..4 and panel_count 1..8")
    limits = _limits(limits)
    directory = Path(output)
    directory.mkdir(mode=0o700, parents=True, exist_ok=False)
    source_hash = _source_hash()
    jobs = [(seed,count,limits,panel_count,str(directory/("seed-%d-records-%d" % (seed,count))),source_hash) for seed in seeds for count in budgets]
    _save(directory/"plan-private.json", {"protocol": PROTOCOL, "source_sha256": source_hash,
          "seeds": list(seeds), "budgets": list(budgets), "workers": workers, "panel_count": panel_count,
          "limits": limits, "source_version": SOURCE_VERSION, "source_specs": source_specs(),
          "maximum_nominal_fit_cpu_seconds": len(jobs)*limits["cpu_seconds"]})
    reports, failures = [], []
    os.environ.update(OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1", MKL_NUM_THREADS="1")
    with ProcessPoolExecutor(max_workers=workers, mp_context=multiprocessing.get_context("spawn")) as pool:
        futures = [(job,pool.submit(_one,job)) for job in jobs]
        for job,future in futures:
            try:
                reports.append(future.result())
            except Exception as error:
                failures.append({"development_seed": job[0], "record_budget": job[1], "error_type": type(error).__name__})
    _save(directory/"failures-private.json", failures)
    summary = _public_summary(reports,failures,limits,len(jobs),panel_count)
    _save(directory/"public-summary.json",summary)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",required=True)
    parser.add_argument("--seeds",default="7,46,1439,8743")
    parser.add_argument("--budgets",default="8,16")
    parser.add_argument("--workers",type=int,default=2)
    parser.add_argument("--cpu-seconds",type=float,default=60)
    parser.add_argument("--wall-seconds",type=float,default=90)
    parser.add_argument("--residual-attempts",type=int,default=234)
    parser.add_argument("--panel-count",type=int,default=4)
    args=parser.parse_args()
    summary=calibrate(args.output,seeds=tuple(map(int,args.seeds.split(","))),budgets=tuple(map(int,args.budgets.split(","))),
                      workers=args.workers,panel_count=args.panel_count,
                      limits={"cpu_seconds":args.cpu_seconds,"wall_seconds":args.wall_seconds,"residual_attempts":args.residual_attempts})
    print(json.dumps(summary,sort_keys=True,allow_nan=False))


if __name__ == "__main__":
    main()

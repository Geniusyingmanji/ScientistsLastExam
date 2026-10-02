"""Bounded, API-free operator development diagnostics; writes private raw data."""

import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import time

import numpy as np

from .baseline import baseline
from .kernel import Kernel, Parameters, STRUCTURES
from .protocol import NOISE_STD, initial_values, validate_spec
from .reference import radau_reference
from .world import World

DEVELOPMENT_SEEDS = (7, 46, 1439, 8743)


class BudgetStop(RuntimeError):
    pass


class Recorder:
    def __init__(self, output):
        self.output = Path(output)
        self.started = time.process_time()
        self.report = {"protocol": "pattern-development-diagnostics-v1", "world_version": World.version,
                       "scope": "Private development diagnostics only; no model evaluation, official score or depth grade.",
                       "attempt_limit": 70, "cpu_limit_seconds": 100., "attempts": [], "instances": [], "checks": []}

    def save(self):
        self.report["cpu_seconds"] = time.process_time()-self.started
        self.output.write_text(json.dumps(self.report, indent=2, allow_nan=False)+"\n", encoding="utf-8")

    def run(self, label, callable_):
        if len(self.report["attempts"]) >= 70 or time.process_time()-self.started >= 100:
            raise BudgetStop("development budget exhausted; retained partial output")
        entry = {"label": label, "status": "started"}
        self.report["attempts"].append(entry)
        self.save()
        started = time.process_time()
        try:
            values, work = callable_()
            entry.update(status="completed", work=work)
            return values
        except Exception as exc:
            entry.update(status="failed", error_type=type(exc).__name__, error=str(exc))
            return None
        finally:
            entry["cpu_seconds"] = time.process_time()-started
            self.save()


def _seed(seed, label):
    return int(hashlib.sha256(("pattern-development-v1:%d:%s" % (seed, label)).encode()).hexdigest()[:15], 16)


def _spec(length=24., drive=0., mean=0., mode=4, amplitude=.05, phase=0., times=None):
    return validate_spec({"length": length, "drive": drive,
                          "initial": {"mean": mean, "modes": [] if amplitude == 0 else [{"mode": mode, "amplitude": amplitude, "phase": phase}]},
                          "times": [0., .5, 2., 8., 20.] if times is None else times})


def _distribution(values):
    values = np.asarray(values, dtype=float)
    if not len(values):
        return {"count": 0, "mean": None, "min": None, "max": None}
    return {"count": len(values), "mean": float(values.mean()), "min": float(values.min()), "max": float(values.max())}


def calibrate(output):
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as stream:
        stream.write("{}\n")
    rec = Recorder(output)
    try:
        for seed in DEVELOPMENT_SEEDS:
            world = World(seed)
            instance = {"development_seed": seed, "private_stratum": world.operator_stratum(),
                        "private_parameters": asdict(world._kernel.parameters), "source_records": [], "queries": []}
            rec.report["instances"].append(instance)
            for index, spec in enumerate(world.panel(_seed(seed, "sources"), "development", 4)):
                def observed():
                    # Only this result is available to the public-data baseline.
                    observation = world.run(spec, noise_key="development-source-%d" % index)
                    return np.asarray(observation["values"]), {"public_cost": world.cost(spec)}
                values = rec.run("seed-%d-source-%d" % (seed, index), observed)
                if values is not None:
                    instance["source_records"].append({"spec": spec, "observation": {"axis": spec["times"], "channels": list(world.channels), "values": values.tolist()}})
            for kind in ("conditions", "interventions"):
                for index, spec in enumerate(world.panel(_seed(seed, kind), kind, 4)):
                    truth = rec.run("seed-%d-%s-%d" % (seed, kind, index), lambda: world._kernel.trajectory(spec))
                    row = {"kind": kind, "spec": spec, "private_truth": None if truth is None else truth.tolist(), "methods": {}}
                    instance["queries"].append(row)
                    if truth is None:
                        continue
                    for count in (0, 2, 4):
                        if len(instance["source_records"]) < count:
                            continue
                        prediction = np.asarray(baseline(instance["source_records"][:count], spec))
                        residual = (prediction-truth)[np.asarray(spec["times"]) > 0]
                        nrmse = float(np.sqrt(np.mean(residual**2)))
                        row["methods"][str(count)] = {"normalized_rmse": nrmse, "prediction_only_score": float(100*np.exp(-nrmse/.1)), "cells": int(residual.size)}
                    if kind == "conditions" and index == 0:
                        reference = rec.run("seed-%d-independent-Radau" % seed, lambda: radau_reference(world._kernel.parameters, spec))
                        row["independent_reference"] = None if reference is None else {"max_absolute_error": float(np.max(np.abs(truth-reference))),
                            "max_error_in_noise_sd": float(np.max(np.abs(truth-reference)/NOISE_STD)),
                            "same_collocation_grid": True, "PDE_convergence_checked": False}
        checks = rec.report["checks"]
        p = Parameters()
        spec = _spec(length=8*np.pi, mode=4, amplitude=1e-5, times=[0., .25, .5, 1., 2.])
        values = rec.run("small-amplitude-linear-growth", lambda: Kernel(p).trajectory(spec))
        if values is not None:
            linear = initial_values(spec)[None, :]*np.exp(p.r0*np.asarray(spec["times"]))[:, None]
            checks.append({"name": "small_amplitude_growth", "private_eigenvalue": p.r0, "max_abs_error_vs_linear": float(np.max(np.abs(values-linear))), "scope": "cubic term is nonzero, so this is an asymptotic small-amplitude check"})
        for r0 in (.24, -.4):
            spec = _spec(amplitude=0., times=[0., 1., 10., 60.])
            values = rec.run("unforced-zero-%g" % r0, lambda: Kernel(Parameters(r0=r0)).trajectory(spec))
            if values is not None:
                checks.append({"name": "exact_zero_invariant", "private_r0": r0, "max_abs_output": float(np.max(np.abs(values)))})
        # A shift of one probe (four internal grid sites) is an exact symmetry of the unforced collocation ODE.
        for forcing in (0., .05):
            p = Parameters(r0=-.12 if forcing else .24, forcing=forcing, forcing_mode=3, forcing_phase=.4)
            base, shifted = _spec(phase=.2), _spec(phase=(.2+4*2*np.pi/16+np.pi) % (2*np.pi)-np.pi)
            first = rec.run("grid-shift-base-f%g" % forcing, lambda: Kernel(p).trajectory(base))
            second = rec.run("grid-shift-translated-f%g" % forcing, lambda: Kernel(p).trajectory(shifted))
            if first is not None and second is not None:
                difference = second - np.roll(first, -1, axis=1)
                checks.append({"name": "grid_translation", "private_forcing": forcing,
                               "time_zero_max_difference": float(np.max(np.abs(difference[0]))),
                               "positive_time_max_difference": float(np.max(np.abs(difference[1:]))),
                               "expectation": "numerical agreement" if forcing == 0 else "symmetry breaking may be visible"})
        for index, (length, drive, mean, mode) in enumerate(((12., -.4, -.2, 8), (12., .4, .2, 8), (32., -.4, .2, 1), (32., .4, -.2, 5))):
            spec = _spec(length, drive, mean, mode, .3, np.pi, [0., .001, 1., 10., 60.])
            p = Parameters(r0=.32, gain=.7, q0=1.15, cubic=.8, forcing=.07, forcing_mode=5)
            values = rec.run("public-corner-%d" % index, lambda: Kernel(p).trajectory(spec))
            if values is not None:
                checks.append({"name": "public_corner", "spec": spec, "max_abs_probe": float(np.max(np.abs(values))), "all_finite": bool(np.isfinite(values).all())})
        matched = _spec(length=8*np.pi, mode=4, amplitude=.01, times=[0., 1., 5., 15., 30., 60.])
        for label, p in ((STRUCTURES[0], Parameters()), (STRUCTURES[1], Parameters(r0=-.4)),
                         (STRUCTURES[2], Parameters(r0=-.12, forcing=.05, forcing_mode=4))):
            values = rec.run("illustrative-stratum-%s" % label, lambda: Kernel(p).trajectory(matched))
            if values is not None:
                checks.append({"name": "illustrative_stratum_response", "private_stratum": label,
                               "spec": matched, "rms_over_probes": np.sqrt(np.mean(values**2, axis=1)).tolist(),
                               "scope": "chosen parameter illustration, not identification of every generated instance"})
        rec.report["status"] = "completed"
    except BudgetStop as exc:
        rec.report.update(status="budget_exhausted", stop_reason=str(exc))
    except Exception as exc:
        rec.report.update(status="failed", error_type=type(exc).__name__, error=str(exc))
    rows = [row for instance in rec.report["instances"] for row in instance["queries"]]
    rec.report["summary"] = {
        "trajectory_attempts": len(rec.report["attempts"]),
        "completed_trajectories": sum(row["status"] == "completed" for row in rec.report["attempts"]),
        "failed_trajectories": sum(row["status"] == "failed" for row in rec.report["attempts"]),
        "stratum_counts": {label: sum(row["private_stratum"] == label for row in rec.report["instances"]) for label in STRUCTURES},
        "baseline": {str(count): {metric: _distribution([row["methods"][str(count)][metric] for row in rows if str(count) in row["methods"]])
                                   for metric in ("normalized_rmse", "prediction_only_score")} for count in (0, 2, 4)}}
    rec.report["limitations"] = ["Only four fixed development instances; generated strata may be unbalanced.",
        "Baseline uses public observations only but its scores do not establish intrinsic difficulty or model capability.",
        "Finite-mode linear instability is condition-dependent; a generation label is not a complete explanation.",
        "Exact zero stays zero without forcing, even if linearly unstable; no hidden process noise initiates it.",
        "Sixteen probes alias spatial modes; finite observations need not identify the entire field or dynamics.",
        "Independent time integration checks the same finite collocation ODE, not continuum PDE convergence.",
        "No contamination resistance, discovery depth, model completion or scaling result is produced."]
    rec.save()
    return rec.report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    report = calibrate(args.output)
    print(json.dumps({"status": report["status"], "cpu_seconds": report["cpu_seconds"], "summary": report["summary"]}, indent=2))
    return 0 if report["status"] == "completed" and not report["summary"]["failed_trajectories"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

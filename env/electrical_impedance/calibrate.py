"""Operator diagnostics. Call under an external cumulative spectrum/CPU budget.

Development seeds are supplied from a private, predeclared plan. This module
does not choose replacement seeds, fit a model, or run a candidate.
"""

from dataclasses import asdict

import numpy as np

from . import reference
from .baseline import baseline
from .kernel import Branch, Kernel, Parameters
from .protocol import CHANNELS, example
from .world import World


def _error(error):
    return {"type": type(error).__name__, "message": str(error)}


def development(seeds):
    instances = []
    failures = []
    for seed in seeds:
        world = World(seed)
        instance = {"seed": seed, "operator_stratum": world.operator_stratum(),
                    "parameters": asdict(world._kernel.parameters), "source": [], "queries": []}
        source_specs = world.panel(seed, "development", 3)
        for index, spec in enumerate(source_specs):
            row = {"spec": spec}
            try:
                row["observation"] = world.run(spec, noise_key="development-source-%d" % index)
            except Exception as error:
                row["failure"] = _error(error)
                failures.append({"seed": seed, "stage": "source", "index": index, **_error(error)})
            instance["source"].append(row)
        query_number = 0
        for kind in ("conditions", "interventions"):
            for index, spec in enumerate(world.panel(seed, kind, 2)):
                assert spec not in source_specs
                row = {"kind": kind, "index": index, "spec": spec, "prefix_scores": {}}
                try:
                    observation = world.run(spec)
                    row["clean_target"] = observation
                    actual = np.asarray(observation["values"])
                    response = actual/spec["amplitude_v"]
                    row["frequency_shape_rms_gain"] = float(np.sqrt(np.mean((response-response.mean(axis=0))**2)))
                    for prefix in (0, 1, 3):
                        records = [record for record in instance["source"][:prefix] if "observation" in record]
                        try:
                            prediction = np.asarray(baseline(records, spec))
                            residual = prediction-actual
                            gain_error = residual/spec["amplitude_v"]
                            row["prefix_scores"][str(prefix)] = {
                                "actual_records": len(records), "prediction": prediction.tolist(),
                                "rmse_v": float(np.sqrt(np.mean(residual**2))),
                                "frequency_shape_rmse_gain": float(np.sqrt(np.mean((gain_error-gain_error.mean(axis=0))**2)))}
                        except Exception as error:
                            row["prefix_scores"][str(prefix)] = {"failure": _error(error)}
                            failures.append({"seed": seed, "stage": "baseline", "kind": kind, "index": index,
                                             "prefix": prefix, **_error(error)})
                    if query_number == 0:
                        expected = reference.spectrum(world._kernel.parameters, spec)
                        row["independent_reference"] = expected
                        row["independent_max_absolute_error_v"] = float(np.max(np.abs(actual-expected)))
                except Exception as error:
                    row["failure"] = _error(error)
                    failures.append({"seed": seed, "stage": "query", "kind": kind, "index": index, **_error(error)})
                instance["queries"].append(row)
                query_number += 1
        instances.append(instance)
    summary = {"instances_planned": len(seeds), "queries_planned": 4*len(seeds), "failures": failures,
               "stratum_counts": {stratum: sum(row["operator_stratum"] == stratum for row in instances) for stratum in World.operator_strata},
               "baseline_prefixes": {}, "reference_max_absolute_error_v": None,
               "interpretation": "Descriptive diagnostics for this fixed small development set; no tuning, agent evaluation, difficulty certification or topology identification."}
    queries = [row for instance in instances for row in instance["queries"]]
    for prefix in (0, 1, 3):
        rows = [row["prefix_scores"][str(prefix)] for row in queries
                if str(prefix) in row["prefix_scores"] and "failure" not in row["prefix_scores"][str(prefix)]]
        summary["baseline_prefixes"][str(prefix)] = {
            "successful_queries": len(rows), "planned_denominator": len(queries),
            "failed_or_missing_queries": len(queries)-len(rows),
            "mean_rmse_v_successes_only": float(np.mean([row["rmse_v"] for row in rows])) if rows else None,
            "mean_frequency_shape_rmse_gain_successes_only": float(np.mean([row["frequency_shape_rmse_gain"] for row in rows])) if rows else None}
    errors = [row["independent_max_absolute_error_v"] for row in queries if "independent_max_absolute_error_v" in row]
    if errors:
        summary["reference_max_absolute_error_v"] = max(errors)
    return {"instances": instances, "summary": summary}


def ambiguity_diagnostics():
    """Eight predeclared clean spectra; include the external-load negative result."""
    common_c, common_r, common_leakage, inductance, f0 = 2e-6, 250., 5000., .08, 100.
    match_c = 1/(1/common_c+(2*np.pi*f0)**2*inductance)
    rc = Kernel(Parameters(common_leakage, (Branch(common_r, common_c),)))
    rlc = Kernel(Parameters(common_leakage, (Branch(common_r, match_c, inductance),)))
    split = Kernel(Parameters(common_leakage, (Branch(2*common_r, common_c/2), Branch(2*common_r, common_c/2))))
    broad = dict(example(), frequencies_hz=[2., 10., 30., 100., 300., 500., 1000., 3000., 5000.])
    narrow = dict(example(), frequencies_hz=[99.9, 100., 100.1])
    load_changed = dict(example(), frequencies_hz=[100.], source_ohm=1200., load_ohm=200.)
    cases = []
    for name, left, right, spec in (("matched_rc_rlc_narrow", rc, rlc, narrow),
                                    ("matched_rc_rlc_broad", rc, rlc, broad),
                                    ("matched_rc_rlc_external_load_negative_control", rc, rlc, load_changed),
                                    ("single_rc_split_parallel_equivalence", rc, split, broad)):
        row = {"case": name, "spec": spec, "left_parameters": asdict(left.parameters), "right_parameters": asdict(right.parameters)}
        try:
            first, _ = left.spectrum(spec)
            second, _ = right.spectrum(spec)
            difference = second-first
            row.update({"left": first.tolist(), "right": second.tolist(),
                        "max_absolute_difference_v": float(np.max(abs(difference))),
                        "rms_difference_v": float(np.sqrt(np.mean(difference**2))),
                        "joint_difference_norm_per_single_reading_noise_sd": float(np.linalg.norm(difference)/.001)})
            if name == "matched_rc_rlc_narrow":
                row["matched_100hz_max_error_v"] = float(np.max(abs(difference[1])))
        except Exception as error:
            row["failure"] = _error(error)
        cases.append(row)
    return {"cases": cases,
            "noise_interpretation": "Differences compared with 0.001 V independent noise per quadrature. A near-zero narrow-band difference is finite-observation ambiguity, not exact equality throughout an interval; unlimited repeated readings can resolve a nonzero difference. At exactly 100 Hz the constructed admittances agree analytically. Split RC branches agree at all frequencies analytically.",
            "scope": "These constructed comparisons establish specific examples, not population-wide difficulty or unique recovery of internal topology."}

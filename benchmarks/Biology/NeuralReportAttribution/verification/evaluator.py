"""Frozen linearized neural-population response model with report and sensor paths.

Not a simulator of subjective experience, GNWT, or IIT. Identifies specified
effective coupling in a controlled local linear model, with an omitted-state case.
"""
from __future__ import annotations

import copy
import math

import numpy as np

BUDGET = 14
MEASUREMENT_NOISE_SD = .012
FREQUENCIES = [0.08, 0.2, 0.5, 1.1, 2.0]
MODELS = ("recurrent", "report_only", "none")


def dynamics(parameters, report, hidden=False):
    tau = np.asarray(parameters["tau"])
    a, b, local, feed, feedback, report_feedback = parameters["edges"]
    n = 5 if hidden else 4
    matrix = np.zeros((n, n))
    matrix[:4, :4] = np.diag(-1.0/tau)
    matrix[1, 0] = a
    matrix[2, 1] = b
    matrix[0, 1] = local
    matrix[3, 2] = feed
    matrix[1, 2] = feedback
    matrix[1, 3] = report * report_feedback
    if hidden:
        # An omitted slow population mediates P -> V2. Not a static P -> V2 edge.
        matrix[4, 4] = -0.4
        matrix[4, 2] = .9
        matrix[1, 4] = .65
    return matrix


def transfer(world, report, omega):
    hidden = world["kind"] == "unsupported"
    a = dynamics(world["parameters"], report, hidden)
    response = np.linalg.inv(1j * omega * np.eye(len(a)) - a)[:4, :4]
    c, b, d, tau = world["instruments"][report]
    lowpass = 1/(1+1j*omega*tau)
    return lowpass[:, None]*(c @ response @ b) + d


def make_world(seed, kind):
    rng = np.random.default_rng(seed)
    edges = [rng.uniform(.4, .7), rng.uniform(.35, .65), rng.uniform(.12, .3),
             rng.uniform(.45, .8), rng.uniform(.25, .5) if kind == "recurrent" else 0.,
             rng.uniform(.3, .6)]
    if kind == "none":
        edges = [0.] * 6
    parameters = {"tau": rng.uniform(.35, .65, 4), "edges": edges}
    instruments = []
    for report in (0, 1):
        c = np.diag(rng.uniform(.8, 1.3, 4)) + rng.normal(0, .08, (4, 4))
        b = np.diag(rng.uniform(.7, 1.2, 4)) + rng.normal(0, .07, (4, 4))
        d = rng.normal(0, .04, (4, 4))
        tau = rng.uniform(.05, .3, 4)
        instruments.append((c, b, d, tau))
    # A public experimental setting shared by every world, never a world identifier.
    noise = MEASUREMENT_NOISE_SD
    problem = {"population_names": ["V1", "V2", "P", "R"],
               "angular_frequencies": list(FREQUENCIES), "budget_units": BUDGET,
               "measurement_noise_sd": noise, "calibration_noise_sd": .015,
               "time_constant_bounds": [.25, .8], "edge_bounds": [0., 1.2],
               "supported_models": list(MODELS), "minimum_feedback": .15,
               "report_conditions": [0, 1]}
    return {"seed": seed, "kind": kind, "parameters": parameters,
            "instruments": instruments, "problem": problem, "noise": noise}


class Campaign:
    def __init__(self, world):
        self.world = world
        self.used = 0
        self.violated = False
        self.repeats = {}

    def __call__(self, request):
        try:
            if not isinstance(request, dict) or set(request) != {"kind", "report", "frequency", "units"}:
                raise ValueError("invalid request")
            kind, report, freq, n = (request[k] for k in ("kind", "report", "frequency", "units"))
            if kind not in ("calibration", "response") or type(report) is not int or report not in (0, 1):
                raise ValueError("invalid condition")
            if type(freq) is not int or not 0 <= freq < len(FREQUENCIES):
                raise ValueError("invalid frequency")
            if kind == "calibration" and freq != 0:
                raise ValueError("calibration frequency must be zero sentinel")
            if type(n) is not int or n < 1 or self.used+n > BUDGET:
                raise ValueError("invalid exposure")
            self.used += n
            key = (kind, report, freq)
            start = self.repeats.get(key, 0)
            w = self.world
            arrays = []
            for k in range(start, start+n):
                rng = np.random.default_rng([w["seed"], 207, int(kind == "response"), report, freq, k])
                if kind == "calibration":
                    c, b, d, tau = w["instruments"][report]
                    truth = np.concatenate([c.ravel(), b.ravel(), d.ravel(), tau])
                    arrays.append(truth + rng.normal(0, .015, 52))
                else:
                    h = transfer(w, report, FREQUENCIES[freq])
                    truth = np.concatenate([h.real.ravel(), h.imag.ravel()])
                    arrays.append(truth + rng.normal(0, w["noise"], 32))
            self.repeats[key] = start+n
            mean = np.mean(arrays, axis=0)
            if kind == "calibration":
                return {"sensor_mixing": mean[:16].reshape(4, 4).tolist(),
                        "actuator_mixing": mean[16:32].reshape(4, 4).tolist(),
                        "feedthrough": mean[32:48].reshape(4, 4).tolist(),
                        "sensor_time_constants": mean[48:].tolist(), "units": n}
            return {"real": mean[:16].reshape(4, 4).tolist(),
                    "imag": mean[16:].reshape(4, 4).tolist(), "units": n}
        except Exception:
            self.violated = True
            raise ValueError("invalid experiment or exhausted budget") from None


def validate(answer):
    if not isinstance(answer, dict) or type(answer.get("abstain", False)) is not bool:
        raise ValueError("invalid answer")
    confidence = answer.get("confidence", 1.)
    if type(confidence) not in (int, float) or not math.isfinite(confidence) or not 0 <= confidence <= 1:
        raise ValueError("invalid confidence")
    if answer.get("abstain", False):
        return "abstain", 0., 0., float(confidence)
    model = answer.get("model")
    if not isinstance(model, str) or model not in MODELS:
        raise ValueError("invalid model")
    if model == "none":
        return model, 0., 0., float(confidence)
    values = [answer.get("feedback"), answer.get("report_feedback")]
    if any(type(v) not in (int, float) or not math.isfinite(v) or not 0 <= v <= 1.2 for v in values):
        raise ValueError("invalid coupling")
    if model == "report_only" and values[0] != 0:
        raise ValueError("report_only feedback must be zero")
    return model, *map(float, values), float(confidence)


def score_world(world, answer):
    model, feedback, report_feedback, confidence = validate(answer)
    kind = world["kind"]
    correct = model == kind or (kind == "unsupported" and model == "abstain")
    claim = model in ("recurrent", "report_only")
    parameter = 0.
    if correct and claim:
        true_f, true_r = world["parameters"]["edges"][-2:]
        parameter = max(0., 1 - max(abs(feedback-true_f)/.12, abs(report_feedback-true_r)/.15))
    mechanism = parameter if kind in ("recurrent", "report_only") else float(correct)
    return {"valid": True, "model": model, "mechanism": mechanism, "claim": claim,
            "false_claim": bool(claim and not correct),
            "correct_refusal": kind == "unsupported" and model == "abstain",
            "confidence_brier": (confidence-float(correct))**2}


def evaluate(candidate):
    results, records = {}, []
    for split, base in (("development", 381900), ("heldout", 527300)):
        rows = []
        kinds = ["recurrent", "report_only"]*3 + ["none"]*2 + ["unsupported"]*2
        for i in np.random.default_rng(base + 89).permutation(len(kinds)):
            i = int(i)
            kind = kinds[i]
            world = make_world(base+i*113, kind)
            lab = Campaign(world)
            try:
                # A fresh process and tmpfs per world, including the split boundary.
                if (records or rows) and hasattr(candidate, "reset_session"):
                    candidate.reset_session()
                answer = candidate(copy.deepcopy(world["problem"]), lab)
                if lab.violated:
                    raise ValueError("invalidated campaign")
                row = score_world(world, answer)
            except Exception:
                row = {"valid": False, "model": "invalid", "mechanism": 0., "claim": False,
                       "false_claim": False, "correct_refusal": False, "confidence_brier": 1.}
            row.update(split=split, kind=kind, units=lab.used)
            rows.append(row)
        claims = sum(r["claim"] for r in rows)
        false = sum(r["false_claim"] for r in rows)
        raw = sum(r["mechanism"] for r in rows)/len(rows)
        values = {"mechanism_score": max(0., (raw-.2)/.8),
                  "false_discovery_rate": false/claims if claims else 0.,
                  "false_discovery_count": false, "claim_count": claims,
                  "correct_refusal_rate": sum(r["correct_refusal"] for r in rows)/2,
                  "correct_refusal_count": sum(r["correct_refusal"] for r in rows),
                  "refusal_world_count": 2,
                  "discovery_coverage": sum(r["claim"] for r in rows if r["kind"] in ("recurrent", "report_only"))/6,
                  "supported_claim_count": sum(r["claim"] for r in rows if r["kind"] in ("recurrent", "report_only")),
                  "supported_world_count": 6,
                  "none_correct_rate": sum(r["model"] == "none" for r in rows if r["kind"] == "none")/2,
                  "none_correct_count": sum(r["model"] == "none" for r in rows if r["kind"] == "none"),
                  "none_world_count": 2,
                  "valid_world_count": sum(r["valid"] for r in rows),
                  "world_count": len(rows),
                  "experiment_units_sum": sum(r["units"] for r in rows),
                  "valid_rate": sum(r["valid"] for r in rows)/len(rows),
                  "mean_units": sum(r["units"] for r in rows)/len(rows),
                  "confidence_brier": sum(r["confidence_brier"] for r in rows)/len(rows)}
        results.update({split+"_"+k: round(float(v), 10) for k, v in values.items()})
        records.extend(rows)
    results.update(combined_score=results["development_mechanism_score"],
                   valid=float(all(r["valid"] for r in records if r["split"] == "development")),
                   feasibility_rate=results["development_valid_rate"], per_instance=records)
    return results

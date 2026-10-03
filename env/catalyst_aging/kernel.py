"""Private reduced activity/product dynamics; exact constant-condition integral."""
import hashlib
import math
import numpy as np
from .protocol import COUPONS, STANDARD_RESPONSE

GAS_CONSTANT = 8.31446261815324
STRATA = ("single_site", "instrument_jump", "two_site")


def make_instance(seed):
    rng = np.random.default_rng(seed)
    digest = hashlib.sha256(("catalyst-aging-structure-v1:%d" % seed).encode()).digest()
    family = STRATA[digest[0] % len(STRATA)]
    p = {"stratum": family, "rate_ref": float(rng.uniform(.03, .12)),
         "activation_j_mol": float(rng.uniform(45000., 70000.)),
         "deactivation_ref": float(rng.uniform(.007, .025)), "deactivation_activation_j_mol": 30000.,
         "saturation": .4, "gain": float(rng.uniform(.9, 1.1)), "offset": float(rng.uniform(-.018, .018)),
         "gain_slope": float(rng.uniform(-.0065, .0065)), "offset_slope": float(rng.uniform(-.0014, .0014)),
         "jump_event": 7, "gain_jump": 0., "offset_jump": 0., "fractions": [1.], "decay_multipliers": [1.]}
    if family == "instrument_jump":
        p["gain_jump"] = float(rng.choice([-1., 1.]) * rng.uniform(.10, .15))
        p["offset_jump"] = float(rng.choice([-1., 1.]) * rng.uniform(.022, .036))
        p["jump_event"] = int(rng.integers(5, 12))
    elif family == "two_site":
        f = float(rng.uniform(.50, .68))
        p["fractions"] = [f, 1-f]
        p["decay_multipliers"] = [float(rng.uniform(.18, .30)), float(rng.uniform(3.8, 5.2))]
    return p


def reaction_integral(activity, rate, decay, duration):
    """Return product and residual activity, including the exact zero-decay limit."""
    x = decay * duration
    factor = 1. if x == 0. else -math.expm1(-x) / x
    return activity * rate * duration * factor, activity * math.exp(-x)


def reaction_step(activities, event, parameters):
    p, t, c = parameters, event["temperature_k"], event["feed_concentration"]
    rate = p["rate_ref"] * math.exp(p["activation_j_mol"] / GAS_CONSTANT * (1/500. - 1/t)) * c / (1+p["saturation"]*c)
    decay = p["deactivation_ref"] * c * math.exp(p["deactivation_activation_j_mol"] / GAS_CONSTANT * (1/500. - 1/t))
    values = [reaction_integral(a, rate, decay*m, event["duration_min"]) for a, m in zip(activities, p["decay_multipliers"])]
    product = sum(weight*v[0] for weight, v in zip(p["fractions"], values))
    return float(product), [v[1] for v in values]


def instrument(parameters, event_index):
    p, x = parameters, event_index-1
    jump = event_index >= p["jump_event"]
    return p["gain"]+p["gain_slope"]*x+p["gain_jump"]*jump, p["offset"]+p["offset_slope"]*x+p["offset_jump"]*jump


def run_history(spec, parameters):
    # All mutation is local to this call. No World or module state is changed.
    activities = {coupon: [1.] * len(parameters["fractions"]) for coupon in COUPONS}
    results = []
    for index, event in enumerate(spec["events"], start=1):
        if event["kind"] == "reaction":
            coupon = event["coupon_id"]
            value, activities[coupon] = reaction_step(activities[coupon], event, parameters)
        else:
            value = 0. if event["kind"] == "blank" else STANDARD_RESPONSE
        gain, offset = instrument(parameters, index)
        signal = gain*value+offset
        if not math.isfinite(signal):
            raise RuntimeError("laboratory calculation failed")
        results.append(signal)
    return np.asarray([[results[i-1]] for i in spec["event_indices"]])

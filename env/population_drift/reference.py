"""Independent uniformization and analytic references; no production imports."""

import math

import numpy as np
from scipy.special import gammaln

MAX_TERMS = 2500
TAIL_LOG_TARGET = 40.


def _observe(probabilities, size):
    rows = []
    for row in probabilities:
        mean = sum(float(p)*i/size for i, p in enumerate(row))
        mixed = sum(float(p)*2*(i/size)*(1-i/size) for i, p in enumerate(row))
        rows.append([mean, mixed, float(row[-1]), float(row[0])])
    return np.asarray(rows)


def uniformization(parameters, spec):
    """Trusted canonical inputs, independently derived birth/death probabilities.

    Summation uses log-Poisson weights, so large N*t never requires a nonzero
    exp(-N*t) starting value. The upper tail is fixed before any observations.
    """
    n, initial = spec["population_size"], spec["initial_A"]
    up, down = [], []
    # Independently enumerate parent/offspring type events, not z_i from kernel.
    m, a = parameters.mutation_probability, spec["newborn_flip_probability"]
    remain = (1-m)*(1-a)+m*a
    change = m*(1-a)+(1-m)*a
    for i in range(n+1):
        ratio = math.exp(parameters.selection+parameters.frequency_effect*(2*i/n-1)+spec["selection_bias"])
        parent_a = i*ratio/(i*ratio+(n-i))
        born_a = parent_a*remain+(1-parent_a)*change
        born_b = (1-parent_a)*remain+parent_a*change
        up.append((n-i)/n*born_a)
        down.append(i/n*born_b)
    up, down = np.asarray(up), np.asarray(down)
    stay = 1-up-down
    if min(float(up.min()), float(down.min()), float(stay.min())) < -2e-15:
        raise RuntimeError("independent uniformization transition probabilities invalid")
    maximum = n*max(spec["times"])
    final = int(math.ceil(maximum+math.sqrt(2*maximum*TAIL_LOG_TARGET)+2*TAIL_LOG_TARGET)) if maximum else 0
    if final+1 > MAX_TERMS:
        raise RuntimeError("independent uniformization term budget exhausted")
    powers = np.empty((final+1, n+1))
    powers[0] = 0.
    powers[0, initial] = 1.
    for k in range(1, final+1):
        previous = powers[k-1]
        current = previous*stay
        current[1:] += previous[:-1]*up[:-1]
        current[:-1] += previous[1:]*down[1:]
        powers[k] = current
    indices = np.arange(final+1, dtype=float)
    log_factorials = gammaln(indices+1)
    probabilities, tails, masses = [], [], []
    for t in spec["times"]:
        rate_time = n*t
        if rate_time == 0:
            weights = np.zeros(final+1)
            weights[0] = 1.
            bound = 0.
        else:
            weights = np.exp(-rate_time+indices*math.log(rate_time)-log_factorials)
            bound = math.exp(-rate_time+(final+1)*(1+math.log(rate_time)-math.log(final+1)))
        probabilities.append(weights @ powers)
        tails.append(bound)
        masses.append(float(weights.sum()))
    probabilities = np.asarray(probabilities)
    if not np.isfinite(probabilities).all() or np.max(np.abs(probabilities.sum(axis=1)-1)) > 2e-11:
        raise RuntimeError("independent uniformization lost probability mass")
    return {"values": _observe(probabilities, n), "probabilities": probabilities,
            "diagnostics": {"terms": final+1, "maximum_lambda": maximum,
                            "tail_chernoff_bounds": tails, "poisson_weight_sums": masses,
                            "maximum_distribution_mass_error": float(np.max(np.abs(probabilities.sum(axis=1)-1)))}}


def neutral_moments(spec):
    x = spec["initial_A"]/spec["population_size"]
    return {"channels": ["mean_A_frequency", "mean_mixedness"],
            "values": [[x, 2*x*(1-x)*math.exp(-2*t/spec["population_size"])] for t in spec["times"]]}


def neutral_n2(spec):
    if spec["population_size"] != 2 or spec["initial_A"] != 1:
        raise ValueError("N2 analytic reference needs N2 and one initial A")
    probabilities = np.asarray([[(1-math.exp(-t))/2, math.exp(-t), (1-math.exp(-t))/2] for t in spec["times"]])
    return {"values": _observe(probabilities, 2), "probabilities": probabilities}

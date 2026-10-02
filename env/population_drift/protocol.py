"""Public ensemble instrument contract; no hidden mechanism menu."""

import math
import numbers

import numpy as np

VERSION = "population_drift-0.1.0-experimental"
AXIS_FIELD = "times"
CHANNELS = ("mean_A_frequency", "mean_mixedness", "boundary_A", "boundary_B")
SCALES = (1., 1., 1., 1.)
NOISE_STD = (.002, .002, .002, .002)


def integer(value, name, low=0, high=2**63-1):
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, numbers.Integral) or not low <= int(value) <= high:
        raise ValueError(f"{name} must be an integer in [{low}, {high}]")
    return int(value)


def number(value, low, high, name):
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, numbers.Real):
        raise ValueError(f"{name} must be a finite real number")
    try:
        value = float(value)
    except (OverflowError, ValueError):
        raise ValueError(f"{name} must be a finite real number") from None
    if not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f"{name} must be in [{low}, {high}]")
    return value


def validate_spec(spec):
    required = {"population_size", "initial_A", AXIS_FIELD}
    if not isinstance(spec, dict) or not required <= set(spec) or set(spec)-required-{"selection_bias", "newborn_flip_probability"}:
        raise ValueError("expected population_size, initial_A, times and optional selection_bias, newborn_flip_probability")
    size = integer(spec["population_size"], "population_size", 2, 32)
    initial = integer(spec["initial_A"], "initial_A", 0, size)
    raw = spec[AXIS_FIELD]
    if not isinstance(raw, list) or not 1 <= len(raw) <= 33:
        raise ValueError("times must be a list of 1..33 samples")
    times = [number(t, 0, 60, "time") for t in raw]
    if any(b <= a for a, b in zip(times, times[1:])):
        raise ValueError("times must be strictly increasing")
    return {"population_size": size, "initial_A": initial, AXIS_FIELD: times,
            "selection_bias": number(spec.get("selection_bias", 0), -.5, .5, "selection_bias"),
            "newborn_flip_probability": number(spec.get("newborn_flip_probability", 0), 0, .1, "newborn_flip_probability")}


def assigned_initial(spec):
    n, k = spec["population_size"], spec["initial_A"]
    x = k/n
    return [x, 2*x*(1-x), float(k == n), float(k == 0)]


def example():
    return {"population_size": 12, "initial_A": 6, "times": [0., 1., 3., 6., 12., 24., 48., 60.],
            "selection_bias": 0., "newborn_flip_probability": 0.}


def describe():
    return {"name": "population_drift", "version": VERSION,
        "research_prompt": "Investigate the ensemble response of sealed finite two-type populations. Vary preparation, population size and calibrated controls; propose quantitative accounts and experiments that distinguish them, and state what remains unresolved.",
        "channels": list(CHANNELS), "scales": list(SCALES), "noise_std": list(NOISE_STD),
        "axis": {"name": "time", "unit": "replacement-clock units", "rows": "requested times"},
        "semantics": [
            "Each call freshly prepares a large ideal ensemble of well-mixed, fixed-size populations of types A and B. Every replicate begins with exactly initial_A copies of A among population_size individuals. Apparatus properties stay fixed across calls; no state carries over.",
            "One time unit corresponds to population_size replacement attempts on average per replicate, on a Poisson clock. At an attempt one offspring replaces one uniformly chosen individual. The potential parent and replaced individual are sampled independently, so they may be the same individual. Events that leave the A count unchanged still belong to the clock.",
            "selection_bias adds a known log relative reproductive weighting for type A: exp(selection_bias) multiplies each A individual's reproductive weight relative to B, before selecting a parent. It is constant during one call.",
            "newborn_flip_probability independently swaps a newborn's A/B label with the stated probability after its underlying inheritance process and before replacement. This symmetric calibrated intervention is constant during one call; it does not act directly on existing individuals.",
            "Readouts are exact expectation functionals of the finite-population ensemble distribution, plus sensor noise. They are not one realized stochastic trajectory, a finite sample of replicate populations, or a wet-lab experiment. Finite-population variation is integrated into that distribution, not added to the sensor noise.",
            "mean_A_frequency is E[k/N]. mean_mixedness is E[2(k/N)(1-k/N)], the probability of unlike labels when sampling twice WITH replacement inside each replicate, averaged over replicates. It is not 2E[k/N](1-E[k/N]) and is not directly the variance between replicates.",
            "boundary_A is the current ensemble probability that k=N; boundary_B is the current probability that k=0. These are current occupancies, not first-passage probabilities. Reaching a boundary need not mean permanent fixation or absorption, because the underlying process or the newborn flip intervention can allow exit.",
            "Independent additive Gaussian sensor noise has SD0.002 on every coordinate at every requested time, including time zero. It is not clipped; noisy probabilities may leave [0,1] or violate exact clean constraints. There is no finite-replicate/binomial sampling noise. New measurements receive fresh sensor noise.",
            "Sample times do not change evolution. The clean time-zero vector is assigned by preparation: [x0,2*x0*(1-x0),1(initial_A=N),1(initial_A=0)]. Predicting assigned facts alone does not identify the unknown response. Time zero is optional.",
            "A finite set of ensemble moments and boundary occupancies need not uniquely identify transition rates or microscopic mechanisms. Population size remains fixed; demographic growth, spatial structure and empirical organism properties are outside this apparatus."
        ],
        "schema": {"required": ["population_size", "initial_A", AXIS_FIELD],
            "optional": {"selection_bias": 0., "newborn_flip_probability": 0.}, "additional_fields": False,
            "population_size": {"integer_range": [2, 32]}, "initial_A": "integer from0 through population_size",
            AXIS_FIELD: {"length": [1, 33], "range": [0, 60], "strictly_increasing": True},
            "selection_bias": {"range": [-.5, .5]}, "newborn_flip_probability": {"range": [0, .1]},
            "validation": "Reject booleans, nonfinite/nonreal numbers, unknown fields, noninteger counts, oversized arrays and duplicate/unordered times."},
        "cost": "8+n_times*ceil((population_size+1)/8)+ceil(last_time/10); maximum179",
        "examples": [example(), {"population_size": 20, "initial_A": 0, "times": [0., 1., 5., 20., 60.], "newborn_flip_probability": .02}],
        "limitations": "Synthetic expectation readout, not individual-path data or empirical population genetics. No demographic growth, spatial structure, diploidy, linked loci, recombination or measurement of an actual organism is represented."}

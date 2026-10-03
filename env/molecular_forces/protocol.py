"""Public apparatus only; hidden potential families are intentionally absent."""
import math
import numbers
import numpy as np

VERSION = "molecular_forces-0.1.0"
CHANNELS = ("energy_ev",) + tuple("f%d%s_ev_per_a" % (i, a) for i in (1, 2, 3) for a in "xyz")
SCALES = (0.3,) + (1.0,) * 9
NOISE_STD = (0.00035,) + (0.0007,) * 9
MAX_ROWS = 8


def number(value, name, lo, hi):
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, numbers.Real):
        raise ValueError("%s must be a finite real number" % name)
    try:
        value = float(value)
    except (ValueError, OverflowError):
        raise ValueError("%s must be a finite real number" % name) from None
    if not math.isfinite(value) or not lo <= value <= hi:
        raise ValueError("%s must be in [%g, %g]" % (name, lo, hi))
    return value


def integer(value, name, lo, hi):
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, numbers.Integral) or not lo <= value <= hi:
        raise ValueError("%s must be an integer in [%d, %d]" % (name, lo, hi))
    return int(value)


def validate_spec(spec):
    if not isinstance(spec, dict) or set(spec) != {"configurations", "configuration_ids", "temperature_k"}:
        raise ValueError("spec must contain exactly configurations, configuration_ids, temperature_k")
    temperature = number(spec["temperature_k"], "temperature_k", 180, 900)
    raw = spec["configurations"]
    if not isinstance(raw, (list, tuple)) or not 1 <= len(raw) <= MAX_ROWS:
        raise ValueError("configurations must contain 1 to 8 configurations")
    ids = spec["configuration_ids"]
    if not isinstance(ids, (list, tuple)) or len(ids) != len(raw):
        raise ValueError("configuration_ids must match configuration count")
    ids = [integer(x, "configuration_ids entry", 0, MAX_ROWS - 1) for x in ids]
    if ids != list(range(len(raw))):
        raise ValueError("configuration_ids must be consecutive indices starting at zero")
    configurations = []
    for points in raw:
        if not isinstance(points, (list, tuple)) or len(points) != 3:
            raise ValueError("each configuration must contain three particle positions")
        canonical = []
        for row in points:
            if not isinstance(row, (list, tuple)) or len(row) != 3:
                raise ValueError("each position must contain x, y, z")
            canonical.append([number(x, "coordinate", -5.5, 5.5) for x in row])
        p = np.asarray(canonical)
        distances = [float(np.linalg.norm(p[i] - p[j])) for i, j in ((0, 1), (0, 2), (1, 2))]
        if any(d < 2.2 - 1e-12 or d > 5.4 + 1e-12 for d in distances):
            raise ValueError("all pair distances must be between 2.2 and 5.4 angstrom")
        configurations.append(canonical)
    return {"configurations": configurations, "configuration_ids": ids, "temperature_k": temperature}


def example():
    return {"configurations": [[[0., 0., 0.], [3., 0., 0.], [1.5, 2.598076211353316, 0.]],
                               [[0., 0., 0.], [3., 0., 0.], [0., 3., 0.]]],
            "configuration_ids": [0, 1], "temperature_k": 450.}


def describe():
    return {"name": "molecular_forces", "version": VERSION,
            "description": "A constrained three-particle laboratory. Choose particle positions and temperature, measure energy and forces, and investigate which patterns transfer to new geometries and conditions.",
            "channels": list(CHANNELS), "channel_units": ["eV"] + ["eV/angstrom"] * 9,
            "axis": {"name": "configuration index", "unit": "index", "rows": "configuration_ids; indices label separate prepared geometries, not elapsed time"},
            "scales": list(SCALES), "noise_std": list(NOISE_STD),
            "noise": "Independent additive Gaussian readout noise in every returned cell; no clipping or process noise. Repeated readouts with fresh measurement keys are independent.",
            "cost": "One unit per configuration, at most eight configurations per request.",
            "apparatus": {
                "preparation": "Each row independently positions three identical constrained particles at its exact supplied Cartesian positions and holds the temperature fixed. No state carries between rows or requests.",
                "readout": "Total effective energy and force on each particle in the laboratory Cartesian frame. Force channels are ordered particle1 xyz, particle2 xyz, particle3 xyz. Energy reference is fixed across queries. No output cell is an assigned control value.",
                "temperature": "The temperature control labels the prepared environment; there are no fluctuating particle trajectories or thermal sampling. Do not interpret these data as direct measurements of bulk thermodynamics.",
                "positions": "Positions are exact controls in angstrom. Translation, rotation, relabeling, changes in separation and shape are allowed within bounds. Particles stay fixed during a readout; zero z coordinates do not directly assign measured z forces.",
                "scope": "Infer responses only inside the accessible domain; queries do not include dynamics, chemical changes, or arbitrarily separated particles."},
            "schema": {"required": ["configurations", "configuration_ids", "temperature_k"], "additional_fields": False,
                       "configurations": {"shape": "[n,3,3]", "n": [1, 8], "coordinate_bounds_a": [-5.5, 5.5], "all_pair_distance_bounds_a": [2.2, 5.4]},
                       "configuration_ids": "[0,1,...,n-1]; only row labels, not a physical scan coordinate",
                       "temperature_k": {"range": [180, 900], "unit": "K"},
                       "validation": "Only finite real numeric controls; booleans and unknown fields rejected."},
            "examples": [example()],
            "discovery": "You may vary geometry and temperature, replicate measurements, test competing explanations, or investigate where a predictive model stops working. No named potential family or uniquely correct explanation is prescribed."}

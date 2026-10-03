"""Public survey apparatus; no hidden occupancy or detection formulas."""

import math
import numbers

import numpy as np

VERSION = "field_ecology-0.1.0-experimental"
AXIS_FIELD = "habitat_values"
CHANNELS = ("first_visit_detection", "any_visit_detection", "all_visits_detection")
SCALES = (1.0, 1.0, 1.0)
PANEL_SIZE = 64
NOISE_STD = (0.0625, 0.0625, 0.0625)  # Rigorous SD upper bounds, not Gaussian sigmas.
METHOD_COST = {"rapid": 1, "intensive": 2}


def integer(value, name, low=0, high=2**63-1):
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, numbers.Integral) or not low <= int(value) <= high:
        raise ValueError("%s must be an integer in [%d, %d]" % (name, low, high))
    return int(value)


def number(value, low, high, name):
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, numbers.Real):
        raise ValueError("%s must be a finite real number" % name)
    try:
        value = float(value)
    except (OverflowError, ValueError):
        raise ValueError("%s must be a finite real number" % name) from None
    if not math.isfinite(value) or not low <= value <= high:
        raise ValueError("%s must lie in [%g, %g]" % (name, low, high))
    return value


def validate_spec(spec):
    if not isinstance(spec, dict) or set(spec) != {AXIS_FIELD, "visits"}:
        raise ValueError("expected exactly habitat_values and visits")
    raw = spec[AXIS_FIELD]
    if not isinstance(raw, list) or not 1 <= len(raw) <= 24:
        raise ValueError("habitat_values must contain 1..24 values")
    habitat = [number(v, -1.6, 1.6, "habitat value") for v in raw]
    if any(b <= a for a, b in zip(habitat, habitat[1:])):
        raise ValueError("habitat_values must be strictly increasing")
    visits = spec["visits"]
    if not isinstance(visits, list) or not 1 <= len(visits) <= 3:
        raise ValueError("visits must contain 1..3 survey methods")
    if any(not isinstance(v, str) or v not in METHOD_COST for v in visits):
        raise ValueError("each visit must use rapid or intensive")
    return {AXIS_FIELD: habitat, "visits": list(visits)}


def example():
    return {AXIS_FIELD: [-1.5, -.75, 0.0, .75, 1.5], "visits": ["rapid", "rapid", "intensive"]}


def describe():
    return {
        "name": "field_ecology", "version": VERSION,
        "research_prompt": "Investigate species occurrence and survey reliability across habitats in a repeatable synthetic field laboratory. Choose habitat strata and repeat-visit methods. Explain observed survey patterns, make quantitative predictions for new survey designs, and state which ecological interpretations remain unresolved.",
        "channels": list(CHANNELS), "scales": list(SCALES), "noise_std": list(NOISE_STD),
        "axis": {"name": "habitat covariate", "unit": "dimensionless standardized habitat index", "rows": "requested habitat_values; this axis is not time"},
        "units": {channel: "fraction of 64 sampled sites" for channel in CHANNELS},
        "sampling": {"sites_per_habitat": PANEL_SIZE, "independent_unit": "site within a habitat panel", "repeat_unit": "new independent ecological panels on every experiment", "distribution": "joint bounded fractions from shared binary detection histories; not additive Gaussian", "marginal_standard_deviation_upper_bound": list(NOISE_STD), "bias_bound": [0.0, 0.0, 0.0]},
        "semantics": [
            "Each requested habitat value selects 64 independent sites with that exact published covariate. Different rows use distinct independent groups. Each new experiment draws fresh sites from the same instance's population laws; it does not revisit sites from an earlier call.",
            "Within each habitat row, all listed visits survey the SAME 64 sites in order. A site's presence/absence state stays fixed through these 1..3 visits. Survey methods do not alter occupancy; there are no colonizations, extinctions or observer-induced changes during the visit sequence.",
            "A truly absent species cannot yield a positive detection in this instrument. An occupied site can be missed. Conditional on a site's occupancy and habitat, detections on different visits are independent; detection reliability can depend on method and habitat. No method is declared perfect.",
            "first_visit_detection is the fraction of the 64 sites detected on the first listed visit; any_visit_detection is the fraction detected at least once; all_visits_detection is the fraction detected on every listed visit. Values are exact integer multiples of 1/64, without additional readout noise or rounding.",
            "Within a row these channels are correlated: all_visits_detection <= first_visit_detection <= any_visit_detection in every realization. With one visit all three are identical by definition. These identities are instrument bookkeeping, not unknown ecological laws.",
            "Each channel is a mean of 64 independent binary site indicators, hence has marginal standard deviation at most 1/(2*sqrt(64))=0.0625. The reported noise_std values are conservative upper bounds, not exact variances or Gaussian standard deviations. There is no clipping bias. Replicate experiments redraw both occupancy and detections independently.",
            "Choosing a habitat stratum is population sampling, not an intervention that changes an individual site's habitat. Association with habitat alone does not establish a causal effect. Habitat zero is a legal covariate, not an assigned initial state."
        ],
        "schema": {"type": "object", "required": [AXIS_FIELD, "visits"], "additional_fields": False,
                   AXIS_FIELD: {"length": [1,24], "range": [-1.6,1.6], "order": "strictly increasing"},
                   "visits": {"length": [1,3], "choices": ["rapid", "intensive"], "order": "visit order; repeated methods allowed"},
                   "validation": "Finite real habitat values, no booleans, no unknown fields or methods."},
        "cost": "4 + number of habitat strata * sum(method batch costs); rapid costs 1, intensive 2 per 64-site visit batch. Maximum 148 units. Actual site visits equal 64 * strata * number of visits, at most 4608.",
        "examples": [example(), {AXIS_FIELD: [-1.0,0.0,1.0], "visits": ["intensive", "intensive"]}],
        "limitations": "Synthetic independent-site populations, not a fixed georeferenced field census. No spatial correlations, accessibility covariate, abundance estimation, false-positive detections or time-varying occupancy are modeled. Aggregate histories constrain effective detection and occupancy accounts but do not prove a unique ecological cause."
    }

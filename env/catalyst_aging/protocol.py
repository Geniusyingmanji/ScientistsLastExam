"""Public laboratory apparatus and bounded whole-history validation."""
import math
import numbers
import numpy as np

VERSION = "catalyst_aging-0.1.0"
CHANNELS = ("measured_signal",)
SCALES = (1.5,)
NOISE_STD = (0.003,)
COUPONS = ("A", "B", "C", "D")
STANDARD_RESPONSE = 1.5
MAX_EVENTS = 24


def number(value, name, lo, hi):
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, numbers.Real):
        raise ValueError("%s must be a finite real number" % name)
    try:
        value = float(value)
    except (OverflowError, ValueError):
        raise ValueError("%s must be a finite real number" % name) from None
    if not math.isfinite(value) or not lo <= value <= hi:
        raise ValueError("%s must be in [%g, %g]" % (name, lo, hi))
    return value


def integer(value, name, lo, hi):
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, numbers.Integral) or not lo <= value <= hi:
        raise ValueError("%s must be an integer in [%d, %d]" % (name, lo, hi))
    return int(value)


def validate_spec(spec):
    if not isinstance(spec, dict) or set(spec) != {"events", "event_indices"}:
        raise ValueError("spec must contain exactly events and event_indices")
    raw = spec["events"]
    if not isinstance(raw, (list, tuple)) or not 1 <= len(raw) <= MAX_EVENTS:
        raise ValueError("events must be an array of length1 to24")
    events, uses = [], {name: 0 for name in COUPONS}
    for event in raw:
        if not isinstance(event, dict) or event.get("kind") not in ("blank", "standard", "reaction"):
            raise ValueError("event kind must be blank, standard or reaction")
        kind = event["kind"]
        if kind in ("blank", "standard"):
            if set(event) != {"kind"}:
                raise ValueError("blank and standard events contain exactly kind")
            events.append({"kind": kind})
        else:
            fields = {"kind", "coupon_id", "temperature_k", "feed_concentration", "duration_min"}
            if set(event) != fields:
                raise ValueError("reaction needs exactly kind, coupon_id, temperature_k, feed_concentration, duration_min")
            coupon = event["coupon_id"]
            if not isinstance(coupon, str) or coupon not in COUPONS:
                raise ValueError("coupon_id must be A, B, C or D")
            uses[coupon] += 1
            if uses[coupon] > 6:
                raise ValueError("each coupon permits at most six reaction events")
            events.append({"kind": kind, "coupon_id": coupon,
                           "temperature_k": number(event["temperature_k"], "temperature_k", 440., 560.),
                           "feed_concentration": number(event["feed_concentration"], "feed_concentration", .1, 1.2),
                           "duration_min": number(event["duration_min"], "duration_min", 2., 15.)})
    indices = spec["event_indices"]
    if not isinstance(indices, (list, tuple)) or not 1 <= len(indices) <= len(events):
        raise ValueError("event_indices must select one or more events")
    indices = [integer(i, "event index", 1, len(events)) for i in indices]
    if any(b <= a for a, b in zip(indices, indices[1:])):
        raise ValueError("event_indices must be strictly increasing")
    return {"events": events, "event_indices": indices}


def reaction(coupon="A", temperature=500., concentration=.6, duration=8.):
    return {"kind": "reaction", "coupon_id": coupon, "temperature_k": temperature,
            "feed_concentration": concentration, "duration_min": duration}


def example():
    events = [{"kind": "blank"}, {"kind": "standard"}, reaction(), reaction(),
              {"kind": "blank"}, {"kind": "standard"}, reaction("B"), reaction()]
    return {"events": events, "event_indices": list(range(1, len(events)+1))}


def describe():
    return {"name": "catalyst_aging", "version": VERSION,
            "description": "A repeatable coupon laboratory. Plan full sequences of reactions, blanks and calibration standards to study how measured production changes with conditions and prior coupon use.",
            "channels": list(CHANNELS), "channel_units": ["normalized product signal unit"],
            "axis": {"name": "event index", "unit": "serial event", "rows": "requested1-based event_indices; each row is the measurement at completion of that event, not a sample time"},
            "scales": list(SCALES), "noise_std": list(NOISE_STD),
            "noise": "Independent additive Gaussian signal readout noise with sigma0.003; no clipping or process noise. A new measurement key gives independent repeated readouts of the same deterministic whole history.",
            "cost": "One unit per scheduled event, including unobserved preparation and calibration events; selecting fewer rows does not reduce cost.",
            "apparatus": {
                "reset": "EVERY query starts a fresh identically parameterized lab, four fresh identical coupons A–D, and the same instrument reset. There is no continuation across calls. To study history, include the complete ordered history in one query.",
                "execution": "Execute all listed events serially in exactly the supplied order. Reaction conditions remain constant for that event. There is no concurrent execution or completion-order ambiguity.",
                "coupon_history": "Reaction use may change a coupon irreversibly. Only the selected coupon experiences that reaction; other coupons and coupons at rest do not age. At most six reactions per coupon. Reaction product is collected separately for each event; product is not carried into the next event.",
                "feed": "Feed concentration is held constant by replenishment during an event; this is not a closed-batch substrate-depletion assay. Temperature and duration are exact controls.",
                "instrument": "Every event advances the instrument's discrete event counter, including blanks and standards. Instrument state may vary with that counter; it is not a function of elapsed reaction minutes. Each measured signal is obtained at completion using that event's instrument response. Calibrations do not reset or repair the instrument.",
                "blank": "A blank supplies zero product to the instrument and consumes no coupon. Its measured signal can be nonzero and is not an assigned output.",
                "standard": "A stable standard supplies exactly1.5 normalized product units to the instrument and consumes no coupon. Its measured signal depends on the instrument and is not directly assigned to1.5.",
                "readout": "Only measured_signal is returned. Activity, true product, instrument gain and offset are not separately observed. Unrequested events still execute and affect subsequent history."},
            "schema": {"required": ["events", "event_indices"], "additional_fields": False,
                       "events": {"length": [1, 24], "kinds": ["blank", "standard", "reaction"],
                                  "blank_and_standard_fields": ["kind"],
                                  "reaction_fields": ["kind", "coupon_id", "temperature_k", "feed_concentration", "duration_min"],
                                  "coupon_id": list(COUPONS), "maximum_reactions_per_coupon": 6,
                                  "temperature_k": [440., 560.], "feed_concentration": [.1, 1.2], "duration_min": [2., 15.]},
                       "event_indices": "Strictly increasing integer subset of1..len(events); each selected event returns one measured row.",
                       "validation": "Finite real controls only; booleans and unknown fields are rejected."},
            "examples": [example()],
            "discovery": "Compare repeated use, fresh coupons, changed reaction conditions and interleaved instrument checks. Build and test predictions for new complete histories; no unique kinetic formula or named mechanism is prescribed."}

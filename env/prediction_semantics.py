"""Conservative public-control audit of prediction cells, independent of scoring.

This module has no World, kernel, seed, observation, or target input. It marks
exact clean-response constants prescribed by the published instrument contract,
not realized noisy measurements. Unknown means *not certified by these rules*;
it does not assert that every remaining cell requires parameter inference.

Rules are explicit for coupled_oscillators-0.2.0 and ising_spin-0.2.0 only.
No general equation solver, zero-equilibrium inference, approximate saturation,
parameter fitting, or extrapolation to another environment is performed. The
legacy row summary reproduces the 0.3/0.4 prediction_metrics row-selection rule
for audit purposes only; it is not a proposed replacement score.
"""
from collections import Counter
from copy import deepcopy
import math
import numbers


PROTOCOL = "public-prediction-semantics-audit-0.1"
_OSCILLATORS = tuple("ABCD")
_SPINS = tuple("ABCDEF")
SUPPORTED = {
    "coupled_oscillators": {"version": "coupled_oscillators-0.2.0", "axis": "times", "max_rows": 241,
                            "axis_bounds": (0.0, 24.0),
                            "channels": tuple(prefix + node for prefix in ("x_", "v_") for node in _OSCILLATORS)},
    "ising_spin": {"version": "ising_spin-0.2.0", "axis": "temperatures", "max_rows": 32,
                   "axis_bounds": (0.35, 6.0),
                   "channels": tuple("m_" + node for node in _SPINS) +
                               tuple("c_" + a + "_" + b for i, a in enumerate(_SPINS) for b in _SPINS[i + 1:])},
}


def policy_description():
    return {"protocol": PROTOCOL, "supported": deepcopy(SUPPORTED),
            "interpretation": "Exact clean-response values prescribed by public controls; noisy observed samples remain random.",
            "oscillator_rules": "A clamp fixes x_NODE=v_NODE=0 at all times. At exactly t=0, unclamped x/v equal the prescribed initial position/velocity, default zero.",
            "spin_rules": "A clamped mean equals its spin value. A raw pair moment with both endpoints clamped equals their product. A single clamped endpoint leaves the numeric pair value unknown because the free endpoint mean remains unknown.",
            "unsupported": "Other environments, other versions, and unrecognized channels are unknown; no inferred generalization.",
            "unknown_scope": "Unknown means unclassified by these narrow direct-assignment rules, not a proof of mechanism dependence or algebraic independence.",
            "score_relation": "The original metric averages squared normalized errors over retained cells within each experiment, applies its exponential transform, then averages experiments equally. Cell fractions are not score fractions.",
            "legacy_rows": "Drop the first row only when there is more than one row and its axis coordinate equals zero exactly. A sole t=0 row is retained; Ising temperature rows are retained.",
            "changes_existing_scoring": False, "certifies_mechanism_or_agent_shortcut_use": False}


def _number(value):
    if isinstance(value, bool) or not isinstance(value, numbers.Real):
        raise ValueError("public numbers must be finite real values")
    try:
        value = float(value)
    except (ValueError, OverflowError):
        raise ValueError("public numbers must be finite real values") from None
    if not math.isfinite(value):
        raise ValueError("public numbers must be finite real values")
    return value


def _vector(value, count, lower, upper):
    if not isinstance(value, (list, tuple)) or len(value) != count:
        raise ValueError("invalid public control vector")
    values = [_number(item) for item in value]
    if any(not lower <= item <= upper for item in values):
        raise ValueError("public control vector outside bounds")
    return values


def _bonds(values, nodes, *, suppression):
    if not isinstance(values, (list, tuple)) or len(values) > len(nodes) * (len(nodes) - 1) // 2:
        raise ValueError("invalid public bond controls")
    seen = set()
    for item in values:
        if suppression:
            if not isinstance(item, dict) or set(item) != {"nodes", "fraction"} or not 0 <= _number(item["fraction"]) <= 1:
                raise ValueError("invalid public bond suppression")
            item = item["nodes"]
        if (not isinstance(item, (list, tuple)) or len(item) != 2 or
                any(not isinstance(node, str) or node not in nodes for node in item) or item[0] == item[1]):
            raise ValueError("invalid public bond pair")
        pair = tuple(sorted(item))
        if pair in seen:
            raise ValueError("duplicate public bond pair")
        seen.add(pair)


def _oscillator_controls(spec):
    allowed = {"times", "initial_position", "initial_velocity", "mass_add", "damping_add", "cut_edges", "clamp", "drive"}
    if set(spec) - allowed:
        raise ValueError("unknown oscillator spec field")
    clamp = spec.get("clamp", [])
    if (not isinstance(clamp, (list, tuple)) or len(clamp) > 4 or
            any(not isinstance(node, str) or node not in _OSCILLATORS for node in clamp) or len(set(clamp)) != len(clamp)):
        raise ValueError("invalid oscillator clamp")
    position = _vector(spec.get("initial_position", [0] * 4), 4, -1, 1)
    velocity = _vector(spec.get("initial_velocity", [0] * 4), 4, -2, 2)
    if any(position[_OSCILLATORS.index(node)] != 0 or velocity[_OSCILLATORS.index(node)] != 0 for node in clamp):
        raise ValueError("clamped initial state must be zero")
    _vector(spec.get("mass_add", [0] * 4), 4, 0, 3)
    _vector(spec.get("damping_add", [0] * 4), 4, 0, 2)
    _bonds(spec.get("cut_edges", []), _OSCILLATORS, suppression=False)
    drive = spec.get("drive")
    if drive is not None:
        if not isinstance(drive, dict) or set(drive) != {"node", "amplitude", "frequency", "phase"}:
            raise ValueError("invalid oscillator drive")
        if (drive["node"] not in _OSCILLATORS or not -2 <= _number(drive["amplitude"]) <= 2 or
                not 0 <= _number(drive["frequency"]) <= 2 or not -math.pi <= _number(drive["phase"]) <= math.pi or
                drive["node"] in clamp and drive["amplitude"] != 0):
            raise ValueError("invalid oscillator drive")
    return clamp, position, velocity


def _spin_controls(spec):
    if set(spec) - {"temperatures", "external_field", "clamp", "suppress_bonds"}:
        raise ValueError("unknown spin spec field")
    clamp = spec.get("clamp", {})
    if (not isinstance(clamp, dict) or len(clamp) > 6 or
            any(node not in _SPINS or isinstance(value, bool) or not isinstance(value, numbers.Integral) or value not in (-1, 1)
                for node, value in clamp.items())):
        raise ValueError("invalid spin clamp")
    _vector(spec.get("external_field", [0] * 6), 6, -2, 2)
    _bonds(spec.get("suppress_bonds", []), _SPINS, suppression=True)
    return clamp


def classify_cells(environment, spec, channels, axis_field, *, world_version=None):
    """Return detached masks/values/reasons with the requested row/channel shape.

    Supported specs are checked against the documented public control bounds.
    Unknown environment/version inputs receive shape validation only and all
    cells remain unknown. Omitting world_version explicitly uses the supported
    contract version stated in policy_description, rather than querying a World.
    """
    if not isinstance(environment, str) or not environment or not isinstance(axis_field, str) or not axis_field:
        raise ValueError("environment and axis_field must be nonempty strings")
    if not isinstance(spec, dict) or axis_field not in spec:
        raise ValueError("public spec must contain the declared axis")
    if (not isinstance(channels, (list, tuple)) or not 1 <= len(channels) <= 256 or
            any(not isinstance(channel, str) or not 1 <= len(channel) <= 100 for channel in channels) or len(set(channels)) != len(channels)):
        raise ValueError("invalid public channel list")
    rule = SUPPORTED.get(environment)
    supported = rule is not None and (world_version is None or world_version == rule["version"])
    if supported and axis_field != rule["axis"]:
        raise ValueError("axis does not match the declared instrument")
    axis = spec[axis_field]
    maximum = rule["max_rows"] if supported else 4096
    if not isinstance(axis, (list, tuple)) or not 1 <= len(axis) <= maximum:
        raise ValueError("invalid public axis shape")
    axis = [_number(value) for value in axis]
    if any(left >= right for left, right in zip(axis, axis[1:])):
        raise ValueError("public axis must be strictly increasing")
    if supported and any(not rule["axis_bounds"][0] <= value <= rule["axis_bounds"][1] for value in axis):
        raise ValueError("public axis outside instrument bounds")
    default_reason = "unknown_not_directly_assigned" if supported else "unsupported_world" if rule is None else "unsupported_world_version"
    values = [[None for _ in channels] for _ in axis]
    reasons = [[default_reason for _ in channels] for _ in axis]
    if supported:
        controls = _oscillator_controls(spec) if environment == "coupled_oscillators" else _spin_controls(spec)
        for row, coordinate in enumerate(axis):
            for column, channel in enumerate(channels):
                if channel not in rule["channels"]:
                    reasons[row][column] = "unsupported_channel"
                    continue
                if environment == "coupled_oscillators":
                    clamp, position, velocity = controls
                    node = channel[2:]
                    if node in clamp:
                        values[row][column], reasons[row][column] = 0.0, "oscillator_clamp"
                    elif coordinate == 0:
                        initial = position if channel.startswith("x_") else velocity
                        values[row][column], reasons[row][column] = initial[_OSCILLATORS.index(node)], "prescribed_initial_state"
                else:
                    endpoints = [channel[2:]] if channel.startswith("m_") else channel[2:].split("_")
                    if all(node in controls for node in endpoints):
                        value = int(controls[endpoints[0]])
                        if len(endpoints) == 2:
                            value *= int(controls[endpoints[1]])
                        values[row][column] = float(value)
                        reasons[row][column] = "spin_clamped_mean" if len(endpoints) == 1 else "spin_both_clamped_pair"
                    elif len(endpoints) == 2 and any(node in controls for node in endpoints):
                        reasons[row][column] = "one_clamped_endpoint_unknown_mean"
    return {"protocol": PROTOCOL, "environment": environment,
            "world_version": world_version if world_version is not None else rule["version"] if rule else None,
            "supported": supported, "axis_field": axis_field, "axis": axis, "channels": list(channels),
            "known_mask": [[value is not None for value in row] for row in values],
            "known_values": values, "reasons": reasons, "value_semantics": "exact_clean_response_only"}


def summarize_cells(classification):
    """Count directly known cells, including the exact legacy retained-row set."""
    axis, channels = classification["axis"], classification["channels"]
    rows = list(range(1 if len(axis) > 1 and axis[0] == 0 else 0, len(axis)))
    known = sum(sum(row) for row in classification["known_mask"])
    scored_known = sum(sum(classification["known_mask"][row]) for row in rows)
    total, scored = len(axis) * len(channels), len(rows) * len(channels)
    return {"all_cells": total, "directly_known_cells": known, "unknown_cells": total - known,
            "direct_fraction_all_cells": known / total, "scored_rows": len(rows), "scored_row_indices": rows,
            "scored_cells": scored, "directly_known_scored_cells": scored_known,
            "unknown_scored_cells": scored - scored_known, "direct_fraction_scored_cells": scored_known / scored,
            "excluded_initial_cells": total - scored,
            "scored_reason_counts": dict(Counter(reason for row in rows for reason in classification["reasons"][row]))}


def known_controls_only(classification):
    """A diagnostic predictor: direct constants where known, zero everywhere else.

    This is neither the environment's fitted baseline nor a scientific model.
    For oscillator clamps its output already agrees with the zero predictor.
    """
    return [[0.0 if value is None else value for value in row] for row in classification["known_values"]]

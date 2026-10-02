"""Public-semantic eligibility for pilot quantitative paired claims.

Inputs must already be canonical public experiment specifications. This module
does not import worlds, simulate outcomes, infer hidden parameters, or certify
mechanistic novelty. Minimum time lags are declared pilot eligibility resolution,
not fitted biological/physical time constants.
"""
import math
import numbers


_COORDINATE_TOLERANCE = 1e-12
_SPIN_ANGLE_TOLERANCE = 1e-12
_TIME_RULES = {
    "microecology": ("times_h", 1.0, "h", "events", "time_h", 32),
    "microecology_causal": ("times_h", 1.0, "h", "events", "time_h", 32),
    "coupled_oscillators": ("times", 0.25, "s", None, None, 241),
    "reaction_kinetics": ("times_s", 1.0, "s", "interventions", "time_s", 33),
    "heat_transport": ("times", 0.5, "s", None, None, 25),
    "gene_regulation": ("times_h", 0.5, "h", "interventions", "time_h", 41),
    "hysteresis_material": ("times", 0.5, "s", None, None, 129),
    "orbital_dynamics": ("times", 0.25, "T", "impulses", "time", 65),
    "pattern_formation": ("times", 0.25, "T", None, None, 33),
    "spin_echo": ("times_ms", 1.0, "ms", "pulses", "time_ms", 129),
    "population_drift": ("times", 0.25, "replacement-clock units", None, None, 33),
}
_OSCILLATOR_NODES = ("A", "B", "C", "D")
_SPIN_NODES = ("A", "B", "C", "D", "E", "F")
_CHANNELS = {
    "microecology": ("A", "B", "C", "nutrient", "peak-01", "peak-02", "peak-03"),
    "microecology_causal": ("A", "B", "C", "nutrient", "peak-01", "peak-02", "peak-03"),
    "coupled_oscillators": tuple(prefix + node for prefix in ("x_", "v_") for node in _OSCILLATOR_NODES),
    "reaction_kinetics": ("A", "B", "C", "D"),
    "heat_transport": ("probe_1_temperature", "probe_2_temperature", "probe_3_temperature"),
    "gene_regulation": ("G1", "G2", "G3", "G4"),
    "hysteresis_material": ("response",),
    "orbital_dynamics": ("x", "y", "vx", "vy"),
    "pattern_formation": tuple("probe_%02d" % index for index in range(16)),
    "electrical_impedance": ("voltage_real", "voltage_imag"),
    "spin_echo": ("magnetization_x", "magnetization_y", "magnetization_z"),
    "population_drift": ("mean_A_frequency", "mean_mixedness", "boundary_A", "boundary_B"),
    "ising_spin": (tuple("m_" + node for node in _SPIN_NODES) +
                   tuple("c_" + left + "_" + right for index, left in enumerate(_SPIN_NODES)
                         for right in _SPIN_NODES[index + 1:])),
}


def _number(value):
    if isinstance(value, bool) or not isinstance(value, numbers.Real):
        raise ValueError("coordinate must be a finite real number")
    try:
        value = float(value)
    except (ValueError, OverflowError):
        raise ValueError("coordinate must be a finite real number") from None
    if not math.isfinite(value):
        raise ValueError("coordinate must be a finite real number")
    return value


def _decision(eligible, reason):
    return {"eligible": eligible, "reason": reason}


def policy_description():
    """Return detached JSON-safe public policy; no sampled instance data."""
    return {
        "protocol": "public-claim-eligibility-0.10",
        "input_contract": "Apply to canonical public specs after normal experiment/readout validation.",
        "matched_coordinate": "Time-dependent worlds must observe the same time in both arms at the selected readout row. Ising temperatures may differ because temperature itself is a controlled treatment.",
        "absolute_coordinate_tolerance": _COORDINATE_TOLERANCE,
        "minimum_lag": {
            name: {"value": rule[1], "unit": rule[2], "axis_field": rule[0],
                   "event_field": rule[3], "event_time_field": rule[4]}
            for name, rule in _TIME_RULES.items()
        },
        "time_rule": "In each time-dependent arm, the readout must be at least the listed lag after t=0 and after every event at or before that readout. Future events do not affect eligibility. The boundary lag is inclusive, within the absolute coordinate tolerance.",
        "continuous_protocol_rule": "Material field-ramp knots change the drive but do not assign the response. They do not restart the eligibility lag; readouts need matched times and at least 0.5 seconds after preparation.",
        "resolution_interpretation": "These fixed lags declare pilot temporal-resolution eligibility; they are not hidden time constants, fitted detection thresholds, or mechanism-depth certification.",
        "oscillator_rule": "Reject x_NODE or v_NODE if NODE is clamped in either arm. Other downstream unclamped nodes remain eligible subject to the time rule.",
        "ising_rule": "The axis is an equilibrium temperature, not time. Each arm requires a positive temperature, with no temporal lag or cross-arm temperature matching requirement. Temperature-dependence claims remain allowed. Reject m_NODE if NODE is clamped in either arm; reject c_LEFT_RIGHT if both endpoints are clamped in either arm. One-clamped-endpoint correlations and other unclamped observables remain eligible.",
        "frequency_rules": {
            "electrical_impedance": {
                "axis_field": "frequencies_hz", "unit": "Hz", "range": [2, 5000],
                "length": [1, 65], "order": "strictly increasing", "minimum_lag": None,
                "readout_rule": "Each row is an independent sinusoidal steady state. The same zero-based row and voltage_real or voltage_imag channel select the readout in each arm. Selected frequencies may differ: frequency is a controlled treatment, so spectral contrasts are allowed. Apparatus-only contrasts use the same frequency; if frequency and apparatus both differ the claim is a combined contrast, not an isolated load or source effect. Every requested frequency in both arms must satisfy the public range and ordering. There is no elapsed time, t=0 assignment, carried state or temporal lag.",
                "limits": "Public amplitude linearity and known external divider transformations are instrument facts. Eligibility or numerical verification does not certify discovery of a device mechanism or unique internal topology.",
            },
        },
        "spin_echo_rule": {
            "maximum_pulses": 12,
            "integer_pi_angle_tolerance_rad": _SPIN_ANGLE_TOLERANCE,
            "readout_rule": "Match readout times in both arms. Exclude t=0 and pulse timestamps; require at least 1 ms after preparation and every pulse at or before the readout. Future pulses do not affect earlier eligibility. Reject all channels for a zero initial vector. Integer-pi pulses preserve known z up to sign flips. A non-pi pulse can introduce hidden dependence into z only when transverse response already depends on hidden waiting dynamics. Thus a pure-z preparation retains known z through its first non-pi pulse; a later non-pi pulse can mix the intervening unknown transverse evolution into z. Reject channels still fixed by these public dependencies in either arm.",
            "reason_codes": {"public_preparation_assigns_readout": "The initial vector and declared ideal rotations already fix the selected readout in at least one arm."},
            "limits": "These public dependency guards are conservative exclusions, not an algebraically complete test or a detectability guarantee. The 1 ms lag is an administrative pilot resolution, not a fitted physical time constant. The integer-pi angular tolerance is a floating-point policy convention, not exact mathematical equivalence. Known detuning and rotation transformations still require separate scientific evidence review; passing eligibility does not certify discovery. Once a non-pi pulse mixes hidden transverse dependence into z, subsequent waiting does not restore known z.",
        },
        "limits": "Eligibility does not certify causal isolation, evidential relevance, semantic independence, surprise, identifiable mechanism, or novelty. Other analytically predetermined effects require separate evidence review.",
        "reason_codes": {
            "eligible": "Passes these public-semantic eligibility checks only.",
            "unsupported_world": "No public eligibility policy is declared for this world.",
            "mismatched_axis_field": "The supplied axis field differs from the declared public axis.",
            "invalid_readout": "The row/channel does not match the declared public readout schema.",
            "invalid_public_spec": "A required public coordinate, event or clamp has malformed data.",
            "unmatched_readout_coordinate": "The two arms of a time-dependent world observe different times.",
            "readout_before_temporal_resolution": "Readout is too close to the prescribed initial state.",
            "readout_too_soon_after_event": "Readout is too close to an event in at least one arm.",
            "public_clamp_assigns_readout": "At least one arm directly fixes this observable through a public clamp.",
        },
    }


def _spin_echo_known_readout(spec, coordinate, channel):
    """Public preparation/rotation facts only; no hidden ensemble or simulation."""
    if set(spec) != {"initial_magnetization", "detuning_hz", "times_ms", "pulses"}:
        raise ValueError("invalid spin echo public spec")
    initial = spec["initial_magnetization"]
    if not isinstance(initial, list) or len(initial) != 3:
        raise ValueError("invalid initial vector")
    initial = [_number(value) for value in initial]
    if any(abs(value) > 1 for value in initial) or math.sqrt(sum(value*value for value in initial)) > 1 + 1e-12:
        raise ValueError("invalid initial norm")
    if not -40 <= _number(spec["detuning_hz"]) <= 40:
        raise ValueError("invalid detuning")
    times = spec["times_ms"]
    if not isinstance(times, list) or not 1 <= len(times) <= 129:
        raise ValueError("invalid time axis")
    times = [_number(value) for value in times]
    if any(not 0 <= value <= 250 for value in times) or any(b <= a for a, b in zip(times, times[1:])):
        raise ValueError("invalid time axis")
    pulses = spec["pulses"]
    if not isinstance(pulses, list) or len(pulses) > 12:
        raise ValueError("invalid pulse list")
    previous, z_known = None, True
    transverse_hidden_dependency = initial[0] != 0 or initial[1] != 0
    for pulse in pulses:
        if not isinstance(pulse, dict) or set(pulse) != {"time_ms", "angle_rad", "phase_rad"}:
            raise ValueError("invalid pulse")
        time = _number(pulse["time_ms"])
        angle, phase = _number(pulse["angle_rad"]), _number(pulse["phase_rad"])
        if (not .1 <= time <= times[-1] or not -2*math.pi <= angle <= 2*math.pi or
                not -math.pi <= phase <= math.pi or
                (previous is not None and time - previous < .1 - 1e-12)):
            raise ValueError("invalid pulse controls")
        previous = time
        if time <= coordinate and not math.isclose(angle, round(angle/math.pi)*math.pi,
                                                   rel_tol=0.0, abs_tol=_SPIN_ANGLE_TOLERANCE):
            # Positive waits precede all legal pulses. Initial transverse
            # components, or transverse components created by an earlier
            # non-pi pulse, can therefore depend on hidden waiting dynamics.
            # A first non-pi pulse after pure-z preparation creates that later
            # dependence but its z projection is still known from preparation.
            z_known = z_known and not transverse_hidden_dependency
            transverse_hidden_dependency = True
    zero_state = all(value == 0 for value in initial)
    return zero_state or (z_known if channel == "magnetization_z" else not transverse_hidden_dependency)


def _population_public_spec(spec):
    """Finite public controls only; boundary preparation remains eligible."""
    if set(spec) != {"population_size", "initial_A", "times", "selection_bias", "newborn_flip_probability"}:
        raise ValueError("invalid population public spec")
    n, k = spec["population_size"], spec["initial_A"]
    if (isinstance(n, bool) or not isinstance(n, numbers.Integral) or not 2 <= n <= 32 or
            isinstance(k, bool) or not isinstance(k, numbers.Integral) or not 0 <= k <= n):
        raise ValueError("invalid population preparation")
    times = spec["times"]
    if not isinstance(times, list) or not 1 <= len(times) <= 33:
        raise ValueError("invalid population time axis")
    times = [_number(value) for value in times]
    if any(not 0 <= value <= 60 for value in times) or any(b <= a for a, b in zip(times, times[1:])):
        raise ValueError("invalid population time axis")
    if not -.5 <= _number(spec["selection_bias"]) <= .5:
        raise ValueError("invalid reproductive control")
    if not 0 <= _number(spec["newborn_flip_probability"]) <= .1:
        raise ValueError("invalid newborn control")


def claim_eligibility(world_name, control, treatment, readout, axis_field):
    """Reject direct assignment readouts using public semantics only.

    Unknown or malformed inputs fail closed. This supplements normal world
    validation; it intentionally does not duplicate the full experiment schema.
    """
    if not isinstance(world_name, str) or world_name not in _CHANNELS:
        return _decision(False, "unsupported_world")
    expected_axis = ("frequencies_hz" if world_name == "electrical_impedance" else
                     "temperatures" if world_name == "ising_spin" else _TIME_RULES[world_name][0])
    if not isinstance(axis_field, str) or axis_field != expected_axis:
        return _decision(False, "mismatched_axis_field")
    if (not isinstance(readout, dict) or set(readout) != {"row", "channel"} or
            type(readout["row"]) is not int or readout["row"] < 0 or
            not isinstance(readout["channel"], str) or readout["channel"] not in _CHANNELS[world_name]):
        return _decision(False, "invalid_readout")
    row, channel = readout["row"], readout["channel"]
    if world_name == "electrical_impedance":
        # This finite public control check has no world imports or temporal rule.
        try:
            for spec in (control, treatment):
                if not isinstance(spec, dict) or set(spec) != {"frequencies_hz", "source_ohm", "load_ohm", "amplitude_v"}:
                    raise ValueError("invalid public spec")
                axis = spec["frequencies_hz"]
                if not isinstance(axis, list) or not 1 <= len(axis) <= 65:
                    raise ValueError("invalid frequency axis")
                if row >= len(axis):
                    return _decision(False, "invalid_readout")
                coordinates = [_number(value) for value in axis]
                if (any(not 2 <= value <= 5000 for value in coordinates) or
                        any(right <= left for left, right in zip(coordinates, coordinates[1:]))):
                    raise ValueError("invalid frequency range or order")
                for key, low, high in (("source_ohm", 100, 2000), ("load_ohm", 200, 20000),
                                       ("amplitude_v", .25, 2)):
                    if not low <= _number(spec[key]) <= high:
                        raise ValueError("invalid apparatus control")
        except (KeyError, TypeError, ValueError, OverflowError):
            return _decision(False, "invalid_public_spec")
        return _decision(True, "eligible")
    arms = (control, treatment)
    coordinates = []
    spin_known = []
    try:
        for spec in arms:
            if not isinstance(spec, dict):
                raise ValueError("spec must be an object")
            axis = spec[axis_field]
            maximum = 32 if world_name == "ising_spin" else _TIME_RULES[world_name][5]
            if not isinstance(axis, (list, tuple)) or not 1 <= len(axis) <= maximum:
                raise ValueError("invalid public axis")
            if row >= len(axis):
                return _decision(False, "invalid_readout")
            coordinate = _number(axis[row])
            if coordinate < 0 or (world_name == "ising_spin" and coordinate <= 0):
                raise ValueError("invalid public coordinate")
            coordinates.append(coordinate)
            if world_name == "spin_echo":
                spin_known.append(_spin_echo_known_readout(spec, coordinate, channel))
            elif world_name == "population_drift":
                _population_public_spec(spec)
        if world_name != "ising_spin" and not math.isclose(coordinates[0], coordinates[1], rel_tol=0.0,
                                                           abs_tol=_COORDINATE_TOLERANCE):
            return _decision(False, "unmatched_readout_coordinate")

        if world_name == "coupled_oscillators":
            for spec in arms:
                clamp = spec.get("clamp", [])
                if (not isinstance(clamp, (list, tuple)) or len(clamp) > 4 or
                        any(not isinstance(node, str) or node not in _OSCILLATOR_NODES for node in clamp)):
                    raise ValueError("invalid oscillator clamp")
                if channel[2:] in clamp:
                    return _decision(False, "public_clamp_assigns_readout")
        elif world_name == "ising_spin":
            endpoints = (channel[2:],) if channel.startswith("m_") else tuple(channel[2:].split("_"))
            for spec in arms:
                clamp = spec.get("clamp", {})
                if (not isinstance(clamp, dict) or len(clamp) > 6 or
                        any(not isinstance(node, str) or node not in _SPIN_NODES or
                            isinstance(value, bool) or not isinstance(value, numbers.Integral) or value not in (-1, 1)
                            for node, value in clamp.items())):
                    raise ValueError("invalid spin clamp")
                if all(node in clamp for node in endpoints):
                    return _decision(False, "public_clamp_assigns_readout")
            return _decision(True, "eligible")

        _, minimum_lag, _, event_field, event_time_field, _ = _TIME_RULES[world_name]
        for spec, coordinate in zip(arms, coordinates):
            if coordinate + _COORDINATE_TOLERANCE < minimum_lag:
                return _decision(False, "readout_before_temporal_resolution")
            events = [] if event_field is None else spec.get(event_field, [])
            maximum_events = 12 if world_name == "spin_echo" else 4
            if not isinstance(events, (list, tuple)) or len(events) > maximum_events:
                raise ValueError("invalid public event list")
            for event in events:
                if not isinstance(event, dict):
                    raise ValueError("invalid public event")
                event_time = _number(event[event_time_field])
                if event_time < 0:
                    raise ValueError("invalid public event time")
                if event_time <= coordinate and coordinate - event_time + _COORDINATE_TOLERANCE < minimum_lag:
                    return _decision(False, "readout_too_soon_after_event")
        if any(spin_known):
            return _decision(False, "public_preparation_assigns_readout")
    except (KeyError, TypeError, ValueError, OverflowError):
        return _decision(False, "invalid_public_spec")
    return _decision(True, "eligible")

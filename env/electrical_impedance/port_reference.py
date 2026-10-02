"""Public-apparatus-only port transfer; no hidden circuit model or fitting."""

import numbers

import numpy as np

from .protocol import CHANNELS, NOISE_STD, validate_spec

MIN_SOURCE_MAGNITUDE_V = 5*NOISE_STD[0]
DENOMINATOR_EPS_MULTIPLIER = 64.


class ReferenceFailure(ValueError):
    """A retained, typed failure, never an invitation to select another method."""

    def __init__(self, code, message, diagnostics=None):
        super().__init__(message)
        self.code = code
        self.diagnostics = dict(diagnostics or {})


def _finite_cells(raw, rows, columns):
    if not isinstance(raw, list) or len(raw) != rows:
        raise ReferenceFailure("invalid_record", "record row count does not match source spec")
    values = []
    for row in raw:
        if not isinstance(row, list) or len(row) != columns:
            raise ReferenceFailure("invalid_record", "record must have two quadratures per row")
        clean = []
        for cell in row:
            if isinstance(cell, (bool, np.bool_)) or not isinstance(cell, numbers.Real):
                raise ReferenceFailure("invalid_record", "record cells must be finite real numbers")
            try:
                value = float(cell)
            except (ValueError, OverflowError):
                raise ReferenceFailure("invalid_record", "record cells must be finite real numbers") from None
            if not np.isfinite(value):
                raise ReferenceFailure("invalid_record", "record cells must be finite real numbers")
            clean.append(value)
        values.append(clean)
    return np.asarray(values, dtype=float)


def validate_record(record):
    """Validate a public record without using any simulator identity."""
    if not isinstance(record, dict) or set(record) != {"spec", "observation"}:
        raise ReferenceFailure("invalid_record", "record needs exactly spec and observation")
    try:
        source = validate_spec(record["spec"])
    except (TypeError, ValueError) as error:
        raise ReferenceFailure("invalid_record", str(error)) from None
    observation = record["observation"]
    if not isinstance(observation, dict) or set(observation) != {"axis", "channels", "values"}:
        raise ReferenceFailure("invalid_record", "observation needs exactly axis, channels and values")
    if observation["channels"] != list(CHANNELS):
        raise ReferenceFailure("invalid_record", "incorrect channel order")
    axis = observation["axis"]
    if not isinstance(axis, list) or len(axis) != len(source["frequencies_hz"]):
        raise ReferenceFailure("invalid_record", "record axis does not match source spec")
    clean_axis = _finite_cells([[value] for value in axis], len(axis), 1)[:, 0]
    if not np.array_equal(clean_axis, source["frequencies_hz"]):
        raise ReferenceFailure("invalid_record", "record axis does not match source spec")
    return source, _finite_cells(observation["values"], len(axis), 2)


def predict_with_diagnostics(records, spec):
    """One source record and one query; no calibration or target argument exists."""
    if not isinstance(records, (list, tuple)) or len(records) != 1:
        raise ReferenceFailure("invalid_record", "exactly one public source record is required")
    source, values = validate_record(records[0])
    try:
        query = validate_spec(spec)
    except (TypeError, ValueError) as error:
        raise ReferenceFailure("invalid_query", str(error)) from None
    frequencies = source["frequencies_hz"]
    if query["frequencies_hz"][0] < frequencies[0] or query["frequencies_hz"][-1] > frequencies[-1]:
        raise ReferenceFailure("out_of_band", "query lies outside the observed closed frequency band")
    diagnostics = {}
    try:
        with np.errstate(over="raise", invalid="raise", divide="raise", under="ignore"):
            z = values[:, 0]+1j*values[:, 1]
            magnitude = np.abs(z)
            if not np.isfinite(magnitude).all():
                raise FloatingPointError("nonfinite phasor magnitude")
            diagnostics["min_source_magnitude_v"] = float(np.min(magnitude))
            if np.any(magnitude <= MIN_SOURCE_MAGNITUDE_V):
                raise ReferenceFailure("source_near_zero", "source phasor is at or below 0.005 V", diagnostics)
            sensitivity = (source["amplitude_v"]/source["source_ohm"])/magnitude/magnitude
            diagnostics["max_inverse_sensitivity_s_per_v"] = float(np.max(sensitivity))
            admittance = (source["amplitude_v"]/z-1)/source["source_ohm"]-1/source["load_ohm"]
            if not np.isfinite(admittance).all():
                raise FloatingPointError("nonfinite estimated admittance")
            diagnostics["negative_conductance_count"] = int(np.sum(admittance.real < 0))
            diagnostics["min_estimated_conductance_s"] = float(np.min(admittance.real))
            x, q = np.log(frequencies), np.log(query["frequencies_hz"])
            interpolated = np.interp(q, x, admittance.real)+1j*np.interp(q, x, admittance.imag)
            denominator = 1+query["source_ohm"]*(1/query["load_ohm"]+interpolated)
            scale = 1+abs(query["source_ohm"]/query["load_ohm"])+abs(query["source_ohm"]*interpolated)
            if not np.isfinite(denominator).all() or not np.isfinite(scale).all():
                raise FloatingPointError("nonfinite reconstruction intermediate")
            diagnostics["min_denominator_magnitude"] = float(np.min(abs(denominator)))
            if np.any(abs(denominator) <= DENOMINATOR_EPS_MULTIPLIER*np.finfo(float).eps*scale):
                raise ReferenceFailure("ill_conditioned_denominator", "reconstruction denominator is too close to cancellation", diagnostics)
            prediction = query["amplitude_v"]/denominator
            if not np.isfinite(prediction).all():
                raise FloatingPointError("nonfinite predicted phasor")
            diagnostics["finite_passive_bound_violations"] = int(np.sum(abs(prediction) > query["amplitude_v"]))
            output = np.column_stack((prediction.real, prediction.imag)).tolist()
    except FloatingPointError as error:
        raise ReferenceFailure("nonfinite_computation", str(error), diagnostics) from None
    return {"values": output, "diagnostics": diagnostics}


def port_reference(records, spec):
    """Return only the predicted observation matrix, like the weak baseline."""
    return predict_with_diagnostics(records, spec)["values"]

"""Translation-centered Cartesian nearest observation, public records only.

No potential law, rotational equivariance, hidden family or fit parameters.
Failure under orientation changes is a known limitation of this weak baseline.
"""
import numpy as np
from .protocol import CHANNELS, validate_spec


def _feature(points, temperature):
    p = np.asarray(points)
    return np.r_[(p - p.mean(axis=0)).ravel() / 3., (temperature - 450.) / 450.]


def baseline(records, spec):
    spec = validate_spec(spec)
    if not isinstance(records, (list, tuple)) or len(records) > 256:
        raise ValueError("records must contain at most256 records")
    features, values = [], []
    for record in records:
        if not isinstance(record, dict) or not {"spec", "observation"}.issubset(record):
            raise ValueError("records need spec and observation")
        other = validate_spec(record["spec"])
        obs = record["observation"]
        if not isinstance(obs, dict) or obs.get("axis") != other["configuration_ids"] or obs.get("channels") != list(CHANNELS):
            raise ValueError("observation schema mismatch")
        try:
            y = np.asarray(obs["values"], dtype=float)
        except (KeyError, TypeError, ValueError, OverflowError):
            raise ValueError("observation values must be finite numeric arrays") from None
        if y.shape != (len(other["configurations"]), len(CHANNELS)) or not np.isfinite(y).all():
            raise ValueError("observation values must match spec and channels")
        features.extend(_feature(p, other["temperature_k"]) for p in other["configurations"])
        values.extend(y)
    if not features:
        return np.zeros((len(spec["configurations"]), len(CHANNELS))).tolist()
    features, values = np.asarray(features), np.asarray(values)
    return [values[np.argmin(np.sum((features - _feature(p, spec["temperature_k"])) ** 2, axis=1))].tolist() for p in spec["configurations"]]

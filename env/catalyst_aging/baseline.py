"""Public nearest-history baseline, no hidden kinetic/instrument-family access."""
import numpy as np
from .protocol import CHANNELS, validate_spec


def _features(spec, event_index):
    event = spec["events"][event_index-1]
    kind = event["kind"]
    kind_vector = [float(kind==k) for k in ("blank", "standard", "reaction")]
    history = []
    if kind == "reaction":
        history = [e for e in spec["events"][:event_index-1] if e["kind"] == "reaction" and e["coupon_id"] == event["coupon_id"]]
        conditions = [(event["temperature_k"]-500)/60., event["feed_concentration"]/1.2, event["duration_min"]/15.]
        dose = sum(e["duration_min"]*e["feed_concentration"] for e in history)/100.
        history_temp = sum((e["temperature_k"]-500)*e["duration_min"] for e in history)/6000.
    else:
        conditions, dose, history_temp = [0.,0.,0.],0.,0.
    return np.asarray(kind_vector+[event_index/24.]+conditions+[len(history)/6.,dose,history_temp])


def baseline(records, spec):
    spec = validate_spec(spec)
    if not isinstance(records, (list, tuple)) or len(records)>256:
        raise ValueError("records must contain at most256 records")
    bank = {kind: [] for kind in ("blank", "standard", "reaction")}
    for record in records:
        if not isinstance(record, dict) or not {"spec", "observation"}.issubset(record):
            raise ValueError("records need spec and observation")
        other = validate_spec(record["spec"])
        obs = record["observation"]
        if not isinstance(obs,dict) or obs.get("axis") != other["event_indices"] or obs.get("channels") != list(CHANNELS):
            raise ValueError("observation schema mismatch")
        try:
            values = np.asarray(obs["values"],dtype=float)
        except (KeyError, TypeError,ValueError,OverflowError):
            raise ValueError("observation values must be finite arrays") from None
        if values.shape != (len(other["event_indices"]),1) or not np.isfinite(values).all():
            raise ValueError("observation values must match spec and channels")
        for index, y in zip(other["event_indices"], values[:,0]):
            kind = other["events"][index-1]["kind"]
            bank[kind].append((_features(other,index),float(y)))
    result = []
    for index in spec["event_indices"]:
        kind = spec["events"][index-1]["kind"]
        candidates = bank[kind]
        # These defaults are weak guesses, not claimed assigned instrument values.
        if not candidates:
            value = 1.5 if kind == "standard" else 0.
        else:
            feature = _features(spec,index)
            value = min(candidates,key=lambda item:float(np.sum((item[0]-feature)**2)))[1]
        result.append([value])
    return result

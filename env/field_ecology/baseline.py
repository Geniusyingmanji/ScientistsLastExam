"""Public-history interpolation without latent probabilities."""

import numpy as np

from .protocol import AXIS_FIELD, CHANNELS, number, validate_spec


def baseline(records,spec):
    query = validate_spec(spec)
    if not isinstance(records,(list,tuple)) or len(records)>256:
        raise ValueError("records must contain at most 256 experiments")
    rows = []
    for record in records:
        if not isinstance(record,dict) or not {"spec","observation"} <= set(record):
            raise ValueError("record needs spec and observation")
        source = validate_spec(record["spec"])
        obs = record["observation"]
        if not isinstance(obs,dict) or obs.get("axis") != source[AXIS_FIELD] or obs.get("channels") != list(CHANNELS):
            raise ValueError("record axis or channels mismatch")
        raw = obs.get("values")
        if not isinstance(raw,list) or len(raw)!=len(source[AXIS_FIELD]) or any(not isinstance(row,list) or len(row)!=3 for row in raw):
            raise ValueError("record values shape mismatch")
        values = [[number(v,0,1,"record fraction") for v in row] for row in raw]
        if source["visits"] == query["visits"]:
            rows.extend(zip(source[AXIS_FIELD],values))
    if not rows:
        return np.full((len(query[AXIS_FIELD]),3),.5).tolist()
    grouped = {}
    for h,value in rows:
        grouped.setdefault(h,[]).append(value)
    x = sorted(grouped)
    values = np.asarray([np.mean(grouped[h],axis=0) for h in x])
    return np.column_stack([np.interp(query[AXIS_FIELD],x,values[:,j]) for j in range(3)]).tolist()

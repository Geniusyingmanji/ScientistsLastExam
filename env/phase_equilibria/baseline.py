"""Public-record nearest experiment, then interpolation in measured angle."""
import math
import numpy as np
from .protocol import AXIS_FIELD, CHANNELS, number, validate_spec


def baseline(records, spec):
    query = validate_spec(spec)
    if not isinstance(records, (list, tuple)) or len(records) > 256:
        raise ValueError('records must contain at most 256 public experiments')
    options = []
    for record in records:
        if not isinstance(record, dict) or not {'spec', 'observation'} <= set(record):
            raise ValueError('every record needs spec and observation')
        source = validate_spec(record['spec'])
        obs = record['observation']
        if not isinstance(obs, dict) or obs.get('channels') != list(CHANNELS):
            raise ValueError('record channels do not match')
        axis, raw = obs.get('axis'), obs.get('values')
        if not isinstance(axis, list) or axis != source[AXIS_FIELD] or not isinstance(raw, list) or len(raw) != len(axis):
            raise ValueError('record axis or row count mismatch')
        if any(not isinstance(row, list) or len(row) != 1 for row in raw):
            raise ValueError('record values must have one channel')
        values = [number(row[0], -math.inf, math.inf, 'record value') for row in raw]
        distance = ((source['composition']-query['composition'])**2 +
                    ((source['hold_time']-query['hold_time'])/120)**2 +
                    (source['loading']-query['loading'])**2 +
                    (source['preparation'] != query['preparation']))
        options.append((distance, axis, values))
    if not options:
        return [[0.] for _ in query[AXIS_FIELD]]
    _, axis, values = min(options, key=lambda row: row[0])
    return np.interp(query[AXIS_FIELD], axis, values)[:, None].tolist()

"""Shared public validation/receipt mechanics for unregistered history prototypes."""
import hashlib
import json
import math
import numbers
import numpy as np


def real(x, low, high, name):
    if isinstance(x, (bool, np.bool_)) or not isinstance(x, numbers.Real) or not math.isfinite(float(x)) or not low <= x <= high:
        raise ValueError('%s must be finite in [%s, %s]' % (name, low, high))
    return float(x)


def integer(x, name):
    if isinstance(x, (bool, np.bool_)) or not isinstance(x, numbers.Integral) or not 0 <= x < 2**63:
        raise ValueError('%s must be a nonnegative integer below 2**63' % name)
    return int(x)


def times(x):
    if not isinstance(x, list) or not 1 <= len(x) <= 49:
        raise ValueError('times must contain 1..49 entries')
    x = [real(v, 0, 12, 'time') for v in x]
    if any(b <= a for a, b in zip(x, x[1:])):
        raise ValueError('times must strictly increase')
    return x


def schedule(x, value_name, high):
    if not isinstance(x, list) or not 1 <= len(x) <= 4:
        raise ValueError('schedule must contain 1..4 segments')
    result=[]
    for row in x:
        if not isinstance(row, dict) or set(row) != {'at', value_name}:
            raise ValueError('each segment needs at and '+value_name)
        result.append({'at':real(row['at'],0,12,'at'),value_name:real(row[value_name],0,high,value_name)})
    if result[0]['at'] != 0 or any(b['at'] <= a['at'] for a,b in zip(result,result[1:])):
        raise ValueError('schedule starts at zero and strictly increases')
    return result


def observe(seed, spec, values, channels, std, noise_key):
    if noise_key is not None:
        if not isinstance(noise_key,str) or len(noise_key)>256:
            raise ValueError('noise_key must be null or a string of at most 256 characters')
        raw=json.dumps([seed,spec,noise_key],sort_keys=True,allow_nan=False).encode()
        rng=np.random.default_rng(int.from_bytes(hashlib.sha256(raw).digest()[:16],'big'))
        values=values+rng.normal(0,std,values.shape)
    return {'axis':spec['times'],'channels':list(channels),'values':values.tolist()}


def baseline(records, spec):
    """Empirical interpolation; uses public records only, no kernel or family access."""
    if not records:
        return [[0.] for _ in spec['times']]
    def features(s):
        key='stimulus' if 'stimulus' in s else 'flow'
        field='level' if key=='stimulus' else 'rate'
        rows=s[key]
        result=[next(r[field] for r in reversed(rows) if r['at']<=t) for t in np.linspace(0,12,25)]
        if key=='stimulus':
            result += [s['reset_at']/12.,s['retained_fraction']]
        return np.asarray(result)
    target=features(spec)
    def distance(record):
        return float(np.sum((features(record['spec'])-target)**2))
    record=min(records,key=distance)
    return [[float(np.interp(t,record['observation']['axis'],np.asarray(record['observation']['values'])[:,0]))] for t in spec['times']]

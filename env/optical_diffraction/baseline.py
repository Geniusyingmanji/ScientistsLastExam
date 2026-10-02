"""Public record-only symmetric interpolation and known contrast-quadratic baseline."""
from bisect import bisect_left
import math

from .protocol import CHANNELS, validate_spec

Q_DECIMALS = 12


def public_q(spec):
    spec = validate_spec(spec)
    return [abs(2*math.pi*math.sin(t)/spec["wavelength_um"]) for t in spec["angles_rad"]]


def _groups(records):
    if not isinstance(records, (list, tuple)) or len(records) > 256:
        raise ValueError("at most 256 public records required")
    grouped = {}
    for record in records:
        if not isinstance(record, dict) or not {"spec", "observation"} <= set(record) or set(record)-{"id", "spec", "observation"}:
            raise ValueError("only public record fields accepted")
        spec = validate_spec(record["spec"])
        obs = record["observation"]
        if not isinstance(obs, dict) or set(obs) != {"axis", "channels", "values"} or obs["axis"] != spec["angles_rad"] or obs["channels"] != list(CHANNELS):
            raise ValueError("record observation contract mismatch")
        values = obs["values"]
        if not isinstance(values, list) or len(values) != len(obs["axis"]):
            raise ValueError("record length mismatch")
        table = grouped.setdefault(spec["contrast_b"], {})
        for q, row in zip(public_q(spec), values):
            if not isinstance(row, list) or len(row) != 1 or isinstance(row[0], bool) or not isinstance(row[0], (int, float)) or not math.isfinite(row[0]):
                raise ValueError("finite one-channel row required")
            table.setdefault(round(q, Q_DECIMALS), []).append(float(row[0]))
    return {c: [(q, math.fsum(values)/len(values)) for q, values in sorted(table.items())] for c, table in grouped.items()}


def _interpolate(table, q):
    qs = [entry[0] for entry in table]
    q = round(q, Q_DECIMALS)
    index = bisect_left(qs, q)
    if index == 0:
        return table[0][1]
    if index == len(table):
        return table[-1][1]
    x0, y0 = table[index-1]
    x1, y1 = table[index]
    return y0+(y1-y0)*(q-x0)/(x1-x0)


def baseline(records, spec):
    query = validate_spec(spec)
    grouped = _groups(records)
    qs = public_q(query)
    if not grouped:
        return [[1.] for _ in qs]
    c = query["contrast_b"]
    if {-1., 0., 1.} <= set(grouped):
        rows = []
        for q in qs:
            minus, zero, plus = (_interpolate(grouped[k], q) for k in (-1., 0., 1.))
            rows.append([zero+.5*(plus-minus)*c+(.5*(plus+minus)-zero)*c*c])
    else:
        nearest = min(grouped, key=lambda k: (abs(c-k), k))
        rows = [[_interpolate(grouped[nearest], q)] for q in qs]
    if any(not math.isfinite(row[0]) for row in rows):
        raise ValueError("baseline became nonfinite")
    return rows


def support_labels(source_specs, target_spec):
    """Control-only preassigned q support; not a measured-error classifier."""
    if not source_specs:
        return ["no_source" for _ in public_q(target_spec)]
    source_qs = [q for spec in source_specs for q in public_q(spec)]
    low, high = min(source_qs), max(source_qs)
    return ["interpolation" if low-1e-12 <= q <= high+1e-12 else "extrapolation" for q in public_q(target_spec)]

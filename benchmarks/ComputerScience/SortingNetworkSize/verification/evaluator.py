"""Exact 0-1 sorting checker; clipped progress from Batcher to a cited size bound.

The construction checker proves sorting, not the cited lower-bound theorem.
A valid network at the lower bound is optimal conditional on that external bound.
The bound may be unattainable; unused score range is not measured search headroom.
"""

from __future__ import annotations

from itertools import islice
from functools import lru_cache
from numbers import Integral, Real

INVALID_RAW_SCORE = -1e18


def _normalized(value: float, baseline: float, target: float) -> float:
    """Higher-is-better normalization: generic construction=0, cited bound=1."""
    if target <= baseline:
        raise ValueError("target must improve on the zero anchor")
    return float(min(1.0, max(0.0, (value - baseline) / (target - baseline))))


def _cap(n: int) -> int:
    return n * n


def _batcher(n: int):
    """Batcher odd-even mergesort on N = 2^ceil(log2 n) wires, sentinel gates removed.

    A sorting network on N >= n wires restricted to the real wires (padding with +inf
    sentinels makes every gate touching a sentinel a no-op) still sorts the first n
    wires, so deleting those gates yields a legal baseline network for any n.
    """
    size = 1
    while size < n:
        size <<= 1
    net = []

    def compare(i: int, j: int) -> None:
        if max(i, j) < n:
            net.append([min(i, j), max(i, j)])

    def merge(lo: int, length: int, r: int) -> None:
        m = r * 2
        if m < length:
            merge(lo, length, m)
            merge(lo + r, length, m)
            for i in range(lo + r, lo + length - r, m):
                compare(i, i + r)
        else:
            compare(lo, lo + r)

    def sort(lo: int, length: int) -> None:
        if length > 1:
            sort(lo, length // 2)
            sort(lo + length // 2, length // 2)
            merge(lo, length, 1)

    sort(0, size)
    return net


@lru_cache(maxsize=None)
def _inputs(n):
    wires = []
    total = 1 << n
    for wire in range(n):
        run = 1 << wire
        mask = ((1 << run) - 1) << run
        width = 2 * run
        while width < total:
            mask |= mask << width
            width *= 2
        wires.append(mask)
    return tuple(wires)


def _sorts(network, n):
    wires = list(_inputs(n))
    for i, j in network:
        a, b = wires[i], wires[j]
        wires[i], wires[j] = a & b, a | b
    return all(not (a & ~b) for a, b in zip(wires, wires[1:]))


def _prune(network, n):
    network = list(network)
    changed = True
    while changed:
        changed = False
        for pos in range(len(network) - 1, -1, -1):
            trial = network[:pos] + network[pos + 1:]
            if _sorts(trial, n):
                network = trial
                changed = True
    return network


@lru_cache(maxsize=None)
def _baseline(n):
    if not isinstance(n, int) or not 2 <= n <= 17:
        raise ValueError("supported channel counts are 2 through 17")
    width = 1 << (n - 1).bit_length()
    full = _batcher(width)
    choices = []
    for offset in range(width - n + 1):
        window = [(i - offset, j - offset) for i, j in full
                  if offset <= i < j < offset + n]
        choices.append(_prune(window, n))
    best = min(choices, key=lambda net: (len(net), net))
    return tuple(best)


def _baseline_network(n):
    return list(_baseline(n))


# Published size lower bounds reported by Dobbelaere (2025-04-21 update).
# Their proof is external, not certified by the bitmask checker. See known_best.md.
LOWER_BOUNDS = {13: 44, 14: 48, 15: 53, 16: 57, 17: 63}
KNOWN_SIZES = {13: 45, 14: 51, 15: 56, 16: 60, 17: 71}
SIZES = {n: {"baseline": len(_baseline_network(n)), "lower_bound": bound,
             "sota_ref": KNOWN_SIZES[n]} for n, bound in LOWER_BOUNDS.items()}


def conservative_lower_bound(n: int) -> int:
    """Audit cross-check only: Harder S(12)=39 plus Van Voorhis recurrence."""
    return 39 + sum((k - 1).bit_length() for k in range(13, n + 1))


def _initial_wires(n: int) -> list[int]:
    """wires[w] = bitmask over all 2^n inputs; bit x set iff bit w of x is 1."""
    total = 1 << n
    wires = []
    for w in range(n):
        run = 1 << w
        unit = ((1 << run) - 1) << run      # 2^w ones then 2^w zeros, per 2^(w+1) block
        mask = unit
        width = 1 << (w + 1)
        while width < total:
            mask |= mask << width
            width <<= 1
        wires.append(mask)
    return wires


def _as_index(value):
    """Integral index or None (accepts int/numpy integer/5.0; rejects 5.5, bool, str)."""
    if isinstance(value, bool):
        return None
    if isinstance(value, Integral):
        return int(value)
    if isinstance(value, Real):
        f = float(value)
        return int(f) if f.is_integer() else None
    return None


def verify_network(raw, n: int) -> tuple[bool, int, str]:
    """Parse and fully re-check a candidate network; returns (ok, size, reason)."""
    if raw is None or isinstance(raw, (str, bytes, dict, int, float, bool)):
        return False, 0, "network must be a sequence of [i, j] pairs"
    cap = _cap(n)
    if isinstance(raw, (list, tuple)):
        if len(raw) > cap:
            return False, len(raw), f"{len(raw)} comparators exceed checker cap {cap}"
        items = list(raw)
    else:
        try:                                    # bounded even for infinite generators
            items = list(islice(iter(raw), cap + 1))
        except TypeError:
            return False, 0, "network is not iterable"
    if len(items) > cap:
        return False, len(items), f"{len(items)} comparators exceed checker cap {cap}"
    comparators = []
    for pos, item in enumerate(items):
        if item is None or isinstance(item, (str, bytes, dict, int, float, bool)):
            return False, 0, f"comparator {pos} is not a pair of indices"
        try:
            pair = list(islice(iter(item), 3))
        except TypeError:
            return False, 0, f"comparator {pos} is not a pair of indices"
        if len(pair) != 2:
            return False, 0, f"comparator {pos} is not a pair of exactly two indices"
        i = _as_index(pair[0])
        j = _as_index(pair[1])
        if i is None or j is None:
            return False, 0, f"comparator {pos} has a non-integer index"
        if not (0 <= i < j <= n - 1):
            return False, 0, f"comparator {pos} = ({i}, {j}) violates 0 <= i < j <= {n - 1}"
        comparators.append((i, j))
    wires = _initial_wires(n)
    for i, j in comparators:
        a, b = wires[i], wires[j]
        wires[i] = a & b                        # min to the lower-indexed wire
        wires[j] = a | b                        # max to the higher-indexed wire
    for w in range(n - 1):
        if wires[w] & ~wires[w + 1]:
            return False, len(comparators), (
                f"0-1 principle: some input leaves wires {w}, {w + 1} out of order")
    return True, len(comparators), "ok"

def score_n(n: int, ref: dict, build_network) -> dict:
    try:
        raw = build_network(n)
        ok, size, reason = verify_network(raw, n)
    except Exception as exc:  # malformed values and lazy iterators also fail closed
        return {"n": n, "valid": False, "reason": f"raised: {exc}", "score": 0.0}
    if not ok:
        return {"n": n, "valid": False, "reason": reason, "size": size, "score": 0.0}
    base, target, known = ref["baseline"], ref["lower_bound"], ref["sota_ref"]
    if size < target:
        return {"n": n, "valid": False, "size": size, "score": 0.0,
                "bound_contradiction": True,
                "reason": f"audit_required: verified sorting network of size {size} < cited lower bound {target} at n={n}"}
    return {
        "n": n, "valid": True, "size": size, "baseline_size": base,
        "lower_bound": target, "sota_ref": known,
        "record_gap": size - known, "lower_bound_gap": size - target,
        "target_attained": size == target, "beats_known_record": size < known,
        "score": _normalized(float(-size), float(-base), float(-target)),
    }


def evaluate(build_network) -> dict:
    per = [score_n(n, ref, build_network) for n, ref in SIZES.items()]
    n_valid = sum(1 for r in per if r.get("valid"))
    valid = n_valid == len(SIZES)
    contradictions = [r for r in per if r.get("bound_contradiction")]
    result = {
        "combined_score": sum(r["score"] for r in per) / len(per) if valid else 0.0,
        "raw_score": -sum(r["size"] for r in per) / len(per) if valid else INVALID_RAW_SCORE,
        "valid": 1.0 if n_valid == len(SIZES) else 0.0,
        "feasibility_rate": n_valid / len(SIZES),
        "beat_sota": bool(any(r.get("beats_known_record", False) for r in per)),
        "target_attainment_rate": sum(r.get("target_attained", False) for r in per) / len(SIZES),
        "per_n": per,
        "bound_contradiction": float(bool(contradictions)),
    }
    if not valid:
        result["error_message"] = "; ".join(r["reason"] for r in per if not r.get("valid"))
    return result

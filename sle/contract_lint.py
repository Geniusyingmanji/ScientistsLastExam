"""Free submission-shape validation for candidates.

A candidate can import this inside the sandbox and check the shape of what it is about to
return, before the oracle sees it. Calling it costs no oracle budget and reveals nothing about
the science: every check here is about form, and none of it touches a score, a hidden world, or
a reference value.

This exists because protocol failure and scientific failure were indistinguishable in the
results. Tasks whose submissions were rejected had a median hidden evaluator of 808 lines
against 254 for tasks that saturated, and the worst case demanded nine exactly-named fields with
cross-field consistency constraints - a candidate scoring zero there says nothing about whether
the model understands the science.

Usage inside a candidate::

    from sle.contract_lint import finite_array, binary_array, mapping

    ok, why = binary_array(prediction, shape=(shots, n_obs))
    if not ok:
        ...   # fix it before returning; `why` states exactly what is wrong

Every function returns ``(ok, reason)``. ``reason`` is empty when ``ok`` is True.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping, Optional, Sequence


def _numpy():
    try:
        import numpy as np
    except Exception:  # pragma: no cover - numpy is always mounted for candidates
        return None
    return np


def finite_array(value: Any, shape: Optional[Sequence[int]] = None,
                 dtype_kinds: str = "biuf") -> tuple[bool, str]:
    """Check that ``value`` is an array of the given shape holding only finite numbers.

    ``dtype_kinds`` follows numpy's ``dtype.kind``: b bool, i signed, u unsigned, f float.
    """
    np = _numpy()
    if np is None:
        return False, "numpy is unavailable"
    if value is None:
        return False, "value is None"
    try:
        arr = np.asarray(value)
    except Exception as exc:  # noqa: BLE001
        return False, "not array-like (%s)" % type(exc).__name__
    if arr.dtype.kind not in dtype_kinds:
        return False, "dtype kind %r is not one of %r" % (arr.dtype.kind, dtype_kinds)
    if shape is not None:
        want = tuple(int(s) for s in shape)
        if tuple(arr.shape) != want:
            return False, "expected shape %s, got %s" % (want, tuple(arr.shape))
    if arr.dtype.kind == "f" and not np.all(np.isfinite(arr)):
        bad = int(np.count_nonzero(~np.isfinite(arr)))
        return False, "%d non-finite entries (NaN or infinity)" % bad
    return True, ""


def binary_array(value: Any, shape: Optional[Sequence[int]] = None) -> tuple[bool, str]:
    """Check an array whose entries must be exactly 0 or 1, in any of bool/int/float form."""
    np = _numpy()
    ok, why = finite_array(value, shape=shape)
    if not ok:
        return ok, why
    arr = np.asarray(value)
    if arr.dtype.kind == "b":
        return True, ""
    if not np.all(np.isin(arr, (0, 1))):
        offenders = np.unique(arr[~np.isin(arr, (0, 1))])[:3]
        return False, "entries must be exactly 0 or 1; saw %s" % list(offenders)
    return True, ""


def mapping(value: Any, required: Iterable[str] = (),
            optional: Iterable[str] = (), allow_extra: bool = False) -> tuple[bool, str]:
    """Check a dict-like submission's key set.

    Missing and unexpected keys are reported by name, because 'invalid submission' with no
    detail is the failure mode this module exists to remove.
    """
    if not isinstance(value, Mapping):
        return False, "expected a mapping, got %s" % type(value).__name__
    keys = set(value)
    req = set(required)
    missing = sorted(req - keys)
    if missing:
        return False, "missing required keys: %s" % missing
    if not allow_extra:
        extra = sorted(keys - req - set(optional))
        if extra:
            return False, "unexpected keys: %s" % extra
    return True, ""


def in_range(value: Any, low: float, high: float, name: str = "value") -> tuple[bool, str]:
    """Check that a scalar is a finite number inside an inclusive interval."""
    import math

    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False, "%s must be a number, got %s" % (name, type(value).__name__)
    if not math.isfinite(float(value)):
        return False, "%s is not finite" % name
    if not (low <= float(value) <= high):
        return False, "%s must lie in [%g, %g], got %g" % (name, low, high, float(value))
    return True, ""


def probabilities(value: Any, keys: Iterable[str], tolerance: float = 1e-6) -> tuple[bool, str]:
    """Check a name-to-probability mapping: exact key set, each in [0,1], summing to one."""
    ok, why = mapping(value, required=keys)
    if not ok:
        return ok, why
    total = 0.0
    for key in keys:
        ok, why = in_range(value[key], 0.0, 1.0, name="%s[%r]" % ("weights", key))
        if not ok:
            return ok, why
        total += float(value[key])
    if abs(total - 1.0) > tolerance:
        return False, "probabilities must sum to 1 within %g, got %g" % (tolerance, total)
    return True, ""


def sequence_of_str(value: Any, max_items: Optional[int] = None) -> tuple[bool, str]:
    """Check a list of strings, rejecting a bare string and enforcing any item cap."""
    if isinstance(value, str):
        return False, "expected a sequence of strings, got a single string"
    if not isinstance(value, Sequence):
        try:
            value = list(value)
        except Exception:  # noqa: BLE001
            return False, "expected a sequence of strings, got %s" % type(value).__name__
    bad = [i for i, item in enumerate(value) if not isinstance(item, str)]
    if bad:
        return False, "entries at %s are not strings" % bad[:5]
    if max_items is not None and len(value) > max_items:
        return False, "submitted %d items, limit is %d" % (len(value), max_items)
    return True, ""


def explain(*checks: tuple[bool, str]) -> str:
    """Join failing check reasons into one message; empty when everything passed."""
    return "; ".join(reason for ok, reason in checks if not ok)


__all__ = [
    "finite_array", "binary_array", "mapping", "in_range",
    "probabilities", "sequence_of_str", "explain",
]

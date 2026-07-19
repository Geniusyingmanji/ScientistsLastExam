"""Strict JSON codec for values crossing the untrusted-candidate boundary."""

from __future__ import annotations

import base64
import math
from typing import Any

import numpy as np

MAX_ARRAY_BYTES = 64 * 1024 * 1024
MAX_DEPTH = 64


class CodecError(ValueError):
    """Raised when a value is unsafe or unsupported by the RPC protocol."""


def encode(value: Any, depth: int = 0) -> Any:
    if depth > MAX_DEPTH:
        raise CodecError("maximum nesting depth exceeded")
    if value is None or isinstance(value, (bool, str, int)):
        return value
    if isinstance(value, (float, np.floating)):
        value = float(value)
        if not math.isfinite(value):
            raise CodecError("non-finite float")
        return value
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, (complex, np.complexfloating)):
        value = complex(value)
        if not math.isfinite(value.real) or not math.isfinite(value.imag):
            raise CodecError("non-finite complex")
        return {"__fs_type__": "complex", "real": value.real, "imag": value.imag}
    if isinstance(value, np.ndarray):
        if value.dtype.hasobject or value.nbytes > MAX_ARRAY_BYTES:
            raise CodecError("unsupported or oversized ndarray")
        contiguous = np.ascontiguousarray(value)
        return {
            "__fs_type__": "ndarray",
            "dtype": contiguous.dtype.str,
            "shape": list(contiguous.shape),
            "data": base64.b64encode(contiguous.tobytes()).decode("ascii"),
        }
    if isinstance(value, tuple):
        return {"__fs_type__": "tuple", "items": [encode(v, depth + 1) for v in value]}
    if isinstance(value, list):
        return [encode(v, depth + 1) for v in value]
    if isinstance(value, dict):
        if all(isinstance(k, str) for k in value):
            return {k: encode(v, depth + 1) for k, v in value.items()}
        return {"__fs_type__": "mapping", "items": [
            [encode(k, depth + 1), encode(v, depth + 1)] for k, v in value.items()
        ]}
    raise CodecError("unsupported value type: %s" % type(value).__name__)


def decode(value: Any, depth: int = 0) -> Any:
    if depth > MAX_DEPTH:
        raise CodecError("maximum nesting depth exceeded")
    if value is None or isinstance(value, (bool, str, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise CodecError("non-finite float")
        return value
    if isinstance(value, list):
        return [decode(v, depth + 1) for v in value]
    if not isinstance(value, dict):
        raise CodecError("invalid JSON value")
    tag = value.get("__fs_type__")
    if tag == "complex":
        if set(value) != {"__fs_type__", "real", "imag"}:
            raise CodecError("invalid complex encoding")
        out = complex(value["real"], value["imag"])
        if not math.isfinite(out.real) or not math.isfinite(out.imag):
            raise CodecError("non-finite complex")
        return out
    if tag == "tuple":
        if set(value) != {"__fs_type__", "items"} or not isinstance(value["items"], list):
            raise CodecError("invalid tuple encoding")
        return tuple(decode(v, depth + 1) for v in value["items"])
    if tag == "mapping":
        if set(value) != {"__fs_type__", "items"} or not isinstance(value["items"], list):
            raise CodecError("invalid mapping encoding")
        out = {}
        for pair in value["items"]:
            if not isinstance(pair, list) or len(pair) != 2:
                raise CodecError("invalid mapping item")
            key = decode(pair[0], depth + 1)
            try:
                out[key] = decode(pair[1], depth + 1)
            except TypeError as exc:
                raise CodecError("unhashable mapping key") from exc
        return out
    if tag == "ndarray":
        if set(value) != {"__fs_type__", "dtype", "shape", "data"}:
            raise CodecError("invalid ndarray encoding")
        try:
            dtype = np.dtype(value["dtype"])
            shape = tuple(int(x) for x in value["shape"])
            raw = base64.b64decode(value["data"], validate=True)
        except Exception as exc:
            raise CodecError("invalid ndarray encoding") from exc
        if dtype.hasobject or any(x < 0 for x in shape) or len(raw) > MAX_ARRAY_BYTES:
            raise CodecError("unsupported or oversized ndarray")
        expected = dtype.itemsize
        for dim in shape:
            expected *= dim
            if expected > MAX_ARRAY_BYTES:
                raise CodecError("oversized ndarray")
        if expected != len(raw):
            raise CodecError("ndarray byte length mismatch")
        return np.frombuffer(raw, dtype=dtype).copy().reshape(shape)
    if tag is not None:
        raise CodecError("unknown type tag")
    return {str(k): decode(v, depth + 1) for k, v in value.items()}

"""Canonical representation for the scalar conservation-law method DSL."""
from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping

METHOD_FIELDS = (
    "reconstruction",
    "limiter",
    "riemann_solver",
    "time_integrator",
    "cells",
    "cfl",
    "sensor_threshold",
    "shock_blend",
    "flux_dissipation",
)
RECONSTRUCTIONS = ("constant", "muscl", "weno3")
LIMITERS = ("minmod", "mc", "van_leer", "superbee", "central")
RIEMANN_SOLVERS = ("rusanov", "godunov")
TIME_INTEGRATORS = ("euler", "ssprk2", "ssprk3")
CELL_COUNTS = (32, 48, 64, 96, 128, 192)
BOUNDS = {
    "cfl": (0.08, 0.95),
    "sensor_threshold": (0.02, 0.95),
    "shock_blend": (0.0, 1.0),
    "flux_dissipation": (1.0, 1.5),
}


def _finite_number(value, field):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(field + " must be a real number")
    value = float(value)
    if not math.isfinite(value):
        raise ValueError(field + " must be finite")
    low, high = BOUNDS[field]
    if not low <= value <= high:
        raise ValueError(field + " is outside its public bound")
    return 0.0 if value == 0.0 else value


def normalize_method(value):
    """Validate exact fields and collapse parameters inactive under a discrete choice."""
    if not isinstance(value, Mapping) or set(value) != set(METHOD_FIELDS):
        raise ValueError("method must be a mapping with exactly the documented fields")
    reconstruction = value["reconstruction"]
    limiter = value["limiter"]
    riemann_solver = value["riemann_solver"]
    time_integrator = value["time_integrator"]
    if reconstruction not in RECONSTRUCTIONS:
        raise ValueError("unknown reconstruction")
    if limiter not in LIMITERS:
        raise ValueError("unknown limiter")
    if riemann_solver not in RIEMANN_SOLVERS:
        raise ValueError("unknown Riemann solver")
    if time_integrator not in TIME_INTEGRATORS:
        raise ValueError("unknown time integrator")
    cells = value["cells"]
    if isinstance(cells, bool) or not isinstance(cells, int) or cells not in CELL_COUNTS:
        raise ValueError("cells must be one of the documented integer resolutions")

    method = {
        "reconstruction": reconstruction,
        "limiter": limiter,
        "riemann_solver": riemann_solver,
        "time_integrator": time_integrator,
        "cells": cells,
        "cfl": _finite_number(value["cfl"], "cfl"),
        "sensor_threshold": _finite_number(
            value["sensor_threshold"], "sensor_threshold"
        ),
        "shock_blend": _finite_number(value["shock_blend"], "shock_blend"),
        "flux_dissipation": _finite_number(
            value["flux_dissipation"], "flux_dissipation"
        ),
    }
    if reconstruction == "constant":
        method["limiter"] = "minmod"
        method["sensor_threshold"] = 0.5
        method["shock_blend"] = 1.0
    elif reconstruction == "muscl" and limiter == "minmod":
        method["sensor_threshold"] = 0.5
        method["shock_blend"] = 1.0
    elif method["shock_blend"] == 0.0:
        method["sensor_threshold"] = 0.5
        if reconstruction == "weno3":
            method["limiter"] = "minmod"
    if riemann_solver == "godunov":
        method["flux_dissipation"] = 1.0
    return method


def canonical_payload(method):
    normalized = normalize_method(method)
    return json.dumps(normalized, sort_keys=True, separators=(",", ":"))


def canonical_method_id(method):
    digest = hashlib.sha256(canonical_payload(method).encode("utf-8")).hexdigest()
    return "sha256:" + digest

"""Strict separation between search-visible and evaluator-only metrics.

Trusted task oracles may return rich validation, mechanism, robustness and per-instance
diagnostics. Search frameworks must receive only an explicit allowlist needed for feasibility
and selection. Optional upstream frameworks evaluate in child processes, so their full trusted
metrics are persisted in a sidecar keyed by the exact candidate source hash and merged into the
unified trajectory only after search has finished.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping


SEARCH_VISIBLE_KEYS = (
    "combined_score",
    "valid",
    "feasibility_rate",
    "constraint_violations",
    "raw_score",
    "error_message",
    "timeout",
)

METRIC_VISIBILITY_SCOPE = (
    "search receives only allowlisted feasibility/selection metrics; evaluator-only "
    "validation, mechanism, robustness and per-instance metrics remain in the trusted trace"
)


def search_visible_metrics(metrics: Mapping[str, Any]) -> dict[str, Any]:
    """Return the closed allowlist exposed to proposal and selection code.

    Unknown fields are sealed by default. This is deliberately not based on name prefixes:
    future scientific metrics cannot leak merely because a task author chose an unexpected key.
    """
    if not isinstance(metrics, Mapping):
        raise TypeError("metrics must be a mapping")
    return {key: metrics[key] for key in SEARCH_VISIBLE_KEYS if key in metrics}


def source_sha256(source: str) -> str:
    return hashlib.sha256(str(source).encode("utf-8")).hexdigest()


def candidate_sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _sidecar_path(directory: Path, digest: str) -> Path:
    if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
        raise ValueError("invalid candidate digest")
    return Path(directory) / (digest + ".json")


def store_full_metrics(directory: Path, candidate_path: Path,
                       metrics: Mapping[str, Any]) -> str:
    """Atomically store full trusted metrics and return the exact source digest.

    Repeated evaluation of identical source must yield identical metrics. A mismatch is raised
    instead of silently overwriting evidence, which also catches nondeterministic task oracles.
    """
    directory = Path(directory).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    digest = candidate_sha256(candidate_path)
    destination = _sidecar_path(directory, digest)
    rendered = json.dumps(dict(metrics), sort_keys=True, separators=(",", ":"),
                          allow_nan=False) + "\n"
    if destination.is_file():
        existing = destination.read_text(encoding="utf-8")
        if existing != rendered:
            raise RuntimeError("nondeterministic full metrics for candidate %s" % digest)
        return digest
    temporary = destination.with_name(".%s.%d.tmp" % (destination.name, os.getpid()))
    temporary.write_text(rendered, encoding="utf-8")
    os.replace(str(temporary), str(destination))
    return digest


def load_full_metrics(directory: Path, source: str,
                      public_metrics: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Load full metrics for exact source and verify the public selection view."""
    digest = source_sha256(source)
    path = _sidecar_path(Path(directory).resolve(), digest)
    if not path.is_file():
        raise FileNotFoundError("missing trusted metric sidecar for candidate %s" % digest)
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("trusted metric sidecar is not a mapping")
    if public_metrics is not None:
        expected = search_visible_metrics(value)
        observed = {
            key: public_metrics[key] for key in SEARCH_VISIBLE_KEYS
            if key in public_metrics
        }
        # Upstream databases may omit optional absent keys, but may never alter a key they
        # retain or add a search-visible value absent from the trusted oracle.
        for key, observed_value in observed.items():
            if key not in expected or observed_value != expected[key]:
                raise ValueError("upstream public metric mismatch for %s" % key)
        for required in ("combined_score", "valid"):
            if required in expected and observed.get(required) != expected[required]:
                raise ValueError("upstream omitted or changed required metric %s" % required)
    return value

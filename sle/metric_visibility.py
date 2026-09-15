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
import tempfile
from pathlib import Path
from typing import Any, Mapping, Sequence


SEARCH_VISIBLE_KEYS = (
    "combined_score",
    "valid",
    "feasibility_rate",
    "constraint_violations",
    "raw_score",
    "error_message",
    "timeout",
)

SCORE_ONLY_KEYS = ("combined_score",)

METRIC_VISIBILITY_SCOPE = (
    "search receives only allowlisted feasibility/selection metrics; evaluator-only "
    "validation, mechanism, robustness and per-instance metrics remain in the trusted trace"
)

CANDIDATE_FAILURES = frozenset((
    "candidate_timeout", "blocked_or_missing_import", "blocked_operation",
    "blocked_or_missing_file", "non_finite_candidate_value",
    "candidate_callback_schema_error", "candidate_response_too_large",
    "candidate_worker_exit", "candidate_runtime_error",
))


class EvaluationInfrastructureError(RuntimeError):
    """A trusted evaluation failed; it must never become a scientific score."""


def require_scientific_result(metrics: Mapping[str, Any]) -> None:
    if metrics.get("infrastructure_failure"):
        raise EvaluationInfrastructureError("trusted evaluation infrastructure failure")


def public_error_message(metrics: Mapping[str, Any]) -> str:
    """Expose finite failure categories, never arbitrary oracle exception text."""
    message = metrics.get("error_message")
    if message in (
        "candidate is not a regular file", "task has no declared entrypoint.txt",
        "timeout must be positive and finite", "no_code", "signed_decision_contract_invalid",
    ):
        return str(message)
    kind = metrics.get("candidate_failure_kind")
    if isinstance(kind, str) and kind in CANDIDATE_FAILURES:
        return "candidate invalid: " + kind
    if isinstance(message, str) and message.startswith("candidate invalid: "):
        if message[len("candidate invalid: "):] in CANDIDATE_FAILURES:
            return message
    if metrics.get("timeout"):
        return "candidate evaluation timed out"
    return "evaluation rejected; details retained in trusted diagnostics"


def search_visible_metrics(metrics: Mapping[str, Any]) -> dict[str, Any]:
    """Return the closed allowlist exposed to proposal and selection code.

    Unknown fields are sealed by default. This is deliberately not based on name prefixes:
    future scientific metrics cannot leak merely because a task author chose an unexpected key.
    """
    if not isinstance(metrics, Mapping):
        raise TypeError("metrics must be a mapping")
    require_scientific_result(metrics)
    public = {key: metrics[key] for key in SEARCH_VISIBLE_KEYS if key in metrics}
    if public.get("error_message"):
        public["error_message"] = public_error_message(metrics)
    return public


def store_infrastructure_failure(directory: Path, diagnostic: Mapping[str, Any]) -> None:
    """Persist a private fault marker so swallowed backend exceptions still fail closed."""
    failures = Path(directory) / "infrastructure_failures"
    failures.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        rendered = json.dumps(dict(diagnostic), allow_nan=False, default=str)
    except (TypeError, ValueError):
        rendered = json.dumps({"diagnostic": repr(dict(diagnostic))[:8000]})
    descriptor, path = tempfile.mkstemp(prefix="failure_", suffix=".json", dir=str(failures))
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(rendered + "\n")


def require_healthy_evaluations(directory: Path) -> None:
    """Optional frameworks may catch evaluator exceptions; do not publish such runs."""
    failures = Path(directory) / "infrastructure_failures"
    if failures.is_dir() and any(failures.iterdir()):
        raise EvaluationInfrastructureError(
            "trusted evaluation infrastructure failed; use a fresh run directory"
        )


def score_only_metrics(metrics: Mapping[str, Any]) -> dict[str, Any]:
    """Return the scalar objective-only prompt view.

    This is a feedback-bandwidth treatment, not a no-feedback treatment: search may
    still select the next parent with the trusted objective, but the proposal prompt
    receives only ``combined_score``.  Filtering through the closed search-visible
    allowlist first keeps future evaluator-only fields sealed by default.
    """
    visible = search_visible_metrics(metrics)
    return {key: visible[key] for key in SCORE_ONLY_KEYS if key in visible}


def shuffled_feedback_metrics(
    history: Sequence[Mapping[str, Any]], *, seed: int, proposal_step: int
) -> dict[str, Any]:
    """Select one prior metric record without resume-dependent RNG state."""
    if not history:
        raise ValueError("shuffled feedback requires prior metrics")
    selector = hashlib.sha256(
        ("%d:%d" % (seed, proposal_step)).encode("ascii")
    ).digest()
    index = int.from_bytes(selector[:8], "big") % len(history)
    return dict(history[index])


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
    require_scientific_result(metrics)
    directory = Path(directory).resolve()
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    digest = candidate_sha256(candidate_path)
    destination = _sidecar_path(directory, digest)
    rendered = json.dumps(dict(metrics), sort_keys=True, separators=(",", ":"),
                          allow_nan=False) + "\n"
    if destination.is_file():
        existing = destination.read_text(encoding="utf-8")
        if existing != rendered:
            raise RuntimeError("nondeterministic full metrics for candidate %s" % digest)
        return digest
    # Link a complete private file into place exactly once. Concurrent evaluations
    # may agree, but cannot overwrite a conflicting observation between the check
    # above and publication (os.replace would silently lose that evidence).
    descriptor, temporary = tempfile.mkstemp(prefix="." + digest, dir=str(directory))
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(rendered)
        try:
            os.link(temporary, str(destination))
        except FileExistsError:
            if destination.read_text(encoding="utf-8") != rendered:
                raise RuntimeError("nondeterministic full metrics for candidate %s" % digest)
    finally:
        os.unlink(temporary)
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
    require_scientific_result(value)
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

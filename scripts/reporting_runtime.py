"""Retain historical diagnostics while binding new report evidence to durable receipts."""
from __future__ import annotations

import hashlib
from pathlib import Path

from sle.run_verification import verify_run


def report_runtime_binding(workdir: Path, manifest: dict) -> dict:
    descriptor = manifest.get("trusted_evaluator_runtime")
    fingerprint = descriptor.get("fingerprint_sha256") if isinstance(descriptor, dict) else None
    binding = {
        "trusted_evidence": False,
        "trusted_evaluator_runtime_sha256": fingerprint,
        "verification_status": (
            "legacy_format" if "trusted_evaluator_runtime" not in manifest else "unverified"
        ),
        "run_manifest_sha256": hashlib.sha256(
            (workdir / "run_manifest.json").read_bytes()).hexdigest(),
        "proposal_budget": None,
    }
    try:
        verification = verify_run(workdir)
    except (OSError, ValueError):
        # Raw legacy diagnostics do not acquire a modern runtime identity or receipt.
        return binding
    if verification.get("verified") is True and fingerprint is not None and (
        verification.get("trusted_evaluator_runtime_sha256") == fingerprint
    ):
        binding.update(trusted_evidence=True, verification_status="verified",
                       proposal_budget=verification["budget"])
    return binding

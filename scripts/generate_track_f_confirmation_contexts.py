#!/usr/bin/env python3
"""Generate private Track F fresh-world contexts and a public hash commitment.

The private manifest contains root entropy, procedural seeds, resolved worlds and
Diffraction calibration anchors.  It must remain outside version control.  The public
commitment contains only hashes and source/task bindings and is safe to preregister
before any model run.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import importlib.util
import json
import os
import platform
import secrets
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from frontier_science.algorithms.common import (  # noqa: E402
    atomic_write_text,
    runtime_source_sha256,
    task_contract_sha256,
)
from frontier_science.evaluate import canonical_trusted_context  # noqa: E402
from frontier_science.provenance import source_provenance  # noqa: E402
from frontier_science.registry import find_task  # noqa: E402


SUPPORTED_TASKS = (
    "DynamicalSystems/ActiveLawDiscovery",
    "Optics/DiffractionGratingDesign",
)
TASK_SHORT_NAMES = {
    "DynamicalSystems/ActiveLawDiscovery": "active-law",
    "Optics/DiffractionGratingDesign": "diffraction",
}
GENERATOR_ENTRYPOINTS = {
    "DynamicalSystems/ActiveLawDiscovery": "active_law_fresh_v1",
    "Optics/DiffractionGratingDesign": "diffraction_grating_fresh_v1",
}
WORLD_COUNTS = {
    "DynamicalSystems/ActiveLawDiscovery": 7,
    "Optics/DiffractionGratingDesign": 3,
}


def _csv(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def _replicates(value: str) -> list[int]:
    try:
        replicates = [int(part) for part in _csv(value)]
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "replicates must be comma-separated non-negative integers"
        ) from exc
    if (
        not replicates
        or any(value < 0 for value in replicates)
        or len(set(replicates)) != len(replicates)
    ):
        raise argparse.ArgumentTypeError(
            "replicates must be distinct non-negative integers"
        )
    return replicates


def _validate_cohort_id(value: str) -> str:
    if (
        not isinstance(value, str)
        or not 1 <= len(value) <= 24
        or any(character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.-"
               for character in value)
    ):
        raise ValueError("cohort id must be 1--24 portable filename characters")
    return value


def _root_entropy(path: Path | None) -> str:
    value = secrets.token_hex(32) if path is None else path.read_text(
        encoding="utf-8"
    ).strip()
    if (
        len(value) != 64
        or value.lower() != value
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ValueError("root entropy must be exactly 32 lowercase hex bytes")
    return value


def derive_master_seed(root_entropy_hex: str, task: str, replicate_id: int) -> int:
    """Derive one 63-bit seed with task/replicate domain separation."""
    key = bytes.fromhex(root_entropy_hex)
    message = (
        "frontier-science-track-f-confirmation-v1\0%s\0%d"
        % (task, int(replicate_id))
    ).encode("utf-8")
    digest = hmac.new(key, message, hashlib.sha256).digest()
    return int.from_bytes(digest[:8], "big") & ((1 << 63) - 1)


def _load_oracle(task: str):
    spec = find_task(task, include_uncertified=True)
    path = spec.task_dir / "verification" / "evaluator.py"
    module_spec = importlib.util.spec_from_file_location(
        "track_f_context_generator_" + TASK_SHORT_NAMES[task].replace("-", "_"),
        path,
    )
    if module_spec is None or module_spec.loader is None:
        raise ImportError("cannot load confirmation oracle for %s" % task)
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    builder = getattr(module, "build_confirmation_context", None)
    if not callable(builder):
        raise TypeError("task lacks build_confirmation_context: %s" % task)
    return spec, builder


def _private_write(path: Path, document: dict[str, Any]) -> bytes:
    path = path.expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        os.chmod(path.parent, 0o700)
    except PermissionError:
        pass
    payload = (
        json.dumps(document, indent=2, allow_nan=False, sort_keys=True) + "\n"
    ).encode("utf-8")
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=".%s." % path.name, dir=str(path.parent)
    )
    temporary = Path(temporary_name)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(str(temporary), str(path))
        os.chmod(path, 0o600)
    finally:
        temporary.unlink(missing_ok=True)
    return payload


def generate(
    *,
    cohort_id: str,
    tasks: list[str],
    replicates: list[int],
    root_entropy_hex: str,
    private_output: Path,
    public_output: Path,
    command: list[str] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    cohort_id = _validate_cohort_id(cohort_id)
    if not tasks or len(set(tasks)) != len(tasks):
        raise ValueError("tasks must be non-empty and unique")
    unknown = sorted(set(tasks) - set(SUPPORTED_TASKS))
    if unknown:
        raise ValueError("unsupported Track F tasks: %s" % ", ".join(unknown))
    if not replicates or any(value < 0 for value in replicates):
        raise ValueError("replicates must be non-empty non-negative integers")
    provenance = source_provenance(ROOT, command=command)
    if (
        provenance.get("git_available") is not True
        or provenance.get("source_tree_dirty") is not False
    ):
        raise RuntimeError(
            "confirmation contexts require a clean source revision before generation"
        )
    created_at = datetime.now(timezone.utc).isoformat()
    task_bindings = []
    loaded = {}
    for task in tasks:
        spec, builder = _load_oracle(task)
        loaded[task] = (spec, builder)
        task_bindings.append({
            "task": task,
            "task_contract_sha256": task_contract_sha256(spec),
            "generator": GENERATOR_ENTRYPOINTS[task],
            "world_count": WORLD_COUNTS[task],
        })
    blocks = []
    public_blocks = []
    derived_seeds = set()
    for task in tasks:
        _, builder = loaded[task]
        for replicate_id in replicates:
            master_seed = derive_master_seed(
                root_entropy_hex, task, replicate_id
            )
            if master_seed in derived_seeds:
                raise RuntimeError("derived confirmation seed collision")
            derived_seeds.add(master_seed)
            panel_id = "%s-%s-r%d" % (
                cohort_id, TASK_SHORT_NAMES[task], replicate_id
            )
            context = builder(panel_id, master_seed)
            payload = canonical_trusted_context(context)
            digest = hashlib.sha256(payload).hexdigest()
            blocks.append({
                "task": task,
                "replicate_id": replicate_id,
                "context_sha256": digest,
                "context": context,
            })
            public_blocks.append({
                "task": task,
                "replicate_id": replicate_id,
                "panel_id": panel_id,
                "generator": GENERATOR_ENTRYPOINTS[task],
                "world_count": WORLD_COUNTS[task],
                "context_sha256": digest,
                "context_utf8_bytes": len(payload),
            })
    source_binding = {
        "git_revision": provenance["git_revision"],
        "runtime_source_sha256": runtime_source_sha256(),
        "tasks": task_bindings,
    }
    private_document = {
        "schema_version": 1,
        "purpose": "track_f_private_fresh_confirmation_contexts",
        "cohort_id": cohort_id,
        "created_at": created_at,
        "root_entropy_hex": root_entropy_hex,
        "source_binding": source_binding,
        "blocks": blocks,
    }
    private_payload = _private_write(private_output, private_document)
    public_document = {
        "schema_version": 1,
        "commitment_version": 1,
        "purpose": "track_f_fresh_confirmation_context_commitment",
        "cohort_id": cohort_id,
        "created_at": created_at,
        "source_provenance": provenance,
        "environment": {"python": sys.version, "platform": platform.platform()},
        "source_binding": source_binding,
        "private_manifest_sha256": hashlib.sha256(private_payload).hexdigest(),
        "private_manifest_utf8_bytes": len(private_payload),
        "block_count": len(public_blocks),
        "blocks": public_blocks,
        "claim_limit": (
            "pre_search_hash_commitment_only_not_confirmation_outcome_or_"
            "autonomous_discovery_evidence"
        ),
    }
    public_output = public_output.expanduser().resolve()
    public_output.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(
        public_output,
        json.dumps(public_document, indent=2, allow_nan=False) + "\n",
    )
    return private_document, public_document


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cohort-id", required=True)
    parser.add_argument(
        "--tasks", default=",".join(SUPPORTED_TASKS),
        help="comma-separated supported task IDs",
    )
    parser.add_argument("--replicates", type=_replicates, required=True)
    parser.add_argument(
        "--root-entropy-file", type=Path, default=None,
        help="optional 32-byte lowercase hex secret; default uses system CSPRNG",
    )
    parser.add_argument("--private-output", type=Path, required=True)
    parser.add_argument("--public-output", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    raw_argv = list(argv) if argv is not None else sys.argv[1:]
    args = build_parser().parse_args(raw_argv)
    private_output = args.private_output.expanduser().resolve()
    public_output = args.public_output.expanduser().resolve()
    if private_output.exists() or public_output.exists():
        raise SystemExit("refusing to overwrite a confirmation context or commitment")
    tasks = _csv(args.tasks)
    try:
        _, public = generate(
            cohort_id=args.cohort_id,
            tasks=tasks,
            replicates=args.replicates,
            root_entropy_hex=_root_entropy(args.root_entropy_file),
            private_output=private_output,
            public_output=public_output,
            command=[sys.executable, str(Path(__file__).resolve()), *raw_argv],
        )
    except (OSError, ValueError, RuntimeError, TypeError) as exc:
        raise SystemExit(str(exc)) from exc
    print(json.dumps({
        "public_output": str(public_output),
        "private_output": str(private_output),
        "block_count": public["block_count"],
        "private_manifest_sha256": public["private_manifest_sha256"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Run reproducible, multi-seed Frontier-Science experiments.

The output contains every raw run plus per-task and overall mean/95% CI for
terminal best score, best-so-far AUC over charged proposal/benchmark
``budget_units``, actual ``oracle_calls``, wall time, tokens, and estimated cost.
Only the seven certified tasks are selected unless ``--all`` is explicit.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import multiprocessing
import platform
import random
import stat
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sle.algorithms import ALGORITHMS, get_algorithm  # noqa: E402
from sle.algorithms.common import llm_condition_sha256  # noqa: E402
from sle.algorithms.common import atomic_write_text  # noqa: E402
from sle.algorithms.common import feedback_scope  # noqa: E402
from sle.algorithms.common import runtime_source_sha256  # noqa: E402
from sle.algorithms.common import task_contract_sha256  # noqa: E402
from sle.algorithms.common import task_package_sha256  # noqa: E402
from sle.config import load_llm_client  # noqa: E402
from sle.certification import certification_status  # noqa: E402
from sle.evaluate import resolve_trusted_runtime  # noqa: E402
from sle.frontier import frontier_binding  # noqa: E402
from sle.llm import LLMClient  # noqa: E402
from sle.protocol import mean_confidence_interval  # noqa: E402
from sle.protocol import compact_trajectory_snapshot  # noqa: E402
from sle.provenance import (  # noqa: E402
    SOURCE_SCOPE,
    finalize_report_trust,
    source_provenance,
)
from sle.registry import find_task, list_tasks  # noqa: E402
from sle.run_verification import verify_run  # noqa: E402
from sle.runtime_identity import validate_runtime_descriptor  # noqa: E402


def _csv(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def _seeds(value: str) -> list[int]:
    try:
        seeds = [int(part) for part in _csv(value)]
    except ValueError as exc:
        raise argparse.ArgumentTypeError("seeds must be comma-separated integers") from exc
    if not seeds:
        raise argparse.ArgumentTypeError("at least one seed is required")
    return seeds


def _run_key(task_id: str, algorithm: str, feedback_mode: str, seed: int) -> str:
    return "%s|%s|%s|%d" % (task_id, algorithm, feedback_mode, seed)


def _trusted_runtime_records(specs: list[Any]) -> dict[str, dict[str, Any]]:
    """Resolve each task's evaluator once without retaining executable paths."""

    records = {}
    for spec in specs:
        runtime = resolve_trusted_runtime(spec.task_dir)
        descriptor = validate_runtime_descriptor(runtime.descriptor)
        records[spec.task_id] = {
            "descriptor": descriptor,
            "fingerprint_sha256": runtime.fingerprint_sha256,
        }
    return records


def _frozen_task_bindings(specs: list[Any]) -> dict[str, dict[str, Any]]:
    """Freeze every source, task, frontier, and evaluator input used by workers."""

    runtimes = _trusted_runtime_records(specs)
    bindings = {}
    for spec in specs:
        card = spec.task_dir / "TASK_CARD.yaml"
        runtime = runtimes[spec.task_id]
        bindings[spec.task_id] = {
            "task_contract_sha256": task_contract_sha256(spec),
            "task_package_sha256": task_package_sha256(spec),
            "task_card_sha256": (
                hashlib.sha256(card.read_bytes()).hexdigest()
                if card.is_file() else None
            ),
            "runtime_source_sha256": runtime_source_sha256(),
            **frontier_binding(spec),
            "trusted_evaluator_runtime": runtime["descriptor"],
            "trusted_evaluator_runtime_sha256": runtime[
                "fingerprint_sha256"
            ],
        }
    return bindings


def _assert_task_binding(spec: Any, frozen: dict[str, Any]) -> None:
    current = _frozen_task_bindings([spec])[spec.task_id]
    if current != frozen:
        raise RuntimeError("frozen task binding changed")


def _assert_task_bindings(
    specs: list[Any], bindings: dict[str, dict[str, Any]]
) -> None:
    for spec in specs:
        _assert_task_binding(spec, bindings[spec.task_id])


def _final_integrity_errors(
    specs: list[Any],
    bindings: dict[str, dict[str, Any]],
    initial_provenance: dict[str, Any],
) -> list[str]:
    errors = []
    try:
        _assert_task_bindings(specs, bindings)
    except Exception:  # noqa: BLE001 - emit a path-free trust decision
        errors.append("task_binding_changed")
    current = source_provenance(ROOT)
    provenance_fields = ("git_revision", "source_tree_dirty", "source_changes")
    if any(
        current.get(field) != initial_provenance.get(field)
        for field in provenance_fields
    ):
        errors.append("source_provenance_changed")
    return errors


class _BindingCheckedLLM:
    """Guard every provider call against task/runtime TOCTOU changes."""

    def __init__(self, delegate: LLMClient, spec: Any, binding: dict[str, Any]):
        self._delegate = delegate
        self._spec = spec
        self._binding = binding

    def __getattr__(self, name: str) -> Any:
        return getattr(self._delegate, name)

    def complete(self, *args: Any, **kwargs: Any) -> str:
        _assert_task_binding(self._spec, self._binding)
        result = self._delegate.complete(*args, **kwargs)
        _assert_task_binding(self._spec, self._binding)
        return result


def _condition_order(
    feedback_modes: list[str], seed: int, design: str = "reverse_parity",
    *, schedule_index: int | None = None,
) -> list[str]:
    """Return the preregistered within-block condition execution order."""
    modes = list(feedback_modes)
    if design == "reverse_parity":
        return list(reversed(modes)) if int(seed) % 2 else modes
    if design == "balanced_williams":
        if len(modes) != 4 or len(set(modes)) != 4:
            raise ValueError("balanced_williams requires exactly four distinct modes")
        # A B D C, B C A D, C D B A, D A C B. Each condition occupies each
        # position once and every directed first-order carryover occurs once.
        rows = (
            (0, 1, 3, 2),
            (1, 2, 0, 3),
            (2, 3, 1, 0),
            (3, 0, 2, 1),
        )
        index = int(seed) if schedule_index is None else int(schedule_index)
        return [modes[position] for position in rows[index % len(rows)]]
    raise ValueError("unknown condition order design %r" % design)


def _condition_schedule(
    feedback_modes: list[str], seeds: list[int], design: str,
    randomization_seed: int | None,
) -> list[list[str]]:
    """Build and freeze the full within-block condition schedule."""
    if design == "balanced_williams":
        if randomization_seed is None:
            raise ValueError(
                "balanced_williams requires --condition-order-randomization-seed"
            )
        row_indices = [index % 4 for index in range(len(seeds))]
        random.Random(int(randomization_seed)).shuffle(row_indices)
        return [
            _condition_order(
                feedback_modes, seed, design, schedule_index=row_index
            )
            for seed, row_index in zip(seeds, row_indices)
        ]
    if randomization_seed is not None:
        raise ValueError(
            "--condition-order-randomization-seed requires balanced_williams"
        )
    return [
        _condition_order(feedback_modes, seed, design)
        for seed in seeds
    ]


def _execution_preregistration_is_committed(path: Path) -> bool:
    """Return whether ``path`` exactly matches its blob at the current HEAD."""

    resolved = Path(path).resolve()
    try:
        repository_relative = resolved.relative_to(ROOT).as_posix()
    except ValueError:
        return False
    tracked = subprocess.run(
        ["git", "ls-files", "--error-unmatch", repository_relative],
        cwd=str(ROOT), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        check=False,
    ).returncode == 0
    if not tracked:
        return False
    committed_payload = subprocess.check_output(
        ["git", "show", "HEAD:" + repository_relative],
        cwd=str(ROOT), stderr=subprocess.DEVNULL,
    )
    return committed_payload == resolved.read_bytes()


def _bound_repository_file(binding: dict[str, Any], role: str) -> Path:
    """Resolve and hash-check one immutable preregistration input."""

    if not isinstance(binding, dict):
        raise SystemExit("preregistration %s binding is invalid" % role)
    relative = binding.get("path")
    expected_hash = binding.get("sha256")
    if not isinstance(relative, str) or not isinstance(expected_hash, str):
        raise SystemExit("preregistration %s binding is incomplete" % role)
    resolved = (ROOT / relative).resolve()
    try:
        resolved.relative_to(ROOT)
    except ValueError as exc:
        raise SystemExit(
            "preregistration %s binding escapes the repository" % role
        ) from exc
    if not resolved.is_file():
        raise SystemExit("preregistration %s input is missing" % role)
    if hashlib.sha256(resolved.read_bytes()).hexdigest() != expected_hash:
        raise SystemExit("preregistration %s hash differs" % role)
    return resolved


def _preregistration_record(
    path: Path | None,
    *,
    raw_argv: list[str] | None = None,
    specs: list[Any] | None = None,
    llm: LLMClient | None = None,
    task_bindings: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    """Bind and, when declared, enforce an execution preregistration.

    Legacy narrative preregistrations remain hash-bound. A document declaring
    ``design.primary_command`` is an executable contract and fails closed before
    worker dispatch if its command, model, source, task package, or prerequisite
    evidence differs. ``--resume`` is the sole permitted command suffix.
    """

    if path is None:
        return None
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise SystemExit("--preregistration must name a regular file")
    payload = resolved.read_bytes()
    try:
        document = json.loads(payload)
    except ValueError:
        document = None
    try:
        recorded_path = str(resolved.relative_to(ROOT))
    except ValueError:
        recorded_path = str(resolved)
    record = {
        "path": recorded_path,
        "sha256": hashlib.sha256(payload).hexdigest(),
        "bytes": len(payload),
    }
    if not isinstance(document, dict):
        record["execution_contract_validated"] = False
        return record
    design = document.get("design") or {}
    expected_command = (
        design.get("primary_command") if isinstance(design, dict) else None
    )
    if expected_command is None:
        record["execution_contract_validated"] = False
        return record
    if not (
        isinstance(expected_command, list)
        and len(expected_command) >= 2
        and all(isinstance(value, str) for value in expected_command)
        and Path(expected_command[1]).name == Path(__file__).name
    ):
        raise SystemExit("preregistration primary_command is invalid")
    if not _execution_preregistration_is_committed(resolved):
        raise SystemExit(
            "execution preregistration must be tracked and match HEAD"
        )
    if (
        raw_argv is None or specs is None or llm is None
        or task_bindings is None
    ):
        raise SystemExit("execution preregistration lacks runtime validation inputs")
    expected_argv = expected_command[2:]
    command_matches = raw_argv == expected_argv
    resume_matches = raw_argv == expected_argv + ["--resume"]
    if not (command_matches or resume_matches):
        raise SystemExit("runtime command differs from preregistration primary_command")
    resume_permitted = design.get("resume_permitted", True)
    if not isinstance(resume_permitted, bool):
        raise SystemExit("preregistration resume_permitted must be boolean")
    if resume_matches and not resume_permitted:
        raise SystemExit("preregistration does not permit resume")

    model = document.get("model_condition") or {}
    expected_llm = model.get("llm_condition_sha256")
    if expected_llm and expected_llm != llm_condition_sha256(llm):
        raise SystemExit("runtime model condition differs from preregistration")
    readable_model_condition = {
        "wire": llm.config.wire,
        "endpoint_sha256": hashlib.sha256(
            llm.config.base_url.encode("utf-8")
        ).hexdigest(),
        "model": llm.config.model,
        "max_output_tokens": llm.config.max_output_tokens,
        "temperature": llm.config.temperature,
        "reasoning_effort": llm.config.reasoning_effort,
        "provider_request_timeout_seconds": llm.config.timeout_seconds,
        "stream": bool(getattr(llm.config, "stream", False)),
        "chat_max_tokens_field": getattr(
            llm.config, "chat_max_tokens_field", "max_tokens"
        ),
        "chat_reasoning_fallback": bool(getattr(
            llm.config, "chat_reasoning_fallback", False
        )),
        "server_side_seed_control": False,
    }
    declared_readable_fields = sorted(
        field for field in readable_model_condition if field in model
    )
    required_readable_fields = model.get("required_readable_fields")
    if required_readable_fields is not None:
        if not (
            isinstance(required_readable_fields, list)
            and required_readable_fields
            and all(
                isinstance(field, str) and field in readable_model_condition
                for field in required_readable_fields
            )
        ):
            raise SystemExit(
                "preregistration required readable model fields are invalid"
            )
        missing_readable = sorted(
            set(required_readable_fields) - set(declared_readable_fields)
        )
        if missing_readable:
            raise SystemExit(
                "preregistration is missing readable model condition fields: %s"
                % ", ".join(missing_readable)
            )
    if any(
        field in model and model[field] != value
        for field, value in readable_model_condition.items()
    ):
        raise SystemExit(
            "runtime readable model condition differs from preregistration"
        )
    frozen_source = document.get("frozen_source") or {}
    expected_runtime = frozen_source.get("runtime_source_sha256")
    if expected_runtime and expected_runtime != runtime_source_sha256():
        raise SystemExit("runtime source differs from preregistration")
    parent_revision = frozen_source.get("parent_revision")
    if parent_revision:
        current_provenance = source_provenance(ROOT)
        if current_provenance.get("source_tree_dirty") is not False:
            raise SystemExit("scoped source tree is dirty at execution")
        ancestor = subprocess.run(
            ["git", "merge-base", "--is-ancestor", str(parent_revision), "HEAD"],
            cwd=str(ROOT), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            check=False,
        ).returncode == 0
        if not ancestor:
            raise SystemExit("preregistration parent revision is not an ancestor")
        changes = subprocess.check_output(
            [
                "git", "diff", "--name-only", str(parent_revision), "HEAD",
                "--", *SOURCE_SCOPE,
            ],
            cwd=str(ROOT), text=True, stderr=subprocess.DEVNULL,
        ).splitlines()
        if any(value.strip() for value in changes):
            raise SystemExit("scoped source changed after preregistration parent")

    task_rows = design.get("tasks")
    if task_rows is not None:
        if not isinstance(task_rows, list) or [
            row.get("task") if isinstance(row, dict) else None for row in task_rows
        ] != [spec.task_id for spec in specs]:
            raise SystemExit("runtime task cohort differs from preregistration")
        for row, spec in zip(task_rows, specs):
            actual = task_bindings[spec.task_id]
            for field, value in actual.items():
                if row.get(field) != value:
                    if field.startswith("trusted_evaluator_runtime"):
                        raise SystemExit(
                            "trusted evaluator runtime differs from preregistration "
                            "for %s" % spec.task_id
                        )
                    raise SystemExit(
                        "%s differs from preregistration for %s"
                        % (field, spec.task_id)
                    )

    source_cohort = document.get("source_cohort")
    if source_cohort is not None:
        _bound_repository_file(source_cohort, "source_cohort")

    prerequisites = document.get("prerequisites") or []
    if not isinstance(prerequisites, list):
        raise SystemExit("preregistration prerequisites must be a list")
    for prerequisite in prerequisites:
        if not isinstance(prerequisite, dict):
            raise SystemExit("preregistration prerequisite is invalid")
        evidence_path = _bound_repository_file(prerequisite, "prerequisite")
        try:
            evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
        except ValueError as exc:
            raise SystemExit("preregistration prerequisite is not valid JSON") from exc
        if not (
            isinstance(evidence, dict)
            and evidence.get("execution_passed") is True
            and evidence.get("trusted_evidence") is True
            and evidence.get("passed") is True
        ):
            raise SystemExit("preregistration prerequisite is not trusted passing evidence")

    record.update({
        "preregistration_id": document.get("preregistration_id"),
        "claim_limit": document.get("claim_limit"),
        "execution_contract_validated": True,
        "command_contract_matches": True,
        "resume_suffix_permitted": resume_permitted,
        "model_condition_matches": not expected_llm or bool(
            expected_llm == llm_condition_sha256(llm)
        ),
        "readable_model_condition_matches": bool(declared_readable_fields),
        "readable_model_condition_status": (
            "matched" if declared_readable_fields else "not_declared"
        ),
        "readable_model_condition_declared_fields": declared_readable_fields,
        "runtime_source_matches": not expected_runtime or bool(
            expected_runtime == runtime_source_sha256()
        ),
        "scoped_source_tree_clean": bool(
            not parent_revision
            or current_provenance.get("source_tree_dirty") is False
        ),
        "task_count": len(specs),
        "trusted_runtime_count": len(task_bindings),
        "prerequisite_count": len(prerequisites),
        "source_cohort_matches": source_cohort is not None,
    })
    return record


def _maturity_contract_sha256(spec: Any) -> str:
    """Match the broader contract used by the task-maturity ledger."""

    paths: list[Path] = []
    for suffix in (
        "Task.md", "solution.py", "verification/evaluator.py", "frontier_eval",
    ):
        path = spec.task_dir / suffix
        if path.is_dir():
            paths.extend(
                child for child in path.rglob("*")
                if child.is_file() and "__pycache__" not in child.parts
            )
        elif path.is_file():
            paths.append(path)
    card = spec.task_dir / "TASK_CARD.yaml"
    if card.is_file():
        paths.append(card)
    digest = hashlib.sha256()
    for path in sorted(set(paths)):
        relative = path.relative_to(spec.task_dir).as_posix().encode("utf-8")
        payload = path.read_bytes()
        digest.update(len(relative).to_bytes(4, "big"))
        digest.update(relative)
        digest.update(len(payload).to_bytes(8, "big"))
        digest.update(payload)
    return digest.hexdigest()


def _cohort_manifest_record(
    path: Path | None, specs: list[Any], *, include_uncertified: bool,
) -> dict[str, Any] | None:
    """Validate and bind an exact task cohort before any model call.

    A cohort manifest is stricter than a generic preregistration: task order,
    runtime contracts and task-card hashes must all match the requested run.
    """

    if path is None:
        return None
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise SystemExit("--cohort-manifest must name a regular JSON file")
    payload = resolved.read_bytes()
    try:
        document = json.loads(payload)
    except ValueError as exc:
        raise SystemExit("--cohort-manifest is not valid JSON") from exc
    if document.get("schema_version") != 1:
        raise SystemExit("unsupported cohort manifest schema")
    rows = document.get("tasks")
    if not isinstance(rows, list) or not rows:
        raise SystemExit("cohort manifest must contain a nonempty tasks list")
    manifest_ids = [row.get("task") for row in rows if isinstance(row, dict)]
    requested_ids = [spec.task_id for spec in specs]
    if manifest_ids != requested_ids:
        raise SystemExit(
            "cohort manifest task order does not match the requested task cohort"
        )
    for row, spec in zip(rows, specs):
        if row.get("maturity_contract_sha256") != _maturity_contract_sha256(spec):
            raise SystemExit(
                "cohort manifest maturity contract differs for %s" % spec.task_id
            )
        expected_runtime = row.get("runtime_contract_sha256")
        if expected_runtime != task_contract_sha256(spec):
            raise SystemExit(
                "cohort manifest runtime contract differs for %s" % spec.task_id
            )
        card = spec.task_dir / "TASK_CARD.yaml"
        actual_card = (
            hashlib.sha256(card.read_bytes()).hexdigest()
            if card.is_file() else None
        )
        if row.get("task_card_sha256") != actual_card:
            raise SystemExit(
                "cohort manifest task card differs for %s" % spec.task_id
            )
    if not include_uncertified and any(
        certification_status(spec.task_id) != "certified" for spec in specs
    ):
        raise SystemExit(
            "cohort manifest includes non-certified tasks; pass --all explicitly"
        )
    try:
        recorded_path = str(resolved.relative_to(ROOT))
    except ValueError:
        recorded_path = str(resolved)
    return {
        "path": recorded_path,
        "sha256": hashlib.sha256(payload).hexdigest(),
        "bytes": len(payload),
        "manifest_id": document.get("manifest_id"),
        "analysis_role": document.get("analysis_role"),
        "claim_limit": document.get("claim_limit"),
        "confirmatory_reuse_permitted": (
            (document.get("selection") or {}).get("confirmatory_reuse_permitted")
        ),
        "task_count": len(rows),
    }


def _execution_blocks(
    task_ids: list[str], algorithms: list[str], seeds: list[int],
    condition_schedule: list[list[str]],
) -> list[dict[str, Any]]:
    if len(seeds) != len(condition_schedule):
        raise ValueError("condition schedule does not match replicate identifiers")
    blocks = []
    for task_id in task_ids:
        for algorithm in algorithms:
            for seed, ordered_modes in zip(seeds, condition_schedule):
                blocks.append({
                    "block_index": len(blocks) + 1,
                    "task": task_id,
                    "algorithm": algorithm,
                    "seed": int(seed),
                    "feedback_modes": list(ordered_modes),
                })
    return blocks


def _safe_batch_cell_paths(
    work_root: Any,
    task_id: str,
    algorithm: str,
    feedback_modes: list[str],
    seed: int,
) -> list[Path]:
    """Resolve worker cell paths without following aliases outside its root."""

    root = Path(work_root)
    try:
        root_stat = root.lstat()
        resolved_root = root.resolve(strict=True)
    except OSError as exc:
        raise RuntimeError("unsafe batch cell path: work root is unavailable") from exc
    if (
        not root.is_absolute()
        or root != resolved_root
        or stat.S_ISLNK(root_stat.st_mode)
        or not stat.S_ISDIR(root_stat.st_mode)
    ):
        raise RuntimeError("unsafe batch cell path: work root is not canonical")

    def component(value: str, role: str) -> str:
        allowed = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-"
        if (
            not value or len(value) > 64 or value in {".", ".."}
            or any(character not in allowed for character in value)
        ):
            raise RuntimeError(
                "unsafe batch cell path: invalid %s component" % role
            )
        return value

    task_component = component(task_id.replace("/", "__"), "task")
    algorithm_component = component(algorithm, "algorithm")
    seed_component = component("seed_%d" % seed, "seed")
    paths = []
    for feedback_mode in feedback_modes:
        parts = (
            task_component,
            algorithm_component,
            component(str(feedback_mode), "feedback mode"),
            seed_component,
        )
        candidate = root
        for part in parts:
            candidate = candidate / part
            try:
                candidate_stat = candidate.lstat()
            except FileNotFoundError:
                continue
            except OSError as exc:
                raise RuntimeError("unsafe batch cell path: cannot inspect path") from exc
            if (
                stat.S_ISLNK(candidate_stat.st_mode)
                or not stat.S_ISDIR(candidate_stat.st_mode)
            ):
                raise RuntimeError(
                    "unsafe batch cell path: existing component is not a directory"
                )
        try:
            resolved = candidate.resolve(strict=False)
            resolved.relative_to(root)
        except (OSError, ValueError) as exc:
            raise RuntimeError("unsafe batch cell path: path escapes work root") from exc
        if resolved != candidate:
            raise RuntimeError("unsafe batch cell path: path is aliased")
        paths.append(candidate)
    return paths


def _execute_block(payload: dict[str, Any]) -> dict[str, Any]:
    """Execute one task/algorithm/replicate block in an isolated process.

    Conditions remain serial in their frozen Williams order.  Only distinct
    blocks may be scheduled concurrently, so Python RNG state, environment
    changes and LLM client accounting cannot leak between blocks.
    """
    task_id = str(payload["task"])
    algorithm_name = str(payload["algorithm"])
    seed = int(payload["seed"])
    spec = find_task(task_id, include_uncertified=True)
    frozen_binding = payload["frozen_task_binding"]
    _assert_task_binding(spec, frozen_binding)
    if task_id != spec.task_id:
        raise RuntimeError("unsafe batch cell path: task identifier is not canonical")
    work_root = Path(payload["work_root"])
    feedback_modes = [str(value) for value in payload["feedback_modes"]]
    run_dirs = _safe_batch_cell_paths(
        work_root, task_id, algorithm_name, feedback_modes, seed
    )
    algorithm = get_algorithm(algorithm_name)
    # The parent hashes this exact config object before dispatch.  Do not
    # re-read a mutable git-ignored YAML file inside the worker.
    llm = _BindingCheckedLLM(
        LLMClient(payload["llm_config"]), spec, frozen_binding
    )
    _assert_task_binding(spec, frozen_binding)
    skip_keys = set(payload.get("skip_keys") or [])
    entries = []
    logs = []
    for position, (feedback_mode, run_dir) in enumerate(
        zip(feedback_modes, run_dirs), 1
    ):
        key = _run_key(task_id, algorithm_name, feedback_mode, seed)
        if key in skip_keys:
            logs.append("skip completed %s" % key)
            continue
        # Recheck immediately before inspecting or executing the cell so an
        # alias introduced after worker preflight cannot be used by a backend.
        current_run_dir = _safe_batch_cell_paths(
            work_root, task_id, algorithm_name, [feedback_mode], seed
        )[0]
        if current_run_dir != run_dir:
            raise RuntimeError("unsafe batch cell path: path changed after preflight")
        checkpoint = run_dir / "checkpoint.json"
        trajectory = run_dir / "trajectory.jsonl"
        manifest = run_dir / "run_manifest.json"
        full_resume = bool(
            checkpoint.is_file() and trajectory.is_file() and manifest.is_file()
        )
        baseline_retry = bool(
            manifest.is_file() and not checkpoint.exists()
            and not trajectory.exists()
        )
        resume_cell = bool(payload["resume"] and (full_resume or baseline_retry))
        partial_resume_state = bool(payload["resume"] and run_dir.exists()
                                    and any(run_dir.iterdir()) and not resume_cell)
        started = time.monotonic()
        cell_logs = []
        try:
            if partial_resume_state:
                raise ValueError(
                    "incomplete cell state lacks the full resume artifact set"
                )
            algorithm_kwargs = {
                "spec": spec,
                "llm": llm,
                "budget": int(payload["budget"]),
                "timeout_s": float(payload["timeout_s"]),
                "workdir": run_dir,
                "seed": seed,
                "resume": resume_cell,
                "feedback_mode": feedback_mode,
                "log_fn": cell_logs.append,
            }
            if algorithm_name == "greedy_rewrite":
                algorithm_kwargs.update({
                    "active_wall_horizon_s": payload.get("active_wall_horizon_s"),
                    "sentinel_interval_s": payload.get("sentinel_interval_s"),
                    "signed_decisions": payload.get("signed_decisions", False),
                    "signed_decision_policy": payload.get(
                        "signed_decision_policy", "record_only"
                    ),
                })
            if _safe_batch_cell_paths(
                work_root, task_id, algorithm_name, [feedback_mode], seed
            )[0] != run_dir:
                raise RuntimeError(
                    "unsafe batch cell path: path changed before execution"
                )
            result = algorithm(**algorithm_kwargs)
            entry = {
                "task": spec.task_id,
                "algorithm": result.algorithm,
                "feedback_mode": feedback_mode,
                "seed": seed,
                "baseline": result.baseline_score,
                "best": result.best_score,
                "accepted": result.accepted,
                "evaluated": result.evaluated,
                "workdir": str(run_dir),
                "summary": result.summary,
                "trajectory_snapshot": compact_trajectory_snapshot(
                    run_dir / "trajectory.jsonl", schema_version=2
                ),
            }
            if (
                payload.get("active_wall_horizon_s") is not None
                and (
                    result.summary.get("horizon_reached") is not True
                    or result.summary.get("baseline_crossed_horizon") is True
                )
                and result.summary.get("honored_signed_stop_action") is None
            ):
                entry["protocol_incomplete"] = (
                    "baseline_evaluation_exceeds_active_wall_horizon"
                    if result.summary.get("baseline_crossed_horizon") is True
                    else "proposal_budget_exhausted_before_active_wall_horizon"
                )
            if "protocol_incomplete" not in entry and result.summary.get("protocol_incomplete"):
                # Set by the search loop when no proposal was ever valid (see evolve.py).
                entry["protocol_incomplete"] = str(result.summary["protocol_incomplete"])
        except Exception as exc:  # noqa: BLE001 - retain failed conditions
            entry = {
                "task": spec.task_id,
                "algorithm": algorithm_name,
                "feedback_mode": feedback_mode,
                "seed": seed,
                "workdir": str(run_dir),
                "error": "%s: %s" % (type(exc).__name__, exc),
                "wall_seconds": time.monotonic() - started,
            }
            if trajectory.is_file():
                try:
                    entry["trajectory_snapshot"] = compact_trajectory_snapshot(
                        trajectory, schema_version=2
                    )
                except Exception as snapshot_exc:  # noqa: BLE001 - retain failure
                    entry["trajectory_snapshot_error"] = type(
                        snapshot_exc
                    ).__name__
        try:
            _assert_task_binding(spec, frozen_binding)
        except Exception:  # noqa: BLE001 - record post-execution TOCTOU failure
            entry = {
                "task": spec.task_id,
                "algorithm": algorithm_name,
                "feedback_mode": feedback_mode,
                "seed": seed,
                "workdir": str(run_dir),
                "error": "RuntimeError: frozen task binding changed after backend execution",
                "wall_seconds": time.monotonic() - started,
            }
        entry["trusted_evaluator_runtime"] = frozen_binding[
            "trusted_evaluator_runtime"
        ]
        entry["trusted_evaluator_runtime_sha256"] = frozen_binding[
            "trusted_evaluator_runtime_sha256"
        ]
        entry["budget"] = int(payload["budget"])
        entry["attempt_started"] = True
        entry["workdir_scope"] = "local_only_not_portable_evidence_identity"
        entry["execution_block_index"] = int(payload["block_index"])
        entry["within_block_position"] = position
        entries.append(entry)
        logs.extend("[%s] %s" % (feedback_mode, line) for line in cell_logs)
        if entry.get("error"):
            logs.append(
                "[%s] block halted before later conditions after outer error"
                % feedback_mode
            )
            for blocked_position, (blocked_mode, blocked_dir) in enumerate(
                zip(feedback_modes[position:], run_dirs[position:]),
                position + 1,
            ):
                blocked_key = _run_key(
                    task_id, algorithm_name, blocked_mode, seed
                )
                if blocked_key in skip_keys:
                    logs.append("skip completed %s" % blocked_key)
                    continue
                entries.append({
                    "task": spec.task_id,
                    "algorithm": algorithm_name,
                    "feedback_mode": blocked_mode,
                    "seed": seed,
                    "workdir": str(blocked_dir),
                    "error": (
                        "BlockedByPriorConditionError: earlier condition failed "
                        "before this scheduled condition could start"
                    ),
                    "blocked_by_run_key": key,
                    "attempt_started": False,
                    "wall_seconds": 0.0,
                    "trusted_evaluator_runtime": frozen_binding[
                        "trusted_evaluator_runtime"
                    ],
                    "trusted_evaluator_runtime_sha256": frozen_binding[
                        "trusted_evaluator_runtime_sha256"
                    ],
                    "budget": int(payload["budget"]),
                    "workdir_scope": "local_only_not_portable_evidence_identity",
                    "execution_block_index": int(payload["block_index"]),
                    "within_block_position": blocked_position,
                })
            break
    return {
        "block_index": int(payload["block_index"]),
        "task": task_id,
        "algorithm": algorithm_name,
        "seed": seed,
        "entries": entries,
        "logs": logs,
    }


def _latest_runs(runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for run in runs:
        latest[_run_key(
            run["task"], run["algorithm"], run["feedback_mode"], int(run["seed"])
        )] = run
    return [latest[key] for key in sorted(latest)]


def _verified_completed_keys(
    runs: list[dict[str, Any]],
    task_bindings: dict[str, dict[str, Any]],
    *,
    expected_budget: int,
    expected_work_root: Path,
) -> set[str]:
    """Return only report cells whose underlying run verifies at this runtime."""

    completed = set()
    for run in _latest_runs(runs):
        if run.get("error"):
            continue
        task_id = run.get("task")
        if not (
            isinstance(task_id, str) and task_id
            and isinstance(run.get("algorithm"), str)
            and isinstance(run.get("feedback_mode"), str)
            and isinstance(run.get("seed"), int)
            and not isinstance(run.get("seed"), bool)
            and isinstance(run.get("budget"), int)
            and not isinstance(run.get("budget"), bool)
            and run.get("workdir_scope")
            == "local_only_not_portable_evidence_identity"
        ):
            raise SystemExit("completed cell report identity is invalid")
        frozen = task_bindings.get(task_id)
        workdir = run.get("workdir")
        if not frozen or not isinstance(workdir, str) or not workdir:
            raise SystemExit("completed cell is unverifiable")
        run_path = Path(workdir).expanduser()
        if not run_path.is_absolute() or str(run_path.resolve()) != workdir:
            raise SystemExit("completed cell workdir is not a canonical local path")
        try:
            expected_run_path = _safe_batch_cell_paths(
                expected_work_root,
                task_id,
                run["algorithm"],
                [run["feedback_mode"]],
                run["seed"],
            )[0]
        except RuntimeError as exc:
            raise SystemExit("completed cell frozen work root is invalid") from exc
        if run_path != expected_run_path:
            raise SystemExit("completed cell workdir differs from frozen work root")
        if not (
            run.get("trusted_evaluator_runtime")
            == frozen["trusted_evaluator_runtime"]
            and run.get("trusted_evaluator_runtime_sha256")
            == frozen["trusted_evaluator_runtime_sha256"]
        ):
            raise SystemExit("completed cell trusted evaluator runtime differs")
        try:
            verified = verify_run(
                run_path,
                expected_budget=expected_budget,
                expected_trusted_runtime_sha256=frozen[
                    "trusted_evaluator_runtime_sha256"
                ],
            )
        except (OSError, ValueError) as exc:
            raise SystemExit("completed cell is unverifiable") from exc
        if verified.get("verified") is not True:
            raise SystemExit("completed cell is unverifiable")
        if verified.get("trusted_evaluator_runtime_sha256") != frozen[
            "trusted_evaluator_runtime_sha256"
        ]:
            raise SystemExit("completed cell trusted evaluator runtime differs")
        expected_identity = {
            "task_id": task_id,
            "algorithm": run["algorithm"],
            "feedback_mode": run["feedback_mode"],
            "seed": run["seed"],
            "budget": int(expected_budget),
            "trusted_evaluator_runtime": frozen["trusted_evaluator_runtime"],
            "trusted_evaluator_runtime_sha256": frozen[
                "trusted_evaluator_runtime_sha256"
            ],
        }
        for field in (
            "task_contract_sha256", "task_package_sha256",
            "runtime_source_sha256", "task_family_id", "wave_id",
            "wave_manifest_sha256",
        ):
            if field in frozen:
                expected_identity[field] = frozen[field]
        if run.get("budget") != expected_budget or any(
            verified.get(field) != value
            for field, value in expected_identity.items()
        ):
            raise SystemExit("completed cell verified identity differs from report")
        completed.add(_run_key(
            task_id,
            run["algorithm"],
            run["feedback_mode"],
            run["seed"],
        ))
    return completed


def aggregate_runs(
    runs: list[dict[str, Any]],
    *,
    scheduled_run_keys: set[str] | None = None,
) -> dict[str, Any]:
    runtime_by_task: dict[str, str] = {}
    for run in runs:
        task_id = str(run["task"])
        fingerprint = run.get("trusted_evaluator_runtime_sha256")
        if not (
            isinstance(fingerprint, str)
            and len(fingerprint) == 64
            and all(char in "0123456789abcdef" for char in fingerprint)
        ):
            raise ValueError(
                "run lacks trusted evaluator runtime identity for %s" % task_id
            )
        try:
            descriptor = validate_runtime_descriptor(
                run.get("trusted_evaluator_runtime")
            )
        except ValueError as exc:
            raise ValueError(
                "run lacks trusted evaluator runtime descriptor for %s" % task_id
            ) from exc
        if descriptor["fingerprint_sha256"] != fingerprint:
            raise ValueError(
                "run trusted evaluator runtime descriptor differs for %s" % task_id
            )
        previous = runtime_by_task.setdefault(task_id, fingerprint)
        if previous != fingerprint:
            raise ValueError(
                "mixed trusted evaluator runtimes for %s" % task_id
            )
    fields = {
        "best_score": lambda run: run["best"],
        "best_so_far_auc": lambda run: run["summary"]["best_so_far_auc"],
        "budget_units": lambda run: run["summary"]["budget_units"],
        "oracle_calls": lambda run: run["summary"]["oracle_calls"],
        "wall_seconds": lambda run: run["summary"]["wall_seconds"],
        "input_tokens": lambda run: run["summary"]["llm"].get("input_tokens"),
        "output_tokens": lambda run: run["summary"]["llm"].get("output_tokens"),
        "total_tokens": lambda run: run["summary"]["llm"].get("total_tokens"),
        "estimated_cost_usd": lambda run: run["summary"]["llm"].get(
            "estimated_cost_usd"
        ),
    }
    current = _latest_runs(runs)
    attempts_by_run: dict[str, list[dict[str, Any]]] = {}
    for run in runs:
        attempts_by_run.setdefault(_run_key(
            run["task"], run["algorithm"], run["feedback_mode"], int(run["seed"])
        ), []).append(run)
    observed_keys = set(attempts_by_run)
    planned_keys = (
        set(scheduled_run_keys) if scheduled_run_keys is not None
        else observed_keys
    )
    if not observed_keys <= planned_keys:
        raise ValueError("run lies outside the frozen schedule")
    groups: dict[str, list[dict[str, Any]]] = {}
    for run in current:
        key = "%s|%s|%s" % (run["task"], run["algorithm"], run["feedback_mode"])
        groups.setdefault(key, []).append(run)
    scheduled_by_condition: dict[str, int] = {}
    for key in planned_keys:
        condition_key = key.rsplit("|", 1)[0]
        scheduled_by_condition[condition_key] = (
            scheduled_by_condition.get(condition_key, 0) + 1
        )
        groups.setdefault(condition_key, [])

    by_condition = {}
    for key, group in sorted(groups.items()):
        successful_group = [
            run for run in group
            if not run.get("error") and not run.get("protocol_incomplete")
        ]
        group_attempts = [
            attempt
            for run in group
            for attempt in attempts_by_run[_run_key(
                run["task"], run["algorithm"], run["feedback_mode"], int(run["seed"])
            )]
        ]
        recovered = sum(
            not run.get("error") and not run.get("protocol_incomplete") and any(
                attempt.get("error") for attempt in attempts_by_run[_run_key(
                    run["task"], run["algorithm"], run["feedback_mode"], int(run["seed"])
                )]
            )
            for run in group
        )
        scheduled_count = scheduled_by_condition.get(key, len(group))
        by_condition[key] = {
            # ``n`` remains the valid-only sample size for compatibility. The
            # scheduled denominator and retry history are retained separately so
            # a recovered condition cannot erase an earlier failure.
            "n": len(successful_group),
            "scheduled_n": scheduled_count,
            "successful_runs": len(successful_group),
            "terminal_failed_runs": scheduled_count - len(successful_group),
            "completion_rate": (
                len(successful_group) / scheduled_count
                if scheduled_count else 0.0
            ),
            "attempt_count": len(group_attempts),
            "failed_attempts": sum(bool(run.get("error")) for run in group_attempts),
            "protocol_incomplete_attempts": sum(
                bool(run.get("protocol_incomplete")) for run in group_attempts
            ),
            "recovered_runs": recovered,
            **{name: mean_confidence_interval(getter(run) for run in successful_group)
               for name, getter in fields.items()},
        }
    successful = [
        run for run in current
        if not run.get("error") and not run.get("protocol_incomplete")
    ]
    failed_attempts = sum(bool(run.get("error")) for run in runs)
    recovered_run_keys = {
        key
        for key, attempts in attempts_by_run.items()
        if (
            not attempts[-1].get("error")
            and not attempts[-1].get("protocol_incomplete")
            and any(run.get("error") for run in attempts)
        )
    }
    first_attempts = [
        attempts[0] for attempts in attempts_by_run.values()
    ]
    successful_first_attempts = [
        run for run in first_attempts
        if not run.get("error") and not run.get("protocol_incomplete")
    ]
    valid_only = {
        name: mean_confidence_interval(getter(run) for run in successful)
        for name, getter in fields.items()
    } if successful else {}
    return {
        "trusted_evaluator_runtime_sha256_by_task": dict(
            sorted(runtime_by_task.items())
        ),
        "attempt_count": len(runs),
        "superseded_attempts": len(runs) - len(current),
        "failed_attempts": failed_attempts,
        "protocol_incomplete_attempts": sum(
            bool(run.get("protocol_incomplete")) for run in runs
        ),
        "attempt_failure_rate": failed_attempts / len(runs) if runs else 0.0,
        "recovered_runs": len(recovered_run_keys),
        "successful_runs": len(successful),
        "failed_runs": len(planned_keys) - len(successful),
        "intent_to_evaluate": {
            "scheduled_runs": len(planned_keys),
            "successful_runs": len(successful),
            "terminal_failed_runs": len(planned_keys) - len(successful),
            "completion_rate": (
                len(successful) / len(planned_keys) if planned_keys else 0.0
            ),
            "observed_run_rows": len(current),
            "missing_run_rows": len(planned_keys) - len(current),
            "run_cells_with_any_failed_attempt": sum(
                any(run.get("error") for run in attempts)
                for attempts in attempts_by_run.values()
            ),
            "run_cells_with_protocol_incomplete_attempt": sum(
                any(run.get("protocol_incomplete") for run in attempts)
                for attempts in attempts_by_run.values()
            ),
            "recovered_runs": len(recovered_run_keys),
        },
        "first_attempt_intent_to_evaluate": {
            "scheduled_runs": len(planned_keys),
            "observed_run_rows": len(first_attempts),
            "missing_run_rows": len(planned_keys) - len(first_attempts),
            "successful_runs": len(successful_first_attempts),
            "failed_runs": len(planned_keys) - len(successful_first_attempts),
            "completion_rate": (
                len(successful_first_attempts) / len(planned_keys)
                if planned_keys else 0.0
            ),
        },
        "quality_metrics_scope": (
            "latest successful runs only; interpret jointly with intent_to_evaluate "
            "and failed_attempts"
        ),
        "by_condition": by_condition,
        "overall": valid_only,
        "overall_valid_only": valid_only,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tasks", default=None, help="comma-separated task IDs/names")
    parser.add_argument("--all", action="store_true", help="include uncertified inventory")
    parser.add_argument("--algorithms", default="greedy_rewrite", help="comma-separated algorithms")
    parser.add_argument(
        "--feedback-modes", default="normal",
        help=(
            "normal,none,shuffled,score_only,delayed_replay,selection_blind "
            "(the last three protocol controls are greedy-only)"
        ),
    )
    parser.add_argument(
        "--condition-order-randomization-seed", type=int, default=None,
        help="preregistered seed that randomizes balanced Williams rows over blocks",
    )
    parser.add_argument("--seeds", type=_seeds, default=[0, 1, 2, 3, 4])
    parser.add_argument(
        "--condition-order-design",
        choices=("reverse_parity", "balanced_williams"),
        default="reverse_parity",
        help="within-task/identifier execution-order schedule",
    )
    parser.add_argument("--budget", type=int, default=30)
    parser.add_argument("--timeout", type=float, default=300.0)
    parser.add_argument(
        "--active-wall-horizon", type=float, default=None,
        help=(
            "per-run active wall-clock cutoff in seconds; currently supported "
            "only by greedy_rewrite"
        ),
    )
    parser.add_argument(
        "--sentinel-interval", type=float, default=None,
        help="fixed-grid boundary sentinel interval in active wall seconds",
    )
    parser.add_argument(
        "--signed-decisions", action="store_true",
        help="require continue/commit/abstain decision JSON after every proposal",
    )
    parser.add_argument(
        "--signed-decision-policy",
        choices=("record_only", "honor_stop"),
        default="record_only",
        help="record decisions during forced continuation, or stop on commit/abstain",
    )
    parser.add_argument(
        "--block-workers", type=int, default=1,
        help=(
            "maximum concurrent task/algorithm/replicate blocks; conditions "
            "inside each block remain serial in the frozen order"
        ),
    )
    parser.add_argument("--llm-config", default=None)
    parser.add_argument(
        "--run-role",
        choices=("performance", "calibration", "protocol_smoke"),
        default="performance",
        help="claim-bounded role recorded in evidence_scope",
    )
    parser.add_argument(
        "--preregistration", type=Path, default=None,
        help="immutable preregistration artifact to hash-bind into the report",
    )
    parser.add_argument(
        "--cohort-manifest", type=Path, default=None,
        help="exact ordered task cohort with runtime-contract and task-card hashes",
    )
    parser.add_argument("--workdir", type=Path, default=ROOT / "runs" / "experiments")
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--resume", action="store_true", help="resume individual runs and result file")
    return parser


def main(argv: list[str] | None = None) -> int:
    raw_argv = list(argv) if argv is not None else sys.argv[1:]
    args = build_parser().parse_args(raw_argv)
    if args.budget < 0:
        raise SystemExit("--budget must be non-negative")
    if args.active_wall_horizon is not None and args.active_wall_horizon <= 0:
        raise SystemExit("--active-wall-horizon must be positive")
    if args.sentinel_interval is not None and args.sentinel_interval <= 0:
        raise SystemExit("--sentinel-interval must be positive")
    if args.sentinel_interval is not None and args.active_wall_horizon is None:
        raise SystemExit("--sentinel-interval requires --active-wall-horizon")
    if args.signed_decisions and args.active_wall_horizon is None:
        raise SystemExit("--signed-decisions requires --active-wall-horizon")
    if not args.signed_decisions and args.signed_decision_policy != "record_only":
        raise SystemExit("--signed-decision-policy requires --signed-decisions")
    if args.block_workers < 1:
        raise SystemExit("--block-workers must be >= 1")
    algorithms = _csv(args.algorithms)
    if not algorithms or len(set(algorithms)) != len(algorithms):
        raise SystemExit("algorithms must be nonempty and unique")
    unknown = sorted(set(algorithms) - set(ALGORITHMS))
    if unknown:
        raise SystemExit("unknown algorithms: %s" % ", ".join(unknown))
    if set(algorithms) != {"greedy_rewrite"}:
        raise SystemExit(
            "batch evidence is supported only for greedy_rewrite because other "
            "backends lack durable receipt verification"
        )
    if args.active_wall_horizon is not None and set(algorithms) != {"greedy_rewrite"}:
        raise SystemExit(
            "--active-wall-horizon is currently implemented only for greedy_rewrite"
        )
    feedback_modes = _csv(args.feedback_modes)
    if not feedback_modes or len(set(feedback_modes)) != len(feedback_modes):
        raise SystemExit("feedback modes must be nonempty and unique")
    if len(set(args.seeds)) != len(args.seeds):
        raise SystemExit("replicate identifiers must be unique")
    unknown_modes = sorted(
        set(feedback_modes) - {
            "normal", "none", "shuffled", "score_only", "delayed_replay",
            "selection_blind",
        }
    )
    if unknown_modes:
        raise SystemExit("unknown feedback modes: %s" % ", ".join(unknown_modes))
    greedy_only_modes = {"score_only", "delayed_replay", "selection_blind"}
    requested_greedy_only = sorted(set(feedback_modes) & greedy_only_modes)
    if requested_greedy_only and set(algorithms) != {"greedy_rewrite"}:
        raise SystemExit(
            "%s implemented only for greedy_rewrite; run upstream backend controls "
            "as separately named conditions" % ", ".join(requested_greedy_only)
        )
    try:
        condition_schedule = _condition_schedule(
            feedback_modes,
            args.seeds,
            args.condition_order_design,
            args.condition_order_randomization_seed,
        )
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    include_uncertified = bool(args.all)
    if args.tasks:
        specs = [find_task(name, include_uncertified=include_uncertified) for name in _csv(args.tasks)]
    else:
        specs = list_tasks(None if args.all else "certified")
    if not specs:
        raise SystemExit("no tasks selected")
    if len({spec.task_id for spec in specs}) != len(specs):
        raise SystemExit("tasks must resolve to unique canonical identifiers")
    planned_run_keys = {
        _run_key(spec.task_id, algorithm, mode, seed)
        for spec in specs
        for algorithm in algorithms
        for mode in feedback_modes
        for seed in args.seeds
    }
    total = len(planned_run_keys)
    # Freeze task-specific evaluator identities before constructing any worker
    # or permitting any provider call. Executable paths remain private.
    task_bindings = _frozen_task_bindings(specs)
    cohort_manifest = _cohort_manifest_record(
        args.cohort_manifest, specs, include_uncertified=include_uncertified
    )

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output = args.output or (ROOT / "experiments" / ("protocol_%s.json" % timestamp))
    output = output.expanduser().resolve()
    work_root = args.workdir.expanduser().resolve()
    if output.exists() and not args.resume:
        raise SystemExit("refusing to overwrite an existing output; use --resume")
    output.parent.mkdir(parents=True, exist_ok=True)
    work_root.mkdir(parents=True, exist_ok=True)
    llm = load_llm_client(args.llm_config)
    provenance = source_provenance(
        ROOT, command=[sys.executable, str(Path(__file__).resolve()), *raw_argv]
    )
    endpoint_hash = hashlib.sha256(llm.config.base_url.encode("utf-8")).hexdigest()
    current_environment = {"python": sys.version, "platform": platform.platform()}
    experiment_config = {
        "tasks": [spec.task_id for spec in specs],
        "algorithms": algorithms,
        "feedback_modes": feedback_modes,
        "scheduled_run_count": total,
        "trajectory_snapshot_schema_version": 2,
        "feedback_protocols": {
            mode: feedback_scope(mode) for mode in feedback_modes
        },
        "condition_order": args.condition_order_design,
        "condition_order_randomization_seed": (
            args.condition_order_randomization_seed
        ),
        "condition_order_schedule": [
            {"replicate_identifier": seed, "feedback_modes": order}
            for seed, order in zip(args.seeds, condition_schedule)
        ],
        "frozen_task_bindings": task_bindings,
        "preregistration": _preregistration_record(
            args.preregistration,
            raw_argv=raw_argv,
            specs=specs,
            llm=llm,
            task_bindings=task_bindings,
        ),
        "cohort_manifest": cohort_manifest,
        "run_role": args.run_role,
        "seeds": args.seeds,
        "replicate_identifier_scope": (
            "controls local Python/random ordering only; the endpoint exposes no "
            "server-side generation seed, so same-number cells do not share model draws"
        ),
        "resource_matching": {
            "proposal_budget_and_max_output_tokens": "matched by configuration",
            "realized_input_output_and_total_tokens": (
                "measured per event; not assumed matched; use a preregistered common-token "
                "horizon or model token imbalance explicitly"
            ),
        },
        "budget": args.budget,
        "timeout_s": args.timeout,
        "active_wall_horizon_s": args.active_wall_horizon,
        "sentinel_interval_s": args.sentinel_interval,
        "signed_decisions": args.signed_decisions,
        "signed_decision_policy": args.signed_decision_policy,
        "boundary_sentinel_policy": (
            {
                "required": [
                    "t0", "first_valid", "submission", "commit_or_abstain",
                    "fixed_grid", "terminal",
                ],
                "implemented_by_runner": [
                    "t0", "first_valid", "submission", "fixed_grid", "terminal",
                    *(["commit_or_abstain"] if args.signed_decisions else []),
                ],
                "commit_or_abstain": (
                    args.signed_decision_policy
                    if args.signed_decisions
                    else "disabled; not synthesized"
                ),
                "late_result_policy": (
                    "retain result but prevent post-cutoff incumbent or feedback update"
                ),
            }
            if args.active_wall_horizon is not None else None
        ),
        "block_workers": args.block_workers,
        "block_parallelism": {
            "unit": "task_algorithm_replicate",
            "within_block_conditions": "serial_in_condition_order_schedule",
            "cross_block_scheduling": "fixed_submission_order_nonadaptive",
            "maximum_concurrent_blocks": args.block_workers,
        },
        "work_root": str(work_root),
        "work_root_scope": "local_only_not_portable_evidence_identity",
        "llm_condition_sha256": llm_condition_sha256(llm),
        "llm": {
            "wire": llm.config.wire,
            "endpoint_sha256": endpoint_hash,
            "model": llm.config.model,
            "max_output_tokens": llm.config.max_output_tokens,
            "temperature": llm.config.temperature,
            "reasoning_effort": llm.config.reasoning_effort,
            "input_cost_per_million": llm.config.input_cost_per_million,
            "output_cost_per_million": llm.config.output_cost_per_million,
            "server_side_seed_control": False,
        },
    }

    document: dict[str, Any]
    if args.resume and output.is_file():
        document = json.loads(output.read_text(encoding="utf-8"))
        if document.get("config") != experiment_config:
            raise SystemExit("refusing to resume: experiment config does not match the report")
        if document.get("environment") != current_environment:
            raise SystemExit("refusing to resume: Python/platform environment does not match")
        previous = document.get("source_provenance") or {}
        if (
            previous.get("git_revision") != provenance.get("git_revision")
            or previous.get("source_tree_dirty") != provenance.get("source_tree_dirty")
            or previous.get("source_changes") != provenance.get("source_changes")
        ):
            raise SystemExit("refusing to resume: source provenance does not match the report")
    elif args.resume:
        raise SystemExit("--resume requires an existing --output report")
    else:
        document = {
            "schema_version": 1,
            "trust_status": "TRUSTED_SECURE_EVAL",
            "evidence_scope": (
                "PROTOCOL_SMOKE_ONLY_NOT_MODEL_PERFORMANCE"
                if args.run_role == "protocol_smoke"
                else "MODEL_CALIBRATION_NOT_POPULATION_PERFORMANCE"
                if args.run_role == "calibration"
                else "MODEL_PERFORMANCE"
            ),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "source_provenance": provenance,
            "environment": current_environment,
            "config": experiment_config,
            "runs": [],
        }
        if args.run_role == "protocol_smoke" or args.budget == 0:
            document["warning"] = (
                "Protocol/calibration run: validates configured artifacts and accounting; "
                "do not treat it as population model performance."
            )
    # A report row is an index, never completion evidence on its own. Rebuild
    # every terminal run before allowing --resume to skip a cell.
    done = _verified_completed_keys(
        document.get("runs", []), task_bindings,
        expected_budget=args.budget,
        expected_work_root=work_root,
    )
    blocks = _execution_blocks(
        [spec.task_id for spec in specs], algorithms, args.seeds,
        condition_schedule,
    )
    payloads = [
        {
            **block,
            "llm_config": llm.config,
            "work_root": str(work_root),
            "budget": args.budget,
            "timeout_s": args.timeout,
            "active_wall_horizon_s": args.active_wall_horizon,
            "sentinel_interval_s": args.sentinel_interval,
            "signed_decisions": args.signed_decisions,
            "signed_decision_policy": args.signed_decision_policy,
            "resume": args.resume,
            "skip_keys": sorted(done),
            "frozen_task_binding": task_bindings[block["task"]],
        }
        for block in blocks
        if any(
            _run_key(
                block["task"], block["algorithm"], mode, block["seed"]
            ) not in done
            for mode in block["feedback_modes"]
        )
    ]
    _assert_task_bindings(specs, task_bindings)
    # Persist the cohort plan and source provenance before any worker can make
    # an LLM call. A process interruption can then be resumed without
    # reconstructing an unrecorded design.
    document["aggregate"] = aggregate_runs(
        document.get("runs") or [], scheduled_run_keys=planned_run_keys
    )
    atomic_write_text(
        output, json.dumps(document, indent=2, allow_nan=False) + "\n"
    )

    def retain_block(result: dict[str, Any]) -> None:
        for line in result.get("logs") or []:
            print("  " + line, flush=True)
        entries = result.get("entries") or []
        _verified_completed_keys(
            entries, task_bindings, expected_budget=args.budget,
            expected_work_root=work_root,
        )
        document.setdefault("runs", []).extend(entries)
        document["aggregate"] = aggregate_runs(
            document["runs"], scheduled_run_keys=planned_run_keys
        )
        atomic_write_text(
            output, json.dumps(document, indent=2, allow_nan=False) + "\n"
        )
        print(
            "[block %d/%d] complete %s|%s|%d" % (
                result["block_index"], len(blocks), result["task"],
                result["algorithm"], result["seed"],
            ),
            flush=True,
        )

    if args.block_workers == 1:
        for payload in payloads:
            retain_block(_execute_block(payload))
    else:
        context = multiprocessing.get_context("spawn")
        with concurrent.futures.ProcessPoolExecutor(
            max_workers=args.block_workers, mp_context=context,
        ) as executor:
            future_payload = {
                executor.submit(_execute_block, payload): payload
                for payload in payloads
            }
            for future in concurrent.futures.as_completed(future_payload):
                payload = future_payload[future]
                try:
                    result = future.result()
                except Exception as exc:  # noqa: BLE001 - retain crashed blocks
                    document.setdefault("block_failures", []).append({
                        "block_index": payload["block_index"],
                        "task": payload["task"],
                        "algorithm": payload["algorithm"],
                        "seed": payload["seed"],
                        "feedback_modes": payload["feedback_modes"],
                        "error": "BlockWorkerError: %s" % type(exc).__name__,
                        "completed_at": datetime.now(timezone.utc).isoformat(),
                    })
                    document["aggregate"] = aggregate_runs(
                        document.get("runs") or [],
                        scheduled_run_keys=planned_run_keys,
                    )
                    atomic_write_text(
                        output,
                        json.dumps(document, indent=2, allow_nan=False) + "\n",
                    )
                    print(
                        "[block %d/%d] worker failed %s|%s|%d" % (
                            payload["block_index"], len(blocks),
                            payload["task"], payload["algorithm"],
                            payload["seed"],
                        ),
                        flush=True,
                    )
                    continue
                retain_block(result)

    document["completed_at"] = datetime.now(timezone.utc).isoformat()
    document["aggregate"] = aggregate_runs(
        document["runs"], scheduled_run_keys=planned_run_keys
    )
    integrity_errors = _final_integrity_errors(
        specs, task_bindings, provenance
    )
    document["final_integrity"] = {
        "passed": not integrity_errors,
        "errors": integrity_errors,
    }
    execution_passed = (
        document["aggregate"]["failed_runs"] == 0
        and document["aggregate"]["successful_runs"] == total
        and not integrity_errors
    )
    finalize_report_trust(document, execution_passed)
    atomic_write_text(output, json.dumps(document, indent=2, allow_nan=False) + "\n")
    print("Results: %s" % output)
    return 0 if execution_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())

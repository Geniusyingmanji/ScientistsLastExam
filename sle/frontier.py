"""Frozen task-family waves and append-only lifetime frontier credit.

Release scores remain properties of one immutable task package.  This module adds a
separate, content-bound ledger for scientific gains that survive across waves of the
same task family.  Evaluators, not candidate programs, are responsible for producing
the canonical record identifiers passed to :class:`FrontierLedger`.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import yaml

from .evaluation_ledger import EvaluationLedger, RunLease

try:
    import fcntl
except ImportError:  # pragma: no cover - SLE runners target POSIX
    fcntl = None


WAVE_SCHEMA_VERSION = 1
EVALUATION_RECEIPT_SCHEMA_VERSION = 1
FRONTIER_EVENT_SCHEMA_VERSION = 2
_HASH = re.compile(r"^[0-9a-f]{64}$")
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]*$")


def _canonical_json(value: Any) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
        + "\n"
    ).encode("utf-8")


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value)).hexdigest()


def _durable_atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(".%s.tmp" % path.name)
    with temporary.open("wb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(str(temporary), str(path))
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    directory_fd = os.open(str(path.parent), flags)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


def _identifier(value: Any, label: str, *, maximum: int = 256) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > maximum
        or not _IDENTIFIER.fullmatch(value)
    ):
        raise ValueError("%s is not a bounded canonical identifier" % label)
    return value


def _hash(value: Any, label: str) -> str:
    if not isinstance(value, str) or not _HASH.fullmatch(value):
        raise ValueError("%s must be a lowercase SHA-256" % label)
    return value


def _canonical_id(value: Any) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > 256
        or any(ord(char) < 33 or ord(char) > 126 for char in value)
    ):
        raise ValueError("canonical_id must be bounded printable ASCII without spaces")
    return value


def _number(value: Any, label: str, *, nonnegative: bool = False) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
        or (nonnegative and float(value) < 0.0)
    ):
        qualifier = " finite non-negative" if nonnegative else " finite"
        raise ValueError("%s must be a%s number" % (label, qualifier))
    return float(value)


def _semantic_contract(
    value: Any, *, contract_root: Path | None = None
) -> dict[str, str]:
    if not isinstance(value, Mapping):
        raise ValueError("cell semantic_contract must be a mapping")
    expected = {
        "canonicalizer_id",
        "canonicalizer_path",
        "canonicalizer_sha256",
        "evidence_predicate_id",
        "evidence_predicate_path",
        "evidence_predicate_sha256",
        "evaluation_panel_path",
        "evaluation_panel_sha256",
        "oracle_path",
        "oracle_sha256",
    }
    if set(value) != expected:
        raise ValueError("cell semantic_contract fields differ from schema")
    normalized = {
        "canonicalizer_id": _identifier(
            value.get("canonicalizer_id"), "canonicalizer_id"
        ),
        "canonicalizer_path": _identifier(
            value.get("canonicalizer_path"), "canonicalizer_path"
        ),
        "canonicalizer_sha256": _hash(
            value.get("canonicalizer_sha256"), "canonicalizer_sha256"
        ),
        "evidence_predicate_id": _identifier(
            value.get("evidence_predicate_id"), "evidence_predicate_id"
        ),
        "evidence_predicate_path": _identifier(
            value.get("evidence_predicate_path"), "evidence_predicate_path"
        ),
        "evidence_predicate_sha256": _hash(
            value.get("evidence_predicate_sha256"), "evidence_predicate_sha256"
        ),
        "evaluation_panel_path": _identifier(
            value.get("evaluation_panel_path"), "evaluation_panel_path"
        ),
        "evaluation_panel_sha256": _hash(
            value.get("evaluation_panel_sha256"), "evaluation_panel_sha256"
        ),
        "oracle_path": _identifier(value.get("oracle_path"), "oracle_path"),
        "oracle_sha256": _hash(value.get("oracle_sha256"), "oracle_sha256"),
    }
    if contract_root is not None:
        root = contract_root.resolve()
        for prefix in (
            "canonicalizer",
            "evidence_predicate",
            "evaluation_panel",
            "oracle",
        ):
            relative = Path(normalized[prefix + "_path"])
            if relative.is_absolute() or ".." in relative.parts:
                raise ValueError("semantic contract path must stay inside the task package")
            path = (root / relative).resolve()
            if root != path and root not in path.parents:
                raise ValueError("semantic contract path escapes the task package")
            try:
                actual = hashlib.sha256(path.read_bytes()).hexdigest()
            except OSError as exc:
                raise ValueError("semantic contract artifact is missing: %s" % relative) from exc
            if actual != normalized[prefix + "_sha256"]:
                raise ValueError("semantic contract artifact hash differs: %s" % relative)
    return normalized


def _validate_cell(
    value: Any, *, contract_root: Path | None = None
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError("wave cell must be a mapping")
    cell = dict(value)
    cell_id = _identifier(cell.get("id"), "cell id")
    kind = cell.get("kind")
    if kind not in {"optimization", "discovery"}:
        raise ValueError("cell %s has an invalid kind" % cell_id)
    provided_definition = cell.get("definition_sha256")
    weight = _number(cell.get("weight"), "cell weight", nonnegative=True)
    if weight <= 0.0:
        raise ValueError("cell weight must be positive")
    normalized: dict[str, Any] = {
        "id": cell_id,
        "kind": kind,
        "weight": weight,
        "semantic_contract": _semantic_contract(
            cell.get("semantic_contract"), contract_root=contract_root
        ),
    }
    if kind == "optimization":
        objective = cell.get("objective")
        if objective not in {"maximize", "minimize"}:
            raise ValueError("optimization cell objective must be maximize or minimize")
        scale = _number(cell.get("credit_scale"), "credit_scale", nonnegative=True)
        if scale <= 0.0:
            raise ValueError("credit_scale must be positive")
        normalized.update({
            "objective": objective,
            "reference_value": _number(cell.get("reference_value"), "reference_value"),
            "credit_scale": scale,
            "minimum_delta": _number(
                cell.get("minimum_delta"), "minimum_delta", nonnegative=True
            ),
        })
    else:
        per_claim = _number(
            cell.get("credit_per_claim"), "credit_per_claim", nonnegative=True
        )
        if per_claim <= 0.0:
            raise ValueError("credit_per_claim must be positive")
        normalized["credit_per_claim"] = per_claim
        normalized["novelty_namespace"] = _identifier(
            cell.get("novelty_namespace"), "novelty_namespace"
        )
    definition = _sha256(normalized)
    if provided_definition is not None and _hash(
        provided_definition, "cell definition_sha256"
    ) != definition:
        raise ValueError("cell definition_sha256 does not match its semantics")
    normalized["definition_sha256"] = definition
    return normalized


@dataclass(frozen=True)
class FrozenWave:
    task_family_id: str
    wave_id: str
    manifest_sha256: str
    predecessor_wave_sha256: str | None
    cells: dict[str, dict[str, Any]]

    def binding(self) -> dict[str, str]:
        return {
            "task_family_id": self.task_family_id,
            "wave_id": self.wave_id,
            "wave_manifest_sha256": self.manifest_sha256,
        }

    def ledger_document(self) -> dict[str, Any]:
        return {
            **self.binding(),
            "predecessor_wave_sha256": self.predecessor_wave_sha256,
            "cells": [self.cells[key] for key in sorted(self.cells)],
        }


def load_frozen_wave(spec: Any) -> FrozenWave | None:
    """Load an opted-in task's semantic wave manifest.

    Legacy tasks remain valid without family metadata.  Once either family metadata
    or ``wave.yaml`` exists, all fields are mandatory and fail closed.
    """

    metadata = getattr(spec, "metadata", {}) or {}
    eval_dir = getattr(spec, "eval_dir", None)
    path = Path(eval_dir) / "wave.yaml" if eval_dir is not None else None
    opted_in = "task_family_id" in metadata or "wave_id" in metadata
    if not opted_in and (path is None or not path.is_file()):
        return None
    if path is None or not path.is_file():
        raise ValueError("task family metadata requires frontier_eval/wave.yaml")
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError("wave manifest is not valid YAML") from exc
    if not isinstance(raw, Mapping) or raw.get("schema_version") != WAVE_SCHEMA_VERSION:
        raise ValueError("wave manifest schema_version must be 1")
    family = _identifier(raw.get("task_family_id"), "task_family_id")
    wave_id = _identifier(raw.get("wave_id"), "wave_id")
    if metadata.get("task_family_id") != family:
        raise ValueError("metadata task_family_id differs from wave manifest")
    if metadata.get("wave_id") != wave_id:
        raise ValueError("metadata wave_id differs from wave manifest")
    predecessor = raw.get("predecessor_wave_sha256")
    if predecessor is not None:
        predecessor = _hash(predecessor, "predecessor_wave_sha256")
    raw_cells = raw.get("cells")
    if not isinstance(raw_cells, list) or not raw_cells:
        raise ValueError("wave manifest must contain at least one cell")
    cells: dict[str, dict[str, Any]] = {}
    role = metadata.get("scientific_role")
    for raw_cell in raw_cells:
        cell = _validate_cell(raw_cell, contract_root=Path(spec.task_dir))
        if cell["id"] in cells:
            raise ValueError("wave manifest contains duplicate cell ids")
        if role in {"optimization", "discovery"} and cell["kind"] != role:
            raise ValueError("wave cell kind differs from task scientific_role")
        cells[cell["id"]] = cell
    semantic = {
        "schema_version": WAVE_SCHEMA_VERSION,
        "task_family_id": family,
        "wave_id": wave_id,
        "predecessor_wave_sha256": predecessor,
        "cells": [cells[key] for key in sorted(cells)],
    }
    return FrozenWave(
        task_family_id=family,
        wave_id=wave_id,
        manifest_sha256=_sha256(semantic),
        predecessor_wave_sha256=predecessor,
        cells=cells,
    )


def frontier_binding(spec: Any) -> dict[str, str]:
    wave = load_frozen_wave(spec)
    return wave.binding() if wave is not None else {}


def validate_family_waves(specs: list[Any]) -> list[str]:
    """Validate the complete repository-visible chain for every opted-in family."""

    families: dict[str, list[tuple[str, FrozenWave]]] = {}
    issues: list[str] = []
    for spec in specs:
        try:
            wave = load_frozen_wave(spec)
        except ValueError:
            continue  # The per-task audit reports the more specific parse failure.
        if wave is not None:
            families.setdefault(wave.task_family_id, []).append((spec.task_id, wave))
    for family, rows in sorted(families.items()):
        by_id: dict[str, tuple[str, FrozenWave]] = {}
        by_hash: dict[str, tuple[str, FrozenWave]] = {}
        cell_definitions: dict[str, str] = {}
        novelty_cells: dict[str, str] = {}
        for task_id, wave in rows:
            if wave.wave_id in by_id:
                issues.append("family %s repeats wave_id %s" % (family, wave.wave_id))
            else:
                by_id[wave.wave_id] = (task_id, wave)
            if wave.manifest_sha256 in by_hash:
                issues.append(
                    "family %s repeats wave manifest %s" %
                    (family, wave.manifest_sha256)
                )
            else:
                by_hash[wave.manifest_sha256] = (task_id, wave)
            for cell_id, cell in wave.cells.items():
                prior = cell_definitions.get(cell_id)
                if prior is not None and prior != cell["definition_sha256"]:
                    issues.append(
                        "family %s changes cell definition %s" % (family, cell_id)
                    )
                cell_definitions[cell_id] = cell["definition_sha256"]
                if cell["kind"] == "discovery":
                    namespace = cell["novelty_namespace"]
                    prior_cell = novelty_cells.get(namespace)
                    if prior_cell is not None and prior_cell != cell_id:
                        issues.append(
                            "family %s reuses novelty namespace %s across cells" %
                            (family, namespace)
                        )
                    novelty_cells[namespace] = cell_id
        roots = [wave for _, wave in rows if wave.predecessor_wave_sha256 is None]
        if len(roots) != 1:
            issues.append("family %s must contain exactly one genesis wave" % family)
        child_counts: dict[str, int] = {}
        for _, wave in rows:
            predecessor = wave.predecessor_wave_sha256
            if predecessor is None:
                continue
            if predecessor not in by_hash:
                issues.append(
                    "family %s wave %s has a missing predecessor" %
                    (family, wave.wave_id)
                )
                continue
            child_counts[predecessor] = child_counts.get(predecessor, 0) + 1
        if any(count > 1 for count in child_counts.values()):
            issues.append("family %s wave chain contains a fork" % family)
        if len(roots) == 1:
            visited = set()
            current = roots[0]
            while current.manifest_sha256 not in visited:
                visited.add(current.manifest_sha256)
                children = [
                    wave for _, wave in rows
                    if wave.predecessor_wave_sha256 == current.manifest_sha256
                ]
                if len(children) != 1:
                    break
                current = children[0]
            if len(visited) != len(rows):
                issues.append("family %s wave chain is disconnected or cyclic" % family)
    return sorted(set(issues))


def _validated_wave(wave: FrozenWave) -> FrozenWave:
    if not isinstance(wave, FrozenWave):
        raise ValueError("frontier wave must be a FrozenWave")
    cells = {}
    novelty_cells = {}
    for raw_cell in wave.cells.values():
        cell = _validate_cell(raw_cell)
        if cell["id"] in cells:
            raise ValueError("frontier wave repeats a cell")
        if cell["kind"] == "discovery":
            namespace = cell["novelty_namespace"]
            if namespace in novelty_cells and novelty_cells[namespace] != cell["id"]:
                raise ValueError("frontier wave repeats a novelty namespace")
            novelty_cells[namespace] = cell["id"]
        cells[cell["id"]] = cell
    if not cells:
        raise ValueError("frontier wave must contain at least one cell")
    predecessor = wave.predecessor_wave_sha256
    if predecessor is not None:
        predecessor = _hash(predecessor, "predecessor_wave_sha256")
    normalized = FrozenWave(
        task_family_id=_identifier(wave.task_family_id, "task_family_id"),
        wave_id=_identifier(wave.wave_id, "wave_id"),
        manifest_sha256=_hash(wave.manifest_sha256, "wave_manifest_sha256"),
        predecessor_wave_sha256=predecessor,
        cells=cells,
    )
    semantic = {
        "schema_version": WAVE_SCHEMA_VERSION,
        "task_family_id": normalized.task_family_id,
        "wave_id": normalized.wave_id,
        "predecessor_wave_sha256": normalized.predecessor_wave_sha256,
        "cells": [normalized.cells[key] for key in sorted(normalized.cells)],
    }
    if normalized.manifest_sha256 != _sha256(semantic):
        raise ValueError("wave_manifest_sha256 does not match its semantics")
    return normalized


class FrontierLedger:
    """Append-only, hash-chained frontier decisions for one local evidence root."""

    def __init__(self, workdir: Path) -> None:
        self.root = Path(workdir).resolve() / "frontier_ledger"
        self.event_root = self.root / "events"
        self.lock_path = self.root / "ledger.lock"

    @staticmethod
    def _empty_state() -> dict[str, Any]:
        return {
            "waves": {},
            "wave_evidence_bindings": {},
            "cell_definitions": {},
            "novelty_cells": {},
            "optimization_frontiers": {},
            "optimization_artifacts": {},
            "artifact_records": {},
            "evaluation_requests": {},
            "discoveries": set(),
            "lifetime_credit": 0.0,
            "accepted_record_count": 0,
        }

    @staticmethod
    def _register_wave(
        state: dict[str, Any], wave: FrozenWave, evidence_binding: Mapping[str, str]
    ) -> None:
        expected_fields = {
            "task_contract_sha256",
            "task_package_sha256",
            "runtime_source_sha256",
            "trusted_evaluator_runtime_sha256",
        }
        if set(evidence_binding) != expected_fields:
            raise ValueError("wave evidence binding fields differ from schema")
        normalized_binding = {
            key: _hash(evidence_binding.get(key), key) for key in sorted(expected_fields)
        }
        wave_key = "%s|%s" % (wave.task_family_id, wave.wave_id)
        prior_binding = state["wave_evidence_bindings"].get(wave_key)
        if prior_binding is not None and prior_binding != normalized_binding:
            raise ValueError("immutable wave evidence binding changed")
        state["wave_evidence_bindings"][wave_key] = normalized_binding
        family_waves = state["waves"].setdefault(wave.task_family_id, [])
        existing = next((row for row in family_waves if row["wave_id"] == wave.wave_id), None)
        if existing is not None:
            if existing["manifest_sha256"] != wave.manifest_sha256:
                raise ValueError("recorded wave_id has a different manifest")
        else:
            expected = family_waves[-1]["manifest_sha256"] if family_waves else None
            if wave.predecessor_wave_sha256 != expected:
                raise ValueError("wave predecessor does not extend the recorded manifest chain")
            family_waves.append({
                "wave_id": wave.wave_id,
                "manifest_sha256": wave.manifest_sha256,
            })
        for cell_id, cell in wave.cells.items():
            key = "%s|%s" % (wave.task_family_id, cell_id)
            prior = state["cell_definitions"].get(key)
            if prior is not None and prior != cell["definition_sha256"]:
                raise ValueError("cell definition changed across immutable waves")
            state["cell_definitions"][key] = cell["definition_sha256"]
            if cell["kind"] == "discovery":
                namespace_key = "%s|%s" % (
                    wave.task_family_id, cell["novelty_namespace"]
                )
                prior_cell = state["novelty_cells"].get(namespace_key)
                if prior_cell is not None and prior_cell != cell_id:
                    raise ValueError("novelty namespace was reused across cells")
                state["novelty_cells"][namespace_key] = cell_id

    @staticmethod
    def _canonical_records(records: Any) -> list[dict[str, Any]]:
        if not isinstance(records, list):
            raise ValueError("frontier records must be a list")
        if len(records) > 10000:
            raise ValueError("frontier submission contains too many records")
        normalized = []
        for raw in records:
            if not isinstance(raw, Mapping):
                raise ValueError("frontier record must be a mapping")
            value = dict(raw)
            _canonical_json(value)
            normalized.append(value)
        normalized.sort(key=_canonical_json)
        if any(
            normalized[index] == normalized[index - 1]
            for index in range(1, len(normalized))
        ):
            raise ValueError("frontier receipt repeats an identical record")
        return normalized

    @staticmethod
    def _bind_evidence(
        state: dict[str, Any],
        wave: FrozenWave,
        *,
        request_id: str,
        metrics_sha256: str,
        artifact_sha256: str,
        records_sha256: str,
        event_index: int,
    ) -> None:
        if request_id in state["evaluation_requests"]:
            raise ValueError("frontier ledger repeats an evaluation request")
        state["evaluation_requests"][request_id] = {
            "metrics_sha256": metrics_sha256,
            "event_index": event_index,
        }
        artifact_key = "%s|%s|%s" % (
            wave.task_family_id, wave.manifest_sha256, artifact_sha256
        )
        prior = state["artifact_records"].get(artifact_key)
        if prior is not None and prior != records_sha256:
            raise ValueError("canonical artifact changed its frontier record set")
        state["artifact_records"][artifact_key] = records_sha256

    @staticmethod
    def _apply_records(
        state: dict[str, Any], wave: FrozenWave, records: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], float]:
        decisions = []
        credit_delta = 0.0
        optimization_cells = set()
        for raw in records:
            if not isinstance(raw, Mapping):
                raise ValueError("frontier record must be a mapping")
            cell_id = _identifier(raw.get("cell_id"), "record cell_id")
            canonical_id = _canonical_id(raw.get("canonical_id"))
            try:
                cell = wave.cells[cell_id]
            except KeyError as exc:
                raise ValueError("record refers to a cell outside the frozen wave") from exc
            key = "%s|%s" % (wave.task_family_id, cell_id)
            accepted = False
            duplicate = False
            credit = 0.0
            if cell["kind"] == "optimization":
                if cell_id in optimization_cells:
                    raise ValueError(
                        "frontier receipt contains multiple values for one optimization cell"
                    )
                optimization_cells.add(cell_id)
                value = _number(raw.get("value"), "optimization value")
                artifact_key = "%s|%s" % (key, canonical_id)
                prior_value = state["optimization_artifacts"].get(artifact_key)
                if prior_value is not None:
                    if value != prior_value:
                        raise ValueError("canonical optimization artifact changed value")
                    duplicate = True
                else:
                    state["optimization_artifacts"][artifact_key] = value
                    incumbent = state["optimization_frontiers"].get(
                        key, cell["reference_value"]
                    )
                    improvement = (
                        value - incumbent
                        if cell["objective"] == "maximize"
                        else incumbent - value
                    )
                    if improvement >= cell["minimum_delta"] and improvement > 0.0:
                        credit = cell["weight"] * improvement / cell["credit_scale"]
                        state["optimization_frontiers"][key] = value
                        accepted = True
                decision = {
                    "cell_id": cell_id,
                    "canonical_id": canonical_id,
                    "kind": "optimization",
                    "value": value,
                    "accepted": accepted,
                    "duplicate": duplicate,
                    "credit": credit,
                }
            else:
                claim_key = (
                    wave.task_family_id, cell["novelty_namespace"], canonical_id
                )
                if claim_key in state["discoveries"]:
                    duplicate = True
                else:
                    state["discoveries"].add(claim_key)
                    credit = cell["weight"] * cell["credit_per_claim"]
                    accepted = True
                decision = {
                    "cell_id": cell_id,
                    "canonical_id": canonical_id,
                    "kind": "discovery",
                    "accepted": accepted,
                    "duplicate": duplicate,
                    "credit": credit,
                }
            decisions.append(decision)
            credit_delta += credit
            if accepted:
                state["accepted_record_count"] += 1
        state["lifetime_credit"] += credit_delta
        return decisions, credit_delta

    def _events(self) -> list[dict[str, Any]]:
        if not self.event_root.is_dir():
            return []
        events = []
        previous = None
        paths = sorted(self.event_root.glob("*.json"))
        for index, path in enumerate(paths):
            if path.name != "%08d.json" % index:
                raise ValueError("frontier ledger event filenames are not contiguous")
            try:
                event = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                raise ValueError("frontier ledger event is corrupt: %s" % path.name) from exc
            if (
                not isinstance(event, dict)
                or event.get("schema_version") != FRONTIER_EVENT_SCHEMA_VERSION
            ):
                raise ValueError("frontier ledger event schema is invalid")
            actual_hash = event.get("event_sha256")
            payload = {key: value for key, value in event.items() if key != "event_sha256"}
            if actual_hash != _sha256(payload):
                raise ValueError("frontier ledger event hash differs")
            if event.get("previous_event_sha256") != previous:
                raise ValueError("frontier ledger hash chain differs")
            if event.get("event_index") != len(events):
                raise ValueError("frontier ledger event indices are not contiguous")
            previous = actual_hash
            events.append(event)
        return events

    def _replay(self, events: list[dict[str, Any]]) -> dict[str, Any]:
        state = self._empty_state()
        for event in events:
            wave_doc = event.get("wave")
            if not isinstance(wave_doc, Mapping):
                raise ValueError("frontier ledger event lacks a wave binding")
            cells = {}
            raw_cells = wave_doc.get("cells")
            if not isinstance(raw_cells, list) or not raw_cells:
                raise ValueError("frontier ledger event has no cells")
            for raw_cell in raw_cells:
                cell = _validate_cell(raw_cell)
                if cell["id"] in cells:
                    raise ValueError("frontier ledger wave repeats a cell")
                cells[cell["id"]] = cell
            predecessor = wave_doc.get("predecessor_wave_sha256")
            if predecessor is not None:
                predecessor = _hash(predecessor, "predecessor_wave_sha256")
            wave = FrozenWave(
                task_family_id=_identifier(
                    wave_doc.get("task_family_id"), "task_family_id"
                ),
                wave_id=_identifier(wave_doc.get("wave_id"), "wave_id"),
                manifest_sha256=_hash(
                    wave_doc.get("wave_manifest_sha256"), "wave_manifest_sha256"
                ),
                predecessor_wave_sha256=predecessor,
                cells=cells,
            )
            wave = _validated_wave(wave)
            request_id = _hash(
                event.get("evaluation_request_id"), "evaluation_request_id"
            )
            metrics_hash = _hash(
                event.get("evaluation_metrics_sha256"),
                "evaluation_metrics_sha256",
            )
            _hash(event.get("task_contract_sha256"), "task_contract_sha256")
            _hash(event.get("task_package_sha256"), "task_package_sha256")
            _hash(event.get("runtime_source_sha256"), "runtime_source_sha256")
            trusted_runtime_hash = _hash(
                event.get("trusted_evaluator_runtime_sha256"),
                "trusted_evaluator_runtime_sha256",
            )
            _identifier(event.get("task_id"), "task_id")
            artifact_hash = _hash(event.get("artifact_sha256"), "artifact_sha256")
            embedded_request = event.get("evaluation_request")
            embedded_receipt = event.get("evaluation_receipt")
            if not isinstance(embedded_request, Mapping) or not isinstance(
                embedded_receipt, Mapping
            ):
                raise ValueError("frontier ledger lacks embedded evaluation evidence")
            if _sha256(dict(embedded_request)) != request_id:
                raise ValueError("embedded evaluation request hash differs")
            embedded_metrics = embedded_receipt.get("metrics")
            if not isinstance(embedded_metrics, Mapping):
                raise ValueError("embedded evaluation receipt lacks metrics")
            if not (
                embedded_receipt.get("schema_version")
                == EVALUATION_RECEIPT_SCHEMA_VERSION
                and embedded_receipt.get("request_id") == request_id
                and embedded_receipt.get("request_sha256") == request_id
                and embedded_receipt.get("metrics_sha256") == metrics_hash
                and _sha256(dict(embedded_metrics)) == metrics_hash
                and isinstance(embedded_receipt.get("completed_at_utc"), str)
                and bool(embedded_receipt.get("completed_at_utc"))
            ):
                raise ValueError("embedded evaluation receipt binding differs")
            _number(
                embedded_receipt.get("evaluation_wall_seconds"),
                "evaluation_wall_seconds",
                nonnegative=True,
            )
            for key, expected in wave.binding().items():
                if embedded_request.get(key) != expected:
                    raise ValueError("embedded evaluation wave binding differs")
            if not (
                embedded_request.get("task_id") == event.get("task_id")
                and embedded_request.get("task_contract_sha256")
                == event.get("task_contract_sha256")
                and embedded_request.get("task_package_sha256")
                == event.get("task_package_sha256")
                and embedded_request.get("runtime_source_sha256")
                == event.get("runtime_source_sha256")
                and embedded_request.get("trusted_evaluator_runtime_sha256")
                == trusted_runtime_hash
                and embedded_request.get("candidate_sha256") == artifact_hash
            ):
                raise ValueError("embedded evaluation source binding differs")
            if embedded_metrics.get("infrastructure_failure"):
                raise ValueError("embedded evaluation is an infrastructure failure")
            if _number(embedded_metrics.get("valid"), "evaluator valid") != 1.0:
                raise ValueError("embedded evaluation result is invalid")
            records = self._canonical_records(embedded_metrics.get("frontier_records"))
            if records != event.get("records"):
                raise ValueError("frontier ledger records differ from embedded receipt")
            records_hash = _sha256(records)
            if event.get("records_sha256") != records_hash:
                raise ValueError("frontier ledger record-set hash differs")
            self._register_wave(
                state,
                wave,
                {
                    "task_contract_sha256": event["task_contract_sha256"],
                    "task_package_sha256": event["task_package_sha256"],
                    "runtime_source_sha256": event["runtime_source_sha256"],
                    "trusted_evaluator_runtime_sha256": trusted_runtime_hash,
                },
            )
            self._bind_evidence(
                state,
                wave,
                request_id=request_id,
                metrics_sha256=metrics_hash,
                artifact_sha256=artifact_hash,
                records_sha256=records_hash,
                event_index=int(event["event_index"]),
            )
            decisions, credit = self._apply_records(
                state, wave, records
            )
            if decisions != event.get("decisions") or credit != event.get("credit_delta"):
                raise ValueError("frontier ledger decision replay differs")
        return state

    def record(
        self,
        wave: FrozenWave,
        *,
        evaluation_ledger: EvaluationLedger,
        request_id: str,
    ) -> dict[str, Any]:
        """Reject unverified direct credit; use :func:`promote_frontier_receipt`."""

        del wave, evaluation_ledger, request_id
        raise ValueError(
            "frontier credit requires promote_frontier_receipt from a verified run"
        )

    def _record_verified(
        self,
        wave: FrozenWave,
        *,
        evaluation_ledger: EvaluationLedger,
        request_id: str,
        verified_run: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Append one receipt already proven by ``verify_run``."""

        if fcntl is None:
            raise RuntimeError("frontier ledger requires POSIX advisory locks")
        wave = _validated_wave(wave)
        if not isinstance(evaluation_ledger, EvaluationLedger):
            raise ValueError("frontier credit requires an EvaluationLedger")
        request_hash = _hash(request_id, "evaluation request_id")
        if not isinstance(verified_run, Mapping) or not verified_run.get("verified"):
            raise ValueError("frontier credit requires a verified run result")
        if request_hash not in verified_run.get("verified_request_ids", []):
            raise ValueError("frontier receipt is not a verified trajectory event")
        bound = evaluation_ledger.require_bound_record(request_hash)
        request = bound.get("request")
        receipt = bound.get("receipt")
        if not isinstance(request, Mapping) or not isinstance(receipt, Mapping):
            raise ValueError("evaluation ledger returned an invalid bound record")
        for key, expected in wave.binding().items():
            if request.get(key) != expected:
                raise ValueError("evaluation request %s differs from frozen wave" % key)
        task_id = _identifier(request.get("task_id"), "evaluation task_id")
        contract_hash = _hash(
            request.get("task_contract_sha256"), "task_contract_sha256"
        )
        package_hash = _hash(
            request.get("task_package_sha256"), "task_package_sha256"
        )
        runtime_hash = _hash(
            request.get("runtime_source_sha256"), "runtime_source_sha256"
        )
        trusted_runtime_hash = _hash(
            request.get("trusted_evaluator_runtime_sha256"),
            "trusted_evaluator_runtime_sha256",
        )
        if trusted_runtime_hash != verified_run.get(
            "trusted_evaluator_runtime_sha256"
        ):
            raise ValueError("evaluation request trusted runtime differs from verified run")
        artifact_hash = _hash(request.get("candidate_sha256"), "candidate_sha256")
        metrics = receipt.get("metrics")
        if not isinstance(metrics, Mapping) or metrics.get("infrastructure_failure"):
            raise ValueError("frontier credit requires a valid evaluator result")
        valid = _number(metrics.get("valid"), "evaluator valid")
        if valid != 1.0:
            raise ValueError("frontier credit requires a valid evaluator result")
        records = metrics.get("frontier_records")
        if records is None:
            raise ValueError("valid evaluator result must contain frontier_records")
        records = self._canonical_records(records)
        records_hash = _sha256(records)
        metrics_hash = _hash(
            receipt.get("metrics_sha256"), "evaluation metrics_sha256"
        )
        if metrics_hash != (verified_run.get("verified_receipt_metrics_sha256") or {}).get(
            request_hash
        ):
            raise ValueError("evaluation receipt differs from verified run")
        self.root.mkdir(parents=True, exist_ok=True)
        with self.lock_path.open("a+b") as lock_handle:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
            try:
                events = self._events()
                state = self._replay(events)
                repeated = next(
                    (
                        event for event in events
                        if event.get("evaluation_request_id") == request_hash
                    ),
                    None,
                )
                if repeated is not None:
                    if repeated.get("evaluation_metrics_sha256") != metrics_hash:
                        raise ValueError(
                            "evaluation request was previously bound to different metrics"
                        )
                    if not (
                        repeated.get("wave") == wave.ledger_document()
                        and repeated.get("task_id") == task_id
                        and repeated.get("task_contract_sha256") == contract_hash
                        and repeated.get("task_package_sha256") == package_hash
                        and repeated.get("runtime_source_sha256") == runtime_hash
                        and repeated.get("trusted_evaluator_runtime_sha256")
                        == trusted_runtime_hash
                        and repeated.get("artifact_sha256") == artifact_hash
                        and repeated.get("records_sha256") == records_hash
                        and repeated.get("records") == records
                        and repeated.get("evaluation_request") == dict(request)
                        and repeated.get("evaluation_receipt") == dict(receipt)
                    ):
                        raise ValueError("evaluation request replay binding differs")
                    return {
                        "event_sha256": repeated["event_sha256"],
                        "credit_delta": repeated["credit_delta"],
                        "lifetime_credit": state["lifetime_credit"],
                        "decisions": repeated["decisions"],
                        "receipt_reused": True,
                    }
                self._register_wave(
                    state,
                    wave,
                    {
                        "task_contract_sha256": contract_hash,
                        "task_package_sha256": package_hash,
                        "runtime_source_sha256": runtime_hash,
                        "trusted_evaluator_runtime_sha256": trusted_runtime_hash,
                    },
                )
                self._bind_evidence(
                    state,
                    wave,
                    request_id=request_hash,
                    metrics_sha256=metrics_hash,
                    artifact_sha256=artifact_hash,
                    records_sha256=records_hash,
                    event_index=len(events),
                )
                decisions, credit = self._apply_records(state, wave, records)
                event = {
                    "schema_version": FRONTIER_EVENT_SCHEMA_VERSION,
                    "event_index": len(events),
                    "previous_event_sha256": (
                        events[-1]["event_sha256"] if events else None
                    ),
                    "wave": wave.ledger_document(),
                    "evaluation_request_id": request_hash,
                    "evaluation_metrics_sha256": metrics_hash,
                    "evaluation_request": dict(request),
                    "evaluation_receipt": dict(receipt),
                    "task_id": task_id,
                    "task_contract_sha256": contract_hash,
                    "task_package_sha256": package_hash,
                    "runtime_source_sha256": runtime_hash,
                    "trusted_evaluator_runtime_sha256": trusted_runtime_hash,
                    "artifact_sha256": artifact_hash,
                    "records_sha256": records_hash,
                    "records": records,
                    "decisions": decisions,
                    "credit_delta": credit,
                }
                event["event_sha256"] = _sha256(event)
                event_path = self.event_root / ("%08d.json" % len(events))
                if event_path.exists():
                    raise ValueError("frontier ledger event index already exists")
                _durable_atomic_write(event_path, _canonical_json(event))
                return {
                    "event_sha256": event["event_sha256"],
                    "credit_delta": credit,
                    "lifetime_credit": state["lifetime_credit"],
                    "decisions": decisions,
                    "receipt_reused": False,
                }
            finally:
                fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)

    def snapshot(self) -> dict[str, Any]:
        events = self._events()
        state = self._replay(events)
        waves = sum(len(rows) for rows in state["waves"].values())
        return {
            "schema_version": FRONTIER_EVENT_SCHEMA_VERSION,
            "event_count": len(events),
            "event_head_sha256": events[-1]["event_sha256"] if events else None,
            "family_count": len(state["waves"]),
            "wave_count": waves,
            "accepted_record_count": state["accepted_record_count"],
            "unique_discovery_count": len(state["discoveries"]),
            "optimization_frontiers": dict(state["optimization_frontiers"]),
            "lifetime_credit": state["lifetime_credit"],
        }


def promote_frontier_receipt(
    spec: Any,
    *,
    run_workdir: Path,
    ledger_root: Path,
    request_id: str,
) -> dict[str, Any]:
    """Promote one run receipt into an explicitly selected cross-run ledger."""

    from .algorithms.common import (  # Imported lazily to avoid an import cycle.
        runtime_source_sha256,
        task_contract_sha256,
        task_package_sha256,
    )
    from .evaluate import resolve_trusted_runtime
    from .run_verification import verify_run

    wave = load_frozen_wave(spec)
    if wave is None:
        raise ValueError("task is not opted into a frontier family")
    run_root = Path(run_workdir).resolve()
    ledger_path = Path(ledger_root).resolve()
    if ledger_path == run_root or run_root in ledger_path.parents:
        raise ValueError("canonical frontier ledger must live outside the model run")
    current_trusted_runtime = resolve_trusted_runtime(spec.task_dir)
    with RunLease(run_root):
        verified = verify_run(
            run_root,
            acquire_lease=False,
            expected_trusted_runtime_sha256=(
                current_trusted_runtime.fingerprint_sha256
            ),
        )
        if request_id not in verified["verified_request_ids"]:
            raise ValueError("frontier receipt is not a verified trajectory event")
        manifest_path = run_root / "run_manifest.json"
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError("run workdir lacks a valid run_manifest.json") from exc
        current = {
            "task_id": spec.task_id,
            "task_contract_sha256": task_contract_sha256(spec),
            "task_package_sha256": task_package_sha256(spec),
            "runtime_source_sha256": runtime_source_sha256(),
            "trusted_evaluator_runtime": current_trusted_runtime.descriptor,
            **wave.binding(),
        }
        if any(manifest.get(key) != value for key, value in current.items()):
            raise ValueError("run manifest differs from current frozen task/runtime binding")
        evidence = EvaluationLedger(run_root)
        bound = evidence.require_bound_record(request_id)
        request = bound["request"]
        receipt = bound["receipt"]
        request_current = {
            key: value for key, value in current.items()
            if key != "trusted_evaluator_runtime"
        }
        request_current["trusted_evaluator_runtime_sha256"] = (
            current_trusted_runtime.fingerprint_sha256
        )
        if any(request.get(key) != value for key, value in request_current.items()):
            raise ValueError(
                "evaluation request differs from current frozen task/runtime binding"
            )
        expected_metrics_hash = verified["verified_receipt_metrics_sha256"][request_id]
        if receipt.get("metrics_sha256") != expected_metrics_hash:
            raise ValueError("evaluation receipt changed after run verification")
        return FrontierLedger(ledger_path)._record_verified(
            wave,
            evaluation_ledger=evidence,
            request_id=request_id,
            verified_run=verified,
        )

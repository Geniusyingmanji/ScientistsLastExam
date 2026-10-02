"""Finite candidate-owned model snapshots. No simulator or operator-data access.

This module runs on the trusted side of CandidateProxy's existing JSON callbacks.
It never executes candidate code or deserializes Python objects.
"""

import ast
import hashlib
import json
import math
import os
import re
import tempfile
from pathlib import Path


PROTOCOL = "sle-analysis-snapshots-0.1"
LIMITS = {"snapshots": 16, "total_bytes": 262144, "parameter_bytes": 16384,
          "code_bytes": 32768, "json_depth": 12, "json_nodes": 4096,
          "callback_attempts": 256, "frozen_source_bytes": 64000}
_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,47}\Z")


def _identifier(value):
    if type(value) is not str or _IDENTIFIER.fullmatch(value) is None:
        raise ValueError("model name/version must be 1..48 ASCII letters, digits, dot, underscore or hyphen, starting with a letter or digit")
    return value


def _json(value, *, root_object=False):
    """Bound traversal before serialization; reject subclasses and object hooks."""
    if root_object and type(value) is not dict:
        raise ValueError("model parameters must be a JSON object")
    nodes = [0]
    active = set()

    def visit(item, depth):
        nodes[0] += 1
        if depth > LIMITS["json_depth"] or nodes[0] > LIMITS["json_nodes"]:
            raise ValueError("snapshot JSON depth/node limit exceeded")
        kind = type(item)
        if item is None or kind is bool:
            return
        if kind is int:
            if abs(item) > 2**53 - 1:
                raise ValueError("snapshot integers must be exactly representable within +/- (2**53-1)")
            return
        if kind is float:
            if not math.isfinite(item):
                raise ValueError("snapshot numbers must be finite")
            return
        if kind is str:
            if len(item) > LIMITS["parameter_bytes"]:
                raise ValueError("snapshot string is too large")
            return
        if kind not in (list, dict):
            raise ValueError("snapshots accept only plain JSON data; convert arrays with tolist()")
        if len(item) > LIMITS["json_nodes"] or id(item) in active:
            raise ValueError("snapshot container is oversized or cyclic")
        active.add(id(item))
        try:
            if kind is dict:
                for key, child in item.items():
                    if type(key) is not str or key == "__fs_type__":
                        raise ValueError("snapshot keys must be strings; __fs_type__ is reserved by JSON RPC")
                    visit(key, depth + 1)
                    visit(child, depth + 1)
            else:
                for child in item:
                    visit(child, depth + 1)
        finally:
            active.remove(id(item))

    visit(value, 0)
    encoded = json.dumps(value, sort_keys=True, ensure_ascii=True, allow_nan=False, separators=(",", ":"))
    if len(encoded.encode("ascii")) > LIMITS["parameter_bytes"]:
        raise ValueError("snapshot parameter byte limit exceeded")
    return encoded


def _code(value):
    if type(value) is not str or not value or len(value) > LIMITS["code_bytes"]:
        raise ValueError("saved predictor code must contain 1..32768 UTF-8 bytes")
    try:
        size = len(value.encode("utf-8"))
        if size > LIMITS["code_bytes"]:
            raise ValueError("saved predictor code must contain 1..32768 UTF-8 bytes")
        ast.parse(value)
    except (SyntaxError, RecursionError, UnicodeError, MemoryError):
        raise ValueError("saved predictor code has invalid Python syntax/encoding") from None
    return value


def bind_parameters(code, parameters):
    """Emit ordinary source with JSON-loaded MODEL; execute only in predictor sandbox.

    JSON text is itself serialized as a JSON string literal, which is a valid
    ASCII Python string literal. Candidate parameter text is never Python code.
    No repr, eval, pickle, object serializer, or host-side candidate execution.
    """
    code = _code(code)
    parameter_json = _json(parameters, root_object=True)
    tree = ast.parse(code)
    preamble, line = [], 0
    for index, node in enumerate(tree.body):
        is_docstring = (index == 0 and isinstance(node, ast.Expr) and
                        isinstance(node.value, ast.Constant) and isinstance(node.value.value, str))
        is_future = isinstance(node, ast.ImportFrom) and node.module == "__future__"
        if not (is_docstring or is_future):
            break
        preamble.append(node)
        line = node.end_lineno
    # A future import and an executable statement on the same source line would
    # otherwise run that statement before MODEL exists. Reject that ambiguity.
    if any(node not in preamble and node.lineno <= line for node in tree.body):
        raise ValueError("snapshot predictor preamble must use separate source lines")
    lines = code.splitlines(keepends=True)
    prefix = "".join(lines[:line])
    if prefix and not prefix.endswith("\n"):
        prefix += "\n"
    binding = ("import json as _sle_model_json\nMODEL = _sle_model_json.loads(" +
               json.dumps(parameter_json, ensure_ascii=True) + ")\ndel _sle_model_json\n")
    source = prefix + binding + "".join(lines[line:])
    if len(source.encode("utf-8")) > LIMITS["frozen_source_bytes"]:
        raise ValueError("bound snapshot predictor exceeds final source limit")
    ast.parse(source)
    return source


def contract():
    return {"protocol": PROTOCOL, "limits": dict(LIMITS),
            "save": "save_model(name, version, parameters, predictor_code=None) -> receipt; parameters is a plain finite JSON object",
            "read": "read_model(name, version) -> saved parameters, optional predictor_code and reference",
            "list": "list_models() -> receipts, without parameter/code bodies",
            "versioning": "Name/version is immutable. Identical saves are idempotent; changed content requires a new version. No delete, overwrite, latest alias, path or cross-episode read.",
            "submit": "Use model_snapshot={name,version,sha256} instead of predictor_code to use saved code. Or provide both predictor_code and model_snapshot to bind saved parameters to that code. MODEL holds the restored parameters in the fresh predictor sandbox.",
            "scope": "Candidate-owned JSON/code only. Saving does not execute code or prove predictive correctness. No world, seed, targets, files or network become accessible."}


class ModelSnapshots:
    """One episode's append-only store; callbacks have only this store's authority."""

    def __init__(self, directory=None):
        self._directory = Path(directory) if directory is not None else None
        if self._directory is not None:
            self._directory.mkdir(mode=0o700, parents=False, exist_ok=False)
        self._items = {}
        self._bytes = 0
        self._attempts = 0
        self._sealed = False

    def _attempt(self):
        if self._sealed:
            raise ValueError("model snapshots are frozen")
        self._attempts += 1
        if self._attempts > LIMITS["callback_attempts"]:
            raise ValueError("model snapshot callback allowance exhausted")

    def _persist(self, digest, encoded):
        if self._directory is None:
            return
        temporary = None
        try:
            fd, temporary = tempfile.mkstemp(prefix=".pending-", dir=str(self._directory))
            with os.fdopen(fd, "wb") as stream:
                stream.write(encoded)
                stream.flush()
                os.fsync(stream.fileno())
            # Atomic publication without replacing any existing pathname.
            os.link(temporary, str(self._directory / (digest + ".json")), follow_symlinks=False)
        except OSError:
            raise ValueError("model snapshot persistence failed") from None
        finally:
            if temporary is not None:
                try:
                    os.unlink(temporary)
                except OSError:
                    pass

    def save_model(self, *args, **kwargs):
        self._attempt()
        return self._save_model(*args, **kwargs)

    def _save_model(self, name, version, parameters, predictor_code=None):
        name, version = _identifier(name), _identifier(version)
        parameter_json = _json(parameters, root_object=True)
        if predictor_code is not None:
            predictor_code = _code(predictor_code)
            bind_parameters(predictor_code, parameters)
        item = {"protocol": PROTOCOL, "name": name, "version": version,
                "parameters": json.loads(parameter_json), "predictor_code": predictor_code}
        encoded = json.dumps(item, sort_keys=True, ensure_ascii=True, allow_nan=False, separators=(",", ":")).encode("ascii")
        digest = hashlib.sha256(encoded).hexdigest()
        key = (name, version)
        if key in self._items:
            if self._items[key]["sha256"] != digest:
                raise ValueError("model name/version already exists; use a new version")
            return dict(self._items[key]["receipt"])
        if len(self._items) >= LIMITS["snapshots"] or self._bytes + len(encoded) > LIMITS["total_bytes"]:
            raise ValueError("model snapshot storage allowance exhausted")
        receipt = {"name": name, "version": version, "sha256": digest,
                   "uri": "model://%s/%s" % (name, version), "bytes": len(encoded),
                   "has_predictor_code": predictor_code is not None}
        self._persist(digest, encoded)
        # Mutation occurs only after every validation and atomic publication.
        self._items[key] = {"sha256": digest, "encoded": encoded, "receipt": receipt}
        self._bytes += len(encoded)
        return dict(receipt)

    def _read(self, name, version):
        key = (_identifier(name), _identifier(version))
        if key not in self._items:
            raise ValueError("unknown model snapshot")
        item = self._items[key]
        body = json.loads(item["encoded"].decode("ascii"))
        body["reference"] = {key: item["receipt"][key] for key in ("name", "version", "sha256")}
        return body

    def read_model(self, *args, **kwargs):
        self._attempt()
        return self._read(*args, **kwargs)

    def list_models(self, *args, **kwargs):
        self._attempt()
        if args or kwargs:
            raise ValueError("list_models takes no arguments")
        return self.catalog()

    def catalog(self):
        return [dict(item["receipt"]) for _, item in sorted(self._items.items())]

    def callbacks(self):
        return {"save_model": self.save_model, "read_model": self.read_model, "list_models": self.list_models}

    def seal(self):
        self._sealed = True

    def resolve_submission(self, submission):
        if type(submission) is not dict or "model_snapshot" not in submission:
            return submission, None
        allowed = {"model_snapshot", "claims", "explanation"}
        if set(submission) not in (allowed, allowed | {"predictor_code"}):
            raise ValueError("snapshot submit needs model_snapshot, claims, explanation and optional predictor_code")
        reference = submission["model_snapshot"]
        if type(reference) is not dict or set(reference) != {"name", "version", "sha256"}:
            raise ValueError("model_snapshot requires name, version, sha256 from a saved receipt")
        if type(reference["sha256"]) is not str or re.fullmatch(r"[0-9a-f]{64}", reference["sha256"]) is None:
            raise ValueError("invalid model snapshot sha256")
        item = self._read(reference["name"], reference["version"])
        if item["reference"] != reference:
            raise ValueError("model snapshot digest mismatch")
        code = submission.get("predictor_code", item["predictor_code"])
        if code is None:
            raise ValueError("snapshot has no predictor code; supply predictor_code in submit")
        bound = bind_parameters(code, item["parameters"])
        frozen = {"predictor_code": bound, "claims": submission["claims"], "explanation": submission["explanation"]}
        binding = dict(item["reference"], protocol=PROTOCOL,
                       bound_source_sha256=hashlib.sha256(bound.encode("utf-8")).hexdigest())
        return frozen, binding

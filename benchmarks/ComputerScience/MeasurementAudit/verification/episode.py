"""Measurements-only discovery adapter: no answer key or latent-world oracle.

The trusted broker owns these measurements. Candidate programs receive only
JSON observations from the declared tools; they never receive this filesystem.
The bundled hand-entered table tests the protocol, not scientific capability.
"""
from __future__ import annotations

import copy
import csv
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import stat
import statistics


TASK_ID = "DiscoveryEvidence/MeasurementAudit"
MAX_FILE_BYTES = 4 * 1024 * 1024
MAX_ROWS = 10000
MAX_COLUMNS = 16
NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,47}$")
PARTITIONS = ("exploration", "replication")


def _digest(value):
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _keys(value, keys):
    if not isinstance(value, dict) or set(value) != set(keys):
        raise ValueError("incorrect object keys")


def _text(value, limit=2000):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError("expected bounded nonempty text")


def _finite(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("expected a finite number")
    try:
        valid = math.isfinite(value) and abs(value) <= 1e100
    except (OverflowError, ValueError):
        valid = False
    if not valid:
        raise ValueError("number is nonfinite or outside numeric limits")


def _integer(value, lower, upper):
    if isinstance(value, bool) or not isinstance(value, int) or not lower <= value <= upper:
        raise ValueError("integer outside declared bounds")


def _no_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate manifest key")
        result[key] = value
    return result


def _read_regular(path, directory_fd):
    """Read one explicitly named regular file, rejecting final-link races."""
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    fd = os.open(path.name, flags, dir_fd=directory_fd)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or not 0 < info.st_size <= MAX_FILE_BYTES:
            raise ValueError("bundle files must be bounded nonempty regular files")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            value = stream.read(MAX_FILE_BYTES + 1)
        after = os.fstat(fd)
        if len(value) > MAX_FILE_BYTES or (info.st_size, info.st_mtime_ns, info.st_ctime_ns) != (
                after.st_size, after.st_mtime_ns, after.st_ctime_ns):
            raise ValueError("bundle file changed during loading")
        return value
    finally:
        os.close(fd)


def load_bundle(bundle_path):
    """Strictly load an operator-provided two-file immutable data snapshot.

    The manifest binds bytes and records provenance; it does not authenticate
    the provenance assertion, randomization, independence, or scientific truth.
    """
    path = Path(bundle_path).absolute()
    if path != path.resolve() or path.is_symlink():
        raise ValueError("bundle path and ancestors cannot be symlinks")
    if not path.is_dir():
        raise ValueError("data bundle must be a directory")
    if {entry.name for entry in path.iterdir()} != {"manifest.json", "measurements.csv"}:
        raise ValueError("bundle must contain exactly manifest.json and measurements.csv")
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(str(path), flags)
    try:
        manifest_bytes = _read_regular(path / "manifest.json", fd)
        data_bytes = _read_regular(path / "measurements.csv", fd)
        if set(os.listdir(fd)) != {"manifest.json", "measurements.csv"}:
            raise ValueError("bundle contents changed during loading")
    except OSError as exc:
        raise ValueError("bundle contains an inaccessible or nonregular file") from exc
    finally:
        os.close(fd)
    try:
        manifest = json.loads(manifest_bytes.decode("utf-8"), object_pairs_hook=_no_duplicate_keys,
                              parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite manifest value")))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("manifest must be UTF-8 JSON") from exc
    _keys(manifest, ["schema_version", "dataset_id", "provenance", "columns", "files"])
    if type(manifest["schema_version"]) is not int or manifest["schema_version"] != 1:
        raise ValueError("unsupported data manifest version")
    _text(manifest["dataset_id"], 160)
    _keys(manifest["files"], ["measurements.csv"])
    if manifest["files"]["measurements.csv"] != hashlib.sha256(data_bytes).hexdigest():
        raise ValueError("measurement bytes do not match manifest")
    provenance = manifest["provenance"]
    _keys(provenance, ["kind", "citation", "collection_description", "target_population",
                       "independence_unit", "replication_design", "limitations"])
    if provenance["kind"] not in ("observed_measurements", "protocol_fixture"):
        raise ValueError("unrecognized provenance kind")
    if provenance["replication_design"] not in (
            "held_out_same_source", "independent_collection", "protocol_fixture"):
        raise ValueError("unrecognized replication design")
    if (provenance["kind"] == "protocol_fixture") != (provenance["replication_design"] == "protocol_fixture"):
        raise ValueError("protocol fixture must be identified consistently")
    for key in ("citation", "collection_description", "target_population", "independence_unit"):
        _text(provenance[key])
    if not isinstance(provenance["limitations"], list) or not 1 <= len(provenance["limitations"]) <= 30:
        raise ValueError("at least one bounded provenance limitation is required")
    for item in provenance["limitations"]:
        _text(item)
    columns = manifest["columns"]
    if not isinstance(columns, list) or not 1 <= len(columns) <= MAX_COLUMNS:
        raise ValueError("invalid number of measurement columns")
    names = []
    for column in columns:
        _keys(column, ["name", "unit", "description"])
        name = column["name"]
        if not isinstance(name, str) or not NAME.fullmatch(name) or name in ("sample_id", "partition"):
            raise ValueError("invalid numeric column name")
        names.append(name)
        _text(column["unit"], 120)
        _text(column["description"])
    if len(set(names)) != len(names):
        raise ValueError("duplicate measurement column")
    try:
        reader = csv.reader(io.StringIO(data_bytes.decode("utf-8"), newline=""), strict=True)
        header = next(reader)
        if header != ["sample_id", "partition"] + names:
            raise ValueError("CSV header must match manifest column order")
        rows = {partition: [] for partition in PARTITIONS}
        ids = set()
        for row in reader:
            if len(ids) >= MAX_ROWS or len(row) != len(header):
                raise ValueError("invalid CSV dimensions")
            _text(row[0], 160)
            if row[0] in ids or row[1] not in PARTITIONS:
                raise ValueError("sample IDs must be unique and partitions explicit")
            ids.add(row[0])
            numeric = [float(value) for value in row[2:]]
            for value in numeric:
                _finite(value)
            rows[row[1]].append(dict(zip(header, row[:2] + numeric)))
        if any(len(rows[partition]) < 2 for partition in PARTITIONS):
            raise ValueError("each partition requires at least two distinct samples")
    except (UnicodeDecodeError, csv.Error, StopIteration) as exc:
        raise ValueError("invalid UTF-8 measurement CSV") from exc
    binding = {"schema_version": 1, "dataset_id": manifest["dataset_id"],
               "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
               "measurements_sha256": hashlib.sha256(data_bytes).hexdigest(),
               "provenance": copy.deepcopy(provenance), "columns": copy.deepcopy(columns),
               "partition_counts": {key: len(value) for key, value in rows.items()},
               "ground_truth": "absent", "provenance_authentication": "operator_asserted_not_verified"}
    binding["sha256"] = _digest(binding)
    return manifest, rows, binding


class MeasurementEnvironment:
    task_id = TASK_ID
    evaluation_mode = "evidence_only"
    budget_units = 4096

    def __init__(self, bundle_path):
        self._manifest, self._rows, self._binding = load_bundle(bundle_path)
        self._columns = [item["name"] for item in self._manifest["columns"]]
        self._spent = 0
        self._phase = "exploration"
        self._sequence = 0

    @classmethod
    def from_bundle(cls, bundle_path):
        return cls(bundle_path)

    def data_binding(self):
        return copy.deepcopy(self._binding)

    def public_problem(self):
        return {
            "task_id": self.task_id, "contract_version": "measurement-evidence-v1",
            "evaluation_mode": self.evaluation_mode, "budget_units": self.budget_units,
            "evaluation_role": "protocol_only" if self._binding["provenance"]["kind"] == "protocol_fixture" else "evidence_candidate",
            "frontier_eligible": False, "data_binding": self.data_binding(),
            "objective": "Develop falsifiable explanations for observed measurements, compare competing hypotheses, and prospectively test them on a sealed measurement partition. Report uncertainty and inconclusive results.",
            "ground_truth": "No answer key, known mechanism, hidden coefficients, or correctness oracle exists in this adapter.",
            "tools": {
                "read_measurements": {"arguments": {"partition": "exploration", "columns": "nonempty distinct measurement names", "offset": "zero-based row offset", "limit": "1..256"},
                                      "cost": "number of returned rows times number of requested measurement columns",
                                      "returns": "rows, columns, partition, evidence_id; rows are reused measurements, not fresh samples"},
                "summarize": {"arguments": {"partition": "exploration or replication", "column": "measurement name", "statistic": "mean or mean_difference", "group_column": "null for mean, measurement name for difference", "group_values": "null for mean, two distinct finite numbers for difference"},
                              "cost": "total rows in requested partition, irrespective of grouping; every query is charged",
                              "returns": "value, n, std_error, group summaries, partition, evidence_id",
                              "mean_difference": "mean of group_values[1] minus mean of group_values[0]; fewer than 2 samples in either group returns insufficient_samples, never a numerical claim"}},
            "replication": {"access": "sealed until immutable dossier commit; exploration closes when replication begins",
                            "scope": self._binding["provenance"]["replication_design"],
                            "budget": "{} total units across exploration and replication; reserve enough before committing".format(self.budget_units),
                            "limits": "A reserved data partition is not automatically an independent collection. Repeated queries reuse the same measurements. No multiple-testing correction or causal identification is supplied."},
            "numeric_diagnostics": "Standard error uses sample standard deviation/sqrt(n), or independent-group sum of variances for a difference. These formulas assume independent samples within the declared unit; manifest assertions are not verified. There is no significance decision or scientific correctness score.",
        }

    def _selection(self, tool, arguments):
        if tool == "read_measurements":
            _keys(arguments, ["partition", "columns", "offset", "limit"])
            if arguments["partition"] != "exploration":
                raise ValueError("raw-row tool exposes exploration only")
            columns = arguments["columns"]
            if (not isinstance(columns, list) or not columns or len(columns) > len(self._columns)
                    or any(not isinstance(item, str) or item not in self._columns for item in columns)
                    or len(set(columns)) != len(columns)):
                raise ValueError("invalid measurement column selection")
            _integer(arguments["offset"], 0, len(self._rows["exploration"]) - 1)
            _integer(arguments["limit"], 1, 256)
            selected = self._rows["exploration"][arguments["offset"]:arguments["offset"] + arguments["limit"]]
            return selected, len(selected) * len(columns)
        if tool != "summarize":
            raise ValueError("unknown measurement tool")
        _keys(arguments, ["partition", "column", "statistic", "group_column", "group_values"])
        if arguments["partition"] not in PARTITIONS or arguments["column"] not in self._columns:
            raise ValueError("invalid partition or measurement column")
        selected = self._rows[arguments["partition"]]
        if arguments["statistic"] == "mean":
            if arguments["group_column"] is not None or arguments["group_values"] is not None:
                raise ValueError("mean requires null grouping fields")
            return selected, len(selected)
        if arguments["statistic"] != "mean_difference" or arguments["group_column"] not in self._columns:
            raise ValueError("invalid statistic or grouping column")
        levels = arguments["group_values"]
        if not isinstance(levels, list) or len(levels) != 2:
            raise ValueError("difference requires two group values")
        for level in levels:
            _finite(level)
        if levels[0] == levels[1]:
            raise ValueError("group values must be distinct")
        groups = [[row for row in selected if row[arguments["group_column"]] == level] for level in levels]
        # Group existence and group counts are measurement information, so
        # neither validity nor preflight cost may expose them while sealed.
        return groups, len(selected)

    def action_cost(self, tool, arguments):
        # Deliberately phase-agnostic: the broker can reserve the full cost of
        # preregistered sealed tests before beginning the one-way transition.
        _selected, cost = self._selection(tool, arguments)
        return cost

    def is_sealed_action(self, tool, arguments):
        self._selection(tool, arguments)
        return arguments["partition"] == "replication"

    def begin_confirmation(self):
        if self._phase != "exploration":
            raise ValueError("replication phase can begin only once")
        self._phase = "replication"

    @staticmethod
    def _summary(rows, column):
        values = [row[column] for row in rows]
        if len(values) < 2:
            return {"n": len(values), "value": None, "sample_sd": None,
                    "std_error": None, "status": "insufficient_samples"}
        sd = statistics.stdev(values)
        return {"n": len(values), "value": statistics.fmean(values),
                "sample_sd": sd, "std_error": sd / math.sqrt(len(values)), "status": "observed"}

    def experiment(self, tool, arguments):
        selected, cost = self._selection(tool, arguments)
        if arguments["partition"] != self._phase:
            raise ValueError("requested measurements are unavailable in this episode phase")
        if self._spent + cost > self.budget_units:
            raise ValueError("measurement budget exhausted")
        if tool == "read_measurements":
            payload = {"partition": "exploration", "columns": list(arguments["columns"]),
                       "rows": [{"sample_id": row["sample_id"], **{name: row[name] for name in arguments["columns"]}}
                                for row in selected], "n": len(selected)}
        elif arguments["statistic"] == "mean":
            payload = self._summary(selected, arguments["column"])
            payload.update({"partition": arguments["partition"], "column": arguments["column"],
                            "statistic": "mean", "groups": None})
        else:
            groups = [self._summary(group, arguments["column"]) for group in selected]
            for group, level in zip(groups, arguments["group_values"]):
                group["group_value"] = level
            observed = all(group["status"] == "observed" for group in groups)
            payload = {"partition": arguments["partition"], "column": arguments["column"],
                       "statistic": "mean_difference", "group_column": arguments["group_column"],
                       "groups": groups, "n": sum(group["n"] for group in groups),
                       "value": groups[1]["value"] - groups[0]["value"] if observed else None,
                       "std_error": math.sqrt(sum(group["std_error"] ** 2 for group in groups)) if observed else None,
                       "status": "observed" if observed else "insufficient_samples"}
        self._spent += cost
        self._sequence += 1
        if tool == "read_measurements":
            scope_rows = selected
            scope_columns = list(arguments["columns"])
        elif arguments["statistic"] == "mean":
            scope_rows = selected
            scope_columns = [arguments["column"]]
        else:
            scope_rows = [row for group in selected for row in group]
            # Group counts and the group-ordered sample IDs also expose the
            # grouping variable. Its later summary is a reuse of information,
            # even when the earlier query's target was a different column.
            scope_columns = list(dict.fromkeys([arguments["column"], arguments["group_column"]]))
        # Only disclose actual observed row identities after the phase guard.
        # This footprint lets the ledger detect post-hoc tests even when a
        # previous raw-row query and a later summary use different arguments.
        payload["evidence_scope"] = {
            "data_sha256": self._binding["measurements_sha256"],
            "partition": arguments["partition"], "sampling": "fixed_rows",
            "measured_columns": scope_columns,
            "sample_ids": [row["sample_id"] for row in scope_rows],
        }
        payload.update({"measurement_source_sha256": self._binding["sha256"],
                        "sampling": "fixed_observed_rows_reused_across_queries", "charged_units": cost})
        native = {"dataset": self._binding["sha256"], "sequence": self._sequence,
                  "tool": tool, "arguments": arguments, "observation": payload}
        payload["evidence_id"] = "measurement-{}-{}".format(self._sequence, _digest(native)[:24])
        return copy.deepcopy(payload)


def create_environment(seed, bundle_path=None):
    # Seeds do not generate measurements, reshuffle partitions, or define truth.
    # Explicitly accept the common runner's seed without pretending it creates
    # independent scientific worlds or model draws.
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise ValueError("seed must be a nonnegative integer")
    if bundle_path is None:
        bundle_path = Path(__file__).resolve().parents[1] / "fixtures" / "protocol"
    return MeasurementEnvironment.from_bundle(bundle_path)

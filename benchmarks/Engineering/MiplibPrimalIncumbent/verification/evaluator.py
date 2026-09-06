"""Primal-only oracle for three frozen MIPLIB 2017 integer programs.

The official MIPLIB checker is a primal feasibility and objective check. Duals are not
part of the contract. This evaluator reparses the vendored MPS files and checks a dense
integer assignment with the published MIPLIB linear and integrality tolerances. It does
not fetch anything, does not read `.sol` files, and does not call a MIP solver.
"""
from __future__ import annotations

import hashlib
from collections import defaultdict
from pathlib import Path
from typing import Any

TASK_DIR = Path(__file__).resolve().parents[1]
INSTANCE_DIR = TASK_DIR / "references" / "instances"

CONSTRAINT_ABS_TOL = 1e-6
CONSTRAINT_REL_TOL = 1e-5
INTEGRALITY_TOL = 1e-5

# Dated MIPLIB 2017 solufile v36 proven optima. Literals by design: this checker is primal-only.
PUBLISHED_OPTIMUM_GEN_IP002 = -4783.733392
PUBLISHED_OPTIMUM_GEN_IP021 = 2361.45419519
PUBLISHED_OPTIMUM_GEN_IP054 = 6840.96564179

INSTANCES = (
    {
        "name": "gen-ip002",
        "mps_filename": "gen-ip002.mps",
        "mps_sha256": "30ed071e531beea561b330dd8e590eb641a5ec6d4e3f41a8d54735ce27db01b6",
        "n_variables": 41,
        "n_constraints": 24,
        "baseline_objective": 0.0,
        "reference_objective": PUBLISHED_OPTIMUM_GEN_IP002,
    },
    {
        "name": "gen-ip021",
        "mps_filename": "gen-ip021.mps",
        "mps_sha256": "ab3150e5e4ba4fd022f5a0ccab21bef329b6da8001cb67eedacb11221f2e7c54",
        "n_variables": 35,
        "n_constraints": 28,
        "baseline_objective": 4808.1407336654,
        "reference_objective": PUBLISHED_OPTIMUM_GEN_IP021,
    },
    {
        "name": "gen-ip054",
        "mps_filename": "gen-ip054.mps",
        "mps_sha256": "8b71b70a6f92ea9bde78b375f4366e7cc021cfb517df87130775f8b8bdf47333",
        "n_variables": 30,
        "n_constraints": 27,
        "baseline_objective": 10700.711798467,
        "reference_objective": PUBLISHED_OPTIMUM_GEN_IP054,
    },
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _parse_mps(path: Path) -> dict[str, Any]:
    sense: dict[str, str] = {}
    objective: dict[str, float] = {}
    matrix: dict[str, dict[str, float]] = defaultdict(dict)
    rhs: dict[str, float] = {}
    lower: dict[str, float] = {}
    section = None
    objrow = None
    columns: list[str] = []
    seen: set[str] = set()
    with path.open(encoding="iso-8859-1") as handle:
        for raw in handle:
            line = raw.strip()
            if not line or line.startswith("*"):
                continue
            if line.startswith("ROWS"):
                section = "ROWS"
                continue
            if line.startswith("COLUMNS"):
                section = "COLUMNS"
                continue
            if line.startswith("RHS"):
                section = "RHS"
                continue
            if line.startswith("BOUNDS"):
                section = "BOUNDS"
                continue
            if line.startswith("ENDATA"):
                break
            if line.startswith("NAME") or line.startswith("OBJSENSE"):
                continue
            fields = line.split()
            if section == "ROWS":
                row_sense, name = fields[0], fields[1]
                sense[name] = row_sense
                if row_sense == "N" and objrow is None:
                    objrow = name
                continue
            if section == "COLUMNS":
                if "MARKER" in line:
                    continue
                column = fields[0]
                if column not in seen:
                    seen.add(column)
                    columns.append(column)
                rest = fields[1:]
                for index in range(0, len(rest), 2):
                    row, value = rest[index], float(rest[index + 1])
                    if row == objrow:
                        objective[column] = objective.get(column, 0.0) + value
                    else:
                        matrix[row][column] = matrix[row].get(column, 0.0) + value
                continue
            if section == "RHS":
                rest = fields[1:]
                for index in range(0, len(rest), 2):
                    rhs[rest[index]] = float(rest[index + 1])
                continue
            if section == "BOUNDS":
                kind = fields[0]
                if kind in {"LO", "LI"}:
                    lower[fields[2]] = float(fields[3]) if len(fields) > 3 else 0.0
    constraint_names = [name for name, row_sense in sense.items() if row_sense != "N"]
    return {
        "columns": columns,
        "objective": [float(objective.get(column, 0.0)) for column in columns],
        "lower_bounds": [float(lower.get(column, 0.0)) for column in columns],
        "row_senses": [sense[name] for name in constraint_names],
        "rhs": [float(rhs.get(name, 0.0)) for name in constraint_names],
        "matrix": [
            {column: coeff for column, coeff in matrix[name].items()}
            for name in constraint_names
        ],
    }


def _load_model(row: dict[str, Any]) -> dict[str, Any]:
    path = INSTANCE_DIR / row["mps_filename"]
    digest = _sha256(path)
    if digest != row["mps_sha256"]:
        raise RuntimeError("vendored MPS hash mismatch for %s" % row["name"])
    model = _parse_mps(path)
    if len(model["columns"]) != row["n_variables"]:
        raise RuntimeError("variable count mismatch for %s" % row["name"])
    if len(model["rhs"]) != row["n_constraints"]:
        raise RuntimeError("constraint count mismatch for %s" % row["name"])
    return model


def _csr(model: dict[str, Any]) -> tuple[list[int], list[int], list[float]]:
    row_ptr = [0]
    column_indices: list[int] = []
    coefficients: list[float] = []
    index = {name: position for position, name in enumerate(model["columns"])}
    for entries in model["matrix"]:
        for name in sorted(entries, key=lambda item: index[item]):
            column_indices.append(index[name])
            coefficients.append(float(entries[name]))
        row_ptr.append(len(column_indices))
    return row_ptr, column_indices, coefficients


def _public_instance(row: dict[str, Any], model: dict[str, Any]) -> dict[str, Any]:
    row_ptr, column_indices, coefficients = _csr(model)
    return {
        "name": row["name"],
        "sense": "minimize",
        "n_variables": row["n_variables"],
        "n_constraints": row["n_constraints"],
        "variable_names": list(model["columns"]),
        "objective": list(model["objective"]),
        "lower_bounds": list(model["lower_bounds"]),
        "row_senses": list(model["row_senses"]),
        "rhs": list(model["rhs"]),
        "row_ptr": row_ptr,
        "column_indices": column_indices,
        "coefficients": coefficients,
        "mps_sha256": row["mps_sha256"],
        "constraint_abs_tol": CONSTRAINT_ABS_TOL,
        "constraint_rel_tol": CONSTRAINT_REL_TOL,
        "integrality_tol": INTEGRALITY_TOL,
    }


def _read_assignment(value: Any, n_variables: int) -> list[int]:
    if not isinstance(value, (list, tuple)) or len(value) != n_variables:
        raise ValueError("assignment must be a dense list of n_variables integers")
    assignment: list[int] = []
    for entry in value:
        if isinstance(entry, bool) or not isinstance(entry, int):
            raise ValueError("assignment entries must be integers; floats are rejected")
        assignment.append(int(entry))
    return assignment


def _max_violation(assignment: list[int], model: dict[str, Any]) -> float:
    index = {name: position for position, name in enumerate(model["columns"])}
    worst = 0.0
    for sense, rhs, entries in zip(model["row_senses"], model["rhs"], model["matrix"]):
        activity = 0.0
        for name, coeff in entries.items():
            activity += coeff * assignment[index[name]]
        if sense == "L":
            slack = activity - rhs
        elif sense == "G":
            slack = rhs - activity
        else:
            slack = abs(activity - rhs)
        scale = max(1.0, abs(rhs), abs(activity))
        allowed = max(CONSTRAINT_ABS_TOL, CONSTRAINT_REL_TOL * scale)
        worst = max(worst, slack - allowed)
    return worst


def _objective(assignment: list[int], model: dict[str, Any]) -> float:
    return sum(coeff * value for coeff, value in zip(model["objective"], assignment))


def _instance_score(row: dict[str, Any], objective: float) -> float:
    baseline = row["baseline_objective"]
    reference = row["reference_objective"]
    span = baseline - reference
    if span <= 0:
        return 0.0
    progress = (baseline - objective) / span
    return max(0.0, min(1.0, progress))


def evaluate(improve_primal):
    rows = []
    for index, row in enumerate(INSTANCES):
        model = _load_model(row)
        published = {
            "instance_index": index,
            "name": row["name"],
            "n_variables": row["n_variables"],
            "n_constraints": row["n_constraints"],
        }
        try:
            assignment = _read_assignment(
                improve_primal(_public_instance(row, model)), row["n_variables"])
            for value, lower in zip(assignment, model["lower_bounds"]):
                if value < lower - INTEGRALITY_TOL:
                    raise ValueError("variable below its lower bound")
            violation = _max_violation(assignment, model)
            if violation > 0:
                raise ValueError("infeasible assignment; residual %s" % violation)
            objective = _objective(assignment, model)
            score = _instance_score(row, objective)
            published.update({
                "valid": True,
                "objective": float(objective),
                "instance_score": round(score, 6),
                "constraint_violation": 0.0,
            })
        except Exception as exc:  # noqa: BLE001
            published.update({
                "valid": False,
                "reason": "%s: %s" % (type(exc).__name__, exc),
                "objective": None,
                "instance_score": 0.0,
                "constraint_violation": None,
            })
        rows.append(published)

    valid = [row for row in rows if row["valid"]]
    combined = sum(row["instance_score"] for row in rows) / len(rows)
    return {
        "combined_score": float(combined),
        "valid": 1.0 if valid else 0.0,
        "feasibility_rate": len(valid) / len(rows),
        "raw_score": float(combined),
        "instances_with_a_feasible_assignment": len(valid),
        "per_instance": rows,
    }

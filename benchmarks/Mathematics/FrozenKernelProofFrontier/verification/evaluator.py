"""Hidden oracle for FrozenKernelProofFrontier.

A first-wave conversion of FormalResearchProof: small closed tautologies in a frozen
propositional Hilbert kernel, scored by proof size. Not Lean, not mathlib, not Tate.
Closure count is not the score. Sorry is not a tactic here because there are no tactics.

Score one is hung on target sizes strictly below the compiled natural-deduction
proofs. Matching those compiled terms therefore lands in (0.3, 0.8), not at one.
The scale is logarithmic in length so identity (size 5 vs cap 64) does not saturate.
"""
from __future__ import annotations

import math
from typing import Any

SIZE_CAP = 64
ATOMS = ("A", "B", "C")
AXIOMS = ("K", "S", "ANDI", "ANDEL", "ANDER")

THEOREMS = (
    {
        "name": "identity",
        "goal": ("imp", "A", "A"),
        "compiled_size": 5,
        "target_size": 3,
    },
    {
        "name": "conjunction_swap",
        "goal": ("imp", ("and", "A", "B"), ("and", "B", "A")),
        "compiled_size": 26,
        "target_size": 14,
    },
    {
        "name": "packed_composition",
        "goal": ("imp", ("and", ("imp", "A", "B"), ("and", ("imp", "B", "C"), "A")), "C"),
        "compiled_size": 35,
        "target_size": 18,
    },
    {
        "name": "modus_ponens_closed",
        "goal": ("imp", ("and", ("imp", "A", "B"), "A"), "B"),
        "compiled_size": 20,
        "target_size": 11,
    },
)


def _formula(value: Any):
    if isinstance(value, str):
        if value not in ATOMS:
            raise ValueError("unknown atom")
        return value
    if isinstance(value, (list, tuple)) and len(value) == 3 and value[0] in {"imp", "and"}:
        return (value[0], _formula(value[1]), _formula(value[2]))
    raise ValueError("a formula is an atom or [imp|and, left, right]")


def _axiom_formula(name: str, subst: dict):
    try:
        x, y = subst["X"], subst["Y"]
    except KeyError as exc:
        raise ValueError("axiom substitution missing a variable") from exc
    if name == "K":
        return ("imp", x, ("imp", y, x))
    if name == "ANDI":
        return ("imp", x, ("imp", y, ("and", x, y)))
    if name == "ANDEL":
        return ("imp", ("and", x, y), x)
    if name == "ANDER":
        return ("imp", ("and", x, y), y)
    if name == "S":
        z = subst.get("Z")
        if z is None:
            raise ValueError("S needs Z")
        return ("imp", ("imp", x, ("imp", y, z)), ("imp", ("imp", x, y), ("imp", x, z)))
    raise ValueError("axiom not on the allowlist")


def _check_proof(raw: Any, goal: tuple) -> int:
    if not isinstance(raw, (list, tuple)) or not raw:
        raise ValueError("a proof is a non-empty list of lines")
    if len(raw) > SIZE_CAP:
        raise ValueError("proof longer than the size cap")
    derived = []
    for line in raw:
        if not isinstance(line, dict):
            raise ValueError("each line is a mapping")
        if "axiom" in line:
            name = line["axiom"]
            if name not in AXIOMS:
                raise ValueError("axiom not on the allowlist")
            subst = line.get("subst")
            if not isinstance(subst, dict):
                raise ValueError("axiom substitution must be a mapping")
            frozen = {key: _formula(value) for key, value in subst.items()}
            derived.append(_axiom_formula(name, frozen))
            continue
        if "mp" in line:
            pair = line["mp"]
            if not isinstance(pair, (list, tuple)) or len(pair) != 2:
                raise ValueError("mp is [antecedent_index, implication_index]")
            i, j = pair
            if isinstance(i, bool) or isinstance(j, bool) or not isinstance(i, int) or not isinstance(j, int):
                raise ValueError("mp indices must be integers")
            if not (0 <= i < len(derived) and 0 <= j < len(derived)):
                raise ValueError("mp index out of range")
            antecedent, implication = derived[i], derived[j]
            if not (isinstance(implication, tuple) and implication[0] == "imp"
                    and implication[1] == antecedent):
                raise ValueError("modus ponens does not match")
            derived.append(implication[2])
            continue
        raise ValueError("a line is either axiom or mp")
    if derived[-1] != goal:
        raise ValueError("last line is not the theorem")
    return len(raw)


def _public_instance(row: dict) -> dict:
    def ser(formula):
        if isinstance(formula, str):
            return formula
        return [formula[0], ser(formula[1]), ser(formula[2])]

    return {
        "name": row["name"],
        "theorem": ser(row["goal"]),
        "size_cap": SIZE_CAP,
        "axiom_names": list(AXIOMS),
        "atoms": list(ATOMS),
        "target_size": row["target_size"],
    }


def evaluate(build_proofs):
    problem = {
        "size_cap": SIZE_CAP,
        "axiom_names": list(AXIOMS),
        "atoms": list(ATOMS),
        "theorems": [_public_instance(row) for row in THEOREMS],
    }
    rows = []
    try:
        bundle = build_proofs(problem)
    except Exception as exc:  # noqa: BLE001
        bundle = exc
    for index, row in enumerate(THEOREMS):
        published = {
            "instance_index": index,
            "name": row["name"],
            "size_cap": SIZE_CAP,
            "target_size": row["target_size"],
            "compiled_size": row["compiled_size"],
        }
        try:
            if isinstance(bundle, Exception):
                raise bundle
            if not isinstance(bundle, dict):
                raise ValueError("build_proofs must return a mapping of name to proof")
            size = _check_proof(bundle.get(row["name"]), row["goal"])
            if size >= SIZE_CAP:
                score = 0.0
            else:
                span = math.log(SIZE_CAP / row["target_size"])
                score = math.log(SIZE_CAP / size) / span
            published.update({
                "valid": True,
                "proof_size": size,
                "instance_score": round(max(0.0, score), 6),
            })
        except Exception as exc:  # noqa: BLE001
            published.update({
                "valid": False,
                "reason": "%s: %s" % (type(exc).__name__, exc),
                "proof_size": None,
                "instance_score": 0.0,
            })
        rows.append(published)
    valid = [row for row in rows if row["valid"]]
    combined = sum(row["instance_score"] for row in rows) / len(rows)
    return {
        "combined_score": float(combined),
        "valid": 1.0 if valid else 0.0,
        "feasibility_rate": len(valid) / len(rows),
        "raw_score": float(combined),
        "instances_with_a_valid_proof": len(valid),
        "per_instance": rows,
    }

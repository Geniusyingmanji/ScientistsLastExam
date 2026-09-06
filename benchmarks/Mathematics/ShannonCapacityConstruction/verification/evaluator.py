"""Exact finite C7 strong-power construction check; standard library only.

Candidate execution must be isolated by the caller. This module checks returned
data and catches ordinary candidate exceptions; it is not a Python sandbox.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


ALPHABET_SIZE = 7
BLOCK_LENGTH = 5
MAX_CODEWORDS = 512
BASELINE_SIZE = 243
REFERENCE_SIZE = 367
REFERENCE_SHA256 = "3f24988518568a090a7023079439281738c245dfe73171d7981cf589b02d77f3"


def verify_codewords(codewords, *, alphabet_size=7, block_length=5, max_codewords=512):
    """Validate the whole matrix, then check every distinct pair exactly.

    Optional dimensions support small oracle controls. Evaluation always uses the
    fixed task dimensions. Invalid artifacts never receive a credited raw size.
    """
    result = {"schema_valid": False, "valid": False, "raw_size": None, "reason": ""}
    if type(codewords) is not list or not 1 <= len(codewords) <= max_codewords:
        result["reason"] = "codewords must be a list with 1..max_codewords rows"
        return result
    for row in codewords:
        if type(row) is not list or len(row) != block_length:
            result["reason"] = "each row must be a list of exactly block_length symbols"
            return result
        if any(type(value) is not int or not 0 <= value < alphabet_size for value in row):
            result["reason"] = "symbols must be native integers in the alphabet range"
            return result
    if len({tuple(row) for row in codewords}) != len(codewords):
        result["reason"] = "codewords must be distinct"
        return result
    result["schema_valid"] = True
    for i, word in enumerate(codewords):
        for other in codewords[i + 1:]:
            if not any(min(abs(x - y), alphabet_size - abs(x - y)) > 1
                       for x, y in zip(word, other)):
                result["reason"] = "a pair is confusable in every coordinate"
                return result
    result.update(valid=True, raw_size=len(codewords), reason="valid exact independent set")
    return result


def load_reference_codewords():
    """Load the public historical fixture and verify its content before use."""
    reference = Path(__file__).resolve().parents[1] / "references/c7_power5_reference.json"
    fixture = json.loads(reference.read_text(encoding="utf-8"))
    rows = fixture["codewords"]
    digest = hashlib.sha256(json.dumps(rows, separators=(",", ":")).encode()).hexdigest()
    if digest != REFERENCE_SHA256 or fixture["witness_sha256"] != digest:
        raise ValueError("public reference fixture hash mismatch")
    result = verify_codewords(rows)
    if not result["valid"] or result["raw_size"] != REFERENCE_SIZE:
        raise ValueError("public reference fixture failed exact verification")
    return rows


def normalized_size_gain(size, reference_size):
    """Arithmetic score only; calling this does not validate a construction."""
    return max(0.0, (size - BASELINE_SIZE) / (reference_size - BASELINE_SIZE))


def evaluate(build_code):
    reference_size = len(load_reference_codewords())
    result = {
        "combined_score": 0.0, "valid": False, "schema_valid": False,
        "raw_size": None, "reference_size": reference_size,
        "baseline_size": BASELINE_SIZE, "beyond_reference": False, "reason": "",
    }
    # Fresh scalar-only input: a candidate cannot mutate the oracle's problem.
    problem = {"alphabet_size": ALPHABET_SIZE, "block_length": BLOCK_LENGTH,
               "max_codewords": MAX_CODEWORDS, "reference_size": reference_size}
    try:
        artifact = build_code(problem)
    except Exception as exc:
        result["reason"] = "candidate raised " + type(exc).__name__
        return result
    if type(artifact) is not dict or set(artifact) != {"codewords"}:
        result["reason"] = "return exactly a dictionary with the key codewords"
        return result
    checked = verify_codewords(artifact["codewords"], alphabet_size=ALPHABET_SIZE,
                               block_length=BLOCK_LENGTH, max_codewords=MAX_CODEWORDS)
    result.update(checked)
    if result["valid"]:
        result["combined_score"] = normalized_size_gain(result["raw_size"], reference_size)
        result["beyond_reference"] = result["raw_size"] > reference_size
    return result

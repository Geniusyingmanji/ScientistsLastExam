"""Bounded exact verifier for positive rational Diophantine septuple JSON data.

This is a binary object challenge. Pair counts are diagnostics, not a score.
The CLI never imports, evaluates, or executes a candidate program.
"""
from __future__ import annotations

import argparse
from fractions import Fraction
from itertools import combinations
import json
from math import isqrt
import re
import sys


MAX_COMPONENT_BITS = 2048
MAX_RAW_STRING_LENGTH = 1235  # Two 617-digit integers plus '/'.
MAX_INPUT_BYTES = 32768
RATIONAL_PATTERN = re.compile(r"[0-9]+(?:/[0-9]+)?", re.ASCII)


def _invalid(reason, total_pairs=21):
    return {"schema_valid": False, "success": False, "pairs_satisfied": 0,
            "total_pairs": total_pairs, "status": "invalid", "reason": reason}


def verify(data, *, expected_count=7):
    """The optional count is for known smaller controls; CLI always requires 7."""
    if type(expected_count) is not int or not 1 <= expected_count <= 7:
        raise ValueError("expected_count must be an integer from 1 through 7")
    total_pairs = expected_count * (expected_count - 1) // 2
    if type(data) is not list or len(data) != expected_count:
        return _invalid(f"expected a JSON list of exactly {expected_count} strings", total_pairs)
    # Validate every raw field before any integer conversion or pair arithmetic.
    for raw in data:
        if type(raw) is not str or not 1 <= len(raw) <= MAX_RAW_STRING_LENGTH:
            return _invalid("each rational must be a string of 1..1235 characters", total_pairs)
        if RATIONAL_PATTERN.fullmatch(raw) is None:
            return _invalid("use ASCII decimal integer or numerator/denominator strings", total_pairs)
    values = []
    for raw in data:
        pieces = raw.split("/")
        numerator = int(pieces[0])
        denominator = int(pieces[1]) if len(pieces) == 2 else 1
        if numerator.bit_length() > MAX_COMPONENT_BITS or denominator.bit_length() > MAX_COMPONENT_BITS:
            return _invalid("raw numerator and denominator must each fit 2048 bits", total_pairs)
        if numerator <= 0 or denominator <= 0:
            return _invalid("numerator and denominator must be positive", total_pairs)
        values.append(Fraction(numerator, denominator))
    if len(set(values)) != expected_count:
        return _invalid("rationals must be distinct after exact reduction", total_pairs)
    pairs_satisfied = 0
    for left, right in combinations(values, 2):
        product_plus_one = left * right + 1
        numerator, denominator = product_plus_one.numerator, product_plus_one.denominator
        if isqrt(numerator) ** 2 == numerator and isqrt(denominator) ** 2 == denominator:
            pairs_satisfied += 1
    success = pairs_satisfied == total_pairs
    return {"schema_valid": True, "success": success, "pairs_satisfied": pairs_satisfied,
            "total_pairs": total_pairs, "status": "success" if success else "not_found",
            "reason": "all required pairs are rational squares" if success else "at least one pair is not a rational square"}


def _reject_nonfinite(value):
    raise ValueError("nonfinite JSON constants are not accepted")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("submission", nargs="?", default="-", help="JSON data file, or - for stdin")
    args = parser.parse_args(argv)
    try:
        if args.submission == "-":
            payload = sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)
        else:
            with open(args.submission, "rb") as source:
                payload = source.read(MAX_INPUT_BYTES + 1)
        if len(payload) > MAX_INPUT_BYTES:
            result = _invalid("JSON document exceeds 32768 bytes")
        else:
            data = json.loads(payload, parse_constant=_reject_nonfinite)
            result = verify(data)
    except (OSError, ValueError, UnicodeError, RecursionError):
        result = _invalid("cannot read a bounded valid JSON data document")
    print(json.dumps(result, sort_keys=True, allow_nan=False))
    return 0 if result["success"] else (1 if result["schema_valid"] else 2)


if __name__ == "__main__":
    sys.exit(main())

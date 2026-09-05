"""Frozen oracle for OrthogonalDNACodewords (hidden from the agent).

Build the largest library of DNA words that stay orthogonal under hybridization:
fixed GC content, a minimum pairwise Hamming distance, a cap on Watson-Crick
complementary pairs over every shifted alignment of one word against the reverse
complement of another (self included), and a homopolymer-run cap. Verification is a
pure counting check independent of how the library was built, so the record is open:
score one ties the frozen truth-blind witness search and any larger valid library
scores above it.
"""

from __future__ import annotations

import numpy as np

BASE_CODES = {"A": 0, "C": 1, "G": 2, "T": 3}

FAMILIES = (
    {"family": "dna16", "length": 16, "gc_count": 8, "min_hamming": 8,
     "max_crossdimer": 6, "max_homopolymer": 3, "max_library": 512},
    {"family": "dna12", "length": 12, "gc_count": 6, "min_hamming": 7,
     "max_crossdimer": 5, "max_homopolymer": 3, "max_library": 512},
)

# Sizes of the frozen witness library for each family, reproduced by
# verification/reference_solver.py with restarts=240 and seed 0 (the command is in
# references/known_best.md). The trivial floor — any two compatible words — anchors
# zero, so progress is (size - floor) / (witness - floor) and larger libraries score
# above one.
WITNESS_SIZE = {"dna16": 32, "dna12": 29}
TRIVIAL_SIZE = {"dna16": 2, "dna12": 2}


def problem_statement():
    return {
        "families": [dict(row) for row in FAMILIES],
        "alphabet": ["A", "C", "G", "T"],
        "scoring": "per family score = library_size / witness_size, averaged; larger libraries score above one",
        "verification_note": (
            "a library is valid when every word meets the family constraints and every "
            "pair (including a word with itself) meets the Hamming and cross-dimer "
            "caps; cross-dimer pairs are Watson-Crick matches over all shifted "
            "alignments of a word against the reverse complement of the other"
        ),
    }


def _encode(words):
    rows = []
    for word in words:
        rows.append([BASE_CODES[base] for base in word])
    return np.asarray(rows, dtype=np.int8)


def _homopolymer_ok(codes, cap):
    if codes.shape[1] == 0:
        return True
    changes = np.diff(codes, axis=1) != 0
    longest = np.ones(len(codes), dtype=np.int64)
    current = np.ones(len(codes), dtype=np.int64)
    for column in range(codes.shape[1] - 1):
        current = np.where(changes[:, column], 1, current + 1)
        longest = np.maximum(longest, current)
    return longest <= cap


def _min_hamming_matrix(codes):
    return (codes[:, None, :] != codes[None, :, :]).sum(axis=2)


def _max_crossdimer_matrix(codes):
    """Watson-Crick complementary pairs over all shifted alignments.

    For every pair (i, j) — including i == j — slide the reverse complement of word j
    along word i at every offset and count complementary matches (code sum 3); the
    reported number is the maximum over offsets. Offsets with zero overlap are
    excluded, so identical non-palindromic single words still pass unless they dimer.
    """
    n, length = codes.shape
    reverse_complement = (3 - codes)[:, ::-1]
    best = np.zeros((n, n), dtype=np.int64)
    for offset in range(-(length - 1), length):
        if offset >= 0:
            left = codes[:, offset:]
            right = reverse_complement[:, :length - offset] if offset else reverse_complement
        else:
            left = codes[:, :length + offset]
            right = reverse_complement[:, -offset:]
        overlap = left.shape[1]
        if overlap == 0:
            continue
        matches = (left[:, None, :] + right[None, :, :] == 3).sum(axis=2)
        np.maximum(best, matches, out=best)
    return best


def check_library(family, words):
    """Return (ok, reason). Pure verification, independent of construction."""
    if not isinstance(words, (list, tuple)) or len(words) < 2:
        return False, "library must list at least two words"
    if len(words) > family["max_library"]:
        return False, "library exceeds the verification cap"
    length = family["length"]
    for word in words:
        if not isinstance(word, str) or len(word) != length:
            return False, "every word must be a string of length %d" % length
        if any(base not in BASE_CODES for base in word):
            return False, "words may only contain A, C, G, T"
    codes = _encode(words)
    if len(set(tuple(row) for row in codes.tolist())) != len(words):
        return False, "words must be unique"
    gc = (codes == 1).sum(axis=1) + (codes == 2).sum(axis=1)
    if np.any(gc != family["gc_count"]):
        return False, "every word must hold exactly %d G/C bases" % family["gc_count"]
    if not np.all(_homopolymer_ok(codes, family["max_homopolymer"])):
        return False, "homopolymer runs exceed the cap"
    hamming = _min_hamming_matrix(codes)
    np.fill_diagonal(hamming, 1 << 30)  # a word is not a pair with itself
    if np.any(hamming < family["min_hamming"]):
        return False, "a word pair violates the Hamming floor"
    crossdimer = _max_crossdimer_matrix(codes)
    if np.any(crossdimer > family["max_crossdimer"]):
        return False, "a word pair exceeds the cross-dimer cap"
    return True, ""


def evaluate(build_codeword_library):
    submissions = []
    try:
        submissions = build_codeword_library(problem_statement())
    except Exception:
        submissions = None
    rows, scores = [], []
    valid_all = submissions is not None
    for family in FAMILIES:
        row = {"family": family["family"], "valid": False, "size": 0, "score": 0.0,
               "reason": ""}
        try:
            words = submissions[family["family"]] if isinstance(submissions, dict) else None
            if words is None:
                row["reason"] = "missing family artifact"
            else:
                ok, reason = check_library(family, words)
                if ok:
                    size = len(words)
                    floor = TRIVIAL_SIZE[family["family"]]
                    witness = WITNESS_SIZE[family["family"]]
                    span = max(witness - floor, 1)
                    row.update({"valid": True, "size": size,
                                "score": float(max(0.0, (size - floor) / span))})
                else:
                    row["reason"] = reason
        except Exception as exc:
            row["reason"] = "%s: %s" % (type(exc).__name__, exc)
            valid_all = False
        if not row["valid"]:
            valid_all = False
        rows.append(row)
        scores.append(row["score"])
    return {
        "combined_score": float(np.mean(scores)) if valid_all else 0.0,
        "valid": 1.0 if valid_all else 0.0,
        "feasibility_rate": (1.0 if valid_all else 0.0),
        "family_sizes": {row["family"]: row["size"] for row in rows},
        "per_family": rows,
        "raw_score": float(np.mean(scores)) if valid_all else 0.0,
    }

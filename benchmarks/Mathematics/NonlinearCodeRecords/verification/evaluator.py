"""Hidden oracle for NonlinearCodeRecords.

`A(n, d)` is the largest number of binary words of length `n` that pairwise differ in at least `d`
positions. It is unknown for most `(n, d)`, and the published lower bounds are held by *nonlinear*
codes. That is the whole task: linear codes are what a parity-check construction gives you in a
second, and at these parameters they stop a factor of one and a half to two short of the record.

    A(23, 10)   linear reaches 64, the published code has 80
    A(24, 10)   linear reaches 64, the published code has 136
    A(25, 10)   linear reaches 128, the published code has 192
    A(26, 10)   linear reaches 256, the published code has 384

Verification is counting: the submission is a list of words, and the oracle checks that they are
distinct, binary, of the right length, and pairwise at distance at least `d`. Nothing about how a
code was found matters, and nothing but its size is scored. The score is uncapped - the published
record is the witness worth 1, not a ceiling - because these cells are open.

**Why the upper half of the sandwich is not here.** An earlier version of this task also asked for
a Delsarte linear-programming certificate to bound A(n, d) from above, on the theory that a
construction plus a proof of near-optimality is the shape of a real result. Measuring it killed it:
the Delsarte bound computed by a fifty-line linear program lands at 151.9 against a published upper
bound of 150 for A(23, 10), at 6553.6 against 6552 for A(18, 4), and at 13107.2 against 13104 for
A(19, 4). For binary codes the published upper bound essentially *is* the linear program, so the
certificate half would have measured whether a candidate can call `scipy.optimize.linprog`. The
finding is recorded in references/known_best.md; a certificate task needs a cell where the standard
relaxation is not already tight.
"""
from __future__ import annotations

import math

import numpy as np

# Published sandwiches, from Brouwer's table of bounds on A(n,d) (aeb.win.tue.nl/codes/binary-1.html,
# retrieved 2026-09-04). Every one of these four is an open gap - lower and upper disagree - which
# is what makes the cell worth a task. The values are recorded in references/anchors.json with
# their source, and the freshness checker will ask for them to be re-derived.
INSTANCES = (
    {"n": 23, "d": 10, "published_lower": 80, "published_upper": 150},
    {"n": 24, "d": 10, "published_lower": 136, "published_upper": 268},
    {"n": 25, "d": 10, "published_lower": 192, "published_upper": 466},
    {"n": 26, "d": 10, "published_lower": 384, "published_upper": 836},
)

MAX_CODEWORDS = 40000
CERTIFICATE_TOLERANCE = 1e-9


def _pack(words: np.ndarray) -> np.ndarray:
    """Pack 0/1 rows into uint64 columns so distances are popcounts of XORs."""
    padded = np.zeros((words.shape[0], 64 * ((words.shape[1] + 63) // 64)), dtype=np.uint8)
    padded[:, : words.shape[1]] = words
    return np.packbits(padded, axis=1).view(np.uint64)


_POPCOUNT8 = np.array([bin(i).count("1") for i in range(256)], dtype=np.uint16)


def _min_distance(words: np.ndarray, chunk: int = 512) -> int:
    """Smallest pairwise Hamming distance, by chunked XOR and byte-table popcount."""
    packed = _pack(words).view(np.uint8)
    count = packed.shape[0]
    best = words.shape[1] + 1
    for start in range(0, count, chunk):
        block = packed[start : start + chunk]
        # Only the upper triangle is needed, but comparing each block against everything after it
        # keeps the loop simple and still halves the work.
        other = packed[start:]
        xor = block[:, None, :] ^ other[None, :, :]
        distances = _POPCOUNT8[xor].sum(axis=2)
        rows, cols = np.triu_indices(block.shape[0], k=1, m=other.shape[0])
        offset = np.arange(block.shape[0])[:, None] < np.arange(other.shape[0])[None, :]
        masked = np.where(offset, distances, words.shape[1] + 1)
        if masked.size:
            best = min(best, int(masked.min()))
        if start + chunk < count:
            cross = distances[:, block.shape[0] :]
            if cross.size:
                best = min(best, int(cross.min()))
    return best


def _validate_code(value, n: int, d: int):
    """Read a claimed code. Anything malformed is a candidate failure, never an oracle one."""
    if value is None:
        return None, "no code submitted"
    array = np.asarray(value)
    if array.dtype == object or array.ndim != 2:
        return None, "code must be a rectangular array of 0/1 rows"
    if array.shape[0] == 0:
        return None, "code is empty"
    if array.shape[0] > MAX_CODEWORDS:
        return None, "code exceeds %d codewords" % MAX_CODEWORDS
    if array.shape[1] != n:
        return None, "codewords must have length %d" % n
    if not np.all(np.isin(array, (0, 1))):
        return None, "codewords must be binary"
    words = array.astype(np.uint8)
    if len(np.unique(words, axis=0)) != words.shape[0]:
        return None, "codewords must be distinct"
    minimum = _min_distance(words)
    if minimum < d:
        return None, "minimum distance is %d, below %d" % (minimum, d)
    return int(words.shape[0]), None


def _trivial_size(n: int, d: int) -> float:
    """Where the scale starts: split the coordinates into blocks of d and repeat one bit in each.

    The crudest construction that still guarantees the distance, and the thing the delivered
    baseline submits. The reference - the largest *linear* code - sits about two thirds of the way
    from here to the published record, and the last third is where linearity has to be given up.
    """
    return float(2 ** (n // d))


PUBLIC_PROBLEM = {
    "instances": [
        {"n": row["n"], "distance": row["d"],
         "trivial_construction_size": int(_trivial_size(row["n"], row["d"])),
         "published_upper_bound": row["published_upper"]}
        for row in INSTANCES
    ],
    "max_codewords": MAX_CODEWORDS,
    "code_contract": "a list of distinct binary rows of length n, pairwise Hamming distance at "
                     "least distance; its size is a lower bound on A(n, distance)",
    "scoring": "zero is the block-repetition construction, one is the published record, and the "
               "scale is uncapped. The largest linear code sits about two thirds of the way up; "
               "the published records at these parameters are held by nonlinear codes",
}


def _instance_score(row, size):
    """Progress from the trivial construction to the published record. Uncapped above."""
    anchor = _trivial_size(row["n"], row["d"])
    published = float(row["published_lower"])
    if size is None:
        return 0.0
    return (float(size) - anchor) / (published - anchor)


def evaluate(build_code):
    rows = []
    for index, row in enumerate(INSTANCES):
        n, d = row["n"], row["d"]
        anchor = _trivial_size(n, d)
        record = {"instance_index": index, "n": n, "distance": d,
                  "published_lower": row["published_lower"],
                  "published_upper": row["published_upper"],
                  "trivial_construction_size": int(anchor)}
        try:
            size, error = _validate_code(build_code(n, d), n, d)
            if size is None:
                raise ValueError(error)
            score = _instance_score(row, size)
            record.update({
                "valid": True, "code_size": size, "instance_score": round(score, 6),
                "beats_the_trivial_construction": bool(size > anchor),
                "beats_the_published_record": bool(size > row["published_lower"]),
            })
        except Exception as exc:  # noqa: BLE001 - a bad candidate scores zero, it does not crash this
            record.update({
                "valid": False, "reason": "%s: %s" % (type(exc).__name__, exc),
                "code_size": None, "instance_score": 0.0,
                "beats_the_trivial_construction": False, "beats_the_published_record": False,
            })
        rows.append(record)

    valid = [r for r in rows if r["valid"]]
    combined = float(np.mean([r["instance_score"] for r in rows]))
    return {
        "combined_score": combined,
        "valid": 1.0 if valid else 0.0,
        "feasibility_rate": len(valid) / len(rows),
        "raw_score": combined,
        "instances_with_a_valid_code": len(valid),
        "instances_beating_the_trivial_construction": sum(
            1 for r in rows if r["beats_the_trivial_construction"]),
        "instances_beating_the_published_record": sum(
            1 for r in rows if r["beats_the_published_record"]),
        "mean_code_size": float(np.mean([r["code_size"] or 0 for r in rows])),
        "per_instance": rows,
    }

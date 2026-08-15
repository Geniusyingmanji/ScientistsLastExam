"""RNA inverse folding scored by ensemble defect, against ViennaRNA's own designer.

The science. Inverse folding asks for a sequence whose secondary structure is a given target.
The usual pass/fail form - does the minimum-free-energy structure equal the target - ignores that
a sequence folds into a Boltzmann ensemble, not a single shape. Ensemble defect, the expected
number of nucleotides paired differently from the target over that ensemble, is the measure a
designer actually cares about, and it is what NUPACK-style design optimises.

The oracle is ViennaRNA, the community standard for this thermodynamics, so a score here measures
agreement with the Turner nearest-neighbour model rather than with a private reimplementation.

The anchor is ViennaRNA's `inverse_pf_fold`, the routine that maximises the target's probability
under the partition function, run by the evaluator on the same targets at scoring time and kept as
the best of ANCHOR_RESTARTS restarts by ensemble defect. It is the community routine written for
this objective, so reaching 1.0 means matching what the field already does rather than clearing a
bar chosen to be clearable.

An earlier version anchored on `inverse_fold`, which searches for MFE structure match. Measured on
these targets that is about 75x worse on ensemble defect, and a twelve-proposal search cleared it
four times over. Anchoring on the routine that optimises a different objective was setting the bar
by accident.

Candidates may call either routine themselves. An earlier draft forbade it, which the harness
cannot enforce - the oracle sees a returned sequence, not how it was produced - and making the
anchor a best-of-restarts removes the need.

    score = log(defect_baseline / defect_candidate) / log(defect_baseline / defect_anchor)

with the baseline a fixed unstructured sequence. Matching ViennaRNA's designer scores 1.0;
beating it scores above 1.0; doing no better than an unstructured sequence scores 0.

The ratio is taken in logs for the same reason the surface-code task takes one: the baseline
defect is near 0.75 and the anchor near 0.03, so a linear normalisation spends almost its whole
range on the gap between "did nothing" and "reached the reference", and compresses the region
above 1.0 where the actual work happens. On a linear scale, halving the defect below the anchor
is worth about 0.03; in logs it is worth about 0.2.
"""

from __future__ import annotations

import hashlib
import random

# Difficulty selects the target set. Level 1 is the shipped configuration. Targets are generated
# from motif grammars rather than written by hand, so a level is reproducible and a harder level
# is a real change of regime rather than a longer list of the same thing.
DIFFICULTY = 1

# Difficulty is the anchor's own ensemble defect band, not a hand-tuned bulge rate. Targets are
# drawn from the grammar and kept only if ViennaRNA can design them at all and if its best of ten
# restarts lands inside the band. A higher level asks for targets its own designer handles worse.
_LADDER = {
    1: {"branch_counts": (2, 3), "stem": (3, 6), "loop": (4, 7), "bulge_rate": 0.12,
        "anchor_defect_band": (0.0008, 0.004), "designability_restarts": 4,
        "count": 5, "max_draws": 120, "seed": 20260811},
    2: {"branch_counts": (3, 4), "stem": (3, 5), "loop": (4, 8), "bulge_rate": 0.18,
        "anchor_defect_band": (0.002, 0.010), "designability_restarts": 6,
        "count": 5, "max_draws": 200, "seed": 20260812},
    3: {"branch_counts": (4, 5), "stem": (3, 5), "loop": (4, 9), "bulge_rate": 0.22,
        "anchor_defect_band": (0.004, 0.020), "designability_restarts": 8,
        "count": 5, "max_draws": 300, "seed": 20260813},
}

_SEALED_LADDER = {
    1: {"branch_counts": (2, 3), "stem": (3, 6), "loop": (5, 8), "bulge_rate": 0.12,
        "anchor_defect_band": (0.0008, 0.004), "designability_restarts": 4,
        "count": 3, "max_draws": 120, "seed": 771201},
    2: {"branch_counts": (3, 4), "stem": (3, 5), "loop": (5, 9), "bulge_rate": 0.18,
        "anchor_defect_band": (0.002, 0.010), "designability_restarts": 6,
        "count": 3, "max_draws": 200, "seed": 771202},
    3: {"branch_counts": (4, 5), "stem": (3, 5), "loop": (5, 10), "bulge_rate": 0.22,
        "anchor_defect_band": (0.004, 0.020), "designability_restarts": 8,
        "count": 3, "max_draws": 300, "seed": 771203},
}

# `inverse_pf_fold` maximises the probability of the target under the partition function, which is
# the objective this task scores. `inverse_fold` searches for MFE structure match instead, and
# measured on this task's own targets it is about 75x worse on ensemble defect - median 0.108
# against 0.00145 - so anchoring on it would set a bar a twelve-proposal search clears four times
# over. The partition-function routine is also far more consistent across restarts, which is why
# three suffice where the MFE routine needed ten.
ANCHOR_RESTARTS = 3

BASELINE_BASE = "A"
ALPHABET = "ACGU"
MAX_LENGTH = 400


def _helix(rng, length, bulge_rate):
    """One side of a helix, with occasional single-nucleotide bulges.

    A bulge breaks a helix into stacks that must each be stabilised separately, and it makes the
    competing register - the same helix slipped by one - close in energy. Without them a helix is
    filled with GC pairs and the design problem largely disappears, which is what happened at the
    first shipped level: a twelve-proposal search drove the ensemble defect to 0.001.
    """
    left, right = [], []
    for _ in range(length):
        left.append("(")
        right.append(")")
        if bulge_rate and rng.random() < bulge_rate:
            left.append(".")
    return "".join(left), "".join(reversed(right))


def _hairpin(rng, stem, loop, bulge_rate=0.0):
    length = rng.randint(*stem)
    left, right = _helix(rng, length, bulge_rate)
    return left + "." * rng.randint(*loop) + right


def _target(rng, branches, stem, loop, bulge_rate):
    """A closing stem enclosing `branches` hairpins, with short unpaired spacers between them.

    Built by construction rather than written out, because a hand-typed dot-bracket string is
    easy to get wrong - the first draft of this task had an unbalanced target that ViennaRNA
    rejected outright and that scored -1.0 without failing.
    """
    inner = []
    for index in range(branches):
        if index:
            inner.append("." * rng.randint(1, 3))
        inner.append(_hairpin(rng, stem, loop, bulge_rate))
    left, right = _helix(rng, rng.randint(*stem), bulge_rate)
    return left + "".join(inner) + right


def _seed_rna(RNA, *parts) -> None:
    """Pin ViennaRNA's own RNG before a call that draws from it.

    `inverse_fold` and `inverse_pf_fold` start from a *random* sequence when handed `None`, drawn
    from a process-global generator inside ViennaRNA that Python's `random.Random` does not reach.
    Two consequences, and the second is the one that matters. Anchor defects wander by about 1e-4
    between runs, which is merely noise; but a target whose anchor sits near the edge of the
    acceptance band flips in and out of the set, so *which instances exist* changes between runs
    and two scores stop being comparable at all. That is how this task came back non-deterministic
    on the 43-task baseline sweep while reproducing perfectly when re-run by hand: the fifth
    development target was a different target.

    Seeding per call, from the call's own inputs, rather than once at import: the candidate is
    arbitrary code and may draw from this same generator before the evaluator does, which would
    otherwise shift every draw after it.
    """
    digest = hashlib.sha256("|".join(str(part) for part in parts).encode("utf-8")).digest()
    RNA.init_rand(int.from_bytes(digest[:4], "big"))


def _designable(RNA, structure, restarts):
    """Does any sequence fold into this structure as its MFE?

    Not every dot-bracket string is designable. Scoring an undesignable target measures how close
    a candidate gets to something impossible, and the anchor there is arbitrary rather than a
    reference. A first version of this task tuned bulge density by hand and produced target sets
    where ViennaRNA's own designer reached the target on none of them; filtering for designability
    replaces that guesswork with a property.
    """
    for restart in range(restarts):
        _seed_rna(RNA, "designable", structure, restart)
        sequence, distance = RNA.inverse_fold(None, structure)
        if distance == 0 and RNA.fold(sequence)[0] == structure:
            return True
    return False


def _generate(profile):
    """Draw structures from the motif grammar and keep the designable, non-trivial ones.

    Two filters. Designability makes the target reachable at all. The defect band keeps targets
    that are neither solved by the reference designer on sight nor hopeless: a target whose anchor
    already sits near zero cannot show a searcher doing better, which is what retired the first
    shipped level after a twelve-proposal search drove its defects to 0.001.
    """
    RNA = _rna()
    rng = random.Random(profile["seed"])
    low, high = profile["anchor_defect_band"]
    out, examined = [], 0
    while len(out) < profile["count"] and examined < profile["max_draws"]:
        examined += 1
        branches = profile["branch_counts"][examined % len(profile["branch_counts"])]
        structure = _target(rng, branches, profile["stem"], profile["loop"],
                            profile["bulge_rate"])
        if not balanced(structure) or len(structure) > MAX_LENGTH:
            continue
        if not _designable(RNA, structure, profile["designability_restarts"]):
            continue
        best = min(
            ensemble_defect(RNA, _pf_design(RNA, structure, restart), structure)
            for restart in range(ANCHOR_RESTARTS)
        )
        if not (low <= best <= high):
            continue
        out.append({"key": "t%d_b%d_n%d" % (len(out), branches, len(structure)),
                    "structure": structure})
    if len(out) < profile["count"]:
        raise ValueError(
            "only %d of %d targets met the designability and defect band in %d draws"
            % (len(out), profile["count"], examined)
        )
    return tuple(out)


def _profile(ladder, level):
    level = int(level)
    if level not in ladder:
        raise ValueError(
            "difficulty %d has no entry; add one and record its anchor defects before use"
            % level
        )
    return ladder[level]


def development_targets():
    """Built on first use: generation now folds candidate structures, so it cannot run at import."""
    if "dev_targets" not in _CACHE:
        _CACHE["dev_targets"] = _generate(_profile(_LADDER, DIFFICULTY))
    return _CACHE["dev_targets"]


def sealed_targets():
    if "sealed_targets" not in _CACHE:
        _CACHE["sealed_targets"] = _generate(_profile(_SEALED_LADDER, DIFFICULTY))
    return _CACHE["sealed_targets"]

_CACHE: dict = {}


def _rna():
    import RNA

    return RNA


def balanced(structure: str) -> bool:
    depth = 0
    for character in structure:
        if character == "(":
            depth += 1
        elif character == ")":
            depth -= 1
            if depth < 0:
                return False
        elif character != ".":
            return False
    return depth == 0


def ensemble_defect(RNA, sequence: str, structure: str) -> float:
    """Expected number of misplaced nucleotides over the Boltzmann ensemble, per nucleotide."""
    fold_compound = RNA.fold_compound(sequence)
    fold_compound.pf()
    return float(fold_compound.ensemble_defect(structure))


def _pf_design(RNA, structure: str, restart: int = 0) -> str:
    """ViennaRNA's partition-function designer, returning the sequence it settles on.

    The structure must be balanced before this is called. ViennaRNA segfaults on an unbalanced
    dot-bracket string rather than raising, so a malformed target takes the whole evaluator down
    with no diagnostic - which is what a hand-typed target did during development.
    """
    if not balanced(structure):
        raise ValueError("refusing to hand an unbalanced structure to ViennaRNA")
    _seed_rna(RNA, "pf_design", structure, restart)
    result = RNA.inverse_pf_fold(None, structure)
    return result[0] if isinstance(result, (tuple, list)) else result


def _anchors(RNA, targets, tag):
    """Baseline and ViennaRNA-designer defects, recomputed here rather than quoted."""
    key = "anchors::%s::%s" % (tag, tuple(t["structure"] for t in targets))
    if key in _CACHE:
        return _CACHE[key]
    rows = {}
    for target in targets:
        structure = target["structure"]
        if not balanced(structure):
            raise ValueError("generated target %s is not balanced" % target["key"])
        baseline_sequence = BASELINE_BASE * len(structure)
        best_sequence, best_defect = None, float("inf")
        for _restart in range(ANCHOR_RESTARTS):
            designed = _pf_design(RNA, structure, _restart)
            defect = ensemble_defect(RNA, designed, structure)
            if defect < best_defect:
                best_sequence, best_defect = designed, defect
        rows[target["key"]] = {
            "baseline_defect": ensemble_defect(RNA, baseline_sequence, structure),
            "anchor_defect": best_defect,
            "anchor_sequence": best_sequence,
            "anchor_restarts": ANCHOR_RESTARTS,
            "anchor_reaches_target": RNA.fold(best_sequence)[0] == structure,
        }
    _CACHE[key] = rows
    return rows


# A perfectly designed sequence can have a defect at the numerical floor, where a log is
# undefined. The floor exists only to keep the logarithm finite and must sit far below anything a
# search reaches: at 1e-3 it silently capped the score at about 2.06, and a twelve-proposal search
# was pressing against it on four of six targets.
DEFECT_FLOOR = 1e-6


def _log_ratio_score(defect: float, baseline: float, anchor: float) -> float:
    """Log-ratio reduction in ensemble defect, 0 at the baseline and 1 at the anchor."""
    import math

    defect = max(float(defect), DEFECT_FLOOR)
    baseline = max(float(baseline), DEFECT_FLOOR)
    anchor = max(float(anchor), DEFECT_FLOOR)
    span = math.log(baseline / anchor)
    if span <= 1e-9:
        return 0.0
    return max(0.0, math.log(baseline / defect) / span)


def _clean(submission, length):
    if not isinstance(submission, str):
        return None, "expected a sequence string, got %s" % type(submission).__name__
    sequence = submission.strip().upper().replace("T", "U")
    if len(sequence) != length:
        return None, "expected length %d, got %d" % (length, len(sequence))
    bad = sorted({c for c in sequence} - set(ALPHABET))
    if bad:
        return None, "characters outside ACGU: %s" % bad
    return sequence, ""


def _score_split(RNA, design_rna, targets, tag):
    anchors = _anchors(RNA, targets, tag)
    per_target = []
    scores = []
    for target in targets:
        structure = target["structure"]
        row = anchors[target["key"]]
        try:
            raw = design_rna(structure)
        except Exception as exc:  # noqa: BLE001 - candidate faults are scored, not raised
            per_target.append({"key": target["key"], "valid": False,
                               "reason": "raised: %s" % type(exc).__name__})
            scores.append(0.0)
            continue
        sequence, why = _clean(raw, len(structure))
        if sequence is None:
            per_target.append({"key": target["key"], "valid": False, "reason": why})
            scores.append(0.0)
            continue
        defect = ensemble_defect(RNA, sequence, structure)
        score = _log_ratio_score(defect, row["baseline_defect"], row["anchor_defect"])
        scores.append(score)
        per_target.append({
            "key": target["key"],
            "valid": True,
            "length": len(structure),
            "ensemble_defect": defect,
            "baseline_defect": row["baseline_defect"],
            "anchor_defect": row["anchor_defect"],
            "anchor_reaches_target": row["anchor_reaches_target"],
            "mfe_matches_target": RNA.fold(sequence)[0] == structure,
            "score": score,
        })
    valid = [row for row in per_target if row["valid"]]
    return {
        "score": sum(scores) / len(scores) if scores else 0.0,
        "valid_count": len(valid),
        "target_count": len(targets),
        "mfe_match_rate": (
            sum(1 for row in valid if row["mfe_matches_target"]) / len(valid)
            if valid else 0.0
        ),
        "per_target": per_target,
    }


def evaluate(design_rna) -> dict:
    RNA = _rna()
    development = _score_split(RNA, design_rna, development_targets(), "dev")
    valid = development["valid_count"] == development["target_count"]
    result = {
        "combined_score": float(development["score"]) if valid else 0.0,
        "valid": 1.0 if valid else 0.0,
        "development_score": float(development["score"]),
        "development_valid_count": development["valid_count"],
        "development_mfe_match_rate": development["mfe_match_rate"],
        "per_instance": development["per_target"],
        "difficulty": DIFFICULTY,
    }
    if valid:
        sealed = _score_split(RNA, design_rna, sealed_targets(), "sealed")
        result["robustness_score"] = float(sealed["score"])
        result["sealed_mfe_match_rate"] = sealed["mfe_match_rate"]
        result["sealed_per_instance"] = sealed["per_target"]
    else:
        result["robustness_score"] = 0.0
    return result

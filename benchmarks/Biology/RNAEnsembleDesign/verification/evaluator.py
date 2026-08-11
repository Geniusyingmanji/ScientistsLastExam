"""RNA inverse folding scored by ensemble defect, against ViennaRNA's own designer.

The science. Inverse folding asks for a sequence whose secondary structure is a given target.
The usual pass/fail form - does the minimum-free-energy structure equal the target - ignores that
a sequence folds into a Boltzmann ensemble, not a single shape. Ensemble defect, the expected
number of nucleotides paired differently from the target over that ensemble, is the measure a
designer actually cares about, and it is what NUPACK-style design optimises.

The oracle is ViennaRNA, the community standard for this thermodynamics, so a score here measures
agreement with the Turner nearest-neighbour model rather than with a private reimplementation.

The anchor is ViennaRNA's own `inverse_fold`, run by the evaluator on the same targets at scoring
time and kept as the best of ANCHOR_RESTARTS restarts by ensemble defect. That routine optimises
MFE structure match, not ensemble defect, so it is a real reference rather than an upper bound:
on the harder targets here it does not even reach the target structure. Beating it on ensemble
defect is the point, and the score is uncapped so that beating it is visible.

Candidates may call `inverse_fold` themselves. An earlier draft forbade it, which was a rule the
harness cannot enforce - the oracle sees a returned sequence, not how it was produced. Making the
anchor a best-of-restarts removes the need: a candidate that simply calls the routine once
reaches parity and no more, and one that restarts it is doing what the anchor already does.

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

import random

# Difficulty selects the target set. Level 1 is the shipped configuration. Targets are generated
# from motif grammars rather than written by hand, so a level is reproducible and a harder level
# is a real change of regime rather than a longer list of the same thing.
DIFFICULTY = 1

_LADDER = {
    1: {"branch_counts": (1, 2, 3), "stem": (4, 7), "loop": (4, 7), "count": 6, "seed": 20260811},
    2: {"branch_counts": (2, 3, 4), "stem": (5, 9), "loop": (4, 8), "count": 6, "seed": 20260812},
    3: {"branch_counts": (3, 4, 5), "stem": (6, 11), "loop": (4, 9), "count": 6, "seed": 20260813},
}

_SEALED_LADDER = {
    1: {"branch_counts": (2, 3), "stem": (5, 8), "loop": (5, 8), "count": 3, "seed": 771201},
    2: {"branch_counts": (3, 4), "stem": (6, 10), "loop": (5, 9), "count": 3, "seed": 771202},
    3: {"branch_counts": (4, 5), "stem": (7, 12), "loop": (5, 10), "count": 3, "seed": 771203},
}

# The anchor restarts the reference designer and keeps its best attempt by ensemble defect, so
# that a candidate cannot beat it merely by restarting it more times than the evaluator did.
ANCHOR_RESTARTS = 10

BASELINE_BASE = "A"
ALPHABET = "ACGU"
MAX_LENGTH = 400


def _hairpin(rng, stem, loop):
    s = rng.randint(*stem)
    l = rng.randint(*loop)
    return "(" * s + "." * l + ")" * s


def _target(rng, branches, stem, loop):
    """A closing stem enclosing `branches` hairpins, with short unpaired spacers between them.

    Built by construction rather than written out, because a hand-typed dot-bracket string is
    easy to get wrong - the first draft of this task had an unbalanced target that ViennaRNA
    rejected outright and that scored -1.0 without failing.
    """
    inner = []
    for index in range(branches):
        if index:
            inner.append("." * rng.randint(1, 3))
        inner.append(_hairpin(rng, stem, loop))
    closing = rng.randint(*stem)
    return "(" * closing + "".join(inner) + ")" * closing


def _generate(profile):
    rng = random.Random(profile["seed"])
    out = []
    for index in range(profile["count"]):
        branches = profile["branch_counts"][index % len(profile["branch_counts"])]
        structure = _target(rng, branches, profile["stem"], profile["loop"])
        out.append({"key": "t%d_b%d_n%d" % (index, branches, len(structure)),
                    "structure": structure})
    return tuple(out)


def _profile(ladder, level):
    level = int(level)
    if level not in ladder:
        raise ValueError(
            "difficulty %d has no entry; add one and record its anchor defects before use"
            % level
        )
    return ladder[level]


DEVELOPMENT_TARGETS = _generate(_profile(_LADDER, DIFFICULTY))
SEALED_TARGETS = _generate(_profile(_SEALED_LADDER, DIFFICULTY))

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
            designed, _distance = RNA.inverse_fold(None, structure)
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
# undefined. The floor is one thousandth of a nucleotide, far below anything the thermodynamic
# model resolves, and it caps the score rather than letting it run away.
DEFECT_FLOOR = 1e-3


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
    development = _score_split(RNA, design_rna, DEVELOPMENT_TARGETS, "dev")
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
        sealed = _score_split(RNA, design_rna, SEALED_TARGETS, "sealed")
        result["robustness_score"] = float(sealed["score"])
        result["sealed_mfe_match_rate"] = sealed["mfe_match_rate"]
        result["sealed_per_instance"] = sealed["per_target"]
    else:
        result["robustness_score"] = 0.0
    return result

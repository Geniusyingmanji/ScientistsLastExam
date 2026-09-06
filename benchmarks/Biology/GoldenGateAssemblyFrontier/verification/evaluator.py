"""Deterministic oracle for data-guided Golden Gate assembly design.

The ligation counts are a lossless sparse extraction from Pryor et al. (2020) Tables S1--S4.
Rows are 5' overhangs and columns are possible ligation partners.  For a chosen overhang ``s``,
the Watson--Crick partner is ``reverse_complement(s)``.  The fidelity calculation below is an
independent implementation of equations 1--2 in the paper; no OMEGA source code is used.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
import random
from functools import cache, lru_cache
from pathlib import Path

OVERHANG_LENGTH = 4
DNA = frozenset("ACGT")
DATA_PATH = (
    Path(__file__).resolve().parents[1] / "data" / "pryor_ligation_counts_v1.json"
)
DATA_SHA256 = "2ec0191f2ca3a8c87c5a63f8080dc03876e29965aa06e7b3faf0cb2820e7dfb5"
ENZYME_RECOGNITION_SITES = {
    "BsaI-HFv2": "GGTCTC",
    "BsmBI-v2": "CGTCTC",
    "Esp3I": "CGTCTC",
    "BbsI-HF": "GAAGAC",
}

_DEVELOPMENT_PROFILES = (
    {
        "id": "dev_a",
        "seed": 2026090601,
        "length": 2860,
        "fragment_count": 16,
        "fragment_length_bounds": (140, 230),
        "blocked_sites": ("GGTCTC",),
    },
    {
        "id": "dev_b",
        "seed": 2026090602,
        "length": 3220,
        "fragment_count": 16,
        "fragment_length_bounds": (165, 250),
        "blocked_sites": ("CGTCTC",),
    },
    {
        "id": "dev_c",
        "seed": 2026090603,
        "length": 2500,
        "fragment_count": 14,
        "fragment_length_bounds": (140, 230),
        "blocked_sites": ("GAAGAC",),
    },
)
_HELDOUT_PROFILES = (
    {
        "id": "heldout_a",
        "seed": 2026090691,
        "length": 3040,
        "fragment_count": 17,
        "fragment_length_bounds": (140, 225),
        "blocked_sites": ("GGTCTC", "GAAGAC"),
    },
    {
        "id": "heldout_b",
        "seed": 2026090692,
        "length": 3400,
        "fragment_count": 17,
        "fragment_length_bounds": (160, 245),
        "blocked_sites": ("CGTCTC",),
    },
)


def reverse_complement(sequence: str) -> str:
    return sequence.translate(str.maketrans("ACGT", "TGCA"))[::-1]


def canonical_overhang(sequence: str) -> str:
    return min(sequence, reverse_complement(sequence))


@lru_cache(maxsize=1)
def _source_data() -> dict:
    payload = DATA_PATH.read_bytes()
    if hashlib.sha256(payload).hexdigest() != DATA_SHA256:
        raise RuntimeError("frozen Pryor ligation-count data hash differs")
    return json.loads(payload)


def _contains_site(sequence: str, site: str) -> bool:
    return site in sequence or reverse_complement(site) in sequence


def _target(profile: dict) -> str:
    """Create one noncoding synthetic target with exactly the requested blocked site families."""
    blocked = set(profile["blocked_sites"])
    all_sites = set(ENZYME_RECOGNITION_SITES.values())
    for attempt in range(100):
        rng = random.Random(profile["seed"] + attempt * 1009)
        letters = [rng.choice("ACGT") for _ in range(profile["length"])]
        for index, site in enumerate(sorted(blocked)):
            position = (index + 1) * profile["length"] // (len(blocked) + 1)
            letters[position : position + len(site)] = site
        target = "".join(letters)
        observed = {site for site in all_sites if _contains_site(target, site)}
        if observed == blocked:
            return target
    raise RuntimeError("could not construct the frozen restriction-site panel")


def _public_problem(profile: dict) -> dict:
    source = _source_data()
    return {
        "instance_id": profile["id"],
        "target_sequence": _target(profile),
        "fragment_count": profile["fragment_count"],
        "fragment_length_bounds": list(profile["fragment_length_bounds"]),
        "overhang_length": OVERHANG_LENGTH,
        "canonical_overhangs": list(source["canonical_overhangs"]),
        "conditions": {
            name: {
                "recognition_site": ENZYME_RECOGNITION_SITES[name],
                "ligation_counts": dict(row["counts"]),
                "source_supplement": row["supplement"],
            }
            for name, row in source["conditions"].items()
        },
        "fidelity_definition": (
            "Pryor equations 1-2: multiply per-junction probabilities; each numerator is the "
            "two directional Watson-Crick counts and each denominator contains ligations from "
            "both orientations to every selected overhang and its reverse complement"
        ),
        "artifact_contract": (
            "choose one condition and return fragment_count target substrings whose adjacent "
            "four-base overlaps exactly reconstruct target_sequence"
        ),
    }


def _count(counts: dict[str, int], left: str, right: str) -> int:
    return int(counts.get(f"{left}>{right}", 0))


def site_probability(site: str, sites: list[str], counts: dict[str, int]) -> float:
    complement = reverse_complement(site)
    ends = sites + [reverse_complement(other) for other in sites]
    correct = _count(counts, site, complement) + _count(counts, complement, site)
    total = sum(_count(counts, site, other) for other in ends)
    total += sum(_count(counts, complement, other) for other in ends)
    if correct <= 0 or total < correct:
        return 0.0
    return correct / total


def log_fidelity(sites: list[str], counts: dict[str, int]) -> float:
    probabilities = [site_probability(site, sites, counts) for site in sites]
    if not probabilities or any(value <= 0.0 or value > 1.0 for value in probabilities):
        return -math.inf
    return math.fsum(math.log(value) for value in probabilities)


def _feasible_remainder(
    position: int,
    remaining_fragments: int,
    target_length: int,
    minimum: int,
    maximum: int,
) -> bool:
    remaining_length = target_length - position
    minimum_length = remaining_fragments * minimum - OVERHANG_LENGTH * (
        remaining_fragments - 1
    )
    maximum_length = remaining_fragments * maximum - OVERHANG_LENGTH * (
        remaining_fragments - 1
    )
    return minimum_length <= remaining_length <= maximum_length


def _refine_cuts(
    problem: dict, enzyme: str, cuts: tuple[int, ...], passes: int
) -> tuple[float, tuple[int, ...], tuple[str, ...]]:
    target = problem["target_sequence"]
    minimum, maximum = map(int, problem["fragment_length_bounds"])
    allowed = set(problem["canonical_overhangs"])
    counts = problem["conditions"][enzyme]["ligation_counts"]
    positions = [
        position
        for position in range(1, len(target) - OVERHANG_LENGTH + 1)
        if canonical_overhang(target[position : position + OVERHANG_LENGTH]) in allowed
    ]
    current = list(cuts)
    current_sites = [
        target[position : position + OVERHANG_LENGTH] for position in current
    ]
    current_score = log_fidelity(current_sites, counts)
    for _ in range(passes):
        changed = False
        for index in range(len(current)):
            previous = current[index - 1] if index else 0
            following = current[index + 1] if index + 1 < len(current) else len(target)
            lower = previous + minimum - OVERHANG_LENGTH
            upper = previous + maximum - OVERHANG_LENGTH
            if index + 1 < len(current):
                lower = max(lower, following - maximum + OVERHANG_LENGTH)
                upper = min(upper, following - minimum + OVERHANG_LENGTH)
            else:
                lower = max(lower, following - maximum)
                upper = min(upper, following - minimum)
            used = {
                canonical_overhang(site)
                for other_index, site in enumerate(current_sites)
                if other_index != index
            }
            best = (current_score, current[index], current_sites[index])
            for position in positions:
                if position < lower:
                    continue
                if position > upper:
                    break
                site = target[position : position + OVERHANG_LENGTH]
                if canonical_overhang(site) in used:
                    continue
                proposal = list(current_sites)
                proposal[index] = site
                score = log_fidelity(proposal, counts)
                candidate = (score, -position, site)
                incumbent = (best[0], -best[1], best[2])
                if candidate > incumbent:
                    best = (score, position, site)
            if best[1] != current[index]:
                current[index] = best[1]
                current_sites[index] = best[2]
                current_score = best[0]
                changed = True
        if not changed:
            break
    return current_score, tuple(current), tuple(current_sites)


def search_design(problem: dict, beam_width: int, refinement_passes: int = 0) -> dict:
    """Deterministic public-data beam search used at two declared strengths for the anchors."""
    target = problem["target_sequence"]
    count = int(problem["fragment_count"])
    minimum, maximum = map(int, problem["fragment_length_bounds"])
    allowed = set(problem["canonical_overhangs"])
    best = None
    for enzyme in sorted(problem["conditions"]):
        condition = problem["conditions"][enzyme]
        if _contains_site(target, condition["recognition_site"]):
            continue
        counts = condition["ligation_counts"]
        positions = [
            position
            for position in range(1, len(target) - OVERHANG_LENGTH + 1)
            if canonical_overhang(target[position : position + OVERHANG_LENGTH])
            in allowed
        ]
        states = [(0.0, (), ())]
        for stage in range(count - 1):
            expanded = []
            for _, cuts, sites in states:
                lower = (
                    minimum - OVERHANG_LENGTH
                    if not cuts
                    else cuts[-1] + minimum - OVERHANG_LENGTH
                )
                upper = (
                    maximum - OVERHANG_LENGTH
                    if not cuts
                    else cuts[-1] + maximum - OVERHANG_LENGTH
                )
                for position in positions:
                    if position < lower:
                        continue
                    if position > upper:
                        break
                    site = target[position : position + OVERHANG_LENGTH]
                    identity = canonical_overhang(site)
                    if identity in {canonical_overhang(value) for value in sites}:
                        continue
                    remaining = count - stage - 1
                    if not _feasible_remainder(
                        position, remaining, len(target), minimum, maximum
                    ):
                        continue
                    next_sites = sites + (site,)
                    score = log_fidelity(list(next_sites), counts)
                    if math.isfinite(score):
                        expanded.append((score, cuts + (position,), next_sites))
            expanded.sort(key=lambda row: (-row[0], row[1], row[2]))
            states = expanded[:beam_width]
            if not states:
                break
        for score, cuts, sites in states:
            if (
                len(cuts) != count - 1
                or not minimum <= len(target) - cuts[-1] <= maximum
            ):
                continue
            candidate = (score, enzyme, cuts, sites)
            if (
                best is None
                or candidate[0] > best[0]
                or (candidate[0] == best[0] and candidate[1:] < best[1:])
            ):
                best = candidate
    if best is None:
        raise RuntimeError("no feasible assembly found")
    _, enzyme, cuts, sites = best
    if refinement_passes:
        score, cuts, sites = _refine_cuts(problem, enzyme, cuts, refinement_passes)
        best = (score, enzyme, cuts, sites)
    starts = (0,) + cuts
    ends = tuple(position + OVERHANG_LENGTH for position in cuts) + (len(target),)
    return {
        "enzyme": enzyme,
        "fragments": [target[start:end] for start, end in zip(starts, ends)],
        "overhangs": list(sites),
    }


def baseline_design(problem: dict) -> dict:
    """Evenly space fragments and take the nearest legal, unused measured junction."""
    target = problem["target_sequence"]
    count = int(problem["fragment_count"])
    minimum, maximum = map(int, problem["fragment_length_bounds"])
    allowed = set(problem["canonical_overhangs"])
    enzyme = next(
        name
        for name in sorted(problem["conditions"])
        if not _contains_site(target, problem["conditions"][name]["recognition_site"])
    )
    cuts = []
    identities = set()
    for stage in range(1, count):
        previous = cuts[-1] if cuts else 0
        lower = previous + minimum - OVERHANG_LENGTH
        upper = previous + maximum - OVERHANG_LENGTH
        remaining = count - stage
        ideal = round(stage * len(target) / count)
        options = []
        for position in range(lower, upper + 1):
            if not _feasible_remainder(
                position, remaining, len(target), minimum, maximum
            ):
                continue
            site = target[position : position + OVERHANG_LENGTH]
            identity = canonical_overhang(site)
            if identity in allowed and identity not in identities:
                options.append((abs(position - ideal), position, site, identity))
        if not options:
            raise RuntimeError("the even-spacing baseline found no legal junction")
        _, position, _, identity = min(options)
        cuts.append(position)
        identities.add(identity)
    starts = (0,) + tuple(cuts)
    ends = tuple(position + OVERHANG_LENGTH for position in cuts) + (len(target),)
    return {
        "enzyme": enzyme,
        "fragments": [target[start:end] for start, end in zip(starts, ends)],
        "overhangs": [
            target[position : position + OVERHANG_LENGTH] for position in cuts
        ],
    }


def reference_design(problem: dict) -> dict:
    """Best of two deterministic beam starts followed by coordinate refinement."""
    candidates = [
        search_design(problem, beam_width=8, refinement_passes=4),
        search_design(problem, beam_width=32, refinement_passes=4),
    ]
    scored = []
    for submission in candidates:
        value, error = _validate(problem, submission)
        if error or value is None:
            raise RuntimeError(error)
        scored.append((value, submission["enzyme"], submission))
    return max(scored, key=lambda row: (row[0], row[1]))[2]


def _validate(problem: dict, submission) -> tuple[float | None, str | None]:
    if not isinstance(submission, dict) or set(submission) != {
        "enzyme",
        "fragments",
        "overhangs",
    }:
        return None, "submission must contain exactly enzyme, fragments, and overhangs"
    enzyme = submission["enzyme"]
    fragments = submission["fragments"]
    overhangs = submission["overhangs"]
    if enzyme not in problem["conditions"]:
        return None, "unknown enzyme condition"
    if not isinstance(fragments, list) or len(fragments) != problem["fragment_count"]:
        return None, "wrong fragment count"
    if not isinstance(overhangs, list) or len(overhangs) != len(fragments) - 1:
        return None, "wrong overhang count"
    if any(
        not isinstance(fragment, str) or not fragment or set(fragment) - DNA
        for fragment in fragments
    ):
        return None, "fragments must be nonempty ACGT strings"
    minimum, maximum = problem["fragment_length_bounds"]
    if any(not minimum <= len(fragment) <= maximum for fragment in fragments):
        return None, "fragment length outside the published bounds"
    if any(
        not isinstance(site, str) or len(site) != OVERHANG_LENGTH or set(site) - DNA
        for site in overhangs
    ):
        return None, "overhangs must be four-base ACGT strings"
    for index, site in enumerate(overhangs):
        if (
            fragments[index][-OVERHANG_LENGTH:] != site
            or fragments[index + 1][:OVERHANG_LENGTH] != site
        ):
            return None, "overhang does not match both adjacent fragment ends"
    reconstructed = fragments[0] + "".join(
        fragment[OVERHANG_LENGTH:] for fragment in fragments[1:]
    )
    if reconstructed != problem["target_sequence"]:
        return None, "fragments do not exactly reconstruct the target"
    recognition = problem["conditions"][enzyme]["recognition_site"]
    if _contains_site(reconstructed, recognition):
        return None, "selected enzyme has an internal restriction site"
    identities = [canonical_overhang(site) for site in overhangs]
    if any(identity not in problem["canonical_overhangs"] for identity in identities):
        return None, "overhang is outside the measured frozen panel"
    if len(set(identities)) != len(identities):
        return None, "overhang reverse-complement classes must be unique"
    value = log_fidelity(overhangs, problem["conditions"][enzyme]["ligation_counts"])
    if not math.isfinite(value):
        return None, "ligation fidelity is undefined"
    return value, None


@cache
def _anchors(instance_id: str) -> tuple[float, float]:
    profile = next(
        row
        for row in _DEVELOPMENT_PROFILES + _HELDOUT_PROFILES
        if row["id"] == instance_id
    )
    problem = _public_problem(profile)
    baseline, error = _validate(problem, baseline_design(problem))
    if error:
        raise RuntimeError(error)
    reference, error = _validate(problem, reference_design(problem))
    if error or reference is None or baseline is None or reference <= baseline:
        raise RuntimeError("reference must strictly improve the baseline")
    return baseline, reference


def _score_world(design_assembly, profile: dict, split: str) -> dict:
    problem = _public_problem(profile)
    baseline, reference = _anchors(profile["id"])
    row = {
        "instance_id": profile["id"],
        "split": split,
        "baseline_log_fidelity": baseline,
        "reference_log_fidelity": reference,
    }
    try:
        submission = design_assembly(copy.deepcopy(problem))
        value, error = _validate(problem, submission)
        if error or value is None:
            raise ValueError(error)
        score = max(0.0, (value - baseline) / (reference - baseline))
        row.update(
            {
                "valid": True,
                "log_fidelity": value,
                "predicted_fidelity": math.exp(value),
                "instance_score": score,
                "enzyme": submission["enzyme"],
            }
        )
    except Exception as exc:  # noqa: BLE001 - candidate failure is data, not an oracle crash
        row.update(
            {
                "valid": False,
                "log_fidelity": None,
                "predicted_fidelity": 0.0,
                "instance_score": 0.0,
                "enzyme": None,
                "reason": f"{type(exc).__name__}: {exc}",
            }
        )
    return row


def evaluate(design_assembly) -> dict:
    development = [
        _score_world(design_assembly, row, "development")
        for row in _DEVELOPMENT_PROFILES
    ]
    heldout = [
        _score_world(design_assembly, row, "heldout") for row in _HELDOUT_PROFILES
    ]
    all_rows = development + heldout
    return {
        "combined_score": sum(row["instance_score"] for row in development)
        / len(development),
        "robustness_score": sum(row["instance_score"] for row in heldout)
        / len(heldout),
        "valid": 1.0 if all(row["valid"] for row in development) else 0.0,
        "feasibility_rate": sum(row["valid"] for row in all_rows) / len(all_rows),
        "mean_predicted_fidelity": sum(row["predicted_fidelity"] for row in all_rows)
        / len(all_rows),
        "instances_beating_reference": sum(
            row["instance_score"] > 1.0 for row in all_rows
        ),
        "per_instance": all_rows,
    }

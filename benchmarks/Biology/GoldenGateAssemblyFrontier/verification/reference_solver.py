"""Truth-blind reference using only fields in the public problem mapping."""

import math

OVERHANG_LENGTH = 4


def _reverse_complement(sequence):
    return sequence.translate(str.maketrans("ACGT", "TGCA"))[::-1]


def _canonical(sequence):
    return min(sequence, _reverse_complement(sequence))


def _contains_site(sequence, site):
    return site in sequence or _reverse_complement(site) in sequence


def _count(counts, left, right):
    return int(counts.get(f"{left}>{right}", 0))


def _log_fidelity(sites, counts):
    values = []
    ends = list(sites) + [_reverse_complement(site) for site in sites]
    for site in sites:
        complement = _reverse_complement(site)
        correct = _count(counts, site, complement) + _count(counts, complement, site)
        total = sum(_count(counts, site, other) for other in ends)
        total += sum(_count(counts, complement, other) for other in ends)
        if correct <= 0 or total < correct:
            return -math.inf
        values.append(math.log(correct / total))
    return math.fsum(values) if values else -math.inf


def _feasible_remainder(position, remaining, target_length, minimum, maximum):
    length = target_length - position
    low = remaining * minimum - OVERHANG_LENGTH * (remaining - 1)
    high = remaining * maximum - OVERHANG_LENGTH * (remaining - 1)
    return low <= length <= high


def _refine(problem, enzyme, cuts, passes):
    target = problem["target_sequence"]
    minimum, maximum = map(int, problem["fragment_length_bounds"])
    allowed = set(problem["canonical_overhangs"])
    counts = problem["conditions"][enzyme]["ligation_counts"]
    positions = [
        position
        for position in range(1, len(target) - OVERHANG_LENGTH + 1)
        if _canonical(target[position : position + OVERHANG_LENGTH]) in allowed
    ]
    current = list(cuts)
    sites = [target[position : position + OVERHANG_LENGTH] for position in current]
    score = _log_fidelity(sites, counts)
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
                _canonical(site)
                for other_index, site in enumerate(sites)
                if other_index != index
            }
            best = (score, current[index], sites[index])
            for position in positions:
                if position < lower:
                    continue
                if position > upper:
                    break
                site = target[position : position + OVERHANG_LENGTH]
                if _canonical(site) in used:
                    continue
                proposal = list(sites)
                proposal[index] = site
                value = _log_fidelity(proposal, counts)
                if (value, -position, site) > (best[0], -best[1], best[2]):
                    best = (value, position, site)
            if best[1] != current[index]:
                score, current[index], sites[index] = best
                changed = True
        if not changed:
            break
    return score, tuple(current), tuple(sites)


def _search(problem, beam_width, refinement_passes):
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
            if _canonical(target[position : position + OVERHANG_LENGTH]) in allowed
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
                used = {_canonical(site) for site in sites}
                for position in positions:
                    if position < lower:
                        continue
                    if position > upper:
                        break
                    site = target[position : position + OVERHANG_LENGTH]
                    if _canonical(site) in used:
                        continue
                    remaining = count - stage - 1
                    if not _feasible_remainder(
                        position, remaining, len(target), minimum, maximum
                    ):
                        continue
                    next_sites = sites + (site,)
                    score = _log_fidelity(next_sites, counts)
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
            score, cuts, sites = _refine(problem, enzyme, cuts, refinement_passes)
            candidate = (score, enzyme, cuts, sites)
            if (
                best is None
                or candidate[0] > best[0]
                or (candidate[0] == best[0] and candidate[1:] < best[1:])
            ):
                best = candidate
    if best is None:
        raise RuntimeError("no feasible assembly found")
    return best


def _build(problem, result):
    _, enzyme, cuts, sites = result
    target = problem["target_sequence"]
    starts = (0,) + cuts
    ends = tuple(position + OVERHANG_LENGTH for position in cuts) + (len(target),)
    return {
        "enzyme": enzyme,
        "fragments": [target[start:end] for start, end in zip(starts, ends)],
        "overhangs": list(sites),
    }


def design_assembly(problem):
    candidates = [_search(problem, width, 4) for width in (8, 32)]
    return _build(problem, max(candidates, key=lambda row: (row[0], row[1])))

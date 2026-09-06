"""Baseline: evenly spaced fragments with the nearest legal measured junctions."""

OVERHANG_LENGTH = 4


def _reverse_complement(sequence):
    return sequence.translate(str.maketrans("ACGT", "TGCA"))[::-1]


def _canonical(sequence):
    return min(sequence, _reverse_complement(sequence))


def _contains_site(sequence, site):
    return site in sequence or _reverse_complement(site) in sequence


def design_assembly(problem):
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
            remaining_length = len(target) - position
            minimum_length = remaining * minimum - OVERHANG_LENGTH * (remaining - 1)
            maximum_length = remaining * maximum - OVERHANG_LENGTH * (remaining - 1)
            if not minimum_length <= remaining_length <= maximum_length:
                continue
            site = target[position : position + OVERHANG_LENGTH]
            identity = _canonical(site)
            if identity in allowed and identity not in identities:
                options.append((abs(position - ideal), position, identity))
        if not options:
            raise RuntimeError("no legal junction near the even fragment spacing")
        _, position, identity = min(options)
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

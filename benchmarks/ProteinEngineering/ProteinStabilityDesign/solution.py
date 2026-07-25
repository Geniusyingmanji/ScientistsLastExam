"""Weak valid baseline: rank feasible pairs by the additive single-mutation proxy."""


def design_stable_batch(problem, assay):
    del assay
    wild_type = str(problem["wild_type_sequence"])
    left, right = [int(value) for value in problem["mutable_positions"]]
    proxy = {
        int(row["position"]): dict(row["scores"])
        for row in problem["single_mutation_proxy"]
    }

    ranked = []
    for pair in problem["candidate_residue_pairs"]:
        pair = str(pair)
        score = float(proxy[left][pair[0]]) + float(proxy[right][pair[1]])
        ranked.append((-score, pair))
    ranked.sort()

    sequences = []
    for _, pair in ranked[:int(problem["batch_size"])]:
        sequence = list(wild_type)
        sequence[left], sequence[right] = pair
        sequences.append("".join(sequence))
    return {"sequences": sequences}

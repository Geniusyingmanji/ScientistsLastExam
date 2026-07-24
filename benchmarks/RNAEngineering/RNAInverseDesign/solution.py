"""Weak valid baseline: satisfy sequence constraints but ignore the target fold."""


def design_rna(problem):
    sequence = list(("ACGU" * ((int(problem["length"]) + 3) // 4))[:problem["length"]])
    for index, base in problem["fixed_bases"]:
        sequence[int(index)] = str(base)
    return {"sequence": "".join(sequence)}

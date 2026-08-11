"""A truth-blind reference designer, for calibration only. Never the baseline.

Constraint-aware random restart: place Watson-Crick pairs where the target pairs, sample loop
bases, keep the best ensemble defect seen. It uses ViennaRNA to score its own attempts, exactly
as a candidate may, and it does not call `inverse_fold` - reaching the anchor has to be work.
"""

from __future__ import annotations

import random

PAIRS = ("GC", "CG", "AU", "UA", "GU", "UG")


def _pair_table(structure: str) -> dict[int, int]:
    stack, table = [], {}
    for index, character in enumerate(structure):
        if character == "(":
            stack.append(index)
        elif character == ")":
            left = stack.pop()
            table[left] = index
            table[index] = left
    return table


def design_rna(structure: str) -> str:
    import RNA

    table = _pair_table(structure)
    rng = random.Random(len(structure) * 7919)
    best, best_defect = None, float("inf")
    for _attempt in range(60):
        sequence = [""] * len(structure)
        for left, right in table.items():
            if left > right:
                continue
            pair = rng.choice(PAIRS[:4] if rng.random() < 0.85 else PAIRS)
            sequence[left], sequence[right] = pair[0], pair[1]
        for index, character in enumerate(sequence):
            if not character:
                sequence[index] = rng.choice("ACGU")
        candidate = "".join(sequence)
        fold_compound = RNA.fold_compound(candidate)
        fold_compound.pf()
        defect = fold_compound.ensemble_defect(structure)
        if defect < best_defect:
            best, best_defect = candidate, defect
    return best

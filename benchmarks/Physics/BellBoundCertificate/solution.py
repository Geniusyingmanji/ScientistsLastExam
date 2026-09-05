"""Baseline: the identity certificate, which proves only the algebraic bound.

Take the basis to be the first level - the identity, every A_x, every B_y - and the certificate to
be a single square per basis word with weight equal to the corresponding coefficient of the
functional. The operator identity is satisfied by construction and nothing is optimised, so the
bound this proves is the one you get from the triangle inequality: the sum of the magnitudes of the
functional's coefficients. That is above the free level-1 relaxation on every instance and scores
zero by construction.
"""
from fractions import Fraction


def build_certificate(instance):
    settings = instance["settings"]
    words = [([], [])]
    words += [([x], []) for x in range(settings[0])]
    words += [([], [y]) for y in range(settings[1])]
    index = {(tuple(a), tuple(b)): position for position, (a, b) in enumerate(words)}
    size = len(words)

    squares = []
    for (a_part, b_part), coefficient in instance["functional"].items():
        if coefficient == 0:
            continue
        left = index[(tuple(a_part), ())] if a_part else index[((), ())]
        right = index[((), tuple(b_part))] if b_part else index[((), ())]
        # |c| * (s -+ t)^dagger (s -+ t) / 2 contributes -c * (s^dagger t + t^dagger s) / 2 plus
        # |c| * (identity) when s and t are distinct words: the cross terms carry the functional
        # and the diagonal pays for them. This is the triangle inequality, written as squares.
        sign = -1 if coefficient > 0 else 1
        weight = Fraction(abs(coefficient), 2)
        vector = [0] * size
        if left == right:
            vector[left] = 1
            squares.append({"weight": [abs(coefficient), 1],
                            "vector": [[v, 1] for v in vector]})
            continue
        vector[left] = 1
        vector[right] = sign
        squares.append({"weight": [weight.numerator, weight.denominator],
                        "vector": [[v, 1] for v in vector]})
    return {"basis": [[list(a), list(b)] for a, b in words], "squares": squares}

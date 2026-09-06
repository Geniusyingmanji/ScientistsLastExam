"""Catalog SOS for I_4422^{13}: two CHSH replacements using four frozen BB extras.

This is a hand exact certificate, not an SDP solve. It proves 7/2, strictly below the
triangle bound 4, and uses extra moments from the frozen NPA-2 pool rather than free words.
"""
from fractions import Fraction


def reduce_side(letters) -> tuple:
    out: list = []
    for x in letters:
        if out and out[-1] == x:
            out.pop()
        else:
            out.append(x)
    return tuple(out)


def canonical(a, b) -> tuple:
    return (reduce_side(a), reduce_side(b))


def dagger(word: tuple) -> tuple:
    a, b = word
    return (tuple(reversed(a)), tuple(reversed(b)))


def multiply(u: tuple, v: tuple) -> tuple:
    return canonical(u[0] + v[0], u[1] + v[1])


BLOCKS = (
    (0, 2, 1, 2, (-1, -1, -1, 1)),
    (1, 3, 0, 3, (-1, -1, -1, 1)),
)


def build_certificate(instance):
    npa1 = [((), ())] + [((i,), ()) for i in range(4)] + [((), (j,)) for j in range(4)]
    extras = []
    skip = set()
    for i1, i2, j1, j2, _signs in BLOCKS:
        skip |= {((i1,), (j1,)), ((i1,), (j2,)), ((i2,), (j1,)), ((i2,), (j2,))}
        extras += [((), (j1, j2)), ((), (j2, j1))]
    basis = npa1 + extras
    index = {word: position for position, word in enumerate(basis)}
    size = len(basis)
    squares = []
    for (a_part, b_part), coefficient in instance["functional"].items():
        if (tuple(a_part), tuple(b_part)) in skip:
            continue
        left = index[(tuple(a_part), ())] if a_part else index[((), ())]
        right = index[((), tuple(b_part))] if b_part else index[((), ())]
        sign = -1 if coefficient > 0 else 1
        vector = [0] * size
        if left == right:
            vector[left] = 1
            squares.append({"weight": [abs(int(coefficient)), 1],
                            "vector": [[value, 1] for value in vector]})
            continue
        vector[left] = 1
        vector[right] = sign
        weight = Fraction(abs(int(coefficient)), 2)
        squares.append({"weight": [weight.numerator, weight.denominator],
                        "vector": [[value, 1] for value in vector]})
    for i1, i2, j1, j2, signs in BLOCKS:
        s2, s3, t2, t3 = signs
        for pairs in (
            [(((i1,), ()), 1), (((), (j1,)), s2), (((), (j2,)), s3)],
            [(((i2,), ()), 1), (((), (j1,)), t2), (((), (j2,)), t3)],
        ):
            vector = [0] * size
            for word, coeff in pairs:
                vector[index[word]] = coeff
            squares.append({"weight": [1, 2],
                            "vector": [[value, 1] for value in vector]})
    return {"basis": [[list(a), list(b)] for a, b in basis], "squares": squares}

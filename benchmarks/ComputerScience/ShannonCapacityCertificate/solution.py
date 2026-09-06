"""Baseline: the interval anyone gets without doing anything, which is worth exactly zero.

Below, take the largest independent set in the cycle itself - every second vertex, ``floor(n/2)``
of them - as a code of block length one. Above, take the all-ones matrix, which satisfies the
Lovasz pattern trivially and whose largest eigenvalue is ``n``. The pair is a correct certified
interval, ``[floor(n/2), n]``, and it is enormous: for the seven-cycle it proves
``3 <= Theta(C_7) <= 7`` where the free bound already proves ``3.2237 <= Theta(C_7) <= 3.3177``.

Nothing here is wrong. It is simply the argument that costs nothing, and the scale is anchored so
that it scores 0.000000.
"""


def build_certificate(instance):
    cycle = instance["cycle"]
    independent = [[vertex] for vertex in range(0, cycle - 1, 2)]
    ones = [[1] * cycle for _ in range(cycle)]
    # b*I - J is only positive semidefinite at b = n, so nudge past it by one grid step; the
    # certificate has to be positive definite, not almost.
    bound = [cycle * instance["max_denominator"] + 1, instance["max_denominator"]]
    return {
        "lower_certificates": [{"power": 1, "vertices": independent}],
        "upper_certificate": {"matrix": ones, "bound": bound},
    }

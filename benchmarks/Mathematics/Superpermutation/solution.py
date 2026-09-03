"""Initial baseline for Superpermutation (concatenate every permutation).

The concatenation of all n! permutations in lex order is always a valid superpermutation of
length n*n!, far from the known records. Edit this file to emit a shorter string — overlapping
permutations, hierarchical constructions, or better.
"""
import itertools


def build_superpermutation(n: int) -> str:
    """Return a string over '1'..str(n) containing every n-permutation as a substring."""
    alphabet = "".join(str(i) for i in range(1, n + 1))
    return "".join("".join(p) for p in itertools.permutations(alphabet))

"""Self-contained 243-word product baseline for the fixed C7^5 task."""
from itertools import product


def build_code(problem):
    return {"codewords": [list(word) for word in product((0, 2, 4), repeat=5)]}

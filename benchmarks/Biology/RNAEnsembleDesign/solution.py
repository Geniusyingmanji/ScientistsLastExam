"""Baseline: an unstructured poly-A sequence of the right length.

Valid by construction and deliberately weak - poly-A forms no pairs, so its ensemble defect is
the whole target. It scores exactly 0.
"""


def design_rna(structure: str) -> str:
    return "A" * len(structure)

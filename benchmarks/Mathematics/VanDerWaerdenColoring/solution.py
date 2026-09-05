"""Initial baseline for VanDerWaerdenColoring.

Splits {0,...,r*(k-1)-1} into r consecutive blocks of exactly (k-1) elements each, one color per
block. Since every color is then used exactly (k-1) times in total, no color can possibly contain
k elements at all -- let alone k elements forming an arithmetic progression -- so this is valid by
construction with zero search, but wastes almost all of the available room: real avoiding
colorings are known to run far longer than r*(k-1). Edit this file to do better -- a real search
should extend the coloring position by position, choosing at each step a color that does not
complete a monochromatic k-term arithmetic progression with any earlier position.
"""
from __future__ import annotations


def construct_coloring(r: int, k: int):
    """Return a list of colors in {0,...,r-1} with no monochromatic k-term AP."""
    return [c for c in range(r) for _ in range(k - 1)]

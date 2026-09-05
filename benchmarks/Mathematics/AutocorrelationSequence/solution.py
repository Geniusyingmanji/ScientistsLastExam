"""Initial baseline for AutocorrelationSequence.

A uniform (all-ones) step function: valid for both the unsigned and signed variants, and
its discrete autoconvolution ratio is exactly 2 regardless of length -- a real, scale-
invariant fact, but far from the published upper bounds. Edit this file to do better --
shaping the sequence (a window that tapers toward the edges, for instance) lowers the
autoconvolution peak relative to the sum.
"""
from __future__ import annotations


def construct_sequence(signed: bool):
    """Return a list of N step heights (N>=10 if signed, N>=100 if unsigned; non-negative if
    unsigned)."""
    n = 20 if signed else 100
    return [1.0] * n

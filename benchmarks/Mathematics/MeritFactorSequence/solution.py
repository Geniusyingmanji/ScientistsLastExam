"""Initial baseline for MeritFactorSequence.

An all-ones sequence of length 100: valid (all coefficients in {-1, 1}, length >= 100), but
its autocorrelation at every lag is large (C_k = n - k for every k), giving a very poor
merit factor. Edit this file to do better -- flipping individual signs to reduce the
autocorrelation sidelobes raises the merit factor substantially.
"""
from __future__ import annotations


def construct_sequence():
    """Return a list of +/-1 coefficients of length >= 100."""
    return [1.0] * 100

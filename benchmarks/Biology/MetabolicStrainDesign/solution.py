"""Weak valid baseline: ship the wild-type strain untouched.

No knockouts, no overexpressions — the factory default the normalization anchors at
zero.
"""

from __future__ import annotations


def design_strain(problem):
    del problem
    return {"knockouts": [], "overexpressions": {}}

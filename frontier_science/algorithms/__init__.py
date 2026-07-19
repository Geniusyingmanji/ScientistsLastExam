"""Named search backends for Frontier-Science."""

from __future__ import annotations

from typing import Callable

from .common import EvolveResult
from .evolve import greedy_rewrite

ALGORITHMS = ("greedy_rewrite", "openevolve", "abmcts", "shinkaevolve")


def get_algorithm(name: str) -> Callable[..., EvolveResult]:
    normalized = str(name).strip().lower()
    if normalized == "greedy_rewrite":
        return greedy_rewrite
    if normalized == "openevolve":
        from .openevolve_backend import openevolve

        return openevolve
    if normalized == "abmcts":
        from .abmcts_backend import abmcts

        return abmcts
    if normalized == "shinkaevolve":
        from .shinkaevolve_backend import shinkaevolve

        return shinkaevolve
    raise KeyError("unknown algorithm %r; available: %s" % (name, ", ".join(ALGORITHMS)))


__all__ = ["ALGORITHMS", "EvolveResult", "get_algorithm", "greedy_rewrite"]

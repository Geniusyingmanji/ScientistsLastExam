"""Standalone input-only classical reference; no world generator or truth."""

from copy import deepcopy

from functools import lru_cache

import numpy as np

def _matrix(problem):
    a = np.zeros((len(problem["fragments"]), len(problem["variant_ids"])))
    constant = 0.
    for i, f in enumerate(problem["fragments"]):
        e = np.asarray(f["error_probabilities"])
        a[i, f["positions"]] = (2 * np.asarray(f["alleles"]) - 1) * .5 * np.log((1-e)/e)
        constant += float(.5 * np.log(e * (1-e)).sum())
    return a, constant

def reference(problem, starts=1):
    """Signed read graph initialization followed by exact likelihood bit flips."""
    a, _ = _matrix(problem)
    gram = a.T @ a
    np.fill_diagonal(gram, 0.)
    _, vectors = np.linalg.eigh(gram)
    rng = np.random.default_rng(129)
    best, best_value = None, -np.inf
    for attempt in range(starts):
        h = np.where(vectors[:, -1] >= 0, 1., -1.) if attempt == 0 else rng.choice([-1., 1.], a.shape[1])
        z = a @ h
        for _ in range(12):
            changed = False
            for j in range(len(h)):
                proposed = z - 2 * h[j] * a[:, j]
                gain = np.sum(np.logaddexp(proposed, -proposed) - np.logaddexp(z, -z))
                if gain > 1e-10:
                    h[j] *= -1
                    z = proposed
                    changed = True
            if not changed:
                break
        value = float(np.logaddexp(z, -z).sum())
        if value > best_value:
            best, best_value = h.copy(), value
    return {"haplotype": ((best + 1) / 2).astype(int).tolist()}

assemble_haplotypes = reference

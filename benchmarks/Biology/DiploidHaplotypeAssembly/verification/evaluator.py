"""Diploid read-mixture likelihood; no hidden phase enters the objective."""
from copy import deepcopy
from functools import lru_cache
import numpy as np


def _world(index):
    rng = np.random.default_rng(81400 + index)
    n = (200, 240, 280, 320)[index]
    truth = rng.integers(0, 2, n)
    blocks = np.repeat(np.arange(2), n // 2)
    def reads(count):
        out = []
        for _ in range(count):
            block = rng.integers(2)
            positions = np.sort(rng.choice(np.flatnonzero(blocks == block), int(rng.integers(3, 9)), replace=False))
            errors = rng.uniform(.06, .24 + .02 * index, len(positions))
            alleles = truth[positions] ^ rng.integers(2) ^ (rng.random(len(positions)) < errors)
            out.append(dict(positions=positions.tolist(), alleles=alleles.tolist(), error_probabilities=errors.tolist()))
        return out
    problem = dict(variant_ids=[f"v{i}" for i in range(n)], block_ids=blocks.tolist(),
                   fragments=reads(n * 3), noise_model="independent_flip_equal_homolog_mixture")
    return problem, truth, reads(n)


def _matrix(problem):
    a = np.zeros((len(problem["fragments"]), len(problem["variant_ids"])))
    constant = 0.
    for i, f in enumerate(problem["fragments"]):
        e = np.asarray(f["error_probabilities"])
        a[i, f["positions"]] = (2 * np.asarray(f["alleles"]) - 1) * .5 * np.log((1-e)/e)
        constant += float(.5 * np.log(e * (1-e)).sum())
    return a, constant


def likelihood(problem, haplotype):
    a, c = _matrix(problem)
    z = a @ (2 * np.asarray(haplotype) - 1)
    return float(c + np.sum(np.logaddexp(z, -z) - np.log(2)))


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


@lru_cache(None)
def _anchors(index):
    p, _, _ = _world(index)
    return likelihood(p, [0] * len(p["variant_ids"])), likelihood(p, reference(p)["haplotype"])


def _score_output(index, problem, output):
    if not isinstance(output, dict) or set(output) != {"haplotype"}:
        return 0., False
    h = output["haplotype"]
    if not isinstance(h, list) or len(h) != len(problem["variant_ids"]) or any(type(v) is not int or v not in (0, 1) for v in h):
        return 0., False
    if not any(h):
        return 0., True
    baseline, ref = _anchors(index)
    return float(np.clip((likelihood(problem, h) - baseline) / (ref - baseline), 0, 1)), True


def evaluate(assemble_haplotypes):
    rows = []
    for index in range(4):
        p, truth, prediction = _world(index)
        score, valid, predictive, accuracy = 0., False, 0., 0.
        try:
            out = assemble_haplotypes(deepcopy(p))
            score, valid = _score_output(index, p, out)
            if valid:
                h = np.asarray(out["haplotype"])
                accuracy = float(np.mean([max(np.mean(h[np.array(p["block_ids"]) == b] == truth[np.array(p["block_ids"]) == b]),
                                             np.mean(h[np.array(p["block_ids"]) == b] != truth[np.array(p["block_ids"]) == b])) for b in (0, 1)]))
                predictive = likelihood(dict(p, fragments=prediction), h) / len(prediction)
        except Exception:
            score, valid = 0., False
        rows.append(dict(score=score, valid=valid, phase_accuracy=accuracy, predictive_log_likelihood=predictive))
    return dict(combined_score=float(np.mean([r["score"] for r in rows[:2]])),
                valid=float(all(r["valid"] for r in rows)), heldout_score=float(np.mean([r["score"] for r in rows[2:]])), per_instance=rows)

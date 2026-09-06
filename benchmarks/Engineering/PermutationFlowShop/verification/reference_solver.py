"""Truth-blind reference witness: NEH construction refined by seeded iterated local search.

Deterministic: one numpy RNG seeded from the instance seed, a fixed iteration budget and
a fixed perturbation schedule. The descent uses the accelerated insertion evaluation
(prefix completion tables and suffix tail tables, O(machines) per candidate position),
which is what makes a fixed-iteration witness reproducible in CPU minutes. Run with
larger iteration budgets it reproduces the frozen witness makespans recorded in the
evaluator and references/known_best.md.
"""

from __future__ import annotations

import numpy as np

# One complete perturb-and-descent cycle is a competent runnable witness and
# scores in the middle of the scale.  The frozen 3000-iteration makespans remain
# the stronger record anchor, so additional search has measurable value.
DEFAULT_ITERATIONS = 1


def makespan_of(times, order):
    m = times.shape[1]
    completion = np.zeros(m, dtype=np.int64)
    for job in order:
        completion[0] += times[job, 0]
        for machine in range(1, m):
            completion[machine] = max(completion[machine],
                                      completion[machine - 1]) + times[job, machine]
    return int(completion[-1])


def _neh(times):
    jobs = times.shape[0]
    order = sorted(range(jobs), key=lambda j: -int(times[j].sum()))
    built = []
    for job in order:
        best, best_makespan = None, None
        for position in range(len(built) + 1):
            candidate = built[:position] + [job] + built[position:]
            value = makespan_of(times, candidate)
            if best_makespan is None or value < best_makespan:
                best, best_makespan = candidate, value
        built = best
    return built


def _prefix_tables(times, seq):
    """e[i][j]: completion time of seq[:i] on machine j (e[0] = 0)."""
    m = times.shape[1]
    e = np.zeros((len(seq) + 1, m), dtype=np.int64)
    for index, job in enumerate(seq):
        row = e[index].copy()
        cur = row[0] + times[job, 0]
        e[index + 1, 0] = cur
        for machine in range(1, m):
            cur = max(cur, row[machine]) + times[job, machine]
            e[index + 1, machine] = cur
    return e


def _suffix_tables(times, seq):
    """f[i][j]: time from the start of seq[i] on machine j to the completion of
    seq[i:] on all machines; f[len(seq)][j] = 0."""
    m = times.shape[1]
    n = len(seq)
    f = np.zeros((n + 1, m), dtype=np.int64)
    for index in range(n - 1, -1, -1):
        job = seq[index]
        below = f[index + 1]
        # last machine first
        f[index, m - 1] = times[job, m - 1] + f[index + 1, m - 1]
        for machine in range(m - 2, -1, -1):
            f[index, machine] = times[job, machine] + max(f[index, machine + 1],
                                                          below[machine])
    return f


def _insertion_positions(times, job, e, f):
    """Makespan of inserting `job` at every position k, given prefix table e of the
    jobs before the hole and suffix table f from the job after it."""
    m = times.shape[1]
    results = []
    for k in range(len(e)):
        prev = e[k]
        cur = prev[0] + times[job, 0]
        value = cur + f[k, 0]
        for machine in range(1, m):
            cur = max(cur, prev[machine]) + times[job, machine]
            value = max(value, cur + f[k, machine])
        results.append(int(value))
    return results


def _descent(times, order):
    current = list(order)
    current_score = makespan_of(times, current)
    improved = True
    while improved:
        improved = False
        for index in range(len(current)):
            job = current.pop(index)
            e = _prefix_tables(times, current)
            f = _suffix_tables(times, current)
            candidates = _insertion_positions(times, job, e, f)
            best_position = int(np.argmin(candidates))
            best_value = candidates[best_position]
            current.insert(best_position, job)
            if best_value < current_score:
                current_score = best_value
                improved = True
    return current, current_score


def schedule_flow_shop(problem, iterations=DEFAULT_ITERATIONS, seed=0):
    times = np.asarray(problem["processing_times"], dtype=int)
    rng = np.random.default_rng(int(problem.get("seed", 0)) + 7919 * int(seed))
    best = _neh(times)
    best_score = makespan_of(times, best)
    current, current_score = list(best), best_score
    for step in range(int(iterations)):
        perturbed = list(current)
        for _ in range(3):
            index = int(rng.integers(0, len(perturbed)))
            job = perturbed.pop(index)
            perturbed.insert(int(rng.integers(0, len(perturbed) + 1)), job)
        candidate, candidate_score = _descent(times, perturbed)
        if candidate_score <= current_score:
            current, current_score = candidate, candidate_score
            if candidate_score < best_score:
                best, best_score = list(candidate), candidate_score
        elif step % 25 == 24:
            current, current_score = list(best), best_score
    return best

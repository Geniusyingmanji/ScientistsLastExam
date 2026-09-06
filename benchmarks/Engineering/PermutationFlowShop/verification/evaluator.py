"""Frozen oracle for PermutationFlowShop (hidden from the agent).

Minimize the makespan of a deterministic permutation flow shop: n jobs, m machines,
every job visits the machines in the same order, and the candidate fixes the job
sequence. Instances are fresh-seeded in the Taillard style (processing times uniform on
{1..99}), so no published table or memorized best solution transfers. The score is the
fraction of the gap closed between the shipped baseline (as-given job order) and a
frozen truth-blind iterated-local-search witness; beating the witness scores above one.
"""

from __future__ import annotations

import numpy as np

# (seed, jobs, machines) — development and held-out instance families.
DEVELOPMENT_SPECS = (
    (44011, 20, 5),
    (44017, 30, 10),
    (44023, 50, 5),
    (44029, 50, 10),
)
HELDOUT_SPECS = (
    (44037, 20, 5),
    (44041, 30, 5),
    (44043, 50, 10),
)

# Makespans of the frozen witness search (verification/reference_solver.py with
# iterations=3000, seed 0), reproduced by the command in references/known_best.md.
# The baseline makespan is recomputed from the instance at scoring time, so only the
# witness side is frozen.
WITNESS_MAKESPAN = {
    44011: 1180,
    44017: 2182,
    44023: 3023,
    44029: 2979,
}
HELDOUT_WITNESS_MAKESPAN = {
    44037: 1222,
    44041: 1734,
    44043: 3012,
}


def instance(spec):
    """Deterministic Taillard-style instance: processing times uniform on {1..99}."""
    seed, jobs, machines = spec
    rng = np.random.default_rng(int(seed))
    times = rng.integers(1, 100, size=(jobs, machines))
    return {
        "instance_id": "pfs_%d_%dx%d" % (seed, jobs, machines),
        "seed": int(seed),
        "jobs": int(jobs),
        "machines": int(machines),
        "processing_times": times.astype(int).tolist(),
    }


def makespan(processing_times, order):
    times = np.asarray(processing_times, dtype=int)
    order = np.asarray(order, dtype=int)
    completion = np.zeros(times.shape[1], dtype=np.int64)
    for job in order:
        completion[0] += times[job, 0]
        for machine in range(1, times.shape[1]):
            completion[machine] = max(completion[machine],
                                      completion[machine - 1]) + times[job, machine]
    return int(completion[-1])


def _check_order(order, jobs):
    array = np.asarray(order)
    if array.shape != (jobs,):
        raise ValueError("permutation must list every job index exactly once")
    if np.any(array < 0) or np.any(array >= jobs) or len(set(array.tolist())) != jobs:
        raise ValueError("permutation must list every job index exactly once")


def _neh_makespan(times):
    """The classic NEH construction, computed inside the oracle as the zero anchor.

    The as-given order is so weak that every competent construction closes over
    ninety percent of the gap to the witness; anchoring zero at NEH keeps the scale
    about search quality beyond the textbook construction.
    """
    jobs, machines = times.shape
    order = sorted(range(jobs), key=lambda j: -int(times[j].sum()))
    built = []
    for job in order:
        best, best_makespan = None, None
        for position in range(len(built) + 1):
            candidate = built[:position] + [job] + built[position:]
            value = makespan(times, candidate)
            if best_makespan is None or value < best_makespan:
                best, best_makespan = candidate, value
        built = best
    return best_makespan


def _normalized_score(achieved, baseline, witness):
    if baseline <= witness:
        return 1.0 if achieved <= witness else 0.0
    progress = (baseline - achieved) / float(baseline - witness)
    return float(max(0.0, progress))


def _run_split(candidate, specs, witness_table):
    rows = []
    for spec in specs:
        problem = instance(spec)
        entry = {"instance_id": problem["instance_id"], "valid": False,
                 "makespan": None, "score": 0.0}
        try:
            order = candidate(problem)
            _check_order(order, problem["jobs"])
            achieved = makespan(problem["processing_times"], order)
            times = np.asarray(problem["processing_times"], dtype=int)
            baseline = _neh_makespan(times)
            entry.update({
                "valid": True, "makespan": achieved,
                "score": _normalized_score(achieved, baseline, witness_table[spec[0]]),
            })
        except Exception:
            pass
        rows.append(entry)
    return rows


def evaluate(schedule_flow_shop):
    development = _run_split(schedule_flow_shop, DEVELOPMENT_SPECS, WITNESS_MAKESPAN)
    heldout = _run_split(schedule_flow_shop, HELDOUT_SPECS, HELDOUT_WITNESS_MAKESPAN)
    dev_valid = sum(row["valid"] for row in development)
    hold_valid = sum(row["valid"] for row in heldout)
    return {
        "combined_score": (float(np.mean([row["score"] for row in development]))
                           if dev_valid == len(development) else 0.0),
        "valid": 1.0 if dev_valid == len(development) else 0.0,
        "feasibility_rate": dev_valid / len(development),
        "mean_makespan": (float(np.mean([row["makespan"] for row in development
                                         if row["valid"]])) if dev_valid else 0.0),
        "robustness_score": (float(np.mean([row["score"] for row in heldout]))
                             if hold_valid == len(heldout) else 0.0),
        "heldout_feasibility_rate": hold_valid / len(heldout),
        "per_instance": development + heldout,
        "raw_score": (float(np.mean([row["score"] for row in development]))
                      if dev_valid == len(development) else 0.0),
    }

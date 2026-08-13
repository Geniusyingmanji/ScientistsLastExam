"""Infer a coupled spin system from its simulated NMR spectrum.

The science. A high-resolution proton NMR spectrum of n coupled spins is the eigenspectrum of a
Zeeman-plus-scalar-coupling Hamiltonian. Reading the chemical shifts and J couplings back out of
the peak list is the daily work of spectral assignment, and it is genuinely inverse: second-order
systems produce peaks at positions that are not simple sums of shifts and couplings, intensities
redistribute across transitions, and different spin systems can produce near-identical spectra.

The oracle is nmrsim, which builds and diagonalises the Hamiltonian rather than approximating it
with first-order multiplet rules, so a score here measures agreement with the quantum mechanics
and not with a reimplementation of it.

This is a discovery task, and its three axes are reported separately and never averaged, for the
reason CausaLab documents and this repository reproduces: a single maximised scalar hides the
failure that matters. `combined_score` carries mechanism recovery alone; false-discovery rate and
calibrated refusal sit beside it in the metrics and are meant to be read with it.

    mechanism   how close the returned shifts and couplings are to the truth
    fdr         how often a coupling is claimed where the truth has none
    refusal     whether the candidate declines on a spectrum that does not determine the system
"""

from __future__ import annotations

import math
import random

DIFFICULTY = 1

# Every level carries true-zero couplings. Without them the false-discovery axis has no
# denominator and reports None, which is what the first shipped level did.
#
# Difficulty is the number of coupled spins and how close their shifts sit. Two spins far apart
# are first-order and readable by inspection; three or more spins with shifts inside a few
# couplings of each other are strongly second-order, where intensities move and the naive
# reading fails.
_LADDER = {
    1: {"spins": 3, "shift_span": 260.0, "min_gap": 45.0, "j_range": (3.0, 12.0),
        "sparsity": 0.34, "count": 5, "seed": 20260812},
    2: {"spins": 4, "shift_span": 220.0, "min_gap": 28.0, "j_range": (2.0, 14.0),
        "sparsity": 0.25, "count": 5, "seed": 20260813},
    3: {"spins": 5, "shift_span": 180.0, "min_gap": 18.0, "j_range": (1.5, 16.0),
        "sparsity": 0.40, "count": 5, "seed": 20260814},
}

_SEALED_LADDER = {
    1: {"spins": 3, "shift_span": 240.0, "min_gap": 40.0, "j_range": (3.0, 12.0),
        "sparsity": 0.34, "count": 3, "seed": 880101},
    2: {"spins": 4, "shift_span": 200.0, "min_gap": 25.0, "j_range": (2.0, 14.0),
        "sparsity": 0.25, "count": 3, "seed": 880102},
    3: {"spins": 5, "shift_span": 170.0, "min_gap": 16.0, "j_range": (1.5, 16.0),
        "sparsity": 0.40, "count": 3, "seed": 880103},
}

# A coupling below this is not resolvable at the linewidth used here, so claiming one is neither
# right nor wrong - it is unfalsifiable. Truth values are kept away from the boundary.
RESOLVABLE_J = 1.0
LINEWIDTH = 0.5

# Some worlds are deliberately under-determined: two spins are made magnetically equivalent, which
# collapses their mutual coupling out of the observable spectrum entirely. The only correct answer
# there is to decline, and a candidate that confidently reports the hidden coupling is guessing.
_CACHE: dict = {}


def _nmrsim():
    import nmrsim

    return nmrsim


class _quiet:
    """Swallow nmrsim's Hamiltonian debug printing.

    The library prints two lines to stdout on every simulation. A single calibration run produced
    2.8 MB of it, which the harness captures verbatim; a search making thousands of simulations
    would bury its own trajectory.
    """

    def __enter__(self):
        import contextlib
        import io

        self._redirect = contextlib.redirect_stdout(io.StringIO())
        self._redirect.__enter__()
        return self

    def __exit__(self, *exc):
        return self._redirect.__exit__(*exc)


def _profile(ladder, level):
    level = int(level)
    if level not in ladder:
        raise ValueError(
            "difficulty %d has no entry; measure its anchor before adding one" % level
        )
    return ladder[level]


def _draw_world(rng, profile, degenerate: bool):
    """One spin system: shifts in Hz and a symmetric coupling matrix."""
    n = profile["spins"]
    while True:
        shifts = sorted(rng.uniform(0.0, profile["shift_span"]) for _ in range(n))
        gaps = [shifts[i + 1] - shifts[i] for i in range(n - 1)]
        if min(gaps) >= profile["min_gap"]:
            break
    low, high = profile["j_range"]
    couplings = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            if rng.random() < profile["sparsity"]:
                continue  # a true zero, which is what the false-discovery axis tests
            value = rng.uniform(low, high)
            couplings[i][j] = couplings[j][i] = value
    if degenerate:
        # Make spins 0 and 1 magnetically equivalent. Their mutual coupling then has no effect on
        # the spectrum, so no method can recover it and the honest answer is to decline.
        shifts[1] = shifts[0]
        for k in range(2, n):
            couplings[1][k] = couplings[k][1] = couplings[0][k]
    return {"shifts": [float(s) for s in shifts], "couplings": couplings,
            "degenerate": degenerate}


def _simulate(world):
    """Peak list from the full Hamiltonian, via nmrsim."""
    nmrsim = _nmrsim()
    import numpy as np

    with _quiet():
        system = nmrsim.SpinSystem(
            list(world["shifts"]), np.array(world["couplings"], dtype=float),
            w=LINEWIDTH, second_order=True,
        )
        raw = system.peaklist()
    peaks = [(float(f), float(i)) for f, i in raw if i > 1e-6]
    peaks.sort()
    return peaks


def _generate(profile, tag):
    key = "worlds::%s::%s" % (tag, sorted(profile.items()))
    if key in _CACHE:
        return _CACHE[key]
    rng = random.Random(profile["seed"])
    worlds = []
    for index in range(profile["count"]):
        # Every third world is under-determined, so refusal is testable rather than always wrong.
        degenerate = index % 3 == 2
        world = _draw_world(rng, profile, degenerate)
        world["key"] = "w%d_n%d%s" % (index, profile["spins"], "_deg" if degenerate else "")
        world["peaks"] = _simulate(world)
        worlds.append(world)
    _CACHE[key] = tuple(worlds)
    return _CACHE[key]


def development_worlds():
    return _generate(_profile(_LADDER, DIFFICULTY), "dev")


def sealed_worlds():
    return _generate(_profile(_SEALED_LADDER, DIFFICULTY), "sealed")


def _observation(world):
    """What the candidate sees: the peak list and the spin count. Never the truth."""
    return {
        "peaks": [list(p) for p in world["peaks"]],
        "spins": len(world["shifts"]),
        "linewidth_hz": LINEWIDTH,
        "resolvable_coupling_hz": RESOLVABLE_J,
    }


def _parse(submission, n):
    if not isinstance(submission, dict):
        return None, "expected a dict, got %s" % type(submission).__name__
    if submission.get("abstain"):
        return {"abstain": True}, ""
    shifts = submission.get("shifts")
    couplings = submission.get("couplings")
    if shifts is None or couplings is None:
        return None, "missing 'shifts' or 'couplings' (or set 'abstain': True)"
    try:
        shifts = [float(x) for x in shifts]
        couplings = [[float(x) for x in row] for row in couplings]
    except (TypeError, ValueError):
        return None, "shifts and couplings must be numbers"
    if len(shifts) != n:
        return None, "expected %d shifts, got %d" % (n, len(shifts))
    if len(couplings) != n or any(len(row) != n for row in couplings):
        return None, "couplings must be %dx%d" % (n, n)
    if any(not math.isfinite(x) for x in shifts):
        return None, "non-finite shift"
    if any(not math.isfinite(x) for row in couplings for x in row):
        return None, "non-finite coupling"
    return {"abstain": False, "shifts": shifts, "couplings": couplings}, ""


def _match_shifts(truth, guess):
    """Best assignment of guessed shifts to true ones, since ordering is not observable."""
    import itertools

    n = len(truth)
    best = None
    for order in itertools.permutations(range(n)):
        error = sum(abs(guess[order[i]] - truth[i]) for i in range(n))
        if best is None or error < best[0]:
            best = (error, order)
    return best[1]


def _mechanism(world, parsed):
    """Shift and coupling recovery under the best permutation, scaled by what is resolvable."""
    truth_shifts = world["shifts"]
    truth_j = world["couplings"]
    n = len(truth_shifts)
    order = _match_shifts(truth_shifts, parsed["shifts"])
    shift_error = [abs(parsed["shifts"][order[i]] - truth_shifts[i]) for i in range(n)]
    # A shift is recovered if it lands inside two linewidths.
    shift_score = sum(1.0 for e in shift_error if e <= 2 * LINEWIDTH) / n

    pairs = [(i, j) for i in range(n) for j in range(i + 1, n)]
    # A degenerate world's 0-1 coupling is unobservable; it is excluded from scoring rather than
    # counted as a miss, because no method can recover it.
    if world["degenerate"]:
        pairs = [(i, j) for i, j in pairs if not (i == 0 and j == 1)]
    hits = claimed_false = 0
    true_zero = 0
    for i, j in pairs:
        truth_value = truth_j[i][j]
        guess_value = abs(parsed["couplings"][order[i]][order[j]])
        if truth_value >= RESOLVABLE_J:
            if abs(guess_value - truth_value) <= max(0.5, 0.1 * truth_value):
                hits += 1
        else:
            true_zero += 1
            if guess_value >= RESOLVABLE_J:
                claimed_false += 1
    real = sum(1 for i, j in pairs if truth_j[i][j] >= RESOLVABLE_J)
    coupling_score = hits / real if real else 1.0
    fdr = claimed_false / true_zero if true_zero else None
    return {
        "shift_recovery": shift_score,
        "coupling_recovery": coupling_score,
        "mechanism": 0.5 * shift_score + 0.5 * coupling_score,
        "false_discovery_rate": fdr,
        "true_zero_couplings": true_zero,
        "resolvable_couplings": real,
        "mean_shift_error_hz": sum(shift_error) / n,
    }


def _score_split(design_fn, worlds):
    rows = []
    for world in worlds:
        try:
            raw = design_fn(_observation(world))
        except Exception as exc:  # noqa: BLE001 - candidate faults are scored, not raised
            rows.append({"key": world["key"], "valid": False,
                         "reason": "raised: %s" % type(exc).__name__})
            continue
        parsed, why = _parse(raw, len(world["shifts"]))
        if parsed is None:
            rows.append({"key": world["key"], "valid": False, "reason": why})
            continue
        if parsed["abstain"]:
            rows.append({"key": world["key"], "valid": True, "abstained": True,
                         "degenerate": world["degenerate"],
                         "mechanism": 0.0,
                         "correct_refusal": bool(world["degenerate"])})
            continue
        metrics = _mechanism(world, parsed)
        metrics.update({"key": world["key"], "valid": True, "abstained": False,
                        "degenerate": world["degenerate"], "correct_refusal": False})
        rows.append(metrics)

    valid = [r for r in rows if r["valid"]]
    scored = [r for r in valid if not r.get("abstained")]
    degenerate = [r for r in valid if r["degenerate"]]
    fdrs = [r["false_discovery_rate"] for r in scored
            if r.get("false_discovery_rate") is not None]
    return {
        "rows": rows,
        "valid_count": len(valid),
        "world_count": len(worlds),
        # Mechanism over the worlds that are determined. Abstaining on a determined world scores
        # zero for it, so refusing everything cannot buy a good mechanism score.
        "mechanism": (sum(r["mechanism"] for r in valid if not r["degenerate"])
                      / max(1, sum(1 for r in valid if not r["degenerate"]))),
        "false_discovery_rate": (sum(fdrs) / len(fdrs)) if fdrs else None,
        "correct_refusal_rate": ((sum(1 for r in degenerate if r["correct_refusal"])
                                  / len(degenerate)) if degenerate else None),
        # Refusing a world that was in fact determined is the opposite error.
        "unwarranted_refusal_rate": (
            sum(1 for r in valid if r.get("abstained") and not r["degenerate"])
            / max(1, sum(1 for r in valid if not r["degenerate"]))
        ),
        # The same quantity the other way round, published because that is the one the discovery
        # report needs: whether a discovery was attempted where one was available. A task on which
        # every proposal declines every world otherwise looks exactly like a task nobody could do.
        "discovery_coverage": (
            sum(1 for r in valid if not r.get("abstained") and not r["degenerate"])
            / max(1, sum(1 for r in valid if not r["degenerate"]))
        ),
    }


def evaluate(infer_spin_system) -> dict:
    development = _score_split(infer_spin_system, development_worlds())
    valid = development["valid_count"] == development["world_count"]
    result = {
        # Mechanism recovery alone. The other two axes are reported beside it and must not be
        # folded in: averaging them is what lets a task look solved while its discoveries are wrong.
        "combined_score": float(development["mechanism"]) if valid else 0.0,
        "valid": 1.0 if valid else 0.0,
        "development_mechanism_score": development["mechanism"],
        "development_false_discovery_rate": development["false_discovery_rate"],
        "development_correct_refusal_rate": development["correct_refusal_rate"],
        "development_discovery_coverage": development["discovery_coverage"],
        "development_unwarranted_refusal_rate": development["unwarranted_refusal_rate"],
        "development_determined_world_count": sum(
            1 for w in development_worlds() if not w["degenerate"]),
        "development_undetermined_world_count": sum(
            1 for w in development_worlds() if w["degenerate"]),
        "per_instance": development["rows"],
        "difficulty": DIFFICULTY,
    }
    if valid:
        sealed = _score_split(infer_spin_system, sealed_worlds())
        result.update({
            "robustness_score": float(sealed["mechanism"]),
            "heldout_mechanism_score": sealed["mechanism"],
            "heldout_false_discovery_rate": sealed["false_discovery_rate"],
            "heldout_correct_refusal_rate": sealed["correct_refusal_rate"],
            "heldout_discovery_coverage": sealed["discovery_coverage"],
            "sealed_per_instance": sealed["rows"],
        })
    else:
        result["robustness_score"] = 0.0
    return result

"""Truth-blind reference: least-squares fit of the nmrsim forward model. Calibration only.

This is what spectral-fitting programs do - propose a spin system, simulate it with the full
Hamiltonian, compare the simulated peak list with the observed one, and iterate. The science is
nmrsim's; the search around it is ordinary numerical optimisation.

It never sees the truth. It reads only what a candidate reads.
"""

from __future__ import annotations

import random


def _peak_distance(a, b, linewidth):
    """Symmetric nearest-peak distance between two peak lists, weighted by intensity."""
    if not a or not b:
        return 1e6
    total = 0.0
    for freq, intensity in a:
        nearest = min(abs(freq - g) for g, _ in b)
        total += intensity * min(nearest / max(linewidth, 1e-6), 50.0)
    for freq, intensity in b:
        nearest = min(abs(freq - g) for g, _ in a)
        total += intensity * min(nearest / max(linewidth, 1e-6), 50.0)
    return total


def infer_spin_system(observation):
    import numpy as np
    import nmrsim

    peaks = [(float(f), float(i)) for f, i in observation["peaks"]]
    n = int(observation["spins"])
    width = float(observation["linewidth_hz"])
    rng = random.Random(1729 + n * 31 + int(sum(f for f, _ in peaks)))

    lo = min(f for f, _ in peaks) - 5.0
    hi = max(f for f, _ in peaks) + 5.0

    import contextlib, io

    def simulate(shifts, couplings):
        with contextlib.redirect_stdout(io.StringIO()):
            system = nmrsim.SpinSystem(list(shifts), np.array(couplings, dtype=float),
                                       w=width, second_order=True)
            raw = system.peaklist()
        return [(float(f), float(i)) for f, i in raw if i > 1e-6]

    def cost(shifts, couplings):
        return _peak_distance(peaks, simulate(shifts, couplings), width)

    best = None
    for _restart in range(6):
        shifts = sorted(rng.uniform(lo, hi) for _ in range(n))
        couplings = [[0.0] * n for _ in range(n)]
        current = cost(shifts, couplings)
        for _sweep in range(40):
            improved = False
            for i in range(n):
                for step in (8.0, 2.0, 0.5):
                    for sign in (1, -1):
                        trial = list(shifts)
                        trial[i] += sign * step
                        value = cost(trial, couplings)
                        if value < current:
                            shifts, current, improved = trial, value, True
            for i in range(n):
                for j in range(i + 1, n):
                    for step in (4.0, 1.0, 0.25):
                        for sign in (1, -1):
                            trial = [row[:] for row in couplings]
                            trial[i][j] = trial[j][i] = max(0.0, trial[i][j] + sign * step)
                            value = cost(shifts, trial)
                            if value < current:
                                couplings, current, improved = trial, value, True
            if not improved:
                break
        if best is None or current < best[0]:
            best = (current, sorted(shifts), [row[:] for row in couplings])
    return {"shifts": best[1], "couplings": best[2]}

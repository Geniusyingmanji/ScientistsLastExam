"""Truth-blind reference: forward-model least squares over the QuTiP propagator. Calibration only.

This is what device characterisation actually does - propose parameters, simulate the dynamics
with the same solver the experiment is compared against, score the residual against the measured
traces, and descend. The physics is QuTiP's; the search around it is coordinate descent with
restarts.

It never sees the truth. It reads only what a candidate reads.
"""

from __future__ import annotations

import random


def learn_hamiltonian(observation):
    import numpy as np
    import qutip

    n = observation["spins"]
    times = list(observation["times"])
    measured = np.array(observation["magnetisation"], dtype=float)
    rng = random.Random(4111 + n)

    def operators():
        sx, sy, sz = [], [], []
        for index in range(n):
            for store, op in ((sx, qutip.sigmax()), (sy, qutip.sigmay()),
                              (sz, qutip.sigmaz())):
                factors = [qutip.qeye(2)] * n
                factors[index] = op
                store.append(qutip.tensor(factors))
        return sx, sy, sz

    sx, sy, sz = operators()
    psi0 = qutip.tensor([qutip.basis(2, 0)] + [qutip.basis(2, 1)] * (n - 1))

    def residual(fields, couplings):
        H = sum(fields[i] * sz[i] for i in range(n))
        for i in range(n):
            for j in range(i + 1, n):
                if couplings[i][j]:
                    H += couplings[i][j] * (sx[i] * sx[j] + sy[i] * sy[j])
        got = qutip.sesolve(H, psi0, times, e_ops=sz)
        return float(np.sum((np.array(got.expect, dtype=float) - measured) ** 2))

    best = None
    for _restart in range(4):
        fields = [rng.uniform(-1.2, 1.2) for _ in range(n)]
        couplings = [[0.0] * n for _ in range(n)]
        for i in range(n):
            for j in range(i + 1, n):
                value = rng.choice([0.0, rng.uniform(0.4, 1.6)])
                couplings[i][j] = couplings[j][i] = value
        current = residual(fields, couplings)
        for step in (0.4, 0.15, 0.05):
            improved = True
            sweeps = 0
            while improved and sweeps < 8:
                improved = False
                sweeps += 1
                for i in range(n):
                    for sign in (1, -1):
                        trial = list(fields)
                        trial[i] += sign * step
                        value = residual(trial, couplings)
                        if value < current:
                            fields, current, improved = trial, value, True
                for i in range(n):
                    for j in range(i + 1, n):
                        for sign in (1, -1):
                            trial = [row[:] for row in couplings]
                            trial[i][j] = trial[j][i] = max(0.0, trial[i][j] + sign * step)
                            value = residual(fields, trial)
                            if value < current:
                                couplings, current, improved = trial, value, True
        if best is None or current < best[0]:
            best = (current, list(fields), [row[:] for row in couplings])
    return {"fields": best[1], "couplings": best[2]}

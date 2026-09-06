# Reference method and evidence boundary

## 1. Reference method and complete configuration

`verification/reference_method.py` is an independently executable, public-problem-only witness.
It returns one adaptive finite-volume method and does not import the evaluator or read the frozen
panel. The witness is a score-one normalization anchor, not a globally optimal numerical method.
It uses 192 cells, WENO3 face reconstruction, Superbee fallback, the exact scalar
Godunov flux, SSPRK3, CFL 0.70, sensor threshold 0.15, full shock blending, and the canonically
inactive Godunov dissipation value 1.0.

## 2. Baseline and development score

The baseline is the legal 32-cell piecewise-constant Rusanov/Euler method with CFL 0.45 and
dissipation multiplier 1.15. Its development raw utility is `0.4306775062` and normalizes to
`0.0`; the reference raw utility is `0.9705475629` and normalizes to `1.0`. A 48-point local
CFL/sensor grid found raw utility `0.9716657335` at CFL 0.85 and sensor threshold 0.10. This known
point is the wave ledger incumbent, so reconstructing it earns no lifetime credit. None of these
values is a convergence theorem or a published state of the art.

## 3. Held-out score

Held-out worlds do not enter `combined_score`. Their raw utilities are `0.4476810274` for the
baseline and `0.9720236480` for the reference. They cover a Gaussian advection pulse, a narrower
top-hat under negative advection speed, and a Burgers rarefaction, but remain repository-visible
synthetic checks rather than fresh external confirmation.

## 4. Ablation ladder

Six targeted ablations all reduce development utility relative to the reference:

| ablation | normalized score |
|---|---:|
| no sensor blend | 0.978250 |
| sensor threshold 0.95 | 0.994197 |
| MUSCL instead of WENO3 | 0.973684 |
| 128 instead of 192 cells | 0.990420 |
| SSPRK2 instead of SSPRK3 | 0.985257 |
| joint solver+dissipation change to Rusanov at 1.5 | 0.996005 |

## 5. Shortcut probes

An earlier 216-point audit invalidated the original construction: a method with no sensor blend
scored `1.104486`, showing that its advertised adaptivity was harmful. That version was not frozen.
After rebuilding the oracle around WENO3 with sensor-triggered fallback, a 432-method nonadaptive
grid over reconstruction, limiter, flux, integrator, resolution and CFL reached at most
`0.988555`. Its best point was 192-cell MUSCL/MC/Godunov/SSPRK3 at CFL 0.85. This grid is a
documented shortcut probe, not proof that no stronger low-dimensional shortcut exists.

## 6. Construction history and frontier draw

The first construction used only MUSCL/TVD choices and multiplied every slope by a curvature
suppression factor. Builder review found that removing this advertised adaptive mechanism improved
the score, so that construction was rejected before freeze. The replacement adds WENO3 face
states with sensor-triggered fallback and binds every scoring constant plus the complete evaluator
oracle. A later review found that the agent-visible example leaked the exact score-one method and
that inactive fallback coordinates produced distinct canonical IDs; both were repaired before any
model draw. HY3 normal versus selection-blind calibration remains deliberately pending until the
committed task/runtime hashes are frozen.

## 7. Robustness, cost, limitations and provenance

The reference uses a mean of 46,656 cell-stage updates on development worlds and 45,120 on held-out
worlds; the baseline means are 688 and 661.33. Every accepted update uses one shared conservative
face flux, so conservation is a validity/integrity gate rather than the main scientific estimand;
the latter is the accuracy--stability--work tradeoff under a hard work budget. Target cell averages now use
closed-form antiderivatives instead of subcell quadrature. A separate implementation that imports
neither the primary oracle nor its panel agrees for baseline, reference, incumbent and six ablations
across all seven worlds: L1 within `2e-9`, work exactly, each balance below `1e-12`, and raw utility
within `2e-6`, with the same ordering. Tests also cover ninety one-step DSL grid points representing
sixty-six canonical methods,
fourteen malformed in-process shapes, ten JSON-safe malformed sandbox shapes, nonfinite transport
rejection, inconsistent calls, exceptions, session isolation, deterministic replay, black-box
reference execution, canonical inactive-coordinate collapse, the complete 432-method probe and
work-budget rejection. The cell follows van Leer's
conservative reconstruction (DOI
`10.1016/0021-9991(79)90145-1`), Shu and Osher's SSP integration (DOI
`10.1016/0021-9991(88)90177-5`), and Jiang and Shu's WENO construction (DOI
`10.1006/jcph.1996.0130`). It tests only seven visible one-dimensional scalar-law worlds on uniform
grids. It omits multidimensional meshes, systems, stiffness, entropy proofs, general positivity,
parallel cost and application validation. The fixed wave has bounded coordinates and resource
envelopes, while its score is not clipped at the reference; only verified future immutable waves
can extend lifetime family credit.
External numerical-PDE review and HY3 calibration are still missing, so this package remains a
candidate.

# WallClosureDiscovery — measured values

All numbers are reproducible from `verification/`.

## Solver validation, and what it does not prove

| Re_tau | fitted kappa | log-law intercept B | U+ at y+ = 1.0 |
|---|---|---|---|
| 1000 | 0.418 | 5.32 | — |
| 2000 | 0.421 | 5.48 | — |
| 5200 | 0.421 | 5.55 | 1.01 |

The closure was given `kappa = 0.41`, so recovering 0.418–0.421 by fitting the solver's own output
validates **the quadrature**, not the physics. The highest-Reynolds-number channel DNS measures
`kappa = 0.384 ± 0.004` (Lee & Moser, *JFM* **774** (2015) 395), which is not 0.41; that
disagreement is live and this task does not adjudicate it.

The first attempt wrote the closure as an explicit `nu_t+(y+)` and produced a fitted kappa between
**13 and 31**. The implicit coupling between eddy viscosity and mean gradient is what produces the
log law; dropping it does not approximate the physics, it destroys it.

The grammar reproduces van Driest in **11 nodes** to `3.55e-15` against the direct implementation.

## World calibration, in four measurements

**1. The third regime, first version, was unanswerable everywhere.** It put structure above the
largest sampled `y+`. That structure is unconstrained in *every* regime, so blanket abstention
would have been correct everywhere and the task would have measured nothing. Discarded.

**2. Starving the data does not separate the regimes.** Reporting the profile binned instead of at
all 400 solver nodes, swept against the systematics:

| bins | recoverable passes | degenerate passes | inconsistent passes |
|---|---|---|---|
| 24 | 8/8 | 7/8 | 0/8 |
| 12 | **0/8** | 2/8 | 0/8 |
| 8 | 0/8 | 0/8 | 0/8 |

There is no window: at 24 bins the degeneracy does not bite, at 12 the answerable regime has
already broken.

**3. Fitting the nuisances is what reveals the regime.** Truth `(kappa, A+) = (0.41, 26.0)`:

| span | nuisances fitted | best kappa | 1-sigma width |
|---|---|---|---|
| wide 180/950/4000 | no | 0.413 | 0.029 |
| wide 180/950/4000 | yes | 0.398 | **0.054** |
| narrow 180/200/220 | no | **0.501** | 0.078 |
| narrow 180/200/220 | yes | 0.413 | **0.112** |

Two readings. The narrow span carries twice the uncertainty, so the regime is real. And a fit that
ignores the two per-profile systematics is **biased**, not merely uncertain — 0.501 against 0.410,
twenty-two per cent high — because they have nowhere to go except into `kappa`. That is the failure
mode this subject has, and it appeared without being put there.

**4. Widening the Reynolds span does not help; the tolerance is the lever.**

| sampled Reynolds numbers | 1-sigma width in kappa | implied held-out spread |
|---|---|---|
| 180 / 200 / 220 | 0.112 | 1.90 |
| 180 / 950 / 4000 | 0.054 | 0.91 |
| 180 / 1500 / 8000 | 0.058 | 0.99 |
| 200 / 2000 / 10000 | 0.054 | 0.91 |

What limits `kappa` is the two unknown nuisances per profile, not the Reynolds range. The tolerance
was set to 6 % of centreline velocity (about 1.3), which the answerable regime clears at 0.91 with a
factor of 1.4 in hand and the degenerate regime misses at 1.90 by the same factor — margin on both
verdicts instead of one of them sitting on the line.

## The two refusal reasons are orthogonal, and one is a trap

Per regime, with the nuisances projected out:

| regime | reduced chi-square | admissible kappa width |
|---|---|---|
| `recoverable` | 0.23 – 0.51 | **0.025 – 0.045** |
| `degenerate_parameters` | **0.11 – 0.20** | 0.050 – 0.105 |
| `inconsistent` | **0.71 – 2.30** | 0.050 – 0.110 |

Width separates the answerable regime; the residual separates the inconsistent one. They are
different tests and a searcher needs both. And `degenerate_parameters` has the *lowest* residuals of
the three — its fits look better than the answerable ones. That is the trap, and it is not placed by
hand: it is what happens when a whole interval of closures explains the data equally well.

With two fixed Reynolds spans these gaps are clean and a pair of thresholds scores 1.0, so the top
Reynolds number is drawn from overlapping ranges — 700–4000 for the answerable regime, 230–900 for
the others.

## Baseline and reference

| submission | combined | mechanism | FDR | refusal | coverage | abstentions |
|---|---|---|---|---|---|---|
| baseline | **0.000000** | 1.000 | 0.333 | 0.000 | 1.000 | none anywhere |
| reference | **0.710938** | 0.875 | 0.000 | 0.812 | — | degenerate 5/8, inconsistent 8/8, recoverable 1/8 |

The baseline recovers the law on every answerable case and scores zero, because it never abstains.
That is the point of it: the fitting is not the hard part.

The reference misses three of eight degenerate cases and abstains once when it should not have. The
headroom is in the regime the literature is about.

## Robustness

Nineteen degenerate and adversarial submissions score 0.000000 without raising: blanket abstention,
never abstaining, the textbook van Driest closure submitted blindly, a constant closure, a zero
closure, a negative closure, guessing without observing, `None`, `{}`, a non-boolean abstain flag, a
NaN confidence, an out-of-range confidence, not abstaining without a formula, an unknown operator,
an unknown variable, a float constant, a zero-denominator constant, an over-cap expression, a
raising callable, flooding the observation budget, and observing an unsampled Reynolds number.

**The sharpest is the textbook closure.** Submitting van Driest with the published constants scores
**0.000000** while reaching a mechanism score of **0.750** and a false discovery rate of 0.458. The
hidden constants are drawn near the published ones, so a blind submission lands 6 of 24 cases — and
it still scores nothing, because two thirds of the cases should not receive a formula at all and it
submits one everywhere.

That is the cleanest statement of what this task measures. Recall buys a recovery number that looks
good in isolation and is worth zero once the refusal axis is in the report.

An earlier configuration of this task did give this submission a false discovery rate of 1.00, and
the claim was written down before the Reynolds spans became a continuum and the tolerance moved to
6 %. It is corrected here rather than carried forward.

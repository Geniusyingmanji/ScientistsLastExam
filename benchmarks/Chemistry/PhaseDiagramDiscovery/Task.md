# PhaseDiagramDiscovery

## The question

An isothermal section of a binary system A-B. You have a synthesis budget: each call prepares one
composition and returns its powder diffraction pattern. Which equilibrium phases exist, over
which composition ranges - or does this system not support an equilibrium answer at all?

## Three traps, none visible in a single pattern

- **A two-phase field looks like a new compound.** Between two single-phase regions, every
  pattern is a lever-rule superposition of the two neighbours: more peaks than either, and
  distinct-looking. The test is whether it decomposes as a mixture of its neighbours' signatures.
- **An impurity looks like a real peak.** A contaminant appears in a minority of syntheses,
  adding a few weak peaks that belong to no equilibrium phase. One pattern cannot tell; a
  replicate can, because the impurity does not reproduce.
- **A trapped system looks like data.** In some systems the middle of the diagram never reaches
  equilibrium: repeated synthesis at one composition freezes in a different mixture each time,
  with transient peaks that never reproduce. No equilibrium phase set is supported, and the
  honest answer is to decline rather than publish whichever mixture appeared.

## Where the budget actually goes

Boundaries are the expensive part, and the lever rule is the cheap way to them: in the gap
between phases p and q the mixing fraction is **linear in composition**, zero at p's boundary and
one at q's. Two or three measured fractions inside a gap fit a line whose intercepts are both
boundaries at once. Bisection pays four or five syntheses for one boundary; the regression pays
one or two for two. Fractions should be normalised by each phase's pure-pattern intensity, or the
fit inherits a bias toward whichever phase scatters more.

Note the detection limit: a minority phase at fraction 0.2 puts every one of its peaks below any
"strong peak" threshold you might use for signature discovery. Signatures and fractions need
different floors.

## What you implement

```python
def discover_phases(problem, synthesize):
    ...
    return {"phases": [...], "confidence": ..., "abstain": False}
```

### `problem` - every key you are given

| key | meaning |
|---|---|
| `synthesis_budget_calls` | how many syntheses you may run on this system (26) |
| `composition_bounds` | `[0.0, 1.0]`; compositions must lie inside |
| `two_theta_bounds` | `[10.0, 90.0]`; all peak positions live here |
| `position_noise_sigma` | Gaussian noise on each reported peak position (0.08) |
| `intensity_noise_relative` | relative Gaussian noise on each intensity (0.05) |
| `detection_limit` | peaks weaker than this are not reported (0.06) |
| `max_claimed_phases` | at most this many phases may be claimed (6) |
| `measurement_model` | prose: what a synthesis returns |
| `impurity_model` | prose: how the contaminant behaves |
| `abstain_when` | prose: when no equilibrium phase set is supported |

### `synthesize(composition)`

Returns one pattern: a list of `{"two_theta": ..., "intensity": ...}` peaks, sorted by position.
Compositions must be finite and inside `[0, 1]` or the call raises. Calling past the budget
raises and the world scores zero, so count your calls.

Repeating a composition re-draws the noise, the impurity, and - in a trapped system - the
frozen-in mixture. That is what makes replication informative, and it costs budget.

### What you return

| key | meaning |
|---|---|
| `phases` | one entry per claimed phase: `{"composition_range": [lo, hi], "peak_two_thetas": [...]}` |
| `confidence` | in `[0, 1]`; clipped |
| `abstain` | `True` to decline: this system supports no equilibrium phase set |

Ranges must satisfy `0 <= lo < hi <= 1`, must not overlap between phases, and each claim carries
1-12 peak positions inside `two_theta_bounds`. Anything malformed scores that world zero. It is
never an infrastructure failure.

## How you are scored

Each system contributes a mechanism score:

- **an equilibrium answer exists**: your claimed phase set must match the truth **exactly** - each
  claim matched to a distinct true phase by its peaks, no true phase missing, no extra claim. The
  set is gated: wrong set, zero, however good the boundaries. With the set right, the score is
  the mean boundary accuracy over the interior boundaries (the endpoints 0 and 1 are free), full
  marks near 0.005, zero at 0.05.
- **the system is trapped**: declining scores 1, publishing a diagram scores 0.

`combined_score` is the mean of those, renormalised so that **declining every system scores
exactly 0.0**.

Reported separately, never averaged into one number:

`phase_set_rate` · `boundary_score` · `false_phase_rate` (a claim matching no true phase - a
superposition or an impurity promoted to a compound) · `false_discovery_rate` ·
`correct_refusal_rate` · `discovery_coverage` · `confidence_calibration`

A sealed held-out set of eight further systems is scored too and is not visible to a searcher.

## What each competence is worth

Ablating the reference - the same phase identification everywhere, only one skill removed at a
time:

| strategy | score | phase set | boundaries | false phases | false discovery |
|---|---|---|---|---|---|
| decompose + replicate + lever regression | **0.730** | 1.00 | 0.730 | 0.00 | 0.00 |
| same identification, grid-midpoint boundaries | 0.006 | 1.00 | 0.006 | 0.00 | 0.00 |
| same everything, never declining | 0.444 | 1.00 | 0.730 | 0.00 | 1.00 |
| uniform grid, no decomposition, no replicates | 0.000 | 0.00 | 0.100 | 0.86 | 1.00 |
| declining everything | 0.000 | - | - | 0.00 | 0.00 |

The gaps between single-phase regions are 0.2-0.3 wide, so grid midpoints miss boundaries by ~0.1
and the lever regression is worth +0.72 on its own. Knowing when to decline is worth +0.29. The
reference spends 13 of its 26 calls; what the other 13 could buy is left on the table.

## Rules

- Only edit `solution.py`; keep `discover_phases(problem, synthesize)`.
- `sle.contract_lint` is importable and free to call for shape checks. It costs no oracle call.
- Do not read `verification/` or `frontier_eval/`.

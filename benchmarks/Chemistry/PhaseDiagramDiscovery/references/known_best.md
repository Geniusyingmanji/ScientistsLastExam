# PhaseDiagramDiscovery - reference results

Every number here is produced by running code in this directory. Nothing is copied from a table.

## Reproducing

```
python3 frontier_eval/run_eval.py --candidate verification/reference_mapping.py \
    --metrics-out /tmp/metrics.json
```

## Reference - `verification/reference_mapping.py`

Truth-blind: it reads only the public problem and the budgeted synthesizer.

| metric | development | held out |
|---|---|---|
| mechanism score (normalized) | **0.7300** | 0.7522 |
| phase set rate | 1.00 | 1.00 |
| boundary score | 0.730 | - |
| false phase rate | 0.00 | 0.00 |
| false discovery rate | 0.00 | 0.00 |
| correct refusal rate | 1.00 | 1.00 |
| synthesis calls | 13.4 of 26 | - |

Its design: one synthesis at each terminal to anchor the two solid-solution signatures; three
replicates at mid-composition *before anything else is bought* - a trapped system swings its
terminal-phase share between replicates and its transient peaks never reproduce, so nothing
downstream is worth paying for; a nine-point interior scan; iterative signature peeling for the
intermediate compounds; and lever-rule regression for every boundary, with fractions normalised
by pure-pattern intensities.

**The reference is deliberately not at the ceiling.** It gets every phase set right and every
refusal right, and its boundary score is 0.730 on half its budget. The 13 unspent calls - more
gap points, replicate averaging of fractions, targeted syntheses near the fitted intercepts - are
the headroom a better searcher is supposed to claim. This is the admission bar recorded in the
card: a first model proposal that reaches the reference means the task needs hardening before it
is anything more than an on-ramp.

## Model draw - Claude Opus 5, 2026-09-02

`experiments/opus5_phase_diagram_calibration_2026-09-02_v2.json`, a clean-revision run (the first
run was on a dirty tree and was discarded). Three seeds, three proposals each, greedy_rewrite,
normal feedback. The admission bar this task was built under: a first proposal must not reach the
reference.

| seed | baseline | proposal 1 | proposal 2 | proposal 3 | best |
|---|---|---|---|---|---|
| 0 | 0.0000 | 0.1010 | 0.0000 | 0.0000 | 0.1010 |
| 1 | 0.0000 | **0.6706** | 0.3783 | 0.3657 | 0.6706 |
| 2 | 0.0000 | 0.3402 | 0.0000 | 0.0000 | 0.3402 |

**No proposal reached the reference's 0.730, so the admission bar holds and the task is
unsaturated at the frontier.** The best of nine proposals is 0.6706, and the layered headroom is
real: model best 0.671, reference 0.730, ceiling 1.0.

What the axes say is more specific than the scalar. On seed 1's first proposal the phase set is
**exactly right** (phase_set_rate 1.0) and the shortfall is entirely in the boundaries
(boundary_score 0.67 against the reference's 0.73) - the model identifies which phases exist but
does not place their limits as well as the lever-rule regression does, which is precisely the
skill this task isolates. Its false-phase rate starts at 0.86 on the baseline and drops to
0.00-0.14 on the better proposals.

One caveat, stated because a 3-proposal single arm cannot support more: the best proposal is
usually the *first* one here, not a later one, so this run is evidence of headroom, not of
feedback-driven improvement. Whether iteration pays on this task needs the paired
`selection_blind` arm and a longer budget, which have not been run.

## Baseline - `solution.py`

A 13-point uniform grid; every distinct-looking pattern becomes a phase; boundaries at grid
midpoints; no replication; never declines.

| metric | value |
|---|---|
| combined score | **0.0000** |
| false phase rate | 0.86 |
| false discovery rate | 1.00 |
| discovery coverage | 0.86 |

Confidently wrong rather than empty: two-phase superpositions and impurity peaks enter its phase
list, and trapped systems get published as equilibrium diagrams. Blanket abstention also scores
0.0000 with false-phase 0.00 and coverage 0.00 - the same scalar from the opposite direction,
which is why the axes are reported separately.

## Difficulty ladder

Ablations of the reference: the same phase identification everywhere, one skill removed at a time.

| strategy | score | phase set | boundaries | false phases | false discovery | held out |
|---|---|---|---|---|---|---|
| decompose + replicate + lever regression | 0.7300 | 1.00 | 0.730 | 0.00 | 0.00 | 0.7522 |
| same identification, grid-midpoint boundaries | 0.0060 | 1.00 | 0.006 | 0.00 | 0.00 | 0.0131 |
| same everything, never declining | 0.4443 | 1.00 | 0.730 | 0.00 | 1.00 | 0.4188 |
| uniform grid, no decomposition, no replicates | 0.0000 | 0.00 | 0.100 | 0.86 | 1.00 | 0.0000 |
| declining everything | 0.0000 | - | - | 0.00 | 0.00 | 0.0000 |

The interior gaps are 0.2-0.3 wide, so grid midpoints miss boundaries by ~0.1: the lever-rule
regression is worth +0.72 on its own, which makes boundary placement - not phase spotting - the
score-carrying skill. Declining where it is right is worth +0.29.

## Two build errors this went through, both found by measuring

- **One intensity floor where two were needed.** The first reference reused its strong-peak floor
  (0.27, chosen to sit above the impurity) for fraction estimation. A minority phase at fraction
  0.2 puts every peak below that floor, so most scan points inside two-phase fields read as pure,
  the lever regressions starved, and the reference scored 0.075. Signature discovery needs the
  floor; fraction estimation needs the whole pattern with the known signature doing the impurity
  rejection. The fix moved the reference to 0.615 before any other change.

- **Support clustering merges adjacent compounds.** Grouping residual peaks by which scan points
  share them cannot separate two intermediate compounds: in the gap between them every pattern
  carries both signatures, so their supports always touch and both two-compound worlds came back
  as one claimed phase. Iterative peeling - identify the purest unexplained point, read one
  signature there, subtract, look again - fixed both without extra budget.

## Robustness

- Twelve malformed candidate shapes - raising, empty, `None`, a string, an empty phase list,
  an inverted range, overlapping ranges, a NaN peak, an out-of-window peak, too many phases,
  overspending the budget, and an out-of-range composition - all score zero with `valid = 0`,
  and none raises out of the evaluator.
- Two consecutive evaluations of the reference are key-identical; the reference's largest spend
  is 19 of 26 calls.
- Declining every world scores exactly 0.0 by construction of the normalisation.

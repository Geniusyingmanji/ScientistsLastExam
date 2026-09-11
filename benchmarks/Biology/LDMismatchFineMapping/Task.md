# LDMismatchFineMapping: which variants are causal, when the public LD panel is not the cohort?

## 关系与区别 / How this differs from the nearest tasks in this repository

- **`PopulationGenetics/DemographicSFS`** is the other population-genetics task. It recovers a
  population-size history from a site-frequency spectrum, one number per epoch. Here the object
  is a **set of causal variants** at one locus and their effects, the data are association
  statistics from twenty thousand people, and the trouble is linkage disequilibrium, which the
  site-frequency spectrum never sees.
- **`Microbiology/MetagenomeCompositionAssignment`** is the other Biology task in the substance
  cell. It says which marker profiles of a fixed library are present in a read mixture, and
  declines when the library cannot explain the counts. Here the library is not the problem: the
  candidates are sixty typed variants and the question is which of them, correlated through a
  haplotype structure the candidate is only shown an approximation of, carry the effect.
- **`Ecology/OccupancyDetectionDesign`** and **`Phylogenomics/AnomalyZoneSpeciesTree`** also buy
  data under a budget. Their purchases are surveys and loci, independent draws of the same
  process; here every purchase is one row of a fixed correlation matrix, the budget is six rows
  out of sixty, and the whole game is which rows.
- **`Physics/HiddenCouplingNetwork`** infers a coupling graph from dynamics. There is no dynamics
  here and no graph to recover: the correlation structure is the nuisance, and the answer is a
  set of one to three indices with a signed number each.

No task in the Frontier-Eng catalogue concerns genome-wide association, linkage disequilibrium
or statistical fine-mapping.

## Admission revision and scope

Current Linux construction screen (Python 3.8.10, NumPy 1.24.4, SciPy 1.10.1, one numerical
thread; source `83e2e3c7`):

| method | development | heldout | development false-verdict rate |
|---|---:|---:|---:|
| complete masking-aware reference | 0.96183425 | 0.94551825 | 0.000000 |
| original region-wide reference, omitting the local test | 0.806301625 | 0.74832275 | 0.000000 |
| strongest fixed-grid shortcut: two ranked rows and conditional selection | 0.5568645 | 0.25574175 | 0.166667 |
| baseline panel clumping | 0.000000 | 0.004447 | 0.833333 |

All 1120 prespecified strategies executed and were valid on every world. The grid maximum is
0.5568645; the largest heldout score among grid cells is 0.510255. The independent enumeration
of every equal-size causal configuration, including joint replacements, found all alternative
configurations outside the designated ambiguous pair at least 6.19119 below the generating
configuration. Twenty-nine reference/ablation/control rungs were rerun; the deliberately
overspending eight-row control was invalid and is not difficulty evidence. Cold construction
of the 18 worlds took 23.142 seconds after reusing genotype sufficient statistics; independent
per-variant least-squares regression tests verify the algebraic optimization.

These measurements were an in-process construction screen, not the sandbox contribution gate
or model calibration. The full source-bound compact record and raw artifact hashes are in
`.research/ld_mismatch_fine_mapping/admission_2026-09-11.json`; the machine contract separately
pins the standalone reference and shortcut candidates for sandbox validation.


The current complete reference is `verification/reference_masking_aware.py`. It includes the
masking-aware local conditional test and an exact conversion from marginal t-statistics to joint
per-allele estimates. The older region-wide method is retained as an ablation. Numerical tables
below describe the original builder revision, before correcting the truth units to use the
standard deviation of the actual accepted phenotype draw; they are historical construction
results, not current admission measurements. The task card distinguishes newly measured shortcut
declarations and frontier calibration from those historical numbers.

The summary-statistic likelihood is a working RSS approximation to the marginal t-statistics.
The unresolved verdict means the specified finite-sample configuration gap is too small at this
fixed cohort size; it does not assert that arbitrarily more data could never distinguish two
variants with correlation below one. This curated synthetic challenge does not estimate the
prevalence of these cases in real GWAS data.

Each world starts a fresh candidate process with fresh imported-module state and private tmpfs.
All paid and repeat LD-row callbacks within that world share its session. State cannot carry
from one development world to another or from development to heldout.

## The question

A genome-wide association study of 20000 unrelated people regressed a quantitative trait on each
of sixty typed variants at one locus and found a signal. You are given the marginal z-score,
standard error and allele frequency of every variant, and the correlation matrix of the same
sixty variants in a public reference panel of 500 people from a related population. Say which
variants are causal, with their per-allele effects on the standardised trait, or say that the
association cannot be resolved to a causal set. You may buy in-sample linkage disequilibrium: the
exact correlation of one variant of your choice with all sixty, measured in the study cohort
itself, at one unit per row, under a budget of six rows.

## Five ways to be wrong

- **The panel is not the cohort.** The reference panel's correlations differ from the cohort's
  by an amount that is not published: over the eighteen graded worlds the mean absolute
  difference on correlated pairs is 0.07 to 0.17, and the largest single difference 0.34 to 0.83.
  A fine-mapping that trusts the panel is confident and wrong (Benner et al. 2017). In every
  single-variant world the causal variant has a proxy that the cohort correlates with it at
  r-squared 0.30 to 0.39 and the panel at 0.09 or less, and that proxy is itself genome-wide
  significant, at |z| 6.1 to 9.2. Clumping on the panel reports two independent signals where
  there is one, conditional analysis on the panel keeps both, and either is a false discovery.
  Fed the panel's rows in place of the cohort's, the reference itself falls from 0.806 to 0.000.
- **A masked variant has no marginal signal.** In the masked worlds two causal variants sit in
  the same haplotype block, correlated at 0.71 to 0.81 in the cohort, with effects of opposite
  sign, the second 49 to 62 per cent of the first in size. The second variant's marginal z-score
  is 2.6 to 4.6 in absolute value, below genome-wide significance at rank 4 to 8 of sixty, and
  in all five masked worlds it carries the wrong sign. The marginal scan never calls it, clumping
  never sees it, and a stepwise conditional analysis on the panel's correlations has the
  residual wrong. It appears only in the residual of the lead variant computed with the cohort's
  own row, where its conditional chi-square is 11.2 to 12.6.
- **Every world has a second hit, and most of them are noise.** Given the exact rows of the
  causal variants, exactly one non-causal variant in every typed or unresolved world has a
  conditional chi-square of 9.5 to 12.6, the same band as the masked partner's, and no other
  non-causal variant comes near it. That decoy is genome-wide significant on its own, at |z|
  5.5 to 8.1, and its cohort correlation with every causal variant is 0.30 or less, so
  clumping at any threshold takes it as an independent signal, on the panel and on the
  cohort's own rows alike. It is a fluctuation of the scan. A region-wide selection line cannot
  separate the two: the band sits above the plain BIC line of 9.9 and around the Bonferroni line
  of 11.2 for sixty variants at 0.05, and every line that takes the masked partners takes decoys
  with them. The reference, which uses one region-wide line, takes neither and names only the
  lead of every masked pair. What distinguishes a masked partner from a decoy is not its
  chi-square but where it sits.
- **Three signals, one ranking.** In the multi-signal worlds three causal variants sit in three
  haplotype blocks with marginal |z| of 5.9 to 8.6, 9.3 to 12.9 and 16.1 to 18.3. The strongest
  block's proxies fill the top of the ranking, so the weakest signal ranks 9th to 20th by |z|.
  Rows bought for the six largest |z| are spent on proxies of one signal and never reach the
  third: that strategy scores 0.382 against the reference's 0.806.
- **An unresolvable pair.** In the unresolved worlds a causal variant has a near-duplicate, a
  typed variant whose genotypes coincide with its own on 99.6 per cent or more of cohort
  haplotypes, so that the two are correlated at 0.992 to 0.996 in the cohort. The panel shows
  the same pair at 0.57 to 0.86, because the mutation that separates them arose on a haplotype
  background that is common in the panel's population and rare in the cohort's. The panel says
  the pair is resolvable and the cohort says it is not: the two configurations differ by 0.3 to
  1.3 in twice the log-likelihood, where no configuration outside the pair comes within 11.
  In four of the six unresolved worlds the pair is the weakest of three signals, at |z| 5.1 to
  7.2 and rank 12 to 19, behind the proxies of two stronger signals in other blocks, so rows
  spent by rank never reach it. Naming either member is a claim the data cannot support.
  Nothing in the public problem says which worlds are unresolved: the panel shows an ordinary
  pair of proxies, and the evidence is in rows you have to think to buy.

What resolvable means is fixed by the cohort's own linkage disequilibrium and the
summary-statistic likelihood z ~ N(R lambda, R) (Zhu and Stephens 2017), under which twice the
maximised log-likelihood of a configuration S is z_S' R_SS^-1 z_S. Every typed world has its
causal set at least 6 ahead of every configuration that swaps one member for another typed
variant, the graded worlds are at 6.2 to 134.4. Every unresolved world has the two members of
its pair within 2 of each other and the pair at least 6 ahead of everything else. A candidate
that names a causal set in an unresolved world, either member, is a false discovery; one that
declines a typed world is a false discovery too, since it claims an ambiguity that is not there.

## Where the budget actually goes

Six rows out of sixty. The reference's chase of the residual models every world with 2.4
rows on average and spends the rest on the closest proxy of each variant it has modelled, the
weakest first, which is where a near-duplicate is found: stopping when the chase stops leaves
every unresolved world unrecognised and scores 0.306. Three or four rows score 0.507, so the
budget is not free, rows bought by marginal rank rather than by residual score 0.382 at the
same six, and proxy rows spent on the largest predicted z-scores rather than one per modelled
variant score 0.431, because they all go to the strongest signal's neighbours.

## What you implement

```python
def fine_map(problem, ld_row):
    ...
    return {"verdict": "typed", "causal": [17, 42], "effects": [0.11, -0.08], "confidence": 0.8}
```

### `problem` — every key you are given

| key | meaning |
|---|---|
| `n_variants` | 60, the typed variants at the locus, indexed 0 to 59 in position order |
| `n_gwas` | 20000, the cohort size |
| `n_reference` | 500, the reference panel size |
| `row_budget` | 6, how many rows you may buy in this world |
| `max_causal` | 3, the most causal variants any world has |
| `z` | the marginal z-score of each variant in the cohort |
| `standard_error` | the marginal per-allele standard error of each variant |
| `allele_frequency` | the frequency of the counted allele of each variant in the cohort |
| `reference_ld` | the 60 by 60 sample correlation matrix of the variants in the reference panel |
| `association_model` | prose: an additive quantitative trait with unit variance, at most `max_causal` causal variants, every causal variant typed |
| `reference_ld_model` | prose: a related population whose haplotype frequencies differ from the cohort's by an unpublished amount |
| `row_model` | prose: what `ld_row` returns and costs |
| `abstain_when` | prose: when the verdict is `unresolved` |
| `answer_format` | prose: what a typed verdict must contain |

### `ld_row(variant)`

Charges one unit and returns a list of sixty floats: the exact correlation of `variant` with
every typed variant in the study cohort, `variant` being an integer index. Buying a row twice
returns the same row and is charged once. Buying past `row_budget` raises and the world scores
zero, so count your rows.

### What you return

| key | meaning |
|---|---|
| `verdict` | `"typed"` or `"unresolved"` |
| `causal` | required when the verdict is `typed`: one to `max_causal` distinct integer indices |
| `effects` | required when the verdict is `typed`: one finite per-allele effect on the standardised trait per causal variant, in the same order; the sign matters |
| `confidence` | in `[0, 1]`; clipped |
| `abstain` | `True` is accepted as a synonym for the unresolved verdict |

Anything malformed scores that world zero. It is never an infrastructure failure.
`sle.contract_lint` is importable and free to call for shape checks; it costs no row.

## How you are scored

Twelve development worlds: three single-variant, three masked, two multi-signal, four
unresolved, of which one has a single signal and three have the pair as the weakest of three.
Each contributes a mechanism score:

- **typed world**: a causal set that names no non-causal variant scores
  `F1 * (0.5 + 0.5 * effect_score)`, where F1 is the set overlap with the truth and the effect
  score is the mean over the named variants of `exp(-|ln(estimate / truth)|)`, zero for a wrong
  sign, so an effect off by a factor of two scores 0.5 on that variant. Naming any non-causal
  variant scores 0 and is a false discovery whatever the confidence. Declining scores 0 and is a
  false discovery.
- **unresolved world**: declining scores 1 and is a correct refusal; any causal set scores 0 and
  is a false discovery.

`combined_score` is the mean over the development worlds, renormalised so that **declining every
world scores exactly 0.0**. Naming one fixed variant everywhere also scores 0.0, and naming the
top variant by |z| everywhere scores 0.180. `confidence` feeds only the calibration axis: it
cannot lower the false discovery rate.

Reported separately, never averaged into one number:

`development_set_f1` · `development_effect_score` · `development_false_discovery_rate` ·
`development_correct_refusal_rate` · `development_discovery_coverage` ·
`development_confidence_calibration` · `development_mean_rows_bought` ·
`development_raw_mechanism`

Each split also publishes `world_count`, `valid_count`, `determinable_world_count`,
`unsupported_world_count`, `false_discovery_count`, `correct_refusal_count`,
`discovery_attempt_count`, and `mechanism_score_sum`, with that split's prefix. False discovery
here is the number of false scientific verdicts divided by **all worlds**, not FDR conditional
on making a claim. Refusal divides by unsupported worlds; discovery coverage divides by
determinable worlds. Invalid worlds stay in these denominators and earn no refusal credit.
Mechanism is `(mechanism_score_sum - unsupported_world_count) / determinable_world_count`,
clipped to `[0, 1]`. The card records these separate estimands for the reporting layer.

A sealed held-out set of six further worlds, one single, two masked, one multi-signal and two
unresolved, is scored too, under the same keys with the `heldout_` prefix, and is not visible to
a searcher. `per_instance` carries one row per world.

## What each competence is worth

Ablating the reference, one choice changed at a time:

| strategy | score | set F1 | effects | false discovery | refusal | coverage | rows | held out |
|---|---|---|---|---|---|---|---|---|
| rows chased by the conditional residual, then the closest proxy of each modelled variant, weakest first; every configuration of at most three bought variants scored by the extended BIC on the bought rows; declined when swapping a modelled variant for another bought one costs less than 3; joint effects | **0.806** | 0.88 | 0.81 | 0.00 | 1.00 | 1.00 | 6.0 | 0.749 |
| same, fed the panel's rows in place of the cohort's | 0.000 | 0.35 | 0.33 | 0.58 | 0.25 | 1.00 | 0.0 | 0.268 |
| same, rows bought for the six largest \|z\| instead of chased | 0.382 | 0.83 | 0.81 | 0.25 | 0.25 | 1.00 | 6.0 | 0.375 |
| same, stopping when the chase stops, no proxy rows | 0.306 | 0.88 | 0.81 | 0.33 | 0.00 | 1.00 | 2.4 | 0.249 |
| same, proxy rows by the largest predicted z-score instead of one per modelled variant | 0.431 | 0.88 | 0.81 | 0.25 | 0.25 | 1.00 | 6.0 | 0.499 |
| same, the strongest modelled variant's proxy first instead of the weakest's | 0.806 | 0.88 | 0.81 | 0.00 | 1.00 | 1.00 | 6.0 | 0.749 |
| same, two proxy rows per modelled variant reserved instead of one | 0.507 | 0.83 | 0.81 | 0.17 | 0.50 | 1.00 | 6.0 | 0.450 |
| same, no rows reserved: the chase may spend everything | 0.806 | 0.88 | 0.81 | 0.00 | 1.00 | 1.00 | 6.0 | 0.749 |
| same, never declining | 0.306 | 0.88 | 0.81 | 0.33 | 0.00 | 1.00 | 6.0 | 0.249 |
| same, refusal margin 1 instead of 3 | 0.431 | 0.88 | 0.81 | 0.25 | 0.25 | 1.00 | 6.0 | 0.749 |
| same, refusal margin 6 instead of 3 | 0.806 | 0.88 | 0.81 | 0.00 | 1.00 | 1.00 | 6.0 | 0.749 |
| same, declining on a bought \|r\| of 0.95 or more instead of the margin | 0.431 | 0.88 | 0.81 | 0.25 | 0.25 | 1.00 | 6.0 | 0.499 |
| same, marginal effects z times the standard error instead of joint | 0.426 | 0.88 | 0.80 | 0.25 | 0.25 | 1.00 | 6.0 | 0.494 |
| same, plain BIC (penalty 9.9) instead of extended (18.1) | 0.599 | 0.62 | 0.57 | 0.25 | 1.00 | 1.00 | 6.0 | 0.709 |
| same, the extended BIC penalty halved (9.0) | 0.599 | 0.62 | 0.57 | 0.25 | 1.00 | 1.00 | 6.0 | 0.709 |
| same, the penalty at the Bonferroni line for sixty variants at 0.05 (11.2) | 0.842 | 0.88 | 0.81 | 0.08 | 1.00 | 1.00 | 6.0 | 0.709 |
| same, the extended BIC penalty doubled | 0.806 | 0.88 | 0.81 | 0.00 | 1.00 | 1.00 | 6.0 | 0.749 |
| same, then a masking-aware local test: the strong-LD neighbours of each modelled variant, read from its exact row, scanned conditionally at a Bonferroni line for that neighbourhood alone | 0.962 | 1.00 | 0.92 | 0.00 | 1.00 | 1.00 | 6.0 | 0.947 |
| same, PLINK clumping at r-squared 0.1 on the bought rows instead of the extended BIC | 0.199 | 0.25 | 0.22 | 0.42 | 1.00 | 0.75 | 6.0 | 0.511 |
| same, stepwise conditional selection at t 5 on the bought rows instead of the extended BIC | 0.431 | 0.88 | 0.81 | 0.25 | 0.25 | 1.00 | 6.0 | 0.499 |
| same, chase threshold 2 or 4.5 instead of 3 | 0.806 | 0.88 | 0.81 | 0.00 | 1.00 | 1.00 | 6.0 | 0.749 |
| same, a budget of 3 or 4 rows | 0.507 | 0.83 | 0.81 | 0.17 | 0.50 | 1.00 | 3.0 | 0.450 |
| same, a budget of 8 rows: more than the task allows, fails closed | 0.000 | — | — | — | — | — | 6.0 | 0.000 |
| PLINK clumping on the panel at r-squared 0.1, marginal effects, never declining (baseline) | 0.000 | 0.17 | 0.14 | 0.83 | 0.00 | 1.00 | 0.0 | 0.005 |
| declining everything | 0.000 | — | — | 0.67 | 1.00 | 0.00 | 0.0 | 0.000 |

Every row costs something real: trusting the panel costs 0.81, buying by rank 0.42, not buying
the proxy rows 0.50, never declining 0.50, marginal effects 0.38, three or four rows 0.30,
clumping on the exact rows 0.61, since the decoy is an independent clump on any LD. The
selection line is the axis with headroom on both sides. Sharper region-wide lines take the
masked partners and the decoys with them: the plain BIC and the halved penalty lose 0.21 here
and make a false discovery in three of the twelve worlds, and the Bonferroni line for sixty
variants gains 0.04 on the development split, with one false discovery, and loses 0.04 held
out. What actually separates a masked partner from a decoy is linkage: the partner sits in the
lead's own block, the decoy does not, and a conditional test confined to the strong-LD
neighbourhood of each modelled variant, which is where masking happens (Yang et al. 2012),
names every partner in the graded worlds with no false discovery, and none on one hundred and
twenty-five further worlds. The reference does not do this, and that is the 0.16 it leaves on
the table. The rest is the sampling noise of the effects.

**Low-dimensional shortcuts do not solve this task.** A sweep of 1120 strategies was scored on
the same rows a candidate would buy: the panel alone, or rows for the two, four or six largest
|z|, or rows chased by the residual with zero, two or four rows held back for proxies; the
model by the top variant, by clumping at r-squared 0.1, 0.2 or 0.5, by stepwise conditional
selection at t 4, 5 or 5.45, or by the extended BIC at half, once or 1.6 times the penalty;
refusal never, on a near-duplicate at |r| 0.9, 0.95 or 0.98, on a swap margin of 1, 3 or 6, or
on a residual t above 4; effects joint or marginal. The best of them reaches **0.557** on the
development split and 0.257 held out, against the reference's 0.806 and 0.749 and a ceiling
of 1.0, by rows for the two largest |z|, stepwise conditional selection and declining on a
residual t above 4; it makes a false discovery in two worlds and declines two of the four
unresolved ones. No strategy in the sweep reaches 0.6; the chase family, the reference's own
purchase rule with proxies by predicted z-score, tops out at 0.556, and every strategy that
never buys a row stays at or below 0.305.

## Rules

- Only edit `solution.py`; keep `fine_map(problem, ld_row)`.
- `sle.contract_lint` is importable and free to call for shape checks. It costs no row.
- Do not read `verification/` or `frontier_eval/`.

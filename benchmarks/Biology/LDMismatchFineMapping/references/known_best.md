# LDMismatchFineMapping: known best

## Current complete reference and correction

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


`verification/reference_masking_aware.py` is standalone and truth-blind: it reads only the public
problem and ordinary charged LD rows. It adds the local masked-partner test that the original
reference deliberately omitted and converts marginal t-statistics to correlations before the
joint effect fit. All six rows remain charged, and repeat queries remain free. Sampling error
in effect estimates remains; no standard competence is disabled to lower the admission line.

The oracle now expresses true effects in the exact units of the realised standardised
phenotype, using the accepted draw's sample standard deviation instead of
`sqrt(Var(signal) + 1)`. The numerical construction results below are preserved as the original
builder's measurements and must not be used as current expected scores. Current sandbox,
shortcut and model-calibration records are separate, source-bound artifacts.

The likelihood-gap rule is an operational finite-sample RSS criterion. RSS is an approximate
likelihood for marginal regression summaries, not an assertion of permanent non-identifiability
at infinite sample size. The task is a curated conditional simulation, not an empirical claim
about the prevalence of ambiguous GWAS loci.

## Historical reference (truth-blind): rows chased by the conditional residual, one proxy row per modelled variant, extended BIC, swap-margin refusal

`verification/reference_conditional_rows.py`. It buys the row of the strongest variant, then
the row of the variant whose z-score is least explained by the variants already modelled, with
the residual standardised by the Schur complement of the bought rows, until nothing is left
above t 3 or only one row per modelled variant remains. It spends what remains on the closest
unbought proxy of each modelled variant, the weakest variant's first, then on the largest
predicted z-scores. On the bought variants it scores every configuration of at most three by
the summary-statistic likelihood z_B ~ N(R_BS lambda_S, R_BB) with the extended BIC penalty
log(n) + 2 log(p) = 18.1 per variant. It declines when replacing any modelled variant by any
other bought variant costs less than 3 in the score, and otherwise reports the joint estimate
converted to per-allele units with the marginal standard error, at confidence 0.8.

| split | score | set F1 | effects | false discovery | refusal | coverage | rows |
|---|---|---|---|---|---|---|---|
| development | 0.806 | 0.88 | 0.81 | 0.00 | 1.00 | 1.00 | 6.0 |
| held out | 0.749 | 0.83 | 0.77 | 0.00 | 1.00 | 1.00 | 6.0 |

Its swap margin is 20.9 to 134.4 on the twelve typed worlds and 0.3 to 1.3 on the six
unresolved ones, against a threshold of 3 and construction gaps of at least 6 and at most 2.
What it leaves on the table, by design: it names only the lead of every masked pair, because
the partner's conditional chi-square (11.2 to 12.6 given the lead's exact row) is below its
region-wide selection line, so the masked worlds score 0.51 to 0.55 with a set F1 of 0.67. A
sharper region-wide line takes the decoys that every other world carries in the same band (see
the ladder). The recoverable headroom is a masking-aware local test, and the ladder's rung for
it shows what it is worth: 0.962 on the development split and 0.947 held out. The rest is the
sampling noise of the effects, 0.81 on the development split, under the original approximate marginal-standard-error conversion. The current reference
uses the exact linear-regression conversion instead.

On one hundred and twenty-five worlds outside the graded seeds, twenty-five of each kind, the reference makes no false discovery: single-variant worlds score 0.921 to 1 on the mechanism axis, masked worlds 0.484 to 0.55 with the partner unnamed, multi-signal worlds 0.916 to 1, and every unresolved world is declined, for a mean of 0.890. The three sharper region-wide selection lines all take the masked partners and pay for it in the single-variant worlds, where the decoy sits in the same band: the Bonferroni line for sixty variants makes nine false discoveries in twenty-five and scores 0.886 overall, the plain BIC eighteen and 0.833, the halved extended BIC twenty-five and 0.780. The masking-aware local test, run after the reference on the same rows, names the partner in twenty-four of the twenty-five masked worlds, makes no false discovery, and scores 0.968 overall. Building those worlds took 21 attempts and 27 noise draws on average, 305 and 59 at most, and every typed world has its causal set at least 6.2 ahead of every single-member swap.

## Model draws

The 2026-09-11 fixed campaign ran three `gpt-5.6-sol` high first proposals, with
selection-blind budget 1, evaluator timeout 300 seconds, maximum output 16384 tokens
and seed labels 0/1/2. Labels identify replicates rather than provider-controlled
randomness. All three proposals were valid on all 18 worlds and reached exactly
the complete reference: development **0.9618342499999997**, heldout
**0.9455182499999999**. The reference's YAML declaration rounds development to
0.96183425; the independent comparison uses its actual prior sandbox measurement.
All proposals had zero false discoveries, complete supported-world discovery
coverage and complete correct refusal on both splits. Confidence remains a
separate axis and is not used to turn this into a different score.

**Criterion D16 fails on all three draws; hold this task from merging.** The fixed
plan was created after the complete-reference repair and source freeze at
`766aff5fab3c347b2d982ae76417a342845a9029`. The task package was
`6d5e734ce57ef3566103f22339f7c152242ef6b2d403b2ac8b5714c2c67be1f2`, runtime
`8159a99d54894dd304e3ac48956cd05d4389f12a041f5d5d86a2c079641c2c86`, and plan
`16ba07b5c28ad2771ae53bbdeeea602282dc34342a1f09f36ddd551e0bc60b6b`.

The three baseline and three proposal evaluations remain in the original private
run tree; there were no adaptive retries or task changes after observing scores.
Total provider-reported usage was 52200 tokens; price was unavailable. A separate
read-only review checks the original source, all expected cells, retained candidate
bytes, requests/receipts, complete world validity and file hashes. Its public
scalar report is `experiments/ld_mismatch_first_draw_review_2026-09-11.json`.
Later card/reference-note edits are documentation only and leave old source and
receipt bindings intact. This is operator calibration evidence, not certification
or a long-horizon cohort. Global evidence is not refreshed for this held task.

## Baseline: PLINK clumping on the panel, marginal effects, never declining

`solution.py`. It takes the genome-wide significant variants in order of |z| and keeps one per
clump, a clump being everything at panel r-squared 0.1 or more with a kept variant, up to three,
with marginal effects z times the standard error, at confidence 0.9. It buys no row.

| split | score | set F1 | effects | false discovery | refusal | coverage |
|---|---|---|---|---|---|---|
| development | 0.000 | 0.17 | 0.14 | 0.83 | 0.00 | 1.00 |
| held out | 0.000 | 0.58 | 0.53 | 0.50 | 0.00 | 1.00 |

It is confidently wrong in every single-variant world, where the panel-invisible proxy and the
decoy are further clumps; in every masked world, where the partner has no marginal signal; in
every unresolved world, where it names one of the pair; and in the multi-signal worlds, where
the decoy is a fourth clump or displaces the weakest signal. The normalisation takes what is
left to zero.

## Difficulty ladder

`.research/ld_mismatch_fine_mapping/ablation.py`, one reference choice changed at a time. The
full table is in Task.md. The costs on the development split: trusting the panel 0.81, buying
by rank 0.42, not buying the proxy rows 0.50, proxy rows by predicted z-score instead of one per
modelled variant 0.38, two proxy rows reserved per variant 0.30, never declining 0.50, a refusal
margin of 1 instead of 3 0.38, a near-duplicate threshold instead of the margin 0.38, marginal
effects 0.38, the plain BIC 0.21, the halved penalty 0.21, clumping on the bought rows 0.61,
stepwise conditional selection on the bought rows 0.38, three or four rows 0.30. The
Bonferroni line for sixty variants gains 0.04 on the development split with one false
discovery and loses 0.04 held out. The chase threshold at 2 or 4.5, the margin at 6, the
strongest variant's proxy first, no reserved rows and a doubled penalty change nothing. The
masking-aware local test, a conditional scan of the strong-LD neighbours (|r| at least 0.5 in
the bought row) of each modelled variant at a Bonferroni line of 0.01 over that neighbourhood
alone, gains 0.16 on the development split and 0.20 held out, with no false discovery.

## Shortcut probe

`.research/ld_mismatch_fine_mapping/probe.py`. 1120 strategies over the purchase rule (the
panel alone; rows for the two, four or six largest |z|; the residual chase with zero, two or
four proxy rows by predicted z-score), the model (top variant; clumping at r-squared 0.1, 0.2 or
0.5; stepwise conditional selection at t 4, 5 or 5.45; the extended BIC at half, once or 1.6
times the penalty, over the bought variants or the top twelve by |z| when nothing is bought),
the refusal (never; a bought or panel |r| of 0.9, 0.95 or 0.98 to a modelled variant; a swap
margin of 1, 3 or 6; a residual t above 4) and the effects (joint or marginal).

The best strategy scores 0.557 on the development split and 0.257 held out, 69 per cent of the
reference: rows for the two largest |z|, stepwise conditional selection at t 4, 5 or 5.45, and
declining on a residual t above 4, with joint effects. It names the single-variant and
multi-signal worlds, misses every masked partner, makes a false discovery in two worlds and
declines two of the four unresolved worlds. Twenty-four of the 1120 strategies reach 0.5 and
none reaches 0.6. The chase family, the reference's own purchase rule with proxies by predicted
z-score, tops out at 0.556; the panel alone at 0.305; every clumping model at 0.199, since the
decoy is an independent clump on any LD; every strategy that never declines at 0.308; the
near-duplicate thresholds and the swap margins at 0.433, because rows by rank or by predicted
z-score do not reach the pair in the three-signal unresolved worlds. Held out, no strategy
exceeds 0.511.

## Construction errors caught on the way

- The first refusal world had an untyped causal variant and asked the candidate to decline its
  best typed tag as a poor fit. The residual chi-square meant to detect that had a
  noncentrality of ten to forty against a spread the chase rows inflated, so no threshold
  separated the worlds. The world was replaced by the near-duplicate pair, whose unresolvability
  is a likelihood identity, z_i^2 - z_j^2 under the cohort's rows, and not a test.
- The near-duplicate was first planted on the founder haplotypes and could not exceed a cohort
  correlation of 0.91, because the mosaic's copying error and switches separated the two sites
  in four per cent of haplotypes. It is now planted on the realised haplotypes with a mismatch
  rate of 0.1 to 0.4 per cent in the cohort and 6 to 15 per cent in the panel.
- The first residual covariance ignored the fitted variants; it is now the Schur complement.
- Verification rows ranked by observed |z| inflated the residual in weak worlds; they are ranked
  by predicted |z|, and the refusal no longer depends on them at all.
- A budget of eight rows left the reference two rows of slack: four rows scored 0.892 and six
  the full score. The budget is six.
- Two masked worlds had no genome-wide significant variant, which no scan would have sent to
  fine-mapping. Every world now has one.
- The candidate was handed the campaign object, whose budget it could overwrite in-process. It
  is handed a closure.
- With every unresolved pair the strongest signal in its world, rows for the two largest |z|
  and a stepwise selection reached 0.940 against a reference of 0.959. Three of the four
  development unresolved worlds now have the pair as the weakest of three signals, at rank 10
  to 19, and the reference buys one proxy row per modelled variant, the weakest first, instead
  of two rows by predicted z-score.
- The reference then scored 0.959, with the masked partners at a conditional chi-square of 18
  to 20, above every selection line, so the task had no headroom. The partner's band was moved
  to 9.5 to 13.5, below the extended BIC penalty; that alone made the plain BIC the best rung at
  0.958, since the graded worlds had nothing for a sharper line to lose on. Every typed and
  unresolved world now carries a decoy in the same band, a non-causal variant in weak LD with
  every causal one, so no region-wide line takes the partners without the decoys, and only the
  lead's LD neighbourhood separates them.
- A band that narrow could not be met by redrawing haplotypes: one masked seed failed four
  hundred attempts. The construction now fixes the haplotypes and the effects and redraws the
  phenotype noise, up to sixty times per haplotype draw.
- With the decoys in place, rows chased by the residual, clumping at r-squared 0.1 on the bought
  rows and a swap-margin refusal tied the reference at 0.807 on the development split: the
  decoys were below genome-wide significance, so clumping never saw them, and the bought row of
  a pair member exposes its near-duplicate to a swap margin computed over all sixty variants.
  Every decoy is now genome-wide significant on its own, at |z| 5.5 to 8.1, and clumping on the
  bought rows falls to 0.199. The probe's best is 0.557.
- One world had a second non-causal variant within the band, so "exactly one secondary hit" was
  false there. The construction now requires every other non-causal variant to sit at least 2
  below the band; over the graded worlds the runner-up is at 3.0 to 7.3.

## Robustness

`.research/ld_mismatch_fine_mapping/checks.py`: two evaluations of the reference agree key for
key; declining everything scores 0.000 in both forms; a fixed variant scores 0.000; the top
variant by |z| never declining scores 0.180; twenty-three malformed candidate shapes, including
overspending, a patched budget, a float and a boolean row index, all score valid 0, combined 0,
feasibility 0 without raising; a repeated row is free and the seventh raises. Every module
parses as Python 3.8. The eighteen graded worlds take 0 to 58 haplotype draws and 2 to 58 noise
draws to build, about forty seconds in all on the build machine; the worlds are cached per
process, and `eval_time_seconds` is 90.

Not done: the sandbox half of `scripts/check_task_contribution.py` (no Bubblewrap on the build
machine), a frontier-model draw, the global evidence refresh.

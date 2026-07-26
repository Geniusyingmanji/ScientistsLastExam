# Feedback measurement pilot preregistration v2

Frozen before any nonzero-budget run of this cohort: 2026-07-26 UTC. This version supersedes
`.research/feedback_measurement_pilot_prereg_2026-07-26.md`; no scheduled nonzero-budget cell was
run under v1.

## Revision record

Full-suite v16 (SHA-256
`e6732621830fcdf7011d3c7890143f974333a10e1f30c205186a9719ea10f322`) failed 14 historical
analysis tests on clean source `2052d25`. Thirteen failures came from changing the frozen portable
trajectory projection without increasing its schema version. One failure came from treating every
generic harness file as part of a historical task's scientific evaluator. The negative report is
retained as `FAILED_FULL_TEST_SUITE / DO_NOT_USE_AS_PASSING_EVIDENCE`.

Revision `241d78a9f680a3784ab3c31ef114e77034398d28` restores the frozen schema-v1 projection and
adds an explicit schema-v2 projection for new reports. It also separates trusted evaluator/task
source equivalence from search/report-protocol equivalence. A 101-test failure-focused run passes;
123 historical v1 snapshots across 103 reports reproduce exactly from their raw trajectories, and
the trusted evaluator/task scopes of twelve affected tasks have zero source differences from their
frozen model revisions. The transitional budget-zero smoke at `a30cb08` (SHA-256
`70d13983ae71a9bf808a1d0ac2e8a8ff456115614a2b58497d2826567b1ee663`) is retained but
superseded because its top-level snapshot says v1 while its event payload contains the then-new
v2 fields. A correctly versioned smoke must precede the cohort.

## Purpose and claim limit

This pilot checks whether four feedback treatments execute with auditable lineage, complete
provider token records and enough outcome variation to design a later repeated study. It is not a
confirmatory feedback experiment. Two local replicate identifiers per cell do not estimate a
population effect, and the Azure Responses endpoint exposes no server-side generation seed.
Condition differences may therefore be reported only as descriptive pilot contrasts.

## Frozen source and model condition

- Source revision: `241d78a9f680a3784ab3c31ef114e77034398d28`.
- Runtime source SHA-256: `9895f96c63e1d63c3f9c2270a3eae759d072da238ef14e0fb84005a61ca9c51e`.
- LLM-condition SHA-256: `5b0df4671481f6b3505155bc6c5654a64c4da5591422fb806904e7d0f44fc4d2`.
- Model condition: keyless Azure Responses endpoint, model `gpt-5.5`, reasoning effort `low`,
  `max_output_tokens=16000`, no temperature parameter and no server-side seed control.
- Any source or model-condition change requires a new preregistration version. Existing completed
  cells remain immutable and are not pooled across revisions in the primary report.

## Scheduled risk set

The fixed cohort has 16 run cells. Each cell uses `greedy_rewrite`, proposal budget 3, evaluator
timeout 300 seconds and one of the local replicate identifiers 0 or 1. Even identifiers run
conditions in the order below and odd identifiers reverse that order.

| Task | Contract SHA-256 | Scientific role |
|---|---|---|
| `DynamicalSystems/ActiveLawDiscovery` | `6a08897ce2c685ca30db0b3be957838576816fc85dd24803d9e4bf1ec9a4eb4e` | mechanism recovery, prediction, false discovery and refusal |
| `Optics/DiffractionGratingDesign` | `8af05515bbe25350e3e543cd2751f76e195125c8db8eab80dacaebd64700ff27` | nominal optical design, held-out transfer and sealed-shift robustness |

The four conditions are:

1. `normal`: the current true-score-selected incumbent and its allowlisted selection metrics.
2. `score_only`: the same online selection rule, but the prompt receives only
   `combined_score`. This is a feedback-bandwidth treatment, not a no-feedback condition.
3. `delayed_replay`: proposal `k` sees the best valid artifact released through proposal `k-2`.
   The baseline is available initially; observer-side final selection retains all evaluated
   candidates.
4. `selection_blind`: every proposal receives the frozen baseline artifact and baseline metrics;
   all candidate scores are used only for observer-side best-of-batch selection.

## Outcomes and analysis

The primary measurement outcomes are run completion, valid-proposal rate, realized input/output/
total tokens, prompt payload bytes, oracle calls and lineage conformance. The primary scientific
outcomes are terminal `combined_score` and best-so-far AUC over proposal budget. The following
evaluator-only axes are reported separately and never averaged across tasks:

- ActiveLawDiscovery: `mechanism_score`, `development_prediction_score`,
  `validation_prediction_score`, `robustness_score`, development/validation false discoveries and
  correct abstentions.
- DiffractionGratingDesign: `robustness_score`, `heldout_policy_score`,
  `heldout_robustness_score`, development/held-out minimum and mean target efficiency, and sealed
  shift-geometry feasibility.

Every condition is compared at its configured proposal horizon and at a common realized-total-token
horizon. For each task and replicate identifier, the common horizon is the minimum total provider
tokens across all four successful cells. A proposal counts at that horizon only if its full provider
call completed by the cutoff. The baseline is available at token zero. Missing or inconsistent
input/output/total token usage invalidates token-horizon analysis for that run; it is never imputed
as zero. Token-adjusted results are descriptive because unequal prompts and uncontrolled model
randomness remain.

Normal-minus-control contrasts are reported for `score_only`, `delayed_replay` and
`selection_blind`. With two local replicate identifiers, all intervals are diagnostics. No
significance test, multiplicity-adjusted claim, cross-task mean science score, model ranking or
feedback-causal claim is permitted.

## Failure, retry and stopping rules

- Run all 16 scheduled cells unless the endpoint or evaluator is unavailable. Do not stop for
  apparent positive, negative or saturated outcomes.
- The outer report retains every failed attempt. A retry uses the same run cell and `--resume` only
  when the committed checkpoint and manifest match exactly. Recovery history remains in the report.
- Report intent-to-evaluate completion over the frozen 16-cell denominator and a paired-completer
  sensitivity. Do not silently drop terminal failures.
- Infrastructure failure, missing trajectory, manifest mismatch, lineage mismatch, missing selected
  evaluator-only axes or provider token-accounting failure makes the derived analysis fail closed.
- Candidate invalidity or unparsable model output is a scientific/operational outcome, not an
  exclusion.

## Gate to a later Track F study

This pilot may motivate a later study only if all 16 cells complete or all failures are retained,
the four lineage contracts pass, provider usage is complete, and at least one task retains
non-saturated outcome variation. A feedback claim still requires a separately preregistered cohort
with at least ten independent runs per condition, server-controlled randomness if it becomes
available or explicit unpaired randomization if it does not, pilot-based precision planning, fresh
or server-held worlds and independent scientific validation. This pilot alone cannot pass that
gate.

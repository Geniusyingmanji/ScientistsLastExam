# Feedback measurement pilot preregistration

Frozen before any nonzero-budget run of this cohort: 2026-07-26 UTC.

## Purpose and claim limit

This pilot checks whether four feedback treatments execute with auditable lineage, complete
provider token records and enough outcome variation to design a later repeated study. It is not a
confirmatory feedback experiment. Two local replicate identifiers per cell do not estimate a
population effect, and the Azure Responses endpoint exposes no server-side generation seed.
Condition differences may therefore be reported only as descriptive pilot contrasts.

## Frozen source and model condition

- Source revision before preregistration: `a30cb0824ebc02e34fa53d42cba8c6b3236554af`.
- Runtime source SHA-256: `4da758ef984de35d88396be3064b77f7299efb48ad0025dfc933720f703ad82c`.
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

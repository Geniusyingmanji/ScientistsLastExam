# Strict iterative-feedback pilot results

Date: 2026-07-21 (UTC). This document reports the frozen design in
`feedback_pilot_preregistration.md`. Four task reports bind clean source revision `e59612b`; the
preregistered derived analysis binds clean revision `ea43a49`. All five reports set
`execution_passed=true`, `trusted_evidence=true` and `passed=true`.

## Completion and interpretation boundary

All 24 task-condition-replicate runs completed without a condition-level infrastructure error.
The matrix consumed 72 proposal slots, 96 actual oracle calls including baselines, 352,881 model
tokens and 3,016.9 summed run-seconds. Every strict-control proposal retained the baseline parent
hash and `offline_best_of_open_loop_batch` metadata. The implementation pilot therefore passes
its workflow gate.

Three replicate identifiers do not support a confirmatory causal claim. The Azure endpoint does
not expose a server-side random seed, so paired identifiers do not share model random draws. The
normal condition also used more tokens than the strict control on every task. Mean paired
normal-minus-control token differences ranged from 3,070 to 6,676 tokens per three-proposal run.
Incumbent program/context growth is a plausible contributor, but prompt-length and generated-code
length were not separately analyzed. The comparison is call-matched but not token-matched.

## Paired outcomes

All differences below are normal minus `selection_blind`. Intervals are diagnostic Student-t
intervals with three pairs.

| Task | Visible terminal difference, mean [95% interval] | Science difference, mean [95% interval] | Direct reading |
|---|---:|---:|---|
| Pendulum | -0.2479 [-1.2863, 0.7905] | shifted robustness -0.0068 [-0.1074, 0.0938] | Replicate directions disagree; no stable feedback lift is visible. |
| Gate synthesis | 0.0000019 [-0.0000061, 0.0000099] | development hardware robustness 0.0118 [-0.0296, 0.0531] | Both conditions saturate nominal fidelity; hardware differences are unresolved. |
| Active law discovery | -0.0493 [-0.2821, 0.1836] | validation mechanism -0.0466 [-0.2549, 0.1618] | One low normal replicate drives the mean; every selected candidate still makes one false discovery in each split. |
| OPF | 0.00000003 [-0.00000010, 0.00000017] | N-1 robustness approximately 0 [-0.0000000012, 0.0000000008] | Both conditions reach nominal score one and retain identical contingency feasibility. |

For ActiveLawDiscovery, the `robustness_score` column is the sealed validation mechanism score,
not physical robustness. Development and validation false-discovery differences are exactly
zero because both conditions make one false discovery in each split for every selected
candidate. For OPF, the mean complete-outage feasibility difference is exactly zero; both
conditions remain at 0.113997 feasibility despite nominal score one.

## What the pilot changes

The pilot does not support the preregistered directional hypothesis that normal iterative
feedback improves sealed validation over an open-loop batch. This is an absence of evidence in a
three-replicate, non-token-matched pilot, not evidence that feedback has no value. It does rule
out using these short results as a positive Track F claim.

Two task-design conclusions are more direct. OPF has no useful nominal headroom after the first
valid solver, so additional nominal-only iterations cannot teach N-1 security. ActiveLawDiscovery
can improve in-library fit while its misspecified-world decision remains wrong. The next focused
experiment should expose structured security or model-adequacy feedback in a development-only
treatment while preserving held-out contingencies and misspecified worlds for sealed evaluation.

The confirmatory feedback experiment should also use at least ten replicate identifiers, impose
matched token or context budgets, and separate parent-program adaptation from score-information
content. A delayed/replayed-score condition can hold parent timing and message shape closer to
normal. Until those controls are run, the project should describe Track F as implemented and
piloted, not validated.

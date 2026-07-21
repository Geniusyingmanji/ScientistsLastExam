# Strict iterative-feedback pilot preregistration

Frozen before model calls. Date: 2026-07-21 (UTC).

## Question and scope

This pilot tests whether iterative incumbent and score feedback improves short-horizon scientific
optimization relative to repeated open-loop proposals. It is an implementation and variance
pilot, not the confirmatory Track F experiment. The Azure Responses endpoint exposes no
server-side random seed, so local seed identifiers define matched task/configuration blocks and
condition ordering but do not guarantee common random numbers.

## Conditions

- `normal`: each proposal sees the current best program and its allowlisted public metrics;
  true `combined_score` selects the next incumbent.
- `selection_blind`: every proposal sees the original baseline program and the original
  allowlisted baseline metrics. Evaluation results never change a later parent or prompt. The
  report selects the best valid proposal only after the open-loop batch is complete.

Both conditions receive the same task contract, proposal-slot text, model configuration, tool
access, proposal budget and secure evaluator. The comparison tests the full value of iterative
parent-program plus score feedback. It does not isolate score text while holding the parent
program fixed, and prompt lengths can diverge when the normal incumbent program changes.

## Fixed design

- Model: local keyless Azure GPT-5.5 Responses endpoint, `reasoning_effort=low`.
- Search: built-in `greedy_rewrite` only.
- Tasks: `ControlTheory/InvertedPendulumSwingUp`, `QuantumControl/GateSynthesis`,
  `DynamicalSystems/ActiveLawDiscovery`, and `PowerSystems/OptimalPowerFlow`.
- Conditions: `normal`, `selection_blind`.
- Replicate identifiers: 0, 1, 2.
- Proposal budget: 3 per task-condition-replicate, plus one baseline event.
- Per-candidate timeout: 180 seconds.
- Condition ordering: listed order on even replicate identifiers and reversed order on odd
  identifiers. Tasks may run in separate concurrent processes; each task report preserves its
  within-task order.
- No exclusions after inspecting outcomes. Infrastructure failures remain in the report and may
  be rerun only as a separately retained attempt with the same configuration.

The planned matrix contains 24 runs and 72 proposal calls. Actual oracle calls are reported
separately because unparsable or failed proposals still consume proposal budget.

## Outcomes

Primary descriptive outcomes are paired differences in terminal best visible score and
best-so-far AUC. Science outcomes are evaluated on the selected best-visible candidate:

- Pendulum: shifted `robustness_score` and development-robustness gap.
- Gate synthesis: development and held-out hardware robustness.
- Active law discovery: validation mechanism score, validation prediction score, and
  development/validation false-discovery counts.
- OPF: development and held-out N-1 robustness, contingency-constraint feasibility, complete
  outage feasibility and overload diagnostics.

Token count, wall time, proposal events, actual oracle calls, candidate lineage and invalid-rate
differences are secondary outcomes. Task-specific science metrics will not be averaged into one
score. With three replicate identifiers, intervals are diagnostic only and no significance or
causal-generalization claim will be made.

## Decision rule

The workflow is considered runnable if all 24 conditions retain trusted clean-source provenance,
compact trajectory snapshots and no unrecorded failures. A larger confirmatory study is warranted
when the pilot exposes nonzero within-task variance and no systematic protocol failure. The
confirmatory design requires at least ten matched replicates and should add delayed/replayed
feedback plus a narrower score-information-only control.

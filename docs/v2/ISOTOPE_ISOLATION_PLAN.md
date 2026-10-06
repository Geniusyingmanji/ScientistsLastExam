# Isotope isolated operator smoke plan v1

Frozen before execution, 2026-10-06. Status: EXECUTED ONCE; STOPPED AT SANDBOX STARTUP.
Purpose: verify the actual private journal / candidate sandbox / prospective
session lifecycle. No model calls and no scientific capability score.

## Admission decision

Do not add isotope to the general registry yet. The shared constructor currently
requires both registry membership and a frontier allowlist entry. Unit tests of
individual adapters do not exercise this constructor. Introduce an explicit,
operator-only prototype selection path with default denial, limited to the exact
isotope version. Keep CLI/model environment choices and historical manifests
unchanged. Do not monkeypatch registry membership in the smoke run.

## Fixed development run

- Exposed world seed: 100 (already used in development; never a held-out instance).
- One task directory, exclusive creation, private receipts. No retries.
- One source query using World.example(), then one preregistered validation.
- Target: times [0, 2, 5], static source fractions [0.4, 0.1, 0.1, 0.4].
- Readout: double_label at row 2; 4 independent replicates; one frozen constant
  predictor returning [1, 0, 0] at each row. This is an intentionally weak
  interface fixture, not an authored scientific reference.
- Profile predictive_validation; one test; no fitting or revision. Record the
  outcome even when rejected or inconclusive; do not adjust tolerance after it.
- Maximum 5 World.run calls (1 source + 4 target), 128 experiment units,
  2 isolated predictor calls, 15 seconds per call, 30 seconds charged prediction
  time, 30 seconds total simulation time, 120 seconds task wall time,
  1024 MB predictor memory, family alpha .05, at most 4 actions.
- Check the current request tolerance policy before invocation; freeze an exact
  request artifact and hash it before any observation. If policy rejects it,
  record rejection and stop; do not adapt the scientific design within this run.

## Separate isolation checks

At most two standalone candidate workers, each 15 seconds / 1024 MB: attempt to
read a private canary file and import the isotope kernel. Both must be denied;
only success/failure categories may enter public reports. These are security
smokes, not experiments or API calls. Stop on unexpected access or startup fault.
No fallback to in-process prediction. Keep all artifacts and failure receipts.

## Verification and remaining gates

Recompute sealed receipts, verify attempted/charged calls and source binding,
inspect candidate mount inputs, and project a private evidence packet. Public
HTML receives only aggregate checks, counts and limitations. Never raw predictor
code, observations, private seed or target outcomes.

A successful operator smoke does not register the environment: task presentation,
full claim semantics, calibration and initial-state adapters must still pass.
A failure is an engineering result, not evidence of scientific difficulty.

## Observed execution, 2026-10-06

One source observation (24 units), one predictor startup attempt, 15 seconds
charged prediction allowance. Startup failed before prediction; zero prospective
tests completed and no target replicates collected. Twelve private receipts
verified; no scientific conclusion. Host is macOS with no bwrap available; the
secure worker requires a Linux/bubblewrap runtime. The generic runtime failure
is consistent with this unmet prerequisite, not a measured model failure.
Stopped without retry or in-process fallback. The two separate access probes
were not run after startup failure. Future Linux validation requires a newly
frozen, separately recorded development run; preserve this failure.

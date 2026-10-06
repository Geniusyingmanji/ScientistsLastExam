# Prototype audit — 2026-10-06

This unit audits existing synthetic instruments; it does not add four new worlds.
The four task definitions in env/v2_tasks/catalog.json are development research
specifications, not registered agent workflows or paid evaluation results.

## Corrections from implementation inspection

- Adaptive signaling: arbitrary stimulus histories do not distinguish the matched
  input/output realizations. Selective reset, timed during a transient, is the
  actual distinguishing intervention. Paired pulses alone are insufficient.
- Retention transport: the public flow range is nonnegative. Flow reversal in the
  earlier roadmap was not a legal experiment and has been removed. Matched total
  flow with different pause duration is a supported design.
- Both are linear latent-state instruments. They add intervention identifiability
  but do not by themselves establish broad multidisciplinary coverage or hardness.
- Electrochemical impedance is deferred pending a genuinely new control or
  nonlinear question: another linear response kernel risks duplicating existing
  electrical impedance and climate tasks. Isotope tracing is the next candidate
  to design, but must use conservation and labeling information rather than a
  renamed two-state relaxation model.

## Evidence gates

Existing exposed development calibration is retained, not rerun as new evidence.
The focused numerical tests verify equivalence/discrimination witnesses and
independent numerical agreement. This unit reruns those tests only as regression
checks. No model performance or discovery-depth claim follows from them.

Next unit: freeze an isotope-tracing design with explicit label conservation,
competitive flux explanations, pulse/chase interventions, and a nonidentifiable
regime before implementation. Retain as prototype until shared adapters and
budgeted reference checks pass.

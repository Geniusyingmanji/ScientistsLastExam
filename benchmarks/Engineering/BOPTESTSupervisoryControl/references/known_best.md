# Reference and admission record — BOPTESTSupervisoryControl

## 1. Reference method

`verification/reference.py` is standalone and uses only public inputs and charged interfaces. Forecast boundary tracking with online thermal disturbance estimation and one-step CO2 control.
It is a method witness, not independent high-fidelity verification. A load-compensated baseline and sufficient 30 kW capacity make all declared climates feasible. Public comfort excursion/rate tolerances replace permissive hidden thresholds; CO2 enforces the published limit. Anchor errors are separated from candidate errors.

## 2. Baseline and normalization

The shipped `solution.py` is the baseline. Tests check valid near-zero development scores.
Optimization references define one through recomputed objective differences; discovery scores
retain their fixed supported-world ceilings and refusal normalization. Changed oracle versions
must not be compared as if their score differences were model improvements.

## 3. Capability comparisons and ablations

Run `python scripts/diagnose_pr9_engineering.py --output tmp/hardening/diagnostics.json --sweeps`.
Historical public methods are replayed on the current oracle where available; these comparisons
are **not** isolated causal ablations. HVAC additionally removes occupancy forecasting, and the
wastewater constant controller removes all state feedback. A complete per-capability ladder,
including measured nonzero drops, still requires clean Linux execution before admission.

## 4. Shortcut probes

The diagnostic script includes 528 constant aeration/recycle pairs, 48 historical thermostat
parameter pairs, a source-only single-well archive, and historical public search methods.
`tests/test_new_task_hardening.py` pins the diagnosed scientific failures and known shortcuts.
All remaining untested low-dimensional families are admission risks; passing these probes does
not prove the absence of shortcuts. Numeric tables from a laptop are local debugging output,
not frozen benchmark evidence.

## 5. Frontier-model calibration

Not run. This task remains `candidate`. A clean Linux model draw, frozen before exposure, must
show that the first proposal does not reach the competent reference. No calibration or external
review is implied by these local code changes. Server-held worlds and independent model review
remain required.

## 6. Construction errors and revisions

2026-09-05 hardening: A load-compensated baseline and sufficient 30 kW capacity make all declared climates feasible. Public comfort excursion/rate tolerances replace permissive hidden thresholds; CO2 enforces the published limit. Anchor errors are separated from candidate errors.
Standalone references no longer import the hidden evaluator. The task card records the review
lineage, licensing uncertainty and public-world contamination risk. Earlier measurements below
belong to the pre-hardening version and are retained only as history.

## 7. Robustness and reproducibility

Development and heldout metrics remain separate. The new tests cover anchor feasibility,
equivalent-parameter scoring, mass conservation, time refinement, forecast-unit invariance,
instrument error poisoning and malformed submissions as applicable. Formal Linux sandbox
replay, global evidence refresh and independent scientific replication are still pending.
See the task card citations for background; the explicitly declared reduced model is not
certified by those publications.

## Historical pre-hardening record (obsolete scores)

# Reference witness

The normalization witness is a deterministic forecast-aware supervisory controller with thermal
preconditioning, action smoothing and CO2-responsive ventilation. It receives only the same
public forecasts and current observations as a candidate and is not claimed optimal. Official
BOPTEST FMU replay, cross-test-case ranking and frontier-model calibration remain pending.

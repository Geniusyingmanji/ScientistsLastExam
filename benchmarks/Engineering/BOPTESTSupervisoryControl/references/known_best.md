# Reference and admission record — BOPTESTSupervisoryControl

## 1. Reference method

`verification/reference.py` is standalone and uses only public inputs and charged interfaces. It blends a conservative feasible thermostat with forecast boundary tracking, online thermal disturbance estimation and one-step CO2 control.
It is a method witness, not independent high-fidelity verification. A load-compensated baseline and sufficient 30 kW capacity make all declared climates feasible. Public comfort excursion/rate tolerances replace permissive hidden thresholds; CO2 enforces the published limit. Anchor errors are separated from candidate errors.

## 2. Baseline and normalization

The shipped `solution.py` is the zero baseline. The runnable 40%-model/60%-conservative controller
scores `0.681069` development / `0.810403` held-out. The evaluator independently recomputes the
pure public-model controller as score one, leaving adaptive model trust and stronger control as
checkable headroom. The scale is floored at zero and uncapped.

## 3. Capability comparisons and ablations

Run `python scripts/diagnose_pr9_engineering.py --output tmp/hardening/diagnostics.json --sweeps`.
On the current dirty macOS tree, the safety-blended reference scores `0.681069` development and
`0.810403` held out. Replacing the public occupancy forecast with constant full occupancy reduces
the same controller to `0.230030` development and `-0.570399` held out while remaining feasible.
The occupancy forecast therefore contributes `0.451039` development score in this diagnostic.

## 4. Shortcut probes

All 48 proportional thermostat probes (six gains by eight ventilation coefficients) failed the
published comfort/IAQ feasibility gate on at least one development climate; none produced a valid
aggregate score. This rules out that particular two-parameter family, not thermostat shortcuts in
general. The pure public-model controller is the score-one anchor, so the safety blend's lower score
is reference headroom rather than a model-difficulty measurement. These are local diagnostics, not
frozen benchmark evidence.

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
public forecasts and current observations as a candidate and is not claimed optimal. In the
historical version it defined score one directly. Official
BOPTEST FMU replay, cross-test-case ranking and frontier-model calibration remain pending.

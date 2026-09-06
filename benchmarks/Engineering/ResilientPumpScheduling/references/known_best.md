> Version note (2026-09-05, second local hardening): Discrete stable-speed/minimum-run commitment and auxiliary/start costs are active. Single-pump/single-tank fidelity and global optimality remain limited. The sections below include historical measurements from the first hardening; they are not measurements of the current version. Current local comparisons are recorded in `https://github.com/BLGZZY/ScientistsLastExam/blob/3106a1e/docs/reviews/new_tasks_difficulty_v2.md`.

# Reference and admission record — ResilientPumpScheduling

## 1. Reference method

`verification/reference.py` is standalone and uses only public inputs and charged interfaces. It solves public-demand-band convex dispatch on a conservative all-on commitment with linear storage/pressure/ramp constraints and a switching epigraph.
It is a method witness, not independent high-fidelity verification. Replaces tariff coordinate moves with constrained convex optimization. No invented 0.92-baseline anchor is used when the reference fails; an invalid anchor is an infrastructure error. This remains a single-tank surrogate, not a pipe-network solver.

## 2. Baseline and normalization

The shipped `solution.py` is the zero baseline. The runnable all-on convex dispatch scores
`0.569407` development / `0.493703` held-out. The evaluator's block-exchange commitment search
is the reproducible score-one anchor; discrete commitment is the measured headroom. The scale is
floored at zero and uncapped. The maintainer observed 79 seconds for the baseline on another host;
the declared expected time is 120 seconds and the wrapper timeout is 300 seconds.

## 3. Capability comparisons and ablations

Run `python scripts/diagnose_pr9_engineering.py --output tmp/hardening/diagnostics.json --sweeps`.
On the current dirty macOS tree, convex dispatch on the all-on commitment scores `0.569407`
development and `0.493703` held out. The historical coordinate-move method is invalid on every
development instance and one of two held-out instances. The evaluator's block-exchange commitment
search defines score one, but it has not yet been packaged as a separately runnable ablation.

## 4. Shortcut probes

The conservative constant-speed baseline scores zero. The all-on convex policy is both the current
reference and the measured no-commitment-search probe (`0.569407`); its gap to one is therefore
discrete-commitment search headroom, not independent evidence of difficulty. Fixed tariff-window,
two-block and threshold-on/off schedules remain unmeasured. These values are local diagnostics,
not frozen benchmark evidence.

## 5. Frontier-model calibration

Not run. This task remains `candidate`. A clean Linux model draw, frozen before exposure, must
show that the first proposal does not reach the competent reference. No calibration or external
review is implied by these local code changes. Server-held worlds and independent model review
remain required.

## 6. Construction errors and revisions

2026-09-05 hardening: Replaces tariff coordinate moves with constrained convex optimization. No invented 0.92-baseline anchor is used when the reference fails; an invalid anchor is an infrastructure error. This remains a single-tank surrogate, not a pipe-network solver.
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

The normalization witness performs deterministic public-demand coordinate moves that reduce
costly-hour pumping while replaying public storage, pressure and ramp constraints. It never sees forecast error or outage hours. It is a strong
feasible witness rather than a global optimum for the nonlinear energy model; in the historical
version it defined score one and stronger savings could exceed 1.0. EPANET/WNTR replication and frontier-model calibration are pending.

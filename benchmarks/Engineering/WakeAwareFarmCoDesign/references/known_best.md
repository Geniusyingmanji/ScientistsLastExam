# Reference and admission record — WakeAwareFarmCoDesign

## 1. Reference method

`verification/reference.py` is standalone and uses only public inputs and charged interfaces. It uses ten seeded layout starts, coordinate yaw search and one 80 m feasible layout-refinement scale; the evaluator independently runs the stronger 180-start, three-scale anchor.
It is a method witness, not independent high-fidelity verification. Adds layout refinement after yaw selection. Cross-model robustness, restarts and independent FLORIS validation remain open.

## 2. Baseline and normalization

The shipped `solution.py` is the zero baseline. The runnable co-design search scores `0.741392`
development / `0.613817` held-out against the stronger reproducible search anchor. Additional
starts and finer 40/20 m layout moves are the measured headroom. The scale is floored at zero and
uncapped.

## 3. Capability comparisons and ablations

Run `python scripts/diagnose_pr9_engineering.py --output tmp/hardening/diagnostics.json --sweeps`.
On the current dirty macOS tree, ten layout starts, coordinate yaw and one 80 m layout-refinement
scale score `0.741392` development, `0.613817` robustness and `0.735669` held-out policy. Replaying
the historical yaw-only construction scores `0.490932`, `0.347172` and `0.494141` respectively.
The added layout refinement and restarts contribute `0.250460` development score in this method
comparison.

## 4. Shortcut probes

The regular-grid, zero-yaw baseline scores zero. The historical yaw-only search reaches
`0.490932`, below the co-design reference but high enough to show that yaw is a substantial partial
shortcut. The remaining reference-to-anchor gap is finite search over starts and 40/20 m layout
moves, not a frontier-model measurement. Row staggering, boundary packing and fixed-yaw grids
remain unmeasured. These values are local diagnostics, not frozen benchmark evidence.

## 5. Frontier-model calibration

Not run. This task remains `candidate`. A clean Linux model draw, frozen before exposure, must
show that the first proposal does not reach the competent reference. No calibration or external
review is implied by these local code changes. Server-held worlds and independent model review
remain required.

## 6. Construction errors and revisions

2026-09-05 hardening: Adds layout refinement after yaw selection. Cross-model robustness, restarts and independent FLORIS validation remain open.
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

The witness screens 180 deterministic valid jitters around a staggered grid and then performs
coordinate yaw refinement using only the public wake model and wind rose. It is not a global
layout or yaw optimum, so the historical normalization remained uncapped above it. FLORIS cross-model rankings and
frontier-model calibration are pending.

# DistributionNetworkTopology — boolean tomography of a water grid

## Scientific setting

Sending a release down a testable route of a district network reports whether it
arrived: a route fails exactly when any of its pipes is broken. Recovering the
broken pipes from budgeted route tests is boolean network tomography — an
identifiability problem, not just a search problem: pipes whose routes coincide can
never be told apart, and a confident localization there is a false discovery.

## Your task

```python
def recover_network(problem, probe, budget_units):
    """Return {"broken_pipes": [pipe ids], "abstain": bool, "confidence": [0,1]}."""
```

`problem` is a mapping with the keys

```text
pipe_ids                  the grid pipes plus two parallel service lines
parallel_service_pipes    the twin ids s11 and s21
routes                    route id -> ordered pipe list (several hundred monotone
                          routes across a 4x4 grid, plus the twin service corridor)
probe_cost / budget_units 1 / 26
route_note                a route fails when any of its pipes is broken; reports
                          flip with the published probability and repeats draw
                          fresh noise
claim_note                the twin service lines sit in series on the same corridor,
                          so no route can tell which twin is broken
```

`probe(route_id)` charges one unit and returns `{route_id, arrived, budget_cost}`.
Overspending or unknown ids invalidate the world even when caught.

## Evaluation

- `combined_score` is development broken-set recovery above the always-abstain
  baseline: F1 of the claimed set against the truth. The default regime allows up
  to two broken pipes under four percent report flips.
- Twin-corridor worlds score refusal only; abstaining scores one and any claim
  scores zero.
- Set F1, false discovery rate, correct refusal rate and discovery coverage are
  reported with denominators; a full abstention scores exactly zero.
- `robustness_score` repeats the audit on held-out break sets.

This is a synthetic boolean grid, not a claim about any real district.

## Rules

- Only edit `solution.py`; keep the complete function signature.
- Deterministic Python/NumPy/SciPy/stdlib code only; no network or process creation.
- Do not read `verification/` or `frontier_eval/`.
- Dispatch errors and overspending invalidate the world even when caught.
- Use `sle.contract_lint` for free local shape checks before returning an inference.

Reference: Ostfeld et al. (2008), J. Water Resour. Plan. Manage.,
doi:`10.1061/(ASCE)0733-9496(2008)134:6(556)`.

## 关系与区别 / Relationship to nearby tasks

GraphFromDistances reconstructs edges from distance queries on a hidden weighted
network; ModalDamageAttribution localizes stiffness damage from modal shifts. This
task recovers a failure set from pass/fail route probes under flip noise, and its
refusal world is structural non-identifiability — twin pipes with identical route
signatures that no probe can separate.

## Admission and reference scope

This package remains **candidate**. The runnable reference uses public inputs only:
likelihood-tracked hypothesis search: break sets of at most two pipes scored
under the published flip probability, information-splitting route choice, and
margin-based claims with structural-twin refusal. Local shortcut
and ablation diagnostics are recorded in `references/known_best.md`; they do not
replace clean Linux sandbox replay, independent review or a frozen frontier-model
calibration draw.

## Frontier-Eng overlap comparison (2026-09-06)

无. Nearest catalog entries: EV2GymSmartCharging; tree_gsm_safety_stock. Paid path tests identify failed water pipes with inseparable twin-line refusal. FE chooses charging schedules or inventory service times on known graphs. Despite the name, this task diagnoses failures on a supplied route graph; it is not network-layout or energy-dispatch optimization.

See `.research/pr9_frontier_eng_overlap_2026-09-06.md` for the pinned 47-task paper and complete available repository catalog. The requested 95-entry source could not be reconciled with the available 78 rows (84 expanded tasks); source reconciliation and maintainer acceptance remain pending.

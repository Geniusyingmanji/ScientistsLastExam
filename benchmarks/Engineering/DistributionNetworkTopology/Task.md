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
  baseline: F1 of the claimed set against the truth.
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
greedy set-cover probing, majority-vote re-probes of failed routes, exhaustive
minimal hitting sets and a discrimination loop over rival candidates. Local shortcut
and ablation diagnostics are recorded in `references/known_best.md`; they do not
replace clean Linux sandbox replay, independent review or a frozen frontier-model
calibration draw.

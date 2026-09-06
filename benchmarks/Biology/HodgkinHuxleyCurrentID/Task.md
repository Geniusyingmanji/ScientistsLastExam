# HodgkinHuxleyCurrentID — recover channel parameters from voltage-clamp protocols

## Scientific setting

Voltage-clamp experiments hold the membrane at chosen potentials and read the ionic
current transient; fitting the classic Hodgkin-Huxley gating model to well-chosen
protocols is how channel conductances, reversal potentials and activation shifts were
first measured. A membrane carrying a current outside the three-current family — a
fast-inactivating A-type conductance, or a rectifying leak — cannot be explained by
any parameter row, and a confident fit there is a false discovery.

## Your task

```python
def recover_channel_parameters(problem, voltage_step, budget_units):
    """Return {"parameters": [gNa, gK, gL, ENa, EK, EL, sNa, sK] within bounds,
               "abstain": bool, "confidence": float in [0,1]}."""
```

`problem` is a mapping with the keys

```text
parameters / parameter_bounds   the eight names and bounds
gating_equations                the public 1952 alpha/beta forms
current_equation                the public three-current expression with the shift
                                convention V -> V - sNa (V - sK) inside gating
holding_potential_mV            -80
step_bounds_mV                  [-70, 60]
durations_ms                    [5, 10, 20, 30]
sample_dt_ms                    0.25
protocol_cost / budget_units    1 / 8
noise_note                      Gaussian noise scales with each trace's peak current
refusal_note                    extra-current membranes must be refused
```

`voltage_step(step_potential_mV, duration_ms)` charges one unit and returns
`{step_potential_mV, duration_ms, time_ms, current, noise_std, budget_cost}` — the
noisy current trace with a stated noise level. Overspending or malformed calls
invalidate the world even when caught.

## Evaluation

- `combined_score` is development mechanism recovery above the always-abstain
  baseline: geometric mean of parameter recovery (normalized by public bounds) and a
  sealed trace prediction at a held-out protocol (45 mV, 20 ms).
- A-type and rectifying worlds score refusal only; abstaining scores one and any
  parameter claim scores zero.
- Parameter recovery, false discovery rate, correct refusal rate and discovery
  coverage are reported with denominators; a full abstention scores exactly zero.
- `robustness_score` repeats the audit on held-out parameters and failures.

This is a deterministic simulation of the public equations, not a claim about any
specific preparation.

## Rules

- Only edit `solution.py`; keep the complete function signature.
- Deterministic Python/NumPy/SciPy/stdlib code only; no network or process creation.
- Do not read `verification/` or `frontier_eval/`.
- Amplifier errors and overspending invalidate the world even when caught.
- Use `sle.contract_lint` for free local shape checks before returning an inference.

Reference: Hodgkin & Huxley (1952), J. Physiol., doi:`10.1113/jphysiol.1952.sp004764`.

## 关系与区别 / Relationship to nearby tasks

RANSCalibration fits an algebraic closure to channel-flow data; ChronoamperometryLawID
identifies electrochemical law families from potential steps. This task recovers a
bounded eight-parameter row of a nonlinear kinetic model from self-designed
voltage-clamp protocols, with extra-current refusal worlds and a sealed held-out
protocol prediction.

## Admission and reference scope

This package remains **candidate**. The runnable reference uses public inputs only:
four fixed steps, closed-form gating (exact at clamped voltage), multistart bounded
least squares including the classic squid-axon start, and a residual misfit gate. Local
shortcut and ablation diagnostics are recorded in `references/known_best.md`; they do
not replace clean Linux sandbox replay, independent review or a frozen frontier-model
calibration draw.

## Frontier-Eng overlap comparison (2026-09-06)

无. Nearest catalog entries: predict_modality; perturbation_prediction; PIDTuning. Budgeted voltage-clamp experiments recover membrane-current parameters and refuse extra-current worlds. FE predicts cell responses or tunes a flying controller, not membrane conductance inference.

See `.research/pr9_frontier_eng_overlap_2026-09-06.md` for the pinned 47-task paper and complete available repository catalog. The requested 95-entry source could not be reconciled with the available 78 rows (84 expanded tasks); source reconciliation and maintainer acceptance remain pending.

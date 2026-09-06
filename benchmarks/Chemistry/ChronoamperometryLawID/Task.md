# ChronoamperometryLawID — identify the current law behind potential-step transients

## Scientific setting

A potential step across an electrode interface answers with a current transient whose
shape encodes the transport and reaction mechanism: semi-infinite diffusion
(Cottrell), bounded diffusion, catalytic regeneration, kinetic limitation, adsorption
desorption, or mixed surface-plus-diffusion control. Two measurement failures make a
confident family claim a false discovery: fractional-diffusion transport (anomalous
t^-1/3 decay) and a superposed linear baseline drift, neither expressible in the
family.

## Your task

```python
def identify_current_law(problem, step, budget_units):
    """Return a mapping with exactly:
      family_probabilities: mapping covering the six public families, summing to one
      parameters: [a, b, c] — inactive slots are free, active slots respect the
                  public bounds
      abstain: bool
      confidence: finite scalar in [0,1]
    """
```

`problem` is a mapping with the keys

```text
families            the six family names
current_laws        public closed forms for each family
amplitude_factor    phi(E) = 1 - exp(-3*E)
parameter_bounds    [a, b, c] bounds for active slots
potential_bounds    [0.1, 1.0] volts
time_grid_s         the fixed 28-point log grid (0.002..8 s) every step reports
step_cost           1
budget_units        6
noise_note          Gaussian noise scales with the largest current of each step
refusal_note        anomalous transport and baseline drift must be refused
```

`step(potential)` charges one unit and returns `{potential, time_s, current,
noise_std, budget_cost}` — the noisy transient on the public time grid with a stated
noise level. Overspending or malformed calls invalidate the world even when caught.

## Evaluation

- `combined_score` is development mechanism recovery above the always-abstain
  baseline: geometric mean of the true family probability, active-parameter recovery
  (normalized by public bounds) and a sealed extrapolation of the transient to
  t = 12 and 20 s at a sealed potential, multiplied by an evidence-efficiency factor
  `1 - 0.50 * budget_used / 6` on supported discoveries. Accurate identification with fewer potential steps
  therefore retains measurable room above the three-step reference.
- Anomalous and drift worlds score refusal only; abstaining scores one and claiming a
  family scores zero. Refusal credit is not multiplied by evidence efficiency, preventing
  evidence-backed refusal from scoring below blind abstention.
- Intrinsic and efficiency-adjusted mechanism recovery, evidence efficiency, false discovery rate, correct refusal rate and discovery
  coverage are reported separately; a full abstention scores exactly zero.
- `robustness_score` repeats the audit on held-out families, parameters and failures.

The aggregate efficiency diagnostics are `development_evidence_efficiency_score` and
`heldout_evidence_efficiency_score`; per-world rows also retain
`intrinsic_mechanism_score`, `mechanism_score`, `evidence_efficiency_score` and
`budget_used`. Split membership and hidden truth are never candidate inputs.

This is a deterministic reduced-order electroanalytical simulation, not evidence
about any particular cell.

## Oracle and difficulty

Parameters are seeded uniformly in the public bounds; Gaussian noise scales with each
step's largest current. Difficulty levels 1–3 raise the noise (1.5 → 4.5 percent of
peak current) and drift strength; level 1 is the shipped default.

## Rules

- Only edit `solution.py`; keep the complete function signature.
- Deterministic Python/NumPy/SciPy/stdlib code only; no network or process creation.
- Do not read `verification/` or `frontier_eval/`.
- Instrument errors and overspending invalidate the world even when caught.
- Use `sle.contract_lint` for free local shape checks before returning an inference.

Reference: Bard & Faulkner, *Electrochemical Methods: Fundamentals and Applications*,
ISBN `9780471057528`. It motivates the transient families; the benchmark uses the
public closed forms stated above.

## 关系与区别 / Relationship to nearby tasks

EnzymeKineticsLaw identifies rate laws from scalar initial rates in a biochemical
setting; ActiveLawDiscovery recovers ODE right-hand sides from trajectories. This
task identifies which published current-law family generated multi-potential
functional transients, with two structurally unmodellable refusal worlds and a
sealed time extrapolation that separates diffusion tails from kinetic saturation.

## Admission and reference scope

This package remains **candidate**. The runnable reference uses public inputs only:
three potential steps, per-family bounded least squares with an Akaike-style freedom
penalty, a chi-square misfit gate and a variable-projection test for a shared linear
drift. Local shortcut and ablation diagnostics are recorded in
`references/known_best.md`; they do not replace clean Linux sandbox replay,
independent electrochemistry review or a frozen frontier-model calibration draw.

## Frontier-Eng overlap comparison (2026-09-06)

无. Nearest catalog entries: snar_multiobjective; mit_case1_mixed; reizman_suzuki_pareto; BatteryFastChargingSPMe. Choose potential-step measurements to discriminate current-law families and refuse drift/fractional transport. FE optimizes reaction yield/Pareto fronts or charging; it does not return a scientific family decision and calibrated refusal.

See `.research/pr9_frontier_eng_overlap_2026-09-06.md` for the pinned 47-task paper and complete available repository catalog. The requested 95-entry source could not be reconciled with the available 78 rows (84 expanded tasks); source reconciliation and maintainer acceptance remain pending.

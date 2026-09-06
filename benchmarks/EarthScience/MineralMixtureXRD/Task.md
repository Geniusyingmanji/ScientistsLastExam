# MineralMixtureXRD — quantify a mineral mixture from powder diffraction

## Scientific setting

A powder pattern reports a blend of diffraction peaks: each library mineral
contributes its peak set scaled by weight fraction, an amorphous component adds a
broad hump, and an unknown crystalline phase adds sharp peaks no library fit can
absorb. Quantitative phase analysis must separate the three cases: name and
quantify the library minerals, ignore the hump, refuse the unknown phase.

## Your task

```python
def identify_minerals(problem, coarse_scan, slow_scan, budget_units):
    """Return {"minerals": [library ids], "fractions": {id: weight, summing to one
               over the crystalline portion}, "abstain": bool, "confidence": [0,1]}."""
```

`problem` is a mapping with the keys

```text
mineral_library      twelve minerals, each a list of [two_theta, intensity]
two_theta_range_deg  [10, 80] on a 0.05-degree grid
grid_step_deg / peak_shape  the public resolution model
coarse_noise         0.08 relative noise on the free coarse scan
slow_noise / slow_window_deg  0.025 relative noise on a charged 15-degree window
scan_cost / budget_units  1 / 4
convention           fractions are relative to the crystalline portion; the
                     amorphous hump must not trigger refusal, an unknown sharp
                     phase must
```

`coarse_scan()` is free; `slow_scan(center_deg, width_deg)` charges one unit and
returns a high-resolution window. Overspending or malformed calls invalidate the
world even when caught.

## Evaluation

- `combined_score` is development mixture recovery above the always-abstain
  baseline: 0.7 x set F1 plus 0.3 x a log-ratio fraction score.
- Unknown-phase worlds score refusal only; abstaining scores one and any library
  claim scores zero and counts as a false discovery.
- False discovery rate, correct refusal rate and discovery coverage are reported
  with denominators; a full abstention scores exactly zero.
- `robustness_score` repeats the audit on held-out mixtures, humps and unknowns.

This is a synthetic peak simulation, not a claim about any real rock.

## Rules

- Only edit `solution.py`; keep the complete function signature.
- Deterministic Python/NumPy/SciPy/stdlib code only; no network or process creation.
- Do not read `verification/` or `frontier_eval/`.
- Instrument errors and overspending invalidate the world even when caught.
- Use `sle.contract_lint` for free local shape checks before returning an inference.

Reference: Rietveld (1969), J. Appl. Crystallogr., doi:`10.1107/S0021889869006558`.

## 关系与区别 / Relationship to nearby tasks

CrowdedSpectrumAssignment identifies library species in a blended optical spectrum
with resolution zooming; PhaseDiagramDiscovery maps binary equilibria by synthesis
budget. This task quantifies weight fractions of a crystalline mixture from free
coarse plus budgeted slow diffraction windows, and its refusal axis separates a
broad amorphous hump (distractor) from a sharp unknown phase (must refuse).

## Admission and reference scope

This package remains **candidate**. The runnable reference uses public inputs only:
nonnegative least squares over merged coarse and slow feature windows, slow-window
refinement at the strongest peaks, and a local-contrast sharpness gate on the fit
residual. The reference leaves large headroom on fraction accuracy (0.396
development); local diagnostics are in `references/known_best.md`. They do not
replace clean Linux sandbox replay, independent review or a frozen frontier-model
calibration draw.

## Frontier-Eng overlap comparison (2026-09-06)

无. Nearest catalog entries: predict_modality; phase_fourier_pattern_holography. Paid diffraction windows identify crystalline phases and weights, separating amorphous background and unknown phases; FE predicts molecular modalities or synthesizes a holographic phase mask, rather than identifying a mineral mixture.

See `.research/pr9_frontier_eng_overlap_2026-09-06.md` for the pinned 47-task paper and complete available repository catalog. The requested 95-entry source could not be reconciled with the available 78 rows (84 expanded tasks); source reconciliation and maintainer acceptance remain pending.

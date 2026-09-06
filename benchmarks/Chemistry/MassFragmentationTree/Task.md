# MassFragmentationTree — recover a fragmentation tree from multi-energy MS/MS

## Scientific setting

Tandem mass spectrometry identifies small molecules by breaking the isolated precursor
ion at several collision energies and reading the fragment spectra. Computational
fragmentation-tree reconstruction — the core of tools such as SIRIUS — must decide which
peaks are real fragments of one precursor, which are background, and how fragments derive
from one another through neutral losses. Two measurement failures make over-interpretation
easy: a molecule that fragments in the ion source never shows a surviving molecular ion,
and a co-isolated isobar superposes a second fragmentation series onto the same spectra.
In both worlds a single confident tree is a false discovery.

## Your task

```python
def recover_fragmentation_tree(problem, acquire, zoom, budget_units):
    """Return a mapping with exactly:
      nodes: list of positive finite fragment-ion m/z floats (may include the precursor)
      edges: list of [parent_mz, child_mz, loss_name]; each endpoint must reference a
             distinct submitted node within mass_tolerance_da; loss_name must come from
             the public loss library
      abstain: bool
      confidence: finite scalar in [0,1]
    """
```

`problem` is a mapping with the keys

```text
precursor_mz               isolated target m/z (the [M+H]+ of the intended analyte)
loss_library               name -> {formula, neutral_mass} for twelve public neutral losses
element_mass_table         monoisotopic H, C, N, O masses
proton_mass                proton mass added to neutral masses to form m/z
fragment_formula_ranges    public C, H, N, O bounds a fragment formula may occupy
mass_tolerance_da          matching tolerance (0.015 Da)
energy_bounds              [10.0, 60.0]
acquire_cost / zoom_cost   1 / 2 budget units
budget_units               8 total
min_relative_intensity     fragments below 0.5% of the base peak are not reported
background_note            low flat background peaks may be present
zoom_note                  a zoom reports monoisotopic peaks with M+1/M isotope ratios
```

`acquire(collision_energy)` charges `acquire_cost` and returns

```text
collision_energy  the requested energy
peaks             list of {mz, intensity} sorted by descending intensity; intensity is
                  percent of the base peak
budget_cost       units charged
```

`zoom(center_mz, window_width_da)` charges `zoom_cost` (width within `[0.1, 3.0]`) and
returns

```text
window_center / window_width  the requested window
peaks                         list of {mz, intensity, m1_ratio} inside the window;
                              m1_ratio estimates the ion's carbon count via 1.1% per carbon
budget_cost                   units charged
```

Overspending or malformed calls invalidate the world even when caught. Repeated calls
with identical arguments return identical spectra (deterministic instrument).

## Evaluation

- `combined_score` is development mechanism recovery above the always-abstain baseline:
  node F1 (mass-tolerance optimal matching) averaged with edge F1 (an edge counts only
  when both endpoints are matched to the true parent and child and the named loss is
  correct).
- In-source and co-isolate worlds score refusal only: abstaining scores one, claiming a
  tree scores zero.
- Mechanism recovery, false discovery rate, correct refusal rate and discovery coverage
  are reported separately; a full abstention scores exactly zero.
- `robustness_score` repeats the audit on held-out molecules, trees and failures.

This is a deterministic reduced-order instrument simulation, not evidence about any
particular laboratory instrument.

## Oracle and difficulty

The molecule is a hidden CHNO formula; the fragmentation cascade is a hidden tree over
the public loss library with per-edge labilities; peak positions carry Gaussian mass
error and log-normal intensity error, plus one to three flat background peaks. Difficulty
levels 1–3 raise mass error (0.004 → 0.012 Da), intensity noise and background count;
level 1 is the shipped default.

## Rules

- Only edit `solution.py`; keep the complete function signature.
- Deterministic Python/NumPy/SciPy/stdlib code only; no network or process creation.
- Do not read `verification/` or `frontier_eval/`.
- Instrument errors and overspending invalidate the world even when caught.
- Use `sle.contract_lint` for free local shape checks before returning an inference.

References: Dührkop et al. (2015), PNAS, doi:`10.1073/pnas.1509788112`; Böcker &
Dührkop (2016), Journal of Cheminformatics, doi:`10.1186/s13321-016-0116-8`. These
motivate fragmentation-tree reconstruction from tandem MS data; the benchmark uses the
reduced-order cascade stated above.

## 关系与区别 / Relationship to nearby tasks

CrowdedSpectrumAssignment identifies library species in a blended spectrum (substance,
no measurement choice); NMRSpectrumFitting and SpinSystemInference recover peak
mechanisms from one-dimensional spectra without an active instrument; GraphFromDistances
reconstructs a network from distance queries. This task actively spends an energy/zoom
budget, and its product is a fragmentation tree whose two failure worlds — no surviving
precursor and a co-isolated isobar — must be refused rather than explained.

## Admission and reference scope

This package remains **candidate**. The runnable reference uses public inputs only:
four energy scans plus one precursor-window zoom, CHNO mass decomposition, flat-background
filtering, greedy loss-library attachment, and refusal when the precursor never survives
or two precursor ions with different isotope ratios share the window. Local shortcut and
ablation diagnostics are recorded in `references/known_best.md`; they do not replace
clean Linux sandbox replay, independent mass-spectrometry review or a frozen
frontier-model calibration draw.

## Frontier-Eng overlap comparison (2026-09-06)

无. Nearest catalog entries: weighted_parameter_coverage; diverse_conformer_portfolio; torsion_profile_fitting. Charged MS/MS queries reconstruct directed neutral-loss fragment trees with co-isolation/no-precursor refusal. FE chooses molecules/conformers or fits force-field energies. Molecular context alone does not share the inverse graph problem.

See `.research/pr9_frontier_eng_overlap_2026-09-06.md` for the pinned 47-task paper and complete available repository catalog. The requested 95-entry source could not be reconciled with the available 78 rows (84 expanded tasks); source reconciliation and maintainer acceptance remain pending.

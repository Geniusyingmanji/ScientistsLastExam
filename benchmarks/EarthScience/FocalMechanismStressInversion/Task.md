# FocalMechanismStressInversion — resolve nodal-plane ambiguity into a stress regime

## Scientific setting

Every earthquake focal mechanism reports two nodal planes and does not say which one
slipped. Inverting a catalog for the regional stress tensor (Michael 1984, under the
Wallace-Bott assumption that slip parallels the resolved shear traction) means solving a
combinatorial plane-choice problem shared across events: each event contributes a
two-fold ambiguity, and the tensor is only identifiable through their joint agreement.
Two failure worlds make a confident tensor a false discovery: a catalog mixing two
stress regimes, and an incoherent catalog with no deviatoric signal at all.

## Your task

```python
def infer_stress_orientation(problem, reanalyze, budget_units):
    """Return a mapping with exactly:
      sigma1: [trend_deg, plunge_deg] with trend in [0,360), plunge in [-90,90]
      sigma3: same form; sigma2 is implied as the cross product
      R: shape ratio (sigma1 - sigma2)/(sigma1 - sigma3) in [0,1]
      plane_assignments: 0/1 row over every event (which listed plane slipped)
      abstain: bool
      confidence: finite scalar in [0,1]
    """
```

`problem` is a mapping with the keys

```text
event_count                 number of events (48)
events                      list of {id, plane_a, plane_b}; each plane is
                            [strike_deg, dip_deg, rake_deg] (Aki-Richards); the two
                            nodal planes are listed in arbitrary order
plane_convention            the geometry statement above
noise_sigma_deg             coarse mechanism uncertainty (4 degrees)
reanalysis_sigma_deg        tightened uncertainty after re-analysis (1.2 degrees)
reanalysis_budget           16 credits
reanalysis_cost             1 credit per event, once per event
model_note                  Wallace-Bott statement and the R convention
```

`reanalyze(event_id)` charges one credit, works once per event, and returns
`{id, plane_a, plane_b, budget_cost}` with the tighter uncertainty.

Overspending, re-analyzing an event twice, or malformed calls invalidate the world even
when caught.

## Evaluation

- `combined_score` is development mechanism recovery above the always-abstain baseline.
  On supported worlds mechanism is the geometric mean of an axis score (|cosine| to the
  true sigma1 and sigma3, shifted so a random axis guess scores zero), a shape-ratio
  score exp(-6|ΔR|), and a plane-assignment score (2×accuracy − 1, clipped at zero).
- Mixed and incoherent worlds score refusal only: abstaining scores one, reporting a
  tensor scores zero.
- Mechanism recovery, false discovery rate, correct refusal rate and discovery coverage
  are reported separately with their denominators; a full abstention scores exactly zero.
- `robustness_score` repeats the audit on held-out tensors, mixtures and noise.

This is a deterministic synthetic seismological catalog, not a claim about any real
seismic sequence.

## Oracle and difficulty

Stress tensors are seeded (uniform orientation, R uniform on 0.15–0.85); fault normals
are sampled with a slip-tendency floor; slip follows the Wallace-Bott shear direction;
both nodal planes are perturbed by Gaussian angular noise and listed in seeded order.
Difficulty levels 1–3 raise the coarse noise (4 → 8.5 degrees) and lower the sampling
floor; level 1 is the shipped default.

## Rules

- Only edit `solution.py`; keep the complete function signature.
- Deterministic Python/NumPy/SciPy/stdlib code only; no network or process creation.
- Do not read `verification/` or `frontier_eval/`.
- Observatory errors and overspending invalidate the world even when caught.
- Use `sle.contract_lint` for free local shape checks before returning an inference.

References: Michael (1984), J. Geophys. Res., doi:`10.1029/JB089iB13p11517`; Bott
(1959), Geological Magazine, doi:`10.1017/S0016756800059987`. These motivate the linear
stress inversion and the Wallace-Bott slip assumption; the benchmark uses the synthetic
catalog stated above.

## 关系与区别 / Relationship to nearby tasks

GravityInversion and DeformationMechanismInference recover continuous parameters from
active surveys; GeneNetworkIntervention recovers a signed network from interventions;
BlackBoxGroupIdentification identifies an algebraic structure from black-box queries.
This task's hidden structure is a second-rank tensor behind a per-event two-fold
combinatorial ambiguity, and its refusal worlds are regime mixtures and incoherent
catalogs, which no single-tensor fit can honestly explain.

## Admission and reference scope

This package remains **candidate**. The runnable reference uses public inputs only:
multi-start plane-choice initialization, alternating linear least-squares tensor fits
with per-event plane swaps, budgeted re-analysis of the worst-misfit events, and
refusal when the converged misfit distribution is too broad or heavy-tailed. Local
shortcut and ablation diagnostics are recorded in `references/known_best.md`; they do
not replace clean Linux sandbox replay, independent seismology review or a frozen
frontier-model calibration draw.

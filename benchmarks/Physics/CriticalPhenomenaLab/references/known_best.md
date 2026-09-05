# CriticalPhenomenaLab reference record

The score-one value is an evaluator-recomputed exact-descriptor ceiling, not a claim that an active
scientist can recover every hidden world perfectly. Recompute it with:

```bash
python3 -c "from verification.evaluator import reference_anchor; print(reference_anchor())"
```

`verification/reference_solver.py` is the truth-blind scientific reference. It uses only the public
experiment callback: a coarse small-lattice scan, targeted measurements at three larger sizes, a
joint Binder-cumulant finite-size-scaling fit, and magnetization scaling at the inferred transition.

Server calibration (2026-09-05, branch `feat/Physics/CriticalPhenomenaLab`, base `e326975`):

- baseline: development `combined_score` `0.0000`, valid `1.0`; it performs one low-cost call and
  abstains everywhere;
- truth-blind reference: valid `1.0`, development `combined_score` `0.2763086`, raw mechanism
  `0.4830776`, development discovery coverage `0.60`, false-discovery rate `0.0`, and
  correct-refusal rate `1.0`;
- held-out validation: robustness score `0.52079975`, discovery coverage `0.75`, false-discovery
  rate `0.0`, and correct-refusal rate `1.0`;
- the reference used exactly 27 laboratory calls and 42 budget units in every world.

The nonzero reference score confirms useful headroom above the always-abstain baseline after the
observation-noise and BKT-like-width calibration update. The reference is still only a calibration
witness: server-held families, independent Monte Carlo recomputation and external statistical-
physics review remain required before certification.

The baseline performs one measurement and abstains everywhere. By construction its normalized
development and held-out mechanism scores are both 0.0.

Scientific interpretation follows Binder and Landau (DOI `10.1103/PhysRevB.30.1477`). The reference
is a reproducible computational witness for this reduced-order laboratory, not a published record or
a substitute for independent Monte Carlo validation.

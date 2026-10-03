# Molecular forces laboratory

A candidate places three constrained particles, changes the temperature, and
measures total energy and Cartesian forces. It can compare geometries, repeat
measurements, develop arbitrary predictive models, and test those models on new
conditions. Nothing requires selecting a named potential or matching a golden
formula. This migrates the apparatus of `ForceFieldCalibration`; the old
classification/refusal evaluator and virial-answer scoring are not imported.

`World.describe()` is the complete public apparatus contract. Source, manifest,
this README, scientific notes and generated instance parameters are operator
material and must not enter candidate workers. No known potential menu appears
in the public description. Registration and research-runner integration are
managed separately; this package alone is a prototype.

- Spec: `configurations` of shape `[n,3,3]`, `configuration_ids=[0,...,n-1]`,
  and one `temperature_k`. Every row is a separate static preparation.
- Limits:1–8rows; coordinates ±5.5Å; all three separations2.2–5.4Å;180–900K.
- Output: one energy(eV) and nine forces(eV/Å), ordered particle1xyz,
  particle2xyz, particle3xyz. No measured channel is a directly assigned value.
- Noise: independent additive Gaussian, σ=.00035eV and.0007eV/Å,
  no clipping/process noise. A fresh measurement key provides independent noise.
- Cost: number of prepared configurations. Static indices have no time lag.
- `baseline` is a public-record nearest neighbor after centering coordinates.
  It has no potential-family prior and deliberately does not infer rotations.

Run focused checks with `pytest env/molecular_forces/tests`. See
[DEVELOPMENT_PLAN.md](DEVELOPMENT_PLAN.md) for preregistered bounds and
[SCIENTIFIC_NOTES.md](SCIENTIFIC_NOTES.md) for interpretation limits.

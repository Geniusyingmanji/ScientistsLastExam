# StokesShapeDrag — optimize 2D body shape for minimum drag in Stokes flow

## Scientific background
In low-Reynolds-number (Stokes) flow, the drag on a body depends solely on its geometry.
For a fixed cross-sectional area, the minimum-drag shape is not a circle — it involves
subtle curvature distributions. Pironneau (1973) proved the optimal shape for minimum drag
exists and computed it. This problem connects to microorganism locomotion, MEMS, and
sedimentation. The body is described by a Fourier series r(θ).

Reference: Pironneau, J. Fluid Mech. 59, 117 (1973); Pozrikidis 1992.

## Your task
```python
def optimize_shape(n_modes, area_target):
    \"\"\"Return Fourier coefficients (2*n_modes+1,): [a0, a1, b1, a2, b2, ...].
    Body: r(θ) = a0 + Σ(an cos nθ + bn sin nθ). Constraint: area = π, all r > 0.1.
    Goal: minimize drag coefficient (perimeter-based).\"\"\"
```

## Scoring
`score = clip((C_D_circle - C_D_found) / (C_D_circle - C_D_optimal), 0, 1)`
Circle → score 0. Pironneau optimal (~15% reduction) → score 1.0.

## Rules
- Only edit `solution.py`. numpy/scipy only. CPU. Do not read `verification/`.

# CompositeLaminateStacking — robust composite-laminate sequencing

## Task

Implement:

```python
def design_laminate(problem):
    return {"ply_angles_deg": [...]}
```

Choose the order of a fixed multiset of unidirectional plies. The number of plies, permitted
angles and exact count of every angle are supplied in `problem`. The returned laminate must be
symmetric and balanced and may not contain more than the published number of consecutive equal
plies. Values are checked exactly; the oracle never repairs a submission.

The public model is classical laminate theory. The trusted evaluator assembles the `A` and `D`
matrices, searches simply-supported Navier modes `(m,n)=1..4` for buckling, and computes a
Tsai-Hill first-ply reserve factor at both ply faces over every supplied membrane and bending-moment load case. The smaller reserve is
the design quality. This is a deterministic screening abstraction; certification of a real panel
would require finite-element analysis, damage-tolerance checks and tests.

`combined_score` is the mean development reserve improvement above the shipped quasi-isotropic
baseline, normalized by a fixed-seed, truth-blind permutation-search witness. It is uncapped:
beating that witness scores above 1. The evaluator separately reports held-out panels and a sealed
material/load-degradation check.

Important public keys are `ply_count`, `allowed_angles_deg`, `required_angle_counts`,
`maximum_consecutive_equal_plies`, `ply_thickness_m`, panel dimensions, `load_cases_n_per_m`, and
the orthotropic elastic/strength values in `material`.

Use deterministic NumPy/SciPy/standard-library CPU code. Do not read `verification/` or
`frontier_eval/`, access the network, or create processes.

References: Le Riche & Haftka, *AIAA Journal* 31(5), 951–956 (1993),
doi:10.2514/3.11710; Zhao, Sun & Silberschmidt, *Composite Structures* 149, 186–194 (2016),
doi:10.1016/j.compstruct.2016.01.052.

## Complete public input contract

Numeric values below are the first public example; per-instance arrays and coefficients vary.
All keys and shapes are part of the contract; forecasts contain exactly `horizon_steps` samples.

| Key | Type, shape or meaning |
|---|---|
| `ply_count` | 16 |
| `allowed_angles_deg` | array [4]; [-45, 0, 45, 90] |
| `required_angle_counts` | mapping; fields listed below |
| `required_angle_counts.-45` | 4 |
| `required_angle_counts.0` | 4 |
| `required_angle_counts.45` | 4 |
| `required_angle_counts.90` | 4 |
| `symmetric` | True |
| `balanced` | True |
| `maximum_consecutive_equal_plies` | 3 |
| `ply_thickness_m` | 0.000125 |
| `panel_length_m` | 1.2 |
| `panel_width_m` | 0.72 |
| `load_cases_n_per_m` | array [2, 3] |
| `material` | mapping; fields listed below |
| `material.e1_pa` | 132000000000.0 |
| `material.e2_pa` | 9200000000.0 |
| `material.g12_pa` | 4800000000.0 |
| `material.nu12` | 0.29 |
| `material.xt_pa` | 1450000000.0 |
| `material.xc_pa` | 1050000000.0 |
| `material.yt_pa` | 55000000.0 |
| `material.yc_pa` | 185000000.0 |
| `material.s_pa` | 72000000.0 |
| `model` | classical laminate A/D matrices; simply-supported Navier buckling modes 1..4; Tsai-Hill first-ply reserve |

## 关系与区别 / Relationship to nearby tasks

TrussWeightMinimization optimizes member sizes, HeatExchangerDesign optimizes thermal geometry, and ModalDamageAttribution infers damage. This task orders a fixed ply multiset and checks bending stiffness under loads; it does not identify damage or change laminate composition.

## Admission and reference scope

This package remains **candidate**. The metadata difficulty is a target, not a certified result. The runnable reference uses public inputs only. Local shortcut and ablation diagnostics are recorded in `references/known_best.md`; they do not replace clean Linux sandbox replay, independent domain review, Frontier-Eng overlap review or a frozen frontier-model calibration draw.

### Current reference and remaining difficulty

900 seeded permutation starts followed by up to twelve feasible pair-exchange refinement passes. The new witness refines permutations rather than stopping after random screening. The old membrane-only strength was order-invariant. The hardened model supplies paired bending moments and evaluates both faces of every ply using membrane strain plus depth times curvature, so material failure now depends on order. Independent anisotropic buckling validation is still pending. The optimization reference defines 1 by construction; a discovery reference is evaluated against the fixed recovery ceiling. Neither fact certifies difficulty.

`moment_cases_n` has shape `[number_of_load_cases,3]`, with `[Mx,My,Mxy]` in N (moment per unit panel width), paired with `load_cases_n_per_m`. The symmetric laminate uses `strain=A^-1*N`, `curvature=D^-1*M` and global ply-face stress `Qbar*(strain+z*curvature)` before material-axis Tsai-Hill evaluation. Membrane loads have been rescaled to kN/m order so buckling and ply failure can both affect ranking. The current Navier screening expression still neglects anisotropic mode coupling in buckling; external finite-element review is required.

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
Tsai-Hill first-ply reserve factor over every supplied membrane-load case. The smaller reserve is
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

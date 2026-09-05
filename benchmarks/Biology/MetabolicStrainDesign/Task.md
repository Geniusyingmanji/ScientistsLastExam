# MetabolicStrainDesign — engineer product flux under sealed capacity draws

## Scientific setting

Flux-balance analysis turns a stoichiometric network plus enzyme capacities into a
linear program: knock out reactions and overexpress enzymes, and the steady-state
flux distribution follows. Real strain engineering fails on the factory floor when
true capacities deviate from nominal — the design must keep producing across the
sealed draws, not just the textbook case.

## Your task

```python
def design_strain(problem):
    """Return {"knockouts": [enzyme names], "overexpressions": {enzyme: multiplier}}."""
```

`problem` is a mapping with the keys

```text
reactions                seventeen public reaction names
stoichiometry            metabolite -> reaction -> coefficient (steady-state rows)
nominal_capacity         public upper bounds per reaction
enzymes                  the six editable enzymes, each mapping to the reactions it
                         catalyzes — an edit acts on every reaction in its map
max_enzyme_edits         at most three knockouts plus overexpressions combined
overexpression_range     [1.0, 4.0]
engineering_budget       the sum of (multiplier - 1) over overexpressed enzymes
biomass_fraction_gate    the strain must hold biomass at or above half the
                         un-engineered maximum under the same capacities
capacity_note            true capacities deviate from nominal by up to 35 percent and
                         are sealed; the alternative route and glyoxylate shunt give
                         the network real trade-offs
```

## Evaluation

- The oracle re-solves the linear programs under sealed capacity draws: the wild
  type anchors zero, the frozen truth-blind witness design anchors one, and your
  design's product flux closes the gap. No literal anchors are stored, and every
  scored draw is checked to keep the witness strictly above the wild type.
- Beating the witness design on a draw scores above one — the record is open.
- Feasibility requires the biomass gate under each scored draw and the shared
  engineering budget; infeasible or contract-violating designs score zero, and
  degenerate draws (witness no better than the wild type) are excluded by
  construction so no draw hands out free points.
- `robustness_score` repeats the audit on held-out draws.

This is a toy stoichiometric network, not a claim about any organism.

## Rules

- Only edit `solution.py`; keep the complete function signature.
- Deterministic Python/NumPy/SciPy/stdlib code only; no network or process creation.
- Do not read `verification/` or `frontier_eval/`.

Reference: Orth, Thiele & Palsson (2010), Nat. Biotechnol., doi:`10.1038/nbt.1614`.
It motivates flux-balance analysis; the benchmark uses the declared toy network.

## 关系与区别 / Relationship to nearby tasks

BSM1AerationControl and BOPTESTSupervisoryControl operate dynamic control loops;
GeneNetworkIntervention recovers network structure from perturbation data. This task
is a single-shot edit-set design evaluated by re-solving steady-state linear programs
under sealed capacity draws, with the witness anchor recomputed rather than stored.

## Admission and reference scope

This package remains **candidate**. The runnable reference is a worst-case greedy
enzyme-edit search over stratified draws from the public deviation model, under
the shared engineering budget; it reaches 0.85 and leaves continuous-multiplier
allocation as documented headroom. Local shortcut
and ablation diagnostics are recorded in `references/known_best.md`; they do not
replace clean Linux sandbox replay, independent metabolic-engineering review or a
frozen frontier-model calibration draw.

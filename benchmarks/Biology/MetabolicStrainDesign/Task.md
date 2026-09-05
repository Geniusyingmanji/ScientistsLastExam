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
    """Return {"knockouts": [reaction names], "overexpressions": {name: multiplier}}."""
```

`problem` is a mapping with the keys

```text
reactions                ten public reaction names
stoichiometry            metabolite -> reaction -> coefficient (steady-state rows)
nominal_capacity         public upper bounds per reaction
essential_reactions      knockouts that cannot yield a viable strain
editable_reactions       reaction names edits may target
biomass_fraction_gate    the strain must hold biomass at or above this fraction of the
                         un-engineered maximum under the same capacities
max_edits                at most five knockouts plus overexpressions combined
overexpression_range     [1.0, 4.0]
capacity_note            true capacities deviate from nominal by up to 35 percent and
                         are sealed
```

## Evaluation

- The oracle re-solves the linear programs under sealed capacity draws: the wild
  type anchors zero, the frozen truth-blind witness design anchors one, and your
  design's product flux closes the gap. No literal anchors are stored.
- Beating the witness design on a draw scores above one — the record is open.
- Feasibility requires the biomass gate under each scored draw; infeasible or
  contract-violating designs score zero.
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
edit search over stratified draws from the public deviation model. Local shortcut
and ablation diagnostics are recorded in `references/known_best.md`; they do not
replace clean Linux sandbox replay, independent metabolic-engineering review or a
frozen frontier-model calibration draw.

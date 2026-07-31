# RNAInverseDesign — design a constrained sequence for a target ensemble

## Scientific background

RNA inverse folding asks for a nucleotide sequence that adopts a requested secondary structure.
Making every requested pair canonical is only a proxy: the same sequence can support alternative
pairings, so its minimum-free-energy (MFE) structure, target Boltzmann probability and ensemble
defect can disagree with pair compatibility.

This benchmark uses one explicit, reproducible abstraction rather than claiming to implement the
full Turner/ViennaRNA model. Structures are pseudoknot-free. A base pair `(i,j)` is allowed when
`j-i > min_hairpin` and the ordered bases are in the public energy table. Its energy is
`pair_energy[base_i + base_j]`. Directly nested pairs `(i,j)` and `(i+1,j-1)` also receive:

```text
-0.75 kcal/mol  if both pairs are GC or CG
-0.25 kcal/mol  if either pair is GU or UG
-0.45 kcal/mol  otherwise
```

Each pair that is not directly stacked on `(i+1,j-1)` instead pays the public
`loop_initiation_kcal` energy. The Boltzmann weight is `exp(-energy / (R*T))` with the `R`, `T`,
pair energies, loop initiation and minimum hairpin length provided in every problem. The trusted
evaluator sums the complete noncrossing ensemble by dynamic programming and computes exact
base-pair marginals.

## Your task

Implement:

```python
def design_rna(problem):
    """Return an A/C/G/U string or {"sequence": that_string}."""
```

Each problem provides:

- `target_structure`: dot-bracket target;
- `length`, `min_hairpin`, `temperature_kelvin`, `gas_constant_kcal`,
  `loop_initiation_kcal` and `pair_energies`;
- `fixed_bases`: `(zero_based_index, base)` pairs representing functional constraints;
- `gc_fraction`: inclusive lower and upper bounds;
- `forbidden_motifs`: substrings that may not occur.

## Evaluation

For each sequence, the evaluator separately computes:

- target-pair compatibility, a cheap proxy;
- exact target Boltzmann probability;
- normalized ensemble defect from exact pair marginals;
- pair F1 between the MFE and target structures;
- exact utility, the geometric mean of target probability, ensemble correctness and MFE F1;
- transfer to held-out structure families and robustness to sealed temperature and energy shifts.

`combined_score` is normalized development exact utility. The weak baseline is a deterministic,
constraint-feasible ACGU repeat that ignores the target. Exact component, proxy, robustness,
held-out and per-instance metrics are evaluator-only. A proxy-perfect sequence can therefore
remain a poor ensemble design.

## Available tools and resources

Literature on McCaskill partition functions, RNA inverse folding, NUPACK and ViennaRNA can help
derive an exact or approximate search objective. External databases may supply structural motifs,
but no database contains the generated task-specific answer. The runtime candidate is networkless.

## Rules and scope

- Only edit `solution.py`; keep `design_rna(problem)`.
- Return exactly one deterministic sequence with the requested length and alphabet.
- Honor fixed bases, GC bounds and forbidden motifs.
- NumPy and SciPy are available; do not create processes or use the network.
- Do not read `verification/` or `frontier_eval/`.

This is a controlled sequence-design benchmark. It does not model pseudoknots, tertiary folding,
kinetics, cellular context or experimental function, and it is not evidence of a new RNA design.

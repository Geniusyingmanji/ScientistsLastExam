# MolecularLeadOptimization — build a diverse portfolio of novel, developable leads

## Scientific setting

Lead optimization is a multi-parameter problem, and it is a *portfolio* problem. A medicinal
chemistry program does not advance one compound: attrition from potency, selectivity, toxicity
and pharmacokinetics is high enough that teams carry several structurally distinct chemotypes
in parallel. Two analogues of the same scaffold usually fail for the same reason, so a series
of near-identical molecules is worth much less than the same number of genuinely different
ones.

That makes the hard constraint here **structural diversity, not drug-likeness**. Quantitative
estimate of drug-likeness (QED) is a smooth desirability function that peaks near 0.95 for
almost any well-formed medicinal-chemistry scaffold in the right size and lipophilicity window;
brute-force enumeration over a handful of privileged cores reaches that ceiling immediately.
What enumeration cannot do is field *many mutually dissimilar* scaffolds that all clear the
same physicochemical, synthetic-accessibility and assay-interference filters. How many such
chemotypes exist is not known, which is why this task is scored uncapped.

## Your task

Implement:

```python
def design_molecules(spec):
    """Return a list of SMILES for the requested lead-optimization profile."""
```

`spec` gives the full profile:

- `n_required` — the portfolio size you are being asked for;
- `mw_range`, `logp_range`, `tpsa_max`, `rotatable_max`, `hbd_max`, `hba_max` — the
  physicochemical window (Lipinski and Veber descriptors);
- `sa_max` — synthetic accessibility ceiling (Ertl–Schuffenhauer score, 1 = trivial,
  10 = intractable);
- `pains_allowed` — whether pan-assay interference substructures are tolerated;
- `diversity_max_tanimoto` — the pairwise similarity ceiling *within* your portfolio;
- `panel_novelty_max_tanimoto` — the similarity ceiling against the approved-drug panel;
- `max_submissions` — how many SMILES you may return.

Return a list of SMILES strings. Submit more than `n_required`: the oracle filters and then
selects, so over-submission is the intended strategy.

**RDKit is available to you.** This is deliberate. You are not being asked to recall molecules
from memory; you are being asked to write a search — fragment enumeration, a graph genetic
algorithm, scaffold hopping, matched molecular pairs, simulated annealing over SMILES edits, or
something better — and to run it against the same descriptors the oracle uses.

## Evaluation

A submitted molecule is retained only if it clears every stage:

1. parses to a single covalent species (salts and mixtures are rejected);
2. satisfies the whole physicochemical window and the synthetic-accessibility ceiling;
3. carries no PAINS substructure;
4. is **novel**: Tanimoto similarity below `panel_novelty_max_tanimoto` to every member of the
   approved-drug reference panel, on 2048-bit Morgan fingerprints with radius 2 — submitting a
   known drug back is recall, not design;
5. survives greedy diversity selection: candidates are considered in descending QED order and
   admitted only if dissimilar to everything already admitted.

With `n` = `n_required` and `top` the retained set truncated to `n`:

```text
score = ( Σ_{i ∈ top} QED_i / n ) / reference_mean_QED
```

`reference_mean_QED` is the mean drug-likeness of the structurally distinct approved drugs that
satisfy the same profile, computed at evaluation time from a 20-drug panel whose SMILES were
each checked against their published molecular weight.

The score is therefore smooth in **both** breadth and quality: a half-filled portfolio of
excellent molecules and a full portfolio of mediocre ones can score the same, and filling the
portfolio at approved-drug quality scores 1.0. There is **no upper clamp** — a full portfolio
above that quality level scores above 1.0.

A second, undisclosed profile with tighter physicochemical windows and a stricter diversity
ceiling is scored separately as `robustness_score`. A search tuned to the development scaffold
space will lose ground there.

## Rules

- Only edit `solution.py`; keep `design_molecules(spec)`.
- Deterministic CPU code: Python standard library, NumPy, SciPy and RDKit only.
- The same callable is applied to both profiles. Do not hard-code the development profile's
  numbers; read them from `spec`.
- No network or process creation. Do not read `verification/` or `frontier_eval/`.

References: Bickerton et al., DOI `10.1038/nchem.1243` (QED); Ertl and Schuffenhauer,
DOI `10.1186/1758-2946-1-8` (synthetic accessibility); Baell and Holloway,
DOI `10.1021/jm901137j` (PAINS); Lipinski et al., DOI `10.1016/S0169-409X(96)00423-1`;
Veber et al., DOI `10.1021/jm020017n`; Jensen, DOI `10.1039/C8SC05372C` (graph GA baseline
for molecular optimization); Brown et al., DOI `10.1021/acs.jcim.8b00839` (GuacaMol).

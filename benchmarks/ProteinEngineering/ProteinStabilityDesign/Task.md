# ProteinStabilityDesign — allocate assays and design a stable protein batch

## Scientific setting

This task is an offline experimental-design replay built from the Tsuboyama et al. cDNA-display
proteolysis landscapes distributed in ProteinGym v1.3.  In each protein domain, exactly two
positions may be changed.  Hundreds of feasible double mutants have measured stability, but you
receive only the wild-type sequence and the corresponding single-mutation scores.  Those
single-mutant scores form a useful additive proxy, yet double-mutant epistasis means that simply
choosing its top sequences can promote poor designs.

You can spend a small assay budget to reveal selected double-mutant measurements, then submit a
diverse batch for follow-up.  The point is to implement a reusable batch-design policy under
limited evidence, not to identify a memorized sequence from a named public table.

## Your task

Implement:

```python
def design_stable_batch(problem, assay):
    """Return {"sequences": [eight distinct feasible amino-acid sequences]}.

    assay(sequence) returns:
      stability_ddg:          measured ProteinGym/Tsuboyama ddG_ML_float;
  combined_delta_g_95ci:  conservative interval width across duplicate constructs;
      budget_cost:            one charged assay unit;
      remaining_budget:       units left after this assay.
    """
```

`problem` contains:

- `wild_type_sequence` and two zero-based `mutable_positions`;
- `candidate_residue_pairs`, the feasible residue pair for every assayed double mutant;
- `single_mutation_proxy`, containing each position's public single-mutant scores;
- `batch_size == 8` and `assay_budget == 12`.

Construct a feasible sequence by copying the wild type and replacing the two mutable positions
with one listed residue pair.  Assays are deterministic replays of the frozen experimental table.
Repeated assays still consume budget.  Invalid queries and budget overruns fail the world even if
candidate code catches the callback exception.  A final sequence does not have to have been
assayed, so a policy may generalize from measured pairs.

## Evaluation

- `combined_score` is development batch utility normalized so the additive-proxy top eight score
  zero and a strong diversity-aware full-landscape reference scores one.  Utility combines mean
  measured stability and pairwise batch diversity.
- evaluator-only top-decile hit rate, mean measured stability, batch diversity, assay efficiency,
  selected-but-unmeasured fraction and additive-proxy false promotions diagnose the policy.
- `robustness_score` independently replays the raw trypsin and chymotrypsin stability readouts.
- `heldout_policy_score` and `heldout_robustness_score` apply the same code in three held-out
  protein domains.

No one scalar establishes a scientific discovery.  A high proxy score without experimental
utility is a false promotion; a high joint score with poor performance in one protease is not
robust evidence.

## Available tools and resources

Literature on protein stability, epistasis, active learning and batch experimental design can
inform the policy.  The runtime candidate is networkless and cannot read the frozen evaluator
data.  NumPy and SciPy are available.

## Rules and scope

- Only edit `solution.py`; keep `design_stable_batch(problem, assay)`.
- Return exactly eight distinct, feasible, full-length amino-acid sequences.
- Use at most twelve assays per protein domain.
- Deterministic CPU code only; no network or process creation.
- Do not read `verification/` or `frontier_eval/`.

This benchmark replays already published measurements.  It does not design a new protein,
perform a wet-lab experiment, validate biological function or by itself demonstrate autonomous
scientific discovery.  Public DMS landscapes also remain vulnerable to lookup and require future
server-held proteins for deployment claims.

Only source records with finite, non-dummy trypsin and chymotrypsin estimates and combined plus
protease-specific 95% interval widths no greater than 0.5 kcal/mol enter the frozen landscapes.

References: Tsuboyama et al., *Nature* 620, 434–444 (2023), DOI
`10.1038/s41586-023-06328-6`; ProteinGym v1.3, DOI `10.5281/zenodo.15293562`.

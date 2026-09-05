# MetagenomicMixtureID — recover a strain mixture from purchased sequencing depth

## Scientific setting

Shotgun metagenomics profiles a microbial sample by mapping reads to a reference
marker database: genome-specific markers expose which strains are present and at what
abundance, while conserved core markers fire for everything alive in the tube. A
novel organism outside the database contributes only to the conserved core — an
excess no library assignment can explain, and a mixture claim that ignores it is a
false discovery.

## Your task

```python
def identify_mixture(problem, run_sequencing, budget_units):
    """Return {"present": [genome ids], "abundances": {id: fraction summing to one},
               "abstain": bool, "confidence": float in [0,1]}."""
```

`problem` is a mapping with the keys

```text
genome_ids            thirty library genomes
marker_database       marker -> {genome, type} with unique and conserved types
sequencing_depths     [1, 2, 5, 10, 20] purchasable depth units
reads_per_depth_unit  5000 reads per depth unit
mapping_note          the public read-allocation statement
run_cost / budget_units  1 / 6
```

`run_sequencing(depth_units)` charges one unit per run (repeated depths allowed,
fresh independent noise) and returns `{depth_units, total_reads, marker_counts,
budget_cost}` with per-marker read counts. Overspending or unknown depths invalidate
the world even when caught.

## Evaluation

- `combined_score` is development mixture recovery above the always-abstain
  baseline: 0.7 x set F1 plus 0.3 x an abundance score exp(-2 x mean |log ratio|).
- Novel-organism worlds score refusal only: abstaining scores one, any library
  mixture claim scores zero and counts as a false discovery.
- Set F1, false discovery rate, correct refusal rate and discovery coverage are
  reported with denominators; a full abstention scores exactly zero.
- `robustness_score` repeats the audit on held-out mixtures and novel shares.

This is a deterministic marker-count simulation, not a claim about any real biome.

## Oracle and difficulty

Mixtures hold two to five seeded strains with Dirichlet weights; novel worlds give a
hidden organism 15 to 40 percent of the read mass. Read allocation follows the
public statement (0.6 unique / 0.3 conserved / remainder dropped, novel reads only
on conserved markers).

## Rules

- Only edit `solution.py`; keep the complete function signature.
- Deterministic Python/NumPy/SciPy/stdlib code only; no network or process creation.
- Do not read `verification/` or `frontier_eval/`.
- Sequencer errors and overspending invalidate the world even when caught.
- Use `sle.contract_lint` for free local shape checks before returning an inference.

Reference: Truong et al. (2015), Nat. Methods, doi:`10.1038/nmeth.3589`. It motivates
marker-based taxonomic profiling; the benchmark uses the declared simulation.

## 关系与区别 / Relationship to nearby tasks

CrowdedSpectrumAssignment identifies library species in a blended optical spectrum
with zooming resolution. This task buys shotgun sequencing depth against Poisson
read counts, estimates continuous abundances, and its refusal world is a novel
organism visible only as a conserved-core excess — a statistically testable
signature rather than an unresolvable peak overlap.

## Admission and reference scope

This package remains **candidate**. The runnable reference uses public inputs only:
pooled runs, a Poisson presence threshold per genome, unique-mass abundance
normalization and a four-sigma conserved-excess novelty test. Local shortcut and
ablation diagnostics are recorded in `references/known_best.md`; they do not replace
clean Linux sandbox replay, independent review or a frozen frontier-model
calibration draw.

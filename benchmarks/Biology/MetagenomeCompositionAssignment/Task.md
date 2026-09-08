# MetagenomeCompositionAssignment — composition, aliases, or an inadequate library

This candidate submission is withdrawn pending instance redesign. The branch preserves
the repaired executable contract; it is not an admitted or recalibrated benchmark.

## Question and nearest tasks

Allocate marker-panel sequencing and infer the taxa and abundances in a mixture. Exact reference
aliases must remain an ambiguous group; a strong marker outside the reference cone means the
library is inadequate. Spectroscopy/CrowdedSpectrumAssignment separates continuous spectral lines
by resolution, whereas this task uses multinomial marker counts and reference-column identifiability.

## Interface

Implement assign_composition(problem, sequence). sequence(panel_id) charges one panel and returns
the keys panel_id, read_count, and marker_counts.

Problem keys are taxon_ids, marker_ids, reference_profiles, initial_observation, available_panels,
panel_markers, panel_budget, minimum_reported_abundance, abundance_tolerance, and
known_alias_groups. Four overlapping follow-up panels compete for a budget of two.

Return exactly:

    {
      "taxa": [{"taxon": "t4", "abundance": 0.35}],
      "ambiguous_groups": [["t0", "t1"]],
      "abstain": False
    }

Taxa must be unique and abundances finite in [0,1]. Ambiguous groups must exactly match a declared
known_alias_groups entry, cannot overlap concrete taxa, and earn credit jointly with the abundance
of identifiable mixture members. Each reported group counts as one claim. A known alias
group is not evidence that its members occur in the sample: in supported worlds an
absent group reduces taxon-set precision and counts as a false claim; in library-inadequate
worlds every taxon or group claim is false. All-world false-discovery rates
count both concrete taxa and groups in their denominator. In alias worlds, all extra unsupported concrete taxa
count as false discoveries and reduce composition credit through claim precision; a correct
alias group does not excuse unrelated false species. Use abstain only when the reference library cannot explain the
sample; then taxa and groups must be empty. The evaluator separately reports composition
recovery, all-world false discovery, separate alias resolution and library refusal, coverage, and held-out
performance. Blanket abstention and the single-marker baseline score zero.

This is a controlled marker-count model. It evaluates mixture reasoning, not a clinical or
environmental identification claim.
sle.contract_lint is importable and free to call for submission-shape checks.

## Accuracy normalization

Absolute abundance tolerance is **0.025** (2.5 percentage points), exposed as
`abundance_tolerance`. An abundance error at or above this value earns zero
abundance credit; exact identifiable abundances define that component's 1.0.
Taxon-set F1, alias grouping, false-claim penalties, library-inadequacy refusal
and the blanket-refusal floor are unchanged. This tightens scientific accuracy,
not the number of observations or the reference algorithm.

Any invalid world makes the entire submission invalid: aggregate development and
held-out scores are zero. Per-world diagnostics are retained only in trusted reports.

Nearest task forms: CrowdedSpectrumAssignment and TransmissionSpectrumSpecies also require evidence for distinguishable components; this task uses marker-count mixtures, but current exact aliases and sentinel markers still require redesign.

Both splits use `max(0, (mean_scientific - library_world_fraction) /
(1 - library_world_fraction))`. Alias resolution and library refusal have separate
rates and world counts. FDR uses all taxon/group claims as its denominator;
`claim_count` is reported for each split.

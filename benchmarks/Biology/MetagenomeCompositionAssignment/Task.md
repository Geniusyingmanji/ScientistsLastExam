# MetagenomeCompositionAssignment — composition, aliases, or an inadequate library

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
worlds every taxon or group claim is false. Unsupported-world false-discovery rates
count both concrete taxa and groups in their denominator. In alias worlds, all extra unsupported concrete taxa
count as false discoveries and reduce composition credit through claim precision; a correct
alias group does not excuse unrelated false species. Use abstain only when the reference library cannot explain the
sample; then taxa and groups must be empty. The evaluator separately reports composition
recovery, unsupported-world false discovery, alias/library refusal, coverage, and held-out
performance. Blanket abstention and the single-marker baseline score zero.

This is a controlled marker-count model. It evaluates mixture reasoning, not a clinical or
environmental identification claim.
sle.contract_lint is importable and free to call for submission-shape checks.

## PR scope coordination

The near-duplicate `Metagenomics/MetagenomicMixtureID` has been removed from
[PR #9](https://github.com/Geniusyingmanji/ScientistsLastExam/pull/9) and is not
in its [Chemistry/Biology split #22](https://github.com/Geniusyingmanji/ScientistsLastExam/pull/22).
This package is retained as the single marker-panel composition task in this
contribution. Removal of the competing submission resolves the duplication
concern; stronger difficulty calibration remains pending.

## Accuracy normalization

Absolute abundance tolerance is **0.025** (2.5 percentage points), exposed as
`abundance_tolerance`. An abundance error at or above this value earns zero
abundance credit; exact identifiable abundances define that component's 1.0.
Taxon-set F1, alias grouping, false-claim penalties, library-inadequacy refusal
and the blanket-refusal floor are unchanged. This tightens scientific accuracy,
not the number of observations or the reference algorithm.

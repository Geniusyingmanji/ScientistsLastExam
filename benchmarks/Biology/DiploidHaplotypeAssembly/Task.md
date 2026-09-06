# Diploid Haplotype Assembly

Implement `assemble_haplotypes(problem) -> {"haplotype": [0, 1, ...]}`.
Return exactly that key and one Python integer bit per variant; booleans, floats,
nonfinite values, wrong lengths and extra keys are invalid. NumPy and SciPy are available.

`variant_ids` orders 200/240 development or 280/320 held-out anonymous heterozygous
loci. `block_ids` contains two disconnected read blocks. Each of `fragments` has
`positions` (distinct zero-based variant indices), `alleles` (aligned bits), and
`error_probabilities` (aligned per-base error probabilities). `noise_model` is
`independent_flip_equal_homolog_mixture`: independently choose one homolog with
probability 1/2 for each fragment, then independently flip each observed allele
with its given probability. There is no Hi-C, correlated error or coverage bias.
Fragments contain 3–8 loci; block flips are independently unidentifiable.

Maximize the sum over fragments of
`log((prod_k P(a_k|h_k) + prod_k P(a_k|1-h_k))/2)`, where the probability is
`1-e_k` for a match and `e_k` otherwise. The oracle uses log-sum-exp. True phase
never enters this objective. Complementing any complete block leaves it invariant.
A read is a mixture as a whole: multiplying per-site averaged likelihoods loses
linkage. Input order conveys no biological phase.

Per world the score is `clip((L-L_zero)/(L_reference-L_zero),0,1)`.
`L_zero` is the all-zero phase. The frozen input-only reference uses the leading
eigenvector of the signed read Gram matrix then up to 12 exact bit-flip sweeps
(see trusted evaluator). This is a normalization anchor, not an optimum claim.
Development score averages worlds 0–1; worlds 2–3 have larger blocks and higher
errors and are held out from the search score. Invalid output scores zero;
`valid` is one only if every world is valid. Independent new-fragment mean
log likelihood and block-aligned phase accuracy are sealed diagnostics.
All worlds are procedural and repository-visible, not server-secret instances.

Baseline: all-zero phase, exactly zero. Expected runtime budget: 120 CPU seconds
for a candidate evaluation. No filesystem access to verification is allowed.
The reference and its seed are evaluator internals, not extra candidate inputs.

Nearest tasks: DemographicSFS infers population history from frequency spectra;
MetagenomeCompositionAssignment infers species mixtures; PhylogeneticParsimonySearch
constructs species trees. This task reconstructs within-individual read linkage.
The model is motivated by [HapCUT2](https://doi.org/10.1101/gr.213462.116);
no HapCUT2 code or individual genome data is redistributed. External review and
comparison to HapCUT2 are pending; expert-level difficulty is not established.

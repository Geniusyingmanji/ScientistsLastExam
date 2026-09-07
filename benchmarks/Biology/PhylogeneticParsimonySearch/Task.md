# PhylogeneticParsimonySearch — search unrooted binary tree space

## Question and nearest tasks

Return a binary Newick tree with low Fitch parsimony cost for the supplied alignment. The task is
an optimization benchmark: equal-scoring trees receive equal credit, and no claim is made that the
minimum-parsimony tree is the true evolutionary history. Unlike Algorithm/GraphFromDistances, the
artifact is a tree optimized against character changes, not an unknown graph recovered through
distance queries. Unlike Mathematics/NonlinearCodeRecords, validity is tree topology and the
objective requires ancestral character minimization.

## Interface

Implement build_tree(problem), returning a string.

Problem keys are taxa, alignment, criterion, and missing_symbol. Taxa are leaf labels that must
each occur exactly once; alignment contains one equal-length ACGT sequence per taxon in the same
order; criterion is unordered_fitch_parsimony; missing_symbol reserves the question-mark marker.

Return one rooted representation of an unrooted binary topology, for example
((t0,t1),(t2,t3));. Branch lengths and internal labels are not accepted. The verifier parses the
tree independently and computes Fitch cost site by site. Score is clipped to [0,1]:
`clip((C_baseline-C_tree)/max(1,C_baseline-C_lower),0,1)`. The baseline is a
caterpillar tree. `C_lower = sum_site(number_of_distinct_observed_states-1)`
is a topology-independent lower bound: every additional observed state requires
at least one change on any tree. Equality may require incompatible per-site trees,
so 1.0 is a relaxation bound, not an asserted attainable optimum. Average linkage
is a comparison reference below this bound; NNI search earns strictly more credit.
Held-out alignments are separate. This task makes no uncapped record claim.

The alignments are deterministic procedural panels designed to test tree search. They are not a
new phylogeny or a biological inference result.

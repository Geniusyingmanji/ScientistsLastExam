# PhylogeneticParsimonySearch reference evidence

## Scoring
Parsimony gap closure is nonnegative and uncapped above a recomputed average-linkage witness.
## Anchor
No external best-known score is embedded; both anchors are recomputed on every alignment.
## Baseline
The deterministic taxon-order caterpillar scores 0.
## Reference
The truth-blind average-linkage tree scores 1.0 development and held out by construction. The
repository's truth-blind NNI headroom probe improves every frozen alignment and scores above 1.
## Ablations
Random taxa order, neighbor joining, SPR and ratchet probes remain required; NNI is executable in
verification/headroom_probe.py.
## Shortcut and robustness
Mature search methods may exceed the witness; uncapped scoring preserves measurable headroom.
## Provenance
Search heuristics are grounded in the Parsimony Ratchet (doi:10.1111/j.1096-0031.1999.tb00277.x) and MPBoot (doi:10.1186/s12859-018-2009-1). Retrieved 2026-09-05.

# MetagenomeCompositionAssignment reference evidence

## Scoring
Composition/refusal utility is normalized above blanket abstention and the single-marker baseline.
## Anchor
Reference profiles and procedural worlds are deterministically recomputed by the evaluator.
## Baseline
Single-marker nearest-reference assignment scores 0.
## Reference
Panel-conditional mixture fitting with exact alias grouping, abundance scoring and residual refusal
scores about 0.903 development and 0.959 held out.
## Ablations
Unweighted nearest column, NNLS without alias handling, no residual refusal and blanket genus grouping are required probes.
## Shortcut and robustness
The PR-review probe adds five false taxa to each alias-world reference output. Previously the
score and false-discovery count were unchanged. After repair the development score drops from
0.903336 to 0.636460; held-out scientific utility drops from 0.959084 to 0.725724. The false
claim count is 10, denominator 12, and unsupported-world FDR is 0.833333.
The prototype omits read mapping and copy-number error; it is a mechanism test, not a real-sample benchmark.
## Provenance
Taxonomic profiling form is grounded in TIPP (doi:10.1093/bioinformatics/btu721). Retrieved 2026-09-05.

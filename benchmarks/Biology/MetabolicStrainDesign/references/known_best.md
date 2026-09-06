# MetabolicStrainDesign reference evidence

## Scoring
Clipped normalization from the unchanged strain to exhaustive search over at most four allowed knockouts.
## Anchor
The anchor is recomputed by verification/reference_design.py for every public problem; it is not an external SOTA.
## Baseline
No knockouts gives zero worst-case product on every development panel and score 0.
## Reference
The truth-blind exhaustive witness scores 1.0 development and held out.
## Ablations
Single knockout, greedy knockout, nominal-product-only and arbitrary-optimum probes remain required before calibration.
## Shortcut and robustness
The former two-pool model was saturated by deleting public columns (0,-1); that failure is
retained as construction history. The replacement five-pool model adds energy-consuming growth,
intermediate branches and alternative energy production. Deleting all terminal drains scores
0/0; deleting all allowed redox-consuming reactions scores 0.822276/0.854729; fixed first-four
positions score 0.157783/0 (development/held-out). These comparisons defeat the tested structural
rules, not arbitrary future shortcuts. Exhaustive search still saturates the small prototype;
larger networks and model calibration remain required for difficulty evidence.
## Provenance
Scientific form follows OptKnock (doi:10.1002/bit.10803) and RobustKnock (doi:10.1093/bioinformatics/btp704). Retrieved 2026-09-05.

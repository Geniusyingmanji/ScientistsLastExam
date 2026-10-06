# Fixed observation-only lineage screen — 2026-10-07
Frozen before sampling. Synthetic development only; no held-out/model claim.
Three exposed fixtures: mu=.5, batch=.2,p=c=.5,n=32; lineage=.4,.1,0.
For each fixture compare neither-shared control to founder-only shared treatment.
Exactly2000pairs/arm, two independent calls with noise seeds9100+2i and9101+2i.
Six calls maximum,768000simulated individuals, no fits/retries/adaptive stopping.
Use existing fixed_interval with alpha=.05/3 (Bonferroni family of three).
Record all intervals and truth coverage; three outcomes cannot establish empirical
coverage or general power. Do not promote if only strong effects distinguish.

## Result and decision
All6calls completed,768000individuals, approximately0.070s sampling/serialization
wall time on this host. Intervals: strong[.006261,.075453], weak[-.031550,.037642],
null[-.033437,.035755]. Strong excludes zero; weak/null do not. All three cover
fixed truths, which is not a coverage-rate estimate. No extra samples collected.
Decision: defer full World implementation under the current observation policy.
Current evidence supports a strong-effect design witness, not robust weak-effect
research or generic high difficulty. Small computational time does not erase the
experimental sample cost. Preserve candidate; revisit only with a justified
candidate-visible uncertainty method or a different budgeted scientific design.
Next candidate screening should prioritize distinct physics (seismic inverse
response) rather than another covariance wrapper.

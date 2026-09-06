# BatchEffectDiscovery reference evidence

## Scoring
Scientific utility is normalized above the frozen batch-blind baseline and the best no-discovery policy (correct confounding refusal plus blanket effect denial).
## Anchor
All panels and truth sets are deterministically recomputed by the evaluator.
## Baseline
Marginal log-fold change ignoring batch scores 0 after normalization.
## Reference
After removing the layout label leak, balanced cross-cell sampling and batch-adjusted regression
score 0.511369 development and 0.655606 held-out raw scientific utility. These are different
scales: the development score is normalized; held-out scientific utility is raw. The reference
makes one unsupported-world false claim (FDR 1/1), so it is not a calibrated domain standard.
The previous 0.926/0.969 measurements describe the superseded world generator.
## Ablations
No follow-up, batch-blind regression, fixed fold-change, blanket discovery and blanket abstention are required probes.
## Shortcut and robustness
All worlds now have four initial rows and the supported/null menus are identical. Blanket denial
and a layout-only refusal/denial strategy both score exactly zero. A standard fixed pipeline may
still saturate this prototype; admission requires frontier draws and server-held panels.
A construction-time threshold sweep (0.45–0.70) was inspected diagnostically; the shipped
threshold remains the original 0.55, with balanced sampling replacing one-cell sampling.
These inspected panels are development evidence, not a fresh blind confirmation.
## Provenance
Count modeling follows DESeq2 (doi:10.1186/s13059-014-0550-8) and ComBat-seq (doi:10.1093/nargab/lqaa078). Retrieved 2026-09-05.

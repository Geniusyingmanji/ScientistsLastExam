# Prediction scope audit

New observations are not automatically out-of-distribution or mechanism discovery.
The isotope pilot used random static recipes and recipe-to-unlabeled chase at the
same switch time already present in training. Its pooled RMSE therefore supports
fresh-query prediction under a known family, not novel temporal structure or a
structural holdout. Keep the published result intact and narrow its interpretation.

The new public development_design.py defines separate static-recipe, three-segment
history and ambiguity-control panels. This is a design fixture, not another model
run or new scientific calibration. Fixtures are exposed, not sealed test cases.
Future scoring must retain per-axis errors rather than pooling away distinctions.
An independent-source negative control is intentionally nondiscriminating.
Assigned initial fractions should be excluded from future scored prediction cells;
the old development RMSE included them and must not be silently recalculated.

Next integration gate: freeze an explicit prediction-cell mask and implement
isotope claim/evidence adapters with fail-closed behavior before registry admission.
No changes to v1 frozen scoring or runtime are authorized by this audit.

# PR 59: preserve the measured two-point logit gain

Reviewed source: `ea2ee20e25163e47f239f89c168cba1b7c33952a`.

`shortcut_probe._candidate(..., two_point=True)` computed a gain from the public
trials, then replaced it with the constant parameter-grid gain. Initialize the
constant parameters before selecting the two-point variant so the estimated gain
is bounded and used in both the submitted parameters and probability predictions.

Four synthetic regressions check an interior estimate, both bounds, and the
unchanged constant-gain variant. On the original implementation, the three
two-point cases fail and the constant case passes. After this fix all four pass
on local Python 3.14. These are candidate-logic checks, not scientific oracle runs.

The evaluator, world definitions, reference, parameter grid and model evidence
are unchanged. No model draw or new parameter search was performed for this fix.
The previously published 3,456-strategy scores describe the pre-fix probe and
must not be attributed to this corrected implementation. Replaying that fixed
strategy family through Linux and checking it against the complete reference
remain required before updating admission evidence or merging the task.

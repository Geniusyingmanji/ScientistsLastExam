# Post-hoc homogeneous family audit — 2026-10-07

Diagnostic of the already observed noisy screen, not a prospective rejection.
No new samples. Use source observations and target observations already archived.
Known measurement SD .001; Bonferroni Gaussian bound across4source+3target
values, family alpha .05. Under homogeneous model t=sqrt(a+b*x²), transform
positive time bounds to linear constraints on a,b within original[.01,100]bounds.
For each target offset[1,2,4], solve two linear programs for minimum/maximum
squared time (six solves total, maximum1000iterations each). Compare family
prediction ranges with observed target measurement ranges. Stop on solver
failure; no parameter-grid tuning. Intersections at separate points do not
prove one joint parameter fits all points. Because chosen after results, this
is a descriptive audit only; it cannot be promoted to prospective significance.

Result: all6solves succeeded. Measurement half-width .00269011. Family target
ranges were [2.034815,2.070452], [2.128811,2.275230], [2.469269,2.955718].
Each overlaps its corresponding observed-measurement range. Therefore no single
target point rejects the source-compatible family with this diagnostic. The
large point-predictor RMSE alone does not demonstrate model-family rejection.
This audit did NOT solve joint source-and-target feasibility, so it does not
establish that one homogeneous parameter pair explains all observations.
Next test joint feasibility as a separately bounded calculation, then decide
whether a wider source aperture or tighter measurement design is required.

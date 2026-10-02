# Fixed spin-echo reference study

This is a zero-API engineering reference study on six previously used author
instances, not a GPT score or an estimate of scientific discovery. The frozen
world source was `cb275fa2d1d230e1d8786b8991383aa35ed5aebf`. The three existing
operator strata contributed two instances each; this is not a random unseen
cohort.

The reference receives the same two noisy source records as the unchanged weak
baseline: a dense free-induction scan and a Hahn-echo measurement. Together these
contain 121 rows, 363 scalar readings and 148 public experimental units per
instance. The author supplies a common constant nonnegative transverse-decay
rate and static-offset model class. The method estimates that rate and
interpolates the empirical complex free-induction response; it does not discover
the model class. Hidden offsets, weights and operator labels do not enter the
fit. The fixed rate rule clamps two noisy echo amplitudes above one to zero
decay; those cases remain in the results.

All source records were sealed before fitting, and all predictions were sealed
before acquiring the clean targets. The resulting errors are means of per-query
x/y RMSE, averaged equally across the six instances. Known z coordinates are
excluded from this primary diagnostic.

| Predeclared panel | Queries per method | Reference RMSE | Weak baseline RMSE |
|---|---:|---:|---:|
| New effective-time interpolation | 18 | 0.00133015 | 0.44230373 |
| Late-horizon echo | 18 | 0.00122630 | 0.50526578 |
| Known apparatus transfer, secondary | 12 | 0.00187160 | 0.78641059 |

The reference improved on all 30 pulse/late-echo instance-query pairs. The six
plain free-induction interpolation pairs tied to numerical precision; their
common mean RMSE was 0.00152268. The 12 apparatus comparisons were counted
separately. No planned prediction or target was missing or failed. The reference
was restricted to integer-pi controls and effective times within the measured
120 ms support, even for observations later in laboratory time.

These errors do not establish a statistical noise floor: targets were clean,
while shared noisy source data, interpolation and fitted damping induce
correlated prediction errors. The public sensor sigma of 0.002 is only a scale
reference. The study does not establish arbitrary-pulse transfer, unique
microscopic identification, unseen-structure generalization or budget scaling.
The additional physics prior and dense observations must remain explicit in
future comparisons.

The native run used 60 World attempts, each with one nested physical solve,
6 fits and 96 predictions, with no API calls. Whole-process accounting recorded
14.29 seconds wall time and 0.396 seconds CPU, including native process exit and
log closure but excluding serialization of the outer accounting receipt.
An independent-context, same-model-family review recomputed the saved matrices,
metrics and counts and passed 392 arithmetic/hash/order checks. This review is
provisional and pending external review; no experiment-integrity certification
is available. Local hashes and ordered records establish internal consistency
under the trusted operator, not external immutable chronology.

Raw observations, predictions and instance identities remain in the private
operator archive. Its SHA256 is
`6fed787a557519cc60bdf29ee9a3d03fced1cfdbe5049261ab4c2acf8d124029`;
the review seal is
`f757ced734b4ef5c57806f03b48e7d82cffa7b7b2ccac641fe967dd278c016ab`.
No historical model score or default public baseline was replaced.

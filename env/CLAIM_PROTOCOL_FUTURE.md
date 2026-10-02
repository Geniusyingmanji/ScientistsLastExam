# Future claim diagnostics — development proposal, disabled

This is a separate proposal, not an amendment to pilot scoring. No existing
cohort is rescored. `claim_protocol_diagnostics.py` imports no world, runner or
scoring code and makes no simulator/network calls.

## Finite calibration plan (written before execution, 2026-10-03)

Use 10,000 independent synthetic episodes per cell, eight observations per arm,
three slots, familywise alpha 0.05, root seed 20261003. Sensor sigma is 1 for
scale invariance. Cells are Gaussian at latent mean 0 and zero-clipped Gaussian
at latent means 0, 0.5, 3.0. These are sensor-law reference distributions, not
world instances. Zero-clipped means `max(mu + sigma*Z, 0)`, not a Gaussian
conditioned to be positive.

For each sensor cell use four fixed protocols: (1) three prespecified null
contrasts; (2) choose the three largest absolute exploratory mean effects from
12 null candidates, then use entirely fresh confirmation; (3) deliberately
invalid control: select the largest three effects from 12 confirmation batches
and reuse those same batches; (4) two null slots and one fixed alternative with
latent treatment shift +1.5 sigma. Candidate pools and all counts stay fixed.
No retries, significance-conditioned stopping, threshold search or parameter
revision is permitted after inspecting results.

Report single-null-slot rejection frequency at 0.05 and actual episode false
rejection frequency before/after three-slot Holm control, plus alternative power
for protocol (4). Include denominators, Wilson Monte Carlo intervals, failures,
and planned/completed cells. Evaluate exact 256-sign two-sided randomization,
a conservative Gaussian-Lipschitz bound, and (Gaussian only) a known-noise normal
test. On clipped sensors, the known-Gaussian test must reject the requested route;
no Student-t formula is used. Also report the old three-sample-SE exceedance as
an explicitly uncalibrated diagnostic, never as a new test.

For interval loss, use a separate fixed 100,000-draw Gaussian future-mean sample
(seed branch 100), sigma/sqrt(4)=0.5. Compare centered half-widths
0.8*z_0.95, z_0.95 and 1.2*z_0.95 in units of future-mean SD against the analytic
expected raw interval loss. This is a fixed diagnostic grid, not threshold
optimization. The existing Gaussian exponential-score counterexample is not
rerun or used to tune parameters.

Exact tests cover ties/zero differences, arm reversal, scale invariance,
invalid assumptions, known analytic Gaussian p-values, and Holm with missing
slots and arbitrary dependence. A small seeded simulation checks deterministic
replay and complete accounting. Statistical fluctuations do not trigger
recalibration or test changes. A failed operational run must retain its error;
only implementation defects may be fixed, with their effects disclosed.

## Proposed separation

1. **Forecast loss.** Report raw 90% interval loss
   `U-L + 20*max(L-y, y-U, 0)`, divided only by the fixed public channel scale.
   Target `y` is the mean of eight future noisy treatment-minus-control
   measurements, not a latent noise-free contrast. Average these losses without
   exponentiation, clipping, or conditioning on significance. Lower is better.
   Coverage, width and submitted-slot count are separate fields. Propriety holds
   conditional on a fixed forecast target; adaptive question/slot selection
   changes task difficulty, so this does not create a globally proper score for
   arbitrary self-selected/omitted questions. Missing slots have no invented
   zero loss. A future benchmark aggregate needs a separate fixed-target or
   participation policy. At atoms, quantiles can be nonunique; do not promise
   strict uniqueness for clipped sensors.
2. **Nonzero-effect evidence.** Test the null of zero difference in expected
   measured response separately from interval coverage or width. Known
   independent Gaussian noise gives exact two-sided z p-values using declared
   variances, not estimated SE. Under identical arm sensor laws and an equal
   latent response null, paired differences are independent and symmetric,
   even at the clipped boundary. Enumerating all 2^8 sign changes with inclusive
   ties gives a super-uniform randomization p-value; minimum nonzero two-sided
   p-value is 2/256. This tests a symmetry/exchangeability null, not arbitrary
   equality of means with heteroscedastic/nonidentical distributions.
3. **Episode error control.** Freeze at most three contrasts/readouts and
   tests before independent confirmation. Pad unused/ineligible/duplicate slots
   with p=1, then apply Holm to the three-slot family at 0.05. Report raw and
   adjusted p-values and rejected slot IDs. Holm permits arbitrary dependence
   across slots when each true-null p-value is super-uniform. Interval quality
   must not be relabeled a mechanism/discovery success rate.

For an explicitly conservative route, the average difference of n independent
Gaussian or zero-clipped Gaussian arm readings is a Lipschitz function of 2n
standard normals with squared constant
`v=(sigma_control^2 + sigma_treatment^2)/n`. Thus under zero expected measured
difference, `min(1, 2*exp(-mean_difference^2/(2*v)))` is a valid conservative
p-value bound. Sigma must be the declared pre-clipping Gaussian scale; sample
maxima or sample SE cannot replace it. This route permits unequal known arm
scales but addresses measured-mean equality. Unknown noise, intrinsic process
noise, shared correlated sensor draws and optional stopping require another
protocol; they are outside these guarantees.

With the same positive sigma and common zero-clipping transform,
`E max(mu+sigma Z,0)=mu*Phi(mu/sigma)+sigma*phi(mu/sigma)` is strictly increasing
in mu. Equality of latent responses and equality of measured means therefore
coincide under that restricted sensor model, although nonzero effect magnitudes
are distorted near zero. Unequal sigma destroys that equivalence; a nonzero
measured contrast may be pure sensor bias.

Arbitrary adaptive exploration is compatible with conditional validity only
when selected designs, readouts, intervals and method are frozen before a fresh
confirmation stream, and the declared test assumptions hold for every selected
null. Looking at confirmation to choose slots, revise intervals, choose tests,
retry, or stop early invalidates this argument. Repeated future confirmation
families need a prespecified alpha-spending or valid sequential procedure; this
module implements neither and must not be enabled automatically.

## References and scope

The interval-loss rationale follows [Gneiting and Raftery (2007), section 6.2](https://sites.stat.washington.edu/people/raftery/Research/PDF/Gneiting2007jasa.pdf).
Multiple-test control follows [Holm (1979)](https://www.ime.usp.br/~abe/lista/pdf4R8xPVzCnX.pdf).
The concentration route uses the mean-centered Gaussian Lipschitz inequality
in [Rinaldo, Advanced Statistical Theory, Theorem 6.2](https://www.stat.cmu.edu/~arinaldo/Teaching/36709/S19/Scribed_Lectures/Feb14_Beomjo.pdf).
The sign-flip validity argument here is direct: under the exchangeability null,
conditional on absolute differences each nonzero sign is independent uniform;
zeros and ties are included in every permutation count, conservatively.

The source audit examined `claim_calibration.py`, `scoring.py`, `EVALUATION.md`
and the central `gaussian-score-incentive-audit.json`. The pilot exponential
reward remains unchanged; the proposed raw loss and error-control endpoints
are diagnostic outputs only. Development results below are not evidence about
old-model performance or universal power.

## Recorded development results (2026-10-03)

All 16/16 planned cells completed, with 0 operational failures. Each cell has 10,000 episodes; there were no simulator queries, API calls, or old-cohort accesses. NumPy 2.3.5; root seed 20261003; source SHA256 `053cb4a4111aa5a8eeb6e776579517d65a426dae0617876ae690e33f4761cf79`. The preregistered plan is archived separately before execution. No thresholds, sample sizes or methods were changed after inspecting these results.

Exact data: `/Users/yingmanji/.codex/artifacts/sle-env-eight-hour-20261003/future-claim-protocol/calibration-results.json`.

| Sensor / latent mean in sigma | Protocol | Exact sign-flip + Holm FWER | Concentration + Holm FWER | Gaussian z + Holm FWER |
|---|---|---:|---:|---:|
| gaussian / 0 | fixed_null | 4.54% (454/10000) | 0.64% (64/10000) | 5.22% (522/10000) |
| gaussian / 0 | exploration_then_fresh | 4.86% (486/10000) | 0.62% (62/10000) | 4.88% (488/10000) |
| gaussian / 0 | confirmation_peeking_invalid | 16.43% (1643/10000) | 2.38% (238/10000) | 18.90% (1890/10000) |
| gaussian / 0 | two_null_one_alternative | 3.73% (373/10000) | 0.50% (50/10000) | 5.00% (500/10000) |
| zero_clipped_gaussian / 0 | fixed_null | 1.77% (177/10000) | 0.00% (0/10000) | unsupported |
| zero_clipped_gaussian / 0 | exploration_then_fresh | 1.83% (183/10000) | 0.01% (1/10000) | unsupported |
| zero_clipped_gaussian / 0 | confirmation_peeking_invalid | 6.38% (638/10000) | 0.00% (0/10000) | unsupported |
| zero_clipped_gaussian / 0 | two_null_one_alternative | 1.45% (145/10000) | 0.00% (0/10000) | unsupported |
| zero_clipped_gaussian / 0.5 | fixed_null | 3.84% (384/10000) | 0.03% (3/10000) | unsupported |
| zero_clipped_gaussian / 0.5 | exploration_then_fresh | 3.70% (370/10000) | 0.00% (0/10000) | unsupported |
| zero_clipped_gaussian / 0.5 | confirmation_peeking_invalid | 13.26% (1326/10000) | 0.03% (3/10000) | unsupported |
| zero_clipped_gaussian / 0.5 | two_null_one_alternative | 2.70% (270/10000) | 0.00% (0/10000) | unsupported |
| zero_clipped_gaussian / 3 | fixed_null | 4.40% (440/10000) | 0.62% (62/10000) | unsupported |
| zero_clipped_gaussian / 3 | exploration_then_fresh | 4.52% (452/10000) | 0.54% (54/10000) | unsupported |
| zero_clipped_gaussian / 3 | confirmation_peeking_invalid | 15.90% (1590/10000) | 2.02% (202/10000) | unsupported |
| zero_clipped_gaussian / 3 | two_null_one_alternative | 3.91% (391/10000) | 0.38% (38/10000) | unsupported |

The invalid confirmation-peeking rows deliberately violate the method assumptions; their low concentration-bound rejection rates are not a restored validity guarantee. For Gaussian fixed nulls, z+Holm yielded 5.22%, with Wilson 95% Monte Carlo interval [4.80%, 5.67%]. This fluctuation was retained; alpha was not retuned. Unadjusted Gaussian three-slot episode rejection was 14.48%, versus 5.22% after Holm. Sign-flip corresponding values were 13.45% and 4.54%.

Fresh exploratory selection of three from twelve retained similar error frequencies, while reusing confirmation for selection inflated Gaussian z+Holm to18.90% and sign-flip+Holm to16.43%. At the clipped boundary, sign-flip+Holm was1.77% for fixed designs,1.83% after fresh selection, and6.38% for invalid peeking. Ties and n=8 make the exact randomization test conservative and coarse; they do not justify a Student-t substitute.

The mixed-null/alternative protocol measures strong-error-control behavior as well as power. For a+1.5sigma latent shift, Gaussian z+Holm power was72.80%, sign-flip44.61%, and the bound45.99%. At the clipped boundary, sign-flip power was41.27% and the bound13.99%; smaller bound rejection rates therefore carry a material power cost. These are fixed reference alternatives, not general power guarantees.

Raw-loss fixed-grid analytic expectations for half-widths0.8/1/1.2 times the90% normal quantile were2.196122/2.062713/2.155925. Monte Carlo means were2.191256/2.059529/2.153807, each within one Monte Carlo standard error of its analytic value. The90% interval has the lowest expected raw loss on this prespecified grid. The central exponential-score audit already demonstrates that exponentiation changes incentives; no new optimization was performed.

Ten new unit tests passed, including exhaustive null sign assignments with zeros, conservative ties, arm reversal/scale invariance, known normal tails, explicit rejection of clipped-Gaussian/Student-t misuse, Holm stepdown/missing slots/dependence, seeded replay and failure accounting. Deliberate mocked failures in the unit tests verify reporting; the16-cell calibration itself had none.

**Implementation remains disabled.** The future candidate default would be known-variance z for declared independent Gaussian sensors and exact sign-flip for identical zero-clipped arm laws; the concentration bound is a separately prespecified conservative option. Never choose the smallest p-value across methods after confirmation. A production version still needs explicit noise-model metadata, immutable contrast/readout/method receipts, new family-level output fields and an independently reviewed participation/aggregate-loss policy. Unknown or correlated/process noise must fail closed. No adapter has been added to scoring or runner, and no old results were rescored.

Reproduce with a Python environment containing NumPy: `python -m unittest env.tests.test_claim_protocol_diagnostics -v`; then `python -m env.claim_protocol_diagnostics --episodes 10000 --seed 20261003 --output NEW_PATH.json`. The CLI refuses an existing output path. The original run used `/Users/yingmanji/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3`.

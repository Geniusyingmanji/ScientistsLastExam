# Frozen development plan: isotope pairing

Synthetic two-position tracer instrument, not a validated metabolic model.
Competing accounts preserve paired atoms or assemble positions from independent
source draws. Both conserve mean labeled atom count; mass-isotopomer readout can
distinguish them when the source positions are correlated. Independent-position
source mixtures remain observationally equivalent. This tests experimental design
of joint labeling, beyond bulk concentration and linear response fitting.

Controls: fresh reset; piecewise source fractions [00,10,01,11], at most four
segments, times 0..12 with at most49 readings. Outputs: product fractions with
zero, one, two labels. Hidden turnover fixed per instance; partial scrambling
may be inferred, but synthetic mechanism labels are not graded.

First unit: implement protocol/kernel and tests only. Exposed development
instances 100,101,202. No model calls. Analytic step solution and independent
solve_ivp check; fraction sum, positivity, mean-label conservation, equivalent
independent source and correlated-source separation, reproducibility and schema.
Stop on failed invariant. These tests do not certify high difficulty or full
biochemical realism. Next unit freezes a bounded noisy inference screen before
fitting; no reference score is claimed in this unit. Keep unregistered.

## Screen frozen before execution — 2026-10-06

Three exposed development instances 100,101,202. Per instance: four noisy
training experiments and six clean validation queries, with panel seeds 710/711
(three each conditions/interventions). Training includes independent labeling,
positively correlated labeling, anticorrelated labeling and correlated pulse/chase.
Fit a known two-parameter family with supplied bounds rate [0.1,2], scrambling
[0,1], two fixed starts, max_nfev80 and a hard cap of 2000 kernel predictions
per instance. Compare uninformed unlabeled-product and nearest-history empirical
baselines. No adaptive widening of budgets or additional starts. Record every
fit prediction, validation prediction and World.run call; cap failures retained.
Do not publish sampled parameters or validation targets. These three instances
are not unseen evaluation cases. Success is scoped feasibility, not model hardness.

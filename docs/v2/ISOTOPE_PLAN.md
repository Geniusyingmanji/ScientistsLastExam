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

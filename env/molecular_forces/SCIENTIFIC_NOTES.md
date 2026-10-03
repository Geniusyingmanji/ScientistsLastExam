# Operator scientific assumptions and evidence scope

This is a synthetic static three-particle effective-potential experiment, not an
atomistic material model, molecular dynamics, or direct thermodynamic experiment.
No stochastic thermal configurations, quantum structure or bulk virial claims
are supported. Temperature-dependent potentials here summarize an effective
interaction at a fixed imposed state; no claim of a bare mechanical potential's
intrinsic temperature dependence is warranted.

Private generation varies between central pair interactions, an added
Axilrod–Teller-form three-particle term and a temperature-scaled pair interaction.
The pair bases use LJ12–6 or Morse. All three strata have identical public
apparatus, costs, channel scales and noise. Labels support balanced operator
sampling only; no label recovery is a success criterion. Samples from this code
are not structural holdout or proven contamination resistance.

At fixed temperature, force is minus the Cartesian energy gradient. Production
uses a complex-step derivative of a smooth nonconjugating analytic energy.
This avoids the old evaluator's finite-difference force plus net-force correction;
no correction is applied to disguise conservation errors. An independent real
Cartesian-dot-product reference and fourth-order finite differences test the
kernel. Analytic pair-well and equilateral pure-threebody solutions provide
stronger checks than implementation consistency. Rotation, translation,
permutation, zero net force and zero net torque are additional consistency
checks, not independent evidence for realism. Independent readout noise means
observed net force and torque need not be exactly zero.

Geometries may be collinear; angular terms are computed through side lengths,
without triangle-height division. Positive minimum separation removes potential
singularities. Legal configurations use at most80 analytic energy evaluations
per request (one real energy and nine complex energy evaluations per row).

A temperature-scaled interaction and its unscaled copy coincide at450K, so one
temperature does not identify state dependence. Generalizing to180/900K can
separate the fixed examples. A one-temperature equilateral scan cannot establish
pair additivity: an arbitrary radial function can absorb an angular contribution
along that geometry. Diverse shapes and joint energy/force data constrain this
account, but do not prove a unique microscopic explanation over all possible
functions. Weak effects and sparse sampling can remain unresolved legitimately.

The weak baseline transfers the nearest observed geometry in centered Cartesian
coordinates. It lacks rotation handling; a large error alone does not establish
scientific difficulty. Strong fixed-design inverse fitting has not been supplied
in this first package. No model results or discovery-depth score are asserted by
these package diagnostics. A fresh-world GPT pilot must separately preserve
prediction-before-measurement evidence and final model versions.

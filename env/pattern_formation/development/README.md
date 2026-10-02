# Bounded development diagnostics

The operator design `calibration/pattern-development/design-plan.json` was frozen before numerical execution. The single batch completed **66/66 trajectory attempts**, including four independent Radau integrations, in **1.39 CPU seconds**. Four fixed development instances each supplied four public source experiments and eight disjoint queries. Four public-domain corner checks stayed finite; this is a finite diagnostic sample, not a proof that every allowed experiment will succeed.

The generated sample contains three anchored-forcing instances and one negative-r0 unforced instance; **it contains no positive-r0 unforced instance**. Separate, predeclared illustrative parameter constructions exercise all three dynamical behaviors, but do not turn this into a balanced generalization sample. No instance was resampled to improve coverage or scores.

| Public source records | Mean NRMSE over 32 queries | Mean prediction-only diagnostic score |
|---:|---:|---:|
| 0 | 0.092220 | 42.95 |
| 2 | 0.084705 | 48.88 |
| 4 | 0.081050 | 50.82 |

The weak baseline is nearest-public-trajectory residual transfer. The diagnostic score is `100*exp(-NRMSE/0.1)`, averaged over queries after excluding assigned time-zero cells; it is not an official SLE composite score. These results establish neither intrinsic difficulty nor GPT capability, discovery depth or scaling.

The independent FFT/Radau reference differed from production BDF by at most **3.18e-9 U**, against readout noise standard deviation 0.002 U. Both solvers check the same finite 64-site model; this is not continuum convergence. Maximum production RHS work among recorded numerical checks was **2351**, below the 12,000 work cap. Source-record calls expose their public cost; their internal work counts are not included in that maximum.

Other predeclared diagnostics found:

- Small-amplitude growth agreed with its linear-mode prediction within 4.56e-10 U. This is an operator numerical check with a sub-noise initial amplitude, not an agent-identifiability test.
- Strictly zero unforced fields stayed exactly zero for both positive and negative growth coefficients.
- A shift of four internal sites agreed with a one-probe translation to 1.37e-13 U without forcing. Anchored forcing produced a 0.1886 U positive-time mismatch after equivalent reset translations, while time-zero agreement remained within 1.74e-16 U.
- Chosen positive, negative and forced parameter illustrations showed growth, decay and persistent forcing responses respectively. Those examples do not uniquely identify general mechanisms from sparse data.

The final focused test run had **42 passed**. The first run had one test-fixture failure: it aliased `observation.axis` and `spec.times`, so an attempted mismatch changed both. The fixture was corrected; the failure log and explanation remain in the central artifacts. No dynamics, parameter distributions or source/query choices changed. Combined initial tests and calibration used **88 trajectory attempts**, including two intentional work-limit failures across the test runs, below the planned 100-attempt budget.

Full raw records, private parameters and targets remain outside Git in the operator directory `calibration/pattern-development/`. Its diagnostic raw SHA-256 is `4214a54e8a4d7fbce36165d65bf10e5fe797481bf13f82e1abd4577cd7e69ecf`. The development plan SHA-256 is `8c6139013342ac7b20772a610ff56a0b967caa13d88054ce2c49e77b6cb1ed62`. No API requests were used and no historical evaluation was changed.

The later independent review is separately retained under `calibration/pattern-independent-review/`, including its frozen plan, all attempts and failures. It used 42 attempts and 1.778 numerical CPU seconds: 36 completed, three expected cap failures and three unexpected failures. One production failure is an internally allowed positive-r0-plus-forcing combination outside generated-stratum support; two reviewer reference calls reached their own RHS cap. Three follow-up, predeclared generated-stratum endpoint checks completed. This does not replace the original four instances or expand representative coverage. The review concluded before the tenth-world integration and remains same-family/provisional. The shared integration is a subsequent implementation phase, with its own targeted regression evidence under `calibration/pattern-registration/`.

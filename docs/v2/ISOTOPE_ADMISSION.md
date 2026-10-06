# Isotope admission audit

Status: unregistered prototype, not runnable through the shared registry.

| Integration | Current evidence | Remaining gate |
|---|---|---|
| World/schema | Public validator shared with eligibility; local contract tests | Preserve candidate description fingerprint |
| Prediction | t=0 mask exists separately | Wire to explicit versioned score contract; do not alter frozen v1 |
| Claims | Pre-readout history check | Full submission schema, deduplication, uncertainty and task semantics |
| Observation evidence | Strict local adapter, detached output | Shared archive allowlist, trusted provenance and raw-data boundary |
| Prospective noise | Independent additive Gaussian, no clipping; mean bias zero | Explicit shared policy entry and integration tests |
| Calibration | 3 exposed development instances | Initial-state semantics, wider instance calibration and structural split |
| Presentation/isolation | No registration yet | Explicit task profiles, sandbox and source-exclusion smoke test |

New local noise helper computes uncertainty of a predeclared scalar treatment-
control mean, with independent observations and equal replication per arm. At32
replicates per arm, standard error0.0005 and a single 95% interval half-width
about0.000980. Multiple predeclared readouts use Bonferroni. This is observation
uncertainty only, not model parameter uncertainty or mechanism identification.
No Monte Carlo or new scientific experiment is performed in this unit. Two
analytic/validation tests supplement the previous12 isotope tests.

Next unit should wire one versioned integration path and test it end-to-end
without model calls, rather than treating separate helpers as completed admission.

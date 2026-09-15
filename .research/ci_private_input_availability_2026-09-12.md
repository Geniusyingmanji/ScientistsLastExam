# Distinguishing missing private inputs from corrupt evidence

The first complete integration CI, [run 34675975274](https://github.com/Geniusyingmanji/ScientistsLastExam/actions/runs/34675975274),
tested head `dcd68f007099b69f07624a07b3f9b9f6d72d9b42`, tree
`e4625aadb0991ca6945d1964e38c91767869ae93`. It reported 1,630 passed,
45 skipped and six setup errors; all 58 required checks passed. The run remained
failed. Its artifact digest, checkout tree and JUnit/coverage correspondence were
independently verified and archived; no failed observation was replaced.

All six errors came from the prospective meta-analysis historical test fixture.
Public checkouts do not include its private run directories. The new verifier
wrapped the missing manifest in `ValueError`, whereas the fixture's explicit
missing-data guard expected `FileNotFoundError`.

Repair `87c1a323b8464a0f2629528dc5b5f033cfdee1c8` changes only the specialized
analysis script and its tests. The script now raises `FileNotFoundError` when the
entire resolved private run directory is absent. A present directory with a
missing or malformed manifest still reaches the unchanged verifier and fails.
Legacy runtime identity, missing durable receipts and tampered receipts also
remain invalid. There is no general `ValueError` catch, automatic legacy migration
or receipt-verification exemption. No evaluator, task, budget or runtime source
changed in this repair.

Five report/verifier test files executed on the isolated Linux Python 3.10.20 CI
dependency profile: **57 passed, 68 subtests passed, zero failed/errors, six skipped**,
15.72 seconds of pytest time. All six new independent synthetic checks executed
and passed. The six unavailable checks are exactly the historical calibration
class; their private scientific evidence was not verified by this run. Both pytest
and required-check coverage returned zero. JUnit SHA256:
`6e6382b6a76fb43af27da8c3bedd4132347899c86f5ac0ad71b1d4b8bd95f137`.

The final integration manifest requires these six checks alongside the existing
58 and the three cache-policy sandbox checks: **67 required checks**. The final
87-task complete CI must pass on the submitted tree before merging. Directed
verification above does not substitute for that gate and adds no model or task
science measurements.

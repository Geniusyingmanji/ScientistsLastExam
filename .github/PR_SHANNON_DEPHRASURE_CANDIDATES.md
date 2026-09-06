# Candidate resources: fixed C7 construction and finite-block dephrasure state design

Register two existing optimization cores as candidate resources, visible through
`sle list --all` and excluded from the default certified inventory. Both use CPU
evaluation, uncapped progress scores, explicit public contracts and the standard
trusted CLI wrapper; candidate code has no in-process import fallback.
Metadata evaluation times are conservative CPU estimates, not measured sandbox latencies.

- `Mathematics/ShannonCapacityConstruction` exactly checks independent sets in the
  fixed fifth strong power of C7. The 243-word product baseline scores zero; the
  exact 367-word Polak-Schrijver 2018 historical fixture scores one. Independent
  neighbor enumeration checks the complete literal witness. Public replay is
  cheap, and this is not a current global record or full Shannon-capacity claim.
- `QuantumFoundations/DephrasureCodeDesign` scores n=3/4 input factors by coherent
  information against a recomputed pointwise public witness envelope with product
  closure. Independent tensor Kraus checks and physical channel identities support
  the oracle. Eight upstream MAT witnesses are MIT-licensed and hash-pinned;
  the known printed NN discrepancy is retained. The 1e-9 bits/use excess margin
  is numerical, and the witness library is not an exhaustive global-record claim.

The cards disclose unknown inherited builder-model IDs, external review pending,
and long-horizon status `not_tested`. Exploratory testing has occurred and fresh
model-produced objects are being checked separately. `calibration_runs` is empty
because there are no formal SLE calibration runs. Full-program calibration and
trusted candidate execution are blocked on H200 sandbox mount permissions; core
unit tests on that machine are not evidence of a candidate sandbox run.

Focused packaging verification:

```sh
python -m pytest -q tests/test_expansion_registration.py tests/test_task_cards.py tests/test_exam_taxonomy.py tests/test_task_inventory_document.py
python scripts/check_task_contribution.py --task Mathematics/ShannonCapacityConstruction --skip-eval
python scripts/check_task_contribution.py --task QuantumFoundations/DephrasureCodeDesign --skip-eval
python scripts/report_task_inventory.py --check
```

Registration tests must fail while the task IDs are absent, then pass after
packaging. Wrapper tests substitute the subprocess result and verify delegation
and fail-closed behavior; they do not simulate a successful Linux sandbox run.
`--skip-eval` excludes baseline, determinism and malformed-worker execution.
Independent science tests and immutable reference provenance remain in each core.
Before admission, maintainers must complete trusted Linux execution, formal model
calibration, external review and full integration checks. This packaging change
does not refresh global evidence, alter the challenge outside inventory, publish
a PR, upload artifacts or change sandbox/SSH policy.

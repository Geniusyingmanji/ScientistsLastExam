# PR #13 maintainer review response — 2026-09-06

The task-only contribution has been reconstructed on upstream `2cbf72b` (76 tasks).
The resulting inventory contains 86 tasks: the complete upstream set plus the
original ten biology candidates. All task authors/committers use
`outliers1106 <tuyanlun9716@163.com>` for this contribution.

## Collision findings and current scope

The [maintainer review](https://github.com/Geniusyingmanji/ScientistsLastExam/pull/13#issuecomment-5554433169)
identified a shared `MetabolicEngineering/MetabolicStrainDesign` ID and a near-duplicate
marker-panel mixture task in #9. The subsequent [PR #9 split-index update](https://github.com/Geniusyingmanji/ScientistsLastExam/pull/9)
explicitly defers its metabolic-design task from all split submissions to leave
that ID available to #13, and records removal of `MetagenomicMixtureID` in `3106a1e`.

The actual [Chemistry/Biology split #22](https://github.com/Geniusyingmanji/ScientistsLastExam/pull/22)
was checked: its five packages are `HodgkinHuxleyCurrentID`, `OrthogonalDNACodewords`,
`ChronoamperometryLawID`, `MassFragmentationTree`, and `ThermochemicalCycleAudit`.
Neither conflicting task is present. Therefore #13 retains both original IDs;
no second package with either scientific scope is being introduced by this revision.
This records the other author's published action, not a claim of private agreement.
The two task cards and contracts now explain the overlap and coordination outcome.

## Repository integration

- Preserve upstream registrations, taxonomy cells, logical domains, and Chinese inventory entries;
  resolve additive certification conflicts by taking their union and regenerate `TASKS.md`.
- Update README counts to 86 packages: 46 optimization, 40 discovery; 5 certified and 81 candidate.
- Extract the unrelated seccomp architecture change into branch `fix/seccomp-architecture`
  and a separate PR. Neither `sle/secure_eval.py` nor its test file differs from upstream in #13.
- Keep the shared `sle/frontier_eval_entrypoint.py`. The maintainer accepted this direction;
  repository-wide metric visibility is tracked separately in #14.
- Preserve upstream global audit reports and pointers without contributing local generated snapshots.
  Adopt upstream's `SLE_REQUIRE_FROZEN_INVENTORY` CI behavior: frozen-evidence completeness blocks
  main, not task PRs. No audit requirements or tests are weakened by this contribution.

## Validation

The extracted seccomp change passed all 27 `tests/test_secure_eval.py` tests in the
Linux x86_64 candidate sandbox. Native AArch64/i386 runs remain outside this host's
coverage. The rebased task validation results are recorded after the final run.

Historical validation reports remain historical: rebasing changes source revisions,
and local audit snapshots are not evidence for the reconciled branch. Expert review,
frontier calibration and difficulty risks remain unchanged; all new tasks stay candidate.

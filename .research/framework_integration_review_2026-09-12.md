# PR #17 integration review, 2026-09-12

Reviewed base: `58e4b8e560253bdafc8bb3d6c9baa268712eafb3`.
Freeze-ready source: `cdfdec526efce03cf7622a8b7e2e4234b97ebfad`.
Integration branch: `codex/sle-pr-merge-20260912`.

**Conclusion:** The identified implementation blockers have safe fixes and targeted Linux validation. Integrate only after a new global freeze and full CI on the integrated tree. This supports completed-budget greedy runs and an opt-in family interface; it does not establish scientific lifetime-credit validity or general time-horizon completion verification. There are currently zero real `wave.yaml` task packages, so this integration grants no task frontier eligibility or release certification.

## Functional change and review implications

| Area | Resulting contract | Risk / review boundary |
|---|---|---|
| Trusted interpreter and ABI | Evaluator uses the configured Python entrypoint, preserving a venv, or the invoking interpreter when unset. It probes a path-free Python/distribution descriptor; trusted driver repeats this check and wraps metrics in a bound envelope. | This changes main's default `/usr/bin/python3` selection. Explicitly set the trusted interpreter for campaigns. Python 3.14 and unpinned environments fail closed. Version/ABI identity is not a wheel/binary identity claim. |
| Candidate mounts | Replaces broad host runtime mounts with exact CPython runtime, standard library, selected packages and resolved required shared libraries. Actual mounted package metadata, aliases and RECORD associations are checked. Host/base package stores remain masked. | Relocatable CPython runtime libraries are individually relocated to `/runtime/lib`; no runtime parent directory is mounted. New library and mask logic changes runtime-source identity and requires new evidence. |
| Canonical package setup | Python3.8 full profile has one pinned install transaction. Isolated bootstrap pip25.0.1 fixes a reproduced clean-host RDKit wheel-resolution failure with pip20.0.2. | No host packages changed. CI now installs the declared nmrsim0.6.0/packaging26.2/PyYAML6.0.2 and full candidate dependency chain, replacing main CI's different versions. Old measurements on nmrsim0.6.0.post1 are not silently relabeled. |
| NMR / Numba | Serial `nmrsim.qm` and Numba JIT are available with `NUMBA_NUM_THREADS=1`, `NUMBA_THREADING_LAYER=workqueue`. Optional `tbbpool` binary is explicitly masked and excluded from ELF scanning. | The absent optional libtbb cannot block unrelated serial imports. No generic missing-library exemption was added. Exposed ELF failures still reject. TBB parallel execution is outside this single-thread sandbox. |
| Receipt verifier | New `verify-run` checks completed greedy trajectories against durable requests/receipts, source/candidate/prompt/metrics/runtime identity, counters, feedback selection, incumbent and summary. External expected budget/runtime can be required. | Other algorithms lack equivalent receipt verification. A manifest's local hash consistency is not an independent operator signature. |
| Clock and resumed budget | Baseline time equals its receipt; proposal prefix/publication/completion totals must match receipts, within machine-rounding tolerance only. Historic receipt allocations may increase across completed resumptions while retaining original hashes. | Failed physical attempts and resume downtime are excluded from the logical active clock. An extended run is not equivalent to a fresh run allocated the larger budget from step one. Active-wall completion before exhausting proposal budget is currently rejected as an uncompleted budget contract. |
| Feedback | Shuffled feedback is selected by a deterministic seed/step hash, avoiding resume-dependent RNG state. Public selection metrics retain the main allowlist. | This changes shuffled-control behavior. Prior shuffled runs remain bound to their original runtime and must not be merged as equivalent samples. |
| Family entrypoints | Optional metadata/wave manifest, family audit, `frontier-promote`, and append-only cross-run ledger. Promotion first verifies a completed greedy receipt and current task/package/runtime/wave, then checks exact receipt metrics hash. Direct public `record()` rejects unverified callers. | Family code is an experimental interface with no real opted-in tasks in this tree. Adding family tasks remains a separate scientific admission decision. |
| Credit | Optimization awards positive incumbent improvements meeting frozen minimum_delta. Discovery deduplicates canonical claims within family+namespace and awards fixed weights. Wave chain, immutable cells and literal renamed clones are validated. | Credit is monotone, uncapped and omits FDR/refusal penalties. It is not overall model or discovery quality. Semantic clones with different encodings and scientifically unjustified claims require task/wave review. Promotion order, weights, namespaces and canonical shared ledger must be frozen for a campaign. |
| Duplicate events / recovery | Identical evaluation request reuses its committed event; conflicting metrics/request identity reject. Event hashes chain, fsync, lock and deterministic replay protect normal crash/retry paths. | A repeated CLI call returns its original decision with `receipt_reused`; consumers must use ledger totals, not sum returned historical deltas. Trusted operator rewriting all local artifacts and anchors is outside the threat model. |
| Private receipts / public sidecars | Promoted events embed full evaluator metrics, so ledger must be outside Git, directories0700/events0600. Existing nonprivate root rejects. Ordinary upstream sidecars remain source-bound and filtered; a conflicting full-metric observation now makes a sticky private infrastructure fault. | Ledger head/approved aggregates may be published; raw frontier events must not be published. Fixed pre-evaluation runtime mismatch remains a configuration error, while arbitrary RuntimeError no longer bypasses sticky sidecar failure handling. |
| Reports and historical runs | New-format reports call the actual verifier, bind manifest/runtime/budget, reject corrupt modern runs and preserve exact per-run discovery join state (joined/unusable/missing). Historical files remain unchanged, readable as `legacy_format` and `trusted_evidence=false`. | Historic descriptive rows and values remain diagnostic; they do not acquire modern receipt validity, campaign eligibility or family promotion. Manifest schema remains1 despite the new required capabilities; compatibility is enforced by required bindings rather than automatic migration. |
| Batch/cohort | Runtime/task conditions freeze before workers and model construction; cohort completion checks verified receipts and expected budget. Recovered/failed attempts and fixed planned denominator remain visible. | Cohort evidence is restricted to greedy. There are no new model calls or formal scientific calibration results in this review. |

## New implementation fixes in this review

- `97a3cd996…`: restored reporting bindings lost during the author's merge of main; repaired prospective/PV runtime evidence gates; upgraded only the isolated setup bootstrap.
- `ab4d252e2…`: exact relocatable runtime-library resolution/mounts, with escape and unrelated-library rejection tests.
- `8b4a701e1…`: private external frontier ledgers, atomic0600 event files, permissive-umask and repository-destination regressions.
- `ef3b0b408…`: disabled optional TBB backend in the fixed serial profile; narrow runtime-binding exception type so conflicting sidecars remain sticky infrastructure failures.
- `cdfdec526…`: canonical CI dependency closure and the real NMR/serial-JIT profile regression.

## Executed evidence and its exact scope

- At `97a3cd996…`, canonical Python3.8 full-pin isolated environment: 300 passed, 0 failed, 0 skipped, 221.10 seconds across18 targeted files. An independent secure_eval run passed39/39. Real Radial/Astropy and canonical setup checks ran; this was not a full task-science sweep.
- Before shared-library fix, Python3.10.20 and3.12.13 profiles each yielded98 passed/21 failed/0 skipped. All21 shared the relocatable interpreter's unresolved Tcl libraries; raw failures retained.
- At `ab4d252e2…`, Python3.8/3.10/3.12 each passed132 checks/0 failed/0 skipped, including sandbox, metadata, receipt/clock/family and failure-sidecar checks. Times99.70/84.48/91.31 seconds. Py3.10/3.12 also reported86 subtests each. These are profiles on the existing Linux host, not stock Ubuntu22/24 host-policy certification.
- At `8b4a701e1…`, final ledger/report/batch/cohort focused group passed122/0/0 in65.97 seconds.
- At `cdfdec526…`, NMR/serial-JIT, exposed/hidden ELF boundary, sticky sidecar and protocol group passed70/0/0 in67.47 seconds. Real candidate `nmrsim.qm` import and `njit(lambda x: x+1)(2)` passed; TBB import was unavailable and workqueue/1 observed.
- Fixed data-free probes before the NMR repair passed base NumPy/SciPy, qutip arithmetic and Astropy/erfa imports. NMR initially failed due optional libtbb and was repaired above. Pymatching was correctly rejected before CandidateProxy because it is deliberately a trusted-only reference anchor, not an allowed candidate toolkit. This is not a successful candidate pymatching import.
- Initial NMR regression collection used an incorrect decorator invocation and failed before tests; corrected source and successful rerun are retained separately, not overwritten.

All logs, JUnit and raw runtime checks remain in private operator storage outside Git.
No historical evidence was overwritten, no scientific threshold changed, and this framework
validation made no model calls. Required CI execution now includes the 38 existing admission /
world-isolation checks and 20 additional runtime, receipt, ledger and sidecar regressions.

## Integration gates

Global baseline, wrapper, recovery and preflight measurements are generated separately from
clean revisions and retain the exact measured source. `experiments/framework_merge_validation_2026-09-12_v1.json` records
final counts and hashes. Whole-suite GitHub CI must pass on the submitted merge tree; directed
checks above do not replace that gate.

Completed integration measurements: certification v87, baseline v71, maturity v29;
86/86 baselines valid and deterministic over172 evaluations, infrastructure failures0;
86/86 wrapper results match the independently collected baselines; seven fixed artifacts
have identical complete metrics before/after across28 evaluations; recovery v12 passes
8/8 scenarios; preflight v4 passes70 checks with0 failures/0 missing across21 evaluations.
Inventory stays86 (42 optimization /44 discovery),5 certified /81 candidate; external,
release and long-horizon readiness remain0. New raw baseline and preflight reports remain
private; public files use the existing schema2 projections.

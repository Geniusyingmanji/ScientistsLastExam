# NeuralReportAttribution: PR 73 revision validation

Tested clean source: `981802039e555698c463591553f54d8e03c2b261`.
The later documentation/evidence changes retain the tested task Python files; their
SHA-256 hashes are recorded in `../neural_report_revision_2026-09-10.json`.
This is builder/engineering evidence, not an independent model calibration.

- Linux full suite: **1209 passed, 50 skipped, 0 failed, 508 subtests passed**
  in 2075.60 s (34m 35s), with 117 deprecation warnings (`full-suite.txt`).
- Linux focused tests: **93 passed, 0 skipped, 22 subtests passed** in 20.64 s,
  including actual Bubblewrap world isolation (`focused.txt`).
- Linux contribution gate: all 15 checks passed (`contribution.json`).
- Linux expanded audit: passed with `trusted_evidence: true`; baseline/reference
  repeated through Bubblewrap with every metric equal. Reference took 87.0 / 88.2 s.
- Every ablation and shortcut candidate was valid. The 3024-strategy grid selected on
  development matched its sandbox score and confirmed on heldout once.
- Heldout-only invalid responses: development validity/feasibility remain 1 while
  trusted heldout validity is 0; no invalid-world refusal credit is awarded.
- Wrapper output contains exactly combined_score, valid, feasibility_rate and raw_score.
- Local focused tests after final documentation edits: 58 passed, 1 Linux-only skip,
  5 subtests passed. The Linux focused result is recorded in `focused.txt`.

Environment: Linux x86_64, Python 3.12.3, NumPy 1.26.4, SciPy 1.13.1, one OpenBLAS
and OMP thread. The trusted harness needed sudo to establish namespaces; candidate
workers still ran as UID/GID 65534 in isolated Bubblewrap namespaces. The clean
per-run environment explicitly trusted only this checkout via Git safe.directory;
no global security configuration was changed. An initial suite run with missing
Git ownership context was interrupted and replaced by the recorded clean run.

Reproduce on a configured Linux sandbox host from the tested checkout:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python3 scripts/audit_neural_report.py --output /tmp/neural-revision.json
python3 scripts/check_task_contribution.py --task Neuroscience/NeuralReportAttribution --output /tmp/contribution.json
SLE_REQUIRE_FROZEN_INVENTORY=0 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python3 -m pytest tests/ -q -p no:cacheprovider
```

Full-repository integration additionally runs in PR CI; consult the PR checks for
its final status. The commands above include that full-suite invocation.

Full numerical tables and historical reviewer attribution are in
`benchmarks/Biology/NeuralReportAttribution/references/known_best.md`.
Historical variable-noise evidence is labeled separately. Current and redacted
historical reports omit per-instance answer records; old Git history remains public.

## Review changes

The revision fixes three information leaks: public validity now depends only on
development, all public problem dictionaries use the same response noise SD 0.012,
and the external wrapper writes only the closed search-visible metric allowlist.

Review decisions:

1. Heldout validity remains a trusted diagnostic. Tests inject heldout-only invalid
   responses and require unchanged public feedback; the Linux audit also exercises
   this through the sandbox using an explicitly adversarial temporary fixture.
2. The public dictionary is identical across every frozen world and additional seeds.
   The constant 0.012 is the midpoint of the original public-noise range, chosen
   before the revised heldout evaluation. Paid deterministic observations still need
   server-held replacement for contamination resistance.
3. The audit adds a 3024-strategy calibrated algebraic grid and a fixed 3-unit
   null-or-refusal candidate. Development selects the calibrated strategy, with one
   sandbox confirmation on heldout. The stronger scores are reported without tuning
   the task or reference to suppress them. Historical reviewer results remain attributed.
4. The 14-unit cap remains a resource limit; budget allocation is no longer presented
   as demonstrated difficulty. New runnable 6-unit, never-abstain and no-model-selection
   ablations complement the 10-unit and no-instrument-model variants.
5. No independent model draw is claimed. Lineage and construction status are both
   incomplete_legacy, with the recorded-lineage whitelist entry removed.
6. Wrapper file output is filtered. Published old/new evidence excludes per-world
   answer records; historical artifacts are labeled, and Git history is not erased.

Additional review items: nearest-neighbour rationale and reused scoring design are
explicit; score precision is qualified by NumPy/SciPy versions; expected runtime is
120 seconds under a 300-second timeout; task evaluation budget is recorded; particle
physics template leftovers are removed; decision versus continuous-parameter headroom
is explained; domain review is pending_external_neuroscience. Current origin/main
registrations were merged as a union and TASKS.md was regenerated; README counts
include the new task.

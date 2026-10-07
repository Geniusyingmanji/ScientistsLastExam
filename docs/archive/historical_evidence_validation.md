# Historical records and current compatibility

Historical records do not acquire compatibility with a new evaluator simply
because their raw files are still intact. Validate these claims separately.

## Original file integrity

```bash
python scripts/audit_historical_records.py --task all > /tmp/historical-integrity.json
```

This read-only command pins the committed AlloyHardness, Calorimeter-v2,
RANS-v2, DemographicSFS, DiffractionGrating, ElectrolyteConductivity,
ForceFieldHypothesis, ProteinStability, PhotovoltaicTandem, and ProspectiveMetaAnalysis
analysis documents at revision
`f9c05b65b100e0b7d6acabbf16e64602fb73eea9`. Each document's existing digests bind
its calibration and batch reports, raw trajectories, run manifests, and retained
best/terminal sources. The command also reconstructs the original scalar
trajectory projection and checks it exactly against the batch report. Archive
and batch hashes are checked before following their references.

Exit codes are `0` for all bound files intact, `1` for a failed check, and `2`
for missing files. The denominator remains three runs per task. Recorded paths
are relocated through `resolve_run_workdir`; a worktree may read the original
run tree through a `runs` symlink. The audit never writes into that tree.

`status: passed` means only that the originally bound files and projection were
verified. `trusted_evidence` remains false and current runtime compatibility is
`not_assessed`. This is content integrity anchored to reviewed source control,
not an independent reproduction of the original experiment. Missing intermediate
candidate sources cannot be recreated. Checkpoint/summary files without an
original digest are explicitly listed as `unbound_files`; their presence is not
claimed as verified evidence.

## Current compatibility and replay

The first nine analysis entry points continue to enforce their source migration
checks. With the present source tree, they reject current compatibility: the task/runtime changes exceed the old
audited scope, and current file hashes differ. Intact old migration reports or
a successful direct oracle replay do not override that refusal. New current
evidence requires a separately reviewed migration or new experiments with their
own provenance; do not overwrite old reports or replace their digests.

PhotovoltaicTandem previously used glob pathspec magic with `git ls-tree`, which
that command rejects, and compared only the calibration and model revisions.
It now checks the whole runtime package (a conservative superset of the former
Python-only scope), retains that historical comparison, and independently gates
the model-to-current comparison. Its public tests use pinned archived records as
fixtures; the raw files must still pass the separate audit on a data host.
ProspectiveMetaAnalysis separately validates its historical task contract at the
recorded revision. Its archived files are included in the same integrity audit;
that audit makes no claim about compatibility with the current runtime.

The raw-data integration tests now assert both original integrity and current
refusal. They do not skip on a migration failure. Existing missing-raw-data skips
remain for checkouts that do not contain the ignored run directories. Run the
fixture tests in any checkout; validate retained artifact replays with the original
scientific dependencies because the historical comparisons are exact.

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
python -m pytest tests/test_historical_records.py \
  tests/test_alloy_hardness_analysis.py tests/test_calorimeter_analysis.py \
  tests/test_rans_analysis.py tests/test_demographic_sfs_analysis.py \
  tests/test_diffraction_grating_analysis.py tests/test_electrolyte_conductivity_analysis.py \
  tests/test_force_field_hypothesis_analysis.py tests/test_protein_stability_analysis.py \
  tests/test_photovoltaic_analysis.py \
  tests/test_prospective_meta_analysis_analysis.py \
  -q -p no:cacheprovider
```

The fixtures mutate each type of originally bound file, rewrite a batch
projection after changing its raw trajectory, remove required digests, and
remove raw data. These cases must fail or report missing; none may be counted as
passed. No model calls or newly frozen scientific evidence are involved.

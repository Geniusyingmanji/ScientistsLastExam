# Neuroscience/NeuralReportAttribution: historical initial validation

This record predates the PR 73 review fixes and uses variable per-world noise.
It does not validate the revised evaluator. Published JSON has had `per_instance`
answer records removed; aggregate metrics and original provenance are retained.
`wrapper.json` records the old unfiltered output and is not the revised search interface.

Clean tested source: `21b518f546354d2e8a8c65b4f13165d91b965b51`. Later commits add only experiment evidence.
The branch contains one new task and has no runtime/test dependency on another
new task package. This is builder and engineering evidence, not model calibration.

- Linux focused tests: **84 passed, 86 warnings, 17 subtests passed in 21.07s**.
- Local focused tests: 49 passed, 1 Linux-only skip; the skipped isolation test passed on Linux.
- Contribution gate: passed, including secure baseline repeats, discovery axes,
  blanket refusal and malformed candidates (`contribution.json`).
- Black-box wrapper: valid legal baseline, score 0 (`wrapper.json`).
- Reference and baseline each evaluated twice through the sandbox; all metric keys
  match. All ablations are valid. Full precision and finite-grid probes are in
  `../neural_report_2026-09-10.json`.
- No full-repository run is claimed for this branch; GitHub PR CI supplies that check.

Linux used Python 3.12.3, NumPy 1.26.4, SciPy 1.13.1 and one OpenBLAS thread.
This host requires sudo for the trusted harness to establish namespaces; candidate
workers still run as UID/GID 65534 with unshared namespaces, seccomp, read-only
mounts and per-world private tmpfs. No host-wide security setting was changed.
`validation.json` records source provenance, commands and exit statuses.

Reproduce on a configured Linux sandbox host from the repository root:

```sh
OPENBLAS_NUM_THREADS=1 python3 scripts/audit_neural_report.py --output /tmp/neural_report.json
python3 scripts/check_task_contribution.py --task Neuroscience/NeuralReportAttribution
OPENBLAS_NUM_THREADS=1 python3 -m pytest -q tests/test_neural_report.py tests/test_secure_eval.py tests/test_task_cards.py tests/test_benchmark_layout.py tests/test_task_inventory_document.py tests/test_exam_taxonomy.py
```

Task status remains candidate. Independent model calibration, domain review and
server-held reissue are outstanding. Neither clean-source execution nor passing
security tests establishes frontier difficulty or contamination resistance.

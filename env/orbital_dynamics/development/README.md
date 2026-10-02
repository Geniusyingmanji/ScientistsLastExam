# Development calibration summary, v1

The v1 diagnostic was generated locally with zero model API calls. Reproduction
must write to a new private path outside the Git directory, for example:

```sh
python -m env.orbital_dynamics.calibrate --output /new/private/path/orbital-development-v1.json
```

These are reserved development seeds 7, 46, 1439 and 8743. Each has 12 noisy
public training records, 6 condition queries, 6 intervention queries and one
independent polar-coordinate numerical reference. All targets and operator
stratum annotations in the raw diagnostic are private. Nothing is a formal
evaluation score or a candidate-facing artifact.

The retained central private artifact is
`/Users/yingmanji/.codex/artifacts/sle-env-eight-hour-20261003/calibration/orbital-development-v1.json`.
The former `development/diagnostics-v1.json` copy was removed from this Git
directory only after verifying byte-identical SHA-256 hashes:
`b8c5b212502266712a48bbcdac9bd540fecc9671d8cce5afe5e2467f4f70d992`.
This page contains summaries; the raw diagnostic is not distributed here.

| Public training records | Mean normalized RMSE | Mean diagnostic exponential score |
|---|---:|---:|
| 0 | 1.07627 | 0.02457 |
| 4 | 0.61583 | 0.86036 |
| 12 | 0.57235 | 3.49138 |

The diagnostic removes time-zero rows, uses the four fixed public channel scales
and reports `100*exp(-NRMSE/0.1)`. It does not add claim verification or produce an
official combined score. The weak baseline has no private family, parameter,
seed or query target. These numbers do not calibrate scientific difficulty.

Across the four independent reference comparisons, the largest absolute state
difference was `9.44e-13`; the largest energy/work residual was `4.27e-13`. Among
48 development queries the largest production effort was 4,772 RHS evaluations
against the per-experiment cap of 60,000. The full local diagnostic took about
0.73 s; timing depends on the host and is not a throughput guarantee. Separate
extreme-parameter radial-crossing tests reached 5,501 RHS evaluations.

The matched-law construction gives the same entire circular trajectory for
p=1.5, 2 and 2.5 after matching their attraction at one radius: maximum normalized
difference below `6e-15`. New-radius and impulse probes then give differences
above 0.96 for those specific alternatives. A short (0.03 T) drag contrast is
less than one paired measurement-noise SD; the longer trajectory separates it.
This is a finite-scope demonstration of informative versus uninformative
experiments, not unique mechanism identification.

The reserved seeds sample two alternative-power and two dissipative instances.
They do not include a conservative p=2 instance; its physics is checked through
explicit-parameter independent-reference and analytic tests. No seed mapping was
changed to balance this small development sample.

At the original prototype delivery, `python -m pytest -q
env/orbital_dynamics/tests` passed 59 tests. Python 3.8 syntax was checked by AST;
the local runtime was newer Python. That calibration predates shared registry
integration and used no model API or formal cohort. The current registered
ninth-world experimental status does not change the v1 data or make these
numbers official scores.

The separate pre-integration review recorded 106 trajectory attempts (105
completed and one intentional work-budget failure), including nine independent
RK4 trajectories. Its maximum independent trajectory difference was `2.874e-8`.
Matched circles differed by at most `5.707e-14`; identical impulses left
event-time differences below `1.374e-15` and produced later position differences
of 0.920 and 1.348 L for the specified alternatives. This supports dynamic
separation in those probes while preserving exact-circle nonidentifiability.
The review also records the near-p=1 potential-difference cancellation described
in [SCIENTIFIC_NOTES.md](../SCIENTIFIC_NOTES.md).

Review summaries and raw evidence are retained privately under
`/Users/yingmanji/.codex/artifacts/sle-env-eight-hour-20261003/calibration/orbital-independent-review/`
(`REVIEW.txt`, `findings.json`, `CLAIMS_FROM_RESULTS.json` and their evidence).
The review is same-family/provisional: A=yes, B=yes, C=partial at the time of
review. The integration installs the documented pilot claim rule of 0.25 T after
reset and each impulse at/before the readout, with matched comparison times;
meeting that rule does not itself establish discovery. Integrity remains
unavailable, the canonical evidence helper unresolved, and the precheck supports
existence/hash checking only. The review preserves 93 passing checks and one
harness false positive from matching the substring `mu` in `maximum_norm`,
resolved separately by whole-token and manual public-output checks.

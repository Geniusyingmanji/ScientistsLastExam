# Reference and admission record: DistributionNetworkTopology

Maintainer-facing. Only Task.md, solution.py and constraints.txt are delivered to
candidates. `review_evidence.json` binds the replay commands, source hashes, clean
Linux revision, full grid and capability metrics. Sandbox execution is separately
checked by `check_task_contribution.py` and the integration test.

## 1. Reference method and remaining capability

The standalone witness enumerates every set up to the public break-size bound,
uses the public flip probability, a uniform-cardinality prior, a fair-coin telemetry
alternative and posterior experimental design. It includes all hypotheses tied at
the 96th posterior rank; a rounded utility tie-break avoids NumPy-sort-dependent
probe sequences. Repeated measurements can resolve noisy observations. Signature
groups identify structurally inseparable hypotheses; the model evidence detects
telemetry failures outside the sparse-break family.

The reference makes a one-step experimental-design choice. It does not optimize
a multistep decision policy or integrate every low-posterior hypothesis into each
choice. Those are the remaining experimental-design capabilities; there is no
incorrect hardcoded noise rate or dormant three-pipe extension. It consumes all
remaining budget and leaves errors in supported inference and heldout recovery.

## 2. Baseline and normalization

The shipped one-route, first-pipe guess scores zero. Three corridor observations
are paid before candidate entry, leaving 23 of 26 units. The larger development
cohort has 24 equally cardinality-stratified supported worlds plus six aliases and
six telemetry-fault worlds; heldout has 18+6+6 with independent seeds.
Supported quality is squared set Jaccard; unsupported refusal earns one. The raw
mean is normalized above full abstention and clipped to [0,1]. F1 remains diagnostic.
Partial invalidity affects only the offending row and feasibility fraction.

## 3. Capability ablations

All switches are exposed in the standalone reference for the audit script.
The source-bound table is generated in `review_evidence.json`; final measured
values are listed below after Linux replay. Each of the five advertised components
must reduce development score when removed: the three-pipe family, adaptive route
choice, structural-group refusal, telemetry-model check and cardinality prior.
The regression test checks the degradation, not a hardcoded score.

## 4. Shortcut probes and old failures

The maintainer's [898e28e review](https://github.com/Geniusyingmanji/ScientistsLastExam/pull/51#issuecomment-5583243149)
reported a 420-point failure-ratio grid at **0.960**, above the old reference's
**0.600**. Five supported worlds and coarse F1 created a development-score lottery;
ignoring the corridor gave free alias refusal. Those observations motivated the
cohort, metric, paid-corridor and complete-reference changes. The old claim that
all shortcut risk was intended probe-selection difficulty was wrong.

`verification/review_audit.py` now evaluates **1,680** points: n=6..26 and
threshold=0.05..1.00, both floor/nearest equidistant indexing, and either using or
ignoring the paid initial reports. Requested counts are capped at the remaining
23 calls; the initial corridor cost is always charged. The strongest source is
shipped as `verification/shortcut_grid.py`. Its declared score is checked twice
through the same sandbox as the reference, with a 10% relative margin.

## 5. Frontier-model calibration

A frozen, selection-blind gpt-5.6-sol (high reasoning) first-proposal campaign was
run on clean Linux source `4ba261bb864388dc4c55787f07870def5cb33c0f` with
one proposal for each of seed labels 0, 1 and 2. All three programs were fully valid,
attempted discovery, and reproduced exactly in two additional sandbox evaluations.

| Seed label | Development | Heldout | Reference reached on development |
|---:|---:|---:|:---:|
| 0 | 0.811852 | 0.927469 | no |
| 1 | **1.000000** | 0.861111 | **yes** |
| 2 | 0.862269 | 0.833333 | no |
| Reference | 0.927083 | 0.802469 | — |

The seed-1 result is not an abstention artifact: development set F1, correct-refusal
rate and discovery coverage are all 1.0, with false-discovery rate 0.0. It therefore
fails the current CONTRIBUTING.md D16 first-proposal admission check. The package
remains **candidate/Draft** and must not be promoted on the strength of its reference
score, shortcut grid or engineering gate. The source-bound summary, hashes, transport
limitations and replay result are retained in
`experiments/distribution_network_topology_first_draw_2026-09-14.json`; raw proposals
remain private.

This documentation update changes the task-package and contract hashes after the
draw, so TASK_CARD records the receipt as `historical_only`. Any scientifically
motivated redesign needs a new frozen first-proposal campaign. Budget cuts, threshold
changes or world edits chosen after seeing this result would be post-hoc and are not
used as admission evidence.

## 6. Construction and review corrections

The original route traversal loops, untestable pipe truncation, incorrect h00 alias,
slow signature enumeration, mismatched service ids and bad reference tie handling
are retained in `history_before_2026-09-12.md`. This revision also accepts empty-list
abstention, keeps partial valid scores, exposes flip probability, validates the
identifiability size bound, supplies both refusal causes, adds three nearest tasks,
corrects machine-readable citations and extends the outer runner-test timeout.
The reference's formerly dead structural-refusal and three-pipe branches have
been replaced and now have measurable effects. Each world uses a fresh sandbox
session. The unrelated cross-PR source-count rulings were removed from this PR.

## 7. Robustness, source scope and reproduction

The model is synthetic Boolean tomography, supported by
[Ma et al. (2014)](https://doi.org/10.1145/2663716.2663723).
Ostfeld is application context only. The data remain deterministic and
repository-visible; frozen heldout scores do not prove contamination resistance.
Server-held fresh-world confirmation, external domain review and frontier
calibration remain pending. Global experiments evidence is maintainer-owned and
is not regenerated by this candidate PR.

On a clean Linux checkout with CI dependencies:

```bash
python benchmarks/Engineering/DistributionNetworkTopology/verification/review_audit.py --output /tmp/network-review.json --export-candidates /tmp/network-probes
python scripts/check_task_contribution.py --task WaterDistribution/DistributionNetworkTopology --timeout 300
python -m pytest tests/test_distribution_network_topology.py -q
```

## Current clean Linux diagnostic

Measured at `4ba912cba5ffccea232a33bf68155054d9ac5898` using Ubuntu 22.04, Python 3.10.12, NumPy 1.24.4 and SciPy 1.10.1. The evidence file preserves that revision and its source hashes; this later documentation commit does not change the measured evaluator or reference.

| Variant | Development | Heldout |
|---|---:|---:|
| Reference | 0.927083 | 0.802469 |
| ADAPTIVE | 0.416667 | 0.396605 |
| COMPLEXITY_PRIOR | 0.875000 | 0.847222 |
| MAX_SIZE | 0.722222 | 0.685185 |
| MODEL_CHECK | 0.843750 | 0.635802 |
| STRUCTURAL_REFUSAL | 0.635417 | 0.469136 |

Grid best: **0.502037** development, 0.110247 heldout. Reference repeats were equal. Full grid parameters and diagnostic axes are retained in `review_evidence.json`.

The subsequent full-suite integration audit found an inherited wrapper mismatch
with current main. The task wrapper now uses `sle/frontier_eval_entrypoint.py`;
public files omit heldout and per-world diagnostics. Integration tests opt into
an explicit private sidecar. This wrapper correction leaves the measured evaluator
and reference source unchanged and is validated separately.

`integration_validation_2026-09-12.json` records the subsequent latest-main integration
checks at `22a382ce2d3780a1381fbe74d54f61c3ca8d588c`, including the
real sandbox contribution guard and exact regression scope. Historical full-suite
failures/skips and any successful unchanged-source recheck remain explicitly recorded.
This documentation-only receipt does not change the measured task or framework code.

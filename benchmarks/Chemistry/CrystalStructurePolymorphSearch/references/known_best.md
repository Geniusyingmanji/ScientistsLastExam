# CrystalStructurePolymorphSearch anchors and construction record

## 1. Reference witness

`verification/reference_multistart.py` spends all 24 calls on eight cubic and sixteen anisotropic
random seeds, then maximizes the public utility over every three-member archive. It is truth-blind
and executable, and defines score 1 without an upper clip or a global-optimality certificate.

**The current witness is inadequate as an admission reference.** The 2026-09-15 equal-budget
controls below exceed it. Reference = 1 is legal for this uncapped task; weakening the reference or
changing the margin would not repair these failures.

## 2. Baseline

`solution.py` submits three deterministic random seeds and returns all three relaxed IDs. Clean
Linux standard-entrypoint replays give score 0, valid in all five worlds, with identical full
metrics in both runs. The revised world-isolated evaluator preserves those metrics.

## 3. Capability ladder

The fixed 2026-09-15 comparison uses Linux x86_64, Python 3.11, NumPy 1.24.4 and SciPy 1.10.1,
single-threaded numerical libraries and a 300-second per-evaluation limit. Two fresh trusted
processes independently reconstruct anchors and run each candidate using the canonical
`CandidateProxy`; the oracle's trusted anchor cache is reused within each pass. This is distinct
from the separately recorded standard-entrypoint replays and contribution gate.

| Candidate | Calls/world | Development | Source-heldout |
|---|---:|---:|---:|
| Three-seed baseline | 3 | 0.000000 | 0.000000 |
| Original mixed-start reference | 24 | 1.000000 | 1.000000 |
| Original three-cubic probe | 3 | 0.170819 | 0.338632 |
| Pure cubic multistart | 24 | 1.091073 | 1.066063 |
| Pure anisotropic multistart | 24 | 0.880273 | 1.220566 |
| Eight cubic starts + sixteen incumbent perturbations | 24 | 1.299971 | 1.926998 |
| Reference seeds, three lowest enthalpies only | 24 | 0.992291 | 0.990950 |
| Development-record replay; baseline on unknown compositions | 3 | 1.624799 | 0.000000 |

All eight methods are valid in 5/5 worlds. All full metric dictionaries agree exactly between
passes. Methods, seeds, budgets and selection rules were fixed before measurement; source-heldout
metrics were inspected only for reporting. Query counts, reaped-child CPU accounting, trusted CPU and wall times
are recorded separately in the evidence summary. Concurrent single-threaded passes ran on a
four-vCPU host. Child accounting is not independently verified total candidate-subtree CPU;
wall time is an observed cost, not a controlled CPU benchmark.

Removing diversity-aware archive selection costs only 0.007709 development score. This does not
support a strong claim that archive selection supplies the task's expert-level difficulty. Other
capability ablations and hundreds/thousands of low-dimensional sweeps remain unperformed; the
bounded comparison already falsifies the current no-shortcut claim.

## 4. Shortcut probes and record coverage

The original guard declares a 0.1 relative margin, hence threshold 0.9. The newly declared strong
probes are retained even though they defeat it. The comparison is a failed admission test, not a
new certification claim.

`shortcut_record_replay.py` contains structures generated offline from **only the three development
worlds** by the publicly reproducible old witness. `references/build_record_replay.py` reconstructs
that attack; it never extracts heldout structures. The committed bank was generated once on macOS
with NumPy 1.24.4 / SciPy 1.10.1 and replayed unchanged on Linux. Offline construction costs 72
relaxations; online it makes only three charged calls per world. This is a disclosed contamination
attack, not a truth-blind search reference or a claim about independent discovery.

The five worlds are constants in public source. The two source-heldout compositions are absent
from this record bank, but their score is not the primary `combined_score`. Record replay therefore
scores 1.624799 despite zero transfer score. Merely having a heldout reporting column does not
protect the primary objective. No private instance bank or open-instance generalization guarantee
is claimed. A future instance protocol must address this before D16.

## 5. Frontier draw

No frontier-model draw has been run. The strong controls fail C12 before D16, and the reference
needs substantive improvement. Difficulty remains `unmeasured`, tier remains `candidate`, and no
long-horizon, paired-feedback or independent materials-review claim is made.

## 6. Construction errors and corrections

The first implementation used Python loops over atom/image pairs and exceeded a practical
budget. Vectorization and a 25-iteration relaxation limit made it runnable. The first witness was
then beaten by an eight-start cubic probe; its replacement added cubic starts and exact archive
selection. Neither historical repair established admission.

The original PR declared three-cubic score 0.17252846472624697. A maintainer reported
0.1595070229. On the clean merged source, two standard-entrypoint Linux replays in the pinned
Python 3.11 profile instead give 0.17081851642267407. The new declarations bind the actually tested
Linux profile. A separate macOS arm64 in-process replay with the same NumPy 1.24.4 /
SciPy 1.10.1 versions reproduces **0.17252846472624697 exactly** on unchanged scientific
source. The original declaration therefore has a reproducible platform-specific source;
its mismatch is not by itself proof that the oracle/worlds were edited. Determinism
within one runtime does not by itself establish portability between numerical runtimes.
The supported Python 3.12 / NumPy 1.26.4 / SciPy 1.11.4 profile was also replayed twice: its
three-cubic full metrics match the Python 3.11 results exactly. The maintainer's different
number remains unreproduced; its cause is not established by these runs.

The 2026-09-15 engineering revision merges current main, regenerates inventory descriptions,
resets the candidate process and private tmpfs at every world, and aligns metadata with missing
difficulty calibration. Tests include a real Linux sandbox sentinel for global/tmp leakage,
malformed submissions and caught budget overruns. Twenty-one focused Linux tests and five subtests
pass. Task cards pass for 88/88 packages; numeric-key, documented-key and taxonomy audits pass.
The unmodified full contribution gate also completed on clean `7c66f7e`: structural and
runtime phases pass, every declared score matches its standard-entrypoint measurement,
and the shortcut guard fails because its maximum 1.6247986523685534 exceeds threshold 0.9.
It exits 1 with difficulty unassessed. Candidate source hashes and shortcut-contract hash
match the final evidence revision. These engineering results do not negate the failed
scientific controls.

Reproduction from a clean checkout and a repository-supported pinned Python environment:

```bash
python benchmarks/Chemistry/CrystalStructurePolymorphSearch/references/replay_controls.py "$PWD" /private/csp-pass-1
python benchmarks/Chemistry/CrystalStructurePolymorphSearch/references/replay_controls.py "$PWD" /private/csp-pass-2
python scripts/check_task_contribution.py --task MaterialsScience/CrystalStructurePolymorphSearch --timeout 300 --output /private/csp-gate.json
```

Use writable private paths outside the checkout. The runner creates each pass directory with
mode 0700, refuses existing outputs or dirty source, and preserves all full metrics and failures.
Compare the `metrics` dictionaries in corresponding pass files exactly; timings are separate.
It does not generate model proposals or promote the task.

## 7. Robustness and remaining work

Evidence source, candidate hashes, full-metric equality, raw metric summaries and timings are
recorded in `experiments/crystal_structure_polymorph_search_revision_2026-09-15.json`. Full private
metrics and standard-entrypoint logs are retained outside Git for handoff; no global maintainer
freeze has been regenerated by this fork.

Local relaxation stops after 25 iterations without checking convergence. Further lowering of an
already relaxed seed must be distinguished from finding a new basin. Comparing the original
record energies to the already-measured replay shows further best-enthalpy reductions of
0.000503, 0.360319 and 0.281878 per atom in the three development worlds after one more
relaxation of each record; this diagnosis requires no extra optimization calls. The next revision should
first qualify local convergence, then compare complete budgeted multistart/population/basin-escape
methods, and define an instance protocol that is not satisfied by the published record bank.
These changes invalidate the old oracle/anchor measurements and require a fresh freeze and replay.

The model remains a small binary LJ surrogate. No DFT, phonon, finite-temperature, experimental or
large-cell conclusion follows. Full repository tests, independent materials review, model
admission and certification remain separate outstanding checks.

Sources: Abraham and Probert (2006), DOI `10.1103/PhysRevB.73.224104`;
Oganov and Glass (2006), DOI `10.1016/j.cpc.2006.07.020`;
Amsler and Goedecker (2010), DOI `10.1063/1.3512900`,
<https://arxiv.org/abs/1007.2003> (method guidance for a future converged-local-relaxation revision,
not evidence that the present task is hard).

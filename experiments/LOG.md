# Frontier-Science — Experiment Log

Historical model runs through 2026-06 used the local **keyless GPT-5.5** endpoint. The July
security, certification, baseline, and protocol-zero smokes do not call a model; the three
official-backend smokes evaluate only their initial program. Endpoint details remain confined
to git-ignored `conf/llm/local.yaml`; the repo ships a neutral public example.

Historical June model-run Python: `/home/azureuser/.local/bin/python3.10`. Each July JSON report
records its own exact interpreter and platform; the three optional backends use separate
version-compatible environments.

---

## 2026-06-11 — v0 harness + LennardJonesCluster

**Harness built**: `frontier_science/` package — LLM client (chat + responses wires),
config resolver, task-spec loader (black-box contract), subprocess evaluator,
OpenEvolve-lite `evolve` loop, registry, CLI (`list` / `eval` / `run` / `smoke`).

**Endpoint smoke**: `python -m frontier_science smoke` → `FS_SMOKE_OK` (gpt-5.5, responses wire). OK.

**Task: Chemistry/LennardJonesCluster**
- Oracle: LJ energy (reduced units), normalized vs Cambridge Cluster Database global minima.
- Test sizes: N ∈ {7, 13, 19} (global minima −16.505384, −44.326801, −72.659782).
- Score: `combined_score = mean_n clip(E_found(n)/E_min(n), 0, 1)`; non-interacting gas → ~0, global minima → 1.
- **Baseline (`solution.py`, random gas)**: combined_score = **0.0767** (per-size 0.148 / 0.037 / 0.045), valid=1.0.

**Evolve run (GPT-5.5, budget 6)**: baseline **0.0767 → best 1.000** (4/6 iters accepted).
Trajectory: 0.077 → 0.989 (iter1) → 0.993 (iter3) → 1.000 (iter6).
Winning program (`runs/20260611_181348/best_program.py`, 388 lines) is **legitimate**: analytic
LJ energy+gradient, L-BFGS-B local minimization, FCC + icosahedral seed geometries, and
basin-hopping with random surface-atom relocation. No oracle access, no hardcoded final
coordinates — it reaches the catalogued global minima for N=7/13/19 by real optimization.

**Finding (benchmark design)**: with famous small sizes {7,13,19} a strong model saturates to
1.0 via a correct basin-hopping implementation. To keep the task discriminative, future
versions should add hard non-icosahedral sizes (e.g. N=38 truncated octahedron, N=75/98) where
global optimization is genuinely difficult. Tracked as a v0.1 hardening item.

**Status**: end-to-end loop proven (harness + black-box contract + keyless GPT-5.5 + continuous
reward all functioning).

---

## 2026-06-11 — two more domains added (Physics, Scientific Computing)

**Physics/SpinGlassGroundState**: Sherrington–Kirkpatrick Ising ground state. Instances
N∈{16,18,20} (seed 0); exact ground states found by full enumeration (Gray-code brute force,
cross-checked against naive `itertools` enumeration for N=16: −6.985473 ✓) and embedded as the
normalization ceiling. Score = mean over instances of clip((E_allup − E_found)/(E_allup − E_min), 0, 1).
- **Baseline (best-of-3 random)**: combined_score = **0.146**.
- Evolve (GPT-5.5, budget 5): _pending — see below._

**ScientificComputing/PoissonSolver2D**: −∇²u=f on (0,1)², Dirichlet, hidden multi-mode
manufactured solution (single-mode shortcut `u=f/(2π²)` verified wrong: err 2.98). Score =
log-scaled error reduction between Jacobi-50 (E=0.820) and 4th-order Mehrstellen (E=1.48e-6);
2nd-order direct solve ≈ 0.48, 4th-order/spectral → 1.0.
- **Baseline (Jacobi 50 sweeps)**: combined_score ≈ **0.0**.
- Evolve (GPT-5.5, budget 5): _pending — see below._

### Baseline leaderboard (v0, initial programs)

| Task | Domain | Baseline combined_score |
|---|---|---|
| LennardJonesCluster | Chemistry | 0.0767 |
| SpinGlassGroundState | Physics | 0.1459 |
| PoissonSolver2D | ScientificComputing | ~0.0 |

### Evolve results (GPT-5.5, keyless, budget 5–6)

| Task | Baseline | Best | Iters to best | Winning method (verified legitimate) |
|---|---|---|---|---|
| LennardJonesCluster | 0.0767 | **1.000** | 6 | analytic LJ energy+grad, L-BFGS-B, FCC/icosahedral seeds, basin-hopping |
| SpinGlassGroundState | 0.1459 | **1.000** | 1 | greedy + tabu search + spectral-eigenvector starts + iterated local search (248 lines) |
| PoissonSolver2D | ~0.0 | **1.000** | 1 | spectral solve — divide each mode by its eigenvalue (27 lines) |

All three winners are genuine, correct scientific optimizers with **no oracle access and no
hardcoded answers** (checked by reading each `best_program.py`).

### KEY FINDING — v0 instances saturate for a frontier model

GPT-5.5 drives **all three tasks to combined_score ≈ 1.0**, usually in one iteration, by
writing the textbook-strong algorithm (basin-hopping / tabu+spectral ILS / spectral solver).
The harness, black-box contract, keyless GPT-5.5 loop, and continuous reward are fully proven
end-to-end and across three domains — but the current *instances* are too easy to discriminate
strong models. This is the central design lesson for turning the proof-of-concept into a real
benchmark.

### v0.1 hardening plan (make scores live in (0,1) for frontier models)

- **LennardJonesCluster**: add hard non-icosahedral sizes — N=38 (FCC truncated octahedron),
  N=75/76/77 (Marks decahedra), N=98 — where basin-hopping needs many restarts; cap per-size
  wall-clock so a single L-BFGS pass cannot reach the global minimum.
- **SpinGlassGroundState**: scale to N=40–80 where exact ground states are unknown; normalize
  against a strong reference (e.g. best of long parallel tempering) and allow scores >1 to be
  reported (uncapped) so genuine improvements over the reference are visible; add many seeded
  instances to reduce variance.
- **PoissonSolver2D**: switch to an accuracy×cost objective with a FLOP/wall-clock budget, and
  a non-separable RHS (no clean modal spectral shortcut), so higher-order *and* efficient
  solvers are rewarded rather than an exact modal reconstruction.
- Cross-cutting: report sample-efficiency (best-so-far AUC over charged proposal/benchmark
  `budget_units`), not just final best, so the metric stays continuous even when the ceiling is
  reachable; report actual `oracle_calls` separately.

These are tracked as the next implementation step; v0 is committed as the working foundation.

---

## 2026-06-12 — flagship tier (T3): MatrixMultiplicationRank + CapSet

Two deterministic, CPU-cheap, zero-asset flagship tasks scored **uncapped** vs. best-known
(reach SoTA = 1.0, beat it > 1.0). See `docs/difficulty_and_flagship_plan.md`.

**Algorithm/MatrixMultiplicationRank** — agent emits a rank-R bilinear decomposition of the
matmul tensor; oracle verifies exactness (tensor reconstruction to 1e-7 + random integer
matrices) and returns R. Sizes 2×2×2 / 3×3×3 / 4×4×4, anchored at best-known 7 / 23 / **48**
(AlphaEvolve 2025; recursive Strassen=49 → 0.9375 on 4×4).
- Baseline (naive schoolbook): **0.0**.
- Evolve (GPT-5.5, budget 6): baseline 0 → **0.979** (iter 3). It reproduced Strassen (7),
  **Laderman's 23-mult 3×3**, and recursive Strassen (49) — all *verified exact* — but did not
  reach the 48 frontier. Headroom to ≥1.0 remains open.

**Mathematics/CapSet** — agent builds large cap sets in Z₃ⁿ (no 3 distinct collinear); oracle
verifies and returns |S|. Dims 4/5/6 anchored at the proven maxima 20/45/112; baseline = {0,1}ⁿ
(size 2ⁿ).
- Baseline ({0,1}ⁿ): **0.0**.
- Evolve (GPT-5.5, budget 6): baseline 0 → **0.657** (does NOT saturate). Per-dim: n=4 size **20**
  (= proven max, score 1.0), n=5 size **40** (vs 45, 0.615), n=6 size **81** (vs 112, 0.354), via
  product constructions of small caps. First 3 iters scored 0 (invalid/no improvement) before it
  found a working construction.

### KEY FINDING — uncapped SoTA-relative scoring on open-frontier problems resists saturation

Unlike the v0 tasks (all → 1.0), the flagship tasks land a frontier model in (0,1):
**MatrixMultiplicationRank 0.979, CapSet 0.657.** CapSet is the model unsaturable task — GPT-5.5
matches the dim-4 optimum but falls well short on dims 5–6, and beating the known maximum on
n ≥ 7 (score > 1.0) is a genuine research frontier. This validates the difficulty-ladder thesis:
keep an easy on-ramp (v0) but anchor the hard tier on problems whose best-known value is a live
frontier, scored uncapped so there is always headroom.

### Combined leaderboard (GPT-5.5, keyless evolve)

| Task | Tier | Baseline | GPT-5.5 best | Saturates? |
|---|---|---|---|---|
| ScientificComputing/PoissonSolver2D | T0 | ~0.0 | 1.000 | yes (1 iter) |
| Physics/SpinGlassGroundState | T0 | 0.146 | 1.000 | yes (1 iter) |
| Chemistry/LennardJonesCluster | T0 | 0.077 | 1.000 | yes (6 iters) |
| Algorithm/MatrixMultiplicationRank | T3 | 0.0 | **0.979** | near (48 frontier open) |
| Mathematics/CapSet | T3 | 0.0 | **0.657** | **no** (dims 5–6 + n≥7 open) |

---

## 2026-06-15 — 3 new tasks: GraphMaxCut, ProteinLatticeHP, CirclePacking

Expanded from 5 to **8 tasks across 8 scientific domains**.

**Combinatorics/GraphMaxCut** — weighted max-cut on seeded random graphs (n=18/20/22); exact
optima by brute-force enumeration; clipped. Baseline (best-of-3 random) ~0.
- Evolve (GPT-5.5, budget 5): 0 → **1.0** (iter 1). Wrote a greedy + local-search or
  spectral-SDP solver that reaches the exact optimum.

**Biology/ProteinLatticeHP** — HP lattice protein folding (2D); 3 benchmark sequences with
known optimal energies (Dill / Unger–Moult). Baseline (straight fold, 0 contacts) = 0.
- Evolve (GPT-5.5, budget 5): 0 → **1.0** (iter 2). All optimal folds found.

**Optimization/CirclePacking** — pack unit circles in smallest square; N=7/10/13 anchored at
Packomania best-known. Baseline (regular grid) = 0.
- Evolve (GPT-5.5, budget 5): 0 → **0.999** (iter 2). Near-optimal packings via force-directed
  or simulated-annealing approach; some iters timed out on complex candidates.

### Updated combined leaderboard (GPT-5.5, keyless evolve)

| Task | Tier | Baseline | GPT-5.5 best | Saturates? |
|---|---|---|---|---|
| PoissonSolver2D | T0 | ~0 | 1.000 | yes |
| SpinGlassGroundState | T0 | 0.146 | 1.000 | yes |
| LennardJonesCluster | T0 | 0.077 | 1.000 | yes |
| GraphMaxCut | T1 | ~0 | 1.000 | yes |
| ProteinLatticeHP | T1 | 0 | 1.000 | yes |
| CirclePacking | T1 | 0 | 0.999 | near |
| MatrixMultiplicationRank | T3 | 0 | **0.979** | no (48 frontier) |
| CapSet | T3 | 0 | **0.657** | **no** |

**Pattern confirmed**: tasks with known reachable optima (T0/T1) saturate for GPT-5.5; only
the flagship T3 tasks with open-frontier optima resist. The full benchmark now has a clean
difficulty ladder: easy calibration (6 tasks) + genuinely hard flagships (2 tasks).

---

## 2026-06-21 — current 49-task inventory + baseline audit (superseded)

After the difficulty rebalance (`2bf1618`), the repository is no longer the old 50-task
snapshot. Current CLI discovery reports **49 tasks**:

- **47 hard** clipped tasks and **2 flagship** uncapped tasks.
- Oracle types: **12 analytical**, **36 physical_sim**, **1 dataset_oracle**.
- Flagships remain `Algorithm/MatrixMultiplicationRank` and `Mathematics/CapSet`.
- All tasks are currently metadata-marked CPU-only.

Baseline smoke audit:

```bash
python3 -m frontier_science list
# 49 tasks

# one-pass baseline audit over all discovered tasks, timeout 180s/eval
# output: experiments/current_49_baseline_audit.json
```

Trust status: **`UNTRUSTED_PRE_SANDBOX`**. This run predates trusted candidate isolation and
must not be used as benchmark evidence. It is retained only for provenance. At the time,
**49/49 baseline programs produced valid metrics**, with mean eval wall time **0.258s**
and max **1.686s** (`ChemicalKinetics/ReactionMechanismFitting`). Required contract files are
present for every task. Hash checks found no exact duplicate `Task.md`, `solution.py`,
`frontier_eval/run_eval.py`, or `verification/evaluator.py` files across the 49 tasks.

Notable baseline scores after the current hardening edits:

| Task | Baseline combined_score |
|---|---:|
| Photonics/MultilayerThinFilm | 0.605147 |
| Physics/SpinGlassGroundState | 0.195778 |
| Chemistry/LennardJonesCluster | 0.041930 |
| FluidMechanics/StokesShapeDrag | 0.002646 |
| Geophysics/GravityInversion | ~0 |
| Most remaining tasks | 0.0 |

Stale result warning: `experiments/batch_evolve_results.json` is from the previous **50-task**
batch. Against the current 49-task tree, it covers only **35 current tasks**, contains **15
removed tasks**, and misses **14 current tasks** added during the rebalance. It should be treated
as historical evidence only until a fresh 49-task evolve run is completed.

Recommended next run: refresh `batch_evolve_results.json` (or write a new timestamped result
file) only after the integrity and certification gates, then update this log with
cost-aware multi-seed trajectories on the certified core.

---

## 2026-07-19 — P0 integrity and P1 certification gates

The evaluator was replaced with a trusted-oracle / isolated-candidate design. Candidate code
runs under Bubblewrap with no network, read-only mounts, a minimal environment, memory/CPU/file
limits, and seccomp denial of fork/clone. A typed JSON RPC layer supports arrays, complex
numbers, tuples, mappings, candidate callables, and trusted callbacks without exposing the
oracle or metrics path.

Formal artifacts:

- `security_audit_2026-07-19.json`: **15/15 security/regression tests passed**, including
  oracle/file reads, network, fork, timeout, symlink, stdout/RPC forgery, non-finite output,
  callback deadline cases, typed-value codec checks, and preservation of scientific `raw_score`.
- `task_certification_audit_2026-07-19.json`: **7 certified, 37 candidate, 5 quarantined**;
  all certified records pass required-file, task-card, metadata, and stable-citation checks.
- `secure_baseline_determinism_2026-07-19.json`: **49/49 deterministic** over two secure runs;
  **48/49 valid**, **49/49 fail-closed**, and zero infrastructure failures. The sole invalid
  baseline is `ClimateScience/EnergyBalanceModel`: its oracle emits a non-finite metric and is
  correctly rejected. It remains a candidate, not part of the certified core.

The default registry now exposes only the seven certified tasks. The five generic trigonometric
oracles masquerading as domain simulators are quarantined. Historical `batch_evolve_results.json`
and `current_49_baseline_audit.json` are classified `UNTRUSTED_PRE_SANDBOX` in `TRUST.md` and
remain unchanged as provenance only.

---

## 2026-07-19 — P2 protocol implementation and smoke status

Implemented:

- Unified append-only trajectory schema v2 with candidate/parent hashes, best-so-far AUC over
  charged proposal/benchmark `budget_units`, separate actual `oracle_calls`, wall time,
  token/cost fields, seed, checkpoint/resume, and best-program artifacts. An unparsable proposal
  consumes budget without being counted as an oracle call.
- `greedy_rewrite` is explicitly named and no longer presented as OpenEvolve.
- Optional adapters for official OpenEvolve 0.2.26, TreeQuest AB-MCTS-A, and ShinkaEvolve. Named
  backends never silently fall back; all scores still use the secure evaluator.
- CLI selection (`--algorithm`, `--seed`, `--resume`, `--workdir`, `--feedback-mode`) and a
  multi-task/multi-seed experiment runner with Student-t 95% CIs for best score, AUC, wall,
  charged budget units, actual oracle calls, tokens, and estimated cost.
- Normal/none/shuffled **prompt-metric** controls for `greedy_rewrite`; incumbent/parent selection
  still uses true oracle scores, so these are diagnostics rather than strict causal no-feedback
  controls. Unsupported controls on upstream frameworks fail explicitly.

Local protocol/unit smoke passed without model calls. A live GPT-5.5 experiment was not recorded:
the git-ignored local Responses endpoint returned HTTP 403 on the required smoke check. Therefore
there is deliberately no claimed P2 model-performance result yet. The next valid run must use a
working endpoint and the preregistered five-seed runner; zero-step or synthetic runs are not
scientific evidence.

`protocol_smoke_2026-07-19.json` is a baseline-only two-seed runner smoke. It verifies secure
evaluation, trajectory-schema-v2 budget-unit AUC and separate oracle-call accounting, and
confidence-interval serialization, and is explicitly tagged `PROTOCOL_SMOKE_ONLY`; it contains
no search iterations and is not performance evidence.

`upstream_backend_smoke_2026-07-19.json` records real optional-environment imports, trajectory
schema v2 accounting, and secure baseline evaluations for OpenEvolve 0.2.26 on Python 3.10,
TreeQuest AB-MCTS-A on Python 3.12, and ShinkaEvolve at commit `b67a073` on Python 3.10. All
three passed. These are baseline-only integration checks, not search-performance runs.

All five dated reports referenced above were regenerated from clean source revision `f48b101`; each records
`execution_passed=true`, `trusted_evidence=true`, and `passed=true`. Result JSON and narrative
notes are outside the provenance source-dirty scope. This closes the local P0–P2 infrastructure
record, but it does not create nonzero-budget model-performance evidence.

---

## 2026-07-21 — keyless GPT-5.5 path restored and clean budget-one core pilot

The stale local Azure proxy on port 9876 returned HTTP 403 because its legacy resources had
public access disabled. Without disrupting that shared process, this project switched its
git-ignored local configuration to the existing keyless managed-identity failover proxy on port
9877 (SCUS/SWC). `python3.10 -m frontier_science smoke` returned `FS_SMOKE_OK`; endpoint details
remain excluded from version control.

`gpt55_core_pilot_b1_2026-07-21.json` is the first nonzero-budget schema-v2 report after the
security/provenance hardening. It was run from clean source revision `1c55b84` with GPT-5.5,
greedy full-file rewrite, one seed and one proposal per certified task. All seven conditions
completed with trusted secure evaluation. This is calibration evidence, not a multi-seed model
comparison.

| Task | Baseline | Best after one proposal | Valid proposal? | Tokens |
|---|---:|---:|---:|---:|
| Matrix multiplication rank | 0.0000 | 0.6458 | yes | 3,484 |
| Lennard-Jones cluster | 0.0419 | 0.9817 | yes | 4,197 |
| Cap Set | 0.0000 | 0.6496 | yes | 3,937 |
| Circle packing | 0.0000 | 0.0000 | no | 4,213 |
| Multilayer thin film | 0.5908 | 0.8905 | yes | 3,366 |
| Spin-glass ground state | 0.1958 | 1.0000 | yes | 3,710 |
| Poisson solver | 0.0000 | 1.0000 | yes | 1,810 |

The accepted programs use recognizable domain methods: recursive Strassen, basin-hopping/local
relaxation, randomized cap construction, transfer-matrix-guided coating optimization, tabu
search and a sine pseudospectral solver. The Circle Packing proposal attempted a legitimate
relaxation search but exhausted its candidate-evaluation time. The recorded
`I/O operation on closed file` was a diagnostic masking bug: after the oracle caught the first
timeout and moved to another instance, a second call to the failed worker replaced the original
exception. The secure driver now preserves the first failure so future reports classify it as a
timeout.

### Pilot conclusion

The pipeline now works end to end, including model usage accounting, immutable lineage and
trusted oracle isolation. The task calibration is not yet adequate for the planned budget
30/100/300 study: Poisson and Spin Glass saturate in one proposal, Lennard-Jones nearly does,
and public small-instance constructions create recall/contamination risk. Strong models first
map prompts to known scientific algorithms; fixed instances and a single visible proxy therefore
measure algorithm reproduction more than long-horizon discovery. Hidden procedural instances,
distribution shifts, high-fidelity validation and mechanism-specific tasks must be added before
large-budget claims.

## 2026-07-21 — 50th package: intervention-based SCM mechanism recovery

Added `CausalDiscovery/InterventionalSCM` as a **candidate**, bringing the inventory to 50
packages without changing the seven-task certified core. It exposes budgeted observational and
interventional callbacks over hidden permuted linear SCMs, including a null world. Directed graph
and coefficient recovery define the optimization target; sealed intervention prediction,
experimental cost and correct null abstention are reported separately.

The conservative baseline scores normalized 0.0 (raw mechanism 1/6 by correctly abstaining only
on the null world) and is deterministic through the Bubblewrap callback boundary. A standard
paired-intervention identifiability calibration, which does not read hidden parameters, reaches
0.978 raw mechanism and 0.931 sealed-intervention prediction within the exact 28-unit laboratory
budget. The package remains uncertified pending clean full-inventory audit, GPT-5.5 calibration,
independent evaluator/domain review and a server-held split.

Clean-revision reports bound to `dbbd063` subsequently closed the local inventory checks:

- `task_certification_audit_2026-07-21.json`: 50 packages; 7 certified, 38 candidate and
  5 quarantined; no orphaned records or admission issues on certified tasks.
- `secure_baseline_determinism_2026-07-21.json`: 50/50 deterministic over two runs, 49/50
  valid, 50/50 fail-closed and zero infrastructure failures. The only invalid baseline remains
  `ClimateScience/EnergyBalanceModel`; the new SCM baseline is valid and deterministic.

Both reports set `execution_passed=true`, `trusted_evidence=true` and `passed=true`.

### GPT-5.5 mechanism-task calibration

`gpt55_scm_pilot_b1_2026-07-21.json` was run from clean revision `4b9364d` with one
`greedy_rewrite` proposal. GPT-5.5 improved the normalized mechanism target from 0.0 to
**0.9830** using 4,088 tokens. Its submitted program performed paired interventions on every
variable, estimated the total-effect matrix, inverted it to obtain direct structural
coefficients, thresholded/enforced acyclicity, and used the remaining budget for observational
refinement.

The result used exactly 28/28 laboratory budget units in every world, achieved raw mechanism
score **0.9858**, sealed intervention-prediction score **0.9594**, and correctly abstained on the
null world. Thus the mechanism and validation curves did not meaningfully diverge in this
pilot. This is a useful negative calibration result: adding an intervention API and mechanism
metric does not automatically make a discovery task hard. A fully observed linear SCM with
every variable directly intervenable admits a standard total-effect inversion that GPT-5.5 can
implement in one proposal. The next version needs hidden/latent variables, partial intervention
access, mixed nonlinear mechanisms, model-misspecified/null cases or a tighter adaptive budget;
the current package remains a candidate/on-ramp rather than an open-frontier headline task.

## 2026-07-21 — GPT-5.5 candidate wave 1: oracle-first triage

`gpt55_candidate_wave1_b1_2026-07-21.json` screened four metadata-complete candidates with
GPT-5.5, greedy full-file rewrite, seed 0 and one proposal. The report is a trusted secure-eval
artifact bound to clean source revision `98bc695`; all four runs completed and their proposed
programs were valid. It is calibration evidence only, not a model comparison or certification.

| Task | Baseline | Best after one proposal | Tokens | Admission interpretation |
|---|---:|---:|---:|---|
| Sparse recovery | 0.0000 | 0.9583 | 2,583 | Near-saturated by standard OMP/CoSaMP/HTP methods; add sensing, sparsity and noise shifts before using it as a headline task. |
| Seismic inversion | 0.0000 | 0.0000 | 4,300 | Result is non-diagnostic: the visible forward model depends only on mean velocity, so the requested layerwise inverse is non-identifiable. |
| Neutron diffusion criticality | 0.0000 | 0.3662 | 2,311 | Apparent headroom, but the fixed `k_baseline + 0.07` normalization anchor has not been independently established. |
| Lyapunov control | 0.0000 | 0.3055 | 2,914 | Invalid for capability claims: the variational equation omitted the state derivative of feedback, so the reported quantity was not the closed-loop MLE. |

The cross-task lesson agrees with the certified-core pilot: a plausible scientific name and a
valid numerical output are insufficient admission criteria. Budget-one screening must follow,
not precede, identifiability and oracle review. Template-solvable tasks should become on-ramps
or gain procedural hidden regimes; defective or unsupported evaluators must be repaired and all
old scores superseded before any longer trajectory is run.

### Lyapunov oracle correction and replay

The Lyapunov evaluator now measures the actual sampled-data closed loop with a black-box,
two-trajectory Benettin estimator, including a 20-time-unit transient. An analytic cancellation
plus damping regression distinguishes it from the old open-loop variational equation. The zero
controller gives MLE **0.9134**, consistent with the classical Lorenz regime. Re-evaluating the
immutable wave-1 GPT-5.5 candidate gives MLE **-1.4132**, average control energy **0.4844**, and
clipped score **1.0**. Thus the old 0.3055 score is superseded, but the correction does not rescue
task headroom: nearest-equilibrium feedback is a standard one-proposal solution. The task is an
on-ramp until hidden parameter/initial-condition/actuator regimes and a genuine energy-stability
tradeoff replace the single clipped target.

### Neutron-diffusion stencil and anchor correction

The original variable-diffusion tridiagonal assembly shifted one off-diagonal array by one
cell. It was therefore nonsymmetric and nonconservative, allowing artificial loadings with
`k_eff` near 3.9 and supporting the incorrect edge-enrichment story in the prompt. The corrected
finite-volume stencil uses harmonic interface coefficients on matching upper/lower diagonals.
A separate dense generalized-eigenvalue implementation agrees with power iteration to below
`2e-11`: uniform 5% gives **0.9841790542**, while a deterministic symmetric multistart
multistart-SLSQP witness gives **1.0591815191**, an improvement of **0.0750024649**. The score now uses
this checked witness rather than the unsupported `k_baseline + 0.07` constant.

Replaying the immutable wave-1 candidate under the corrected oracle gives `k_eff=0.904128` and
score **0.0**, superseding its old 0.3662. It had moved enrichment toward leaking boundaries,
which was rewarded only by the faulty stencil. The repaired task still needs procedural reactor
regimes and independent domain review before certification.

`neutron_diffusion_anchor_2026-07-21.json` records this calibration from clean revision
`3d9075a`. All 16 deterministic starts converged, both independent solvers agreed, and the
report sets `execution_passed=true`, `trusted_evidence=true` and `passed=true`.

### Seismic refraction identifiability repair

The superseded SeismicInversion forward model returned `path_length / mean(velocities)`, making
all layer permutations and infinitely many profiles observationally equivalent. It has been
replaced by first-arrival direct/head-wave physics for procedurally generated 4–6 layer surveys.
Every scenario has a full-column-rank finite-difference sensitivity matrix (condition numbers
8.4–20.8). A multistart nonlinear least-squares solver that uses only public task inputs reaches
development score **0.9981**, velocity-mechanism score **0.9988**, and unobserved-offset
prediction score **0.9997**. The task now measures a genuine, identifiable inverse problem;
these high reference values also warn that it may remain a textbook-template task, which the
next GPT-5.5 budget-one calibration must test.

`seismic_inversion_calibration_2026-07-21.json` records the reference and rank checks from clean
revision `7d1add3`; it sets `execution_passed=true`, `trusted_evidence=true` and `passed=true`.

The subsequent clean-revision GPT-5.5 budget-one run
`gpt55_seismic_v2_b1_2026-07-21.json` improves the weak baseline from 0 to **0.993985** using
3,224 tokens. The submitted program implements the disclosed head-wave equations with
multistart SLSQP plus differential evolution. Its separate velocity-mechanism score is
**0.983173** and unobserved-offset prediction score is **0.997326**, so optimization,
mechanism recovery and interpolation improve together here. This validates the repaired task
but also establishes that it is an on-ramp: the remaining science challenge needs unknown
thicknesses, low-velocity/non-identifiable layers, outliers, anisotropy/model mismatch, adaptive
survey design and calibrated refusal rather than simply more optimizer proposals.

### Climate EBM quarantine decision

`ClimateScience/EnergyBalanceModel` is now explicitly quarantined. Its explicit diffusion
iteration uses `D * dt / dx^2 = 85.184` at the textbook baseline, far outside the stability
region, so it produces all-NaN temperatures and correctly fails closed at the secure metric
boundary. More importantly, the embedded temperature vector has no reproducible ERA5 data
provenance and a single steady profile cannot identify the seven jointly fitted radiation,
diffusion, albedo, ice-threshold and solar-scaling parameters. A stable linear solve alone would
not cure those scientific defects. The replacement must use documented data extraction,
multiple forcing/climate regimes, uncertainty, held-out years and parameter/prediction
separation.

### Post-repair full-inventory audit

Clean revision `47c3613` was re-audited after the Lyapunov, neutron, seismic and Climate
decisions. `task_certification_audit_2026-07-21_v2.json` records 50 packages: **7 certified,
37 candidate and 6 quarantined**. `secure_baseline_determinism_2026-07-21_v2.json` records
**50/50 deterministic, 49/50 valid, 50/50 fail-closed and zero infrastructure failures** over
two repetitions. The sole invalid baseline is the explicitly quarantined Climate EBM; it is
deterministically rejected at the non-finite metric boundary. Both reports set
`execution_passed=true`, `trusted_evidence=true` and `passed=true`.

## 2026-07-21 — candidate wave 2 adversarial admission audit

The remaining seven metadata-complete candidates were audited before spending GPT-5.5 calls.
All seven have admission-blocking defects: a reference-length RIR crashes against its shorter
baseline; the low-thrust integrator advances 0.445 initial orbital periods per step and gives an
unforced relative energy drift of 9.34; the pendulum's stable/unstable equilibria contradict its
labels; a nonphysical centerline injection scores 0.9994 on the cavity task; the alloy surrogate
is a hand-written pseudo-physical polynomial with no dataset; an analytic phase ramp scores 1.0
on the scalar-FFT task mislabeled RCWA; and the heat-exchanger pass count changes effectiveness
by less than `6e-16` while maximum area trivially improves the score. All seven are quarantined
pending replacement or substantive repair. No model calls were used on invalid measurement
instruments.

`candidate_wave2_admission_audit_2026-07-21.json` reproduces all seven defects from clean
revision `3b12e7c`; it sets `execution_passed=true`, `trusted_evidence=true` and `passed=true`.

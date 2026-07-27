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

### Pendulum-v2 rebuild

The pendulum task was rebuilt rather than numerically patched. The public convention remains
`theta=0` down and `theta=pi` upright, and the corrected dynamics now make those equilibria
stable and unstable respectively. Two-substep RK4 replaces forward Euler. Five development
initial states share a disclosed nominal plant, while four evaluator-only robustness scenarios
change masses/length/friction and apply bounded force pulses. Development utility combines
balanced time, terminal stabilization, RMS force and cart travel; robustness is reported
separately. A public-input nominal energy-shaping plus LQR reference scores **0.870997** on
development with balanced fraction 1.0, but only **0.454697** on shifted validation. This is the
desired science-specific gap: nominal task success does not imply robust control discovery.

`pendulum_v2_calibration_2026-07-21.json` records this result from clean revision `e098dc2`; it
sets `execution_passed=true`, `trusted_evidence=true` and `passed=true`.

An initial GPT-5.5 budget-one diagnostic on revision `57c0e1b` failed to improve the zero-force
baseline (proposal 0.0000185 versus baseline 0.0000211). Inspection showed that the generated
controller assumed a point-mass pendulum, whereas the evaluator uses the `4/3` effective-inertia
cart-pole equations. Because the original v2 Task text disclosed parameters but not those exact
equations, this run cannot establish headroom. The dynamics were subsequently added verbatim to
the public contract; the diagnostic artifact is retained but superseded for admission purposes.

With the exact equations disclosed, the clean-revision rerun
`gpt55_pendulum_v2_contract_b1_2026-07-21.json` improves development from **0.000021** to
**0.796874** in one proposal using 3,263 tokens. It implements energy shaping plus local LQR,
balances on 97.97% of scored development time, and obtains shifted robustness **0.630753**.
One hidden low-mass/long-pendulum case runs away, producing a development–robustness gap of
**0.166122**. The task is therefore restored as a candidate: it is partly template-solvable but
retains a measurable robustness problem. The paired failed diagnostic also establishes a
benchmark-design lesson: apparent model failure caused by an underspecified plant contract is
not scientific headroom.

### Pendulum-v2 budget-three development/robustness divergence

`gpt55_pendulum_v2_b3_2026-07-21.json` is the first short trajectory in this project to expose
a science-specific proxy gap. Starting from the corrected public contract, GPT-5.5 produces a
valid controller at every proposal. Step 1 scores development **0.690588** and hidden shifted
robustness **0.640591**. Oracle feedback then helps step 2 improve the selected development
score to **0.854016**, while robustness slightly falls to **0.639041**; the gap widens from
**0.049997** to **0.214975**. Step 3 reaches development 0.850876 and robustness 0.634523 and is
correctly rejected by development selection.

This single-seed diagnostic does not prove a causal feedback or Goodhart effect, but it
demonstrates why Frontier-Eng-style best-score curves are insufficient in scientific settings:
the agent learned to improve the visible nominal objective without improving evaluator-only
robust control. A preregistered paired multi-seed normal/selection-blind study is required before
making an inferential claim.

### Default-sealed science metric protocol

Search visibility is now a closed allowlist rather than an evaluator convention. Greedy and
AB-MCTS search state/checkpoints retain only feasibility and selection metrics. OpenEvolve and
Shinka receive the same public view; the trusted evaluator atomically stores the full metric
dictionary in a candidate-source-hash sidecar, and the adapter merges it into the unified trace
only after upstream search completes. Unknown future fields are sealed by default, so
`robustness_score`, `mechanism_score`, held-out predictions and per-instance details cannot leak
through new task-specific names. Sidecar determinism, public/full consistency, checkpoint
redaction and prompt visibility are covered by the 65-test suite. Official-backend integration
reproduction is the remaining acceptance check.

That acceptance check is now complete at baseline-integration scope. From clean revision
`aff026d`, OpenEvolve 0.2.26, TreeQuest 0.3.2 and ShinkaEvolve commit `b67a0732` each evaluated
Pendulum-v2 through the trusted sandbox. In every backend, `robustness_score` is present in the
unified trusted trajectory and absent from upstream-owned search state/database/checkpoints.
`upstream_metric_sealing_audit_2026-07-21.json` validates the common revision, pinned
distributions/commits, trajectory accounting and no-leak assertions with no issues; it sets
`execution_passed=true`, `trusted_evidence=true` and `passed=true`. This is still baseline-only
integration evidence, not a nonzero-budget framework comparison.

## 2026-07-21 — inverse/discovery candidate admission audit

Seven of eight inverse-track candidates have reproducible scientific-validity failures and are
quarantined before model screening. Radiative retrieval maps 10 observations to 20 unknowns
while selecting on one hidden fixed-profile RMSE. The true chemical-kinetics parameters and an
infinite-rate mechanism differ in score by only `3.2e-12`. Gravity signal RMS is only 0.033 of
the declared noise and both instances share one truth. Ocean current signal displacement is
0.57 m versus 1007 m noise, so even the true field scores `1.97e-5`. The demographic SFS
surrogate has rank-two sensitivity for five parameters and exactly ignores three. The RANS
surrogate has rank three for five constants and uses analytic pseudo-DNS. The FWI entrypoint
receives no observed waveform or experiment callback and can only guess one fixed hidden model.
NMR fitting remains a candidate for procedural multi-spectrum rebuilding. These results sharpen
the common conclusion: an inverse-problem narrative does not create a scientific-discovery task
unless observations identify the claim and the interface actually supplies evidence.

The machine-readable reports `inverse_candidate_admission_audit_2026-07-21.json` and
`task_certification_audit_2026-07-21_v3.json` bind clean source revision `54f992d`; both set
`execution_passed=true`, `trusted_evidence=true` and `passed=true`.

## 2026-07-21 — candidate wave 3 admission audit

Six high-priority scientific topics were adversarially checked before model screening. NMR,
D-optimal design, quantum gate synthesis, DC OPF and antenna synthesis all contain non-finite
fail-open paths; `NaN` or a zero array receives full score. The antenna evaluator also measures
its uniform arrays near -9 dB while normalizing against a claimed -13.3 dB PSLL. The OPF
baseline has 65 MW of line violations, yet the candidate interface omits susceptances and
generator-bus assignments. The purported canonical 10-bar truss has only nine unique
undirected members because its middle vertical is duplicated, invalidating its literature
anchor. All six packages are quarantined pending substantive v2 rebuilds; this is not a judgment
that their scientific domains lack value.

`candidate_wave3_admission_audit_2026-07-21.json` and
`task_certification_audit_2026-07-21_v4.json` bind clean revision `e911639`; both set
`execution_passed=true`, `trusted_evidence=true` and `passed=true`.

### Optimal experimental design v2 rebuild

The fail-open fixed-polynomial OED package was replaced with a general discrete D-optimal
allocation policy over supplied candidate points and local sensitivity matrices. Six
development instances span Legendre, Fourier, exponential-decay and saturation models; four
larger or shifted families are retained only as evaluator-side validation. Every reference is
computed by multiplicative design updates and must satisfy the Kiefer-Wolfowitz maximum-
sensitivity condition to relative tolerance `1e-4`. An invertible column whitening keeps
information-matrix condition numbers numerically safe without changing D-optimal allocations.
The weak first-k baseline scores 0; a generic uniform policy scores about 0.859 development and
0.852 validation, while a sequential determinant-gain implementation scores about 0.989 and
0.993. Non-finite indices now fail closed on all ten instances. The task is re-admitted as a
candidate pending GPT-5.5 headroom calibration, independent review and server-held instances.

The clean-revision GPT-5.5 calibration resolves the headroom question for v2. In one proposal,
the model writes a generic column-whitening, multiplicative approximate-design, sequential
determinant-gain and Fedorov-style exchange implementation. Development rises from 0 to
**0.990615**, while sealed shifted-family validation rises from 0 to **0.993697**; the proposal
uses 4,774 tokens. This is scientifically coherent generalization, but it also means the task
saturates at budget one. OED-v2 is retained as an on-ramp and feedback/validation control, not
as evidence of long-horizon autonomous discovery. `gpt55_oed_v2_b1_2026-07-21.json` binds clean
revision `2d2d62d` and sets `execution_passed=true`, `trusted_evidence=true` and `passed=true`.

## 2026-07-21 — candidate wave 4: complete inventory triage

The final 12 unscreened candidates all fail scientific admission. Reproduced defects include:
an acoustic absorber whose model stays below 0.01 absorption against a 0.92 anchor; a prosthetic
joint objective solved by all-upper bounds; distillation with fixed 0.99 top purity and no feed
balance; flame speeds clipped at 5 m/s for both baseline and reference; a purported Stokes
solver that only measures perimeter; heat-source inversion with no target observations; an
inventory simulator whose retailer service is independent of upstream stocks; a calorimeter
baseline with 10.7 X0 and 100% rather than 3.8% resolution; an HF energy functional whose
complete two-coefficient minimum is +0.444915 Ha versus a claimed -1.1167 Ha; MOSFET units that
produce Ion/Ioff 1.0019 versus 1e8; a Rankine surrogate below 6.6% versus its 46% anchor; and a
traffic model trivially solved by maximum greens because no conflicting phase exists. Seven of
these packages also expose direct non-finite fail-open paths. All 50 inventory packages have now
received an adversarial admission pass; the resulting 7 certified / 7 candidate / 36
quarantined split makes explicit that directory count was never the target.

`candidate_wave4_admission_audit_2026-07-21.json` and
`task_certification_audit_2026-07-21_v6.json` bind clean revision `5187019`; both set
`execution_passed=true`, `trusted_evidence=true` and `passed=true`.

## 2026-07-21 — active dynamical-law discovery laboratory

Added `DynamicalSystems/ActiveLawDiscovery` as the first task designed jointly around active
experiment choice, sparse governing-equation recovery, sealed rollout/shift validation and
calibrated refusal. The public 13-term controlled polynomial library is evaluated across seven
development and six shifted-validation worlds, including null and out-of-library dynamics.
Every experiment is charged in integration-step blocks. Always abstaining is normalized to
zero; exact laws and correct null/model-inadequacy abstention score one. A generic multi-start,
persistently excited SINDy reference reaches development mechanism **0.721**, sealed validation
mechanism **0.394**, and rollout prediction **0.962/0.772**. It nevertheless makes one
development and two validation false discoveries, establishing a useful prediction–mechanism–
refusal separation before any LLM calibration.

### GPT-5.5 active-law calibration

At budget one, GPT-5.5 writes a diverse active-experiment plan plus sparse integral regression.
It reaches development mechanism **0.796281**, sealed validation mechanism **0.744607**, and
sealed rollout prediction **0.997392/0.995864**. Every in-library mechanism is recovered near
perfectly and both null worlds are correctly rejected, but both out-of-library worlds receive
high-confidence polynomial explanations. Thus the remaining error is epistemic refusal, not
trajectory prediction. The run uses 4,964 tokens.

An independent budget-three run shows the limitation persists under outer score feedback.
Its first proposal reaches development/validation mechanism **0.711322/0.717925** and rollout
**0.985386/0.992275**, again with false mechanisms in both misspecified worlds. Later proposals
score 0.692210 and 0.679995 and are rejected; all retain the same two false discoveries. Because
the search sees only normalized development mechanism, these single-seed diagnostics do not
prove a causal feedback effect, but they establish non-saturation and a concrete reliability
frontier for paired feedback/refusal studies. `gpt55_active_law_b1_2026-07-21.json` and
`gpt55_active_law_b3_2026-07-21.json` both bind clean revision `cd65c17`.

## 2026-07-21 — quantum gate synthesis v2 rebuild

The fail-open single-CNOT package was replaced with a policy task over supplied one- and
two-qubit Hamiltonians and targets. Four development and two interleaved held-out instances use
exact matrix-exponential propagation and global-phase-invariant process fidelity. Pulse shape,
finiteness and amplitude bounds are rejected rather than clipped. Evaluator-only metrics retain
worst-case detuning, +/-6% amplitude calibration, bandwidth-filtered execution, held-out target
transfer, RMS and slew. An independent nominal GRAPE witness reaches essentially unit fidelity
on all six targets; the same nominal pulses score 0.957 development robustness and 0.984 held-out
robustness, establishing a real but attainable hardware-shift gap. Gate-v2 is re-admitted as a
candidate pending frontier-model calibration and independent review.

GPT-5.5 reproduces a general GRAPE-style solver at budget one, reaching nominal development
**0.999872** and held-out policy **0.999992** in 3,495 tokens. Sealed hardware robustness is
lower at **0.956894/0.983037**; the development gap is driven especially by the high-slew CZ
pulse, whose worst-shift score is 0.867070. In an independent budget-three run, visible nominal
score rises from 0.99999956 to numerical unity. Development hardware robustness incidentally
rises from 0.966531 to 0.974567 as CNOT/CZ pulses change, while held-out robustness remains
approximately 0.9845. Because robustness was sealed and only one seed was run, this correlated
improvement is not evidence that score feedback teaches robust control. It does show that a
Frontier-Eng-style saturated nominal curve can hide a materially lower hardware curve.

## 2026-07-21 — DC optimal power flow v2 rebuild

The fail-open fixed six-bus package was replaced by a network-general policy task over six
complete 5--9 bus meshed DC networks. Candidate policies receive generator locations, demands,
bounds, quadratic/linear costs, line topology, susceptances and thermal limits. Dispatches must
be finite, balanced, within generator bounds and nominally feasible. The trusted evaluator then
exhaustively opens every non-islanding line and retains N-1 security, held-out-network and
per-instance metrics outside the search-visible score.

Two separately implemented convex QP policies expose the intended economy--security frontier.
The nominal DC-OPF witness reaches development/held-out nominal score **1.0/1.0**, but sealed
N-1 robustness is only **0.031378/0.0000007**. The security-constrained witness instead reaches
development/held-out nominal score **0.144294/0.079133** and N-1 robustness approximately
**1.0/1.0**. The proportional baseline is feasible under every tested outage, while non-finite
and unbalanced dispatches fail closed. The clean-revision calibration reproduces these values
on `f64aeeb`, as do the updated wave-3 admission, 51-package certification and 51×2 secure
baseline reports. All four set `execution_passed=true`, `trusted_evidence=true` and
`passed=true`; the secure baseline remains 51/51 deterministic, 50/51 valid, 51/51 fail-closed
with zero infrastructure failures.

### GPT-5.5 OPF calibration

At budget one, GPT-5.5 writes a generic nominal DC-OPF solver and reaches development/held-out
nominal score approximately **1.0/1.0** in 3,784 tokens. The sealed N-1 results sharply differ:
development/held-out robustness is **0.031378/0.0000007**, and only **0.113997** of complete
development outage scenarios are feasible on average. The candidate enumerates no line
contingencies; it implements the visible nominal problem exactly.

An independent budget-three run first produces an invalid candidate, then two valid nominal
solutions near score 1.0. Both valid proposals retain development robustness **0.031378**,
held-out robustness **0.0000007** and outage feasibility **0.113997**. The run uses 12,309
tokens. These one-seed calibrations indicate a reproducible nominal/security separation within
each trajectory, but do not identify a causal feedback effect or a population-level model
property. `gpt55_opf_v2_b1_2026-07-21.json` and `gpt55_opf_v2_b3_2026-07-21.json` bind clean
revision `f64aeeb` and retain full trusted metrics outside search state.

### Portable science-curve archive

Historical batch reports retained run summaries while their full per-step science metrics lived
under git-ignored `runs/`. The batch runner now writes a post-search compact trajectory snapshot
containing scalar visible and sealed metrics, candidate lineage hashes and a SHA-256 binding to
the full raw trajectory. This snapshot is written only after a backend returns and is never
placed in agent or search state. The current derived evidence builder backfills 15 trusted OED,
Pendulum, GateSynthesis, ActiveLawDiscovery, OPF, Truss, Antenna and NMR normal calibration conditions; their cross-task
claim audit is recorded in `.research/science_common_findings.md`.

## 2026-07-21 — strict iterative-feedback implementation pilot

The preregistered pilot compares normal greedy iteration with a strict `selection_blind`
open-loop batch on Pendulum-v2, GateSynthesis-v2, ActiveLawDiscovery and OPF-v2. Each task uses
three replicate identifiers, three proposal slots per condition and counterbalanced within-task
condition order. Every blind proposal sees the frozen baseline program and public baseline
metrics; evaluated scores affect only offline best-of-batch reporting. The Azure Responses
endpoint does not expose a server-side seed.

All **24/24 conditions** completed with clean trusted provenance, **72 proposal slots**, **96
actual oracle calls**, **352,881 tokens** and no condition-level infrastructure failures. The
derived analysis validates every blind parent hash and selected-candidate metric. No task has a
direction-stable normal-over-blind advantage, and every preregistered performance or
science-outcome n=3 interval spans zero.
Pendulum's mean paired visible/shifted-robustness differences are -0.2479/-0.0068; Gate's are
0.0000019/0.0118; ActiveLaw's visible/validation-mechanism differences are -0.0493/-0.0466; and
OPF's visible/N-1 differences are approximately zero. ActiveLaw retains one false discovery in
each split for every selected condition, and OPF retains complete-outage feasibility 0.113997 in
both conditions.

Normal runs use 3,070--6,676 more tokens per three-proposal run on average, so the pilot is
call-matched but not token-matched. These results establish that the strict control and portable
analysis workflow run end to end. They do not establish that iterative feedback is beneficial or
ineffective. A confirmatory Track F study requires at least ten replicates, matched token/context
budgets and delayed/replayed plus score-information-only controls. Full interpretation is in
`.research/feedback_pilot_results.md`.

## 2026-07-21 — structural truss sizing v2 rebuild

The invalid duplicate-member fixed 10-bar package was replaced with a policy task over six
interleaved procedural structures: four development and two held-out aluminum, steel and
titanium X-braced/Pratt families with 8--15 unique members and two load cases each. Candidates
receive complete geometry, support, load, material, allowable, displacement, area and similar-
section inertia data. The trusted direct-stiffness FEM rejects malformed or nominally infeasible
areas and evaluates asymmetric tension/compression stress, every free displacement degree and
pin-ended Euler buckling. Evaluator-only load, modulus/allowable, manufactured-area and combined
shifts remain outside search state.

Independent five-start SLSQP calibration with separately implemented FEM residuals produces
feasible nominal and robust local witnesses with a 5e-4 utilization margin; no global optimum is
claimed and lighter feasible candidates may score one. The nominal witness policy reaches
development/held-out nominal score **1.0/1.0**, but every instance fails at least one shift and
development/held-out robustness is **0.0/0.0**. The robust witness trades nominal score down to
**0.732604/0.667469** while reaching shifted robustness **1.0/1.0**. The all-maximum baseline is
safe under all shifts, and non-finite, wrong-length, out-of-bound and nominally infeasible
designs fail closed. Truss-v2 is re-admitted as a candidate pending GPT-5.5 headroom calibration,
server-held structures and independent structural-engineering review.

### GPT-5.5 Truss-v2 calibration

At budget one, GPT-5.5 writes a robustness-aware SLSQP policy but returns the all-maximum design
on every instance, so development, held-out and shifted robustness scores remain zero. In an
independent budget-three normal run, all three proposals are accepted and visible development
rises **0.000000 -> 0.415579 -> 0.548497 -> 0.611494**. The selected policy transfers nominally
to held-out structures at **0.422348**, but its final accepted update lowers sealed held-out
robustness from **0.206438** to **0.077881** while raising held-out nominal score from 0.251321.
Development robustness ends at 0.536098 and only 75% of development shifted cases are feasible.

A same-local-identifier strict selection-blind budget-three diagnostic selects development
**0.084629**, development robustness **0.069867**, held-out nominal **0.277788** and held-out
robustness **0.416438**. Normal therefore has a large visible advantage in this one diagnostic
but worse held-out robustness. It also uses 19,659 versus 12,637 tokens, and the Azure endpoint
has no server-side seed. The contrast is evidence of task headroom and motivates a token-matched
paired study; it is not a causal feedback claim. All three reports bind clean task source
revision `4c31f5d`; a derived analyzer validates raw trajectory hashes and parent lineage.

## 2026-07-21 — antenna array synthesis v2 rebuild

The fail-open two-ULA package with incorrect fixed `-13.3 dB` anchors was replaced by a policy
task over four development and two interleaved held-out arrays. Instances span 12--24 elements,
broadside and scanned beams, uniform and mildly nonuniform positions, and two interference
neighborhoods. Overall complex excitation scale is quotient-normalized by nominal target
response; zero/non-finite response, wrong length, excessive normalized L2 norm and excessive
per-element amplitude all fail closed. Nominal score uses measured sidelobe/null quality rather
than a prose constant.

Evaluator-only validation exhaustively covers every single-element failure plus `+/-4%`
frequency offsets, bounded position errors and bounded gain/phase calibration errors. An
independent enumeration of 750 Kaiser-taper/regularized-null-projection policies per instance
reproduces every declared reference parameter. Nominal witnesses reach development/held-out
nominal score **1.0/1.0** but only **0.465990/0.302317** robustness. Robust witnesses reach
robustness **1.0/1.0** while retaining nominal **0.384375/0.507933**, establishing a real
pattern-quality/hardware-robustness tradeoff without claiming global optimality.

Citation metadata was checked through Crossref and DOI resolution. Dolph's article is
*Proceedings of the IRE* 34(6), 335--348, DOI `10.1109/JRPROC.1946.225956`; Ramsdale and
Howerton's element-failure/error study is *JASA* 68(3), 901--906, DOI `10.1121/1.384777`.
Antenna-v2 is re-admitted as a candidate pending GPT-5.5 headroom calibration, server-held
arrays, full-wave or measured-pattern replication and independent antenna-domain review.

### GPT-5.5 Antenna-v2 calibration

At budget one, GPT-5.5 writes a general taper/null-projection policy that reaches development
and held-out nominal scores **0.999263/0.995115**. Sealed development/held-out robustness is
only **0.624204/0.394718**, despite shifted target-gain feasibility remaining one. This makes
Antenna-v2 a useful nominal-versus-hardware on-ramp, but not a long-horizon nominal-optimization
headline task.

An independent budget-three normal run accepts all three proposals and raises visible
development score **0.845170 -> 0.993267 -> 1.000000**. Across those accepted proposals,
development robustness falls **0.704823 -> 0.635511 -> 0.576348** and mean worst-shift quality
falls **10.9824 -> 10.6213 -> 10.3506 dB**. Held-out nominal ends at **0.998717** and held-out
robustness at **0.534775**. The dissociation shows that nominal selection did not optimize the
sealed hardware objective within this trajectory. It is descriptive, not a causal feedback or
population result: each condition has one run, the endpoint exposes no model seed, and no
robustness-aware treatment was run.

The task calibration, wave-3 admission, 51-package certification, 51x2 secure baseline and both
GPT-5.5 reports bind clean task revision `8c1373a`. A dedicated analyzer validates report and
raw-trajectory hashes, accepted-parent lineage and every accepted nominal/robustness contrast.

## 2026-07-22 — NMR spectrum fitting v2 rebuild

The fail-open fixed eight-peak reconstruction task was replaced with ten procedural spectra:
six development and four held-out cases spanning resolved and overlapping Lorentzian,
Gaussian/Voigt, low-SNR, variable-axis, smooth-baseline and phase-distorted regimes. Candidates
now return a bounded peak count, center, Lorentzian HWHM, Gaussian sigma, amplitude, line-shape
label, confidence and optional abstention. Non-finite, inconsistent, out-of-range, nonpositive
and contradictory peak artifacts fail closed.

Peak count and parameters are scored by order-invariant optimal assignment. Clean-signal
reconstruction, confidence calibration, false discoveries, correct refusals and held-out
mechanism quality remain separate; only normalized development mechanism/refusal quality drives
selection. The valid always-abstain baseline scores zero, while exact simulator parameters plus
correct null/phase-distortion refusals score one on both splits. Independent Voigt profile checks
match the Olivero–Longbothum FWHM approximation within `1e-4` relative error.

A truth-blind asymmetric-baseline/peak-finding/Lorentzian least-squares policy scores
**0.271110** development and **0.146229** held-out normalized mechanism/refusal quality, despite
clean-signal reconstruction **0.887314/0.851059**. It falsely fits the development
phase-distorted spectrum and one of two held-out unsupported spectra. This establishes useful
headroom and directly demonstrates why residual reconstruction cannot serve as a discovery
metric. BATMAN, ASICS and Voigt-line-width citation metadata and DOI resolution were checked
before the task card was written. NMR-v2 is re-admitted as a candidate pending paired controls,
server-held spectra and independent review.

### GPT-5.5 NMR-v2 calibration

At budget one, GPT-5.5 improves normalized development mechanism/refusal from zero to
**0.427998**, above the truth-blind classical baseline **0.271110** without saturating the exact
reference. Its held-out mechanism/refusal is only **0.176186**, while development/held-out
reconstruction is high at **0.874116/0.878353**. It correctly abstains on each null spectrum but
falsely fits both phase-distorted spectra, yielding false-discovery and correct-refusal rates
**0.5/0.5** on each split.

An independent budget-three normal trajectory scores **0.375440 -> 0.212692 -> 0.161475**;
only the first proposal is accepted. Its selected held-out mechanism/refusal is zero because it
falsely fits both unsupported held-out spectra. Both feedback-conditioned rewrites falsely fit
every unsupported spectrum on both splits, even though development reconstruction remains
**0.819033/0.782865**. The run therefore exposes a residual-versus-mechanism/refusal failure,
not evidence that iterative feedback caused it: each condition has one run, different local
identifiers, no server-side model seed and no matched control.

The task calibration, wave-3 admission, 51-package certification, 51x2 secure baseline and both
GPT-5.5 reports bind clean source `bbb7787`. A dedicated analyzer validates their report and raw
trajectory hashes, accepted-parent lineage, classical/model contrasts and rejected-proposal
failure modes.
## 2026-07-22 — active reaction-mechanism discovery v2

Rebuilt `ChemicalKinetics/ReactionMechanismFitting` from a saturated three-species curve fit into
an active four-species mechanism-discovery laboratory. Candidates choose temperature, initial
mixture, sampling schedule and one or two assayed species under twelve charged budget units,
then return a sparse support, Arrhenius rate curves, confidence or an explicit refusal. Six
development and five held-out worlds include novel topologies, null kinetics and a saturating
out-of-library mechanism. Four single-channel assays provide full-rank active-parameter
sensitivities for all seven in-library worlds, with worst condition number about 6.9e3; mass is
conserved to 5.2e-15. Always-abstain scores zero. A truth-blind classical two-temperature fit
scores **0.481835/0.404269** development/held-out mechanism and **0.860429** development
interpolation, while falsely claiming an in-library mechanism in half of unsupported worlds.

GPT-5.5 budget one and an independent normal budget-three run remain at zero: their proposals
are valid, but use only one or two under-informative assays and abstain on every world. A strict
selection-blind budget-three batch with the same local identifier samples a nonzero policy:
offline best development/held-out mechanism is **0.342579/0.363296**, development support F1 is
**0.645292**, and false-discovery rates remain **0.5/0.5**. Another open-loop proposal reaches
**0.710894** development interpolation and **0.746865** extrapolation but only **0.258952**
normalized mechanism, giving a direct prediction-versus-mechanism/refusal counterexample.
Normal and open-loop use 16,104 and 15,826 tokens respectively; the endpoint provides no
server-side model seed. These single-run conditions are task calibration, not a causal feedback
estimate, population result or wet-lab discovery claim.
## 2026-07-22 — active gravity inversion v2

Rebuilt `Geophysics/GravityInversion` from two duplicate density grids whose signal RMS was only
0.033 times the declared noise into an active multi-height source-discovery laboratory. Seven
procedural signed rectangular-body topologies, null worlds and smooth seven-lobe out-of-library
fields are split across six development and five held-out worlds. The candidate spends a
24-unit budget on station positions and observation heights, then returns up to four bodies or
refuses the source family. Scoring is permutation invariant and compares individual external
field signatures plus signed mass and centroids rather than raw hidden pixels.

The analytic rectangular-body field agrees with independent 40-point Gauss-Legendre area
integration to **2.1e-13 mGal**. A fixed 18-unit multi-height design has full-rank local
sensitivity in all seven in-library worlds, with worst condition number **7.59e4**. In-library
signal-to-noise ratios range from **22.8 to 78.4**. A truth-blind multi-start BIC fit reaches
**0.785947/0.774867** development/held-out normalized mechanism and approximately **0.99**
sealed field prediction while correctly refusing both null and both resolvable misspecified
worlds. One development topology has only 0.226 body-mechanism quality despite 0.984 observed
fit, preserving a scientifically relevant external-field-versus-internal-geology gap. These are
synthetic task-calibration results, not field validation or autonomous geological discovery.

GPT-5.5 budget one generates a sophisticated parametric inversion but incorrectly treats the
documented callback dictionary as a positional tuple, producing a candidate protocol error and
no accepted improvement. An independent budget-three run uses the callback correctly and
reaches **0.993968** development mechanism in its first proposal, then **0.994226** at step
three. The final selected policy has **0.767267** held-out mechanism, **0.987813** held-out field
prediction and correct refusal in all unsupported worlds. On one held-out three-body topology,
field prediction is **0.975280** while body mechanism is only **0.345642**. The rejected step-two
candidate has slightly lower visible development score but higher held-out mechanism
**0.777301**, showing that visible selection and internal-geology transfer are not identical.
This near-one-step synthesis makes Gravity-v2 a valid on-ramp rather than a long-horizon
headline task; both model conditions are single runs and support no population claim.

## 2026-07-22 — active ocean-current inversion v2

Rebuilt `Oceanography/OceanCurrentInversion` from two duplicate, noise-dominated velocity
rasters into an active drifter laboratory. Candidates choose release positions, phases and
sampling times under a 12-unit budget, then return a sparse set of coefficients over thirty
public divergence-free, time-dependent streamfunction modes, confidence or an explicit refusal.
Six development and five held-out worlds include seven in-library currents, two null currents
and two smooth out-of-library currents. Mode support, velocity coefficients, vorticity, field
prediction and drifter prediction are scored separately, including extrapolation and shifted
held-out noise.

The public equations agree with an independent implementation, finite-difference divergence and
normal boundary flow are at numerical zero, and a finer-step RK4 check agrees within 0.0005 m.
All seven in-library trajectory Jacobians have rank 30/30 under the fixed public-budget design;
the worst condition number is 352. The weakest best-of-four-start bounded nonlinear fit of the
public mode library to an out-of-library trajectory has reduced chi-square **10.5279**, above the
refusal threshold 3.0, and all four starts agree within `4e-10`. Unsupported noise levels are a
subset of supported noise levels, so the declared noise metadata cannot identify the world
class. A truth-blind two-release sparse fit reaches **0.706751/0.405617** development/held-out
mechanism quality, claims a mechanism in all seven in-library worlds and correctly refuses all
four unsupported worlds.

### GPT-5.5 Ocean-v2 calibration

The independent budget-one proposal places an initial drifter outside the documented public
interior and fails closed. In the normal budget-three run, the first proposal is valid and uses
two releases plus the full 12-unit observation budget, but returns no modes for any world. It
therefore correctly refuses all four unsupported worlds while also refusing all seven
in-library worlds, giving zero in-library discovery coverage and zero mean in-library mechanism
recovery. The next two proposals incorrectly treat callback dictionary keys as numeric records
and fail closed. No normal proposal is accepted.

A same-local-seed-label strict `selection_blind` run keeps every proposal parent fixed at the
baseline. All three proposals misread the callback schema, so offline best also remains zero.
Normal and open-loop conditions use **16,594** and **16,175** tokens respectively. Azure exposes
no server-side model seed, and each condition contains one run; the equal terminal scores provide
no causal feedback estimate. The useful task-level observation is instead a decomposition: an
aggregate mechanism field can include credit for correct refusal even when supported-world
discovery coverage is zero. Future discovery reports must therefore pair mechanism quality and
false-discovery rate with in-library coverage or a risk–coverage curve.

The task calibration, inverse admission v4, certification v16, security v3 and all three model
reports bind clean source `6271434`. The dedicated analysis on clean source `49041fe` validates
report and raw-trajectory hashes, online and frozen-parent lineage, failure categories and the
classical/model discovery-coverage contrast. Certification v17 and the 23-condition cross-task
summary v5 bind clean source `0be15db`. These are controlled simulator calibrations, not field
oceanography, population model evidence or autonomous scientific discovery.

## 2026-07-22 — active thermal-infrared sounding and retrieval v2

Rebuilt `AtmosphericScience/RadiativeTransferFit` from a fixed ten-radiance/twenty-temperature
hidden-profile score into an active, budgeted atmospheric-mechanism task. Candidates select up
to four channel/view experiments over 24 thermal channels under 18 charged units, then return
four temperature-anomaly knots, one optical-depth scale, exact support, confidence or an explicit
refusal. Six development and five held-out worlds contain seven supported atmospheres, two null
atmospheres, an extra absorber and a cloud outside the public clear-sky family. Mechanism,
radiance prediction, viewing shift, confidence, false discovery, refusal and supported-world
coverage remain separately auditable.

The public recurrence agrees exactly with an independent implementation; the maximum isothermal
recurrence error is **1.39e-17**. A fixed public-budget two-view sounding has full-rank 18-by-5
sensitivity on all seven supported worlds, with worst scaled condition number **27.995**. Bounded
fits of the complete public family to clean absorber and cloud observations have reduced
chi-square **4.652** and **49.673**, both above the refusal threshold 3. A truth-blind nonlinear
fit reaches development/held-out mechanism **0.614395/0.490908**, radiance prediction
**0.854603/0.811647**, viewing-shift prediction **0.853833/0.809226**, full supported-world
coverage and zero false discovery. These are synthetic task-calibration results, not line-by-line
or satellite-retrieval validation.

### Candidate-exception feedback hardening

The pre-v2 audit found that the trusted driver could return a candidate-controlled exception
string as search-visible `error_message`. A malicious candidate could therefore embed callback
observations in an exception and carry them into a later proposal, bypassing the intended finite
metric allowlist. The driver now maps candidate failures to a fixed label-blind taxonomy such as
`candidate_callback_schema_error`, `invalid_return_artifact` or `candidate_runtime_error`; raw
candidate exception text is not returned. A dedicated regression embeds a sentinel in a candidate
exception and verifies its absence from the complete returned metrics. Security v4 records 18/18
passing tests. Historical reports remain immutable and are not promoted beyond their existing
calibration-only scope; future feedback-learning claims require this hardened protocol.

### GPT-5.5 Radiative-v2 calibration

The independent budget-one proposal is protocol-valid, uses two views and the full 18-unit
measurement budget, but returns the canonical refusal for every atmosphere. In an independent
normal budget-three run, all three proposals are valid; their mean per-world measurement use is
18, 0 and 18 units. A same-local-seed-label strict `selection_blind` run also has three valid
proposals, using 0, 18 and 18 units, with every parent fixed at the baseline. Across all seven
nonbaseline proposals, supported-world discovery coverage and mean supported mechanism recovery
are exactly zero, while unsupported-world correct refusal is one and false discovery is zero.
No proposal is accepted in any condition.

Normal and strict open-loop budget-three runs use **17,083** and **15,961** tokens and four oracle
calls each. The endpoint exposes no server-side sampling seed, normal never changes its incumbent,
and both terminal scores are zero. This provides no causal feedback estimate. The task-level
finding is instead a four-way separation: executable validity, measurement-budget use,
unsupported-world refusal and supported-world discovery coverage are distinct. Perfect refusal
and zero false discovery do not establish discovery when coverage is zero.

The task calibration, inverse admission v5, certification v18, security v4 and 51x2 baseline v10
bind clean source `bcccfc3`; all three model reports bind clean source `b09657e`. The dedicated
analysis on clean source `8e8bf9c` validates report/raw hashes, normal and frozen-parent lineage,
source-scope equivalence and every coverage/refusal decomposition. Certification v19 and the
25-condition, 13-task cross-task summary v6 bind clean source `b1e081c`. The current portfolio is
seven certified, eighteen candidate and twenty-six quarantined packages: **25 internally
admissible tasks**, leaving an approximate gap of 25 to the portfolio target.

## 2026-07-22 — low-thrust orbital-transfer optimization v2

Rebuilt `Astrodynamics/LowThrustTransfer` from one unstable 30-day Cartesian Euler trajectory,
silent thrust clipping and unsupported fuel anchors into six orbit-raising, lowering,
eccentricity, plane-change and combined transfers. Candidates return four-segment harmonic RTN
guidance with 28 coefficients. The trusted evaluator propagates modified equinoctial elements
with Earth J2 and rocket-equation mass depletion, analytically checks the continuous all-
longitude thrust bound, and separately retains nominal utility, terminal feasibility, phase,
two held-out missions and three sealed thrust/ISP/J2/pointing/navigation/cutoff shifts. Candidate
processes restart at every mission boundary.

A public-input-only Gauss--Newton policy reaches development/held-out utility
**0.711433/0.719404**, sealed robustness **0.681712/0.659987**, and nominal feasibility **1/1**
on both splits. A separate reachability witness reaches **0.734751/0.715759** nominal and
**0.704309/0.668409** robust utility. The zero-thrust coast baseline remains valid but scores
zero with zero terminal feasibility. Wrong-shape, non-finite, coefficient-bound and continuous-
thrust-bound violations all fail closed.

The 1800 s production RK4 propagation differs from a 900 s refinement by at most **0.042274**
of a public terminal tolerance. The refined MEE propagation differs from an independently coded
Cartesian DOP853 path by at most **0.002876** tolerances and **0.000222 kg**. These checks bound
production discretization and coordinate/formulation disagreement separately; they are not
flight validation. The task still omits third bodies, drag, eclipse, power, thermal and attitude
constraints and needs server-held missions plus independent mission-tool/domain review.

`low_thrust_v2_calibration_2026-07-22.json` binds clean source `43dd780`. Wave-2 admission v3,
certification v20, security v5 and the 51x2 baseline v11 bind clean source `5bf6e0c` and record
seven certified, nineteen candidate and twenty-five quarantined packages. The resulting **26
internally admissible tasks** leave an approximate gap of 24 to the portfolio target. GPT-5.5
headroom calibration is still pending, so none of these results is a model-performance,
feedback-learning, global-optimality or autonomous-discovery claim.

### GPT-5.5 LowThrust-v2 calibration

The independent budget-one proposal is a valid bounded guidance artifact and improves
development utility from zero to **0.007736**, but held-out utility is only **5.78e-9**. It
spends mean development/held-out delta-v **737/833 m/s**, yet none of the six nominal missions or
eighteen shifted cases enters its terminal tolerance set.

In the independent normal budget-three run, the first proposal scores **0.005079** and is the
only accepted update. Two rewrites score **0.004750** and **2.14e-6**. The selected policy has
held-out utility **1.34e-11** and development/held-out robustness **0.003580/3.33e-12**; all
three proposals remain nominally and shift terminal-infeasible. Scalar score feedback therefore
does not localize the long-horizon boundary-value error in this one trajectory.

A same-local-seed-label strict `selection_blind` run keeps all three proposal parents fixed at
the baseline and selects an offline best of **0.005491**, slightly above normal. It too has zero
nominal and shifted feasibility. Normal uses **18,491** tokens versus **13,366** open-loop, both
use four oracle calls, and Azure exposes no server-side sampling seed. The difference is neither
paired nor token-matched and supports no causal feedback conclusion.

Across all seven nonbaseline proposals, executable artifact validity is **7/7** while nominal
terminal-feasible proposal count and shift-feasible proposal count are both **0/7**. The maximum
held-out score is only **5.78e-9**, despite a public-input Gauss--Newton policy reaching
0.711/0.719 development/held-out utility with full nominal feasibility. Budget-one also has a
sealed phase diagnostic nearly equal to the Gauss--Newton policy, even though it misses every
first-five-MEE terminal tolerance. Phase, valid code, nonzero delta-v and graded utility are thus
not substitutes for terminal-state validity or held-out transfer.

All three model reports bind clean source `ba07529`. The dedicated analysis on clean source
`7852a85` verifies report/raw hashes, online/frozen-parent lineage, source-scope equivalence and
the numerical/utility/feasibility/phase/held-out/robustness decomposition. The 27-condition,
14-task cross-task summary v7 and certification v21 bind clean source `71bb7d7`; security v6 and
the 51x2 baseline v12 bind clean source `a3de314`. The full suite now passes **139/139** tests.
These are controlled single-run calibrations, not population model performance, feedback
learning, global optimality, flight validation or autonomous scientific discovery.

## 2026-07-22 — full-field lid-driven-cavity solver v2

Rebuilt `FluidDynamics/LidDrivenCavity` from one Re=100 sparse-centerline comparison into six
steady laminar Reynolds/grid cases and two refinement calls. Candidates return complete
streamfunction and vorticity fields. Trusted code derives velocity and separately checks the
Poisson equation, vorticity transport, Thom wall vorticity, held-out Reynolds transfer, grid
refinement and corrected Ghia Re=100 profiles. Each of the eight candidate calls receives a fresh
process and private temporary filesystem.

The weak zero-interior-flow baseline is valid but has zero score and zero physics feasibility.
The Newton--Krylov continuation reference scores **0.999999998** on development,
**0.999999991** on held-out Reynolds cases, **0.999999997** on development refinement and
**0.999999996** on held-out refinement. Independent equation checks reproduce the oracle
relative residuals exactly; discrete divergence is below `4e-15`. Ghia horizontal/vertical
centerline RMSE is **0.009789/0.012070**. A nonphysical stripe injection scores zero. A 95%
attenuated near-reference field has ungated development utility **0.857026**, but the hard
physics gate reduces its public score to zero because transport feasibility fails.

The independent GPT-5.5 budget-one proposal implements a DST Poisson solve, continuation and
Krylov polish and reaches **0.999999990**. Its held-out and refinement scores are also above
0.99999995. In a separate normal budget-three run, all three proposals are accepted and score
**0.869915 → 0.894913 → 0.898062**. A strict open-loop batch with the same local seed label keeps
every parent fixed at the baseline and produces a **0.999999990** solver at step two.
Normal and open-loop use four oracle calls and **19,483/14,288** tokens. The endpoint exposes no
server-side seed, so the open-loop advantage is neither paired nor a causal feedback estimate.

Three post-hoc combinations absent from the benchmark calls, `(Re,N)=(137,27),(245,39),(375,45)`,
were evaluated after the runs. The budget-one and open-loop programs pass every physics gate and
retain minimum full-field similarity **0.999999951** against the same discrete reference. The
normal selected program also passes all nine public probe gates, with minimum similarity
**0.844965**. Because these probes were selected post hoc and use the same second-order model,
they diagnose general solver behavior but do not provide preregistered hidden, high-order or
experimental validation.

The task and wave-2 v4 calibration bind clean source `678e79a`. Certification v22 records
**7 certified / 20 candidate / 24 quarantined**; security v7 passes **18/18**, and the 51x2
baseline v13 records **51 deterministic, 50 valid, 51 fail-closed and zero infrastructure
failures**, all on the same revision. The three model reports also bind `678e79a`. Their dedicated
analysis on clean source `5f63176` verifies report/raw hashes, online and frozen-parent lineage,
sealed metrics and post-hoc probe results. The full suite passes **147/147** tests. The one-step
and open-loop ceiling make this a CFD algorithm synthesis on-ramp, not evidence of feedback
learning, continuum CFD validity, a new flow mechanism or autonomous scientific discovery.

## 2026-07-22 — active climate-response identification v2

Rebuilt `ClimateScience/EnergyBalanceModel` from the quarantined unstable explicit-diffusion
implementation into a five-parameter two-layer energy-balance identification task. Candidates
choose one 160-year forcing experiment or several shorter experiments under eight charged units,
observe surface temperature and top-of-atmosphere imbalance, then return response parameters,
confidence and a public-model claim or explicit refusal. Six development and five held-out
worlds contain seven supported two-layer climates, two null responses, state-dependent feedback
and an additional deep-ocean reservoir.

The public recurrence agrees with independent RK4 and matrix-exponential implementations. A
fixed long multiscale forcing design has rank-five sensitivity in all seven supported worlds,
with scaled condition numbers from **11.47 to 17.65**. Fits of the public family to all four
unsupported worlds exceed the refusal threshold by the required margin under the benchmark
noise model. The truth-blind long-design fit reaches development/held-out mechanism
**0.808913/0.941773**, prediction **0.998981/0.999242**, full supported claim coverage and zero
false discovery. By contrast, a short under-informative design reaches prediction
**0.9676/0.9897** but mechanism only **0.003909/0.0**, and falsely promotes one misspecified
world in each split. Accurate response interpolation is therefore not sufficient evidence of
parameter recovery or model-class validity.

### GPT-5.5 Climate-v2 calibration

The independent budget-one proposal and all three independent normal budget-three proposals
fail the documented return-artifact contract and remain at zero; this is a model protocol
failure, not an infrastructure failure. A same-local-seed-label strict `selection_blind` batch
keeps every parent fixed at the baseline and finds a valid proposal at step three. Its
development/held-out mechanism is **0.617931/0.282383**, while prediction is
**0.976686/0.994285** and supported-world coverage is one. Unsupported-world refusal is only
0.5 on both splits, with false-discovery rates **0.20/0.25** and high-confidence false public-
model claims for state-dependent feedback and the third ocean layer.

Normal and strict open-loop budget-three runs use **14,181/15,297** tokens and four oracle calls.
The endpoint exposes no server-side generation seed, the conditions are not token matched, and
normal never accepts a valid proposal. Their `0.000/0.618` contrast therefore supports no causal
feedback conclusion.

Twelve procedural worlds selected only after the model runs contain six supported, two null,
two feedback-drift and two three-layer cases. The selected open-loop program is valid on all
twelve. Supported prediction remains **0.994882**, but supported mechanism averages
**0.370445** and falls as low as **0.075278**. It refuses both nulls yet makes high-confidence
false claims in all four feedback-drift/three-layer worlds, for unsupported false discovery
**2/3**. These are post-hoc transfer probes using the same synthetic family, not preregistered
hidden tests, independent GCM validation or observations.

The task rebuild, task calibration, certification v23, security v8 and 51x2 baseline v14 bind
clean source `1755ff0`; the three model reports bind clean source `51246d5`. The dedicated
analysis on clean source `28a63d0` validates task/model report and raw-trajectory hashes, online
and frozen-parent lineage, source-scope equivalence, fixed-world decomposition and all post-hoc
probe records. Certification v23 records **7 certified / 21 candidate / 23 quarantined**;
security v8 passes **18/18**, baseline v14 records **51/51 deterministic, valid and fail-closed**
with zero infrastructure failures, and the full suite passes **157/157** tests.

The portable cross-task summary v9 was generated from clean source `1541116` and freezes **31
normal single-run conditions over 16 tasks**. Strict open-loop diagnostics remain task-specific.
The portfolio now contains **28 internally admissible tasks**, leaving an approximate gap of 22
to the roughly 50-task target. These results are synthetic single-run calibrations, not an
estimate of Earth's climate sensitivity, population model performance, feedback learning or
autonomous scientific discovery.

## 2026-07-23 — robust broadband acoustic absorber v2

Rebuilt `AcousticMetamaterials/BroadbandAbsorber` as a six-instance, variable-policy design
task spanning 6--10 Helmholtz cells, 180--1800 Hz bands and 65--120 mm panel envelopes. The
nominal oracle uses Stinson circular-tube dynamic density, finite rigid cavities, radiation
resistance and parallel surface admittance. A low-frequency lumped public proxy is reported
separately. Five sealed shifts cover incidence angle, warm/light and cold/dense air, two
manufacturing patterns and a combined operating/manufacturing condition.

The weak baseline exact utility is **0.079323/0.067049** on development/held-out instances.
Fixed-seed nominal references reach normalized **1.0/1.0** and robustness
**0.989789/0.939664**; robust references reach nominal **0.993517/0.987409** and robustness
**1.0/1.0**. An independent scalar complex-valued implementation agrees with the production
absorption model to roughly `4e-15` and impedance to `1.2e-14`; all checked impedances are
passive. The public proxy undershoots the distributed reference utility by roughly 0.34--0.59.

### GPT-5.5 absorber calibration

The budget-one proposal times out and leaves the zero-score baseline unchanged. In the
independent normal budget-three run, step one reaches nominal development/held-out
**0.914758/0.858789**, exact utility **0.467799/0.447581**, and sealed robustness
**0.911826/0.858329**. Both later rewrites use the selected incumbent as parent but time out.

In the same-local-seed-label strict open-loop run, all proposal parents remain the frozen
baseline. Offline step two reaches nominal **0.917261/0.957363**, but sealed robustness is only
**0.451869/0.449052**. Its nominal artifact is valid, yet one manufacturing pattern leaves the
hard panel envelope on two development instances and one held-out instance; manufacturing
geometry feasibility is **0.75/0.75**, versus **1.0/1.0** for the normal selected artifact.
Normal/open-loop use the same four oracle calls but **24,179/15,152** tokens. Azure exposes no
server-side generation seed, so the contrast is descriptive and supports no causal feedback
claim.

The task calibration and v24/v9/v15 audits bind clean source `befd90a`; the three model reports
bind clean source `3e4333a`. The dedicated analysis on clean source `9a3fc27` verifies
report/raw hashes, incumbent/frozen-parent lineage, selected artifacts, source scope and
LLM-condition identity. Certification v24 records **7/22/22**, security v9
passes **18/18**, baseline v15 records **51/51 deterministic, valid and fail-closed** with zero
infrastructure failures, and the full suite passes **167/167** tests. Cross-task summary v10
freezes **33 normal single-run conditions over 17 tasks**. The portfolio contains **29**
internally admissible tasks, leaving an approximate gap of **21** to the roughly 50-task target.
These are reduced-order, single-run calibrations, not thermoviscous/experimental validation,
population performance, feedback learning or autonomous scientific discovery.

## 2026-07-23 — robust equilibrium-stage distillation v2

Rebuilt `ChemicalProcess/DistillationColumnDesign` from a fixed-0.99-purity toy into a policy
task over six binary separations. The artifact jointly selects integer tray count and feed
stage, reflux ratio, distillate fraction and a feed-forward split gain. The deterministic
constant-relative-volatility/constant-molar-overflow oracle explicitly closes the total
condenser return, every rectifying/stripping tray, the feed stage, the partial reboiler and the
overall feed-product component balance. Product purity and light/heavy recovery remain hard
constraints rather than requested values assigned by the simulator.

Four development and two interleaved held-out regimes cover close-boiling, high-purity, rich,
lean and partly vaporized feeds. Five sealed conditions vary relative volatility, feed
composition, feed liquid fraction, available reflux and a combined operating shift. Nominal
development cost alone controls proposal selection; shift failures are isolated from nominal
validity and all held-out, per-instance and robustness diagnostics remain sealed.

The conservative maximum-stage/high-reflux policy is feasible in every nominal and shifted
condition. Fixed-seed nominal witnesses use 12--17 trays and cost **35--47%** of baseline, but
their sealed shift-feasibility rate is only **0.20/0.10** on development/held-out instances.
Robust witnesses use 12--21 trays, cost **37--52%** of baseline and retain all five shifts,
scoring nominal **0.963386/0.902777** and robustness **1.0/1.0**. A separate bounded
least-squares MESH implementation reproduces all nominal/robust reference conditions with
maximum product-composition discrepancy about `1.1e-11`; analytic tridiagonal Jacobians also
match finite differences at the top-feed boundary. Malformed, non-finite, boolean,
non-integral and out-of-range artifacts fail closed, and sandbox tests verify a fresh process,
imports and tmpfs for all six candidate calls.

Clean-source `distillation_v2_calibration_2026-07-23.json` reproduces all twelve fixed-seed
reference searches and passes every equation, reference, invalid-artifact and difficulty gate
on revision `469224c`. Wave-4 v3 records two resolved rebuilds and ten retained quarantines;
certification v25 records **7/23/21** with no missing/orphaned records or task issues; security
v10 passes **18/18**; and baseline v16 records **51/51 deterministic, valid and fail-closed**
with zero infrastructure failures. Re-admission yields **30** internally
admissible tasks and an approximate gap of **20** to the roughly 50-task target. This is
reduced-order task calibration, not a global-optimality proof, rate-based process simulation,
pilot-column/plant validation, model-population estimate or autonomous-discovery result.

### GPT-5.5 distillation calibration

The independent budget-one proposal times out after generating a large numerical search and
leaves the valid zero-score baseline unchanged. In the normal budget-three run, steps one and
three time out; step two is valid and accepted, raising development nominal score to
**0.613090** with held-out nominal **0.540692** and full nominal feasibility. Its mean nominal
cost falls from about **2.116M/2.488M** to **1.314M/1.776M** on development/held-out regimes.
However, only the richer-feed condition remains feasible on each instance: sealed shift
feasibility is **0.20/0.20** and robustness is **0.0/0.0**. The valid policy installs minimum
or near-minimum tray counts at high reflux and operates close to purity/recovery limits.

All three strict-open-loop proposals from the frozen baseline time out and score zero. Normal
and selection-blind use the same four oracle calls and local seed label 1, but consume
**21,738/17,926** tokens. The Azure endpoint exposes no server-side seed; this one-run,
non-token-matched contrast supports no causal feedback conclusion. Across budget one and both
budget-three conditions, exactly one of seven proposals is valid and six time out.

The selected program's internal cost routine does not read the public
`annualized_cost_per_tray` or `annualized_cost_per_vapour_flow` fields. A post-hoc sandboxed
counterfactual therefore changes the public cost regime from capital-heavy/energy-light to
capital-light/energy-heavy without changing its 8-stage/high-reflux artifact. Against the same
feasible 13-stage/low-reflux witness, its cost advantage changes from **-0.889M** to a
**+1.536M** disadvantage. The nominal score is valid under the benchmark instances, but this
probe shows that the program did not learn the intended capital--energy tradeoff mechanism.

The three model reports bind clean source `c76767c`; the dedicated analysis on clean source
`964ac5a` verifies report/raw-trajectory hashes, online/frozen-parent lineage, selected-program
hashes, sealed nominal/robust axes and the explicitly post-hoc cost probe. Cross-task summary
v11 and certification v26 bind clean source `f9176df`: **35 normal single-run conditions over
18 tasks** and a **7/23/21** manifest. These are single-run reduced-order calibrations, not
population performance, causal feedback learning, global optimality, plant design or
autonomous scientific discovery.

## 2026-07-23 — stable multi-system Hartree--Fock SCF v2

Replaced the quarantined two-coefficient H2 toy, whose hand-entered integral tensor made the
documented baseline the complete grid minimum and its `-1.1167 Ha` anchor unreachable, with a
finite-basis restricted closed-shell SCF policy task. Four development and three interleaved
held-out systems span H2/HeH+ 6-31G, stretched LiH/H2O, an H6 chain, a symmetry-breaking H8 ring
and a different-size held-out H4 ring. The artifact is an overlap-orthonormal occupied-orbital
matrix; the trusted evaluator reconstructs density, Coulomb/exchange, RHF energy, electron
count, idempotency and the Roothaan--Hall commutator.

The weak policy is a conventional single core-Hamiltonian start with Pulay DIIS. It is valid and
defines task score zero, but converges to internally unstable stationary points on H8 and H4:
their fixed-seed stable multistart witnesses lie **0.037516** and **0.061933 Ha** lower, and the
minimum occupied--virtual curvatures change from **-0.294/-0.511** to **+0.299/+0.095**. Mean
development stability therefore rises from **0.75** to **1.0** and held-out stability from
**2/3** to **1.0**. Reference nominal/robustness scores exceed 0.999 on development and 0.998 on
held-out systems.

Sealed checks use 3% molecular contractions/expansions with freshly generated overlap,
one-electron, two-electron and nuclear-repulsion integrals, plus AO permutations and dense
well-conditioned basis transformations. They never alter nominal validity or search selection.
An independent NumPy/SciPy implementation reproduces all nominal/shifted stored energies within
`4.3e-14 Ha`; malformed, non-finite, complex, nonorthonormal and nonstationary nominal artifacts
fail closed. Every one of the 28 problem/validation calls receives a fresh sandbox session. The
offline PySCF 2.6.2 generator is byte reproducible: two independent generation passes produce
SHA-256 `230fa7bf2ee359dcdcc9f06e62629f5f827d14f5331e5359dd8903f8e21d7bd5`.

Clean-source task calibration, wave-4 admission v4, certification v27, security v11 and 51x2
baseline v17 bind revision `40931fb`. The full suite passes **186/186** tests. Re-admission yields
**7 certified / 24 candidate / 20 quarantined**, or **31** internally admissible tasks, leaving
an approximate gap of **19** to the roughly 50-task target. The task is finite-basis numerical
RHF optimization, not correlated electronic structure, global-minimum proof or chemistry
discovery; server-held procedural molecules and independent domain review remain pending.

### GPT-5.5 Hartree--Fock calibration and material-selection audit

Three independent clean-source reports on revision `746dff0` complete the initial GPT-5.5
calibration. Budget one produces a valid deterministic multistart/stability solver with
development and held-out nominal/robust scores approximately one in **5,272 tokens** and
**103.3 s**. This is a one-proposal synthesis of a known numerical strategy, not feedback
learning or new chemistry. The strict selection-blind budget-three run keeps every proposal
parent fixed at the baseline and obtains an offline-best score approximately one at step two;
feedback is therefore not shown necessary by this calibration.

The normal budget-three trajectory has one fail-closed infrastructure error followed by two
valid accepted proposals. Step two reaches selection score `0.9999999999998133`, development
robustness approximately 1.0 and held-out robustness 0.902. Step three gains only
`9.10e-15` selection score, while development robustness falls to 0.707 and held-out robustness
rises to approximately 1.0. Development/held-out representation invariance similarly move by
-0.125/+0.167. A post-run endpoint replay with selection epsilon `1e-12` retains step two;
neither artifact Pareto-dominates the other. This demonstrates an acceptance/commit-policy
failure, not a feedback-effect estimate. Normal/blind use the same four oracle calls but
20,281/17,159 tokens and 454.7/262.6 seconds; Azure exposes no server-side generation seed.

The v2 calibration on clean source `399ebf2` additionally compares every scalar/sealed baseline
axis between the secure runner and an explicit one-thread direct execution; all registered
tolerances pass. It records a real BLAS-thread basin sensitivity: held-out shifted score is
approximately **0.667** at one thread but approximately **1.0** at 2/4/8 threads. The secure
runner's fixed one-thread environment is authoritative. The earlier calibration report remains
historical evidence of the narrower nominal-only gate and is not overwritten.

The dedicated derived analysis binds all three report hashes, raw-trajectory hashes,
normal/frozen-parent lineage, final program hashes, v2 task calibration, science axes and the
materiality replay. It explicitly supports no causal, population, scaling, chemistry-discovery
or real-world scientific-discovery claim.

Cross-task summary v12 on clean source `f26bb16` validates and freezes **37** normal single-run
conditions across **19** tasks, adding Hartree--Fock budgets one and three. Strict open-loop and
materiality diagnostics remain in the task-specific analysis; heterogeneous science axes are
not averaged into one score.

## 2026-07-23 — room acoustics placement and treatment optimization v2

Rebuilt `Acoustics/RoomImpulseResponse` from fixed target-RIR reconstruction into an open policy
task over four development and two interleaved held-out rooms. The artifact chooses a three-
dimensional source position and treatment area on each of six room surfaces. The nominal oracle
uses an order-10 energy image-source model together with Eyring reverberation time; it separately
scores clarity, target reverberation time, receiver-field uniformity, material cost and geometry.
Sealed evaluation covers installation error, audience-position changes, geometry/sound-speed
shift, material ageing and a combined order-14 condition. A first-order public proxy remains
separate from exact nominal and robust utility.

Independent wall-reflection counts, path energies, surface absorption and reverberation-time
equations reproduce the production oracle. A deterministic public-input search recalibrates the
nominal reference family with maximum residual development gap **4.40e-4**. Malformed, non-finite,
out-of-range and geometry-infeasible artifacts fail closed. The clean v2 task calibration binds
revision `4bd362e`; wave-2 admission v6 re-admits the task, certification v29 records
**7 certified / 25 candidate / 19 quarantined**, security v13 passes **18/18**, and baseline v19
records **51/51 deterministic, valid and fail-closed** with zero infrastructure failures.

### GPT-5.5 room-acoustics calibration

At budget one, the selected development score remains zero. The single proposal is valid but
lowers development nominal utility from **0.608060** to **0.581330**, so online development
selection rejects it; the same proposal improves held-out utility from **0.668935** to
**0.699032** and reaches held-out normalized score **0.419181**. This is one example of a
development/transfer rank reversal, not a population conclusion.

In the independent normal budget-three run, all three proposals access nonexistent absorption
keys and fail closed with `candidate_runtime_error`; the valid baseline remains selected. A
same-local-seed-label strict selection-blind batch keeps every parent frozen at the baseline.
Its step-two artifact reaches development score **0.116213**, and step three reaches development
**0.753684**, held-out nominal **0.742208**, development robustness **0.639263** and held-out
robustness **0.803334**. Normal and open-loop conditions use four oracle calls and
**16,592/16,676** tokens with **167.3/173.8 s** wall time, but Azure exposes no server-side
generation seed. These single-run conditions therefore do not show that feedback hurts or that
open-loop sampling is generally superior.

The dedicated derived analysis on clean revision `8ec7ecf` binds task/model report hashes, all
three raw trajectories, online/frozen-parent lineage, selected artifacts, source equivalence and
every nominal, held-out, proxy and robustness axis. This is reduced-order image-source/Eyring
task calibration, not measured-room validation, causal feedback evidence, population capability
or autonomous acoustic discovery. Server-held rooms, hybrid wave/ray or measured-RIR replication
and independent acoustics review remain required.

Cross-task summary v13 on clean source `6489a07` validates and freezes **39 normal single-run
conditions across 20 tasks**, adding RoomImpulseResponse-v2 budgets one and three. Strict open-
loop diagnostics remain task-specific; heterogeneous science axes are not averaged into one
score.

## 2026-07-23 — convection--diffusion active laboratory calibration

ConvectionDiffusionOpt-v2 is now bound to clean source `84fcbe8`. The task contains six
development and five held-out homogeneous/null/spatially heterogeneous apparatuses, five hidden
anisotropic transport/loss coefficients, a 12-unit heater/sensor experiment budget, four-source
target-field design and four sealed physical shifts. A truth-blind complementary two-experiment
policy reaches development/held-out joint quality **0.895605/0.891509**, mechanism
**0.649464/0.659574** and shifted robustness **0.893876/0.890417**, with zero false discovery.
The symmetric one-experiment policy is numerically rank five but has condition numbers from
**1.0e5 to 4.0e8** and scores approximately zero.

Certification v30 records **7 certified / 26 candidate / 18 quarantined**, wave-4 admission v5
records four substantive rebuilds, security v14 passes **18/18**, and secure baseline v20 records
**51/51 deterministic, valid and fail-closed** over two repetitions with zero infrastructure
failures.

### GPT-5.5 convection--diffusion calibration

The independent budget-one proposal makes an invalid experiment request. In the normal
budget-three run, two proposals fail at runtime and the only valid proposal spends four units
then abstains on all eleven worlds. The same-local-seed-label strict open-loop batch has one
runtime failure and two valid proposals; one spends the full 12 units on two experiments, but
both abstain on every supported and unsupported world. Consequently all conditions select the
zero baseline, supported discovery coverage is zero, and correct unsupported refusal is one.

Normal/open-loop use four oracle calls and **16,833/16,982** tokens. Azure exposes no server-side
generation seed, no condition changes its incumbent, and each condition has one run, so the equal
zero score contains no feedback-effect estimate. The clean derived analysis on `fa8bcfe` binds
all three reports, raw trajectories, frozen/online lineage, selected artifacts, experiment usage
and every mechanism/prediction/design/robustness/refusal axis. This is finite-difference task
calibration, not physical heat-transfer validation or autonomous scientific discovery.

Cross-task summary v14 on clean source `fa8bcfe` validates and freezes **41 normal single-run
conditions across 21 tasks**, adding ConvectionDiffusionOpt-v2 budgets one and three. Strict
open-loop diagnostics remain task-specific and heterogeneous science axes are not averaged into
one score.

## 2026-07-23 — post-findings clean-revision audit refresh

After recording the ConvectionDiffusionOpt-v2 derived analysis and cross-task findings, clean
source `e10da7d` was independently re-audited. Certification v31 retains **7 certified / 26
candidate / 18 quarantined** across all 51 packages with no missing or orphaned manifest records;
security v15 passes **18/18** adversarial regressions; and secure baseline v21 records **51/51
deterministic, 51/51 valid and 51/51 fail-closed** over two repetitions with zero infrastructure
failures. These reports refresh provenance only; they do not add model-performance or discovery
evidence.

## 2026-07-24 — active layered reflection-wave inversion rebuild

SeismicWaveInversion-v2 replaces an evidence-free fixed velocity-model guess with a charged
active acquisition laboratory. Candidates choose CMP positions, source--receiver offsets and
Ricker peak frequencies under a 12-unit budget, then return nine interpretable interval-velocity
and quadratic-interface parameters or explicitly abstain. Six development and five held-out
worlds include supported three-layer media, null responses and resolvable four-layer
low-velocity-zone misspecification. Acquired-waveform fit, evaluator-only waveform prediction,
far-offset transfer, parameter recovery, experiment information, confidence and refusal remain
separate.

The clean-revision calibration on `f8c59dd` independently reproduces the exact public
Snell-ray/Ricker forward model at general CMP/offset/frequency points to maximum absolute error
`1.11e-16`. A truth-blind NMO/Dix initialization plus public-waveform fit reaches
development/held-out joint quality **0.997697/0.994382** and far-offset robustness
**0.998615/0.996791**, with full supported-world coverage and zero false discovery. All seven
supported reference acquisitions have rank nine with worst condition number **246.34**; a
centered narrow-offset design has rank five and zero information score on every supported world.
Best public-model reduced chi-square is **78.06/33.10** on development/held-out misspecified
worlds, so the classical policy refuses both.

This near-ceiling classical witness makes the current task an active-acquisition and model-checking
on-ramp, not a long-horizon headline task. The primary-reflection ray laboratory omits elastic
conversion, attenuation, anisotropy, multiples, source uncertainty, topography and field noise;
it supports neither field-FWI nor autonomous geological-discovery claims.

The full clean-source regression passes **222/222** tests. Inverse-track admission v6 passes all
seven checks and records five repaired candidates plus two remaining quarantines. Certification
v32 records **7 certified / 27 candidate / 17 quarantined** across 51 packages with no task or
manifest issues. Security v16 passes **18/18**, and secure baseline v22 records **51/51**
deterministic, valid and fail-closed tasks over two repetitions with zero infrastructure failures.

### GPT-5.5 seismic-wave calibration and contract diagnostic

The public task contract now states that `acquire()` returns a dictionary. Three earlier reports
from source `2ae6725` predate that statement; four proposals try to unpack that dictionary as a
tuple and fail with `candidate_callback_schema_error`. They are retained as
**superseded underspecified-contract diagnostics**, not counted as current-contract model
performance.

On clean source `e59e7bb`, the formal budget-one, normal budget-three and strict open-loop
budget-three conditions contain seven nonbaseline proposals: **six valid and one timeout**. Five
valid proposals abstain on all seven supported worlds. The budget-one proposal alone makes a
claim, covering no development supported world and one of three held-out supported worlds, with
held-out joint score **0.1020**. All valid proposals have zero false discovery. The three strict
open-loop proposals achieve experiment-information **0.974--1.000** yet mechanism score zero;
normal budget-three also has two full-budget/high-information valid abstentions. This directly
separates experiment geometry/information from inference, supported discovery coverage and
refusal. A scalar score of zero cannot distinguish those abstentions from the timeout.

Normal/open-loop use four oracle calls and **16,749/17,007** tokens, take **1386.45/858.11 s**,
share only a local seed label, and have no server-side generation seed. Neither condition changes
its incumbent, so the equal-zero contrast contains no feedback-effect estimate. These are
single-run synthetic ray-theory calibrations, not population, field-FWI, geological or autonomous
discovery evidence.

## 2026-07-24 — EdgeBench long-horizon protocol review

We cross-checked the ByteDance Seed EdgeBench v1 paper (arXiv:2607.05155, 2026-07-06),
its public dataset card and 51 released task descriptors. The transferable protocol is the dual
feedback loop, hidden fixed-interval trajectory snapshots, three independent long-horizon runs,
continuous-experience versus equal-budget restart controls, first-attempt/gain separation and
adaptive-evaluator attack audit. Its 134-task aggregate log-sigmoid is explicitly a population
phenomenon, not a universal single-task law.

Frontier-Science therefore adds a science-specific protocol rather than copying the scalar
leaderboard: each snapshot retains optimization, fidelity, mechanism, experiment information,
validity, refusal, supported coverage, uncertainty and cost axes; sealed transfer is followed by
one-shot independent confirmation; null/model-mismatch worlds and false-discovery/over-refusal
are mandatory; stochastic artifacts are re-evaluated on hidden seeds; and agent-caused invalid
runs remain in failure-inclusive estimates. The detailed, source-checked experiment list and
phased TODO are in `docs/edgebench_science_experiment_addendum.md`.

## 2026-07-24 — post-analysis clean-revision audit refresh

On clean source `2706281`, the Seismic derived analyzer binds all formal and superseded reports,
raw trajectories, parent/candidate hashes and selected artifacts; cross-task summary v15 binds
**43 normal single-run conditions across 22 tasks**. The complete suite passes **227/227** tests.
Inverse-track admission v7 passes all seven checks and retains five candidates/two quarantines;
certification v33 remains **7 certified / 27 candidate / 17 quarantined**; security v17 passes
**18/18**; and secure baseline v23 records **51/51 deterministic, 51/51 valid and 51/51
fail-closed**, with zero infrastructure failures. These refresh provenance and close the Seismic
evidence loop; they do not turn synthetic calibration into field or discovery evidence.

## 2026-07-24 — EdgeBench implementation and science-task second pass

We checked the full EdgeBench v1 paper and appendices against public SForge commit
`a87350ab80eeb320b13cb71d1b0c3ffcc20a670f`, the official Codex experiment configuration and
the four publicly released Science/ML contracts. This second pass adds science-specific controls
that the first protocol review did not make explicit: declared/terminal artifacts must remain
separate from an evaluator-only historical-best envelope; continuous experience must be split
into artifact, observation-ledger, scientific-notebook and context retention; non-improving
experiments can still refute hypotheses; fixed-interval snapshots require immutable atomic
publishing and event-time accounting; and scaling-law fits require held-out-task, transformation,
selection and independent-restart-null sensitivity analyses. Repeated feedback also requires a
sequential false-discovery study and a one-shot confirmation rule.

The public 51-task manifest contains only four Science/ML tasks, while the private/full suite is
reported to contain 39. The public contracts are useful protocol examples but span inversion,
method replication, stochastic policy optimization and generic ML engineering; their category
label alone is not sufficient admission evidence for a roughly 50-task Frontier-Science
inventory. The updated addendum therefore separates scientific optimization, mechanism/discovery
and replication tracks and adds a task-maturity ledger.

The batch runner now preserves both valid-only quality and intent-to-evaluate reliability.
Conditions with no valid terminal run remain visible; scheduled/completed counts and completion
rates are reported; failed retry attempts and recovered cells no longer disappear when the latest
attempt succeeds. This is an accounting improvement, not a new model-performance result. It does
not yet implement evaluator-only wall-clock snapshots or declared-artifact confirmation.

## 2026-07-24 — EdgeBench full taxonomy and task-construction audit

We rechecked arXiv:2607.05155v1 against the official arXiv API, PDF, source package, public
SForge commit `a87350ab80eeb320b13cb71d1b0c3ffcc20a670f` and Hugging Face revision
`47846a4c3669ad447e0ea984833b0d352460c5f9`. The API remains v1; GitHub and the dataset remain at
those revisions. The source package SHA-256 is
`8193aeb41a3474690a40fac82e2ecbd53e651ab6b4759984b4c6845c04fbfd29`.

The fifth pass audited all 39 Science/ML task design notes and the full per-task score table. It
adds three task-design requirements for Frontier-Science: at least one linked data-QC → inference
→ monitoring/experiment-design → intervention campaign with typed, uncertainty-bearing handoffs;
fresh-world replay of an executable scientific method rather than scoring only a frozen answer;
and a measurement-health gate before assigning long horizons, covering first-valid rate,
baseline/reference separation, fixed-artifact judge noise, floor/ceiling mass, material post-2h
headroom and shortcut resistance. Campaign stages share one statistical lineage, and stage-swap
counterfactuals attribute final decision utility.

The source also exposes a reproducibility warning that was not visible from category totals alone.
`task_by_task_specifications.tex` assigns the 134 tasks as `36/39/19/13/19/8`, while
`category_score_tables.tex` assigns the same IDs as `35/34/16/13/24/12`; eleven tasks move family.
Five Science/ML specification tasks move into Systems, Optimization or Knowledge Work in the
score tables. The mean of the 34 displayed one-decimal Opus rows is `48.494...`, which rounds to
the reported Science score `48.5`; adding the five moved displayed rows gives `47.395`, whose full
row-rounding interval cannot include `48.5`. This does not challenge the 134-task total, but makes
a prose family count insufficient to reproduce family curves. Frontier-Science therefore requires a hashed,
machine-readable cohort manifest for every admission set and aggregate figure/table, with task
IDs, tracks, lineages, weights, transforms, run/failure policy and source revision.
The source-hash-bound 11-task mapping and numerical mean check are retained in
`.research/edgebench_taxonomy_audit_2026-07-24.json`.

These are protocol and portfolio findings, not new Frontier-Science model results. No Rankine-v2
source or calibration artifact was changed by this audit.

## 2026-07-24 — EdgeBench theory-to-science second-order audit

We rechecked EdgeBench v1, the public repository and dataset; they remain at arXiv v1, GitHub
`a87350a` and Hugging Face `47846a4`. This pass used the full theory rather than adding another
summary of the headline curve. Four untested boundaries now enter the Frontier-Science plan.

First, the log-sigmoid derivation explicitly depends on small score units, so identical raw
scientific evidence must be replayed under coarse/canonical/fine rubric partitions and random
task accumulation orders before curve smoothness is treated as an agent property. Second, the
aggregate theorem treats tasks as non-interacting; same-task persistence therefore does not show
cross-task scientific learning, motivating randomized related/unrelated/misleading source→target
curricula. Third, independent equal budgets omit the scientific portfolio problem of choosing
which projects deserve scarce instruments and confirmation. Fourth, stable/replayable task
semantics omit instrument drift, sample depletion, irreversible interventions and out-of-order
experimental results.

The resulting E29--E32 designs, experiment-matrix rows, TODOs and source hashes are recorded in
`docs/edgebench_science_experiment_addendum.md`, `.research/science_experiment_plan.md`,
`.research/plan_gap_audit.md` and
`.research/edgebench_science_second_order_audit_2026-07-24.json`. These are Frontier-Science
proposals derived from explicit EdgeBench assumptions; they are not additional EdgeBench results
and do not change any Rankine implementation or model-performance evidence.

## 2026-07-24 — RankineCycleOpt-v2 pre-commit validation

The quarantined polynomial Rankine surrogate has been replaced by a six-regime, single-reheat
cycle task using self-contained IAPWS-IF97 Regions 1, 2 and 4. Candidate artifacts are bounded
Pareto archives over boiler pressure, main-steam temperature, reheat-pressure fraction and reheat
temperature. Four development and two held-out regimes separate nominal efficiency/specific-work
hypervolume from five sealed weather, pressure-loss, degradation and material-limit shifts. Hard
gates cover moisture, materials, pressure ordering, archive diversity and energy closure.

A fixed-seed power-11 Sobol calibration rebuilds all committed indices and anchors exactly. An
audit-only `iapws==1.5.4` comparison covers 32 Region-1/2/4 states: the largest absolute enthalpy
or internal-energy difference is about `9.1e-13`, and the largest speed-of-sound difference is
about `4.1e-12`. The weak baseline has mean development front efficiency `0.3925913391` and
specific work `1475.758849 kJ/kg`. The nominal witness reaches `1.0/1.0` development/held-out
nominal score but only about `0.7125/0.73125` shift feasibility; the robust witness trades nominal
score down to about `0.484/0.452` while reaching `1.0/1.0` robustness. Maximum observed cycle
energy residual is about `4.55e-13 kJ/kg`.

The complete pending-source suite passes **244/244** tests. Dirty-source Rankine calibration,
candidate-wave-4 and certification audits all have `execution_passed=true`, but correctly record
`trust_decision=source_tree_dirty_or_unknown`, `trusted_evidence=false` and `passed=false`.
They are pre-commit validation only. Formal reports must be regenerated from the committed clean
source before this rebuild contributes trusted evidence or GPT-5.5 calibration results.

## 2026-07-24 — EdgeBench effort-clock and autonomy re-audit

EdgeBench upstream remains unchanged at arXiv `2607.05155v1`, public SForge commit
`a87350ab80eeb320b13cb71d1b0c3ffcc20a670f` and Hugging Face revision
`47846a4c3669ad447e0ea984833b0d352460c5f9`. Re-reading the full theory against the official
51-task Codex configuration exposes a feedback-clock confound not captured by a generic wall-time
breakdown: all tasks use a 12-hour horizon and 30-minute observer auto-evaluation, but agent
submission cooldowns are `44×120 s`, `3×216 s`, `1×2160 s` and `3×0 s`. A common hour axis can
therefore mix search speed with authoritative-feedback opportunity.

Four new, explicitly unrun Frontier-Science experiments enter the plan. S4 fixes active work,
scientific calls and total feedback events/bits while randomizing feedback cadence, then tests
which of wall, active, experiment-cost, feedback-event or revealed-bit time supports stable curve
collapse and forecasts. S5 directly intervenes on matched well-mixed, chain, modular-bottleneck
and hierarchical scientific dependency graphs, including a bridge/prerequisite treatment, so the
frontier-expansion mechanism can be falsified rather than inferred from curve fit. Q1 compares
fixed, menu and open preregistered research questions on fresh-world information/decision value.
K3 randomizes blank, neutral, plausible-wrong, correct and diverse executable starters to measure
scientific-prior anchoring and mechanism retraction.

The source facts, configuration census, designs and claim limits are machine-recorded in
`.research/edgebench_science_third_order_audit_2026-07-24.json`; E33--E36 and the corresponding
experiment-matrix/TODO changes are in the EdgeBench addendum and research plan. These deductions
are not new EdgeBench numerical results and do not change any Frontier-Science model result.

## 2026-07-24 — Trusted Rankine GPT-5.5 calibration and cross-task summary v16

The clean-revision Rankine evidence chain now contains budget-one normal, budget-three normal and
budget-three strict selection-blind GPT-5.5 reports plus raw trajectories, run manifests,
candidate/parent hashes and a trusted derived analysis. Budget one reaches development/held-out
nominal `0.963561/0.957382`; both budget-three conditions reach `1.0/1.0`. Every selected artifact,
however, has development/held-out robustness `0.0/0.0` and shift feasibility `0.6/0.6`: nominal
transfer does not survive material-derating and combined-shift envelopes. All proposals are valid.
The normal run accepts its first proposal and the selection-blind run keeps every proposal parent
at the frozen baseline. Both use four oracle calls, but use 14,206 versus 12,676 tokens and 100.7
versus 134.6 seconds; Azure exposes no server-side generation seed. Therefore the result shows only
that this single nominal success did not require iterative score/parent feedback, not a causal
feedback null effect. It is simulator-specific IF97 cycle optimization, not plant validation or
thermodynamic discovery.

`experiments/science_calibration_summary_2026-07-24_v16.json` binds clean source `ce1cf4d` and
contains **45 normal single-run conditions across 23 tasks**. Each condition still has one seed;
sealed metrics remain task-specific and must not be averaged into one science score.

## 2026-07-24 — EdgeBench raw-measurement, invariance, team and utility audit

EdgeBench upstream remains unchanged at arXiv `2607.05155v1`, SForge `a87350a` and public dataset
`47846a4`. Auditing all 39 Science/ML design notes against the explicit exclusion of vision-dominated
tasks adds four distinct, unrun Frontier-Science experiments. I6/E37 randomizes oracle-clean,
reference-preprocessed and agent-built raw instrument pipelines and propagates calibration/
extraction uncertainty to mechanism and decisions. V4/E38 uses unit, coordinate, channel, grid,
spectral and symmetry-equivalent metamorphic twins plus real physical negative controls. T1/E39
compares one agent, shared branches, isolated investigators and blinded synthesis at equal total
budget, with one team claim committed before fresh confirmation. U1/E40 freezes a legitimate
utility family but draws stakeholder weights only after commit, comparing public-scalar artifacts
with reusable Pareto/method artifacts on sealed regret and safety.

The source hashes, experiment designs and claim boundaries are recorded in
`.research/edgebench_science_fourth_order_audit_2026-07-24.json`. The expansion plan prioritizes
`EvidenceSynthesis/ProspectiveMetaAnalysis`, whose executable screening, duplicate/selective-
reporting detection, hierarchical inference and next-study design are tested by a fresh prospective
confirmation. None of these additions is an EdgeBench numerical result or a completed experiment.

## 2026-07-24 — EdgeBench disclosed-horizon and scientific-judge audit

EdgeBench upstream was rechecked and remains arXiv `2607.05155v1`, SForge `a87350a` and public
dataset `47846a4`. The paper's main per-time values are checkpoints from independent 12-hour
trials, so they describe a 12-hour-aware policy rather than counterfactual agents independently
told to stop at 2/4/6/8/10 hours. A direct recomputation of the official public 51-task displayed
table finds disjoint best-model sets at 2h and 12h on 19/51 tasks. This is descriptive
horizon-conditioned ranking drift, not evidence that disclosed horizon caused the changes.

The current public harness also exposes a model-mediated evaluation path:
`college_english_exam_bank` invokes `grade_with_codex.py`, with the grader selected at runtime by
`SFORGE_JUDGE_MODEL`. The judge image pins grading code, but current judge-image hashing and
persisted effective `run_config.json` do not naturally bind the runtime judge environment. This is
a provenance/reliability risk, not evidence that any EdgeBench score changed or is incorrect.

Three unrun Frontier-Science experiments were added. HZ1/E41 randomizes independently disclosed
2/6/12-hour horizons, compares them with 12-hour-aware matched prefixes and adds a preregistered
random-censoring arm. J1/E42 pins complete judge manifests and measures blinded anchor/duplicate/
style-twin repeatability, inter-judge agreement, executable-outcome concordance and expert
adjudication. F9/E43 separately treats the agent's decision to request costly authoritative
feedback as an acquisition policy, comparing agent-requested, fixed-grid, random, cost-aware VOI
and end-only schedules with pre-request value predictions. The 1M-versus-200k context result is
also scoped to a performance-level advantage: its displayed gap narrows from +5.8 at 2h to +4.4
at 12h, so it does not alone identify a faster baseline-adjusted learning slope. The source hashes,
descriptive recomputation and claim boundaries are recorded in
`.research/edgebench_science_fifth_order_audit_2026-07-24.json`.

## 2026-07-24 — EdgeBench continuation and longitudinal-risk-set audit

The unchanged official 51-task table was reprocessed at all six displayed checkpoints. After a
cumulative-maximum sensitivity used only to respect the paper's declared best-so-far estimand,
246 task--model cells are complete and have positive 2h-to-12h gain. Of these, 33 have larger
8h-to-12h than 2h-to-6h gain, and seven improve by at most one point through 6h but at least two
points afterward. This motivates CA1/E44: compare fixed, deterministic-headroom, randomized and
uncertainty-aware continuation policies while forcing a random audit tranche to 12h, so late
takeoff and the full-cohort endpoint remain estimable.

Separately, six of the 255 public displayed sequences decrease despite the paper's best-so-far
definition. The raw 38,000-hour trajectories and figure-analysis code are not public, so no cause
is assigned and this is not evidence that the upstream headline result is wrong. M2 instead makes
the lesson operational here: freeze scheduled run IDs, assert every single-run observer envelope
is monotone under the versioned selector, publish checkpoint run-flow counts, and separate ITT,
paired-completer and any changing-risk-set summaries. The exact source hash, cells, thresholds and
claim limits are stored in `.research/edgebench_science_sixth_order_audit_2026-07-24.json`.

## 2026-07-24 — EdgeBench release-cohort, builder and evidence-unit audit

EdgeBench upstream remains arXiv `2607.05155v1`, SForge `a87350a` and public dataset
`47846a4`. The official README reports 12-hour aggregates for both the 134-task headline cohort
and the public 51-task subset. Full-minus-public differences are `7.1/5.3/5.1/7.0/5.3` points
for Opus 4.8, GPT-5.5, GPT-5.4, GLM-5.1 and DS-V4-Pro. These are descriptive task-mixture gaps;
without the other 83 contracts, release-selection rule and raw trajectories they do not identify
which cohort is harder or why the gap exists.

Three additional Frontier-Science protocols were added. G1/E45 rotates lineage-matched open-
replay, sealed-prospective and delayed-release pools, then requires independent replay when the
delayed pool is published. G2/E46 records every task-building/calibration model and cross-fits
A-built, B-built and expert-built procedural families to detect builder--solver interactions.
EVI1/E47 binds observations to world/sample/batch/instrument/intervention ancestry and compares
fresh, correlated and duplicate feedback using evidence effective sample size and information gain,
not only calls or bits. These are proposed experiments and release gates, not new EdgeBench or
Frontier-Science model results. Source hashes, arithmetic and claim boundaries are recorded in
`.research/edgebench_science_seventh_order_audit_2026-07-24.json`.

## 2026-07-24 — Trusted MOSFETDoping-v2 calibration and repository audits

Clean source revision `97158a8` replaces the six-orders-wrong per-m3 doping toy with a transparent
six-parameter Gaussian halo compact-model task over four development and two interleaved held-out
devices. It combines screened-Poisson drain coupling, standard MOS threshold electrostatics,
Caughey--Thomas mobility, charge-sheet current and Poisson random-dopant variation. This is a
reduced-order nMOS benchmark model, not TCAD or a measured-device claim.

`mosfet_doping_v2_calibration_2026-07-24.json` reconstructs every fixed-seed 2048-point Sobol
archive and anchor exactly. The valid weak baseline scores `0/0` development/held-out nominal. The
nominal witness scores `1/1` but has development/held-out worst-shift robustness `0/0.2870` and
shift feasibility `0.8385/0.8281`; the robust witness trades nominal score to `0.9340/0.8998` and
reaches unit worst-shift robustness and shift feasibility on both splits. Nominal-feasible pools
contain 1084--1380 of 2048 designs and all-shift-feasible pools 458--852. All directional checks,
fail-closed cases, six-device process/tmpfs isolation and legacy-v2-driver tests pass; the three
task-card DOIs resolve to Sze--Ng, Taur--Ning and Caughey--Thomas metadata.

The same clean revision produces trusted wave4 v7, certification v35, security v19 and secure-
baseline v25 reports. Wave4 recommends MOSFET as a candidate; certification records **7 certified,
29 candidate and 15 quarantined** packages; all 18 security tests pass; and all 51 baselines are
deterministic, valid and fail closed across two runs with zero infrastructure failures. These are
task calibration and infrastructure results, not GPT-5.5 performance, feedback learning, TCAD
validation or semiconductor discovery.

## 2026-07-24 — EdgeBench observation-process audit

EdgeBench upstream remains unchanged at arXiv `2607.05155v1`, SForge `a87350a` and public
dataset `47846a4`. A full scan of the 51 released contracts and the current SForge execution path
finds a measurement distinction not represented by a common wall-time axis. Ordinary artifact
tasks wait one `eval_interval`, capture the live workspace and submit asynchronously before the
next wait. Three public `game_mode=true` text-adventure tasks skip host auto-evaluation entirely;
their agent-driven game-session steps record moves/actions/scores but no wall-clock timestamps.
The public Games family therefore contains three live-state game-mode and five artifact-mode tasks.

This source fact does not show that any EdgeBench score or fit is wrong: the raw 38,000-hour
trajectory corpus and figure-analysis code are unavailable, and the audit cannot reconstruct how
the published curves handled every task. It motivates OBS1/E48 in Frontier-Science. The proposed
gate replays identical sentinel-complete immutable trajectories under dense, 5/15/30/60-minute,
seeded-random-phase and agent-event observation kernels; treats first-valid/material-event time as
interval-censored when necessary; and reports AUC, takeoff, curve-parameter, forecast and ranking
sensitivity. Consumptive, irreversible and interactive scientific worlds instead require
timestamped actions, instrument readings and state transitions in a separate live-state stratum.
Source hashes, contract counts and claim limits are recorded in
`.research/edgebench_science_eighth_order_audit_2026-07-24.json`. OBS1/E48 is an unrun protocol
proposal, not a Frontier-Science model result.

## 2026-07-24 — EdgeBench endogenous-experience and local-result audit

EdgeBench upstream was rechecked and remains arXiv `2607.05155v1`, SForge `a87350a` and public
dataset `47846a4`. The paper explicitly distinguishes benchmark-supplied sequences from its
endogenous long-task stream: the agent chooses local tests, simulations and submissions and thus
changes what it observes next. The public harness preserves outer-loop submissions, auto-evals,
archives and conversation logs, but these are not a structured census of every inner-loop local
experiment or its positive, null, contradictory, failed or censored outcome.

Two unrun Frontier-Science experiments were added. AD1/E49 crosses fixed randomized/balanced and
agent-adaptive acquisition with naive versus policy-aware inference, logging eligible actions and
acquisition probabilities or randomized exploration before outcomes. It reports effect/mechanism
bias, interval coverage, FDR and positivity violations; fresh confirmation does not retroactively
make an invalid adaptive-data interval calibrated. NR1/E50 routes every local simulator/instrument/
data action through a trusted append-only result ledger and compares it with the submitted
claim/evidence package under free-reporting, mandatory-all-result and blinded-synthesis conditions.
It measures sign-conditional omission, effect inflation and claim reversal after full disclosure.

These deductions do not show selective reporting or invalid inference in EdgeBench, whose raw
38,000-hour trajectories are unavailable, and they are not new Frontier-Science performance
results. They specify additional science-only gates that are distinct from E17 repeated-holdout
control, E27 crash-consistent retention, E43 feedback acquisition, E47 evidence eESS and E48
observation-kernel sensitivity.

## 2026-07-24 — Trusted MOSFET OBS1 micro-pilot

The observation-kernel implementation was run from clean source revision `412c101` over the three
trusted MOSFET GPT-5.5 trajectory reports committed at `928447c`. Each raw trajectory is bound to
one clean-revision portable snapshot and report hash. The offline replay uses a common 120-second
analysis horizon, dense-event observation, fixed 15/30/60/120-second grids and a preregistered
seeded-random phase for each grid. The resulting report
`experiments/mosfet_observation_kernel_micro_pilot_2026-07-24.json` has
`execution_passed=true`, `trusted_evidence=true` and source revision `412c101`.

This short implementation pilot shows material observation sensitivity. Dense AUCs are
`0.5427/0.1642/0.4831` for budget-one normal, budget-three normal and budget-three
selection-blind trajectories. A 120-second fixed grid assigns AUC zero to all three and changes
all three pairwise strict comparisons into ties; its seeded-random-phase counterpart produces one
strict pairwise rank reversal and one tie change relative to dense observation. Across all tested
kernels the largest absolute within-trajectory AUC shift is `0.5427`. The report also retains
interval-censored material-event times, missed-current-state rates and the exact realized phases.

The result is **not** a completed long-horizon OBS1 experiment and is not a feedback-effect or
model-ranking estimate. The three inputs are single short calibration runs, the budget-one arm has
only one post-baseline event, feedback conditions are not repeated or generation-seeded, and a
120-second grid is deliberately too coarse for this two-minute window. It demonstrates that the
analysis gate works and that cadence can erase or reverse a short-trajectory AUC comparison; the
planned 5/15/30/60-minute replay still requires sentinel-complete multi-hour trajectories and a
separate path-dependent live-state task.

## 2026-07-24 — EdgeBench conditional-continuation audit

EdgeBench upstream was rechecked and remains arXiv `2607.05155v1`, SForge `a87350a` and public
dataset `47846a4`. The paper's nominally three 12-hour trials are independent runs, and its
stateful ablation compares one continuous 12-hour trajectory with six fresh 2-hour attempts.
Neither design clones one identical mid-run research state into independently randomized
continuations. The theory nevertheless conditions stochastic unlocking on the full latent state
`n(u)`, while the observed score is a scalar projection; its bottleneck/module discussion notes
that frontier location can matter beyond unlocked score mass. Public SForge auto-resume continues
one native session after failure but does not expose a same-checkpoint multi-continuation
experiment primitive.

This motivates the unrun CF1/E51 protocol. On two checkpointable procedural science tasks, freeze
a content-addressed first-valid and mid-budget state containing artifact, context, evidence ledger,
local cache, environment, pending jobs and remaining budget, then fork each parent into multiple
equal-budget randomized continuations. Add matched-score parents reached through different
hypothesis/evidence histories and state-channel controls; report within-parent future variance,
between-history variance, wrong-mechanism lock-in/escape and sealed confirmation. The parent is the
experimental unit and every child is retained—post-hoc best-child selection would turn the audit
into best-of-K search. Source hashes, design distinctions and claim limits are stored in
`.research/edgebench_science_tenth_order_audit_2026-07-24.json`.

This audit does not show excessive path dependence or wrong-hypothesis lock-in in EdgeBench, whose
raw headline trajectories are unavailable. CF1/E51 is a proposed Frontier-Science experiment and
does not change any model-performance result.

## 2026-07-24 — Trusted MOSFET GPT-5.5 analysis and cross-task summary v17

The MOSFET analysis implementation and its fail-closed synthetic tests were committed at clean
source revision `2f647d9`; the full suite then passed **275/275** tests. From that clean revision,
`experiments/mosfet_v2_calibration_analysis_2026-07-24.json` validates the three trusted input
reports, raw/portable trajectory hashes, best-program hashes, run manifests, oracle/token
accounting, normal incumbent lineage, frozen-baseline selection-blind lineage, and all six devices
by six process/operating shifts. The report has `execution_passed=true`,
`trusted_evidence=true` and SHA-256
`733b86d364f0ee497719753123de086bdea081abe9c89451b4858bbbe9630f8f`.

The budget-one selected artifact reaches development/held-out nominal `0.779698/0.746442`,
robustness `0.706953/0.717508` and shift feasibility `0.585938/0.536458`. The normal budget-three
artifact reaches nominal `0.457400/0.445406`, robustness `0.297742/0.401801` and shift feasibility
`0.619792/0.552083`. The frozen-parent selection-blind batch selects nominal
`0.770322/0.738085`, robustness `0.722514/0.711681` and shift feasibility `0.770833/0.708333`.
Normal and selection-blind use the same four oracle calls, but normal uses 18,215 versus 12,708
tokens and the Azure endpoint exposes no server-side generation seed. The observed `-0.313`
normal-minus-blind nominal contrast is therefore descriptive proposal variance, not evidence that
feedback hurts or is unnecessary.

`experiments/science_calibration_summary_2026-07-24_v17.json` has SHA-256
`83d5ba3c3ec4756e172276a3280ba79dcb42809b0d44f786fe5e4962e409a977`, binds the same clean source
and contains **47 normal single-run conditions across 24 tasks**. The strict open-loop MOSFET arm
remains in the task-specific analysis. Both derived artifacts retain the compact-model boundary:
they are neither multidimensional self-consistent/commercial TCAD, fabricated-device validation,
feedback-causal evidence nor autonomous semiconductor discovery.

## 2026-07-24 — EdgeBench milestone-attribution audit

EdgeBench upstream was rechecked and remains arXiv `2607.05155v1`, SForge `a87350a` and public
dataset `47846a4`. Its gravitational-wave case study reports one 12-hour GPT-5.5 run with 224
agent submissions, 23 auto-evaluations and seven representative milestones. The paper usefully
compresses the run into phases involving frequency estimation, time-frequency localization,
source-mass calibration and waveform alignment, but some phases contain many submissions and
effective updates. Component-score movement identifies the scored output that improved; it does
not by itself isolate an individual edit, newly acquired evidence or interaction. The public
paper/release does not provide parent/full-child/component-only/leave-one-out factorial replay or
the raw artifact lineage needed to reconstruct it.

This motivates MA1/E52, an unrun Frontier-Science experiment. Milestones are selected by a
preregistered material-event rule rather than narrative appeal; every parent-to-child diff is
partitioned into observation/data, scientific model, inference/refusal, optimizer/design and
postprocessing components. Parent, full child, component-only, leave-one-out, rollback and key `2x2` interactions
are replayed on common frozen worlds/seeds. When a milestone also acquires data, an explicit
`old/new data x old/new method` design prevents crediting evidence acquisition to a code or
mechanism edit. Non-separable patches are reported rather than scored as zero, and attribution
must survive sealed/mechanism/refusal/validity gates. ReactionMechanismFitting-v2 and
ConvectionDiffusionOpt-v2 are the first proposed micro-pilot tasks because both already expose
active experiments and supported/null/misspecified worlds.

These source facts do not show that the EdgeBench case-study narrative is wrong, and the existing
Frontier-Science calibration contrasts are only positive controls, not agent milestone effects.
The current Reaction and Convection normal b1/b3 trajectories have no positive combined-score jump.
Reaction selection-blind b3 contains one `0.342579` frozen-baseline open-loop candidate, but it is
not an iterative feedback descendant and has development/heldout false-discovery rate `0.5`; it can
only smoke-test bundled replay and does not pass the planned science attribution gate. All three
Convection short-run conditions remain at zero.
MA1/E52 has not been run. Source hashes, design and claim limits are stored in
`.research/edgebench_science_eleventh_order_audit_2026-07-24.json`.

## 2026-07-24 — EdgeBench hypothesis-state and feedback-authority audit

EdgeBench upstream was rechecked and remains arXiv `2607.05155v1`, SForge `a87350a` and public
dataset `47846a4`. The paper's behavioral analysis describes strong systems as preserving a
current best, making focused changes and rolling back failures; its outer loop deliberately
provides task-defined authoritative scores, verdicts or diagnostics. The public paper does not
report a randomized single-incumbent versus explicit competing-hypothesis treatment, nor a
feedback-source bias/drift/conflict treatment. The unavailable raw trajectories may contain
alternative-hypothesis tracking or source criticism, so no absence claim is made.

This motivates two unrun Frontier-Science protocols. HP1/E53 compares a single incumbent with an
explicit hypothesis portfolio, model averaging and diverse branches across an early-ambiguous
phase and later discriminating interventions; one synthesis must be signed before fresh
confirmation. FR1/E54 randomizes calibrated, biased, drifting and conflicting feedback sources,
crosses source labels visible/hidden/permuted and scores source calibration, blind following,
escalation, false discovery and sealed recovery. These proposals do not establish a defect in any
EdgeBench judge or a new model result. Source hashes, distinctions and claim limits are stored in
`.research/edgebench_science_twelfth_order_audit_2026-07-24.json`.

## 2026-07-24 — MA1/E52 analyzer implementation smoke

`scripts/analyze_milestone_attribution.py` now implements the preregistered full-child,
component-only, leave-one-out, rollback, two-factor interaction and `old/new data × old/new
method` estimands with frozen-parent/evidence/evaluator/world/environment hash checks. It reports
non-separable treatments without assigning them a zero effect and applies sealed materiality,
validity and false-discovery gates. Five synthetic and real-control tests pass.

The existing truth-blind task calibrations are analyzer controls, not agent milestones. The
Reaction classical bundle improves aggregate score to `0.4818355`, but two of eleven paired worlds
gain false discoveries and the heldout FDR is `0.5`, so the reliability gate rejects a scientific-
insight attribution; its historical components remain non-separable. In Convection, adding the
off-axis experiment raises combined score from `0` to `0.8956051473` and heldout score from
approximately zero to `0.8915088582`; mechanism, prediction and design improve on all seven
supported paired worlds without changing false discovery on four unsupported worlds. This is a
bounded positive-control evidence contribution in a synthetic benchmark, not an agent discovery.
The current Reaction and Convection normal trajectories still contain zero eligible positive
agent milestones, and the positive Reaction selection-blind artifact remains excluded because it
is an offline frozen-parent proposal with FDR `0.5`.

## 2026-07-24 — GeneNetworkIntervention admission and trusted calibration

`SystemsBiology/GeneNetworkIntervention` adds the 38th internally admissible task and raises the
inventory to 52 directories: 7 certified, 31 candidate and 14 quarantined. It is distinct from
the static interventional SCM task: candidates actively choose bounded CRISPRi/a-like time-series
experiments in a nonlinear four-gene ODE, recover a signed dynamic network and kinetic parameters,
and design a sparse intervention on actionable regulators of a protected phenotype readout.
Mechanism, sealed trajectory prediction, phenotype utility, intervention transfer, confidence,
coverage, false discovery and null/latent-regulator refusal remain separate. Candidate experiments,
final interventions and sealed prediction schedules cannot directly perturb the readout.

The truth-blind nonlinear reference uses six fixed single/pair regulator experiments, derivative
filtering, bounded nonlinear regression, leave-one-experiment model checks and fitted-model
intervention search. It scores `0.905293` development and `0.893222` held-out joint quality;
mechanism is `0.862462/0.800048`, prediction `0.915986/0.898357`, and decision utility
`0.942784/0.993940`. Supported-world coverage and unsupported-world refusal are both one on both
splits, with zero false discovery. These values are synthetic task calibration, not autonomous
agent performance or biological discovery.

All evidence binds clean source revision `b777889`. The task calibration SHA-256 is
`d689563cb72ad9b7acdc699250760ac5094a7f706f6c8a09f46f4e9c134b5e1d`; certification v38 is
`7631a77da11826254522575a41fef5ddd2c9ec772a52a6e9a15738f6edd712bb`; security v22 is
`0ff1ce80104e024f9a905661ab7f70bde5d3f27aa5905c8203ed77c4cd60acab`; and secure baseline v28
is `d09a04a771abb595eeac0b4d1d69b04c5055972e4b207af90b284720ceb629e3`. Certification reports
52 tasks at 7/31/14, security passes 18/18, the 52×2 baseline reports 52 deterministic, valid and
fail-closed tasks with zero infrastructure failures, and the full suite passes 305/305.

The benchmark remains a deterministic synthetic four-gene abstraction. Server-held worlds,
measurement/batch/cell-state models, independent systems-biology review, real Perturb-seq assays
and prospective wet-lab validation remain necessary before any biological claim.

## 2026-07-24 — GeneNetworkIntervention model analysis and cross-task summary v19

`experiments/gene_network_intervention_calibration_analysis_2026-07-24.json` has SHA-256
`d616ab194464c9b142d1fc2894c99be8074f608ff71055693bab740970e7d6d3` and binds analysis
source revision `df205bb`. It verifies task/runtime source equivalence and the three trusted
GPT-5.5 reports. Across their seven proposals, six are invalid: four request invalid experiments
and two violate the candidate callback schema. The only valid proposal refuses every supported
world, so no valid nonzero scientific proposal is observed. Normal and selection-blind budget
three use four oracle calls each, but normal uses 1,548 more tokens and 13.88 more seconds. Azure
does not expose a server-side generation seed, so this contrast is descriptive rather than a
feedback-effect estimate.

`experiments/science_calibration_summary_2026-07-24_v19.json` has SHA-256
`8b24eb3b7d9986556863ca4d0bf981bdd3d7fea941d7ef6f5c765ce79a934471`, binds clean source
revision `1af62cd`, and contains 51 normal single-run conditions across 26 tasks. The strict
selection-blind GeneNetwork condition remains in the task-specific analysis. The expanded
cross-task finding is a reporting rule rather than a biological claim: protocol validity,
supported-world coverage and refusal, and scientific quality conditional on a warranted claim
form separate hurdles. The reports remain single-run synthetic-task calibration, not population,
causal-feedback, real Perturb-seq, wet-lab or autonomous-discovery evidence.

The current full suite passes 307/307 tests. This supersedes the 305/305 implementation count
above by adding the two GeneNetwork analysis tests; the clean-revision certification, security
and secure-baseline reports remain v38/v22/v28 on task revision `b777889`.

## 2026-07-24 — RNAInverseDesign admission, model analysis and cross-task summary v20

`RNAEngineering/RNAInverseDesign` adds the 39th internally admissible task and raises the
inventory to 53 directories: 7 certified, 32 candidate and 14 quarantined. Five development and
three held-out targets span hairpin, bulge, internal-loop, tandem and multibranch families. The
trusted evaluator computes the exact partition function, MFE structure and pair marginals for a
declared pseudoknot-free pair-stack-loop ensemble, enforces fixed bases, GC bounds and forbidden
motifs, and separately scores pair compatibility, target probability, ensemble defect, MFE F1,
held-out transfer, four parameter shifts and proxy false promotion.

The task calibration has SHA-256
`015a27373c8938f9d8c77b64f7e9ae82b14b825b15bf30ba537d70356debf4c4` and binds clean task
revision `41f5fb4`. Reference regeneration is exact, minimum nominal/shifted headroom is
`0.355211/0.342794`, and four exhaustive structure enumerations agree with dynamic programming
to approximately `1e-15`. A valid sequence with pair compatibility `1.0` has target probability
`3e-9`, normalized exact and shifted quality zero, and ensemble defect `0.3347`; target-pair
compatibility is therefore not an adequate ensemble-design objective.

The trusted analysis has SHA-256
`760e0f9b20b0deeb7d32c3fecb3c1671b324db70f3d57130ef250e1db84f79df`. GPT-5.5 budget one
remains at zero because its proposed sequence violates constraints on three of eight targets.
Normal budget three improves development exact utility `0.239243→0.507381→0.720397`, with
held-out utility `0.499732`, development/held-out robustness `0.712426/0.486729` and proxy false
promotion `0.40/0.667`. The frozen-parent selection-blind batch selects development/held-out
`0.893523/0.986008`, robustness `0.888058/0.982162` and zero proxy false promotion. Normal and
selection-blind both use four oracle calls but differ by 12,169 tokens and 37 seconds; Azure has
no server-side seed, so the contrast is descriptive and not a feedback-effect estimate. The
three input report hashes are `5db7c55d…b8b632`, `ef7c710f…2620b` and
`66081083…18de7` respectively.

Clean-revision certification v40 (`d11021ff…9585b1`) reports 53 tasks at 7/32/14; security v24
(`2731e80c…d5e67`) passes 18/18; and secure baseline v30 (`ef06a3b4…127cf9`) reports 53/53
deterministic, valid and fail-closed tasks with zero infrastructure failures. The full test suite
passes 317/317 in 1019.198 seconds.

`experiments/science_calibration_summary_2026-07-24_v20.json` has SHA-256
`b433bd08fe8769bb395015849daa8db01d294d91bf7f4eee5291e047ddadf910`, binds clean source
revision `30593bb`, and contains 53 normal single-run conditions across 27 tasks. Selection-blind
RNA evidence remains task-specific. These artifacts calibrate a transparent simplified ensemble;
they do not implement the complete Turner model, establish global optimality, validate
ViennaRNA/NUPACK agreement, synthesize RNA, measure structure or function, or support population,
feedback-causal or autonomous-discovery claims.

## 2026-07-25 — ProteinStabilityDesign admission and science summary v21

`ProteinEngineering/ProteinStabilityDesign` is now the 40th internally admissible task. The
54-package manifest contains 7 certified, 33 candidate and 14 quarantined tasks. The task rebuilds
2,756 reliable double mutants from hash-bound ProteinGym v1.3 and Tsuboyama 2023 sources across
five development and three held-out domains. Each world exposes a single-mutant additive proxy,
permits twelve charged double-mutant assays and requires eight distinct sequences. Stability,
batch diversity, top-decile rate, proxy false promotion, held-out transfer and raw trypsin and
chymotrypsin readouts remain separate.

The task calibration (`fe7d5aac…be268`) binds clean source `72301ee`. Exact source rebuilding
passes, the weak additive baseline scores zero, the full-landscape normalization witness scores
one and the truth-blind twelve-assay policy reaches development/held-out `0.513673/0.567390`.
The evidence is a finite public DMS replay, not prospective protein design or a wet-lab result.

All seven GPT-5.5 proposals are executable and improve the zero development baseline. Budget one
reaches development `0.614375`, held-out policy `0.411550` and held-out protease robustness
`0.646087`. Normal budget three accepts `0.476907→0.534585`; the second accepted update lowers
development protease robustness `0.488125→0.441239` while held-out policy rises
`0.424996→0.558983`. The frozen-parent selection-blind batch selects development `0.546399`, but
its rejected step three reaches held-out policy/robustness `0.652319/0.753267`, above the selected
artifact's `0.519425/0.722662`. Normal and selection-blind use four oracle calls but 16,306 and
14,172 tokens. Azure exposes no server-side generation seed, so the contrast is descriptive and
does not estimate a feedback effect.

The trusted derived analysis (`a8086d75…47f27`) binds all report and raw-trajectory hashes,
online/frozen-parent lineage, eight world axes and selected/terminal artifact hashes. Its static
screen finds no ProteinGym identifiers, WT sequences, fixed mutations, dataset paths, network or
filesystem reads in retained artifacts. Runtime isolation also passes, but neither check rules out
pretraining contamination or semantically hidden lookup.

On clean candidate revision `21a2220`, certification v42 (`bffad391…34ca`) records `7/33/14`,
security v26 (`37db99a4…c66f`) passes 18/18, and secure baseline v32
(`be51dc71…3534`) reports 54/54 deterministic, valid and fail-closed tasks with zero infrastructure
failures. The full suite passes 332/332 in 1064.926 seconds. Cross-task summary v21
(`272acb27…823`) contains 55 normal single-run conditions across 28 tasks; strict selection-blind
conditions remain in task-specific analyses. These reports support task calibration and offline
scientific optimization only, not population performance, feedback causality, prospective
confirmation, protein function or autonomous scientific discovery.

## 2026-07-25 — ElectrolyteConductivityDesign admission and science summary v22

`Electrochemistry/ElectrolyteConductivityDesign` raises the inventory to 55 packages and the
internally admissible count to 41. The candidate reconstructs a CC-BY-4.0 public EIS source with
5,035 temperature records as 504 experiment IDs. It uses 358 complete historical experiments
over 85 formulations for a public proxy and 141 complete later experiments over 23 non-overlapping
candidate formulations. Each charged assay returns two discovery repeats; two further repeats
remain untouched by proposal feedback and selection.

The trusted task calibration has SHA-256
`b16bb89861bfb154b46595406302e98a0a5b22b040c61c17e87454cb551eb2b6` and binds clean
implementation revision `903f84b`. Exact source rebuilding, all 141 independent Arrhenius
recalculations, conductivity/cell-constant identities, secure-baseline equivalence and metric
sealing pass. The truth-blind eight-assay policy reaches visible development/held-out
`0.407836/0.270111` and discovery-repeat robustness `0.569955/0.355477`, but untouched-repeat
confirmation is only `0.025989/0.000000` and confirmation robustness is zero on both splits.

All seven formal GPT-5.5 proposals are executable, improve the zero discovery-score baseline and
use all eight unique assays per world. Budget one reaches visible development/held-out
`0.262816/0.309358`, while its untouched confirmation axes are all zero. Normal budget three
accepts `0.492354→0.878184`; the selected artifact reaches held-out visible `0.926444` and
discovery-repeat robustness `0.826243/0.895519`, yet all four selected confirmation axes remain
zero. The frozen-parent selection-blind batch selects visible development/held-out
`0.645852/0.764770`, also with zero nominal confirmation. Its discarded first proposal has
development confirmation `0.026578`. Normal and selection-blind use four oracle calls but
22,583 and 14,642 tokens. Azure exposes no server-side sampling seed, so their difference is
descriptive and does not identify a feedback effect.

The trusted derived analysis has SHA-256
`2f3fa9d7b0d57375ddfa1f5699129421fae3931895f6f6e3b3d8894db864bb31`. It binds the three
model reports, raw trajectories, online and frozen-parent lineage, eight world axes, selected and
terminal artifact hashes, and retained-source shortcut scans. The scans find no fixed formulation
IDs, dataset/evaluator terms, filesystem reads or network imports, but cannot rule out pretraining
memorization or semantically hidden lookup.

Certification v43 has SHA-256
`1bb11ebccc9b0b4d5db042ebe3a5c777ae6c968ee0bd0a4a7362dd30e8363f45`, binds clean task
revision `903f84b` and records `7/34/14` with no missing or orphaned manifest records. Cross-task
summary v22 has SHA-256
`cfa60d2cbb66749e830ea8b61b838b005f50239def9878b509a0c1607172eca1`, binds clean revision
`5de2a20` and contains 57 normal single-run conditions over 29 tasks. The EIS result supports
offline scientific-optimization and repeatability-gap analysis. It does not establish a new
electrolyte, independent laboratory replication, complete-cell performance, feedback causality,
population performance or autonomous scientific discovery.

The subsequent 55-package closeout binds the complete infrastructure checks. Security v27 has
SHA-256 `43e225fa6106f789a42d4e70d569ff1af22d0b260503f213f2c3c49a24a94b22` and passes
18/18 adversarial tests. Secure baseline v33 has SHA-256
`add9262b2e1dec521974d2e054f66598d494b8a51bd10b8b13c0cd4437b11b7c` and reports 55/55
deterministic, valid and fail-closed tasks with zero infrastructure failures. Certification v44
has SHA-256 `1db67b1382467b60ac0d9fe0c634b38c9921ff5075fa9226095860ead4c00eaf` and records
`7/34/14`; all three reports bind clean revision `ea0075e`. Full-suite v1 has SHA-256
`f488a433153de963ec94d72d512bdfb610f9e63a145ced5928b6891e5cac691a`, binds clean revision
`24a24ab`, and passes 347/347 tests in 1139.654 seconds.

## 2026-07-25 — DemographicSFS-v2 rebuild and admission evidence

`PopulationGenetics/DemographicSFS` replaces its rank-two five-parameter time-index surrogate
with exact finite-sample Kingman lineage-count CTMC occupancy for a fixed ancestral scale and
constant or three-epoch histories. The task adds charged sample-size/replicate sequencing,
separate finite-SFS fit, held-out sample-size prediction, mechanism, confidence, coverage and
false-discovery axes, plus resolvable ancestral-state-polarization-error refusal.

The trusted task calibration has SHA-256
`3cae853ca742fcd863364f8720ea0ae2c278d3f147c9678ff0ff30e9309f4ca9` and binds clean
implementation revision `d0257dc`. Constant size recovers `theta/i` to floating-point precision,
an independent ODE occupancy calculation agrees below `2e-10`, and all seven nonconstant
supported histories have rank-four log-parameter sensitivities. The truth-blind eight-unit
multisample fit reaches development/held-out mechanism `0.769745/0.509725`, observed-menu fit
`0.985692`, and evaluator-only sample-size prediction `0.988312/0.982711`, with full supported
coverage, full refusal of the two polarization-error worlds and zero false discovery. A one-unit
single-spectrum design reaches only `0.007777/0.060510` mechanism. A subsequently registered
equal-eight-unit design that repeats only `n=12` reaches `0.538014/0.397377`, so the multisample
design's `+0.231731/+0.112348` mechanism gap is not explained by total sequencing budget alone;
the superseding calibration report will bind that control to the candidate-manifest revision.

The calibration does not pretend that every complex history is testable. A four-epoch history
and a mixture of contraction/expansion histories have clean best-three-epoch reduced deviances
`0.0092` and `0.0592`, far below the registered `2.25` refusal threshold; they remain explicit
finite-SFS near-equivalence limits rather than impossible forced-refusal labels. The trusted
inverse admission audit has SHA-256
`241f07bce46d5448a67e169f9f43fad582e97910bfec22475a437133fb159a0d`, also binds
`d0257dc`, passes 7/7 inverse-track checks and recommends candidate admission. This is a synthetic
neutral panmictic inference task, not a real-population history or autonomous biological
discovery. The source manifest becomes `7/35/13`, with 42 internally admissible tasks and an
approximate gap of eight to the roughly 50-task target; post-admission clean infrastructure and
GPT-5.5 calibration evidence remain pending.

## 2026-07-25 — DemographicSFS-v2 post-admission closeout

The superseding calibration, inverse admission, certification, security and secure-baseline
reports all bind clean candidate-manifest revision `9a72b51`. Their SHA-256 digests are,
respectively, `1318e29b2b393cccf6f235a3b9d3ab8057a06c5515856b92b2c3bea601d20927`,
`e9104f603656f5a76550751641b448eab8e84b02afe3af202216f9c9db5cfc12`,
`64c7f6cf6ef261edc25d36530530d178c5d0656141456cbecc753db29f75b466`,
`b09685d5adf8dcd4246811470c037d4df466da882ce1d39858a96c629a9fbaff` and
`58061604b56663e08dcf8bc13c1e9852fe83ac1ff0509bb091e1e3ef31a1e170`.
The calibration includes the equal-budget repeated-small-sample control; inverse admission passes
7/7; certification v45 records `7/35/13`; security v28 passes 18/18; and baseline v34 reports
55/55 deterministic, valid and fail-closed tasks over two repetitions with zero infrastructure
failures.

Full-suite v2 has SHA-256
`8d0458eb0d3b104c8ad510013e7f110621a927800d14b9c6eb2b9d3dbb258a0d`, binds clean audit
revision `090b065`, and passes 355/355 tests in 1162.826 seconds. This closes internal admission
and infrastructure reproduction for DemographicSFS-v2. GPT-5.5 task calibration, server-held
histories, linkage-aware models, real sequence QC and independent population-genetics review
remain separate outstanding evidence.

## 2026-07-25 — DemographicSFS-v2 GPT-5.5 calibration and analysis

Three trusted GPT-5.5 reports bind clean model source `1c30a99`. Budget one (SHA-256
`ba5b8dc1d960be47455f1375c8ade7b84d1d4e046381e8211d5813110cb3d223`) evaluates one
proposal, which fails with the sanitized `candidate_runtime_error` category; the valid baseline
remains selected at zero. The independent normal budget-three report (SHA-256
`77a19700c0097e36abf44603c1711762123443374685eeddc4001e720806655f`) has three valid
proposals. Step one is accepted at development/held-out mechanism `0.639534/0.397010`,
observed-SFS fit `0.865220/0.926762` and prediction `0.883087/0.939153`; it uses all eight
sequencing units in two calls, has full supported coverage and resolvable-mismatch refusal, and
zero false discovery. Steps two and three score `0.520768/0.637054` on development mechanism and
are rejected. Step two nevertheless reaches held-out mechanism `0.603214`, above the selected
step's `0.397010`.

The frozen-parent budget-three report (SHA-256
`8851bc75b08944dd0be8fb291ae5021ae90d30b4702c3f9d7fbcef2393ffb732`) has three runtime-
invalid proposals and remains at zero. Normal and frozen-parent conditions both use four oracle
calls but consume `26,450/17,984` tokens. Azure has no server-side seed, so this difference is
not a feedback-effect estimate. Across the three reports, 3/7 proposals are valid and all four
invalid proposals share the label-blind runtime category.

The derived audit has SHA-256
`88950cd4d3b99c55ca6810a3c2c9d9c0471109fadd2ed817416d3753383222c0`, binds clean
analysis source `7ac644f`, and verifies report/raw-trajectory agreement, lineage, accounting,
selected and terminal artifact hashes, all eleven world axes and narrow retained-source shortcut
scans. Cross-task summary v23 has SHA-256
`3b2beaaf7ad8736ef33a83a00e875f9fccfb7b41d7570846be8eb84feafca0d5`, binds clean
source `63e32fd`, and covers 59 normal conditions across 30 tasks. Full-suite v3 has SHA-256
`3d83d362f09ae04f5ca9ef0e436f712b2bfd7dc6e576b26127415f44ac49c509`, binds clean source
`3e35253`, and passes 359/359 tests in 1147.462 seconds. These are synthetic finite-SFS task and
model calibrations, not real-population inference, feedback causality, population performance or
autonomous biological discovery.

## 2026-07-25 — CalorimeterDesign-v2 rebuild, admission and model calibration

`ParticlePhysics/CalorimeterDesign` now replaces its false fixed-10-GeV baseline and fail-open
clipping path with three cost-conditioned Pb/scintillator design points over four development and
two interleaved held-out regimes. The transparent longitudinal gamma-profile oracle spans 28--40
layers and 0.8--250 GeV, separates resolution, response linearity, containment, material, length
and readout cost, and withholds five fabrication/calibration/dead-material/light-yield/electronics
shifts from search.

The trusted task calibration has SHA-256
`af5754f996fd736564bf991c19eb1256afc26a160a13257fe107a7cb6677f735` and binds clean
source `f6a7b73`. Independent gamma-CDF quadrature and material/cost identities pass; 36 fixed-
seed reference replays have zero gap; malformed, non-finite and duplicate archives fail closed.
The valid weak baseline has development RMS resolution `0.085573` and normalized score zero. The
nominal witness reaches development/held-out `1.0/1.0` at cost utilization `0.994478/0.999435`,
but robustness is zero and shifted-geometry feasibility is only `0.483333/0.466667`. The robust
witness uses `0.975352/0.980763` of cost, reaches nominal `0.797789/0.754127`, and preserves unit
robustness and shifted feasibility. Thus 1.913 percentage points of development cost headroom
reverse the manufacturing-feasibility conclusion. This motivates performance--cost--constraint-
margin curves; it is not evidence for a universal margin or a validated detector.

Wave-4 admission v9 (SHA-256
`e46f6e1e6e6f9888c33c70f5794d30fc130a09b2551e1d237aa82ea0a3909e18`) verifies seven
repaired candidates and retains five defects. Certification v46
(`bf9e5d2ff72af3d78ab600239f64499dcbd447532cd214c75c39f81f73ff7555`) records
`7/36/12`, or 43 internally admissible tasks and an approximate gap of seven to the roughly
50-task target. Security v29
(`ded2213d6372fc7caf37198e90b0a03635f159ca4a7a508948a78b18439792c3`) passes 18/18,
and secure baseline v35
(`348a2183d2fafd734ccb384f461909e2001c4a6668955a021aeb7e1c7c539723`) reports 55/55
deterministic, valid and fail-closed baselines with zero infrastructure failures. All bind clean
source `f6a7b73`.

Three GPT-5.5 reports also bind `f6a7b73`: budget one (SHA-256
`011b5576a7674be9706855302f62de9ef173aa86bc9bc052a982e4a13656c129`), normal budget
three (`a335f39a65e196a8a497342ce871ad22d4f2e72624216d8288e6ebab6a8da9b0`) and frozen-
parent budget three (`82b39b3ed84a6af0927b27045c6dee32eed4163b8e44e837c9623104bdf0aba2`). All seven
proposals are runtime-invalid, all failures are safely exposed only as `candidate_runtime_error`,
and infrastructure failures are zero. The conditions use 5,944, 18,091 and 18,329 tokens. Normal
and frozen-parent budget three match four oracle calls and 6,678 input tokens but differ by 238
output tokens; Azure exposes no server-side seed, so no feedback effect is identified.

The trusted analysis (SHA-256
`d6a09d7500d59652a229dae55112fb01edc7e0cfc405e1eff1bce356d2f5f888`) binds clean
analysis source `3eca1ac`. The three retained terminal sources compile, but the budget-one and
normal terminals request nonexistent `radiation_length_scint_mm`, while the frozen-parent
terminal requests nonexistent `light_yield_per_gev`. Four intermediate proposal sources were not
retained, so they remain only sanitized runtime failures. Cross-task summary v24 (SHA-256
`b49296829e9533b4f98f218a7ff891008e7fbc93077a8c5fd3f31232a99f9732`) binds `3eca1ac`
and covers 61 normal conditions across 31 tasks. These results support reduced-order task and
protocol calibration only, not feedback causality, model population performance, GEANT4/
electronics validity, test-beam performance or autonomous scientific discovery.

The final static-source full-suite v5 report has SHA-256
`bf8b2e87be95e0f4caf7706668de23f1e1d8fa836038bdca45ccbc1b0d9ec68d`, binds clean
source `3eca1ac`, and passes 375/375 tests in 1173.923 seconds. It supersedes the unretained
transition report generated while source work was still changing.

## 2026-07-25 — ProspectiveMetaAnalysis-v1 admission, GPT-5.5 calibration and hurdle analysis

`EvidenceSynthesis/ProspectiveMetaAnalysis` adds a synthetic registered-study workflow over six
development and four held-out worlds. Each world contains registry results, duplicate publications
from shared participant lineages, selectively highlighted outcomes and ineligible records. A
candidate must screen the evidence, fit a heterogeneous linear meta-regression, reject resolvable
nonlinear misspecification, commit a forecast and study design before the result, request at most
one fresh simulated study and update the claim.

The trusted task calibration has SHA-256
`53a2a6ee60fb917ae0077b5714342bf25f4c3806e6d55f9507237d285805a9c9` and binds clean
source `3b10e68`. The weak baseline scores zero. The truth-blind registry-first reference reaches
development/held-out `0.933698/0.886124` and robustness `0.298947/0.541734`, with evidence
integrity, supported-claim coverage and nonlinear refusal `1/1` and false discovery `0/0`.
Naive article/highlighted-outcome analysis has an intercept bias of at least `0.063169` in every
world. The largest supported-world lack-of-fit z-score is `1.358968`, whereas the smallest
nonlinear-world value is `3.199961`. The oracle witness scores one. These values calibrate a
synthetic standardized-summary task, not a real systematic review, clinical trial or autonomous
discovery result.

Wave-5 admission (SHA-256
`2efa2371c5f8786b80c644149732b5b8f18d6fe45e8b0f831c58192068784ca9`) recommends the task
as a candidate. Certification v47
(`0ab2fc89d62788304d0bc885a8f01fa12b883f663f84714a30dfb73de4411ccb`) records 56
packages at `7/37/12`, or 44 internally admissible tasks and an approximate gap of six to the
roughly 50-task target. Security v30
(`2cabf60df9dba8f66da1a4a70b64ad33df2119e0d1151304045d3cab43d0675e`) passes 18/18.
Secure baseline v36
(`97da4727e33982e1d07ac7f3aee94df6dbd9170304dda50733ea08d19826cfd0`) reports 56/56
deterministic, valid and fail-closed baselines with zero infrastructure failures. All bind clean
source `3b10e68`.

Three trusted GPT-5.5 reports also bind `3b10e68`: budget one (SHA-256
`643ed1c4b163def915ed99e9b74217ec2d7438878aaf833a9ac467d85df0c854`), normal budget
three (`2877b41b775f9de023e34772b86c596adb91c7a0cb42dd60f1edc19b97dbec94`) and frozen-
parent budget three (`d1b4e9f5bfd7aea7c72d088497bc1b59a097f8d38de9f87c0e588bcef25a4389`). Across seven
proposals, four are schema-invalid and three are valid empty abstentions. No proposal has nonzero
evidence integrity, makes a confirmation call or covers a supported claim, and every selected
score remains zero. The normal budget-three trajectory changes from schema-invalid at step one to
legal empty abstention at steps two and three. This is protocol repair, not scientific-workflow
progress.

Normal and frozen-parent budget three both use four oracle calls and 4,641 input tokens, but use
13,029 and 13,599 output tokens. Azure exposes no server-side generation seed, and the prompts and
generated programs differ, so the contrast is descriptive rather than causal. The trusted derived
analysis has SHA-256
`d288ad58e4fbf88ebe6d8e89f1c5875a7a07b209b69094de74ee6334f7397c43` and binds clean
analysis source `df4fda0`. It verifies raw/report hashes, lineage, accounting, all ten-world
science axes and narrow hidden-label/I/O scans of the three retained terminal programs. Four
intermediate proposal sources were not retained and receive no narrower diagnosis.

Cross-task summary v25 has SHA-256
`7cd4a4b3af5a729ca901735ca3027df27d15c75ec69b8fe360a3b4d5ef2d7dae`, binds clean source
`b85b0ee`, and covers 63 normal single-run conditions across 32 tasks. A same-revision closeout
rerun records wave-5 admission v2 SHA-256
`8f09efd426e27b8a4c6b25ce6bc5b3cdd9136c1f21a1722a28a46841ff877ca5`, certification v48
`445decdb6b627976ead1b2e669b4e757720bfe5fd20bc1472d83c5b37473eb36`, security v31
`f326b84754526dab9d26880261784681d274f6d20eebd731352ae2e6be9a6b76` and 56×2 secure
baseline v37 `41e29f416b38c79e0f3ffae1637e0e95de3f929d498b8c49961603958d6802a0`.
All are trusted and pass. A new static-source full suite remains to be generated after the
documentation and evidence artifacts are committed.

The first post-documentation full-suite attempt, v6 (SHA-256
`7e8b6be073255a4050464222c49b40e9c0270a04e9beb2ed0256ad35d93264ab`), is retained as
explicit failed evidence. It ran 394 tests and failed only
`test_full_analysis_when_raw_trajectories_exist`: the Calorimeter analyzer treated a change to
the non-runtime `frontier_science/certification.yaml` narrative as a task-runtime mismatch.
Commit `c813f16` narrows both Calorimeter and ProspectiveMetaAnalysis source-equivalence scopes to
Python runtime files, the task-specific benchmark contract and requirements. Two new tests require
that scope, while the existing explicit runtime-mismatch tests still fail closed.

The final clean-revision closeout binds `c813f16`. Wave-5 admission v4 has SHA-256
`637c78c928385cfa05c34973412361d93b055aa4ca183bd5705c30cf123ab5de`, certification v50
`30fcb3352e214824575cb70fa72a3e7aeab304c82f09853d130cfeef607d7bd7`, security v33
`946e0cbe07459e3fd56ae1b8401471f3595a7bece50f05284697e6556d90fdf0`, and 56×2 secure
baseline v39 `942f7f2eb9b57c72d160b8e33b10589290660973e55b42cedba3ec5a288213ab`.
All are trusted and pass; certification remains `7/37/12`, security is 18/18, and every baseline
is deterministic, valid and fail closed with zero infrastructure failures. Full-suite v7
(`af8698781056793a9aef2d8deac8cda54ee24fef1ec325e6950764a88ae36a18`) passes 396/396 in
1224.275 seconds and supersedes v6 for current-source regression evidence.

## 2026-07-25 — PhotovoltaicTandemDesign-v1 admission and clean closeout

`Photovoltaics/PhotovoltaicTandemDesign` adds a three-point fabrication-budget design curve over
five development and three interleaved held-out ASTM-G173-derived spectral/temperature regimes.
Candidates jointly choose one-to-four ordered band gaps and finite optical depths. Six sealed
thermal, band-gap, absorber-loss and spectral perturbations, plus absolute efficiency, current
matching, cost and junction count, remain evaluator-only.

The trusted task calibration (SHA-256
`76f78623101267ddc33405d73a8292a4764e5354ec37b77f0281d84dc006f690`) binds clean source
`0c0ca5e`. The exact 2002-row pvlib v0.13.1 spectrum copy has generated SHA-256
`eeb37120e14ad2fbb5e986d63b5f7711fbf622a03ebf67edabea618df397a728` and integrates to
`1000.370656 W/m2`. An independent first-order-condition root solve reproduces the oracle's
one-through-four-junction ideal efficiencies `0.336948/0.457351/0.512907/0.553294` with maximum
gap `3.33e-16`. The weak baseline scores zero. Nominal witnesses score `1.0/1.0`
development/held-out and select one, two-or-three, then three-or-four junctions as budget rises.
Minimax witnesses select one/two/three junctions, retain nominal score `0.963489/0.964789` and
reach robustness `1.0/1.0`. Minimum per-regime/cap nominal and robust headroom are `0.025202`
and `0.022677` absolute efficiency. These are reduced-order same-model anchors, not certified
device efficiencies, materials, manufacturing results or autonomous discovery.

Wave-6 admission SHA-256
`db6e13dbb5f15e846df247389ef6e9d155ebabf964ad1b082165c13ab6a7541a` recommends one
candidate. Certification v51
(`ad6435882ae0120c3adc8e4b0d5836152c9517402f405331decf26906ede4f32`) records 57
packages at `7/38/12`, or 45 internally admissible tasks. A concurrent security v34 attempt
(`994035a893a6ec175de18a71b1eb128f4ececdeb0d853c02a2cb15c91fc2b3ee`) is retained as
failed evidence because one 0.5-second timeout-classification regression failed under concurrent
CPU-heavy audit load. The isolated test and full serial security v35
(`8cad6e2868f71f644e7ae48cc1c4894348539d73310e0df7774517ae74907a5e`) pass, including
all 18/18 adversarial tests. The 57×2 baseline v40
(`4515392a29ffae58ae3cb224f091d2d53250b80ce30aa747a23b3cbd936f36c8`) reports 57/57
deterministic, valid and fail-closed tasks with zero infrastructure failures. Full-suite v8
(`240e51812a71e0d18f0d410b8f1596c43e482d98a46e9af4ed79cdaf0cc788e6`) passes 404/404
in 1247.653 seconds. All passing closeout reports bind clean source `0c0ca5e`; GPT-5.5 task
calibration was run only after this task closeout.

## 2026-07-25 — PhotovoltaicTandemDesign-v1 GPT-5.5 calibration and analysis

Three trusted GPT-5.5 reports bind clean model source `e57bb68`: budget one (SHA-256
`6402d412916e5d4b252a1d5b7a4a483cfe2c6b0a070f5b8e6c1dac34f5b607c5`), normal budget
three (`581a668727b27a4d621ebf3bb6b2f057595098b98478d706f709183a22428aaa`) and frozen-
parent budget three (`07d3a6d37afa04791eac0dc38b17cf9857be70f77e561a3cf131fb08438538f2`).
Budget one reaches development/held-out nominal `0.994571/0.993728` and development/held-out
robustness `0.862800/0.806769`, using `0.996735/0.998258` of the fabrication cost.

The normal budget-three trajectory is runtime-invalid → `0.974838` → `0.993821`; both valid
proposals are accepted, and the selected artifact reaches held-out nominal `0.989500` and
development/held-out robustness `0.827879/0.814356`. The frozen-parent trajectory scores
`0.999926`, runtime-invalid and `0.942996`; offline selection keeps the first proposal, whose
held-out nominal and development/held-out robustness are `0.999878` and `0.898214/0.824565`.
Across all three conditions, five of seven proposals are valid, two have sanitized
`candidate_runtime_error`, and none has an infrastructure failure.

Normal and frozen-parent budget three both use four oracle calls, but use 20,192 versus 16,723
tokens and 249 versus 660 seconds. Azure exposes no server-side generation seed, their prompt and
parent histories differ, and each condition contains one run. Their ordering is therefore
descriptive rather than a feedback-effect estimate. All three selected programs use nearly the
full fabrication cost, but the sealed shifts alter physical performance rather than the cost
constraint. The observed cost use does not explain the robustness gap, and this task does not yet
implement shifted cost-overrun or constraint-margin axes.

The trusted derived analysis (SHA-256
`e938f0bc635ec1569a2276a9041995ee957eeb89248db008dc5a48a5e8658607`) binds clean analysis
source `744ea3a`. It verifies report and raw-trajectory hashes, runtime/source/LLM-condition
equivalence, normal and frozen-parent lineage, proposal accounting, sealed science axes and
narrow fixed-world/evaluator-term scans of retained best artifacts. The task runtime is unchanged
between the model and analysis revisions. These same-model detailed-balance results support task
and model calibration only, not feedback causality, population performance, material/device
performance, manufacturing validation or autonomous scientific discovery.

Cross-task summary v26 (SHA-256
`4be6c33217f6b3655e8c1571b34064a7818be813eaf8f53bc9d8b86091997051`) binds clean source
`3df0877` and validates 65 normal single-run conditions across 33 tasks. It adds photovoltaic
budgets one and three; strict open-loop diagnostics remain task-specific and heterogeneous science
axes are not averaged.

## 2026-07-25 — CatalystDeactivationLab-v1 admission, calibration and analysis

`Catalysis/CatalystDeactivationLab` adds a procedural reduced-order laboratory with instrument
gain/offset drift, four finite catalyst coupons, at most three irreversible reactions per coupon,
out-of-order batch completion and exact request-retry idempotency. Stale parents, conflicting
retries, concurrent use of one coupon, exhausted samples and excess physical acts fail closed.
Every observation binds laboratory, coupon, calibration and intervention lineage. Candidates
estimate Arrhenius kinetics, deactivation and drift, refuse abrupt-drift or two-site worlds when
appropriate, and submit a fresh-batch operating policy.

The trusted task calibration (SHA-256
`cacf003aab1c8f36bd7d16011808865a4d49be4fbf589aeeec0797089a8624c7`) binds clean source
`2c5e654`. Independent numerical integration agrees with the closed-form product calculation to
`6.35e-12` and exactly reproduces post-reaction activity at the reported precision. The
truth-blind reference reaches development/held-out nominal `0.958034/0.951263` and robustness
`0.883174/0.942773`. It covers every supported world, refuses every unsupported world, has zero
false discovery, uses 12 physical acts, four out-of-order batches and one exact retry per world,
and records no duplicate physical acts or stale-parent attempts. These are synthetic task anchors,
not measurements from a catalyst, reactor or instrument.

Wave-7 admission (SHA-256
`42c6bcaba5c834f2e955e11f6b7ff64653cbcdb33dee784a3b11f3d1c4122a14`) recommends the task as
one candidate. Certification v52
(`df55cffc973ace7e61df9f671d35d72b1563301acacd1e3900a5715a00c36b78`) records 58 packages at
`7/39/12`, or 46 internally admissible tasks. Security v36
(`a253bf99e8bbbb1f49ca32b6b7a326594cd0456dd96b3a5a2634eda257193bb9`) passes 18/18 tests.
Baseline v41 (`7e860be9b068b30175146605b589a5304e37b221dad5548ae55dca1971697c60`) reports 58/58
deterministic, valid and fail-closed tasks over two repetitions with no infrastructure failure.
Full-suite v9 (`8b1462c7055967dee35f4d91fe02c73e4fc05d7b8c567a3d20dcc8401a9364c6`) passes 420/420 in
1273.775 seconds. All five closeout reports bind clean source `2c5e654`.

Three trusted GPT-5.5 reports also bind `2c5e654`. Budget one (SHA-256
`f80636dff17df315898f1b9b6b2de88104587b9b72a3ffac38d84c754899ec0e`) produces one valid
proposal that uses five physical acts and three reactions, refuses every world and remains at
zero. The normal budget-three trajectory
(`5039e9c4a219477d1e909bca19498cc98d8423f5879d40df2e6e46e57972e338`) scores
`0.072976 → 0.075190 → 0.071403`; steps one and two are accepted. Its selected artifact reaches
development/held-out mechanism `0.146052/0.300539` and prediction `0.000337/0.167796`, but has
zero development decision score and robustness. It covers every supported world while refusing
none of the unsupported worlds, yielding false-discovery rates `0.40/0.333`.

The frozen-parent budget-three run (SHA-256
`9c93ff62a965bc0795fb5631c1181d18d321bab9096b7d257b379546a22dc466`) contains one invalid
submission, a selected proposal at `0.041417` and one valid all-refusal proposal at zero. The
selected proposal has the same coverage/refusal and false-discovery pattern as the normal
selection and is the only selected model artifact that processes out-of-order batches. No valid
model proposal exercises exact retry. Normal and frozen-parent use four oracle calls but consume
25,260 versus 18,417 tokens and 450.77 versus 137.50 seconds. Each condition has one run, Azure
provides no server-side generation seed and their histories differ, so the contrast is descriptive
rather than a feedback-effect estimate.

The trusted derived analysis (SHA-256
`387d54463a9255439b8549fe41c3edd54623af676279b133e228792159d2c27e`) binds clean analysis
source `b9bdf63`. It verifies the three reports, raw trajectories, manifests, online-incumbent and
frozen-parent lineage, task/runtime hashes, proposal accounting, all eight world records and
retained best/terminal source scans. Across seven proposals, six are valid, one is an
`invalid_submission`, four have nonzero score, two are valid all-refusal policies and none has an
infrastructure failure. Five proposal source bodies are retained and scan clean; two intermediate
sources are available only through candidate, parent, report and raw-trajectory hashes.

Cross-task summary v27 (SHA-256
`72c259ab05a9ff559401b044a1c86c1e84e74bceace6d0a68365cf541d8ee4dc`) binds clean source
`e76ac03` and validates 67 normal single-run conditions across 34 tasks. It adds catalyst budgets
one and three. The frozen-parent diagnostic remains task-specific, and heterogeneous science axes
are not averaged. None of these reports supports a population, feedback-causal, physical-catalysis
or autonomous-discovery claim.

## 2026-07-25 — QuartzCrystalMicrobalanceLab-v1 admission, calibration and analysis

`Sensors/QuartzCrystalMicrobalanceLab` adds a deterministic reduced-order raw-instrument pipeline.
Each world contains two complex calibration captures and nine quantized I/Q sweeps over harmonics
1/3/5 and deposition times 0/20/40 seconds. Candidates must recover linearly drifting complex
gain/offset, fit BVD resonance and Q, infer Sauerbrey mass and rate, predict 60-second mass, commit
a target-mass stop time, and distinguish supported rigid deposition from viscoelastic/rate-change
model mismatch and I/Q-conjugation/ADC-clipping instrument faults. Returned conclusions bind
immutable calibration and sweep evidence IDs.

The trusted task calibration (SHA-256
`c594b912264c97ef320aebdd5eae64fc0717c72391790960d5e49b1c9c391b68`) and wave-8 admission
(`348499ff163e01db5cdc37ecd0054f9e05563258b5e7717a8543c5d181b2f4e2`) bind clean source
`c49f514`. Independent peak/half-power checks agree with nonlinear BVD fits; maximum recoverable
complex-calibration offset error is 2.057 counts and gain relative error is `2.90e-4`. Missing-data
supported worlds recover, physical anomalies and instrument faults separate, both sealed rate and
Sauerbrey axes affect the counterfactual, malformed/nonfinite/fabricated evidence fails closed and
each world receives a fresh candidate process. The truth-blind reference reaches
development/held-out nominal `0.995228/0.996343` and robustness `0.940278/0.949282`, with full
supported coverage, unsupported refusal and fault diagnosis and zero false discovery. These are
synthetic task anchors, not physical QCM, film or material measurements.

Three trusted GPT-5.5 reports also bind `c49f514`: budget one (SHA-256
`36aa87922f22665b4be7511f629055ed21bf17d7d405f475c029a6d69bbaf3bf`), normal budget three
(`b3ac43274b4b0dece51e079085b268200c63d4ae035168562f166b65a8345dc0`) and frozen-parent
budget three (`7bb471bde4ca16c7a6bbf61ebffc67cf04b7a2160967ff99ea9319fd3304d094`). All seven proposals
are submission-valid but score zero, so all three conditions retain the weak baseline. Five
proposals refuse every supported world. One normal proposal claims every world, covers all
supported worlds but refuses no unsupported world and has development/held-out false-discovery
rate `0.5/0.5`. One frozen-parent proposal covers two of three development supported worlds but no
held-out supported world, with held-out false-discovery rate 1.0. Every proposal has zero normalized
calibration, extraction, mechanism, prediction and decision score.

Normal and frozen-parent budget three both use four oracle calls, but consume 18,662 versus 17,797
tokens and 140.87 versus 137.51 seconds. Each condition contains one run; Azure exposes no
server-side generation seed and the prompt/parent histories differ. Equal zero outcomes therefore
do not identify a feedback effect. The trusted derived analysis (SHA-256
`543133a8c855add9923a1773fa21cc409f6b6cf7d609d2b47b8dc86b346447ad`) binds clean analysis
source `e516d56`; it verifies report/raw-trajectory/manifests, online and frozen-parent lineage,
all ten world records, accounting and retained best/terminal source scans. Three proposal source
bodies are retained and scan clean; four intermediate sources remain bound only by hashes and
metrics.

Certification v53 (SHA-256
`43a08634712135fab2bee49fae5be57df07b3abce92cd177a3c1613fb867c6d3`) records 59 packages at
`7/40/12`, or 47 internally admissible tasks. Security v37
(`cbb6a69c4bd57780afeeec4ca278eca9b10b8b091c081759f111c2be44da5685`) passes 18/18 tests.
Baseline v42 (`41b89e401f11cefefeb73371f83a3b5cbbb2c629e7c1e798e9706ebb8293706b`) reports 59/59
deterministic, valid and fail-closed tasks over two repetitions with no infrastructure failure.
Full-suite v10 (`d1f2f4cd7bb4a96b0f70bdd5535ba0bb627347308ec1f2b85170543d302a353b`) passes 438/438 in
1272.433 seconds. These four reports bind clean analysis source `e516d56`.

Cross-task summary v28 (SHA-256
`940495a9cb64e717e6395b3cb7e4ec1d8d5b8d13232618a05c43e20f68edded4`) binds clean source
`577e66a` and validates 69 normal single-run conditions across 35 tasks. It adds QCM budgets one
and three; the frozen-parent diagnostic remains task-specific and heterogeneous science axes are
not averaged. None of this evidence supports a population, feedback-causal, physical-instrument,
thin-film, material or autonomous-discovery claim.

## 2026-07-26 — ForceFieldCalibration-v2 active-hypothesis evidence

ForceFieldCalibration-v2 replaces the remaining generic trigonometric clone with twelve
procedural three-particle energy/force worlds. The public library contains Mie 12-6 and Morse
pair laws; Buckingham, Axilrod–Teller three-body and temperature-dependent interactions require
refusal. Every query preregisters Mie/Morse/unsupported weights and a monotone retained set. The
first query is restricted to one near-equilibrium equilateral configuration, while later distance,
geometry and temperature choices determine hypothesis retention and information gain.

The trusted calibration (SHA-256
`d2f1a433bae7d2c1a5c1682095180d560301dc49d611eacd30b3a8589b622324`) and wave-9 admission
(`b02fa9e9837240b39e0867313b9bdff97eacd91bca90356c634a897968ebd933`) bind clean source
`0f8a43d`. The truth-blind reference reaches development/held-out nominal
`0.964178/0.949851` and robustness `0.964290/0.949894`. It selects every supported family,
refuses every unsupported world, covers every registered 90% parameter interval, retains the
true hypothesis and has zero false discovery. Independent energy/force invariance and
second-virial/Boyle checks pass. These are reduced-order calibration anchors, not molecular
dynamics, a material potential or a thermodynamic measurement.

Three GPT-5.5 reports also bind `0f8a43d`: budget one (SHA-256
`c5c9ad78f25981fc44433e30aa5d8f8483abb6151ff3642b13a42dbae6d828f9`), normal budget three
(`7224e6bae131be535e9ecc2e085334a291d40ff8d00b483f1b37e5795019de76`) and frozen-parent
budget three (`a992b903a2c594eefde7a37a36049cf4a0e4618d07517c3e5691e4b78f78f442`). All seven
proposals are invalid, so every condition retains the valid zero-score baseline. One proposal
reaches all twelve worlds using three query calls and eleven configuration units per world but
returns invalid submissions. Five proposals have the sanitized `candidate_runtime_error` class,
and one has `blocked_or_missing_import`. None is an infrastructure failure.

The trusted derived analysis (SHA-256
`1f5f6af3e437eb949f3a5075673ba1122ef61f9fffc2b4734b9d2d160d171360`) binds clean analysis
source `74d59f7`. It verifies reports, raw trajectories, manifests, checkpoints, summaries,
online-incumbent and frozen-parent lineage, source hashes and failure accounting. Three terminal
proposal bodies are retained and parse without evaluator/world shortcuts; the blind terminal
source contains the invalid `scipy.optimize.quad` import. Four intermediate proposal bodies are
not retained, so their hashes and sanitized classes do not justify narrower diagnoses.

Certification v54 (SHA-256
`85442a20c031ddeed988e41b471a2d337d1bf0e729cf9dd615288f01331b3ce4`) records 59 packages at
`7/41/11`, or 48 internally admissible tasks. Security v38
(`b0fe56708f6679f0a2dcbdbed6682191f7312bc5f8614c6c624a5eb372e86e16`) passes 18/18 tests.
Baseline v43 (`3d1632568568cb2c8784edf44e0a821d6f0f9994d7dcd741291c6988a7082a56`) reports 59/59
deterministic, valid and fail-closed tasks over two repetitions with no infrastructure failure.
Full-suite v11 (`156f7468d9067c4677bedf5c164f71f1384ead1b1aba3f53463497e0f3d37616`) passes 459/459 in
1444.069 seconds. These four reports bind clean task source `0f8a43d`.

Cross-task summary v29 (SHA-256
`851fdac2bd9f24b69c7b5d6c75009c9b8d4209e902600cb44e4707290e208d0f`) binds clean source
`22f1519` and validates 71 normal single-run conditions across 36 tasks. It adds ForceField
budgets one and three; the frozen-parent diagnostic remains task-specific and heterogeneous
science axes are not averaged. The one-run normal/blind comparison is descriptive rather than
causal, and none of this evidence supports a physical or autonomous-discovery claim.

## 2026-07-26 — AlloyHardnessOptimization-v1 DOI-held replay evidence

AlloyHardnessOptimization-v1 replaces the polynomial pseudo-material task with the Borg et al.
MPEA hardness compilation (article DOI `10.1038/s41597-020-00768-9`, Figshare v9 DOI
`10.6084/m9.figshare.12642953.v9`, CC BY 4.0). The frozen builder retains 358 eligible
room-temperature records from 1,545 rows. It forms a leakage-free historical proxy from 197
recipes and 44 DOI studies, reserves nine cross-DOI exact-recipe records for confirmation, and
uses 65 recipes in thirteen later target DOI studies. A SHA-256 citation split fixes eight
development and five held-out studies. Ridge alpha 100 is selected only by equal-study-weight
leave-one-DOI-out error on the historical pool.

The trusted calibration (SHA-256
`4698c739038ab32d6258096d21f26d1ddb2501f8f4b4ff3c121c77ad2c8943c7`) and wave-10 admission
(`d5c5d1e4dcdf75b24a7a2863c1c5efb53994dd88aabfd6d03574871220eeac61`) bind clean source
`52dcec0`. The frozen two-assay truth-blind policy reaches development/held-out utility
`0.657516/0.877774` and prediction `0.670267/0.652544`. Fresh-process, fail-closed and metric-
sealing checks pass. Only six of 65 target recipes have an exact composition/process record from
another DOI, and these records are not controlled replicates. The task is a retrospective public-
data replay, not prospectively preregistered alloy synthesis, mechanical validation or discovery.

Three GPT-5.5 reports also bind `52dcec0`: budget one (SHA-256
`01cca0c342aec5027e05d56d5b162abe66382f8b3c8f4869a5d9e2632db7d750`), normal budget three
(`54faaf56551f1e1a2c18f13fc7f5051342cbb984df22b43e3caf0b340f665ff6`) and frozen-parent
budget three (`96ebf5a214041f53de8edb974f08b61cd5e4f0dd194cedaf03c36ea7a2584209`). All seven
proposals are protocol-valid and run all thirteen worlds. The selected artifacts are source-
distinct, each reaches development score `0.151632`, and each has held-out utility zero.
Their prediction scores are `0.818232/0.753396`, `0.800608/0.739175` and
`0.803644/0.739619`, with unit interval coverage. Selected exact-recipe confirmation coverage is
only `0.0833/0.0667`; development and held-out confirmation MAE are `79.23/144.60 HV`.

The trusted derived analysis (SHA-256
`a893054dce58713069fd657e9d894e53cd02a014864f9fa614052bab182ff12b`) binds clean analysis
source `e98d3fe`. It verifies calibration/report hashes, raw trajectories, manifests,
checkpoints, online/frozen-parent lineage, source-scope equivalence, retained-artifact shortcut
scans and deterministic re-evaluation. It also freezes two selection-axis counterexamples. Normal
step one is rejected at development score zero despite held-out utility `0.159906`; the selected
step has held-out utility zero. Frozen-parent steps one and two tie at `0.151632`, but step two has
higher development/held-out prediction and narrower intervals at the same unit coverage; the tie
policy retains step one. These facts show information loss under one development scalar, not a
feedback effect.

Certification v55 (SHA-256
`d0d827c172512eb6be002cee5386cc874e77631f7f01a3e266b9b637a80c6193`) records all 59 packages
at `7/42/10`, or 49 internally admissible tasks. Security v39
(`7ab659cce470e67c4767d2a041d0f763f852556dcb74650e1628c2b4e3fcea43`) passes 18/18 tests.
Baseline v44 (`416a607a6fbb26ef44b55df9ed21ca8f9c993fbc5f0cb0b4ad34dd2500b9cd29`) reports 59/59
deterministic, valid and fail-closed tasks over two repetitions with zero infrastructure failures.
Full-suite v12 (`1f3d2048858c496fdfe58b4748fd7bea7b5954718c64e96f91f8b303da3122e1`) passes 479/479 in
1525.927 seconds. These four reports bind clean source `52dcec0`.

Cross-task summary v30 (SHA-256
`50f9bdd2023b082d22baa2b26eaed7af78606da6a8de5a4e59475a406a676584`) binds clean source
`e98d3fe` and validates 73 normal single-run conditions across 37 tasks. The frozen-parent run
remains task-specific. Normal and frozen-parent budget three match four oracle calls and 5,502
input tokens but use 13,720/14,822 total tokens, different prompts and different source artifacts;
the endpoint exposes no server-side generation seed. No feedback-causal, population, prospective
synthesis, mechanical-validation or autonomous-discovery claim is supported.

## 2026-07-26 — DiffractionGratingDesign-v2 RCWA evidence and 50-task closeout

DiffractionGratingDesign-v2 replaces the scalar phase FFT proxy with a five-layer,
one-dimensional Fourier-modal Maxwell solver. The six worlds span four development and two
held-out material/wavelength families, TE/TM polarization, three wavelengths, three angles and
four sealed etch/overlay/index/angle shifts. The trusted task calibration (SHA-256
`ea8e74b609fca6c4d01a6f7ca75861d71babdc22260c7a7d5cb2abbcae2ab4d6`) binds clean source
`e920e1c`. Minimum reference headroom is `0.265762` nominal and `0.246092` under shifts;
order-13 versus order-19 utility differs by at most `0.001697`, and the largest per-condition
efficiency difference is `0.015535`. Uniform-interface Fresnel limits and lossless energy
conservation pass.

The pinned independent `grcwa 0.1.2` cross-check (SHA-256
`4ca80525aed02cf613b60a5cc94ba632c51335057def94b3b7794f413671f8dc`) covers 72
baseline/reference center-wavelength conditions. Maximum, mean and 95th-percentile absolute target
efficiency differences are `0.007846`, `0.001688` and `0.005837`; both implementations conserve
energy within the registered tolerances. This is independent software agreement within the RCWA
method family, not physical experimental validation.

Three trusted GPT-5.5 reports bind clean source `aa92618`: budget one (SHA-256
`706f940f044ddd17fe023d20a4e107b38a6f91af575a3b979ff7400f269d42b9`), normal budget
three (`b6d7b7b16cb2b5faf91b18c16a166ea44a2abbc24896e4f8a5da67225aa436eb`) and frozen-parent
budget three (`493fe7298973b15ba09d5566c7fe734d92a82543c7d21b02298494affd3a718f`). Six of seven
proposals are invalid: four execute only on the three titania development worlds, and two fail on
all six worlds. Frozen-parent step two is the only nominally valid proposal and reaches
development/held-out `0.187130/0.173008` with development robustness `0.108832`. Both held-out
worlds have at least one infeasible sealed-shift geometry, so held-out robustness is zero.

The trusted derived analysis v2 (SHA-256
`c5bfe01b7a6d63f69720e1763f625577c938dc467a9c5e153b0885302260ac4e`) binds clean
analysis source `108322f`. It verifies both task-calibration reports, all three model reports, raw
trajectories, manifests, online/frozen-parent lineage, retained source scans and deterministic
re-evaluation. Normal and frozen-parent budget three match four oracle calls and 2,523 input tokens
but use 11,902/11,437 total tokens, different prompts and different source artifacts; Azure exposes
no server-side generation seed. Their ordering is descriptive rather than feedback-causal.

Cross-task summary v31 (SHA-256
`b3b3983423f1978b3ddf63fe73f3a34f41eb9a450190fdd7a4c78a0b88028c32`) binds clean source
`4be5d4d` and validates 75 normal single-run conditions over 38 tasks. The frozen-parent RCWA run
remains task-specific and heterogeneous science axes are not averaged.

Certification v56 (SHA-256
`e47aec74fc1959e844460a9edf3cd56517fa2775467174e2391544753a6ebefe`) records 59 packages at
`7/43/9`, or 50 internally admissible tasks, with no missing or orphaned records. Security v40
(`a7b329cbbc3cdac33f201f19a320a87d1f96fa3fe9d8469c6d9146d26b831c60`) passes 18/18.
Baseline v45 (`e626a29071c88fdd58b0997ea956209b35ca63867fcd4f695327fa67a96287e9`) reports 59/59
deterministic, valid and fail-closed tasks over two repetitions with zero infrastructure failures.
Full-suite v14 (`d1035f77fe561c9243693e75667b7810f04e27297cf91a353d4ab1a7c152e8b5`) retained a clean
negative run with 496/499 passing: three RCWA assertions required exact zero although supported
NumPy/LAPACK builds leave an `O(1e-16)` normalization residue. After replacing exact-zero gates
with a `1e-12` tolerance, full-suite v15
(`e84103a1d3606329cd457f074f5351c5f283cb07040cbb46f2677cc0458e37b4`) passes 499/499 in
1843.875 seconds on clean source `108322f`.

The 50-task count is an internal admission milestone, not evidence that the tasks are externally
certified or that GPT-5.5 made a scientific discovery. DiffractionGratingDesign-v2 remains a
computational candidate pending repeated paired controls, server-held regimes, independent
full-wave replication, fabrication, optical measurement and photonics review.

## 2026-07-26 — preregistered four-condition feedback measurement pilot

The v3 preregistration (SHA-256
`13278d14205209c3e904212597fce800b81e32b7e3eb1eabf26c9d7faf870b02`) freezes source
`ae6090f`, two tasks, four feedback modes, two local replicate identifiers and three proposals per
cell. Full-suite v18 (SHA-256
`d624bb9a3568849676c0dc2598c7929e1215390db05e4291eac972d45d61c35d`) passes 519/519
tests, and protocol smoke v3 (`d5bc921af2b9eb8010a8187bf2fad5632b61e46115b7b31993b598f34a96c7a6`)
passes all eight zero-budget mode-by-identifier cells before nonzero-budget execution.

The raw pilot (SHA-256
`5e543cdfd36bc560b6f79601c1ab92dec6ecd3f2457abdb46a6d878c034cf15f`) completes all
16/16 scheduled cells with no failed or recovered attempt. All 48 provider usage records are
complete. ActiveLawDiscovery has 24/24 evaluator-valid proposals; DiffractionGratingDesign has
9/24, for 33/48 overall. Full-horizon best scores for identifiers 0/1 are `0.797390/0.798314`,
`0.760925/0.798230`, `0.998551/0.797921` and `0.796497/0.793914` for ActiveLaw normal,
score-only, delayed-replay and selection-blind modes. The corresponding Diffraction scores are
`0.077897/0.198820`, `0.320060/~0`, `0.090693/0.195027` and `0.244893/~0`.

The strict derived analysis (SHA-256
`dbb392acb89fe36da243765f8be92a55ad1039e7c2b9cbc8e0930559e2c4aa5e`) validates every
prompt hash/byte count, parent and delayed-release rule, manifest, checkpoint, retained source,
schema-v2 trajectory, science axis and common-token calculation. Common total-token horizons are
14,395/14,472 for ActiveLaw and 11,491/10,663 for Diffraction; full cell totals span
10,663--22,937. Resource matching changes several reported endpoints, and Diffraction condition
directions reverse between identifiers. The evidence therefore calibrates the measurement
pipeline and allows design of a later Track F study, but identifies no causal feedback or
population effect, supplies no model ranking or cross-task science score, and does not demonstrate
autonomous scientific discovery. Confirmatory Track F still requires a new preregistration, at
least ten independent runs per condition, precision and multiplicity planning, fresh or
server-held worlds, and independent scientific validation. The narrative claim audit is in
`.research/feedback_measurement_pilot_findings_2026-07-26.md`.

Post-pilot security audit v41 (SHA-256
`d2082abe9a2f23604a426fc831126b548374d5a9c4ea5a5a00c4c9c60e1dcb8e`) binds clean source
`08ec441` and passes all 18 adversarial tests in 10.805 seconds. This refresh covers the current
four-condition runner and analyzer source without changing the preregistered runtime scope.

## 2026-07-27 — measurement-health allocation

The task-maturity audit now retains condition-specific proposal counts, observed first-valid
run rates, valid-proposal rates and floor/ceiling mass. These are descriptive observations, not
provider-side probability estimates: most cells contain one run and the Azure endpoint exposes
no generation seed. The v4 maturity ledger still records 59 packages at `7 certified / 43
candidate / 9 quarantined`, 50 internal admissions and zero open-release, externally validated
or long-horizon-ready tasks.

The first measurement-health allocation classifies the inventory as `7 exploratory long-horizon
screen / 24 repair-first / 17 saturated-on-ramp / 2 control-only / 9 quarantined`. The frozen
exploratory screen contains ElectrolyteConductivityDesign, DiffractionGratingDesign,
RNAInverseDesign, MOSFETDoping, TrussWeightMinimization, HeatExchangerDesign and RANSCalibration.
ActiveLawDiscovery is retained separately as a mechanism/refusal and feedback-protocol control;
the repeated common-token analysis did not identify a normal-feedback advantage.

No task passes the complete measurement-health gate, and no task is eligible for a confirmatory
cohort. Fixed-artifact noise, evaluator resolution and materiality, baseline/reference
separation, shortcut resistance and material post-2h headroom remain unmeasured. Moreover, the
seven-task screen was chosen after inspecting current GPT-5.5 outcomes, so it may allocate a
sentinel-complete 2h pilot but cannot double as an unbiased confirmatory cohort. The next study
must freeze sentinel capture, retain a random tranche through 12h, and choose confirmation tasks
independently of these outcomes. The full allocation and claim limits are recorded in
`.research/measurement_health_allocation_2026-07-27_v1.md` and the corresponding machine-readable
audit.

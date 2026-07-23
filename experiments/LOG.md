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

# Frontier-Science plan gap audit

Audit date: 2026-07-19 (UTC), with the experiment roadmap extended on 2026-07-21 after a
full-text EdgeBench comparison. Evidence base: `literature_matrix.md`,
`science_experiment_plan.md`, current source/tests, and the dated artifacts in `experiments/`.

## Executive decision

Keep the expansion freeze. P0 integrity and a narrow P1 certification gate are now
implemented, but the project has not passed the empirical evidence gate needed for a benchmark
release. The defensible current description is:

> A research prototype for cross-domain, executable, budget-constrained scientific generative
> optimization, with a seven-task internally certified core and a larger
> quarantined/candidate inventory.

Do not call simulator-score improvement “autonomous scientific discovery.” Reserve that claim
for work that separately demonstrates feedback learning, mechanism recovery, hidden-shift or
physical validation, and auditable claim–evidence provenance.

## As-built matrix

| Capability | Status on 2026-07-19 | Evidence | Remaining acceptance criterion |
|---|---|---|---|
| Candidate/oracle isolation | Implemented | Clean-revision report `f48b101`; 15/15 security/regression tests; Bubblewrap, no network, read-only mounts, resource/seccomp limits, typed RPC | Reproduce in clean Linux CI; document portability/non-Linux behavior |
| Fail-closed trusted metrics | Implemented | Clean-revision 50×2 run: 50 deterministic, 49 valid, 50 fail-closed; non-finite Climate oracle rejected | Repair or quarantine every invalid candidate oracle before certification |
| Task admission policy | Implemented, narrow | Current manifest: 7 certified / 18 candidate / 25 quarantined; Pendulum-v2 is restored as a nominal-vs-robust candidate | Independent domain + evaluator reviews are still declarations, not completed external review |
| Scientific validity of inventory | Partial | Seven core tasks have citation IDs/invariants; 25 packages are quarantined after clone, numerical, identifiability, SNR, provenance, normalization or shortcut audits | Deep audit the remaining 18 candidates; hidden/generated instances and shortcut analysis |
| Unified trajectory/accounting | Implemented, protocol-smoked | Clean-revision two-seed baseline smoke; trajectory schema v2, hashes, AUC over `budget_units`, separate `oracle_calls`, wall/token/cost, seed, checkpoint/resume | Validate nonzero-budget schema-v2 artifact replay in CI and version future changes |
| Prompt-metric none/shuffled controls | Implemented, unrun | Code and unit smoke; summaries disclose that selection still uses true scores | Add selection-blind controls, then run ≥5 paired seeds with preregistered budgets |
| Evaluator-only metric sealing | Implemented and integration-verified | Closed search-visible allowlist; search-state redaction/hash-keyed sidecars; 65-test suite; clean pinned OpenEvolve/TreeQuest/Shinka no-leak report `aff026d` | Extend from baseline smoke to nonzero-budget upstream runs before comparative claims |
| Official OpenEvolve adapter | Implemented, trusted baseline smoke | Explicit 0.2.26 adapter; clean-revision secure baseline passed under Python 3.10 | Run nonzero-budget/checkpoint integration and multi-seed study |
| TreeQuest AB-MCTS | Implemented, trusted baseline smoke | Real TreeQuest AB-MCTS-A ask/tell adapter; clean-revision secure baseline passed under Python 3.12 | Run nonzero-budget/checkpoint integration and multi-seed study |
| ShinkaEvolve | Implemented, trusted baseline smoke | Official runner/database adapter at pinned commit; clean-revision secure baseline passed under Python 3.10 | Run nonzero-budget/resume integration and token accounting audit |
| Classical/domain baselines | Missing | None | Random/quasi-random plus BO/CMA-ES/DE and one domain heuristic where meaningful |
| Multi-seed benchmark evidence | Missing | Keyless GPT-5.5 Responses path now passes smoke; trusted one-seed budget-one core, SCM and candidate calibration reports exist | Certified-core report with uncertainty and raw trajectories |
| Multifidelity/Pareto | Missing | Plan text only | At least one certified proxy/exact task with rank-correlation calibration; objective vectors/hypervolume |
| Feedback learning claim | Missing | Controls exist but no causal result | Structured feedback must beat shuffled/no-feedback under paired repeated runs |
| Mechanistic discovery | Missing | Outcome scores only | Separate equation/causal artifact score and intervention generalization |
| Validation/distribution shift | Calibration-level | Pendulum-v2 budget-three diagnostic: visible development 0.691→0.854 while shifted robustness 0.641→0.639; single seed and non-sealed adapter feedback | Paired repeated hidden-shift studies plus independent high-fidelity or physical confirmation and abstention cases |
| Research-integrity track | Partial | Immutable candidate/parent hashes and artifacts | Hypothesis–test–evidence records, failed branches, claim links and calibrated refusal |

## What the latest literature changes

The literature matrix separates four capabilities that the old plan collapsed:

1. **Optimization.** Frontier-Eng, AlphaEvolve, FunSearch and ShinkaEvolve justify executable,
   verifier-guided search, but also require real population/tree baselines and deep trajectories.
2. **Feedback learning.** LEAP and lab-in-loop feedback results make best-so-far AUC and
   shuffled/no-feedback controls necessary; terminal score alone cannot show learning.
3. **Scientific discovery.** CausaLab, CARTOGRAPH, DiscoveryWorld and recent epistemic-trace
   studies distinguish objective success from mechanism recovery, falsification, calibrated
   stopping, and response to model misspecification.
4. **Research integrity.** Xcientist/XScientist-style work and long-horizon systems motivate
   immutable lineage, failed branches, evidence links, and re-execution—not score-only logs.

EdgeBench adds a strong long-horizon comparator: its 134-task study motivates dual local/judge
feedback loops, evaluator-only trajectory snapshots, continuous-run versus restart controls,
context/memory ablations, and explicit curve forecasting. It does not replace shuffled or
strict selection-blind controls, and its aggregate best-so-far curves do not establish mechanism
recovery or independent scientific validation. The science-specific experiment matrix and
minimum publishable sequence are specified in `science_experiment_plan.md`.

`arXiv:2601.21165` also creates a direct naming collision: *FrontierScience* already denotes an
expert-authored Olympiad/Research question benchmark. Public release should rename this project
or make the executable-optimization qualifier unavoidable.

## Protocol corrections now reflected in code

- Primary/co-primary metrics are terminal best feasible score and best-so-far AUC over charged
  proposal/benchmark `budget_units`; actual trusted-oracle executions are reported separately as
  `oracle_calls`.
- Five seeds are the runner default; confidence intervals use Student-t rather than a normal
  approximation at small sample size.
- `greedy_rewrite` is not called OpenEvolve. Official framework names map only to genuine
  optional upstream implementations and fail explicitly when unavailable.
- Candidate scoring is framework-independent and always crosses the secure evaluator.
- Checkpoint/resume, seed, candidate lineage hashes, wall/token/cost fields, and raw traces are
  standard artifacts.
- Old 50-task and pre-sandbox results are `UNTRUSTED_PRE_SANDBOX` and cannot support claims.

## Remaining plan deficiencies

### 1. Only calibration-level empirical P2 evidence exists

The keyless GPT-5.5 Responses path was restored and trusted budget-one pilots now cover the
seven-task core, the SCM mechanism candidate and four additional candidates. They expose
one-step saturation and multiple oracle defects, but there are still no valid five-seed
certified-core trajectories, no paired feedback-control result, and no nonzero-budget official-
backend search run. The project must distinguish “calibrated at budget one” from
“experimentally validated” everywhere.

### 2. Optional frameworks lack one reproducible environment

The host default is Python 3.8, OpenEvolve/Shinka require ≥3.10, and current TreeQuest requires
≥3.11. Add a uv/lock-based matrix, pinned commits, and smoke CI. Upstream framework token usage
is not uniformly exposed; cost fields must state missingness rather than report false zeros.

### 3. Seven certifications are internal, not external validation

Task cards and invariant tests are a strong filter, but domain review has not been independently
performed. Matrix multiplication and Cap Set public-known instances have contamination risk;
add time-held-out or procedurally generated instances. Normalization anchors need dated,
reproducible witnesses, not prose claims.

### 4. LLM-only search is an inadequate baseline suite

Recent results show classical optimization can dominate LLM agents. Add random/quasi-random,
Bayesian optimization or CMA-ES/DE when the artifact admits parameterization, and a domain
heuristic. Compare within-task ranks/performance profiles rather than averaging arbitrary scores
as the only headline.

### 5. Optimization remains the only credible track

The old plan promises multifidelity, Pareto objectives and broad autonomous discovery without
implementations. Create an explicit capability ladder:

- **Track O — Optimization:** best feasible artifact + best-so-far AUC over charged benchmark
  budget units, with separate oracle-call accounting. Near-term release target.
- **Track F — Feedback:** normal vs shuffled/delayed/no feedback, paired seeds.
- **Track M — Mechanism:** predictive score separated from equation/causal recovery.
- **Track V — Validation:** proxy/exact generalization, hidden shifts, optional physical tests.
- **Track R — Integrity:** hypotheses, tests, evidence, failed branches, provenance and refusal.

Track O is the only track close to runnable benchmark status. Track F has unrun control
infrastructure and Track R has partial lineage artifacts; none has sufficient empirical evidence.
Do not aggregate these tracks into one “science” score.

### 6. P0–P2 completion is infrastructural, not a release claim

The five dated reports were regenerated from clean source revision `f48b101`: all report
`execution_passed=true`, `trusted_evidence=true`, and `passed=true`. This closes the local
implementation/evidence work scheduled for P0–P2, but the P2 performance gate remains open:
the protocol smoke has budget zero, and each official-backend smoke evaluates only one baseline.
Accordingly, “P0–P2 implemented and recorded” must not be shortened to “benchmark validated.”

## Revised TODO plan

### P0/P1 closeout — completed locally, reproduce in CI

- [x] Trusted oracle / isolated candidate architecture and adversarial regression suite.
- [x] Current 50-package deterministic secure baseline and certification audit; invalid Climate oracle fails closed.
- [x] Seven-task certified core, 18 candidates and 25 quarantined packages after wave-2,
  inverse-track and wave-3 audits, with Pendulum-v2 rebuilt and re-admitted.
- [x] Task-card/citation/invariant audit and dated machine-readable evidence.
- [ ] Add Linux CI reproduction of all dated audits (local clean-revision reproduction is done).
- [x] Quarantine `ClimateScience/EnergyBalanceModel`; replace its unstable, untraceable,
  underidentified formulation rather than patching it into an admissible task.

### P2a — reproducible protocol release

- [x] Unified trajectory schema v2, budget-unit AUC, separate oracle-call/cost fields, seeds,
  hashes, checkpoint/resume.
- [x] Greedy normal/none/shuffled prompt-metric modes and multi-seed statistics runner; scope is
  machine-readable and does not claim selection-blind feedback ablation.
- [x] Real optional OpenEvolve, TreeQuest AB-MCTS-A and ShinkaEvolve adapters.
- [ ] Add a locked Python 3.10/3.11 upstream environment and integration tests.
- [x] Restore a working, authorized LLM endpoint and record smoke metadata (keyless local
  Responses proxy; endpoint details remain git-ignored).
- [ ] Run ≥5 seeds on all seven certified tasks at 30/100/300 proposal/benchmark budget units;
  report the actual oracle-call counts separately.
- [ ] Publish raw trajectories, environment lock, paired uncertainty and performance profiles.

### P2b — missing controls

- [ ] Add random/quasi-random and parameterized BO/CMA-ES/DE baselines.
- [ ] Add at least one strong domain heuristic per certified task family.
- [ ] Audit upstream token/cost accounting and represent unavailable values as `null`/missing.
- [ ] Add direct one-shot LLM and restart-vs-depth allocation ablations.
- [ ] Add structural/behavioral diversity and genealogy-collapse diagnostics.
- [ ] Add adaptive allocation/stopping baselines (for example, SMC-style convergence control).
- [ ] Implement delayed-feedback controls and preregister paired Track F contrasts.
- [ ] Implement strict selection-blind controls (frozen/random parents or open-loop proposal
  batches); prompt masking alone cannot identify causal use of oracle feedback.
- [ ] Evaluate persistent scientific memory/world-model quality over long horizons, beyond
  checkpoint/resume correctness.

### P3 — scientific validity and distinctiveness

- [x] Implement separate development/validation/mechanism trajectory retention and default
  search redaction; do not reduce them to one “science score”. Clean pinned integration confirms
  `robustness_score` stays out of all three official backend search states while remaining in
  trusted trajectories.
- [ ] Independently review all seven core tasks and generate hidden/time-held-out instances.
- [ ] Define task-family/time-held-out splits for search-policy training and transfer studies.
- [ ] Add one certified proxy/exact multifidelity task with measured rank correlation.
- [x] Add one intervention-based mechanism task and separate mechanism score (SCM-v1 is an
  on-ramp: GPT-5.5 reaches 0.983 at budget one, so harder regimes remain required).
- [ ] Add misspecification/refusal cases and false-discovery penalties.
- [ ] Add calibrated confidence, active stopping, and unnecessary-experiment metrics.
- [ ] Add hypothesis–test–evidence/belief-update artifacts, explicit exploration DAGs,
  failed branches, falsification metrics, and replay checks.
- [ ] Add sequential-vs-parallel, tool-access, novelty, ensemble, and component ablations where
  the corresponding scaffold capability is claimed.

### P4 — release governance

- [ ] Resolve the FrontierScience naming collision before public release.
- [ ] Freeze license, data/model redistribution, contamination cutoff and refresh policy.
- [ ] Add human/domain-expert baselines and independent reproduction.
- [ ] Require high-fidelity or physical replication for every “discovery” claim.

## Go/no-go gates

- **v0.1-lite go:** all P2a items complete on the seven certified tasks, with no security or
  certification regression and at least one classical baseline.
- **Track F claim go:** normal feedback shows paired, repeated lift over strict selection-blind,
  shuffled and no-feedback controls—not only prompt-metric masking.
- **Discovery claim go:** the relevant system demonstrates feedback learning over controls,
  mechanism recovery or hidden-shift/intervention validity, independent high-fidelity/physical
  confirmation, calibrated stopping/refusal, and provenance review. Optimization-only results
  must remain labeled optimization.
- **Expansion go:** only after the certified core is empirically useful; directory count is not a
  milestone.

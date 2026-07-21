# Experiment trust manifest

This manifest is append-only provenance. It does not alter historical result payloads.

For dated trusted artifacts, `source_provenance.source_tree_dirty` must be `false`; the block also
records the exact Git revision, command and source scope used to produce the report.

The five dated artifacts below were regenerated from source revision `f48b101` and each records
`execution_passed=true`, `trusted_evidence=true`, and `passed=true`. The protocol/backend scopes
remain baseline-only and must not be promoted to model-performance evidence.

| Artifact | Trust status | Reason / replacement |
|---|---|---|
| `batch_evolve_results.json` | `UNTRUSTED_PRE_SANDBOX` | Historical 50-task run; candidate isolation was absent and the inventory no longer matches. Do not use as benchmark evidence. |
| `current_49_baseline_audit.json` | `UNTRUSTED_PRE_SANDBOX` | Historical one-pass baseline audit before the trusted sandbox. Superseded by `secure_baseline_determinism_2026-07-19.json`. |
| `security_audit_2026-07-19.json` | `TRUSTED_SECURE_EVAL` | 15 security/regression tests passed on clean source `f48b101`. |
| `task_certification_audit_2026-07-19.json` | `TRUSTED_CERTIFICATION_AUDIT` | Seven certified, 37 candidate, five quarantined; all admission checks pass for the certified core on `f48b101`. |
| `secure_baseline_determinism_2026-07-19.json` | `TRUSTED_SECURE_EVAL` | Two secure evaluations per inventory task on `f48b101`; 49 deterministic, 48 valid, 49 fail-closed. |
| `protocol_smoke_2026-07-19.json` | `TRUSTED_SECURE_EVAL / PROTOCOL_SMOKE_ONLY` | Baseline-only two-seed run on `f48b101` validating trajectory schema v2, budget-unit AUC, separate oracle-call accounting, and runner artifacts. It is not model-performance evidence. |
| `upstream_backend_smoke_2026-07-19.json` | `TRUSTED_SECURE_EVAL / UPSTREAM_BASELINE_SMOKE_ONLY` | On `f48b101`, official OpenEvolve 0.2.26 (Python 3.10), TreeQuest AB-MCTS-A (Python 3.12), and ShinkaEvolve at the pinned commit (Python 3.10) each evaluated the secure baseline with trajectory schema v2 successfully. |
| `inverse_candidate_admission_audit_2026-07-21.json` | `TRUSTED_ADMISSION_AUDIT` | On clean source `54f992d`, reproduces all seven inverse-track identifiability, signal-to-noise, surrogate-rank or missing-observation defects and recommends quarantine before model screening. |
| `task_certification_audit_2026-07-21_v3.json` | `TRUSTED_CERTIFICATION_AUDIT` | On clean source `54f992d`, records 50 packages: seven certified, 24 candidate and 19 quarantined, with no certified-task admission issues or orphaned manifest records. |
| `candidate_wave3_admission_audit_2026-07-21.json` | `TRUSTED_ADMISSION_AUDIT` | On clean source `e911639`, reproduces all six fail-open, topology, interface or normalization defects in the NMR/OED/gate/OPF/truss/antenna tranche. |
| `task_certification_audit_2026-07-21_v4.json` | `TRUSTED_CERTIFICATION_AUDIT` | On clean source `e911639`, records 50 packages: seven certified, 18 candidate and 25 quarantined, with no certified-task admission issues or orphaned records. |
| `candidate_wave3_admission_audit_2026-07-21_v2.json` | `TRUSTED_ADMISSION_AUDIT` | On clean source `2d2d62d`, verifies five remaining wave-3 defects and the OED-v2 rebuild: finite-output rejection, ten converged references, six development and four shifted-validation instances. |
| `task_certification_audit_2026-07-21_v5.json` | `TRUSTED_CERTIFICATION_AUDIT` | On clean source `2d2d62d`, records 50 packages: seven certified, 19 candidate and 24 quarantined after OED-v2 re-admission. |
| `gpt55_oed_v2_b1_2026-07-21.json` | `TRUSTED_SECURE_EVAL / CALIBRATION_ONLY` | GPT-5.5 reaches 0.990615 development and 0.993697 sealed shifted validation in one proposal on clean source `2d2d62d`; this establishes budget-one saturation, not a multi-seed leaderboard. |
| `candidate_wave4_admission_audit_2026-07-21.json` | `TRUSTED_ADMISSION_AUDIT` | On clean source `5187019`, reproduces all 12 fail-open, unreachable-anchor, missing-observation, uncoupled-system or degenerate-objective defects in the final unscreened tranche. |
| `task_certification_audit_2026-07-21_v6.json` | `TRUSTED_CERTIFICATION_AUDIT` | On clean source `5187019`, records the fully triaged 50-package inventory: seven certified, seven candidate and 36 quarantined. |
| `active_law_discovery_calibration_2026-07-21.json` | `TRUSTED_TASK_CALIBRATION` | On clean source `cd65c17`, always-abstain scores zero; exact laws/refusals and all stability checks pass; a generic active SINDy reference exposes a 0.721/0.394 development/validation mechanism gap and false discoveries. |
| `task_certification_audit_2026-07-21_v7.json` | `TRUSTED_CERTIFICATION_AUDIT` | On clean source `cd65c17`, records 51 packages: seven certified, eight candidate and 36 quarantined. |
| `secure_baseline_determinism_2026-07-21_v3.json` | `TRUSTED_SECURE_EVAL` | On clean source `cd65c17`, all 51 baselines are deterministic and fail closed, 50 are valid, and there are no infrastructure failures; the sole invalid task remains quarantined Climate EBM. |
| `gpt55_active_law_b1_2026-07-21.json` | `TRUSTED_SECURE_EVAL / CALIBRATION_ONLY` | Budget-one GPT-5.5 reaches 0.796 development, 0.745 sealed validation mechanism and near-perfect rollout, but falsely claims both misspecified worlds; clean source `cd65c17`. |
| `gpt55_active_law_b3_2026-07-21.json` | `TRUSTED_SECURE_EVAL / CALIBRATION_ONLY` | Independent budget-three GPT-5.5 run on clean source `cd65c17`; later proposals do not beat 0.711 development and none fixes the development/validation misspecification false discoveries. |
| `gate_synthesis_v2_calibration_2026-07-21.json` | `TRUSTED_TASK_CALIBRATION` | On clean source `236d8cd`, an independent nominal GRAPE witness reaches numerical unit fidelity on all six targets while sealed hardware scores 0.957/0.984; finite/bound checks and unitary invariants pass. |
| `candidate_wave3_admission_audit_2026-07-21_v3.json` | `TRUSTED_ADMISSION_AUDIT` | On clean source `236d8cd`, verifies OED-v2 and GateSynthesis-v2 rebuilds plus four remaining quarantines. |
| `task_certification_audit_2026-07-21_v8.json` | `TRUSTED_CERTIFICATION_AUDIT` | On clean source `236d8cd`, records 51 packages: seven certified, nine candidate and 35 quarantined. |
| `secure_baseline_determinism_2026-07-21_v4.json` | `TRUSTED_SECURE_EVAL` | On clean source `236d8cd`, all 51 baselines are deterministic/fail-closed, 50 are valid, and infrastructure failures are zero. |
| `gpt55_gate_v2_b1_2026-07-21.json` | `TRUSTED_SECURE_EVAL / CALIBRATION_ONLY` | Budget-one GPT-5.5 reaches 0.999872 nominal development and 0.999992 held-out policy but only 0.956894/0.983037 sealed hardware robustness; clean source `236d8cd`. |
| `gpt55_gate_v2_b3_2026-07-21.json` | `TRUSTED_SECURE_EVAL / CALIBRATION_ONLY` | Independent budget-three run on clean source `236d8cd`; nominal saturates at numerical unity, development robustness rises 0.966531→0.974567, and held-out robustness remains near 0.9845. |

Raw `.out`/`.log` files predating the trusted evaluator inherit
`UNTRUSTED_PRE_SANDBOX` unless a dated trusted report explicitly incorporates them.

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

Raw `.out`/`.log` files predating the trusted evaluator inherit
`UNTRUSTED_PRE_SANDBOX` unless a dated trusted report explicitly incorporates them.

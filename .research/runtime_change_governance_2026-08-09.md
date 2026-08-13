# Runtime changes on this branch and what they invalidate

Date: 2026-08-09. Branch: `feat/community-oracle-tasks`.

This branch modifies the trusted runtime. The project deliberately fails closed on that, so this
note records exactly what changed, what it breaks, and what the project's own machinery expects
before the branch is merged. **It is not a request to relax any guard.**

## What changed in the trusted runtime

| File | Change | Why |
|---|---|---|
| `sle/secure_eval.py` | resolve candidate site-packages for the candidate interpreter; per-task candidate package allowlist | under any search-backend venv the sandbox mounted no numpy at all, so every such candidate failed |
| `sle/benchmark_layout.py` | two domains added to the discipline table | unavoidable when adding tasks in new domains |
| `sle/llm.py` | chat max-tokens parameter name is now a config field | reasoning models reject `max_tokens` on the chat wire |

## Full-suite state

681 tests, 21 failures and 1 error before the fixes below; `tests.test_secure_eval` passes and
`scripts/run_security_audit.py` passes 23/23 with `trusted_evidence: true`, so the sandbox itself
is intact. The failures group into three kinds.

### 1. Live-inventory counts — fixed

The inventory legitimately grew from 59 packages to 61 and from 50 internally admitted to 52.
Guards updated in `test_benchmark_layout`, `test_certification`, `test_task_cards`,
`test_task_maturity`, `test_measurement_health`. Frozen-study guards were deliberately left
alone: the GPT-5.6 census preregistration still pins 50 tasks and the Track F scripts still pin
an inventory of 59, because those describe completed studies. Both still pass.

### 2. Overclaimed maturity metadata on the new task cards — fixed

`test_task_cards.test_schema_two_maturity_metadata_is_machine_readable` caught two genuine
errors in the new cards rather than a problem with itself:

- `frozen_before_eval: true` stopped being accurate the moment GPT-5.6 results drove task edits.
- `lineage.status: complete` overclaimed, with no registered calibration artifacts and no
  external review.

Both corrected to conform. The guard's real protection — that no task can quietly upgrade its own
maturity claim — is preserved intact.

### 3. Runtime immutability — **open, and a governance decision**

`tests.test_runtime_migration` **passes at the base commit `74b9d93` and fails on this branch**.
That attribution is clean. It pins the trusted runtime byte-for-byte:

- `test_layout_runtime_unit_is_unchanged_at_current_revision` requires `benchmark_layout.py`,
  `registry.py` and `spec.py` to be identical to a pinned legacy revision. Adding a domain
  changes `benchmark_layout.py`, so **this guard fires for any new task in a new domain**.
- `test_source_and_none_path_contracts_are_exact` pins `evaluate.py`, `secure_eval.py` and
  `trusted_driver.py`. Its diff already lists all three as changed between its pinned base
  `20c6b780` and HEAD, but the module passed at `74b9d93`, so the pre-existing two are covered by
  an approved migration and `secure_eval.py` is the new unregistered change.

This is the provenance system working as designed: frozen analysis artifacts carry a
`runtime_source_sha256`, and changing the runtime unbinds them. The project already has the
remedy — `experiments/trusted_context_runtime_migration_audit_*.json`, and `_binding_state`
accepts `migration_replayed` — so the expected step is to register a runtime migration recording
base and target revisions and replaying the affected analyses.

Registering that migration is a re-certification of the trusted runtime and should be a
deliberate decision, not something done in passing. It is left open.

**Not attributed.** Several per-task analysis-binding tests also fail
(`test_rans_analysis`, `test_diffraction_grating_analysis`, `test_alloy_hardness_analysis`,
`test_protein_stability_analysis`, `test_electrolyte_conductivity_analysis`,
`test_demographic_sfs_analysis`, `test_calorimeter_analysis`,
`test_force_field_hypothesis_analysis`, `test_alloy_hash_order_migration`). They plausibly fail
for the same runtime-binding reason, but this could not be confirmed: they read `runs/` paths
recorded as absolute paths into the original checkout, so they error out in a clone or worktree,
and the runtime files could not be swapped in place while experiments were running against the
live harness. **Treat their attribution as unknown until checked on a quiet repository.**

## Suggested order before merge

1. Verify the unattributed analysis tests on a quiet checkout, at base and at this branch.
2. Decide whether the runtime change is accepted. If yes, register a runtime migration audit and
   replay the affected analyses; if no, the sandbox fix cannot ship and the search backends stay
   unusable.
3. Only then register the new tasks' measurement evidence in the maturity ledger. Groundwork is
   done: both task contracts have had zero contract-path commits since their runs began, and each
   run records its own `task_contract_sha256`.

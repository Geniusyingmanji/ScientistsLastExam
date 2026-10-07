# Discovery frontier eligibility

Discovery task scores and frontier eligibility answer different questions. A
historical evaluator can still produce a valid score after its task loses the
ability to distinguish frontier models. Its package and historical results are
preserved; it is excluded from frontier claims until a reviewed successor exists.

The policy is executable in `sle/discovery_eligibility.py`, with decisions in
`sle/conf/discovery_eligibility.yaml`. It is enforced inside
`promote_frontier_receipt`, including when the CLI uses `--allow-uncertified`.
That flag permits historical evaluation; it does not permit frontier promotion.
The discovery admission report also includes the current package eligibility,
version binding, and a separate `frontier_claim_eligible` decision without
rewriting historical scientific axes or rescaling scores.

The maturity audit records these holds under `discovery_exclusion`, separately
from `quarantine_reaudit` for broken scientific oracles. A full-score observation
does not prove an oracle defect. Actual oracle-defect quarantines still require
current reproduced-defect evidence; a discovery exclusion must instead match its
reviewed package and supporting policy evidence. Neither kind enters the current
internal admission set, and the report counts both evidence kinds separately.

## Exclusions dated 2026-09-18

| Task | Status | Evidence supporting exclusion |
|---|---|---|
| SurvivorshipConfoundedDesign | `retired_saturated` | Six of six first proposals reached 1.0 under the recorded gpt-5.6-terra condition; GPT-6's first proposal also reached 1.0. |
| EnzymeKineticsLaw | `retired_saturated` | Existing task card declares frontier saturation after Opus calibration; GPT-6's first proposal scored 0.991915. |
| PTAHellingsDowns | `quarantined_shortcut` | Direct four-template SSE comparison reaches the ceiling without uncertainty margins/bootstrap; GPT-6's first proposal scored 1.0. |
| AMOCTippingRefusal | `quarantined_shortcut` | A no-experiment historical-feature rule reaches full score. The model's all-abstain zero is not evidence of difficulty. |
| LookElsewhereAnomaly | `quarantined_provisional` | One GPT-6 first proposal reached 1.0; repeated difficulty remains unmeasured. |
| BlackBoxGroupIdentification | `quarantined_provisional` | One GPT-6 first proposal reached 1.0; repeated difficulty remains unmeasured. |

All six have certification status `quarantined`. Historical packages are still
addressable with `find_task(..., include_uncertified=True)` or the CLI's
`--allow-uncertified`. The independent frontier gate also blocks direct promotion
calls. A discovery cell cannot evade it by labelling its task as optimization.

The policy binds the reviewed packages from commit
`d2a571dafbe92e59e97fc1b777f52abe72634db8`. GPT-6 results were collected earlier at
`a2907479ae895336f5894488e25b8fd501072743`, with `gpt-6-astra`, low reasoning,
streaming, and one first proposal per task. They are screening evidence, not a
new-main rerun or a population saturation estimate. The private aggregate is
identified by SHA-256 in the policy; no hidden world values or private traces are
copied into the repository. Prior enzyme calibration has the degraded source
provenance documented by its task card. A reference program alone scoring 1.0
does not justify adding an exclusion.

## Re-entry and new versions

Every discovery task without a reviewed qualification defaults to
`calibration_required`, including a newly named v2. This does not quarantine all
historical candidates or prevent their development; it blocks claims that their
difficulty is established. A hold follows the task ID even when its files change.
An explicitly qualified task loses qualification if its package hash changes.

Qualification is a reviewed policy decision, not an automatic reward threshold.
The `qualified` record must bind the exact `task_package_sha256` and identify a
reviewer, review date, repository-relative calibration artifact, and that
artifact's SHA-256. The artifact uses schema version 1, repeats `task_id` and
`task_package_sha256`, links supporting evidence under `evidence_refs`, and reports
these `qualification_checks` as boolean true:

- `scientific_validity`: the problem remains identifiable within its information
  and experiment budget, with explicit refusal on genuinely ambiguous worlds.
- `degenerate_controls_below_ceiling`: no-observation, constant-answer, blanket
  refusal, and unsupported-claim controls have measured behavior; invalid runs
  are not scored as successful defenses.
- `repeated_frontier_calibration`: repeated draws under recorded model conditions
  and budgets establish a distribution, separating invalid candidates from
  scientific failures.
- `independent_confirmation_worlds`: final confirmation uses frozen hypotheses
  and worlds/data not used to choose the design or tune the candidate.
- `process_result_verification`: experimental evidence supports the claimed
  mechanism and independently checked result; trace structure alone is insufficient.
- `material_headroom`: current models leave meaningful scientific progress to
  measure; more noise or a score rescale is not accepted as added difficulty.

The gate verifies the review and artifact bindings and rejects incomplete checks;
it does not claim to machine-verify the reviewer's scientific judgments. There
are no newly qualified discovery tasks in this policy change. Optimization tasks
are outside this policy and retain their existing certification and frontier gates.

```sh
python scripts/report_discovery_eligibility.py
python scripts/report_discovery_eligibility.py --task PTAHellingsDowns
python -m sle list --quarantined
```

See [discovery discrimination](discovery_discrimination.md) for the repeated
first-proposal evidence and [frontier families](frontier_families.md) for immutable
wave and verified-receipt requirements. Both gates must pass; eligibility does
not replace run verification, scientific review, or fresh confirmation.

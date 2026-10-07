# Task admission and calibration workflows

The contribution gate now distinguishes structural validity, runtime checks, the declared
shortcut guard, and model difficulty. A passing shortcut guard is not a scientific admission
or certification decision. New model draws and paired feedback experiments are still required.

## Contribution gate

```bash
python scripts/check_task_contribution.py --task MaterialsScience/PhaseDiagramDiscovery \
  --skip-eval --output /tmp/phase-structure.json
```

Exit codes: **0** = all contribution checks executed and passed; **1** = a check failed;
**2** = incomplete (including skipped evaluation, legacy migration, or unmeasured declarations).
`checks[].ok` is `null` for checks that did not establish a result. `phases.structural`,
`phases.runtime`, and `phases.shortcut_guard` report their own status. `phases.difficulty`
is always `unassessed`: this gate does not replace a model calibration or delta ladder.
Repeated infrastructure failures do not establish deterministic scoring.

The 85 tasks present at main `f9c05b65` are explicitly listed in
`schemas/shortcut_probe_migration.json` as **pending**. This list prevents an undocumented
legacy omission from being confused with a new task missing its contract. It never awards
a pass or silently exempts a task from difficulty measurement. Remove a task after the
contract and its measured declarations have been reviewed. New tasks are not automatically
added. The FourSetting task's existing pairing probe is identified there, and an exact
regression executes its valid unpadded form; its reference measurement and complete contract
migration remain pending.

A task card declares candidates and expected measurements:

```yaml
shortcut_probe:
  schema_version: 1
  metric: combined_score
  reference:
    candidate: verification/reference_solver.py
    expected_score: null
  probes:
    - id: cheap_solver
      candidate: verification/shortcut_probe.py
      expected_score: null
  relative_margin: 0.1
  score_tolerance: 0.000001
```

The machine-readable schema is `schemas/shortcut_probe.schema.json`. Every path is relative
to the task package, must exist, and must remain inside the package after symlink resolution.
Reference and probes must be distinct candidate programs exposing the task's entrypoint.
They are evaluated through `evaluate_candidate`, using the same candidate sandbox as other
submissions. The gate does not execute an author-supplied driver script in the oracle process.
It evaluates each twice, requires a valid finite result and identical full metrics, and checks
all supplied expected scores against the task-card declaration. An invalid shortcut cannot
establish that a task is difficult. An infrastructure failure cannot masquerade as zero.

`null` is explicitly unmeasured. A run with null declarations reports observations but remains
incomplete; recording/reviewing those observations in the task card is a separate change.
The gate never edits the card or trusts a probe to state its own expected score.
When declarations match, it requires a positive reference and:

```text
max(probe scores) < measured_reference * (1 - relative_margin)
```

The margin is an explicit task-review decision; the template's 0.1 is a starting point, not a
universal scientific threshold. It is bounded above by a policy ceiling of 0.3, the widest
margin a card may declare without a separate review decision: without a ceiling,
`relative_margin: 0.999` leaves a threshold of `0.001 * reference`, and any probe that scores
at all clears the guard. A wider margin means raising the ceiling with a review record, not
sliding the bar inside an ordinary card change. Probe families should cover the omissions
claimed by the reference and reviewer-discovered cheap alternatives. Existing prose in
`known_shortcuts` is historical context; the gate checks numeric declarations in
`shortcut_probe`, not numbers extracted from prose. Reviewers must reconcile both when
migrating a card.

`excluded` is not an exemption from measurement. The gate evaluates excluded candidates
against the same reference and threshold as the declared probes, because the case that
motivated the key - a strong in-tree candidate argued away instead of evaluated - is exactly
the one a reason alone cannot catch. An excluded candidate that *scores* at or above the
threshold fails the contract. An excluded candidate that comes back invalid is accepted: that
is infeasibility by construction, which is what makes such a program unusable as a probe,
since a probe must be a valid finite-scoring candidate.

## Independent first-draw calibration

Create a plan without calling any model:

```bash
python scripts/calibrate_task.py --task QuantumFoundations/FourSettingMomentCertificate \
  --llm-config sle/conf/llm/local.claude.yaml --seeds 0,1,2 \
  --workdir /tmp/sle-calibration/runs --plan /tmp/sle-calibration/plan.json \
  --output /tmp/sle-calibration/preview.json --dry-run
```

The default is one `selection_blind` proposal per seed. A seed identifies a local replicate;
it does not control the provider's random draw. Model configuration is explicit. Plans record
the model condition hash, task contract/package hashes, runtime hash, orchestration source
hash, source revision, timeouts, budget mode, ordered cohort grid, and every expected cell.
No credential or full LLM configuration is copied into the plan. `llm_config` records only
the operator's local config path; readable model name and hashed conditions identify the run.

Plans are created exclusively and hash checked on reread. To change an experiment, create a
new plan and run root. Existing plans reject planning flags instead of silently replanning.
Task-card updates and scientific evidence freezing are separate operations.

After reviewing the plan, actual model calls are an explicit command:

```bash
python scripts/calibrate_task.py --plan /tmp/sle-calibration/plan.json \
  --output /tmp/sle-calibration/result.json --execute
```

Execution requires a clean known source revision on Linux, unchanged plan bindings, and the
candidate sandbox and scientific dependencies required by `batch_evolve.py`. It delegates to
that runner without changing its budgeting/feedback behavior. It does not install dependencies,
refresh frozen evidence, promote a task, or alter old manifests. `--resume --execute` delegates
resume to the batch runner, which also validates the original experiment configuration.

## Paired delta ladder

```bash
python scripts/run_delta_ladder.py --task QuantumFoundations/FourSettingMomentCertificate \
  --llm-config sle/conf/llm/local.claude.yaml --seeds 0,1,2 --budgets 3,5,8,10,12 \
  --workdir /tmp/sle-delta/runs --plan /tmp/sle-delta/plan.json \
  --output /tmp/sle-delta/preview.json --dry-run
```

Each budget is an independent cohort with matching `normal` and `selection_blind` cells.
Proposal counts exclude the baseline. Feedback-condition order uses the batch runner's fixed
`reverse_parity` design. To measure seconds, supply `--budget-mode active_wall`, explicit
`--budgets` in seconds, and `--proposal-cap N`. Hitting that cap before the time horizon remains
incomplete. Proposal-based admission reports are unavailable for a seconds-based campaign;
the workflow never relabels proposal cuts as seconds.

Replay recorded results without an API call:

```bash
python scripts/run_delta_ladder.py --plan /tmp/sle-delta/plan.json \
  --output /tmp/sle-delta/replay.json --replay --reports /tmp/sle-delta/reports
```

Replay uses the fixed cell grid, batch configuration, run manifests, raw trajectories and their
batch snapshot hashes. It validates task/model/runtime identity, expected budget, recorded
acceptance, and incumbent replay. Missing runs, failed attempts, damaged files, mismatched
versions and shortened runs are represented explicitly. It uses the latest attempt, counts all
scheduled cells in the denominator, and leaves a paired delta null unless both arms completed.
A full-budget mean delta is null unless every planned pair completed. Selected discovery metrics
remain attached to each run and are not combined into a scalar quality estimate. Reported usage
is the latest run's reported usage; it is not a total of superseded/failed provider attempts.

`--reports` optionally runs the existing admission criterion, heldout discovery triple, and
discovery admission report CLIs only after all planned proposal cells complete and the run tree
contains exactly the scheduled manifests. Their outputs remain separate from the campaign's
completeness and paired-budget table. The existing admission reporter uses its own supported
proposal cuts and rules; its output is not an automatic task-card update. A failed auxiliary
report is explicitly recorded. Dry-run previews include all batch/report commands for review.

All plan/replay outputs have `scientific_admission: not_assessed` and `trusted_evidence: false`.
They are operator artifacts to inspect alongside independently validated references, shortcut
results, scientific axes, task/source rights and model calibration. They are never represented
as newly generated frozen benchmark evidence.

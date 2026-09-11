# Frozen first-proposal calibration handoff, 2026-09-12

Status: **not executed; model configuration missing**. This is an execution
runbook, not a completed model plan or admission evidence. Both existing splits
are construction-exposed. External domain review and fresh server-held instances
remain separate requirements.

## Preregister before the first provider call

Use a clean Linux checkout of the final PR source. Record Python/NumPy/SciPy,
thread limits, task/runtime hashes and the model's complete decoding condition.
The reference is `verification/reference_fit.py`; the development objective,
300-second evaluator limit, experiment cap and fixed shortcut/ability plan are
already explicit in the task card and `references/revision_replay.json`.
Reproduce the frozen reference on the same host/environment as the model draws;
retain both complete private metric records and bind their candidate/source hashes.
Do not transplant a historical reference score across a changed task or environment.

Use the real operator configuration path for CALIBRATION_CONFIG. Never use the
public example as if it identified an available model. Provider identity and
output/reasoning budgets must be frozen before execution, with no retries to
select a weaker answer. Seed labels 0/1/2 label three independent requests; they
do not control the provider's random draws. Each gets exactly one proposal.

The following commands run from the checkout; CALIBRATION_ROOT must name a new
private directory outside the checkout, inaccessible to the proposal agent.

```sh
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
: "${CALIBRATION_CONFIG:?Set the path to the real model configuration}"
: "${CALIBRATION_ROOT:?Set a new external private run directory}"
umask 077
mkdir -m 700 "$CALIBRATION_ROOT"
python3 scripts/calibrate_task.py --task Neuroscience/NeuralReportAttribution \
  --llm-config "$CALIBRATION_CONFIG" --seeds 0,1,2 --budgets 1 --timeout 300 \
  --workdir "$CALIBRATION_ROOT/runs" --plan "$CALIBRATION_ROOT/plan.json" \
  --output "$CALIBRATION_ROOT/planned.json" --dry-run
```

Inspect the plan's hashes, model condition and three selection-blind cells. Once
these match the intended frozen condition, execute the same immutable plan:

```sh
python3 scripts/calibrate_task.py --plan "$CALIBRATION_ROOT/plan.json" \
  --output "$CALIBRATION_ROOT/executed.json" --execute
python3 scripts/calibrate_task.py --plan "$CALIBRATION_ROOT/plan.json" \
  --output "$CALIBRATION_ROOT/replay.json" --replay
```

## Interpret the actual first proposal

Campaign `complete` means the scheduled cells were recorded, not that D16 passed.
For every seed retain the actual step-1 candidate, provider response, usage,
manifest, trajectory and evaluation receipt, including invalid or timed-out draws.
Compare the step-1 score against the same-source complete reference, not the
best-so-far endpoint, which can substitute the baseline for a rejected proposal.
Inspect full private development AND heldout validity: public `valid` deliberately
covers only development and cannot establish whole-evaluation validity.

For this predeclared three-draw campaign, report D16 as unresolved unless every
scheduled first proposal is valid on every world and strictly below the complete
reference development score. Any valid proposal reaching/exceeding reference is
a difficulty failure; an invalid proposal is not a valid low-score sample. Report
each outcome, not only the mean or the weaker draws. Preserve every historical
failure. Do not infer hard difficulty, iterative gains or independent domain
validity from this one-proposal check; the other admission requirements still apply.

Publish only aggregate scores, validity counts, environment/model conditions and
source/artifact hashes. Full world records, responses and candidates remain in
the operator's private evidence store. Keep lineage incomplete until real records
exist, and leave maintainer certification/global evidence refresh to the maintainer.

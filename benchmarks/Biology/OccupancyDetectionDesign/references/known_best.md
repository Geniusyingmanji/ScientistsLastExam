# OccupancyDetectionDesign reference results

All values in this file are produced by task-local code. Run:

```bash
python benchmarks/Biology/OccupancyDetectionDesign/verification/analysis.py
python benchmarks/Biology/OccupancyDetectionDesign/frontier_eval/run_eval.py \
  --candidate benchmarks/Biology/OccupancyDetectionDesign/verification/reference_solver.py \
  --metrics-out /tmp/occupancy-reference.json
```

## Reference

The truth-blind reference surveys every site rapidly, spends the remaining budget on balanced
intensive revisits, maximizes the standard marginal occupancy likelihood, and compares the
linear habitat model with quadratic-habitat and transect-spatial alternatives using BIC.
Calibration values are filled from a clean Linux revision before submission.

## Model draws

No model draw has been run yet. The task will remain a candidate.

## Baseline

The legal baseline makes four rapid surveys and reports a fixed positive effect. Its calibrated
score is recorded after the first clean-revision evaluation.

## Difficulty ladder

`verification/analysis.py` measures the complete reference, no-intensive-revisit, reduced-site,
no-model-comparison, and never-refuse variants.

## Shortcut probe

The task-local analysis sweeps fixed sign/prevalence summaries that do not fit the latent
occupancy likelihood. Results are recorded before model calibration.

## Construction findings

The public contract was written before model calibration. Any scoring, budget or difficulty
change triggers a fresh baseline/reference/ablation replay.

## Robustness

The final package must show deterministic complete metrics, exact zero for blanket abstention,
fail-closed malformed candidates, and a clean-revision Linux audit.

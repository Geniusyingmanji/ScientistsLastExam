# OccupancyDetectionDesign reference results

All values in this file are produced by task-local code. Run:

```bash
python benchmarks/Biology/OccupancyDetectionDesign/verification/analysis.py
python benchmarks/Biology/OccupancyDetectionDesign/frontier_eval/run_eval.py \
  --candidate benchmarks/Biology/OccupancyDetectionDesign/verification/reference_solver.py \
  --metrics-out /tmp/occupancy-reference.json
```

## Reference

The truth-blind reference selects 24 habitat-stratified sites, pairs rapid and intensive surveys,
uses the final 12 units for a third visit, and compares the linear model with quadratic-habitat
and transect-spatial alternatives using BIC. Continuous estimates are a fixed 50/50 shrinkage of
the marginal occupancy likelihood estimate and the raw detection-slope estimate.

| metric | development | held out |
|---|---:|---:|
| normalized mechanism | **0.795577** | 0.787752 |
| effect accuracy | 1.000 | 1.000 |
| habitat-effect score | 0.640 | - |
| mean-occupancy score | 0.607 | - |
| false-discovery rate | 0.000 | 0.000 |
| correct-refusal rate | 1.000 | 1.000 |
| supported coverage | 1.000 | 1.000 |

The reference is not a ceiling. Its fixed shrinkage weight, BIC threshold and site allocation are
not optimized per world, leaving continuous effect and occupancy headroom below 1.0.

## Model draws

One `greedy_rewrite` calibration run per model used seed 17, a three-proposal budget, temperature
0.7, and explicit `chat_thinking: disabled`. DeepSeek v4 Flash produced one valid proposal out of
three and reached 0.381693 development / 0.000000 held out; its two invalid proposals were one
candidate runtime error and one timeout. DeepSeek v4 Pro produced three valid proposals and
reached 0.310287 / 0.000000. Neither first proposal reached the 0.795577 reference. The compact,
credential-free record is `experiments/occupancy_detection_design_deepseek_calibration_2026-09-07.json`.

An earlier draw for each model is excluded from performance evidence because all proposals used an
ambiguous nested-versus-integer method-cost representation and failed at runtime. That draw
triggered the public-contract correction described below. The task remains a candidate.

## Baseline

The legal baseline makes four rapid surveys and reports a fixed positive effect. It is valid on
every world and has `combined_score = 0.000000`, with false-discovery rate 0.8.

## Difficulty ladder

| strategy | development | held out | false discovery | refusal | coverage |
|---|---:|---:|---:|---:|---:|
| fixed shrinkage reference | **0.795577** | **0.787752** | 0.000 | 1.000 | 1.000 |
| raw-detection estimate only | 0.765634 | 0.726880 | 0.000 | 1.000 | 1.000 |
| occupancy likelihood only | 0.680809 | 0.567110 | 0.000 | 1.000 | 1.000 |
| 20 stratified sites | 0.549528 | 0.432313 | 0.167 | 1.000 | 1.000 |
| 32 sites with fewer revisits | 0.374474 | 0.806373 | 0.286 | 0.750 | 1.000 |
| no intensive surveys | 0.118457 | 0.416167 | 0.333 | 0.500 | 0.667 |
| no model comparison | 0.128910 | 0.000000 | 0.400 | 0.000 | 1.000 |
| never refuse | 0.128910 | 0.000000 | 0.400 | 0.000 | 1.000 |
| blanket abstention | 0.000000 | 0.000000 | 0.000 | 1.000 | 0.000 |

Paired methods identify detection, broad habitat coverage identifies effect direction, and model
comparison supplies the refusal capability. Too much breadth removes repeats and raises false
discovery even where held-out parameter estimation happens to improve.

## Shortcut probe

The task-local analysis evaluates 432 policies over site count, repeat method, effect threshold,
alternative-model threshold, slope multiplier and prevalence offset. They use only detection
fractions and ordinary correlations, never a latent occupancy likelihood. The best reaches
**0.754093** development and 0.562726 held out, below the reference on both splits.

## Construction findings

The 24-site version was rejected because too few latent Bernoulli states made reference recovery
unstable. Expanding to 48 sites with a proportional 84-unit budget made both supported effects
and model inadequacy identifiable. A second rejected design made rapid surveys too informative,
allowing rapid-only repetition to beat the intended paired-method analysis. The final method
contrast restores the value of intensive revisits. The shortcut sweep then exceeded the initial
likelihood-only reference, motivating the fixed shrinkage estimator before any scored model draw.
An excluded protocol draw then exposed an ambiguous public representation of method costs: model
candidates treated the documented costs as integers while the callback supplied nested mappings.
The public value was simplified to the documented integer mapping before scored calibration; this
did not change the worlds, costs, observations, or scoring.

## Robustness

Consecutive reference evaluations are key-identical. The baseline and blanket abstention are
valid and exactly zero. Overspend remains invalid even if candidate code catches the callback
exception; malformed outputs and fabricated evidence IDs fail closed. Clean-revision Linux audit
results are recorded after the final task package is committed.

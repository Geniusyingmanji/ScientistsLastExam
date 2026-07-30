# Seven-task two-hour exploratory result

Status: complete derived audit. This is a result-selected, single-trajectory-per-task exploratory screen, not confirmatory evidence.

## Execution and evidence

- All 7/7 scheduled cells reached the declared 7200-second active-wall horizon with no infrastructure failure, retry, or protocol-incomplete outcome.
- The audit replayed every trajectory, evaluation receipt, run manifest, checkpoint, sentinel artifact, evaluator payload, and provider-response hash.
- 1033 proposals were made; 790 were evaluator-valid (76.5%). Provider usage was 7740876 total tokens; pricing was not configured.

## Task-specific outcomes

| Task | Online best | 30m→120m | Valid proposals | Held-out | Robustness | Terminal | Signed endpoint | Materiality |
|---|---:|---:|---:|---:|---:|---|---|---|
| Electrochemistry/ElectrolyteConductivityDesign | 0.9402 | 0.000000 | 133/133 | 0.9334 | 0.6851 | valid 0.9402 | commit | fail |
| Optics/DiffractionGratingDesign | 0.6055 | 0.445506 | 46/85 | 0.5653 | 0.5864 | invalid 0.0000 | commit | pass |
| RNAEngineering/RNAInverseDesign | 1.0000 | 0.000039 | 75/76 | 0.9996 | 0.9994 | valid 0.8416 | abstain | pass |
| Semiconductor/MOSFETDoping | 0.7877 | 0.005322 | 179/180 | 0.7792 | 0.8166 | valid 0.6642 | commit | fail |
| StructuralEngineering/TrussWeightMinimization | 0.0525 | 0.000000 | 2/201 | 0.2004 | 0.3008 | invalid 0.0000 | commit | fail |
| Thermodynamics/HeatExchangerDesign | 0.8583 | 0.003196 | 69/72 | 0.6479 | 0.4468 | valid 0.8489 | commit | fail |
| Turbulence/RANSCalibration | 0.6682 | 0.012410 | 286/286 | 0.4278 | 0.3887 | valid 0.6665 | commit | pass |

The online incumbent clears the frozen task-specific operational materiality contract on 3/7 tasks. The terminal workspace artifact clears it on 1/7; signed committed artifacts clear it on 1/6 commits. These are local benchmark thresholds, not external scientific validation.

## Endpoint audit

The runner's terminal sentinel records the last workspace artifact published by the cutoff. The preregistration labels one endpoint `terminal_in_horizon_incumbent`; these are not the same policy. In all seven tasks the terminal workspace artifact differs from the online incumbent, so this report retains the online incumbent, terminal workspace artifact, signed decision, and observer envelope separately.

Five of seven terminal workspace artifacts are evaluator-valid. The last in-horizon signed actions are six commits and one abstention. Signed actions were made before their own evaluator result and were recorded under forced continuation, so they are not score-aware autonomous stopping outcomes.

## Claim boundary

The result supports a complete, hash-bound two-hour exploratory measurement record. It does not estimate population model performance, identify a feedback effect or scaling law, demonstrate post-two-hour headroom, establish a confirmatory scientific result, complete external/physical validation, or demonstrate autonomous scientific discovery. The preselected Diffraction, Electrolyte and HeatExchanger 12-hour tranche remains unexecuted.

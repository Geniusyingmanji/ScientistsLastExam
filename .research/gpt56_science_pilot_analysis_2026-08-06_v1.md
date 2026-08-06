# GPT-5.6 science pilot analysis

This is a four-task, single-identifier calibration, not a 50-task model ranking, causal feedback study, external validation, or autonomous-discovery result.

## Outcome

The pilot passes its protocol-health, challenge, discrimination and anti-saturation gates. It does **not** show that short-horizon online feedback outperforms frozen-parent best-of-batch generation.

| Task | normal best | blind best | valid proposals | diagnosis |
|---|---:|---:|---:|---|
| `DynamicalSystems/ActiveLawDiscovery` | 0.761849 | 0.997892 | 6/6 | mixed near ceiling in one condition |
| `Optics/DiffractionGratingDesign` | 0.066049 | 0.661339 | 6/6 | clear non saturated scientific headroom |
| `MolecularDynamics/ForceFieldCalibration` | 0.000000 | 0.000000 | 0/6 | unresolved due to execution hurdle |
| `Sensors/QuartzCrystalMicrobalanceLab` | 0.000000 | 0.000000 | 4/6 | clear zero science score among executable proposals |

Across 24 proposals, 16 were valid (66.7%). Failure kinds were `{"candidate_runtime_error": 5, "invalid_submission": 3}`.

## Interpretation

- ActiveLaw is scientifically meaningful but has a near-ceiling open-loop draw; its normal selected artifact still makes misspecification false discoveries.

- Diffraction is the cleanest scientific-difficulty case: every proposal executes, yet nominal and sealed robustness outcomes remain widely separated.

- ForceField is dominated by executable-contract failures, so zero cannot be read as resolved evidence about force-field reasoning difficulty.

- QCM retains four executable proposals with zero calibration/extraction/mechanism/prediction/decision score, which is a substantive scientific-pipeline failure; two additional proposals are invalid submissions.

The tasks fit an RSI/self-evolving study at the level of revising executable scientist policies under sealed evaluation. This pilot does not establish persistent skill acquisition, weight updates, recursive self-improvement, or scientific discovery.

## Leakage and provenance

All 24 proposal prompts were reconstructed exactly. The runtime saw only Task.md, public constraints, the parent program, proposal slot and the closed public metric allowlist. Certification, broad physical discipline, historical scores and sealed science metrics were absent. Every selection-blind parent was the frozen baseline.

Raw report SHA-256: `ccb005a14f566e75e7d3924d3756a763d4d3ba62fad687e5c48cf3ab6c437916`.

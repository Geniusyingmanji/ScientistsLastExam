# Seven-task measurement-health preflight

This report separates evaluator mechanics from scientific materiality and fails closed
on missing evidence. It does not establish post-2h headroom or confirmatory readiness.

Preflight passes: **0 / 7**. Long-horizon runs permitted: **0**.

| Task | pass | fail | missing | permitted | blockers |
|---|---:|---:|---:|:---:|---|
| Electrochemistry/ElectrolyteConductivityDesign | 8 | 0 | 2 | no | scientific_materiality, exactly_once_recovery |
| Optics/DiffractionGratingDesign | 7 | 0 | 3 | no | baseline_reference_separation, scientific_materiality, exactly_once_recovery |
| RNAEngineering/RNAInverseDesign | 8 | 0 | 2 | no | scientific_materiality, exactly_once_recovery |
| Semiconductor/MOSFETDoping | 8 | 0 | 2 | no | scientific_materiality, exactly_once_recovery |
| StructuralEngineering/TrussWeightMinimization | 8 | 0 | 2 | no | scientific_materiality, exactly_once_recovery |
| Thermodynamics/HeatExchangerDesign | 8 | 0 | 2 | no | scientific_materiality, exactly_once_recovery |
| Turbulence/RANSCalibration | 8 | 0 | 2 | no | scientific_materiality, exactly_once_recovery |

Numerical evaluator resolution is reported separately from domain-grounded scientific
materiality. Missing materiality declarations and missing crash-recovery evidence remain
explicit blockers even when fixed-artifact replay is deterministic.

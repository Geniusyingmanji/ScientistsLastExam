# Task maturity ledger

Generated from tracked, trusted reports at source revision `865c7753884e88601ebf925a418b1bbdedd3e5ac`. Evidence is task-contract
bound as `current_contract_bound`, `migration_replayed`, `historical_only`, or `unbound`.
Maturity gates are cumulative policy claims, not synonyms for registry status.

## Current counts

| Gate | Passed | Meaning |
|---|---:|---|
| Internal science admission | 43 | Runnable internal risk set with card, certification and baseline gates |
| Open release ready | 0 | Adds domain review, lineage, provenance/novelty and current measurement gates |
| Externally validated | 0 | Adds explicit independent external/high-fidelity/physical validation |
| Long-horizon ready | 0 | Adds repeated controls, fresh confirmation, measurement health and post-2h headroom |

Registry status remains `5 certified / 38 candidate / 0 quarantined`; it is not a maturity count.

## Evidence coverage

| Evidence | Tasks |
|---|---:|
| Valid task card | 43 |
| Current/migration-safe baseline | 43 |
| Current/migration-safe model measurement | 43 |
| Normal budget-one | 43 |
| Normal budget-three | 0 |
| Selection-blind budget-three | 0 |
| Matched controls with at least three repetitions | 0 |
| Fresh post-commit confirmation | 0 |
| Completed external domain review | 0 |
| Builder/calibrator lineage declared | 43 |
| Builder/calibrator lineage complete | 0 |
| Provenance class declared | 43 |
| Novelty risk declared | 43 |
| Declared material post-2h headroom | 0 |
| Current/migration-safe quarantine defect reproduction | 0 |

## Per-task audit

`b1/b3/blind` are current-contract or explicitly migration-replayed run counts. `controls` is
the largest matched normal/selection-blind cohort; it does not turn local seed labels into
paired provider randomness. `fresh` means frozen post-search procedural confirmation, not a lab test.

| Task | Status | Internal | b1 | b3 | blind | controls | fresh | budget-one >=0.95 | First release blockers |
|---|---|:---:|---:|---:|---:|---:|:---:|:---:|---|
| PopulationGenetics/DemographicSFS | candidate | yes | 2 | 0 | 0 | 0 | no | no | external domain review pending; builder and calibrator lineage incomplete; no current or migration replayed task calibration |
| SystemsBiology/GeneNetworkIntervention | candidate | yes | 1 | 0 | 0 | 0 | no | no | external domain review pending; builder and calibrator lineage incomplete; no current or migration replayed task calibration |
| EvidenceSynthesis/ProspectiveMetaAnalysis | candidate | yes | 1 | 0 | 0 | 0 | no | no | external domain review pending; builder and calibrator lineage incomplete; no current or migration replayed task calibration |
| ProteinEngineering/ProteinStabilityDesign | candidate | yes | 1 | 0 | 0 | 0 | no | no | external domain review pending; builder and calibrator lineage incomplete; no current or migration replayed task calibration |
| RNAEngineering/RNAEnsembleDesign | candidate | yes | 1 | 0 | 0 | 0 | no | yes | external domain review pending; builder and calibrator lineage incomplete; no current or migration replayed task calibration |
| RNAEngineering/RNAInverseDesign | candidate | yes | 1 | 0 | 0 | 0 | no | no | external domain review pending; builder and calibrator lineage incomplete; no current or migration replayed task calibration |
| MaterialsScience/AlloyHardnessOptimization | candidate | yes | 1 | 0 | 0 | 0 | no | no | external domain review pending; builder and calibrator lineage incomplete; no current or migration replayed task calibration |
| Catalysis/CatalystDeactivationLab | candidate | yes | 1 | 0 | 0 | 0 | no | no | external domain review pending; builder and calibrator lineage incomplete; no current or migration replayed task calibration |
| ChemicalProcess/DistillationColumnDesign | candidate | yes | 1 | 0 | 0 | 0 | no | no | external domain review pending; builder and calibrator lineage incomplete; no current or migration replayed task calibration |
| Electrochemistry/ElectrolyteConductivityDesign | candidate | yes | 1 | 0 | 0 | 0 | no | no | external domain review pending; builder and calibrator lineage incomplete; no current or migration replayed task calibration |
| MolecularDynamics/ForceFieldCalibration | candidate | yes | 1 | 0 | 0 | 0 | no | no | external domain review pending; builder and calibrator lineage incomplete; no current or migration replayed task calibration |
| Chemistry/LennardJonesCluster | certified | yes | 1 | 0 | 0 | 0 | no | yes | external domain review pending; builder and calibrator lineage incomplete; no current or migration replayed task calibration |
| MedicinalChemistry/MolecularLeadOptimization | candidate | yes | 1 | 0 | 0 | 0 | no | no | external domain review pending; builder and calibrator lineage incomplete; no current or migration replayed task calibration |
| Spectroscopy/NMRSpectrumFitting | candidate | yes | 1 | 0 | 0 | 0 | no | no | external domain review pending; builder and calibrator lineage incomplete; no current or migration replayed task calibration |
| ChemicalKinetics/ReactionMechanismFitting | candidate | yes | 1 | 0 | 0 | 0 | no | no | external domain review pending; builder and calibrator lineage incomplete; no current or migration replayed task calibration |
| Spectroscopy/SpinSystemInference | candidate | yes | 1 | 0 | 0 | 0 | no | no | external domain review pending; builder and calibrator lineage incomplete; no current or migration replayed task calibration |
| Algorithm/GraphFromDistances | candidate | yes | 1 | 0 | 0 | 0 | no | no | external domain review pending; builder and calibrator lineage incomplete; no current or migration replayed task calibration |
| CausalDiscovery/InterventionalSCM | candidate | yes | 1 | 0 | 0 | 0 | no | no | external domain review pending; builder and calibrator lineage incomplete; no current or migration replayed task calibration |
| Algorithm/MatrixMultiplicationRank | certified | yes | 1 | 0 | 0 | 0 | no | no | external domain review pending; builder and calibrator lineage incomplete; heldout sealed or procedural generalization not declared |
| SignalProcessing/SparseRecovery | candidate | yes | 1 | 0 | 0 | 0 | no | yes | external domain review pending; builder and calibrator lineage incomplete; no current or migration replayed task calibration |
| ClimateScience/EnergyBalanceModel | candidate | yes | 1 | 0 | 0 | 0 | no | no | external domain review pending; builder and calibrator lineage incomplete; no current or migration replayed task calibration |
| Geophysics/GravityInversion | candidate | yes | 1 | 0 | 0 | 0 | no | no | external domain review pending; builder and calibrator lineage incomplete; no current or migration replayed task calibration |
| AtmosphericScience/RadiativeTransferFit | candidate | yes | 1 | 0 | 0 | 0 | no | no | external domain review pending; builder and calibrator lineage incomplete; no current or migration replayed task calibration |
| HeatTransfer/ConvectionDiffusionOpt | candidate | yes | 1 | 0 | 0 | 0 | no | no | external domain review pending; builder and calibrator lineage incomplete; no current or migration replayed task calibration |
| Thermodynamics/HeatExchangerDesign | candidate | yes | 1 | 0 | 0 | 0 | no | no | external domain review pending; builder and calibrator lineage incomplete; no current or migration replayed task calibration |
| ControlTheory/InvertedPendulumSwingUp | candidate | yes | 1 | 0 | 0 | 0 | no | no | external domain review pending; builder and calibrator lineage incomplete; no current or migration replayed task calibration |
| Astrodynamics/LowThrustTransfer | candidate | yes | 1 | 0 | 0 | 0 | no | no | external domain review pending; builder and calibrator lineage incomplete; no current or migration replayed task calibration |
| Semiconductor/MOSFETDoping | candidate | yes | 1 | 0 | 0 | 0 | no | no | external domain review pending; builder and calibrator lineage incomplete; no current or migration replayed task calibration |
| NuclearEngineering/NeutronDiffusionCriticality | candidate | yes | 1 | 0 | 0 | 0 | no | yes | external domain review pending; builder and calibrator lineage incomplete; no current or migration replayed task calibration |
| Sensors/QuartzCrystalMicrobalanceLab | candidate | yes | 1 | 0 | 0 | 0 | no | no | external domain review pending; builder and calibrator lineage incomplete; no current or migration replayed task calibration |
| Turbulence/RANSCalibration | candidate | yes | 1 | 0 | 0 | 0 | no | no | external domain review pending; builder and calibrator lineage incomplete; no current or migration replayed task calibration |
| Acoustics/RoomImpulseResponse | candidate | yes | 1 | 0 | 0 | 0 | no | no | external domain review pending; builder and calibrator lineage incomplete; no current or migration replayed task calibration |
| StructuralEngineering/TrussWeightMinimization | candidate | yes | 1 | 0 | 0 | 0 | no | no | external domain review pending; builder and calibrator lineage incomplete; no current or migration replayed task calibration |
| DynamicalSystems/ActiveLawDiscovery | candidate | yes | 1 | 0 | 0 | 0 | no | no | external domain review pending; builder and calibrator lineage incomplete; no current or migration replayed task calibration |
| Mathematics/CapSet | certified | yes | 2 | 0 | 0 | 0 | no | no | external domain review pending; builder and calibrator lineage incomplete; heldout sealed or procedural generalization not declared |
| Optimization/CirclePacking | certified | yes | 1 | 0 | 0 | 0 | no | yes | external domain review pending; builder and calibrator lineage incomplete; heldout sealed or procedural generalization not declared |
| Mathematics/SequenceLawRecovery | candidate | yes | 1 | 0 | 0 | 0 | no | no | external domain review pending; builder and calibrator lineage incomplete; no current or migration replayed task calibration |
| ParticlePhysics/CalorimeterDesign | candidate | yes | 1 | 0 | 0 | 0 | no | yes | external domain review pending; builder and calibrator lineage incomplete; no current or migration replayed task calibration |
| Optics/DiffractionGratingDesign | candidate | yes | 1 | 0 | 0 | 0 | no | no | external domain review pending; builder and calibrator lineage incomplete |
| QuantumDynamics/HamiltonianLearning | candidate | yes | 1 | 0 | 0 | 0 | no | no | external domain review pending; builder and calibrator lineage incomplete; no current or migration replayed task calibration |
| Photonics/MultilayerThinFilm | certified | yes | 1 | 0 | 0 | 0 | no | no | external domain review pending; builder and calibrator lineage incomplete; heldout sealed or procedural generalization not declared |
| QuantumErrorCorrection/QuantumErrorDecoder | candidate | yes | 1 | 0 | 0 | 0 | no | no | external domain review pending; builder and calibrator lineage incomplete; no current or migration replayed task calibration |
| Exoplanets/RadialVelocityPlanets | candidate | yes | 1 | 0 | 0 | 0 | no | no | external domain review pending; builder and calibrator lineage incomplete; no current or migration replayed task calibration |

## Immediate implications

- Repeated matched-control evidence currently covers: none.
- Fresh confirmation currently covers: none.
- Admissible tasks without current/migration-safe model measurement: none.
- Tasks with at least one observed current budget-one score >=0.95: RNAEngineering/RNAEnsembleDesign, Chemistry/LennardJonesCluster, SignalProcessing/SparseRecovery, NuclearEngineering/NeutronDiffusionCriticality, Optimization/CirclePacking, ParticlePhysics/CalorimeterDesign. This is a warning, not a reliable saturation rate.
- No task can inherit external validation or long-horizon readiness from internal registry status.

The machine-readable JSON is authoritative for full blockers, evidence hashes, source revisions,
contract binding states and migration-audit links.

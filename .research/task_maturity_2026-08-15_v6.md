# Task maturity ledger

Generated from tracked, trusted reports at source revision `b4aac273443133ce571aa89777530e2388317f9b`. Evidence is task-contract
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
| Current/migration-safe model measurement | 0 |
| Normal budget-one | 0 |
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
| PopulationGenetics/DemographicSFS | candidate | yes | 0 | 0 | 0 | 0 | no | no | external domain review pending; builder and calibrator lineage incomplete; no current or migration replayed task calibration |
| SystemsBiology/GeneNetworkIntervention | candidate | yes | 0 | 0 | 0 | 0 | no | no | external domain review pending; builder and calibrator lineage incomplete; no current or migration replayed task calibration |
| EvidenceSynthesis/ProspectiveMetaAnalysis | candidate | yes | 0 | 0 | 0 | 0 | no | no | external domain review pending; builder and calibrator lineage incomplete; no current or migration replayed task calibration |
| ProteinEngineering/ProteinStabilityDesign | candidate | yes | 0 | 0 | 0 | 0 | no | no | external domain review pending; builder and calibrator lineage incomplete; no current or migration replayed task calibration |
| RNAEngineering/RNAEnsembleDesign | candidate | yes | 0 | 0 | 0 | 0 | no | no | external domain review pending; builder and calibrator lineage incomplete; no current or migration replayed task calibration |
| RNAEngineering/RNAInverseDesign | candidate | yes | 0 | 0 | 0 | 0 | no | no | external domain review pending; builder and calibrator lineage incomplete; no current or migration replayed task calibration |
| MaterialsScience/AlloyHardnessOptimization | candidate | yes | 0 | 0 | 0 | 0 | no | no | external domain review pending; builder and calibrator lineage incomplete; no current or migration replayed task calibration |
| Catalysis/CatalystDeactivationLab | candidate | yes | 0 | 0 | 0 | 0 | no | no | external domain review pending; builder and calibrator lineage incomplete; no current or migration replayed task calibration |
| ChemicalProcess/DistillationColumnDesign | candidate | yes | 0 | 0 | 0 | 0 | no | no | external domain review pending; builder and calibrator lineage incomplete; no current or migration replayed task calibration |
| Electrochemistry/ElectrolyteConductivityDesign | candidate | yes | 0 | 0 | 0 | 0 | no | no | external domain review pending; builder and calibrator lineage incomplete; no current or migration replayed task calibration |
| MolecularDynamics/ForceFieldCalibration | candidate | yes | 0 | 0 | 0 | 0 | no | no | external domain review pending; builder and calibrator lineage incomplete; no current or migration replayed task calibration |
| Chemistry/LennardJonesCluster | certified | yes | 0 | 0 | 0 | 0 | no | no | external domain review pending; builder and calibrator lineage incomplete; no current or migration replayed task calibration |
| MedicinalChemistry/MolecularLeadOptimization | candidate | yes | 0 | 0 | 0 | 0 | no | no | external domain review pending; builder and calibrator lineage incomplete; no current or migration replayed task calibration |
| Spectroscopy/NMRSpectrumFitting | candidate | yes | 0 | 0 | 0 | 0 | no | no | external domain review pending; builder and calibrator lineage incomplete; no current or migration replayed task calibration |
| ChemicalKinetics/ReactionMechanismFitting | candidate | yes | 0 | 0 | 0 | 0 | no | no | external domain review pending; builder and calibrator lineage incomplete; no current or migration replayed task calibration |
| Spectroscopy/SpinSystemInference | candidate | yes | 0 | 0 | 0 | 0 | no | no | external domain review pending; builder and calibrator lineage incomplete; no current or migration replayed task calibration |
| Algorithm/GraphFromDistances | candidate | yes | 0 | 0 | 0 | 0 | no | no | external domain review pending; builder and calibrator lineage incomplete; no current or migration replayed task calibration |
| CausalDiscovery/InterventionalSCM | candidate | yes | 0 | 0 | 0 | 0 | no | no | external domain review pending; builder and calibrator lineage incomplete; no current or migration replayed task calibration |
| Algorithm/MatrixMultiplicationRank | certified | yes | 0 | 0 | 0 | 0 | no | no | external domain review pending; builder and calibrator lineage incomplete; heldout sealed or procedural generalization not declared |
| SignalProcessing/SparseRecovery | candidate | yes | 0 | 0 | 0 | 0 | no | no | external domain review pending; builder and calibrator lineage incomplete; no current or migration replayed task calibration |
| ClimateScience/EnergyBalanceModel | candidate | yes | 0 | 0 | 0 | 0 | no | no | external domain review pending; builder and calibrator lineage incomplete; no current or migration replayed task calibration |
| Geophysics/GravityInversion | candidate | yes | 0 | 0 | 0 | 0 | no | no | external domain review pending; builder and calibrator lineage incomplete; no current or migration replayed task calibration |
| AtmosphericScience/RadiativeTransferFit | candidate | yes | 0 | 0 | 0 | 0 | no | no | external domain review pending; builder and calibrator lineage incomplete; no current or migration replayed task calibration |
| HeatTransfer/ConvectionDiffusionOpt | candidate | yes | 0 | 0 | 0 | 0 | no | no | external domain review pending; builder and calibrator lineage incomplete; no current or migration replayed task calibration |
| Thermodynamics/HeatExchangerDesign | candidate | yes | 0 | 0 | 0 | 0 | no | no | external domain review pending; builder and calibrator lineage incomplete; no current or migration replayed task calibration |
| ControlTheory/InvertedPendulumSwingUp | candidate | yes | 0 | 0 | 0 | 0 | no | no | external domain review pending; builder and calibrator lineage incomplete; no current or migration replayed task calibration |
| Astrodynamics/LowThrustTransfer | candidate | yes | 0 | 0 | 0 | 0 | no | no | external domain review pending; builder and calibrator lineage incomplete; no current or migration replayed task calibration |
| Semiconductor/MOSFETDoping | candidate | yes | 0 | 0 | 0 | 0 | no | no | external domain review pending; builder and calibrator lineage incomplete; no current or migration replayed task calibration |
| NuclearEngineering/NeutronDiffusionCriticality | candidate | yes | 0 | 0 | 0 | 0 | no | no | external domain review pending; builder and calibrator lineage incomplete; no current or migration replayed task calibration |
| Sensors/QuartzCrystalMicrobalanceLab | candidate | yes | 0 | 0 | 0 | 0 | no | no | external domain review pending; builder and calibrator lineage incomplete; no current or migration replayed task calibration |
| Turbulence/RANSCalibration | candidate | yes | 0 | 0 | 0 | 0 | no | no | external domain review pending; builder and calibrator lineage incomplete; no current or migration replayed task calibration |
| Acoustics/RoomImpulseResponse | candidate | yes | 0 | 0 | 0 | 0 | no | no | external domain review pending; builder and calibrator lineage incomplete; no current or migration replayed task calibration |
| StructuralEngineering/TrussWeightMinimization | candidate | yes | 0 | 0 | 0 | 0 | no | no | external domain review pending; builder and calibrator lineage incomplete; no current or migration replayed task calibration |
| DynamicalSystems/ActiveLawDiscovery | candidate | yes | 0 | 0 | 0 | 0 | no | no | external domain review pending; builder and calibrator lineage incomplete; no current or migration replayed task calibration |
| Mathematics/CapSet | certified | yes | 0 | 0 | 0 | 0 | no | no | external domain review pending; builder and calibrator lineage incomplete; heldout sealed or procedural generalization not declared |
| Optimization/CirclePacking | certified | yes | 0 | 0 | 0 | 0 | no | no | external domain review pending; builder and calibrator lineage incomplete; heldout sealed or procedural generalization not declared |
| Mathematics/SequenceLawRecovery | candidate | yes | 0 | 0 | 0 | 0 | no | no | external domain review pending; builder and calibrator lineage incomplete; no current or migration replayed task calibration |
| ParticlePhysics/CalorimeterDesign | candidate | yes | 0 | 0 | 0 | 0 | no | no | external domain review pending; builder and calibrator lineage incomplete; no current or migration replayed task calibration |
| Optics/DiffractionGratingDesign | candidate | yes | 0 | 0 | 0 | 0 | no | no | external domain review pending; builder and calibrator lineage incomplete; no current or migration replayed model measurement |
| QuantumDynamics/HamiltonianLearning | candidate | yes | 0 | 0 | 0 | 0 | no | no | external domain review pending; builder and calibrator lineage incomplete; no current or migration replayed task calibration |
| Photonics/MultilayerThinFilm | certified | yes | 0 | 0 | 0 | 0 | no | no | external domain review pending; builder and calibrator lineage incomplete; heldout sealed or procedural generalization not declared |
| QuantumErrorCorrection/QuantumErrorDecoder | candidate | yes | 0 | 0 | 0 | 0 | no | no | external domain review pending; builder and calibrator lineage incomplete; no current or migration replayed task calibration |
| Exoplanets/RadialVelocityPlanets | candidate | yes | 0 | 0 | 0 | 0 | no | no | external domain review pending; builder and calibrator lineage incomplete; no current or migration replayed task calibration |

## Immediate implications

- Repeated matched-control evidence currently covers: none.
- Fresh confirmation currently covers: none.
- Admissible tasks without current/migration-safe model measurement: PopulationGenetics/DemographicSFS, SystemsBiology/GeneNetworkIntervention, EvidenceSynthesis/ProspectiveMetaAnalysis, ProteinEngineering/ProteinStabilityDesign, RNAEngineering/RNAEnsembleDesign, RNAEngineering/RNAInverseDesign, MaterialsScience/AlloyHardnessOptimization, Catalysis/CatalystDeactivationLab, ChemicalProcess/DistillationColumnDesign, Electrochemistry/ElectrolyteConductivityDesign, MolecularDynamics/ForceFieldCalibration, Chemistry/LennardJonesCluster, MedicinalChemistry/MolecularLeadOptimization, Spectroscopy/NMRSpectrumFitting, ChemicalKinetics/ReactionMechanismFitting, Spectroscopy/SpinSystemInference, Algorithm/GraphFromDistances, CausalDiscovery/InterventionalSCM, Algorithm/MatrixMultiplicationRank, SignalProcessing/SparseRecovery, ClimateScience/EnergyBalanceModel, Geophysics/GravityInversion, AtmosphericScience/RadiativeTransferFit, HeatTransfer/ConvectionDiffusionOpt, Thermodynamics/HeatExchangerDesign, ControlTheory/InvertedPendulumSwingUp, Astrodynamics/LowThrustTransfer, Semiconductor/MOSFETDoping, NuclearEngineering/NeutronDiffusionCriticality, Sensors/QuartzCrystalMicrobalanceLab, Turbulence/RANSCalibration, Acoustics/RoomImpulseResponse, StructuralEngineering/TrussWeightMinimization, DynamicalSystems/ActiveLawDiscovery, Mathematics/CapSet, Optimization/CirclePacking, Mathematics/SequenceLawRecovery, ParticlePhysics/CalorimeterDesign, Optics/DiffractionGratingDesign, QuantumDynamics/HamiltonianLearning, Photonics/MultilayerThinFilm, QuantumErrorCorrection/QuantumErrorDecoder, Exoplanets/RadialVelocityPlanets.
- Tasks with at least one observed current budget-one score >=0.95: none. This is a warning, not a reliable saturation rate.
- No task can inherit external validation or long-horizon readiness from internal registry status.

The machine-readable JSON is authoritative for full blockers, evidence hashes, source revisions,
contract binding states and migration-audit links.

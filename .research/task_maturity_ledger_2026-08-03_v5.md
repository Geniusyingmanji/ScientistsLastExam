# Task maturity ledger

Generated from tracked, trusted reports at source revision `b9d1d7edecb883bc1175bbbc370ce69081378e56`. Evidence is task-contract
bound as `current_contract_bound`, `migration_replayed`, `historical_only`, or `unbound`.
Maturity gates are cumulative policy claims, not synonyms for registry status.

## Current counts

| Gate | Passed | Meaning |
|---|---:|---|
| Internal science admission | 50 | Runnable internal risk set with card, certification and baseline gates |
| Open release ready | 0 | Adds domain review, lineage, provenance/novelty and current measurement gates |
| Externally validated | 0 | Adds explicit independent external/high-fidelity/physical validation |
| Long-horizon ready | 0 | Adds repeated controls, fresh confirmation, measurement health and post-2h headroom |

Registry status remains `7 certified / 43 candidate / 9 quarantined`; it is not a maturity count.

## Evidence coverage

| Evidence | Tasks |
|---|---:|
| Valid task card | 50 |
| Current/migration-safe baseline | 59 |
| Current/migration-safe model measurement | 50 |
| Normal budget-one | 48 |
| Normal budget-three | 40 |
| Selection-blind budget-three | 37 |
| Matched controls with at least three repetitions | 5 |
| Fresh post-commit confirmation | 2 |
| Completed external domain review | 0 |
| Builder/calibrator lineage declared | 50 |
| Builder/calibrator lineage complete | 0 |
| Provenance class declared | 50 |
| Novelty risk declared | 50 |
| Declared material post-2h headroom | 0 |
| Current/migration-safe quarantine defect reproduction | 9 |

## Per-task audit

`b1/b3/blind` are current-contract or explicitly migration-replayed run counts. `controls` is
the largest matched normal/selection-blind cohort; it does not turn local seed labels into
paired provider randomness. `fresh` means frozen post-search procedural confirmation, not a lab test.

| Task | Status | Internal | b1 | b3 | blind | controls | fresh | budget-one >=0.95 | First release blockers |
|---|---|:---:|---:|---:|---:|---:|:---:|:---:|---|
| PopulationGenetics/DemographicSFS | candidate | yes | 1 | 1 | 1 | 0 | no | no | external domain review pending; builder and calibrator lineage incomplete |
| SystemsBiology/GeneNetworkIntervention | candidate | yes | 1 | 1 | 1 | 0 | no | no | external domain review pending; builder and calibrator lineage incomplete |
| EvidenceSynthesis/ProspectiveMetaAnalysis | candidate | yes | 1 | 1 | 1 | 0 | no | no | external domain review pending; builder and calibrator lineage incomplete |
| Biomechanics/ProstheticJointDesign | quarantined | no | 0 | 0 | 0 | 0 | no | no | internal science admission failed; external domain review pending; builder and calibrator lineage incomplete |
| ProteinEngineering/ProteinStabilityDesign | candidate | yes | 1 | 1 | 1 | 0 | no | no | external domain review pending; builder and calibrator lineage incomplete |
| RNAEngineering/RNAInverseDesign | candidate | yes | 1 | 1 | 1 | 0 | no | no | external domain review pending; builder and calibrator lineage incomplete |
| MaterialsScience/AlloyHardnessOptimization | candidate | yes | 1 | 1 | 1 | 0 | no | no | external domain review pending; builder and calibrator lineage incomplete |
| Catalysis/CatalystDeactivationLab | candidate | yes | 1 | 1 | 1 | 0 | no | no | external domain review pending; builder and calibrator lineage incomplete |
| CrystalGrowth/CzochralskiProcess | quarantined | no | 0 | 0 | 0 | 0 | no | no | internal science admission failed; external domain review pending; builder and calibrator lineage incomplete |
| ChemicalProcess/DistillationColumnDesign | candidate | yes | 1 | 1 | 1 | 0 | no | no | external domain review pending; builder and calibrator lineage incomplete |
| Electrochemistry/ElectrolyteConductivityDesign | candidate | yes | 1 | 1 | 1 | 0 | no | no | external domain review pending; builder and calibrator lineage incomplete |
| Combustion/FlameSpeedOptimization | quarantined | no | 0 | 0 | 0 | 0 | no | no | internal science admission failed; external domain review pending; builder and calibrator lineage incomplete |
| MolecularDynamics/ForceFieldCalibration | candidate | yes | 1 | 1 | 1 | 0 | no | no | external domain review pending; builder and calibrator lineage incomplete |
| QuantumChemistry/HartreeFockSCF | candidate | yes | 1 | 1 | 1 | 0 | no | yes | external domain review pending; builder and calibrator lineage incomplete |
| Chemistry/LennardJonesCluster | certified | yes | 1 | 0 | 0 | 0 | no | yes | external domain review pending; builder and calibrator lineage incomplete |
| Spectroscopy/NMRSpectrumFitting | candidate | yes | 1 | 1 | 0 | 0 | no | no | external domain review pending; builder and calibrator lineage incomplete |
| Photovoltaics/PhotovoltaicTandemDesign | candidate | yes | 1 | 1 | 1 | 0 | no | yes | external domain review pending; builder and calibrator lineage incomplete |
| ChemicalKinetics/ReactionMechanismFitting | candidate | yes | 1 | 1 | 1 | 0 | no | no | external domain review pending; builder and calibrator lineage incomplete |
| CausalDiscovery/InterventionalSCM | candidate | yes | 1 | 0 | 0 | 0 | no | yes | external domain review pending; builder and calibrator lineage incomplete |
| Algorithm/MatrixMultiplicationRank | certified | yes | 1 | 0 | 0 | 0 | no | no | external domain review pending; builder and calibrator lineage incomplete; heldout sealed or procedural generalization not declared |
| ScientificComputing/PoissonSolver2D | certified | yes | 1 | 0 | 0 | 0 | no | yes | external domain review pending; builder and calibrator lineage incomplete; heldout sealed or procedural generalization not declared |
| SignalProcessing/SparseRecovery | candidate | yes | 1 | 0 | 0 | 0 | no | yes | external domain review pending; builder and calibrator lineage incomplete |
| ClimateScience/EnergyBalanceModel | candidate | yes | 1 | 1 | 1 | 0 | no | no | external domain review pending; builder and calibrator lineage incomplete |
| Geophysics/GravityInversion | candidate | yes | 1 | 1 | 0 | 0 | no | no | external domain review pending; builder and calibrator lineage incomplete |
| Oceanography/OceanCurrentInversion | candidate | yes | 1 | 1 | 1 | 0 | no | no | external domain review pending; builder and calibrator lineage incomplete |
| AtmosphericScience/RadiativeTransferFit | candidate | yes | 1 | 1 | 1 | 0 | no | no | external domain review pending; builder and calibrator lineage incomplete |
| Geophysics/SeismicInversion | candidate | yes | 1 | 1 | 1 | 1 | no | yes | external domain review pending; builder and calibrator lineage incomplete |
| WavePropagation/SeismicWaveInversion | candidate | yes | 1 | 1 | 1 | 0 | no | no | external domain review pending; builder and calibrator lineage incomplete |
| AcousticMetamaterials/BroadbandAbsorber | candidate | yes | 1 | 1 | 1 | 0 | no | no | external domain review pending; builder and calibrator lineage incomplete |
| HeatTransfer/ConvectionDiffusionOpt | candidate | yes | 1 | 1 | 1 | 0 | no | no | external domain review pending; builder and calibrator lineage incomplete |
| Thermodynamics/HeatExchangerDesign | candidate | yes | 1 | 1 | 1 | 0 | no | no | external domain review pending; builder and calibrator lineage incomplete |
| ControlTheory/InvertedPendulumSwingUp | candidate | yes | 0 | 3 | 3 | 3 | no | no | external domain review pending; builder and calibrator lineage incomplete |
| FluidDynamics/LidDrivenCavity | candidate | yes | 1 | 1 | 1 | 0 | no | yes | external domain review pending; builder and calibrator lineage incomplete |
| Astrodynamics/LowThrustTransfer | candidate | yes | 1 | 1 | 1 | 0 | no | no | external domain review pending; builder and calibrator lineage incomplete |
| Semiconductor/MOSFETDoping | candidate | yes | 1 | 1 | 1 | 0 | no | no | external domain review pending; builder and calibrator lineage incomplete |
| InventoryManagement/MultiEchelonStock | quarantined | no | 0 | 0 | 0 | 0 | no | no | internal science admission failed; external domain review pending; builder and calibrator lineage incomplete |
| NuclearEngineering/NeutronDiffusionCriticality | candidate | yes | 1 | 1 | 1 | 1 | no | no | external domain review pending; builder and calibrator lineage incomplete |
| PowerSystems/OptimalPowerFlow | candidate | yes | 1 | 4 | 3 | 3 | no | yes | external domain review pending; builder and calibrator lineage incomplete |
| Sensors/QuartzCrystalMicrobalanceLab | candidate | yes | 1 | 1 | 1 | 0 | no | no | external domain review pending; builder and calibrator lineage incomplete |
| Turbulence/RANSCalibration | candidate | yes | 1 | 1 | 1 | 0 | no | no | external domain review pending; builder and calibrator lineage incomplete |
| Thermodynamics/RankineCycleOpt | candidate | yes | 1 | 1 | 1 | 0 | no | yes | external domain review pending; builder and calibrator lineage incomplete |
| Acoustics/RoomImpulseResponse | candidate | yes | 1 | 1 | 1 | 0 | no | no | external domain review pending; builder and calibrator lineage incomplete |
| FluidMechanics/StokesShapeDrag | quarantined | no | 0 | 0 | 0 | 0 | no | no | internal science admission failed; external domain review pending; builder and calibrator lineage incomplete |
| Transportation/TrafficSignalTiming | quarantined | no | 0 | 0 | 0 | 0 | no | no | internal science admission failed; external domain review pending; builder and calibrator lineage incomplete |
| StructuralEngineering/TrussWeightMinimization | candidate | yes | 1 | 1 | 1 | 0 | no | no | external domain review pending; builder and calibrator lineage incomplete |
| Geomechanics/TunnelSupportDesign | quarantined | no | 0 | 0 | 0 | 0 | no | no | internal science admission failed; external domain review pending; builder and calibrator lineage incomplete |
| DynamicalSystems/ActiveLawDiscovery | candidate | yes | 0 | 48 | 48 | 48 | yes | no | external domain review pending; builder and calibrator lineage incomplete |
| Mathematics/CapSet | certified | yes | 1 | 0 | 0 | 0 | no | no | external domain review pending; builder and calibrator lineage incomplete; heldout sealed or procedural generalization not declared |
| Optimization/CirclePacking | certified | yes | 1 | 0 | 0 | 0 | no | no | external domain review pending; builder and calibrator lineage incomplete; heldout sealed or procedural generalization not declared |
| DynamicalSystems/LyapunovControl | candidate | yes | 1 | 1 | 1 | 1 | no | yes | external domain review pending; builder and calibrator lineage incomplete |
| BayesianInference/OptimalExperimentDesign | candidate | yes | 1 | 0 | 0 | 0 | no | yes | external domain review pending; builder and calibrator lineage incomplete |
| Electromagnetics/AntennaArraySynthesis | candidate | yes | 1 | 1 | 0 | 0 | no | yes | external domain review pending; builder and calibrator lineage incomplete |
| ParticlePhysics/CalorimeterDesign | candidate | yes | 1 | 1 | 1 | 0 | no | no | external domain review pending; builder and calibrator lineage incomplete |
| Optics/DiffractionGratingDesign | candidate | yes | 1 | 51 | 51 | 48 | yes | no | external domain review pending; builder and calibrator lineage incomplete |
| QuantumControl/GateSynthesis | candidate | yes | 1 | 4 | 3 | 3 | no | yes | external domain review pending; builder and calibrator lineage incomplete |
| Optoelectronics/LaserCavityDesign | quarantined | no | 0 | 0 | 0 | 0 | no | no | internal science admission failed; external domain review pending; builder and calibrator lineage incomplete |
| Photonics/MultilayerThinFilm | certified | yes | 1 | 0 | 0 | 0 | no | no | external domain review pending; builder and calibrator lineage incomplete; heldout sealed or procedural generalization not declared |
| Physics/SpinGlassGroundState | certified | yes | 1 | 0 | 0 | 0 | no | yes | external domain review pending; builder and calibrator lineage incomplete; heldout sealed or procedural generalization not declared |
| Electromagnetics/WaveguideModeSolver | quarantined | no | 0 | 0 | 0 | 0 | no | no | internal science admission failed; external domain review pending; builder and calibrator lineage incomplete |

## Immediate implications

- Repeated matched-control evidence currently covers: ControlTheory/InvertedPendulumSwingUp, PowerSystems/OptimalPowerFlow, DynamicalSystems/ActiveLawDiscovery, Optics/DiffractionGratingDesign, QuantumControl/GateSynthesis.
- Fresh confirmation currently covers: DynamicalSystems/ActiveLawDiscovery, Optics/DiffractionGratingDesign.
- Admissible tasks without current/migration-safe model measurement: none.
- Tasks with at least one observed current budget-one score >=0.95: QuantumChemistry/HartreeFockSCF, Chemistry/LennardJonesCluster, Photovoltaics/PhotovoltaicTandemDesign, CausalDiscovery/InterventionalSCM, ScientificComputing/PoissonSolver2D, SignalProcessing/SparseRecovery, Geophysics/SeismicInversion, FluidDynamics/LidDrivenCavity, PowerSystems/OptimalPowerFlow, Thermodynamics/RankineCycleOpt, DynamicalSystems/LyapunovControl, BayesianInference/OptimalExperimentDesign, Electromagnetics/AntennaArraySynthesis, QuantumControl/GateSynthesis, Physics/SpinGlassGroundState. This is a warning, not a reliable saturation rate.
- No task can inherit external validation or long-horizon readiness from internal registry status.

The machine-readable JSON is authoritative for full blockers, evidence hashes, source revisions,
contract binding states and migration-audit links.

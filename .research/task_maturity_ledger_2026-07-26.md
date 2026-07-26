# Task maturity ledger

Generated from tracked, trusted reports at source revision `88fcbf1a6bd02d829a32bdd70e8e10deb69b896d`. Evidence is task-contract
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
| Current/migration-safe model measurement | 47 |
| Normal budget-one | 45 |
| Normal budget-three | 37 |
| Selection-blind budget-three | 34 |
| Matched controls with at least three repetitions | 5 |
| Fresh post-commit confirmation | 2 |
| Completed external domain review | 0 |
| Builder/calibrator lineage declared | 0 |
| Provenance class declared | 0 |
| Novelty risk declared | 0 |
| Declared material post-2h headroom | 0 |

## Per-task audit

`b1/b3/blind` are current-contract or explicitly migration-replayed run counts. `controls` is
the largest matched normal/selection-blind cohort; it does not turn local seed labels into
paired provider randomness. `fresh` means frozen post-search procedural confirmation, not a lab test.

| Task | Status | Internal | b1 | b3 | blind | controls | fresh | budget-one >=0.95 | First release blockers |
|---|---|:---:|---:|---:|---:|---:|:---:|:---:|---|
| AcousticMetamaterials/BroadbandAbsorber | candidate | yes | 1 | 1 | 1 | 0 | no | no | external domain review pending; builder and calibrator lineage missing; known answer procedural or prospective provenance missing |
| Acoustics/RoomImpulseResponse | candidate | yes | 1 | 1 | 1 | 0 | no | no | external domain review pending; builder and calibrator lineage missing; known answer procedural or prospective provenance missing |
| Algorithm/MatrixMultiplicationRank | certified | yes | 1 | 0 | 0 | 0 | no | no | external domain review pending; builder and calibrator lineage missing; known answer procedural or prospective provenance missing |
| Astrodynamics/LowThrustTransfer | candidate | yes | 1 | 1 | 1 | 0 | no | no | external domain review pending; builder and calibrator lineage missing; known answer procedural or prospective provenance missing |
| AtmosphericScience/RadiativeTransferFit | candidate | yes | 1 | 1 | 1 | 0 | no | no | external domain review pending; builder and calibrator lineage missing; known answer procedural or prospective provenance missing |
| BayesianInference/OptimalExperimentDesign | candidate | yes | 1 | 0 | 0 | 0 | no | yes | external domain review pending; builder and calibrator lineage missing; known answer procedural or prospective provenance missing |
| Biomechanics/ProstheticJointDesign | quarantined | no | 0 | 0 | 0 | 0 | no | no | internal science admission failed; external domain review pending; builder and calibrator lineage missing |
| Catalysis/CatalystDeactivationLab | candidate | yes | 1 | 1 | 1 | 0 | no | no | external domain review pending; builder and calibrator lineage missing; known answer procedural or prospective provenance missing |
| CausalDiscovery/InterventionalSCM | candidate | yes | 1 | 0 | 0 | 0 | no | yes | external domain review pending; builder and calibrator lineage missing; known answer procedural or prospective provenance missing |
| ChemicalKinetics/ReactionMechanismFitting | candidate | yes | 1 | 1 | 1 | 0 | no | no | external domain review pending; builder and calibrator lineage missing; known answer procedural or prospective provenance missing |
| ChemicalProcess/DistillationColumnDesign | candidate | yes | 1 | 1 | 1 | 0 | no | no | external domain review pending; builder and calibrator lineage missing; known answer procedural or prospective provenance missing |
| Chemistry/LennardJonesCluster | certified | yes | 1 | 0 | 0 | 0 | no | yes | external domain review pending; builder and calibrator lineage missing; known answer procedural or prospective provenance missing |
| ClimateScience/EnergyBalanceModel | candidate | yes | 1 | 1 | 1 | 0 | no | no | external domain review pending; builder and calibrator lineage missing; known answer procedural or prospective provenance missing |
| Combustion/FlameSpeedOptimization | quarantined | no | 0 | 0 | 0 | 0 | no | no | internal science admission failed; external domain review pending; builder and calibrator lineage missing |
| ControlTheory/InvertedPendulumSwingUp | candidate | yes | 0 | 3 | 3 | 3 | no | no | external domain review pending; builder and calibrator lineage missing; known answer procedural or prospective provenance missing |
| CrystalGrowth/CzochralskiProcess | quarantined | no | 0 | 0 | 0 | 0 | no | no | internal science admission failed; external domain review pending; builder and calibrator lineage missing |
| DynamicalSystems/ActiveLawDiscovery | candidate | yes | 0 | 48 | 48 | 48 | yes | no | external domain review pending; builder and calibrator lineage missing; known answer procedural or prospective provenance missing |
| DynamicalSystems/LyapunovControl | candidate | yes | 0 | 0 | 0 | 0 | no | no | external domain review pending; builder and calibrator lineage missing; known answer procedural or prospective provenance missing |
| Electrochemistry/ElectrolyteConductivityDesign | candidate | yes | 1 | 1 | 1 | 0 | no | no | external domain review pending; builder and calibrator lineage missing; known answer procedural or prospective provenance missing |
| Electromagnetics/AntennaArraySynthesis | candidate | yes | 1 | 1 | 0 | 0 | no | yes | external domain review pending; builder and calibrator lineage missing; known answer procedural or prospective provenance missing |
| Electromagnetics/WaveguideModeSolver | quarantined | no | 0 | 0 | 0 | 0 | no | no | internal science admission failed; external domain review pending; builder and calibrator lineage missing |
| EvidenceSynthesis/ProspectiveMetaAnalysis | candidate | yes | 1 | 1 | 1 | 0 | no | no | external domain review pending; builder and calibrator lineage missing; known answer procedural or prospective provenance missing |
| FluidDynamics/LidDrivenCavity | candidate | yes | 1 | 1 | 1 | 0 | no | yes | external domain review pending; builder and calibrator lineage missing; known answer procedural or prospective provenance missing |
| FluidMechanics/StokesShapeDrag | quarantined | no | 0 | 0 | 0 | 0 | no | no | internal science admission failed; external domain review pending; builder and calibrator lineage missing |
| Geomechanics/TunnelSupportDesign | quarantined | no | 0 | 0 | 0 | 0 | no | no | internal science admission failed; external domain review pending; builder and calibrator lineage missing |
| Geophysics/GravityInversion | candidate | yes | 1 | 1 | 0 | 0 | no | no | external domain review pending; builder and calibrator lineage missing; known answer procedural or prospective provenance missing |
| Geophysics/SeismicInversion | candidate | yes | 0 | 0 | 0 | 0 | no | no | external domain review pending; builder and calibrator lineage missing; known answer procedural or prospective provenance missing |
| HeatTransfer/ConvectionDiffusionOpt | candidate | yes | 1 | 1 | 1 | 0 | no | no | external domain review pending; builder and calibrator lineage missing; known answer procedural or prospective provenance missing |
| InventoryManagement/MultiEchelonStock | quarantined | no | 0 | 0 | 0 | 0 | no | no | internal science admission failed; external domain review pending; builder and calibrator lineage missing |
| MaterialsScience/AlloyHardnessOptimization | candidate | yes | 1 | 1 | 1 | 0 | no | no | external domain review pending; builder and calibrator lineage missing; known answer procedural or prospective provenance missing |
| Mathematics/CapSet | certified | yes | 1 | 0 | 0 | 0 | no | no | external domain review pending; builder and calibrator lineage missing; known answer procedural or prospective provenance missing |
| MolecularDynamics/ForceFieldCalibration | candidate | yes | 1 | 1 | 1 | 0 | no | no | external domain review pending; builder and calibrator lineage missing; known answer procedural or prospective provenance missing |
| NuclearEngineering/NeutronDiffusionCriticality | candidate | yes | 0 | 0 | 0 | 0 | no | no | external domain review pending; builder and calibrator lineage missing; known answer procedural or prospective provenance missing |
| Oceanography/OceanCurrentInversion | candidate | yes | 1 | 1 | 1 | 0 | no | no | external domain review pending; builder and calibrator lineage missing; known answer procedural or prospective provenance missing |
| Optics/DiffractionGratingDesign | candidate | yes | 1 | 51 | 51 | 48 | yes | no | external domain review pending; builder and calibrator lineage missing; known answer procedural or prospective provenance missing |
| Optimization/CirclePacking | certified | yes | 1 | 0 | 0 | 0 | no | no | external domain review pending; builder and calibrator lineage missing; known answer procedural or prospective provenance missing |
| Optoelectronics/LaserCavityDesign | quarantined | no | 0 | 0 | 0 | 0 | no | no | internal science admission failed; external domain review pending; builder and calibrator lineage missing |
| ParticlePhysics/CalorimeterDesign | candidate | yes | 1 | 1 | 1 | 0 | no | no | external domain review pending; builder and calibrator lineage missing; known answer procedural or prospective provenance missing |
| Photonics/MultilayerThinFilm | certified | yes | 1 | 0 | 0 | 0 | no | no | external domain review pending; builder and calibrator lineage missing; known answer procedural or prospective provenance missing |
| Photovoltaics/PhotovoltaicTandemDesign | candidate | yes | 1 | 1 | 1 | 0 | no | yes | external domain review pending; builder and calibrator lineage missing; known answer procedural or prospective provenance missing |
| Physics/SpinGlassGroundState | certified | yes | 1 | 0 | 0 | 0 | no | yes | external domain review pending; builder and calibrator lineage missing; known answer procedural or prospective provenance missing |
| PopulationGenetics/DemographicSFS | candidate | yes | 1 | 1 | 1 | 0 | no | no | external domain review pending; builder and calibrator lineage missing; known answer procedural or prospective provenance missing |
| PowerSystems/OptimalPowerFlow | candidate | yes | 1 | 4 | 3 | 3 | no | yes | external domain review pending; builder and calibrator lineage missing; known answer procedural or prospective provenance missing |
| ProteinEngineering/ProteinStabilityDesign | candidate | yes | 1 | 1 | 1 | 0 | no | no | external domain review pending; builder and calibrator lineage missing; known answer procedural or prospective provenance missing |
| QuantumChemistry/HartreeFockSCF | candidate | yes | 1 | 1 | 1 | 0 | no | yes | external domain review pending; builder and calibrator lineage missing; known answer procedural or prospective provenance missing |
| QuantumControl/GateSynthesis | candidate | yes | 1 | 4 | 3 | 3 | no | yes | external domain review pending; builder and calibrator lineage missing; known answer procedural or prospective provenance missing |
| RNAEngineering/RNAInverseDesign | candidate | yes | 1 | 1 | 1 | 0 | no | no | external domain review pending; builder and calibrator lineage missing; known answer procedural or prospective provenance missing |
| ScientificComputing/PoissonSolver2D | certified | yes | 1 | 0 | 0 | 0 | no | yes | external domain review pending; builder and calibrator lineage missing; known answer procedural or prospective provenance missing |
| Semiconductor/MOSFETDoping | candidate | yes | 1 | 1 | 1 | 0 | no | no | external domain review pending; builder and calibrator lineage missing; known answer procedural or prospective provenance missing |
| Sensors/QuartzCrystalMicrobalanceLab | candidate | yes | 1 | 1 | 1 | 0 | no | no | external domain review pending; builder and calibrator lineage missing; known answer procedural or prospective provenance missing |
| SignalProcessing/SparseRecovery | candidate | yes | 1 | 0 | 0 | 0 | no | yes | external domain review pending; builder and calibrator lineage missing; known answer procedural or prospective provenance missing |
| Spectroscopy/NMRSpectrumFitting | candidate | yes | 1 | 1 | 0 | 0 | no | no | external domain review pending; builder and calibrator lineage missing; known answer procedural or prospective provenance missing |
| StructuralEngineering/TrussWeightMinimization | candidate | yes | 1 | 1 | 1 | 0 | no | no | external domain review pending; builder and calibrator lineage missing; known answer procedural or prospective provenance missing |
| SystemsBiology/GeneNetworkIntervention | candidate | yes | 1 | 1 | 1 | 0 | no | no | external domain review pending; builder and calibrator lineage missing; known answer procedural or prospective provenance missing |
| Thermodynamics/HeatExchangerDesign | candidate | yes | 1 | 1 | 1 | 0 | no | no | external domain review pending; builder and calibrator lineage missing; known answer procedural or prospective provenance missing |
| Thermodynamics/RankineCycleOpt | candidate | yes | 1 | 1 | 1 | 0 | no | yes | external domain review pending; builder and calibrator lineage missing; known answer procedural or prospective provenance missing |
| Transportation/TrafficSignalTiming | quarantined | no | 0 | 0 | 0 | 0 | no | no | internal science admission failed; external domain review pending; builder and calibrator lineage missing |
| Turbulence/RANSCalibration | candidate | yes | 1 | 1 | 1 | 0 | no | no | external domain review pending; builder and calibrator lineage missing; known answer procedural or prospective provenance missing |
| WavePropagation/SeismicWaveInversion | candidate | yes | 1 | 1 | 1 | 0 | no | no | external domain review pending; builder and calibrator lineage missing; known answer procedural or prospective provenance missing |

## Immediate implications

- Repeated matched-control evidence currently covers: ControlTheory/InvertedPendulumSwingUp, DynamicalSystems/ActiveLawDiscovery, Optics/DiffractionGratingDesign, PowerSystems/OptimalPowerFlow, QuantumControl/GateSynthesis.
- Fresh confirmation currently covers: DynamicalSystems/ActiveLawDiscovery, Optics/DiffractionGratingDesign.
- Admissible tasks without current/migration-safe model measurement: DynamicalSystems/LyapunovControl, Geophysics/SeismicInversion, NuclearEngineering/NeutronDiffusionCriticality.
- Tasks with at least one observed current budget-one score >=0.95: BayesianInference/OptimalExperimentDesign, CausalDiscovery/InterventionalSCM, Chemistry/LennardJonesCluster, Electromagnetics/AntennaArraySynthesis, FluidDynamics/LidDrivenCavity, Photovoltaics/PhotovoltaicTandemDesign, Physics/SpinGlassGroundState, PowerSystems/OptimalPowerFlow, QuantumChemistry/HartreeFockSCF, QuantumControl/GateSynthesis, ScientificComputing/PoissonSolver2D, SignalProcessing/SparseRecovery, Thermodynamics/RankineCycleOpt. This is a warning, not a reliable saturation rate.
- No task can inherit external validation or long-horizon readiness from internal registry status.

The machine-readable JSON is authoritative for full blockers, evidence hashes, source revisions,
contract binding states and migration-audit links.

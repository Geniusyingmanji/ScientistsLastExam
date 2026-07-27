# Measurement-health task allocation

This audit allocates the current inventory for the next measurement stage. It does not
promote any task to long-horizon-ready. The exploratory cohort was selected after
inspecting current GPT-5.5 outcomes and therefore cannot double as a confirmatory cohort.

## Counts

| Classification | Tasks | Meaning |
|---|---:|---|
| Exploratory long-horizon screen | 7 | Freeze for a sentinel-complete 2 h pilot; not confirmatory |
| Repair first | 24 | Repair contract or measurement path before allocating 2--12 h |
| Saturated/on-ramp | 17 | Useful reconstruction/on-ramp; harden before long-horizon use |
| Control only | 2 | Retain for mechanism/protocol/positive-control studies |
| Quarantined | 9 | Failed internal science admission |

Complete measurement-health passes: **0**. Confirmatory-cohort eligible: **0**.

## Allocation

| Task | Class | b1 | b3 | blind | max later gain | controls | fresh |
|---|---|---:|---:|---:|---:|---:|:---:|
| AcousticMetamaterials/BroadbandAbsorber | repair first | 0.000 | 0.915 | 0.917 | -- | 0 | no |
| Acoustics/RoomImpulseResponse | repair first | 0.000 | 0.000 | 0.754 | -- | 0 | no |
| Algorithm/MatrixMultiplicationRank | repair first | 0.646 | -- | -- | -- | 0 | no |
| Astrodynamics/LowThrustTransfer | repair first | 0.008 | 0.005 | 0.005 | -0.000 | 0 | no |
| AtmosphericScience/RadiativeTransferFit | repair first | 0.000 | 0.000 | 0.000 | 0.000 | 0 | no |
| BayesianInference/OptimalExperimentDesign | saturated on ramp | 0.991 | -- | -- | -- | 0 | no |
| Catalysis/CatalystDeactivationLab | repair first | 0.000 | 0.075 | 0.041 | 0.002 | 0 | no |
| CausalDiscovery/InterventionalSCM | saturated on ramp | 0.983 | -- | -- | -- | 0 | no |
| ChemicalKinetics/ReactionMechanismFitting | repair first | 0.000 | 0.000 | 0.343 | 0.000 | 0 | no |
| ChemicalProcess/DistillationColumnDesign | repair first | 0.000 | 0.613 | 0.000 | -- | 0 | no |
| Chemistry/LennardJonesCluster | saturated on ramp | 0.982 | -- | -- | -- | 0 | no |
| ClimateScience/EnergyBalanceModel | repair first | 0.000 | 0.000 | 0.618 | -- | 0 | no |
| ControlTheory/InvertedPendulumSwingUp | control only | -- | 0.559 | 0.807 | 0.154 | 3 | no |
| DynamicalSystems/ActiveLawDiscovery | control only | -- | 0.794 | 0.804 | 0.487 | 48 | yes |
| DynamicalSystems/LyapunovControl | saturated on ramp | 1.000 | 1.000 | 1.000 | 0.000 | 1 | no |
| Electrochemistry/ElectrolyteConductivityDesign | exploratory long horizon screen | 0.263 | 0.878 | 0.646 | 0.386 | 0 | no |
| Electromagnetics/AntennaArraySynthesis | saturated on ramp | 0.999 | 1.000 | -- | 0.155 | 0 | no |
| EvidenceSynthesis/ProspectiveMetaAnalysis | repair first | 0.000 | 0.000 | 0.000 | 0.000 | 0 | no |
| FluidDynamics/LidDrivenCavity | saturated on ramp | 1.000 | 0.898 | 1.000 | 0.028 | 0 | no |
| Geophysics/GravityInversion | saturated on ramp | 0.000 | 0.994 | -- | 0.000 | 0 | no |
| Geophysics/SeismicInversion | saturated on ramp | 0.998 | 0.998 | 0.998 | 0.000 | 1 | no |
| HeatTransfer/ConvectionDiffusionOpt | repair first | 0.000 | 0.000 | 0.000 | -- | 0 | no |
| MaterialsScience/AlloyHardnessOptimization | repair first | 0.152 | 0.152 | 0.152 | 0.152 | 0 | no |
| Mathematics/CapSet | repair first | 0.650 | -- | -- | -- | 0 | no |
| MolecularDynamics/ForceFieldCalibration | repair first | 0.000 | 0.000 | 0.000 | -- | 0 | no |
| NuclearEngineering/NeutronDiffusionCriticality | saturated on ramp | 0.939 | 0.963 | 0.982 | 0.131 | 1 | no |
| Oceanography/OceanCurrentInversion | repair first | 0.000 | 0.000 | 0.000 | -- | 0 | no |
| Optics/DiffractionGratingDesign | exploratory long horizon screen | 0.000 | 0.294 | 0.247 | 0.311 | 48 | yes |
| Optimization/CirclePacking | repair first | 0.000 | -- | -- | -- | 0 | no |
| ParticlePhysics/CalorimeterDesign | repair first | 0.000 | 0.000 | 0.000 | -- | 0 | no |
| Photonics/MultilayerThinFilm | repair first | 0.890 | -- | -- | -- | 0 | no |
| Photovoltaics/PhotovoltaicTandemDesign | saturated on ramp | 0.995 | 0.994 | 1.000 | 0.019 | 0 | no |
| Physics/SpinGlassGroundState | saturated on ramp | 1.000 | -- | -- | -- | 0 | no |
| PopulationGenetics/DemographicSFS | repair first | 0.000 | 0.640 | 0.000 | -0.002 | 0 | no |
| PowerSystems/OptimalPowerFlow | saturated on ramp | 1.000 | 1.000 | 1.000 | 0.000 | 3 | no |
| ProteinEngineering/ProteinStabilityDesign | repair first | 0.614 | 0.535 | 0.546 | 0.058 | 0 | no |
| QuantumChemistry/HartreeFockSCF | saturated on ramp | 1.000 | 1.000 | 1.000 | 0.000 | 0 | no |
| QuantumControl/GateSynthesis | saturated on ramp | 1.000 | 1.000 | 1.000 | 0.000 | 3 | no |
| RNAEngineering/RNAInverseDesign | exploratory long horizon screen | 0.000 | 0.720 | 0.894 | 0.481 | 0 | no |
| ScientificComputing/PoissonSolver2D | saturated on ramp | 1.000 | -- | -- | -- | 0 | no |
| Semiconductor/MOSFETDoping | exploratory long horizon screen | 0.780 | 0.457 | 0.770 | 0.265 | 0 | no |
| Sensors/QuartzCrystalMicrobalanceLab | repair first | 0.000 | 0.000 | 0.000 | 0.000 | 0 | no |
| SignalProcessing/SparseRecovery | saturated on ramp | 0.958 | -- | -- | -- | 0 | no |
| Spectroscopy/NMRSpectrumFitting | repair first | 0.428 | 0.375 | -- | -0.163 | 0 | no |
| StructuralEngineering/TrussWeightMinimization | exploratory long horizon screen | 0.000 | 0.611 | 0.085 | 0.196 | 0 | no |
| SystemsBiology/GeneNetworkIntervention | repair first | 0.000 | 0.000 | 0.000 | -- | 0 | no |
| Thermodynamics/HeatExchangerDesign | exploratory long horizon screen | 0.000 | 0.126 | 0.294 | 0.118 | 0 | no |
| Thermodynamics/RankineCycleOpt | saturated on ramp | 0.964 | 1.000 | 1.000 | 0.000 | 0 | no |
| Turbulence/RANSCalibration | exploratory long horizon screen | 0.000 | 0.356 | 0.000 | 0.356 | 0 | no |
| WavePropagation/SeismicWaveInversion | repair first | 0.000 | 0.000 | 0.000 | 0.000 | 0 | no |

## Frozen exploratory cohort

- Electrochemistry/ElectrolyteConductivityDesign
- Optics/DiffractionGratingDesign
- RNAEngineering/RNAInverseDesign
- Semiconductor/MOSFETDoping
- StructuralEngineering/TrussWeightMinimization
- Thermodynamics/HeatExchangerDesign
- Turbulence/RANSCalibration

Diffraction has repeated controls and fresh procedural confirmation, but its short-run
distribution is high-variance. ActiveLaw is kept outside this optimization cohort as a
mechanism/refusal control because the repeated common-token normal-minus-blind estimate
did not identify a normal-feedback advantage.

## Next actions

1. Freeze the seven-task result-selected exploratory cohort before any 2 h run.
2. Measure fixed-artifact noise, evaluator resolution, first-valid rate, and baseline/reference separation before long runs.
3. Run every exploratory task for 2 h with t=0, first-valid, submission, fixed-grid, commit, and terminal sentinels.
4. Retain a random audit tranche to 12 h; do not deterministically stop all apparent 2 h failures.
5. Select any confirmatory cohort independently of these GPT-5.5 outcomes, ideally with sealed tasks or a different builder/model split.

The machine-readable report is authoritative for per-task checks, classification reasons,
selection limits, evidence binding, and next-stage restrictions.

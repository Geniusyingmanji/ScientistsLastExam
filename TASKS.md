# 任务汇总

由 `python scripts/report_task_inventory.py` 从注册表生成,`tests/test_task_inventory_document.py` 保证它不过期;不要手改。权威实时清单是 `python -m sle list --all`。

| | |
|---|---:|
| 任务包 | 61 |
| optimization | 29 |
| discovery | 32 |
| certified | 5 |
| candidate | 56 |
| 学科 | 7(Biology 7,Chemistry 13,ComputerScience 6,EarthScience 5,Engineering 10,Mathematics 9,Physics 11) |

认证描述的是证据质量,不是难度。标 on-ramp 的任务首个前沿模型提案已够到参考解,不用于配对 Δ 测量。

## Optimization(29)

### 工程设计(engineering_design) — 15

| 任务 | 学科 | 领域 | 打分 | oracle | 认证 | 说明 |
|---|---|---|---|---|---|---|
| [`AlloyHardnessOptimization`](benchmarks/Chemistry/AlloyHardnessOptimization/) | Chemistry | MaterialsScience | uncapped | real_data_replay | candidate | design a study-held alloy batch |
| [`DistillationColumnDesign`](benchmarks/Chemistry/DistillationColumnDesign/) | Chemistry | ChemicalProcess | uncapped | equilibrium_stage_process_sim | candidate | robust mixed-integer equilibrium-stage design |
| [`ElectrolyteConductivityDesign`](benchmarks/Chemistry/ElectrolyteConductivityDesign/) | Chemistry | Electrochemistry | uncapped | real_data_replay | candidate | allocate EIS assays and select a robust formulation batch |
| [`SparseRecovery`](benchmarks/ComputerScience/SparseRecovery/) | ComputerScience | SignalProcessing | clipped | analytical | candidate | compressed sensing signal recovery |
| [`HeatExchangerDesign`](benchmarks/Engineering/HeatExchangerDesign/) | Engineering | Thermodynamics | uncapped | physical_sim | candidate | discover a multi-fidelity Pareto design archive |
| [`InvertedPendulumSwingUp`](benchmarks/Engineering/InvertedPendulumSwingUp/) | Engineering | ControlTheory | clipped | physical_sim | candidate | swing up and robustly stabilize a cart-pole |
| [`LowThrustTransfer`](benchmarks/Engineering/LowThrustTransfer/) | Engineering | Astrodynamics | uncapped | physical_sim | candidate | design transferable finite-thrust orbit transfers |
| [`MOSFETDoping`](benchmarks/Engineering/MOSFETDoping/) | Engineering | Semiconductor | uncapped | physical_sim | candidate | design transferable silicon nMOS halo-profile Pareto archives |
| [`NeutronDiffusionCriticality`](benchmarks/Engineering/NeutronDiffusionCriticality/) | Engineering | NuclearEngineering | uncapped | physical_sim | candidate | optimize reactor fuel loading for maximum k-effective |
| [`RANSCalibration`](benchmarks/Engineering/RANSCalibration/) | Engineering | Turbulence | uncapped | physical_sim | candidate | calibrate a transferable algebraic channel-flow closure |
| [`RoomImpulseResponse`](benchmarks/Engineering/RoomImpulseResponse/) | Engineering | Acoustics | uncapped | physical_sim | candidate | robust room-acoustic treatment design |
| [`TrussWeightMinimization`](benchmarks/Engineering/TrussWeightMinimization/) | Engineering | StructuralEngineering | uncapped | analytical | candidate | general truss sizing under physical shifts |
| [`CalorimeterDesign`](benchmarks/Physics/CalorimeterDesign/) | Physics | ParticlePhysics | uncapped | analytical_reduced_order_physics | candidate | graded sampling-calorimeter design curves |
| [`DiffractionGratingDesign`](benchmarks/Physics/DiffractionGratingDesign/) | Physics | Optics | uncapped | fourier_modal_rcwa | candidate | polarization-tolerant multilayer relief design |
| [`MultilayerThinFilm`](benchmarks/Physics/MultilayerThinFilm/) | Physics | Photonics | clipped | physical_sim | certified | design a broadband antireflection coating |

### 开放组合纪录(combinatorial,无上限) — 9

| 任务 | 学科 | 领域 | 打分 | oracle | 认证 | 说明 |
|---|---|---|---|---|---|---|
| [`MatrixMultiplicationRank`](benchmarks/ComputerScience/MatrixMultiplicationRank/) | ComputerScience | Algorithm | uncapped | analytical | certified | discover faster matrix-multiplication algorithms |
| [`TensorRank555`](benchmarks/ComputerScience/TensorRank555/) | ComputerScience | Algorithm | uncapped | analytical | candidate | numerical complex decompositions for 5×5 and 6×6 multiplication |
| [`CapSet`](benchmarks/Mathematics/CapSet/) | Mathematics | Mathematics | uncapped | analytical | certified | find large cap sets in Z_3^n |
| [`CapSetFrontier`](benchmarks/Mathematics/CapSetFrontier/) | Mathematics | Mathematics | uncapped | analytical | candidate | large cap sets in dimensions that are still open |
| [`CirclePacking`](benchmarks/Mathematics/CirclePacking/) | Mathematics | Optimization | uncapped | analytical | certified | pack unit circles into the smallest square |
| [`KissingNumber`](benchmarks/Mathematics/KissingNumber/) | Mathematics | Mathematics | uncapped | analytical | candidate | pack more unit spheres around one sphere |
| [`RamseyLowerBound`](benchmarks/Mathematics/RamseyLowerBound/) | Mathematics | Mathematics | uncapped | analytical | candidate | construct larger (s,t)-Ramsey colorings |
| [`Superpermutation`](benchmarks/Mathematics/Superpermutation/) | Mathematics | Mathematics | uncapped | analytical | candidate | shorter strings that contain every permutation |
| [`QuantumErrorDecoder`](benchmarks/Physics/QuantumErrorDecoder/) | Physics | QuantumErrorCorrection | uncapped | stim_stabilizer_circuit_sampling | candidate | decode rotated surface-code memory below threshold |

### 分子与大分子设计(molecular_design) — 5

| 任务 | 学科 | 领域 | 打分 | oracle | 认证 | 说明 |
|---|---|---|---|---|---|---|
| [`ProteinStabilityDesign`](benchmarks/Biology/ProteinStabilityDesign/) | Biology | ProteinEngineering | uncapped | real_data_replay | candidate | allocate assays and design a stable protein batch |
| [`RNAEnsembleDesign`](benchmarks/Biology/RNAEnsembleDesign/) | Biology | RNAEngineering | uncapped | community_thermodynamics_viennarna | candidate | Design an RNA sequence that folds into a given secondary structure — not merely as its |
| [`RNAInverseDesign`](benchmarks/Biology/RNAInverseDesign/) | Biology | RNAEngineering | uncapped | exact_dynamic_programming | candidate | design a constrained sequence for a target ensemble |
| [`LennardJonesCluster`](benchmarks/Chemistry/LennardJonesCluster/) | Chemistry | Chemistry | uncapped | analytical | certified | minimize the energy of atomic clusters |
| [`MolecularLeadOptimization`](benchmarks/Chemistry/MolecularLeadOptimization/) | Chemistry | MedicinalChemistry | uncapped | rdkit_cheminformatics_property_filter | candidate | build a diverse portfolio of novel, developable leads |

## Discovery(32)

### 公式(formula) — 5

| 任务 | 学科 | 领域 | 打分 | oracle | 认证 | 说明 |
|---|---|---|---|---|---|---|
| [`EnzymeKineticsLaw`](benchmarks/Biology/EnzymeKineticsLaw/) | Biology | SystemsBiology | clipped | physical_sim | candidate | A purified enzyme is in front of you. · on-ramp,不配对 |
| [`AMOCTippingRefusal`](benchmarks/EarthScience/AMOCTippingRefusal/) | EarthScience | Oceanography | clipped | physical_sim | candidate | a dip in the fingerprint is not a fold |
| [`ActiveLawDiscovery`](benchmarks/Mathematics/ActiveLawDiscovery/) | Mathematics | DynamicalSystems | clipped | physical_sim | candidate | discover dynamical laws by choosing experiments |
| [`SequenceLawRecovery`](benchmarks/Mathematics/SequenceLawRecovery/) | Mathematics | Mathematics | clipped | community_symbolic_sympy | candidate | Given the first terms of an integer sequence, state the linear recurrence that produced it. |
| [`ComplexBoseLaw`](benchmarks/Physics/ComplexBoseLaw/) | Physics | Physics | clipped | physical_sim | candidate | a mixed cavity occupancy is not textbook Planck |

### 结构(structure) — 6

| 任务 | 学科 | 领域 | 打分 | oracle | 认证 | 说明 |
|---|---|---|---|---|---|---|
| [`GeneNetworkIntervention`](benchmarks/Biology/GeneNetworkIntervention/) | Biology | SystemsBiology | clipped | physical_sim | candidate | discover a dynamic regulatory network and design a phenotype intervention |
| [`GraphFromDistances`](benchmarks/ComputerScience/GraphFromDistances/) | ComputerScience | Algorithm | clipped | community_graph_algorithms_networkx | candidate | A weighted network exists but you cannot see it. |
| [`InterventionalSCM`](benchmarks/ComputerScience/InterventionalSCM/) | ComputerScience | CausalDiscovery | clipped | physical_sim | candidate | recover hidden causal mechanisms by experimentation |
| [`SurvivorshipConfoundedDesign`](benchmarks/ComputerScience/SurvivorshipConfoundedDesign/) | ComputerScience | CausalDiscovery | clipped | physical_sim | candidate | association among survivors is not a treatment effect |
| [`BlackBoxGroupIdentification`](benchmarks/Mathematics/BlackBoxGroupIdentification/) | Mathematics | Mathematics | clipped | analytical | candidate | A finite set of `order` labelled elements and a black-box product: `mul(a, b)` returns the label |
| [`HiddenCouplingNetwork`](benchmarks/Physics/HiddenCouplingNetwork/) | Physics | Physics | clipped | physical_sim | candidate | A network of `units` observed units relaxes to a steady state under constant drive. |

### 证据(evidence) — 5

| 任务 | 学科 | 领域 | 打分 | oracle | 认证 | 说明 |
|---|---|---|---|---|---|---|
| [`ProspectiveMetaAnalysis`](benchmarks/Biology/ProspectiveMetaAnalysis/) | Biology | EvidenceSynthesis | clipped | prospective_evidence_synthesis | candidate | synthesize registered evidence and design confirmation |
| [`ForcedSignalAttribution`](benchmarks/EarthScience/ForcedSignalAttribution/) | EarthScience | ClimateScience | clipped | statistical_sim | candidate | A regional field is observed for `years` years over `regions` regions. |
| [`DiscrepantMeasurements`](benchmarks/Physics/DiscrepantMeasurements/) | Physics | ParticlePhysics | clipped | statistical_sim | candidate | Eight groups have measured the same physical constant. · on-ramp,不配对 |
| [`LookElsewhereAnomaly`](benchmarks/Physics/LookElsewhereAnomaly/) | Physics | ParticlePhysics | clipped | physical_sim | candidate | local 5σ is not a discovery |
| [`PTAHellingsDowns`](benchmarks/Physics/PTAHellingsDowns/) | Physics | Gravitation | clipped | physical_sim | candidate | a common process is not a gravitational-wave background |

### 物质(substance) — 3

| 任务 | 学科 | 领域 | 打分 | oracle | 认证 | 说明 |
|---|---|---|---|---|---|---|
| [`CrowdedSpectrumAssignment`](benchmarks/Chemistry/CrowdedSpectrumAssignment/) | Chemistry | Spectroscopy | clipped | physical_sim | candidate | name the library species in a blended spectrum |
| [`PhaseDiagramDiscovery`](benchmarks/Chemistry/PhaseDiagramDiscovery/) | Chemistry | MaterialsScience | clipped | physical_sim | candidate | An isothermal section of a binary system A-B. |
| [`QuinaryConvexHull`](benchmarks/Chemistry/QuinaryConvexHull/) | Chemistry | MaterialsScience | clipped | analytical | candidate | E_f < 0 is not a new stable |

### 参数反演(parameter_inversion) — 13

| 任务 | 学科 | 领域 | 打分 | oracle | 认证 | 说明 |
|---|---|---|---|---|---|---|
| [`DemographicSFS`](benchmarks/Biology/DemographicSFS/) | Biology | PopulationGenetics | clipped | active_coalescent_inference | candidate | infer population history with a finite sequencing budget |
| [`CatalystDeactivationLab`](benchmarks/Chemistry/CatalystDeactivationLab/) | Chemistry | Catalysis | clipped | stateful_reduced_order_kinetics | candidate | run a stateful catalyst laboratory under instrument drift |
| [`ForceFieldCalibration`](benchmarks/Chemistry/ForceFieldCalibration/) | Chemistry | MolecularDynamics | clipped | active_pair_potential_hypothesis_laboratory | candidate | discriminate pair-potential hypotheses by active force queries |
| [`NMRSpectrumFitting`](benchmarks/Chemistry/NMRSpectrumFitting/) | Chemistry | Spectroscopy | clipped | physical_sim | candidate | recover supported peak mechanisms across spectra |
| [`ReactionMechanismFitting`](benchmarks/Chemistry/ReactionMechanismFitting/) | Chemistry | ChemicalKinetics | clipped | physical_sim | candidate | discover a reaction network by choosing assays |
| [`SpinSystemInference`](benchmarks/Chemistry/SpinSystemInference/) | Chemistry | Spectroscopy | clipped | community_spin_dynamics_nmrsim | candidate | Given a high-resolution proton NMR spectrum, recover the spin system that produced it: the |
| [`EnergyBalanceModel`](benchmarks/EarthScience/EnergyBalanceModel/) | EarthScience | ClimateScience | clipped | active_system_identification | candidate | identify climate response by choosing forcing experiments |
| [`GravityInversion`](benchmarks/EarthScience/GravityInversion/) | EarthScience | Geophysics | clipped | physical_sim | candidate | actively survey and infer subsurface density bodies |
| [`RadiativeTransferFit`](benchmarks/EarthScience/RadiativeTransferFit/) | EarthScience | AtmosphericScience | clipped | physical_sim | candidate | actively select thermal channels and retrieve an atmospheric mechanism |
| [`ConvectionDiffusionOpt`](benchmarks/Engineering/ConvectionDiffusionOpt/) | Engineering | HeatTransfer | clipped | active_pde_identification_and_robust_design | candidate | identify transport and design a robust heater layout |
| [`QuartzCrystalMicrobalanceLab`](benchmarks/Engineering/QuartzCrystalMicrobalanceLab/) | Engineering | Sensors | clipped | raw_complex_instrument_pipeline | candidate | infer deposition from raw I/Q sweeps |
| [`HamiltonianLearning`](benchmarks/Physics/HamiltonianLearning/) | Physics | QuantumDynamics | clipped | community_quantum_dynamics_qutip | candidate | Recover the Hamiltonian of a closed quantum spin chain from the dynamics it generates. |
| [`RadialVelocityPlanets`](benchmarks/Physics/RadialVelocityPlanets/) | Physics | Exoplanets | clipped | community_timeseries_astropy | candidate | A star's spectrum shows a periodic Doppler shift. |

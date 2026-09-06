# PR #9 Frontier-Eng overlap review (2026-09-06)

## Sources and scope

- Paper: https://arxiv.org/html/2604.12290v1#A1 — all 47 Appendix A entries, including the seven EngDesign subproblems.
- Repository: https://github.com/Einsia/Frontier-Engineering/blob/e3fa29c193356af2ce1ec8b3d23ab1a2e2410071/TASK_DETAILS.md — retrieved 2026-09-06. The catalog contains **78 table rows / 84 tasks after expanding EngDesign**, not 95. The recursive tree likewise has 78 Task.md paths. This discrepancy is unresolved; we do not claim to have reviewed an unavailable 95-entry version. Please identify that revision or the missing entries before treating the requested review as complete.
- Additional source reconciliation: `TASK_DETAILS_zh-CN.md` at the same main commit also has 78 rows / 84 expanded tasks. The `v1-arxiv` branch and first catalog revision `57cb4e52ea1c553f0bf36e956502f4135f7a9dee` each have 77 rows / 83 expanded tasks. None supplies the requested 95-entry list.
- EngDesign subtask prompts at the same commit were checked: CY_03 (block driver), WJ_01 (image filtering), XY_05 (CPU control), AM_02/AM_03 (robot navigation), YJ_02 (beam compliance), YJ_03 (crack stress intensity).
- SLE source: original PR #9 head 3106a1e; split batches based on upstream 2cbf72b (76 tasks). 20 submitted tasks are split into five independent batches; MetabolicStrainDesign is deferred.

This is an author comparison of artifacts, governing models and objectives, not independent domain review or certification. No renamed task or changed random seed is counted as novelty. “无” means no matching scientific task in the checked sources; shared numerical methods alone are not a match. “同类不同题” exposes a problem-family relation, which still needs maintainer acceptance under CONTRIBUTING. No checked entry was classified as the identical task.

## Per-task comparison

| SLE task | Conclusion | Nearest Frontier-Eng entries | Difference / remaining decision |
|---|---|---|---|
| ActiveFullWaveformInversion | 无 | CarAerodynamicsSensing; holographic_multiplane_focusing | Budgeted acoustic shots recover a subsurface velocity grid and test model adequacy; FE selects car pressure sensors or designs optical phase masks. Neither recovers acoustic velocity from acquired waveforms. |
| ChronologyAssimilation | 无 | predict_modality; denoising | Paid dating observations jointly constrain sample ages and climate reconstruction with unsupported-world refusal; FE predicts cell modalities or removes image/RNA noise without an age-depth chronology. |
| GroundwaterRemediationDesign | 无 | BatteryFastChargingProfile; EV2GymSmartCharging | Choose extraction-well locations, activation times and rates under contaminant transport, mass balance and receptor limits; FE controls battery charge. Shared time-dependent design does not share governing physics or the remediation objective. |
| IceObservationNetworkDesign | 同类不同题 | CarAerodynamicsSensing; MuonTomography | Both choose observations. Here a costed mixed instrument subset reduces three ice forecast errors under correlated noise and dynamics shifts; FE selects car-surface pressure locations or muon detector geometry. Whether this observation-design family is sufficiently distinct remains a maintainer judgment. |
| FocalMechanismStressInversion | 无 | torsion_profile_fitting | Recover a stress tensor and per-event nodal plane choices, with mixed-regime refusal; FE fits force-field torsion energy scales. Both fit numbers, but neither the observable nor latent scientific structure is shared. |
| MineralMixtureXRD | 无 | predict_modality; phase_fourier_pattern_holography | Paid diffraction windows identify crystalline phases and weights, separating amorphous background and unknown phases; FE predicts molecular modalities or synthesizes a holographic phase mask, rather than identifying a mineral mixture. |
| BOPTESTSupervisoryControl | 同类不同题 | hand_written_control; PIDTuning | Stateful two-zone heating/cooling/ventilation satisfies occupied temperature and CO2 gates under biased forecasts and actuator shifts. FE data-center control couples cooling with workload shifting and battery dispatch, optimizing carbon/water; PIDTuning controls flight. The HVAC/control-family overlap remains high risk and requires explicit maintainer acceptance. |
| CompositeLaminateStacking | 同类不同题 | ISCSO2015; ISCSO2023; TopologyOptimization; PyMOTOSIMPCompliance; EngDesign/YJ_02; EngDesign/YJ_03; DawnAircraftDesignOptimization | Order a fixed balanced symmetric ply multiset under manufacturing constraints to improve buckling and first-ply reserve. FE varies truss sections, continuum density, crack-tip material layout or aircraft geometry/mass. Fixed material composition and ply order are the decision space here; structural-design family overlap is disclosed. |
| ResilientPumpScheduling | 同类不同题 | BatteryFastChargingProfile; BatteryFastChargingSPMe; EV2GymSmartCharging; finite_horizon_dp | A 24-hour on/off and pump-speed plan obeys minimum run, pressure, tank storage and terminal recovery under demand/outage scenarios. FE schedules electrical charge or stock replenishment. Water storage dynamics and service constraints differ, though constrained energy/storage scheduling is shared. |
| WakeAwareFarmCoDesign | 无 | UAVInspectionCoverageWithWind; DawnAircraftDesignOptimization | Joint static turbine locations and directional yaw optimize farm value with wake interactions and wind-rose transfer. FE optimizes flight coverage in wind or aircraft mass/geometry, without turbine-to-turbine wakes or wind-farm yield. |
| PermutationFlowShop | 同类不同题 | JobShop/abz; JobShop/ft; JobShop/la; JobShop/orb; JobShop/swv; JobShop/ta; JobShop/yn | Submit one common job permutation on all machines with a fixed common route; FE JSSP permits job-specific routes and operation schedules. Fresh seeds prevent table lookup but do not establish novelty. PFSP is a restricted scheduling problem with the same makespan objective: admission is explicitly pending a maintainer decision, not declared clear. |
| DistributionNetworkTopology | 无 | EV2GymSmartCharging; tree_gsm_safety_stock | Paid path tests identify failed water pipes with inseparable twin-line refusal. FE chooses charging schedules or inventory service times on known graphs. Despite the name, this task diagnoses failures on a supplied route graph; it is not network-layout or energy-dispatch optimization. |
| ChronoamperometryLawID | 无 | snar_multiobjective; mit_case1_mixed; reizman_suzuki_pareto; BatteryFastChargingSPMe | Choose potential-step measurements to discriminate current-law families and refuse drift/fractional transport. FE optimizes reaction yield/Pareto fronts or charging; it does not return a scientific family decision and calibrated refusal. |
| MassFragmentationTree | 无 | weighted_parameter_coverage; diverse_conformer_portfolio; torsion_profile_fitting | Charged MS/MS queries reconstruct directed neutral-loss fragment trees with co-isolation/no-precursor refusal. FE chooses molecules/conformers or fits force-field energies. Molecular context alone does not share the inverse graph problem. |
| ThermochemicalCycleAudit | 无 | snar_multiobjective; mit_case1_mixed; reizman_suzuki_pareto | Replicates and cross-checks diagnose enthalpy-network inconsistency, instrument drift and unidentifiable fault attribution. FE selects reaction conditions for yield or waste; no measurement-consistency verdict is requested. |
| HodgkinHuxleyCurrentID | 无 | predict_modality; perturbation_prediction; PIDTuning | Budgeted voltage-clamp experiments recover membrane-current parameters and refuse extra-current worlds. FE predicts cell responses or tunes a flying controller, not membrane conductance inference. |
| OrthogonalDNACodewords | 无 | HighReliableSimulation; LDPCErrorFloor | Construct a maximal DNA word library satisfying exact GC, homopolymer, Hamming and shifted cross-dimer constraints. FE estimates error probabilities of fixed communication codes; it does not construct biochemical codewords. |
| ScalingLawIdentification | 无 | MallocLab; MLA; FlashAttention; TriMul | Pay to observe a black-box size ladder, classify asymptotic runtime and refuse branching/noise floors. FE implements faster kernels/allocators rather than inferring a law from budgeted timings. |
| EllipticCurveRecovery | 无 | AES-128 CTR; SHA-256; SHA3-256 | Query finite-field point counts at chosen primes and recover an integer elliptic-curve coefficient pair or refuse. FE implements symmetric cryptographic throughput, with no arithmetic-geometry inverse problem. |
| ExactIdentityEvidence | 无 | clifford_t_synthesis; cross_target_qaoa | Purchase digits to distinguish exact identities, near coincidences and undecidable claims, returning integer relations and verdicts. FE optimizes quantum circuit representations rather than certifying numerical evidence. |
| MetabolicStrainDesign | 无 | snar_multiobjective; mit_case1_mixed | FE reaction-condition optimization is distinct from network FBA edit-set design. Nevertheless this implementation is deferred because PR #13 owns the same registry ID/path; no unilateral rename or assertion of coordination is made. |

## Deferred / already removed tasks

- MetabolicEngineering/MetabolicStrainDesign: excluded from every split batch to leave PR #13's identical path/ID uncontested. The 225-line implementation is preserved at BLGZZY/ScientistsLastExam commit 3106a1e. This is a unilateral deferral, not a claimed agreement with the other author.
- Metagenomics/MetagenomicMixtureID: already removed at 3106a1e for difficulty reasons; remains out, so it cannot duplicate #13's Microbiology/MetagenomeCompositionAssignment in these batches.
- Wastewater/BSM1AerationControl and Volcanology/DeformationMechanismInference: already removed at 3106a1e for difficulty reasons and not restored. No new admission claim is made for them.

## Exhaustive checked-source index

All entries below were considered against all tasks above. The nearest-neighbor column identifies the substantive relations; other pairings share neither scientific artifact nor objective. The index is included to make catalog coverage and the 95-entry discrepancy reviewable.

### Paper Appendix A (47 entries)

1. FlashAttention
2. MLA (Multi-Head Latent Attention)
3. TriMul (Triangular Multiplicative Update)
4. MallocLab
5. AES-128
6. SHA-256
7. SHA3-256
8. Routing QFTEntangled
9. Clifford+T Synthesis
10. Cross-Target QAOA
11. tree_gsm_safety_stock
12. general_meio
13. joint_replenishment
14. finite_horizon_dp
15. disruption_eoqd
16. abz
17. swv
18. ta
19. robust_mvo_rebalance
20. DynamicObstacleAvoidanceNavigation
21. PIDTuning
22. QuadrupedGaitOptimization
23. RobotArmCycleTimeOptimization
24. UAVInspectionCoverageWithWind
25. BatteryFastChargingProfile
26. BatteryFastChargingSPMe
27. hand_written_control
28. adaptive_fault_tolerant_fusion
29. adaptive_temporal_smooth_control
30. phase_dammann_uniform_orders
31. phase_fourier_pattern_holography
32. fiber_wdm_channel_power_allocation
33. fiber_mcs_power_scheduling
34. fiber_guardband_spectrum_packing
35. holographic_multifocus_power_ratio
36. holographic_multiplane_focusing
37. HighReliableSimulation
38. ISCSO2015
39. ISCSO2023
40. TopologyOptimization
41. snar_multiobjective
42. mit_case1_mixed
43. reizman_suzuki_pareto
44. MannedLunarLanding
45. CarAerodynamicsSensing
46. predict_modality
47. EngDesign

### Repository catalog (84 expanded entries)

1. Astrodynamics/MannedLunarLanding
2. ParticlePhysics/MuonTomography
3. ParticlePhysics/ProtonTherapyPlanning
4. KernelEngineering/MLA
5. KernelEngineering/TriMul
6. KernelEngineering/FlashAttention
7. SingleCellAnalysis/denoising
8. SingleCellAnalysis/perturbation_prediction
9. SingleCellAnalysis/predict_modality
10. QuantumComputing/routing_qftentangled
11. QuantumComputing/clifford_t_synthesis
12. QuantumComputing/cross_target_qaoa
13. Cryptographic/AES-128 CTR
14. Cryptographic/SHA-256
15. Cryptographic/SHA3-256
16. CommunicationEngineering/LDPCErrorFloor
17. CommunicationEngineering/PMDSimulation
18. CommunicationEngineering/RayleighFadingBER
19. EnergyStorage/BatteryFastChargingProfile
20. EnergyStorage/BatteryFastChargingSPMe
21. SustainableDataCenterControl/hand_written_control
22. ReactionOptimisation/snar_multiobjective
23. ReactionOptimisation/mit_case1_mixed
24. ReactionOptimisation/reizman_suzuki_pareto
25. ReactionOptimisation/dtlz2_pareto
26. MolecularMechanics/weighted_parameter_coverage
27. MolecularMechanics/diverse_conformer_portfolio
28. MolecularMechanics/torsion_profile_fitting
29. Optics/adaptive_constrained_dm_control
30. Optics/adaptive_temporal_smooth_control
31. Optics/adaptive_energy_aware_control
32. Optics/adaptive_fault_tolerant_fusion
33. Optics/phase_weighted_multispot_single_plane
34. Optics/phase_fourier_pattern_holography
35. Optics/phase_dammann_uniform_orders
36. Optics/phase_large_scale_weighted_spot_array
37. Optics/fiber_wdm_channel_power_allocation
38. Optics/fiber_mcs_power_scheduling
39. Optics/fiber_dsp_mode_scheduling
40. Optics/fiber_guardband_spectrum_packing
41. Optics/holographic_multifocus_power_ratio
42. Optics/holographic_multiplane_focusing
43. Optics/holographic_multispectral_focusing
44. Optics/holographic_polarization_multiplexing
45. ComputerSystems/MallocLab
46. ComputerSystems/DuckDBWorkloadOptimization
47. EngDesign/CY_03
48. EngDesign/WJ_01
49. EngDesign/XY_05
50. EngDesign/AM_02
51. EngDesign/AM_03
52. EngDesign/YJ_02
53. EngDesign/YJ_03
54. InventoryOptimization/tree_gsm_safety_stock
55. InventoryOptimization/general_meio
56. InventoryOptimization/joint_replenishment
57. InventoryOptimization/finite_horizon_dp
58. InventoryOptimization/disruption_eoqd
59. PyPortfolioOpt/robust_mvo_rebalance
60. PyPortfolioOpt/cvar_stress_control
61. PyPortfolioOpt/discrete_rebalance_mip
62. MarketMaking/InventoryAwareQuoting
63. JobShop/abz
64. JobShop/ft
65. JobShop/la
66. JobShop/orb
67. JobShop/swv
68. JobShop/ta
69. JobShop/yn
70. StructuralOptimization/ISCSO2015
71. StructuralOptimization/ISCSO2023
72. StructuralOptimization/TopologyOptimization
73. StructuralOptimization/PyMOTOSIMPCompliance
74. Robotics/DynamicObstacleAvoidanceNavigation
75. Robotics/QuadrupedGaitOptimization
76. Robotics/RobotArmCycleTimeOptimization
77. Robotics/PIDTuning
78. Robotics/UAVInspectionCoverageWithWind
79. Robotics/CoFlyersVasarhelyiTuning
80. Aerodynamics/CarAerodynamicsSensing
81. Aerodynamics/DawnAircraftDesignOptimization
82. WirelessChannelSimulation/HighReliableSimulation
83. PowerSystems/EV2GymSmartCharging
84. AdditiveManufacturing/DiffSimThermalControl

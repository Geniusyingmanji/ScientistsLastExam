# GPT-5.6 50-task science census

This is a complete census of the 50 internally admitted tasks (7 certified and 43 candidate), with one unseeded-provider, normal-feedback, budget-one draw per task. The nine quarantined tasks are excluded.

## Verdict

The portfolio has recognizable scientific applications, domain-specific oracles, professional knowledge and scientific-tool requirements, and it clearly separates task outcomes. It is **not yet a uniformly hard GPT-5.6 benchmark**: the preregistered challenge gate fails (12 executable tasks below 0.50 versus a threshold of 15), 13 valid tasks are near ceiling, and 14 tasks are blocked by candidate execution or submission failures.

| Requirement | Verdict | Evidence |
|---|---|---|
| Scientific application | Internal pass | 50/50 name a scientific question, artifact, oracle and metric; 153 citations |
| Professional knowledge / tools | Internal pass | 50/50 require mapped simulation, inference, optimization, signal, PDE, statistical or exact-algorithm tools |
| Executable difficulty | Partial / gate fail | 12 valid tasks below 0.50; threshold 15 |
| Discrimination | Pass | all four executable score bands occupied; range 1.0 |
| Anti-saturation | Narrow pass | 13/36 valid tasks (36.1%) at or above 0.95; threshold at most 40% |
| Self-evolving / RSI | Structurally suitable, not demonstrated | 15 iterative-study candidates; budget one is not evolution and the four-task pilot has no positive online-feedback signal |
| External validity | Not passed | 0/50 externally validated, open-release ready or long-horizon ready |

## Outcome distribution

| Outcome | Tasks | Meaning |
|---|---:|---|
| Protocol blocked | 14 | invalid proposal; excluded from scientific-difficulty count |
| Executable floor (<=0.01) | 6 | executable but essentially no terminal progress |
| Difficult (0.01-0.50) | 6 | clean one-step challenge |
| Discriminating (0.50-0.95) | 11 | material progress with headroom |
| Near ceiling (>=0.95) | 13 | on-ramp or needs a harder regime |

Proposal validity is 36/50 (72.0%). Candidate failures split into `{"candidate_execution_failure": 8, "submission_or_protocol_failure": 6}`.

## Discipline summary

| Discipline | Tasks | Valid | Evolution candidates | Near ceiling |
|---|---:|---:|---:|---:|
| Biology | 5 | 3 | 3 | 0 |
| Chemistry | 10 | 7 | 3 | 3 |
| ComputerScience | 4 | 4 | 0 | 4 |
| EarthScience | 6 | 5 | 0 | 2 |
| Engineering | 14 | 9 | 5 | 1 |
| Mathematics | 5 | 5 | 3 | 2 |
| Physics | 6 | 3 | 1 | 1 |

## Self-evolving study pool

The preregistered rule nominates 15 tasks with a valid score in `[0.05, 0.95)`. This is a follow-up pool, not evidence that feedback helps. Historical GPT-5.5 budget-three and selection-blind results exist for 11/15, material within-normal post-first-valid gains for 8/15, and at least three matched controls for only 1/15.

| Task | GPT-5.6 best | Prior b3 / blind | Prior material later gain |
|---|---:|---:|---|
| `PopulationGenetics/DemographicSFS` | 0.565934 | 1 / 1 | no |
| `ProteinEngineering/ProteinStabilityDesign` | 0.476907 | 1 / 1 | yes |
| `RNAEngineering/RNAInverseDesign` | 0.867721 | 1 / 1 | yes |
| `Electrochemistry/ElectrolyteConductivityDesign` | 0.543055 | 1 / 1 | yes |
| `Spectroscopy/NMRSpectrumFitting` | 0.333275 | 1 / 0 | no |
| `ChemicalKinetics/ReactionMechanismFitting` | 0.541862 | 1 / 1 | no |
| `Astrodynamics/LowThrustTransfer` | 0.513522 | 1 / 1 | no |
| `Semiconductor/MOSFETDoping` | 0.665027 | 1 / 1 | yes |
| `NuclearEngineering/NeutronDiffusionCriticality` | 0.831723 | 1 / 1 | yes |
| `Turbulence/RANSCalibration` | 0.355935 | 1 / 1 | yes |
| `StructuralEngineering/TrussWeightMinimization` | 0.409781 | 1 / 1 | yes |
| `DynamicalSystems/ActiveLawDiscovery` | 0.797994 | 48 / 48 | yes |
| `Mathematics/CapSet` | 0.656517 | 0 / 0 | no |
| `Optimization/CirclePacking` | 0.726603 | 0 / 0 | no |
| `Photonics/MultilayerThinFilm` | 0.813796 | 0 / 0 | no |

The separate four-task GPT-5.6 budget-three pilot records zero normal wins, two selection-blind wins and two ties. With one draw and no provider seed, that is no positive feedback signal and also not a causal null result.

## Protocol-blocked tasks

| Task | Failure class | Failure kind |
|---|---|---|
| `SystemsBiology/GeneNetworkIntervention` | submission_or_protocol_failure | `invalid_submission` |
| `EvidenceSynthesis/ProspectiveMetaAnalysis` | submission_or_protocol_failure | `wrong_submission_fields` |
| `Catalysis/CatalystDeactivationLab` | submission_or_protocol_failure | `invalid_submission` |
| `ChemicalProcess/DistillationColumnDesign` | candidate_execution_failure | `candidate_timeout` |
| `MolecularDynamics/ForceFieldCalibration` | submission_or_protocol_failure | `invalid_submission` |
| `Oceanography/OceanCurrentInversion` | submission_or_protocol_failure | `invalid_experiment_request` |
| `AcousticMetamaterials/BroadbandAbsorber` | candidate_execution_failure | `candidate_runtime_error` |
| `HeatTransfer/ConvectionDiffusionOpt` | candidate_execution_failure | `candidate_runtime_error` |
| `Thermodynamics/HeatExchangerDesign` | candidate_execution_failure | `candidate_runtime_error` |
| `FluidDynamics/LidDrivenCavity` | submission_or_protocol_failure | `invalid_candidate_artifact` |
| `PowerSystems/OptimalPowerFlow` | candidate_execution_failure | `candidate_worker_exit` |
| `Electromagnetics/AntennaArraySynthesis` | candidate_execution_failure | `candidate_worker_exit` |
| `ParticlePhysics/CalorimeterDesign` | candidate_execution_failure | `candidate_runtime_error` |
| `Physics/SpinGlassGroundState` | candidate_execution_failure | `candidate_runtime_error` |

## All task results and scientific basis

| Task | Scientific outcome | Tool family | Valid | Best | Disposition |
|---|---|---|:---:|---:|---|
| `PopulationGenetics/DemographicSFS` | demographic parameter recovery, held-out sample-size prediction, model-inadequacy refusal and budgeted sequencing design | coalescent stochastic-process modeling, active sequencing design, likelihood-based demographic inference and refusal | yes | 0.565934 | discriminating |
| `SystemsBiology/GeneNetworkIntervention` | active_signed_network_recovery_prediction_phenotype_intervention_transfer_and_refusal | domain simulation, numerical optimization or inverse inference, held-out and robustness analysis | no | 0.000000 | protocol blocked |
| `EvidenceSynthesis/ProspectiveMetaAnalysis` | registry screening, evidence-lineage integrity, heterogeneous meta-regression, calibrated refusal, next-study information and fresh prospective confirmation | evidence screening and meta-regression, uncertainty-calibrated forecasting, prospective study design and confirmation | no | 0.000000 | protocol blocked |
| `ProteinEngineering/ProteinStabilityDesign` | budgeted_batch_stability_top_decile_diversity_protease_robustness_and_domain_transfer | data preprocessing and statistical modeling, budgeted experimental or batch selection, uncertainty and transfer validation | yes | 0.476907 | difficult |
| `RNAEngineering/RNAInverseDesign` | constrained_rna_target_ensemble_probability_defect_mfe_transfer_and_proxy_false_promotion | thermodynamic dynamic programming, constrained sequence design, ensemble and transfer verification | yes | 0.867721 | discriminating |
| `MaterialsScience/AlloyHardnessOptimization` | budgeted_study_held_hardness_diversity_proxy_failure_uncertainty_source_transfer_and_sparse_independent_confirmation | data preprocessing and statistical modeling, budgeted experimental or batch selection, uncertainty and transfer validation | yes | 0.029681 | difficult |
| `Catalysis/CatalystDeactivationLab` | lineage-bound kinetic and calibration-drift recovery with irreversible coupon deactivation, out-of-order completion, model refusal and sealed fresh-batch decision utility | kinetic-system identification, stateful experimental scheduling, drift, refusal and decision analysis | no | 0.000000 | protocol blocked |
| `ChemicalProcess/DistillationColumnDesign` | nominal annualized reduced-order column cost subject to equilibrium-stage purity and recovery constraints, with separate held-out transfer and sealed off-design feasibility | equilibrium-stage process simulation, mixed discrete-continuous optimization, off-design feasibility analysis | no | 0.000000 | protocol blocked |
| `Electrochemistry/ElectrolyteConductivityDesign` | budgeted_temperature_profile_conductivity_batch_diversity_repeat_robustness_and_heldout_transfer | data preprocessing and statistical modeling, budgeted experimental or batch selection, uncertainty and transfer validation | yes | 0.543055 | discriminating |
| `MolecularDynamics/ForceFieldCalibration` | active_competing_hypothesis_retention_model_discrimination_parameter_interval_recovery_sealed_energy_force_prediction_virial_decision_and_model_refusal | energy and force modeling, active hypothesis discrimination and uncertainty, virial integration and model-inadequacy refusal | no | 0.000000 | protocol blocked |
| `QuantumChemistry/HartreeFockSCF` | stable restricted Hartree-Fock energy improvement across finite-basis closed-shell molecular Hamiltonians | Hartree-Fock matrix equations, stable nonlinear SCF optimization, representation and stability diagnostics | yes | 1.000000 | near ceiling |
| `Chemistry/LennardJonesCluster` | mean_gap_closed_to_global_minimum | domain equations or exact combinatorial structure, constrained numerical or discrete optimization, feasibility verification | yes | 0.984703 | near ceiling |
| `Spectroscopy/NMRSpectrumFitting` | peak_mechanism_recovery_with_shifted_reconstruction_and_model_inadequacy_refusal | domain simulation, numerical optimization or inverse inference, held-out and robustness analysis | yes | 0.333275 | difficult |
| `Photovoltaics/PhotovoltaicTandemDesign` | budget-conditioned finite-absorption tandem detailed-balance efficiency with separate held-out spectrum transfer, current matching and worst thermal-process-optical robustness | reduced-order physical equations, constrained design optimization, sensitivity and robustness analysis | yes | 0.997120 | near ceiling |
| `ChemicalKinetics/ReactionMechanismFitting` | active_arrhenius_mechanism_recovery_with_refusal_and_extrapolation | domain simulation, numerical optimization or inverse inference, held-out and robustness analysis | yes | 0.541862 | discriminating |
| `CausalDiscovery/InterventionalSCM` | directed_graph_and_structural_coefficient_recovery | domain simulation, numerical optimization or inverse inference, held-out and robustness analysis | yes | 0.991470 | near ceiling |
| `Algorithm/MatrixMultiplicationRank` | mean_progress_to_best_known_scalar_mult_count | domain equations or exact combinatorial structure, constrained numerical or discrete optimization, feasibility verification | yes | 0.979167 | near ceiling |
| `ScientificComputing/PoissonSolver2D` | log_scaled_error_reduction | domain equations or exact combinatorial structure, constrained numerical or discrete optimization, feasibility verification | yes | 1.000000 | near ceiling |
| `SignalProcessing/SparseRecovery` | mean_recovery_snr | domain equations or exact combinatorial structure, constrained numerical or discrete optimization, feasibility verification | yes | 0.958301 | near ceiling |
| `ClimateScience/EnergyBalanceModel` | two-layer climate-response parameter recovery, forcing transfer, model-inadequacy refusal and budgeted experiment design | active dynamical-system identification, parameter and forcing inference, model-mismatch refusal and transfer | yes | 0.000000 | executable floor |
| `Geophysics/GravityInversion` | active_gravity_source_recovery_with_external_field_validation_and_refusal | domain simulation, numerical optimization or inverse inference, held-out and robustness analysis | yes | 0.983558 | near ceiling |
| `Oceanography/OceanCurrentInversion` | active_divergence_free_current_mechanism_recovery_with_refusal_and_extrapolation | domain simulation, numerical optimization or inverse inference, held-out and robustness analysis | no | 0.000000 | protocol blocked |
| `AtmosphericScience/RadiativeTransferFit` | active_temperature_and_optical_depth_mechanism_recovery_with_model_inadequacy_refusal | domain simulation, numerical optimization or inverse inference, held-out and robustness analysis | yes | 0.000000 | executable floor |
| `Geophysics/SeismicInversion` | refraction_pick_rmse_with_separate_velocity_and_holdout_scores | domain simulation, numerical optimization or inverse inference, held-out and robustness analysis | yes | 0.998144 | near ceiling |
| `WavePropagation/SeismicWaveInversion` | active_layered_velocity_recovery_with_waveform_transfer_and_model_inadequacy_refusal | experiment or survey design, physical inverse modeling, extrapolation and model-inadequacy tests | yes | 0.000000 | executable floor |
| `AcousticMetamaterials/BroadbandAbsorber` | broadband normal-incidence absorption with separate public-proxy agreement, held-out bands and sealed angle, air-property and manufacturing robustness | domain equations or exact combinatorial structure, constrained numerical or discrete optimization, feasibility verification | no | 0.000000 | protocol blocked |
| `HeatTransfer/ConvectionDiffusionOpt` | budgeted anisotropic convection-diffusion mechanism recovery, target-field heater design, physical-shift robustness and model-inadequacy refusal | PDE simulation and inverse identification, active sensor or actuator design, robust constrained optimization | no | 0.000000 | protocol blocked |
| `Thermodynamics/HeatExchangerDesign` | development exact cost-versus-duty Pareto hypervolume with sealed proxy agreement, held-out transfer and fouling/manufacturing/blockage robustness | domain simulation, numerical optimization or inverse inference, held-out and robustness analysis | no | 0.000000 | protocol blocked |
| `ControlTheory/InvertedPendulumSwingUp` | development_swing_up_utility_with_separate_shifted_robustness | domain simulation, numerical optimization or inverse inference, held-out and robustness analysis | yes | 0.000021 | executable floor |
| `FluidDynamics/LidDrivenCavity` | full-field steady incompressible Navier-Stokes accuracy with public residual feasibility and sealed Reynolds/grid transfer | PDE discretization and nonlinear solution, residual and conservation diagnostics, grid and parameter transfer | no | 0.000000 | protocol blocked |
| `Astrodynamics/LowThrustTransfer` | nominal_transfer_utility_with_separate_heldout_phase_and_execution_robustness | domain simulation, numerical optimization or inverse inference, held-out and robustness analysis | yes | 0.513522 | discriminating |
| `Semiconductor/MOSFETDoping` | development nominal compact-model drive-current-versus-leakage Pareto hypervolume with sealed held-out transfer and worst-shift robustness | domain simulation, numerical optimization or inverse inference, held-out and robustness analysis | yes | 0.665027 | discriminating |
| `NuclearEngineering/NeutronDiffusionCriticality` | k_eff_improvement_over_uniform | domain simulation, numerical optimization or inverse inference, held-out and robustness analysis | yes | 0.831723 | discriminating |
| `PowerSystems/OptimalPowerFlow` | nominal_DC_OPF_cost_with_sealed_N_minus_1_security | domain equations or exact combinatorial structure, constrained numerical or discrete optimization, feasibility verification | no | 0.000000 | protocol blocked |
| `Sensors/QuartzCrystalMicrobalanceLab` | evidence-bound raw-IQ calibration, BVD resonance extraction, rigid-film mass/rate recovery, fault-versus-model diagnosis and sealed deposition-stop decision | complex-signal calibration, nonlinear resonance fitting, physical versus instrument-fault diagnosis | yes | 0.000000 | executable floor |
| `Turbulence/RANSCalibration` | development real-DNS mean-velocity-plus-Reynolds-shear closure fit with sealed higher-Re transfer and wall-coordinate robustness | domain simulation, numerical optimization or inverse inference, held-out and robustness analysis | yes | 0.355935 | difficult |
| `Thermodynamics/RankineCycleOpt` | development IF97 single-reheat efficiency-versus-specific-work Pareto hypervolume with sealed held-out transfer and degradation robustness | domain simulation, numerical optimization or inverse inference, held-out and robustness analysis | yes | 0.968361 | near ceiling |
| `Acoustics/RoomImpulseResponse` | room_clarity_reverberation_and_uniformity_utility | domain simulation, numerical optimization or inverse inference, held-out and robustness analysis | yes | 0.000000 | executable floor |
| `StructuralEngineering/TrussWeightMinimization` | nominal weight reduction with sealed topology transfer and load/material/manufacturing robustness | domain equations or exact combinatorial structure, constrained numerical or discrete optimization, feasibility verification | yes | 0.409781 | difficult |
| `DynamicalSystems/ActiveLawDiscovery` | active_sparse_law_recovery_with_sealed_rollout_and_refusal | domain simulation, numerical optimization or inverse inference, held-out and robustness analysis | yes | 0.797994 | discriminating |
| `Mathematics/CapSet` | mean_progress_to_best_known_cap_size | domain equations or exact combinatorial structure, constrained numerical or discrete optimization, feasibility verification | yes | 0.656517 | discriminating |
| `Optimization/CirclePacking` | mean_gap_closed_to_best_known_packing | domain equations or exact combinatorial structure, constrained numerical or discrete optimization, feasibility verification | yes | 0.726603 | discriminating |
| `DynamicalSystems/LyapunovControl` | lyapunov_exponent_reduction | domain simulation, numerical optimization or inverse inference, held-out and robustness analysis | yes | 1.000000 | near ceiling |
| `BayesianInference/OptimalExperimentDesign` | normalized_D_efficiency_with_sealed_shifted_family_validation | domain equations or exact combinatorial structure, constrained numerical or discrete optimization, feasibility verification | yes | 0.990614 | near ceiling |
| `Electromagnetics/AntennaArraySynthesis` | nominal sidelobe/null suppression with sealed frequency, position, gain/phase and single-element-failure robustness | domain equations or exact combinatorial structure, constrained numerical or discrete optimization, feasibility verification | no | 0.000000 | protocol blocked |
| `ParticlePhysics/CalorimeterDesign` | development nominal multi-energy resolution-linearity-containment utility across three public cost caps, with separate held-out detector transfer and worst fabrication/calibration-shift robustness | reduced-order physical equations, constrained design optimization, sensitivity and robustness analysis | no | 0.000000 | protocol blocked |
| `Optics/DiffractionGratingDesign` | development_and_study_held_target_order_efficiency_with_polarization_angle_wavelength_and_fabrication_robustness | Fourier-modal Maxwell simulation, nonconvex photonic geometry design, polarization and fabrication robustness | yes | 0.032584 | difficult |
| `QuantumControl/GateSynthesis` | nominal_process_fidelity_with_sealed_hardware_shift_and_policy_transfer | domain simulation, numerical optimization or inverse inference, held-out and robustness analysis | yes | 1.000000 | near ceiling |
| `Photonics/MultilayerThinFilm` | broadband_antireflection_quality | domain simulation, numerical optimization or inverse inference, held-out and robustness analysis | yes | 0.813796 | discriminating |
| `Physics/SpinGlassGroundState` | mean_gap_closed_to_strong_reference_energy | domain equations or exact combinatorial structure, constrained numerical or discrete optimization, feasibility verification | no | 0.195778 | protocol blocked |

## Leakage, scope and next use

All 50 prompts were reconstructed exactly. The same solver and system prompt were used throughout; every proposal saw only its public task text, baseline program, proposal slot and closed feasibility/selection metric allowlist. Discipline, certification, historical outcomes and sealed science axes were joined offline.

Recommended use: Use as a mixed calibration portfolio, not as a uniformly hard GPT-5.6 benchmark or one-number leaderboard.

Before a strong RSI claim, run preregistered matched normal versus frozen-parent controls over the 15-task pool, add provider generation control or sufficient replication, repair the 14 blocked paths, harden the 13 near-ceiling regimes, and complete independent domain and long-horizon review.

Raw census SHA-256: `f396c86d98b0bb4103c1d9cdf43faf413016a713286d567c73ec47c2e175675e`.

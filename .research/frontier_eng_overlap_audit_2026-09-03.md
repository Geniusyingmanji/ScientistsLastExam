# 与 Frontier-Eng 的任务重合核查(2026-09-03)

起因:TASKS.md 里 15 道工程优化题被归在名为 `frontier_eng` 的 analogue 下,读起来像是从 Frontier-Eng 搬来的。
本文逐题对照,给出结论并改名。

## 对照来源

- Frontier-Eng 论文(NeurIPS 2026 投稿版,本地 `1024_Frontier_Eng_Benchmarking.pdf`)附录 A 的 47 题目录,
  五类:Computing & quantum(10)、Operations research(9)、Robotics/control/energy(8)、Optics & communication(10)、
  Physical sciences & engineering design(10)。
- 仓库 `github.com/Einsia/Frontier-Engineering` 的 `TASK_DETAILS.md`(95 条,含论文之外的 Optics 16 题、
  SingleCellAnalysis、MolecularMechanics、PowerSystems 等)。

## 结论

**没有一道任务是从 Frontier-Eng 拿来的。** 15 道 `engineering_design` 题全部由本仓库在 2026-06-15 至 06-20 之间自行建成
(git 首提交作者 carpedkm),早于 `frontier_eng` 这个标签的出现(2026-09-03,PR #3 的治理提交把它作为 analogue 名引入)。
标签指的是"同一形式"(冻结模拟器下的工程设计、连续奖励、可行性约束),不是出处。

逐题对照(Frontier-Eng 侧列"无"表示两个来源都没有同题):

| 本仓库 | Frontier-Eng 同题? | 同类问题? | 说明 |
|---|---|---|---|
| HeatExchangerDesign | 无 | 无 | |
| TrussWeightMinimization | 无 | **有**:ISCSO2015(45 杆 2D 桁架)、ISCSO2023(284 杆 3D 塔) | 本题产物是跨多结构的尺寸策略,评 sealed topology transfer 与载荷/材料/制造偏移下的稳健性;FE 是单实例 FEM 减重。同类不同题 |
| MOSFETDoping | 无 | 无 | |
| DistillationColumnDesign | 无 | 无 | |
| RANSCalibration | 无 | 无 | |
| NeutronDiffusionCriticality | 无 | 无 | |
| RoomImpulseResponse | 无 | 无 | |
| InvertedPendulumSwingUp | 无 | 无(FE 有四旋翼 PIDTuning,不同系统) | |
| LowThrustTransfer | 无 | 同域不同题:MannedLunarLanding 是 CRTBP 月面着陆载荷最大化 | 本题是 MEE 多圈小推力转移策略 |
| CalorimeterDesign | 无 | 无(FE 的 ParticlePhysics 是 MuonTomography / ProtonTherapyPlanning) | |
| MultilayerThinFilm | 无 | 无 | |
| DiffractionGratingDesign | 无 | **有**:Optics/phase_dammann_uniform_orders(二元相位 Dammann 光栅,-3..+3 级均匀) | 本题是五层介质浮雕 RCWA、+1 级效率、TE/TM、密封的工艺偏移;FE 是 diffractio 标量模型的均匀级配。同类不同题 |
| SparseRecovery | 无 | 无 | |
| ElectrolyteConductivityDesign | 无 | 无(FE 的 EnergyStorage 是电池快充) | |
| AlloyHardnessOptimization | 无 | 无 | |

非工程题里另有一处同域:ForceFieldCalibration(发现类,假设判别 + 拒答)对 FE 仓库的 MolecularMechanics/torsion_profile_fitting(拟合优化),形式不同。

## 处置

1. analogue 改名 `frontier_eng` → `engineering_design`,含义不变;README 的形式树写成"与 Frontier-Eng 同形式,任务不重合"。
2. 两道同类不同题(TrussWeightMinimization、DiffractionGratingDesign)保留:它们在 7 任务冻结队列里,改题等于重测全部证据;
   区别已写在本文,后续改卡片时同步进 `novelty_risk`。是否要用别的题替换,由维护者决定。
3. 新题的建题规则进 CONTRIBUTING 检查清单:建题前对照 FE 的两份目录,同一问题类不再立题。
   本轮计划中的新题(隐藏耦合网络重建、强迫信号归因、黑盒群结构辨识)均不在 FE 目录内。

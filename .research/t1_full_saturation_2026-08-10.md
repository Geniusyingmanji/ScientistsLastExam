# T1 — 全库开环饱和扫描（52 个非隔离任务）

模型 `gpt-5.6-sol`，`selection_blind`，budget 12，seed 0，真沙箱。52/52 完成，无失败。

## 结论

| 判定 | 数量 | 占比 | 含义 |
|---|---:|---:|---|
| GOOD | 17 | 33% | 开环饱和且留有空间 —— 能测迭代改进 |
| no headroom | 25 | 48% | 开环自己就到 ≥0.95 —— 搜索器无处可赢 |
| still climbing | 3 | 6% | 开环仍在爬 —— 独立采样迟早超过任何搜索器 |
| floor | 7 | 13% | 12 次抽样后仍是 0 —— 协议或可执行性问题 |

**一半的库（25/52）没有可测空间。**

## 两个必须记录的发现

### 一、certified 核心里 6/7 没有空间

| 任务 | blind@1 | blind@12 | 判定 |
|---|---:|---:|---|
| CapSet | 0.0000 | 0.7121 | GOOD |
| MultilayerThinFilm | 0.8925 | 0.9544 | no headroom |
| MatrixMultiplicationRank | 0.7292 | 0.9792 | no headroom |
| LennardJonesCluster | 0.9936 | 0.9980 | no headroom |
| CirclePacking | 0.8485 | 0.9991 | no headroom |
| SpinGlassGroundState | 0.1958 | 1.0000 | no headroom |
| PoissonSolver2D | 1.0000 | 1.0000 | no headroom |

七个 certified 任务里只有 `CapSet` 能测迭代改进。`PoissonSolver2D` 的开环第一次抽样就是满分。`SpinGlassGroundState` 在 budget-1 普查里是 0.1958、被判 protocol blocked，但十二次独立抽样直接到 1.0000。

这与另一条独立证据一致：`CirclePacking` 上 OpenEvolve 三次 oracle 调用到 0.9906，单 incumbent 贪心到 0.999989，两个搜索器无法区分 —— 因为任务本身没有难度。

### 二、budget-1 普查系统性误判了七个任务

| 任务 | budget-1 普查 | blind@12 |
|---|---|---:|
| AntennaArraySynthesis | 0.0000 protocol blocked | 1.0000 |
| OptimalPowerFlow | 0.0000 protocol blocked | 1.0000 |
| LidDrivenCavity | 0.0000 protocol blocked | 1.0000 |
| SeismicWaveInversion | 0.0000 executable floor | 1.0000 |
| OceanCurrentInversion | 0.0000 protocol blocked | 0.9990 |
| BroadbandAbsorber | 0.0000 protocol blocked | 0.9985 |
| EnergyBalanceModel | 0.0000 executable floor | 0.9776 |

这七个任务在单次提案下得 0，看起来是"最难的一档"；给十二次独立抽样，开环对照全部解到 0.98 以上。**它们不是难，是需要多试几次。**

单次抽样的普查无法区分「难」与「一次不够」。这条直接影响此前所有基于 budget-1 波段的判断 —— 包括"14 个 protocol blocked"这个数字：其中至少 5 个只是第一次没交对，多抽几次就通了。

## GOOD 名单（17 个）

`CapSet`、`MOSFETDoping`、`TrussWeightMinimization`、`ActiveLawDiscovery`、
`CatalystDeactivationLab`、`DiffractionGratingDesign`、`ElectrolyteConductivityDesign`、
`HeatExchangerDesign`、`InvertedPendulumSwingUp`、`LowThrustTransfer`、
`MolecularLeadOptimization`、`NMRSpectrumFitting`、`ProteinStabilityDesign`、
`QuantumErrorDecoder`、`RANSCalibration`、`ReactionMechanismFitting`、`RoomImpulseResponse`

两个按新规则新建的任务（`MolecularLeadOptimization` 0.3629→0.6362、`QuantumErrorDecoder` 0.7392→0.7906）都在名单内，这是对其设计的一次独立验证 —— 它们的 Δ 也确实在配对实验里为正。

`RANSCalibration` 与 `ReactionMechanismFitting` 的 blind@12 完全等于 blind@1：十二次独立抽样没有一次超过第一次，是最强形式的饱和。

## 对后续项的输入

- **T6 重锚**：名单不是原先的 13 个 near-ceiling，而是 **25 个 no headroom**。其中 6 个是 certified，必须优先处理，否则默认基准测不出任何东西。
- **T5 契约 linter**：仍然需要，但收益要下调 —— 7 个 floor 任务是真的卡住，而原先归为 blocked 的另外 5 个只是首次提交失败。
- **T7 逆问题改判**：与本结果交叉后，`GravityInversion`、`OceanCurrentInversion`、`SeismicWaveInversion`、`EnergyBalanceModel` 等发现形式任务同时也是 no headroom —— 改指标之前得先让它们有空间。
- **优先做 Δ 的对象**：GOOD 里跨度最大的是 `DiffractionGratingDesign`（0.0126→0.8059）、`HeatExchangerDesign`（0.0000→0.9369）、`RoomImpulseResponse`（0.0000→0.8545）。

## 边界

单 seed、单预算（12）。`tail_share` 在总增益接近 0 时分母很小，所以零增益任务的 0.00 应读作"开环完全没动"而非精确测量。阈值（tail ≤ 0.10 判饱和、best@12 ≥ 0.95 判无空间）为本轮设定，未做敏感性分析。9 个 quarantined 任务未扫描。

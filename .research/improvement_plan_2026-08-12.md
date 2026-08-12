# 改进计划

依据是两份可复现的审计:`scripts/audit_benchmark_standards.py`(科学根基,九项)与
`scripts/report_admission_criterion.py`(能否测量迭代改进)。两条轴正交,任务可以只占一头。

先纠正一个我自己先前的说法。我曾把 25 个 `exhausted_unpaired` 任务称作"唯一能新增合格任务的池子"。
按对照终值拆开看,其中 **15 个是 clipped 计分且对照已达 0.958–1.000** —— 对照本身已经打满,
配对臂无论如何都测不出东西。真正的配对队列是 10 个,不是 25 个。

## 分组与现状

| 组 | 数量 | 判据含义 |
|---|---:|---|
| A 已合格 | 5 | 对照已耗尽且反馈持续拉开差距 |
| B 已打满(clipped,对照 ≥0.958) | 15 | 任务被 best-of-N 解掉,配对无意义 |
| C 待配对(尚有空间) | 10 | 对照已耗尽但留有余量,配对能出结论 |
| D 对照仍在爬 | 7 | best-of-N 未耗尽,不满足必要条件 |
| E 反馈有害 | 6 | 其中 3 个仅单 seed 支撑 |
| F 地板 | 6 | 对照始终为零,两条都测不了 |
| G 两臂无差异 | 1 | RNAEnsembleDesign |

---

## P0 — B 组的 15 个:重新定锚,不是配对

这是最大的一块,也是最被误判的一块。`RankineCycleOpt`、`PoissonSolver2D`、`LyapunovControl`、
`AntennaArraySynthesis`、`OptimalPowerFlow`、`HartreeFockSCF`、`GateSynthesis`、
`SpinGlassGroundState`、`LidDrivenCavity`、`PhotovoltaicTandemDesign` 对照终值恰好 1.000;
`SeismicInversion` 0.998、`OptimalExperimentDesign` 0.991、`GravityInversion` 0.990、
`InterventionalSCM` 0.986、`SparseRecovery` 0.958。

clipped 计分下 1.000 就是上限,所以这些任务当前的锚点已经不是"参考水平"而是"天花板"。
三条出路,成本递增:

1. **改 uncapped 并换成社区参考值。** 前提是该领域存在公认的参考实现或记录值。
   `HartreeFockSCF` → PySCF、`SpinGlassGroundState` → 已知实例集、`LennardJonesCluster` →
   Cambridge Cluster Database。这是最彻底的做法,也是 P1 的一部分。
2. **加难度旋钮把实例做难。** QuantumErrorDecoder 与 MolecularLeadOptimization 已验证做法。
   适用于实例可程序化生成的任务(`PoissonSolver2D`、`LidDrivenCavity`、`AntennaArraySynthesis`)。
3. **退役。** 一个 clipped 且被打满、又拿不到外部记录值的任务,继续留在题库里只会稀释结论。

**阻塞项**:路线 1 的一部分需要外部记录值(Packomania、Cambridge Cluster Database),
我不从记忆里写这类数字。要么提供表格、要么开放网络访问,要么接受路线 2/3。

---

## P1 — 科学根基:社区 oracle 只有 3/62

这是九项标准里最根本的缺口,也是决定"分数衡量的是科学还是作者代码"的那一项。

已完成三个:QuantumErrorDecoder(Stim + PyMatching)、MolecularLeadOptimization(RDKit)、
RNAEnsembleDesign(ViennaRNA)。

**优先改造已通过准入、但根基薄的四个** —— 它们的 RSI 适配已验证,补上根基即可进第一梯队,
比从零建新任务便宜得多:

| 任务 | 当前 | 建议 oracle |
|---|---|---|
| `ProteinStabilityDesign` | 作者 NumPy 重实现,标准 4/10 | FoldX / Rosetta ddG,或 ESM 类稳定性预测器 |
| `NMRSpectrumFitting` | 同上 | nmrglue + 公开谱库 |
| `LowThrustTransfer` | 同上 | poliastro / GMAT 轨道传播 |
| `AlloyHardnessOptimization` | 同上 | pymatgen + Materials Project 记录值 |

**次优先**:`RNAInverseDesign` → ViennaRNA(它的认证条目本来就写着"待完整 ViennaRNA 或 NUPACK 复现",
而新建的 RNAEnsembleDesign 已经把这条路走通,可直接迁移)。

**成本**:每个约等于一次 RNAEnsembleDesign 的工作量。那次的实际教训是,难点不在接工具包,
而在**选对锚点例程** —— 我第一版用 `inverse_fold`,它优化的目标和计分不是一回事,差 75 倍。
每个改造都要先确认"这个社区例程优化的是不是我要计分的量"。

---

## P2 — C 组的 10 个:补配对,能出结论

真正值得跑的队列,按剩余空间排序:

| 任务 | 对照终值 | 角色 |
|---|---:|---|
| `RoomImpulseResponse` | 0.585 | optimization |
| `DiffractionGratingDesign` | 0.697 | optimization |
| `MOSFETDoping` | 0.756 | optimization |
| `EnergyBalanceModel` | 0.768 | discovery |
| `ActiveLawDiscovery` | 0.862 | discovery |
| `InvertedPendulumSwingUp` | 0.873 | optimization |
| `RNAInverseDesign` | 0.930 | optimization |
| `CirclePacking` | 1.061 | uncapped,1.0 之上仍有空间 |
| `LennardJonesCluster` | 0.998 | uncapped,同上 |
| `MatrixMultiplicationRank` | 0.979 | uncapped,同上 |

**协议**:每个 4 对 seed、budget 12、`greedy_rewrite`。以本轮经验,4 对 seed 只够出临时判定 ——
`ReactionMechanismFitting` 在 2 对 seed 时是全库最大 Δ(+0.4231),4 对就变号。要下定论需要 8 对。

**成本**:10 个任务 × 8 运行 = 80 次运行,按本轮观测每次 20–60 分钟、5 路并发,约 8–16 小时机时。

---

## P3 — 地板与有害:先分清病因

**F 组 6 个地板任务**。T5 的分离报告已经指出关键区别:被拒提案里"从未执行"(162)与
"执行了但不可行"(101)是两回事。地板任务要先跑这个分离,再决定:

- 执行率低 → 契约障碍。`contract_lint.py` 已经写好但**没有任何 Task.md 提到它**,候选不知道它存在。
  最低成本的一步:在这 6 个任务的 Task.md 里写明可用。
- 执行率高但全不可行 → 科学难度或计分错误。`RadiativeTransferFit` 属此类(通过率 1.00、条件科学分 0.0000)。

**E 组 6 个反馈有害任务**。其中 3 个(`CatalystDeactivationLab`、`ReactionMechanismFitting`、
`DemographicSFS`)仅单 seed 支撑,先补到 8 对 seed 再谈。剩下 3 个
(`TrussWeightMinimization` −0.37、`RANSCalibration`、`HeatExchangerDesign`)方向明确,
值得单独做机制调查:Truss 上已经看到开环靠独立抽样撞到 0.9979 而反馈臂锚在 incumbent 上最好 0.4143。
**这不是缺陷而是发现** —— 题库应当能报告"迭代有时是负收益",但需要写成一份独立结论而不是散落在判定表里。

---

## P4 — 发现侧需要另一套判据

17 个 discovery 任务里只有 `NMRSpectrumFitting` 一个通过,且是 4 对 seed 的临时判定;
5 个是地板、5 个待配对、3 个疑似有害。

根本问题是**现在这套准入判据是为优化设计的**:它比较单一标量的 Δ。发现任务的正确判据是
机制恢复 / 误发现率 / 校准拒绝三元组,而三者不能合并成一个数(T7 已经证明合并会精确地藏起
要紧的失败:`SeismicWaveInversion` combined 1.0000 而机制恢复 0.6667)。

需要做的:

1. 为发现任务定义"迭代改进"的含义 —— 大概是三元组各自的轨迹,而非单一 Δ。
2. 补齐四个任务的 FDR 分母(`ActiveLawDiscovery`、`SeismicInversion`、`InterventionalSCM`、
   `ProspectiveMetaAnalysis` 只发计数不发分母,算不出率)。
   **阻塞项**:改 evaluator 会改任务包哈希,解绑 Track F 那个负结果的分析产物,属治理决策。
3. 之后才谈发现侧的准入。

---

## P5 — 剩余标准缺口

- **难度旋钮 3/62**。当前 50+ 个任务饱和后只能整体报废。做法已在两个任务上验证(实测表而非公式:
  QEC 上"拧码距"会让锚点失败次数塌到个位数;分子任务上两个旋钮通过参考面板耦合)。
- **可运行参考实现 6/62**。另有 6 个只在卡片文案里声称重算。成本低于换 oracle,应先做。
- **外部领域评审 0/62**。这条不是代码能解决的,发布前应明确标注未完成而非留白。

---

## 建议的执行顺序

1. **P2 的前 4 个**(RoomImpulseResponse、DiffractionGratingDesign、MOSFETDoping、
   InvertedPendulumSwingUp)—— 纯机时,不需要决策,能立刻把"有配对证据"从 15/53 推上去。
2. **P1 的 ProteinStabilityDesign 与 NMRSpectrumFitting** —— 已过准入,补根基性价比最高。
3. **P3 的最低成本一步** —— 在 6 个地板任务的 Task.md 里写明 `contract_lint` 可用,然后重测。
4. **P0 需要你的决策**:B 组 15 个任务是走"换 uncapped 社区锚点""加难度旋钮"还是"退役"。
   这决定题库最终规模,不该由我单方面定。
5. **P4 的第 2 步需要治理决策**:是否接受解绑 Track F 的分析产物来换取发现任务可报 FDR。

## 边界

所有 Δ 均由 `greedy_rewrite` + gpt-5.5(reasoning_effort low)测得。交叉点已被证明是任务×搜索器的
性质,换搜索器需重测。对照终值来自 3 个合并 seed 的中位数,足以区分"打满"与"留有空间",
不足以支撑单个任务的精确排序。

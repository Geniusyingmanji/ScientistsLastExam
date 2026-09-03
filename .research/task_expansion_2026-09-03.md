# 2026-09-03 任务扩展记录(从 README 移出)

三个外部 PR(#2 测试可移植性、#3 runtime 与证据绑定加固、#4 十二个候选任务)于 2026-09-03 合并,
库存 46 → 58。以下是 #4 的逐题说明,原写在 README,按"README 只写背景 / 形式 / 评测 / 贡献"的口径移到这里。

- `Spectroscopy/CrowdedSpectrumAssignment`(substance:拥挤光谱指认)
- 五道无上限组合构造:`Mathematics/RamseyLowerBound`、`Mathematics/KissingNumber`、`Algorithm/TensorRank555`、
  `Mathematics/Superpermutation`、`Mathematics/CapSetFrontier`。`CapSetFrontier` / `TensorRank555` 的实例集
  与已认证的 CapSet / MatrixMultiplicationRank 不相交。
- `ParticlePhysics/LookElsewhereAnomaly`(evidence:trials factor)
- `CausalDiscovery/SurvivorshipConfoundedDesign`(structure:survivor collider,不是 InterventionalSCM 的克隆)
- `Oceanography/AMOCTippingRefusal`(formula:fold vs red-noise / ice-restore,不是 EBM 参数反演)
- `Gravitation/PTAHellingsDowns`(evidence:HD quadrupole vs clock monopole,不是 LookElsewhere bump hunt)
- `Physics/ComplexBoseLaw`(formula:NewtonBench 风格的复 Bose 反事实,拒 Fermi)
- `MaterialsScience/QuinaryConvexHull`(substance:五元解析 hull,不是二元 XRD)

十二题均为 `candidate`。metadata 里的 hard / flagship 是目标评审层级,不是测得的难度;
没有前沿模型标定、外部领域验证或长程证据。

合并后的复核结论(详见提交 66707e9):Superpermutation n=8 锚点 46204 经 OEIS A180632 与 Egan 页面核对为 46205,
已修;其余四道构造任务的锚点全部溯源无误;`sota_ref` 类字面锚点此前绕过守卫,守卫已扩展并声明 8 个任务;
`run_cohort.sh` 的完成性检查用裸 `python`,在基准主机上不存在,已改 `python3`;
十二题在 g450 沙箱基线 58/58 通过。准入门在重出 v69/v52/v10 后为 58/58。

## 2026-09-03 下午:三道面向前沿天花板的发现题,以及两次准入失败

按「学科 × 形式」矩阵的空位建了三题,全部 candidate,均不与 Frontier-Eng 的 47/95 题目录重合
(逐题核查见 `frontier_eng_overlap_audit_2026-09-03.md`)。

| 任务 | 格点 | 参考解 dev/heldout | 基线 | 首轮 Opus 5 首提案 | 判定 |
|---|---|---|---|---|---|
| ClimateScience/ForcedSignalAttribution | 证据 | 0.722 / 0.632 | 0.025 | 0.619 / 0.465 / 0.286 | 准入通过 |
| Physics/HiddenCouplingNetwork | 结构 | 0.631 / 0.589 | 0.000 | **0.665** / 0.571 / 0.528 | 一个种子越线,加固 |
| Mathematics/BlackBoxGroupIdentification | 结构 | 0.857 / 1.000 | 0.000 | **1.000** | 严重饱和,加固 |

### 两次加固都改世界,不改参考解

- **群辨识**:根因是查询预算 6×阶数足以重建整张 Cayley 表,有表就能做真同构判定。预算改 2.5×阶数 ——
  卡在「两生成元闭包 = 2×阶数」与「三生成元 = 3×阶数」之间,于是「要不要赌重建」成了每个世界的决策。
  另外核查了目录的可分性:秩 + 阶数分布**分不开** C8xC2/M16(order 16)与 C16xC2/M32(order 32),
  目录外的 C4:C4、Pauli、C8:C4、C2xM16、C3xC4:C4 也各与一个目录项同型,唯一能分开的是中心,
  而中心只能靠每次两查询的交换性抽样估计。新参考解 0.286 / 0.400。
- **网络重建**:12 单元预算 14 → 8,入度 3 → 4,隐藏单元 2 → 1 个弱耦合。参考解 0.445 / 0.358,
  覆盖率 0.57(5 个可解网络拒掉 3 个),头顶空间落在边恢复轴。

### 这轮的方法论结论

参考解偏弱会让准入线形同虚设:网络重建题的参考解本来就误拒两个世界,模型只要拒答策略稍好就能越线。
所以准入线要看两件事 —— 参考解本身是不是能力完整(方法对、只是分配次优),以及首提案有没有够到它。
两条新测试把这次的教训固化:预算倍数必须落在 2 与 3 之间(否则重建又变可行),
目录不能被「秩 + 阶数分布」分开(否则中心成了可选项)。

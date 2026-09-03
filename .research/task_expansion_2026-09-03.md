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

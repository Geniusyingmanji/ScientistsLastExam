# T7 — 发现任务的三元组分报

`scripts/report_discovery_triple.py`，对 17 个 `scientific_role: discovery` 任务，取各自最优有效提案的完整 metrics。

## 前提：轴一直都在

调查发现这些 oracle **早已计算**发现三元组所需的轴，只是被折叠进了单一的 `combined_score`：

| 轴 | 跨任务出现次数 |
|---|---:|
| `development_false_discovery_rate` / `heldout_false_discovery_rate` | 14 / 14 |
| `heldout_mechanism_score` / `mechanism_score` | 11 / 10 |
| `development_supported_claim_coverage` | 9 |
| `development_correct_refusal_rate` / `development_unsupported_refusal_rate` | 7 / 7 |

所以 T7 的工作量在报告层，不在 evaluator 数学层。命名存在多套约定，取值按"从严到宽"排序（held-out 优先于 development）。

## 结果

| 任务 | combined | 机制恢复 | FDR | 拒绝 |
|---|---:|---:|---:|---:|
| ActiveLawDiscovery | 0.7980 | 0.8557 | — | — |
| CatalystDeactivationLab | 0.1722 | 0.0000 | 0.0000 | 0.0000 |
| ConvectionDiffusionOpt | 0.0000 | 0.0000 | 0.0000 | 1.0000 |
| DemographicSFS | 0.6769 | 0.3553 | 0.2000 | 0.0000 |
| EnergyBalanceModel | 0.9776 | 0.9776 | 0.2500 | 0.5000 |
| ForceFieldCalibration | — | 无有效提案 | | |
| GeneNetworkIntervention | 0.0000 | 0.0000 | 0.0000 | 1.0000 |
| GravityInversion | 0.9920 | 0.8662 | 0.0000 | 1.0000 |
| InterventionalSCM | 0.9894 | 0.9912 | — | 1.0000 |
| NMRSpectrumFitting | 0.6759 | 0.5908 | 0.5000 | 1.0000 |
| OceanCurrentInversion | 0.9990 | 0.8982 | 0.0000 | 1.0000 |
| ProspectiveMetaAnalysis | 0.0000 | — | 0.0000 | 1.0000 |
| QuartzCrystalMicrobalanceLab | 0.0000 | 0.0000 | 0.0000 | 1.0000 |
| RadiativeTransferFit | 0.0000 | 0.4000 | 0.0000 | 1.0000 |
| ReactionMechanismFitting | 0.5245 | 0.6829 | 0.5000 | 0.5000 |
| SeismicInversion | 0.9981 | 0.9988 | — | — |
| SeismicWaveInversion | 1.0000 | 0.6667 | 0.0000 | 1.0000 |

## 单一标量在哪里误导

**`SeismicWaveInversion`：combined 1.0000，机制恢复 0.6667。** 头条分是满分，而隐藏机制只恢复了三分之二。任何只看 `combined_score` 的排行榜都会把它当作已解决。

**`EnergyBalanceModel`：combined 0.9776，FDR 0.2500。** 近乎满分的同时，在四分之一的误设世界上仍然提交了"发现"。

**`NMRSpectrumFitting` 与 `ReactionMechanismFitting`：FDR 均为 0.5000。** 一半的误设世界得到了错误断言，而 combined 分别是 0.6759 和 0.5245 —— 看起来是"中等表现"，实际是"一半时候在编"。

**`RadiativeTransferFit`：combined 0.0000，机制恢复 0.4000。** 反方向的误导 —— 头条分说完全失败，机制轴说部分恢复。

这正是 CausaLab 记录的模式（同一设定下任务准确率 92%、全边 F1 仅 0.471）在本仓库的复现：**目标分与机制恢复是两个量，合并会精确地藏起真正要紧的那个失败**。

## 反作弊规则是生效的

`ConvectionDiffusionOpt`、`GeneNetworkIntervention`、`QuartzCrystalMicrobalanceLab`、`ProspectiveMetaAnalysis` 四个任务出现 拒绝 = 1.0000 而 combined = 0.0000。这是"全弃权策略强制得 0"在起作用 —— 全部拒绝可以拿满拒绝率，但拿不到分。若无此规则，拒绝会成为最优刷分策略。

## 缺轴的四个任务

| 任务 | 缺 |
|---|---|
| ActiveLawDiscovery | fdr、refusal |
| SeismicInversion | fdr、refusal |
| InterventionalSCM | fdr |
| ProspectiveMetaAnalysis | mechanism |

这四个的 evaluator 需要补齐相应轴，否则它们的发现形式判定名不副实。`ActiveLawDiscovery` 尤其值得注意 —— 它是 Track F 那个负结果所用的任务，而它连 FDR 轴都没有暴露。

## 边界

单 seed、budget 12、开环条件下各任务的最优有效提案。三元组取自轨迹中记录的 metrics，不同任务的命名约定不同，取值优先级为 held-out 优先。缺轴按缺失报告，不做插补。本报告刻意不产出任何合并数字。

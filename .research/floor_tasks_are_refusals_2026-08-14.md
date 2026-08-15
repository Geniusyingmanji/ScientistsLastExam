# 地板任务不是难,是拒答

六个任务在每个模型上都是 0 分。把它们当作"太难、需要重新标定"处理是错的 ——
逐条查完之后,零分的成因有两种,而且要求相反的处置。

## 两种零分

先看有效性,而不是分数:

| 任务 | 提案 | 有效 | 无效 | 有效且得分 >0 |
|---|---:|---:|---:|---:|
| CalorimeterDesign | 36 | **0** | 36 | 0 |
| GeneNetworkIntervention | 36 | 8 | 28 | 0 |
| ConvectionDiffusionOpt | 36 | 16 | 20 | 0 |
| QuartzCrystalMicrobalanceLab | 36 | 21 | 15 | 0 |
| ProspectiveMetaAnalysis | 36 | 23 | 13 | 0 |
| RadiativeTransferFit | 36 | **36** | 0 | 0 |

两端是完全不同的病:

- **CalorimeterDesign 零有效提案。** 没有人交得出一份合法提交。这是契约猜不中,
  和科学难度无关,零分里不含任何科学信息。
- **RadiativeTransferFit 全部 36 个提案都有效、都跑通、都得 0。** 契约没问题。

## 全零不是难度的形状

关键线索:所有有效提案的分数**恰好都是 0.0**,不是一堆分散的小正值。
科学难会给出梯度,恰好全零是闸门的特征。

但读进 evaluator 的分项指标之后,闸门这个猜测也被推翻了。RadiativeTransferFit 的一次典型提案:

```
combined_score                       0.0
development_correct_refusal_rate     1.0     ← 全对
development_confidence_calibration   1.0     ← 全对
development_false_discovery_rate     0.0     ← 完美
development_discovery_coverage       0.0     ← 什么都没提交
development_radiance_prediction      0.0139
```

归一化是

```
normalized = clip((raw − 全弃权基线) / (1 − 全弃权基线), 0, 1)
```

`全弃权基线 = 不支持世界数 / 总世界数`,也就是**对每个世界都拒答**所能拿到的分。
候选的 coverage 是 0、correct_refusal 是 1 —— 它就是在全面弃权,拿到的正好是基线,
归一化后是 0。

**判据在正确工作。**§7.2 要求"全弃权策略强制得 0",否则拒答会变成刷分策略。
这个零分是它该给的。

## 全库测量

把所有发现类任务按"最好的有效提案是否尝试过"排开,关系是单调的:

| 任务 | 全弃权提案占比 | 平均覆盖率 | 开环最好分 |
|---|---:|---:|---:|
| RadiativeTransferFit | 100% | 0.000 | 0.000 |
| ProspectiveMetaAnalysis | 100% | 0.000 | 0.000 |
| GeneNetworkIntervention | 100% | 0.000 | 0.000 |
| ConvectionDiffusionOpt | 100% | 0.000 | 0.000 |
| QuartzCrystalMicrobalanceLab | 86% | 0.127 | 0.000 |
| ForceFieldCalibration | 60% | 0.400 | 0.060 |
| CatalystDeactivationLab | 28% | 0.725 | 0.098 |
| DemographicSFS | 23% | 0.766 | 0.702 |
| EnergyBalanceModel | 10% | 0.898 | 0.664 |

**地板任务恰好就是模型全面弃权的任务。** 不是难度排序,是拒答率排序。

## 这算不算模型的失败

算。这些任务的卡片明确声明参考策略是"在支持的世界上给出精确参数,**只在 null 或
误设世界上弃权**"。也就是说支持世界上尝试才是正确行为,全弃权是把一条正确的谨慎规则
用到了不该用的地方。

**这一条现在被验证了。** RadiativeTransferFit 补上了可运行的 truth-blind 参考解
(`verification/reference_retrieval.py`,只用公开正演模型与观测回调,从不读隐藏世界):

| | 每一个模型提案 | 参考解 |
|---|---:|---:|
| combined_score | 0.0000 | **0.7910** |
| discovery_coverage | 0.0 | 1.0 |
| 误发现率(development) | 0.0 | **0.0** |
| 正确拒答率(development) | 1.0 | **1.0** |
| 机制恢复 | 0.0 | **0.8606** |

注意模型的误发现率和拒答率也是"完美"的 —— 因为它什么都不提,不可能误报。
参考解在**同样完美**的这两轴上,额外拿到了 0.86 的机制恢复。

**所以全面弃权是模型的失败,不是任务缺陷。** 这句话此前只是卡片里的散文。

参考解的实现过程本身也说明了这个任务在测什么。三版:

| | 判据 | combined | 误发现(dev) | 拒答(dev) |
|---|---|---:|---:|---:|
| 一 | 卡方阈值 4.0 | 0.0000 | 1.0 | 0.0 |
| 二 | 阈值 2.0 + null 弃权 | 0.1615 | 0.5 | 0.5 |
| 三 | **BIC 子集选择** | **0.7910** | **0.0** | **1.0** |

第一版**全部认领**,拿 0 分 —— 与模型的全部弃权正好镜像,两个极端都得零,
这说明归一化在正确地要求**区分能力**。第二版的关键是发现 null 世界拟合得很好
(chi²/dof 0.66),它本就在族内、只是参数全零,正确答案是"没有可报的机制"即弃权。
第三版的关键是:阈值化会把噪声也判成活跃项(5 个里判 4–5 个,而真值只有 2–4 个),
support 是个**模型选择问题**,枚举 32 种组合按 BIC 选才对。

held-out 上参考解只有 0.475(误发现 0.5、拒答 0.5),留有头部空间 ——
一个拿满分的参考解会让任务失去可测量的余地。

## 三个被排除的解释

既然拒答是真实行为,下一个问题是它从哪来。三个最便宜的假设都测了,都不成立。

**不是提示词在诱导。** 统计 Task.md 里 abstain/refuse/decline 一类词的出现密度,
与弃权率的秩相关是 **−0.267**,而且符号是反的:密度最高的 EnergyBalanceModel
(11.9 次/千词)弃权率最低(0.10);密度中等的 ConvectionDiffusionOpt(7.5)是 100%。
Task.md 长度更无关(ρ = −0.017)。

**不是提交字段没写。** RadiativeTransferFit 与 GeneNetworkIntervention 的提交字段
(`support`、`confidence`、`abstain` 及各自的数组)在 Task.md 或 constraints 里**全部有文档**。
这一点和输入键的情况不同 —— 那边是名字压根没写,这边写了。

**剩下的是一个结构性不对称,而且它是被写明的:**

| 动作 | 需要填的字段 |
|---|---|
| 弃权 | `abstain=True`(1 个) |
| 提出主张 | `support`、`confidence` + 任务特有的带形状数组(5–7 个) |

弃权是契约成本最低的合法动作。这不构成"任务设计错了"的结论 ——
在支持世界上尝试仍然是参考策略的做法 —— 但它说明:**在一个允许拒答的发现任务里,
提交结构的复杂度本身会偏置模型的行为**,而这一层此前没有被当作设计变量看待。

**这条假设也被证否了,而且不需要跑那个实验。** 如果提交结构的复杂度在偏置行为,
那么主张字段越多的任务弃权率应该越高。逐任务数了一遍(含嵌套契约常量):

| 任务 | 弃权率 | 主张字段数 |
|---|---:|---:|
| ProspectiveMetaAnalysis | 1.00 | 17 |
| GeneNetworkIntervention | 1.00 | 6 |
| RadiativeTransferFit | 1.00 | 4 |
| ConvectionDiffusionOpt | 1.00 | 4 |
| QuartzCrystalMicrobalanceLab | 0.86 | 13 |
| ForceFieldCalibration | 0.60 | 11 |
| CatalystDeactivationLab | 0.28 | 17 |
| DemographicSFS | 0.23 | 2 |
| EnergyBalanceModel | 0.10 | 2 |

Spearman = **+0.133**(n=9),等于没有关系。

比相关系数更有说服力的是这一对:**ProspectiveMetaAnalysis 17 个字段、100% 弃权;
CatalystDeactivationLab 同样 17 个字段、28% 弃权。** 契约规模相同,行为相反。
两端也对不上:字段最少的两个任务(各 2 个)弃权率是 0.23 和 0.10,
而字段数中等的四个任务全是 100%。

一个测量上的诚实交代:第一版抽取器漏了嵌套契约(ProspectiveMetaAnalysis 的提交是
`confirmation_commit → preconfirmation`,被数成 0 个字段),给出 ρ = −0.183。
补上嵌套后符号翻成 +0.133。两版结论相同 —— 没有关系 —— 但只有后一版站得住。

## 处置

**不要重新标定锚点。** 锚点没问题;把 0 分调高只会让全弃权开始得分,
那恰好是判据存在的理由。

已做的:`scripts/report_discovery_triple.py` 增加 coverage 一列(**不是第四条轴** ——
三元组说发现得多好,coverage 说有没有去发现),并单独列出"最好的有效提案什么都没尝试"的任务。
在此之前,难到做不出和根本没去做,在报告里都显示为同一个 `0.0000`。

同一次修复里还改掉了这个报告的三个静默少报:它只扫单层 cohort 目录、
只取匹配到的**第一个**目录、并且按目录名前缀认任务。结果是它对全部 19 个发现任务
报"no valid proposal",而树里有几百次运行。现在按 manifest 跨 cohort 找,取全局最好的有效提案。

还剩两件:

1. **6 个发现任务的 evaluator 不发布 coverage** —— ActiveLawDiscovery、GravityInversion、
   InterventionalSCM、NMRSpectrumFitting、ReactionMechanismFitting、SpinSystemInference。
   在这些任务上"有没有尝试"根本无法从运行记录里读出来。
2. ~~CalorimeterDesign 的契约要单独修~~ **已修并验证**。它的公开 `problem` 有 27 个键而
   Task.md 只写了 15 个;补齐后同模型同预算重跑,有效率 0% → 82%,最好分 0.0000 → 1.0000。
   它从来不是"地板任务需要重新标定",是没告诉它输入叫什么。详见
   [contract_burden_2026-08-14.md](contract_burden_2026-08-14.md)。

## 一个差点犯的错

第一版的"未尝试"判定把 coverage 缺失当成 coverage=0,于是 `GravityInversion`
(合并分 0.9941、机制分 0.8593)被列为"什么都没尝试"。缺失不等于零 ——
这个仓库已经在别处踩过同一类错(未记录模型被当成第三个模型、空返回被当成无效提交)。
现在缺指标的任务单独一栏,说的是"这件事在它上面没被测量",不是"它拒答了"。


## 排除之后剩下什么

三条便宜的解释都死了:提示词措辞(ρ = −0.267,符号还是反的)、提交字段没文档(全都有文档)、
提交结构不对称(ρ = +0.133,且有同规模反向的一对)。

同时,五个 truth-blind 参考解证明**这些任务是做得出来的**:0.9088 / 0.8330 / 0.7910 /
0.7636 / 0.3926,三条发现轴全部完美。所以不是任务不可解。

**剩下的解释就是模型本身。** 在一个允许拒答的困难推断任务上,这些模型选择拒答而不是尝试,
而拒答在计分上被正确地判为零。这不是任务设计的缺陷,是被测对象的一个行为特征 ——
也正是一个发现类基准应该能测出来的东西。

要把这条再推进一步,需要的不是更多任务侧的假设,而是模型侧的对照:同一个任务上
改变"允许拒答"这一条本身(比如强制作答),看分数是升是降。那个实验测的是模型,不是任务。

# Discovery 评测:能不能被绕过,和能不能分出高下

这是两个独立的问题。一道题可以完全防住廉价策略,同时对任何有能力的候选给出同一个分数;
也可以区分度很好,却被一句"什么都别说"或"什么都说"拿走大半分。

现在的 discovery 契约分别报告机制恢复、错误发现和校准拒答且从不平均,这是对的,但它不回答
其中任何一个。`shortcut_probe` 回答第一个问题的一部分——**作者想得到的**那些候选;四十六道
discovery 题里有三道声明了探针。

`scripts/audit_discovery_discrimination.py` 机械地问这两个问题。

## 方法

四个不懂科学的策略,跑每道题**自己的**参考程序和**自己的**封存 oracle:

| 策略 | 做什么 | 问什么 |
|---|---|---|
| `reference` | 参考程序原样 | 对照 |
| `abstain_all` | 参考解的答案,每个 `abstain` 标志强制为真 | 沉默值多少分 |
| `claim_all` | 同上,强制为假 | 喧哗值多少分 |
| `constant_answer` | 第一个世界的答案,原样重放到每个世界 | 世界之间是否真的不同 |

四个策略提交的都是**参考解自己形状的合法答案**,只动一个标志,所以高分不可能用"畸形候选被
宽容地计分"解释。四十六个 discovery evaluator 全部校验一个 `abstain` 布尔值,这是后两个策略
能写一次而不是写四十六次的原因。

一个 0 分有三种完全不同的成因,报告分开记:`scored`(oracle 接受了提交并给了这个数,只有这些
行说明了防守如何)、`rejected`(翻转后的提交被判无效——是题在拒绝给这个策略打分,不是策略
得分低)、`not_applicable`(探针没找到可翻的标志;有些 oracle 会把由此产生的候选错误吸收成
无效世界,于是跑出一个干净的 0.0,读起来和"防住了"一模一样)。

参考解取卡片 `shortcut_probe.reference` 指名的那个:三个包在真正的见证旁边放了叫 `reference_*`
的消融版,按名字挑会拿消融版去和它自己的退化策略比。这三道题的卡片都写了期望分,本次实测与
声明逐位一致——CacheReplacementPolicyID `0.777778`、SparseVectorAudit `0.819398`、
TransitTimingAttribution `0.594835`。这是整套测量唯一的外部校验点。

## 测到了什么

四十六道 discovery 题,本机测到三十二道:九道以模拟真值锚定、不带参考程序,无从对照;另外五道
缺 oracle 依赖(networkx、astropy、sympy、qutip、nmrsim)。计时类失败都用更长的时钟重跑过,
没有剩下因超时而未测的题。

### 1. 世界是真的不同,沉默也不是免费的

`constant_answer` 在被计分的二十七道题上**全部**是 0.000。把第一个世界的答案重放到所有世界,
一分不得——世界之间的差异是实的,这一层没有可乘之机。

`abstain_all` 被计分的二十八道里有二十七道是 0,唯一的例外是 ProspectiveMetaAnalysis 的 46%。
这是设计使然而非侥幸:多数题的 baseline 本身就写着"一次便宜实验之后在每个世界上拒答",于是
刻度的零点已经把"全部拒答"吸收掉了。

### 2. 校准的代价只被收了一次,而且收的是沉默那一侧

`claim_all` 是唯一有牙的策略。被计分的二十五道题里,十二道给了它非零分,其中八道达到参考解的
一半或以上(QuinaryConvexHull 恰好是 0.500 / 1.000):

| 相对参考解 | 任务 |
|---|---|
| 91.6% | EvidenceSynthesis/ProspectiveMetaAnalysis |
| 72.6% | Geophysics/UPbConcordiaInference |
| 65.9% | StructuralEngineering/ModalDamageAttribution |
| 60.9% | MaterialsScience/PhaseDiagramDiscovery |
| 60.4% | ParticlePhysics/DiscrepantMeasurements |
| 60.2% | Spectroscopy/CrowdedSpectrumAssignment |
| 59.7% | Microbiology/MetagenomeCompositionAssignment |
| 50.0% | MaterialsScience/QuinaryConvexHull |
| 49.5% | SystemsBiology/EnzymeKineticsLaw |

也就是说:**一个照着参考解采集证据、然后在每个世界上都下断言(包括那些根本无法下断言的
世界)的候选,通常还能留住参考解一半的分,最高一例留住 92%。** 刻度的零点定价了沉默,没有
任何东西定价喧哗。

这不只是标量分的问题。在 ComplexBoseLaw 上,拒答率和覆盖率对这个决定的响应完全正确
(`correct_refusal_rate` 1.0 → 0.0,`discovery_coverage` 0.0 → 1.0),而 `false_discovery_rate`
对一个在每个世界上都下断言的候选**仍然是 0.0**:它的错误发现测试只抓"把非 Bose 世界说成
Bose"这一种错,而翻转标志提交的是参考解原本正确的族标签。结论比"这条轴坏了"要窄,但仍然重要
——**过度声明只被收费一次(通过拒答轴),而 false-discovery 这个数不能单独读作"该候选没有做
无支撑的声明"**。审计把这类轴记为 `calibration_blind_axes`。

分母真的为空时更糟。ProspectiveMetaAnalysis 的 evaluator 写着:

```python
"unsupported_refusal_rate": float(np.mean([
    row["correct_refusal"] for row in unsupported
])) if unsupported else 1.0,
```

没有不可支持世界时,校准拒答率报 **1.0** ——一场从未进行的考试给满分。

一个**指向性**的观察,样本太小不能当结论:卡片把分数写成"三条轴的乘积"的三道题,
`claim_all` 全部归零(MethaneSourceAttribution、TransmissionSpectrumSpecies、IMUBiasCalibration);
而为过度声明付钱的十二道题,没有一道是乘积式。乘积让任一轴归零就整体归零,这正是
"从不平均"这条原则在打分函数里的自然写法。另有八道非乘积的题也把 `claim_all` 压到了 0,
所以乘积是充分而非必要。

### 3. 天花板

被计分的三十二道题里,三十一道的参考解至少有一条轴停在极值(FDR 0.0、拒答率 1.0、覆盖率 1.0
或机制分 1.0);二十道至少有一条轴对校准决定不敏感,其中十七道不敏感的正是 false-discovery
那一类。五道题的参考解 `combined_score` 恰好是 1.000:SurvivorshipConfoundedDesign、
PTAHellingsDowns、QuinaryConvexHull、AMOCTippingRefusal、LookElsewhereAnomaly。

在这些题上,任何达到参考解的候选与任何超过它的候选无法区分——量程已经用完。

### 4. 前沿模型落在哪里,以及一次抽样说明不了什么

准入检查点 D16 的线是"**首提案**不得够到参考解"。搜索者条件 `gpt-5.6-terra` / responses /
medium(condition `3cf1c810`,已登记在 `sle/llm_conditions.yaml`),`greedy_rewrite`:

| 任务 | 参考解 | 首提案 | 预算内最好 | 提案数 |
|---|---|---|---|---|
| CausalDiscovery/SurvivorshipConfoundedDesign | 1.000 | **1.000** | 1.000 | 12 |
| AtmosphericChemistry/MethaneSourceAttribution | 0.754 | **0.875** | 0.879 | 3 |
| AtmosphericChemistry/MethaneSourceAttribution | 0.754 | 0.250 | 0.391 | 12 |
| ComputerArchitecture/CacheReplacementPolicyID | 0.778 | 0.000 | 0.222 | 3 |
| Mathematics/BlackBoxGroupIdentification | 0.286 | 0.143 | 0.429 | 12 |
| AtmosphericScience/RadiativeTransferFit | 0.791 | 0.000 | 0.000 | 12 |
| EvidenceSynthesis/ProspectiveMetaAnalysis | 0.909 | 无效 | 0.000 | 5 |

两道题的首提案越过了参考解。MethaneSourceAttribution 那次越线**不是捷径**:逐轴看,模型的机制
恢复是十六个世界里对十五个,参考解对十三个;FDR 0.0625 对 0.0714;拒答率两者都在 1.0 天花板。
它是把参考见证做得更好了。

但一次 draw 不足以说明这是常态还是运气,所以两道题各重复抽样。

**同一条件、同一道题,重复抽样的首提案分布如下**(每次 `--budget 3`,`--seed` 1–5,另加上表
两次完整运行;D16 只读首提案):

| 任务 | 参考解 | 首提案(按 draw) | 越线 |
|---|---|---|---|
| CausalDiscovery/SurvivorshipConfoundedDesign | 1.000 | 1.000 / 1.000 / 1.000 / 1.000 / 1.000 / 1.000 | **6 / 6** |
| AtmosphericChemistry/MethaneSourceAttribution | 0.754 | 0.875 / 0.250 / 0.817 / 0.938 / 0.660 / 0.938 / 0.938 | **5 / 7** |

两道题的结论完全不同,而单看一次 draw 分不出来:

- **SurvivorshipConfoundedDesign 是确定性的天花板。** 六次抽样的首提案全部**恰好**是 1.000,和
  八条轴全部饱和的参考解逐位相同。这道题不是"区分度低",是根本没有区分度:前沿模型第一次
  尝试就到顶,任何更强的模型只会得到同一个数。
- **MethaneSourceAttribution 是高方差地超过参考解。** 七次抽样的首提案跨越 0.250 到 0.938,
  五次越线。也就是说 D16 按单次 draw 判定时,这道题大约有 2/7 的概率被判合格——**同一道题的
  准入结论取决于抽到哪一次**。

这正是 D-d 要按分布写的理由:一个数既不能证明一道题守得住,也不能证明它守不住。

同一个模型在 ProspectiveMetaAnalysis 上五次提案没有一个有效提交,在 RadiativeTransferFit 上
十二次全是 0。**区分度是逐题的,而且现在没有任何东西在测它。**

## 建议的四条判据

- **D-a 退化上界。** 卡片公布三个通用策略的实测分,要求
  `max(abstain_all, claim_all, constant_answer) < reference × (1 − margin)`。这是把
  `shortcut_probe` 的契约形状套到不需要作者想象力的策略上。关键性质是这些策略**合法**——
  提交的是参考解自己的答案,所以"畸形候选当然得零分"不适用。不适用或被拒的策略记为
  `not_applicable` / `rejected`,不折算成通过。
- **D-b 分母。** 每条比率轴公布分子与分母;分母为空时该轴是 `not_measured`,不是 1.0。
- **D-c 余量。** 至少一条计分轴的参考解严格落在量程内部。参考解处处顶格的题只能排出比它差的
  东西,排不出比它好的。
- **D-d 前沿落点,按分布而不是按一个数。** 卡片记录某个具名搜索者条件在给定预算下落在哪里。
  落在参考解之上,说明这道题的见证该抬高或该退出区分集合;落在 0,说明先要分清是科学难度
  还是接口问题。**D16 现在按单次 draw 的首提案判定,这一条需要改**:实测同一条件在
  MethaneSourceAttribution 上七次抽样的首提案跨越 0.250 到 0.938,五次越过参考解,单次判定
  约有 2/7 的概率放它过关。"首提案不得够到参考解"应当写成 k 次 draw 里越线次数的上限,把 k、
  每次的数和搜索者条件都记进卡片。k 不必大:SurvivorshipConfoundedDesign 六次全部**恰好**
  等于参考解,三次就已经说明问题。

## 与既有检查的分工

- `shortcut_probe`(`scripts/shortcut_probe_contract.py`)管**作者声明的**候选,PR #99 已经把
  margin 上限、`excluded` 的度量和 AST 枚举补上。本审计管**通用的**那一族,两者不重叠。
- PR #104 的四列轴契约实现 D-b。
- PR #105 用"参考解是否贴着归一化天花板"实现 D-c 的标量版本;本审计补的是**逐轴**饱和。
  它还排除了一条路径,理由是"通用退化探针是畸形候选,`check_task_contribution` 本来就要求它们
  得零",并举了两例实测(QuinaryConvexHull 上的"全部复制"策略、LookElsewhereAnomaly 上的
  local-z 阈值,都是 0.0)。**那两个例子是对的**:本审计的 `constant_answer` 就是"全部复制"的
  一般形式,它在被计分的二十七道题上全部为 0。但"通用 ⇒ 畸形 ⇒ 零"作为一般命题过宽:校准翻转
  这一族同样通用,提交的却是参考解自己的合法答案(`valid = 1`),`claim_all` 在 QuinaryConvexHull
  上得 0.500、在 ProspectiveMetaAnalysis 上得 0.833。两件工作互补,需要修订的是那条前提的范围,
  不是它举的例子。

## 这次测量到不了的地方

- 九道题不带参考程序,没有可比的对照;本机另有五道缺 oracle 依赖。计时类失败已用更长的时钟
  重跑过,`eval_time_seconds: 30` 的题在本机需要更多时间才能跑完参考解(PR #103 在处理这条)。
- `abstain_all` / `claim_all` 只翻 `abstain` 标志(含通过回调提交的那一份),不构造"换一个错误
  机制"这类声明,所以它给出的是**下界**:一个真正的攻击者不会比它更弱。
- 前沿落点只测了六道题、单一条件。其中两道做到了六到七次 draw,其余每道只有一到两次,所以
  除那两道以外的行同样只是单点,不能据以下准入结论。
- 本审计只报告,不当门。要当门,先要在基准机上重跑一遍,并接受 D-a 会让若干现存任务变红。

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
的消融版。卡片同时写了期望分的两道题,本次实测与声明逐位一致
(CacheReplacementPolicyID 0.777778、SparseVectorAudit 0.819398)。

## 测到了什么

四十六道 discovery 题:九道以模拟真值锚定、不带参考程序,无从对照;本机另有五道缺 oracle
依赖(networkx、astropy、sympy、qutip、nmrsim)。其余在本机测到。

### 1. 世界是真的不同,沉默也不是免费的

`constant_answer` 在被计分的二十五道题上**全部**是 0.000。把第一个世界的答案重放到所有世界,
一分不得——世界之间的差异是实的,这一层没有可乘之机。

`abstain_all` 被计分的二十四道里有二十三道是 0(唯一的例外是 ProspectiveMetaAnalysis 的 46%)。这是设计使然而非侥幸:多数题的 baseline 就写着"一次便宜实验之后
在每个世界上拒答",于是刻度的零点已经把"全部拒答"吸收掉了。

### 2. 校准的代价只被收了一次,而且收的是沉默那一侧

`claim_all` 是唯一有牙的策略。被计分的二十三道题里,十二道给了它非零分,其中八道达到参考解的
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

被计分的二十九道题里,二十八道的参考解至少有一条轴停在极值(FDR 0.0、拒答率 1.0、覆盖率 1.0
或机制分 1.0);十八道至少有一条轴对校准决定不敏感。五道题的参考解 `combined_score` 恰好是 1.000:SurvivorshipConfoundedDesign、
PTAHellingsDowns、QuinaryConvexHull、AMOCTippingRefusal、LookElsewhereAnomaly。

在这些题上,任何达到参考解的候选与任何超过它的候选无法区分——量程已经用完。

### 4. 前沿模型落在哪里

搜索者条件 `gpt-5.6-terra` / responses / medium(condition `3cf1c810`,已登记在
`sle/llm_conditions.yaml`),`greedy_rewrite`,每题预算 12:

| 任务 | 参考解 | 模型最好 | 提案数 |
|---|---|---|---|
| AtmosphericChemistry/MethaneSourceAttribution | 0.754 | **0.879** | 3 |
| Mathematics/BlackBoxGroupIdentification | 0.286 | **0.429** | 13 |
| CausalDiscovery/SurvivorshipConfoundedDesign | 1.000 | **1.000** | 13 |
| ComputerArchitecture/CacheReplacementPolicyID | 0.778 | 0.222 | 4 |
| EvidenceSynthesis/ProspectiveMetaAnalysis | 0.909 | 0.000 | 6 |

MethaneSourceAttribution 那次不是 hack:逐轴看,模型的机制恢复是 16 个世界里对 15 个,参考解
对 13 个;FDR 0.0625 对 0.0714。它是把参考见证做得更好了,用了三次提案。
SurvivorshipConfoundedDesign 则是另一种:模型打到 1.000,与八条轴全部饱和的参考解并列,这道题
已经无法再分出高下。同一个下午,同一个模型,在 ProspectiveMetaAnalysis 上六次提案全是 0。

**区分度是逐题的,现在没有任何东西在测它。**

## 建议的四条判据

- **D-a 退化上界。** 卡片公布三个通用策略的实测分,要求
  `max(abstain_all, claim_all, constant_answer) < reference × (1 − margin)`。这是把
  `shortcut_probe` 的契约形状套到不需要作者想象力的策略上。关键性质是这些策略**合法**——
  提交的是参考解自己的答案,所以"畸形候选当然得零分"不适用。不适用或被拒的策略记为
  `not_applicable` / `rejected`,不折算成通过。
- **D-b 分母。** 每条比率轴公布分子与分母;分母为空时该轴是 `not_measured`,不是 1.0。
- **D-c 余量。** 至少一条计分轴的参考解严格落在量程内部。参考解处处顶格的题只能排出比它差的
  东西,排不出比它好的。
- **D-d 前沿落点。** 卡片记录某个具名搜索者条件在给定预算下落在哪里。落在参考解之上,说明
  这道题的见证该抬高或该退出区分集合;落在 0,说明先要分清是科学难度还是接口问题。

## 与既有检查的分工

- `shortcut_probe`(`scripts/shortcut_probe_contract.py`)管**作者声明的**候选,PR #99 已经把
  margin 上限、`excluded` 的度量和 AST 枚举补上。本审计管**通用的**那一族,两者不重叠。
- PR #104 的四列轴契约实现 D-b。
- PR #105 用"参考解是否贴着归一化天花板"实现 D-c 的标量版本;本审计补的是**逐轴**饱和。
  它还排除了一条路径,理由是"通用退化探针是畸形候选,`check_task_contribution` 本来就要求它们
  得零",并举了两例实测(QuinaryConvexHull 上的"全部复制"策略、LookElsewhereAnomaly 上的
  local-z 阈值,都是 0.0)。**那两个例子是对的**:本审计的 `constant_answer` 就是"全部复制"的
  一般形式,它在被计分的二十五道题上全部为 0。但"通用 ⇒ 畸形 ⇒ 零"作为一般命题过宽:校准翻转
  这一族同样通用,提交的却是参考解自己的合法答案(`valid = 1`),`claim_all` 在 QuinaryConvexHull
  上得 0.500、在 ProspectiveMetaAnalysis 上得 0.833。两件工作互补,需要修订的是那条前提的范围,
  不是它举的例子。

## 这次测量到不了的地方

- 九道题不带参考程序,没有可比的对照;本机另有五道缺 oracle 依赖。计时类失败已用更长的时钟
  重跑过,`eval_time_seconds: 30` 的题在本机需要更多时间才能跑完参考解(PR #103 在处理这条)。
- `abstain_all` / `claim_all` 只翻 `abstain` 标志(含通过回调提交的那一份),不构造"换一个错误
  机制"这类声明,所以它给出的是**下界**:一个真正的攻击者不会比它更弱。
- 前沿落点只测了六道题、单一条件、预算 12,是探针不是普查。
- 本审计只报告,不当门。要当门,先要在基准机上重跑一遍,并接受 D-a 会让若干现存任务变红。

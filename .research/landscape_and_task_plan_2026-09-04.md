# 学科 benchmark 调研与下一批任务计划(2026-09-04)

四路一手核查:数学前沿题的评估方式、2026 各学科(尤其生物)benchmark、跨学科可验证开放问题、
以及最接近的八个竞品逐条读原文。本文只写核实过的事实,未核实的显式标注。

## 0. 先更正三条已流传的错误

- **Terminal-Bench-Science 0.1 的真实榜单**(官方博客 2026-08-27):Opus 5 30.0%、GPT-5.6 Sol 22.4%、
  Claude Fable 5 21.4%。榜上没有 GPT-6 Astra,没有 Fable 5.1。此前口耳相传的「Astra 64.6%」系伪造。
  同一来源的 GeneBench-Pro / LifeSciBench / HLE-with-tools 的 Astra 数字一并降级为**待核实**。
- **Grok 5 与 Gemini 4 不存在**。xAI 现役 Grok 4.5(2026-07-08),Google 现役 Gemini 3.1 Pro / 3.8 Flash。
  GPT-6 代号 Astra 确实存在,2026-09-03 预览、09-05 公开。
- **arXiv:2607.04508 不是 benchmark**,是两作者四页 ICML workshop 立场论文,全文将来时,无任务集无分数。

## 1. 「Claude 67.2%」到底是什么

不是 benchmark 分数。Anthropic 自报的一次性研究结果:把「已证明落在临界线上的 zeta 零点比例下界」
从 41.6% 提到 67.2%。过程是一句 prompt、54 篇 arXiv、两次 Claude Code 会话、31M 输出 token、
约 60 个子智能体、2400 条 shell 命令、约 36 小时。验证是三层:

1. **数值本身**(41.6 → 67.2,无歧义的「更好」)
2. **Lean 形式化**,通过标准校验工具
3. **人类专家**:两位 Anthropic 数学家(Alpöge、Furman)+ 两位外部专家(Conrey、Goldston)

据核查没有 arXiv 预印本,未经独立同行评议。Anthropic 自己写明不认为这条路能通向证明。

**对我们的意义**:第 1 层正是 SLE 无上限计分做的事,第 2 层是形式验证器,第 3 层是 SLE 刻意拒绝的。
更重要的是 —— Levinson/Conrey 方法本身**就是一个优化问题**:选 mollifier 的系数,代入显式变分泛函,
算出比例。41.6 → 67.2 字面上是优化的输出。这给出一个新的任务形状(见 §3)。

## 2. 竞品格局:哪部分新意还在,哪部分没了

逐条读了八篇原文。

### 不再新的:「智能体改程序 → 冻结 oracle 打分 → 受预算迭代」

- **NatureBench**(arXiv:2606.24530,清华,v1 2026-06-23 / v2 07-06)是最大先例风险。90 任务 / 333 实例,
  六领域 + 15 个跨学科任务;Docker 工作区里写代码;宿主侧确定性评测服务智能体够不到;
  4 小时实时预算迭代,三个端点 `/evaluate` `/best_score` `/time_remaining`;**分数无上限**,
  §5.3 明确论证「超出 SOTA 的极端分数是合法输出」。最好 Claude Opus 4.7 在 17.8% 任务上超 SOTA。
  **SLE 优化半边七列里它占了五列。**
- **ORAgentBench**(2606.19787)107 题运筹:「隐藏验证器」「私有 oracle / 参考实现」,45 分钟单次提交,
  分数 clip 进 [0,1]。**Opti-Agent-Bench**(2607.10768)运筹:开发智能体迭代写可执行代码,
  但 40% 的检查点用 LLM-as-judge,rubric 封顶 5.0。
- **SciAgentArena**(2606.12736,Yale + Broad)约 200 题五个生物医学领域,其分子优化子任务字面上是
  「在 100 次 oracle 调用预算内实现并运行一个优化器」。
- **Terminal-Bench-Science 0.1**(Stanford,70 题五个学科)冻结隐藏 pytest,但二值 0/1 奖励、
  单次 episode、只有墙钟超时,没有实时 oracle 循环。

结论:**这个循环不是我们的新意**。README 里把「可执行搜索」与「准入判据」并列会被读成前者也是新的,必须改。

### 仍然无人占据的

1. **开环对照作为准入判据**。八篇里「open-loop」作为实验臂零出现;唯一一次出现是 SciAgentArena
   描述弱智能体的失败模式(「把 100 次调用开环耗光」)。没有任何一篇跑「同一搜索者、同一预算、
   每个提案只看冻结基线」的对照,自然也没有随预算扩大的差距论证,更没有拿它当任务准入门。
2. **发现三轴的打包**。「false discovery rate」/「FDR」在八篇全文里**零命中**。
   Auto-Discovery-Bench(2502.15224,NUS)有机制恢复无拒答,而且自陈「目标不是模拟真实的化学、
   社会学或物理」;SciAgentArena 有 5 道该拒答的题;StatefulDiscovery(2606.11851)整篇讲避免过度解读
   但用 Gemini-3.1-pro 当 judge、全文「oracle」零出现。三件事拆开都不新,合成三元组没人做。
3. **多学科同协议下的发现半边**。NatureBench 有多学科但没有发现半边;Auto-Discovery-Bench 有发现循环
   但是合成抽象、自陈不模拟真实学科。

### 一个被回答了的质疑

「无上限计分是不是没人认为可行?」—— NatureBench 的连续 SOTA-relative gap 加上 §5.3 的显式论证,
说明 2026 年**已经有人认为可行并发表了**。这条压力测试通过,不必再犹豫。

## 3. 新任务形状:`certificate_bound`

67.2% 那件事的可推广形状是:**智能体提出一份证书,冻结程序验证它并报告它蕴含的界**。
这与现有 `combinatorial` 的区别在于产物不是一个对象而是一个**可验证的论证**,分数是它蕴含的界的强度。

这一格现在是空的,而它恰好是 2026 年最受关注的数学结果的形状。候选见 §4 的 B 组。

## 4. 任务候选(按 verifier 成本与格点空缺筛过)

当前 62 题的格点:56 格填了 26 格。最刺眼的空缺是 **Chemistry(最大学科 13 题)在 formula /
structure / evidence 三格全空**,**Engineering × combinatorial = 0**,**EarthScience × structure = 0**,
**Biology × combinatorial / engineering_design = 0**。

### A 组:无上限构造(verifier 最便宜,直接进 combinatorial 格)

| 候选 | 格 | 纪录与出处 | verifier | 成本 | 风险 |
|---|---|---|---|---|---|
| SpinGlassGroundState(G-set Max-Cut) | Physics × comb | G63 = 27,047,arXiv:2510.21105(2025-10) | 一次边求和 | 毫秒 | 低。风险是启发式成熟,模型可能背得出好方法 |
| StabilizerCodeDistance | Physics × comb | codetables.de 的 [[n,k,d]] 表,n=50,k=10 时 d=10 已知 / 上界 15 | Brouwer–Zimmermann 最小距离 | n≲60 时秒级 | 中。最小距离 NP-hard,必须限 n |
| MIPLIBOpenBound | Engineering × comb | 217 个 open 实例(miplib.zib.de,2026-09 访问) | 官方 solution checker | 毫秒 | 中。要挑「秒级可评但纪录难破」的实例 |

### B 组:`certificate_bound`(新格)

| 候选 | 纪录与出处 | verifier | 成本 | 风险 |
|---|---|---|---|---|
| BellInequalityBound(I3322) | NPA level-4 界 ≈ 0.250875,arXiv:2607.14755(2026-07) | NPA SDP 可行性检查 | 毫秒–秒 | 中。需确定性 SDP,不能用随机化求解器 |
| MollifierProportion(黎曼形状) | 41.6% → 67.2%(Anthropic 自报,未同行评议) | 变分泛函数值计算 | 秒 | **高**。泛函涉及 zeta 扭矩,写对本身是研究级工作 |

建议:**先做 Bell,它是同一形状里可控的那个**;Mollifier 作为拉伸目标,并且**不以 67.2% 为锚点**
(未经同行评议),改用已发表的 41.6%(Bui–Conrey–Young 2011 一系)。

### C 组:填学科空缺的发现题(需自建世界,含拒答轴)

| 候选 | 格 | 科学 | 拒答世界 |
|---|---|---|---|
| 化学:预算内从动力学数据认出反应网络的**拓扑** | Chemistry × structure | 已有 ReactionMechanismFitting 是 param_inversion,这题产物是有向图 | 网络不可辨识(多个拓扑给同样的浓度轨迹) |
| 化学:一批相互矛盾的热力学测量,诊断缺陷并给最佳值 | Chemistry × evidence | 与 DiscrepantMeasurements 同形不同题:这里有物理一致性约束(Hess 定律闭合) | 循环不闭合到无法归因于任何单一测量 |
| 地球:预算内布设炮点,反演地下速度结构 | EarthScience × structure | OpenFWI 形状,70×70 网格 | 观测几何使解非唯一 |
| 生物:预算内设计 CRISPRi 扰动,恢复调控关系 | Biology × evidence | Virtual Cell Challenge 形状但加预算与拒答 | 扰动靶点在通路外,数据不含可归因信号 |

## 5. 框架侧必须做的三件事

### 5.1 锚点时效性(从 P2 提到 P0)

AlphaEvolve 2025 把 11 维 kissing number 提到 593,FunSearch 把 8 维 cap set 提到 512 —— 这些纪录
**正在被主动推进**。我们九道无上限题的锚点全是 2026-09-03 重推导的,当前无冲突,但仓库没有任何
时效性检查。过期的无上限锚点会静默地错误计分(见 CirclePacking 与 Superpermutation 两次前科)。

做法:`scripts/check_anchor_freshness.py` —— 每条锚点带 `retrieved_on`,超过 N 天未复核就在
`audit_task_maturity.py` 里标黄;对有公开榜单的(codetables.de、miplib、TSPLIB)做可达性抽查。

### 5.2 退化程序探针(补检查点 12 的另一半)

FrontierMath 的设计准则是盲猜成功率低于 1%。我们的捷径探针查的是「低维参数化能到多少」,
没查「什么都不做的退化程序能到多少」。两者不同:后者是常数输出、空输出、复制基线。
加进 `check_task_contribution.py`。

### 5.3 README / 论文的定位改写

现在的措辞把「多学科 + 可执行搜索 + 开环饱和准入」三者并列。前两者 NatureBench 已占。改成:

- 循环不是新的(点名 NatureBench、ORAgentBench、Opti-Agent-Bench、SciAgentArena)。
- 新的是**门**:开环对照饱和作为任务准入判据,八篇同行里零出现。
- 新的是**发现半边的三轴打包**:FDR 在八篇里零命中。
- 邻居表补上 NatureBench、Terminal-Bench-Science、Auto-Discovery-Bench、SciAgentArena。

## 6. 排期建议

**先做 5.3**(免费,且越晚改越被动),**再做 5.1 与 5.2**(两个脚本,一天),
**然后 A 组两题 + B 组 Bell**(都是便宜 verifier,填 Physics/Engineering × comb 与新格),
**最后 C 组按 Chemistry 优先**(最大学科三格全空最刺眼)。

跨模型测量另计:GPT-6 Astra 与 Gemini 3.1 Pro 现在都可测,而准入判据是「任务 × 搜索器」的联合性质,
多一个搜索器就多一列矩阵。这件事的优先级高于再加任务 —— 五个 certified 任务对 Opus 5 是 0/5,
换个搜索器可能完全不同,那才是判据本身的证据。

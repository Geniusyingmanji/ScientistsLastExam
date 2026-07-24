# EdgeBench → Frontier-Science：长程学习实验增补

> 核验基线：ByteDance Seed, *EdgeBench: Unveiling Scaling Laws of Learning from
> Real-World Environments*, arXiv:2607.05155v1, 2026-07-06；公开数据集
> `ByteDance-Seed/EdgeBench`，2026-07-24 访问。不要与 2018/2024 年同名的
> edge-computing benchmarks 混淆。

## 1. 可以直接吸收的实验骨架

EdgeBench 的主要贡献不是某个科学 oracle，而是对长程 agent 学习的测量设计：134 个任务、
每个 task--model 三次独立 12 小时运行、约 38,000 小时交互，以及如下协议。

覆盖面上也要注意：正文全量 suite 报告 39 个 `Science / ML` 任务，但截至 2026-07-24 的
公开 51-task manifest 中只有 4 个被标为该类（BipedalWalker、Borden source inversion、
D-ABIC gravity inversion、graph node classification）。所以公开集足够核验 harness，却不能替代
Frontier-Science 对约 50 个有科学意义开放任务的领域覆盖、oracle 独立性和发现证据审计。

1. **双反馈环**：agent 可频繁运行本地测试/模拟器；权威 hidden judge 只在主动提交时返回
   有限反馈，并受提交预算与 cooldown 约束。
2. **不可见的固定间隔快照**：host 定时评估当前 artifact，但分数不进入 agent 上下文，因而
   能测量真实轨迹而不增加反馈带宽。
3. **时间切片曲线**：报告 `@2h/@4h/.../@12h` 的 best-so-far，而不是只报告终点。
4. **三次独立重复和逐任务方差**：长程服务故障和生成随机性被显式记录；少于三次有效运行
   的 cell 加标记。
5. **连续经验对照**：12 小时连续 workspace/history 与 6×2 小时独立重启作同总时间比较，
   区分学习和 best-of-N 抽样。
6. **初始能力与学习增益分离**：在 first-attempt 相近的任务切片上比较后续 gain，减少把模型
   先验知识当作环境学习的混淆。
7. **轨迹机制诊断**：除终点外报告有效提交率、提交数量、上下文长度、continuation harness
   和 milestone/subscore 变化。
8. **适应性攻击审计**：原文实际观察到用 400+ 次反馈反演 hidden targets、优化随机上尾、
   复用 judge seed、跨 trust boundary 和联网查答案，并据此采用隐藏多 seed、反馈聚合、完整
   writable-path integrity、网络隔离与 submission throttling。

这些应成为 Frontier-Science 的 long-horizon track，而不替换当前便宜的 admission/calibration
track。先在 4--6 个代表性任务做 2h/6h/12h pilot，证明基础设施与统计口径，再扩大到约 50 个
admissible tasks。

### 1.1 公开 Science/ML 任务的任务级启发

公开 manifest 能核验 task contract，但不能看到私有 evaluator/data。因此下表只判断公开协议能
支持什么证据，不推断私有实现一定缺少什么。

| 公开任务 | 值得迁移的设计 | 公开 contract 尚不能支持的 science 表述 |
|---|---|---|
| Borden source inversion | 稀疏含噪/删失观测、有限区域源、隐藏井与未来时刻预测、预测质量 gate 掉格式分 | 权威分数仍来自一个隐藏 forward model；未公开独立 simulator、null/misspecified worlds、机制等价类和 uncertainty/refusal 评估 |
| D-ABIC gravity inversion | synthetic + measured field data、L0/L1、D-ABIC/Cooling/L-curve 多方法对照、代码与报告共同交付 | 目标方法和论文已指定，主要测复现与实现；真实地下密度不可直接确认，不能把 field-data fit 写成新机制发现 |
| BipedalWalker locomotion | 只提交冻结 policy artifact、隐藏随机评估、aggregate-only feedback、禁止 pretrained policy | 优化的是通用 RL reward；公开目标不要求科学假说、机制、校准或外部验证，因此属于随机开放优化而非科学发现 |
| Graph node classification | unseen graph、CPU 约束、artifact-only evaluator | 公开描述是通用 ML 泛化任务；任务类别本身不提供科学对象、科学问题或发现证据 |

对约 50-task Frontier-Science inventory，由此增加三条准入约束：

1. **按证据目标分 track**：`scientific optimization`、`mechanism/discovery`、`replication` 分榜；
   不把三者混成一个 Science/ML scalar。任务名、数据来源或 ML 方法带有科学词汇不算科学价值证据。
2. **科学对象和决策后果必须明确**：优化任务需对应物理、化学、生物、地学、医学或工程科学中的
   可解释设计/控制量、约束和 sealed operating regimes；发现任务还需 claim、uncertainty、refusal、
   intervention 和独立 confirmation。纯算法吞吐、游戏 reward 或任意预测准确率不计入目标约 50 个。
3. **吸收 baseline-first 和质量 gate，但提高 gate 层级**：先生成 legal weak baseline 可降低 invalid
   run；格式、报告和 nominal score 不能绕过 hidden transfer、hard validity、false discovery 与独立
   confirmation。Baseline 必须足够弱且不携带 truth，reference witness 必须 truth-blind 可复现。

## 2. 不能直接照搬的部分

EdgeBench 的总曲线衡量“环境中提升”，不自动等于科学发现。science 场景至少有五个额外
风险。

- **异质标量平均会隐藏语义**：预测误差、程序速度、机制恢复、实验信息与错误发现不能仅靠
  task-wise 0--100 rescaling 后平均。一个更高 simulator score 可能没有更可信的机制。
- **best-so-far 会奖励幸运上尾**：随机实验、MD/RL、噪声拟合尤其如此。应比较 common-random-
  numbers 下的均值、分位数/CVaR 与重复复核，而非单次最大值。
- **只对 valid runs 求均值有 survivorship bias**：基础设施失败可单列，但 agent 导致的超时、
  协议失败和数值崩溃必须计入 capability；同时报告 intent-to-evaluate 与 valid-only sensitivity。
- **hidden judge 反馈可能成为测量仪器**：连续精细分数可被有限差分或方程求解反演。
  science task 必须有 feedback-channel capacity / target-access audit，且 leaderboard judge 与最终
  confirmation oracle 分离。
- **aggregate log-sigmoid 不是单任务定律**：EdgeBench 自己指出，单任务曲线会有平台和跳跃，
  多模块、bottleneck、异质学习速度会产生多阶段曲线。约 50 个 science tasks 上应预注册曲线
  family comparison，而不是默认拟合 sigmoid 后宣布 scaling law。

### 2.1 对正文、附录与公开 SForge 的二次审计

以下不是对 EdgeBench 结论的否定，而是其协议迁移到 science 后必须显式处理的 estimand 差异。

1. **隐藏历史最佳不是可部署的最终发现**。公开 SForge 文档把 agent submission 和不可见
   auto-eval snapshot 一并纳入 final best。这个 retrospective evaluator envelope 很适合画学习
   上界，但 agent 不知道哪个隐藏快照最好，也无法据此声明最终机制。Science 必须同时保存
   `scheduled current artifact`、仅依据可见证据选出的 `agent-declared incumbent`、
   `terminal artifact` 和事后 `evaluator envelope`；只有预先声明的 artifact 能进入一次性
   confirmation。
2. **continuous versus restart 捆绑了多种“经验”**。EdgeBench 的 12h continuous 与
   `6 x 2h` restart 对照同时改变模型上下文、workspace、当前 artifact、反馈历史、文件笔记和
   continuation harness。它证明“整套持续状态”有增益，却不能定位增益来自科学记忆、代码继承
   还是上下文长度。其 200k/1M context 和 Base/Goal/Ralph 附录消融也表明 harness/state 是实质
   因素。我们需要按记忆通道拆分，而不能把全部差值归因于模型学会了科学规律。
3. **best-so-far 会抹去回退、遗忘和证伪**。EdgeBench 的 latent task graph 把 score unit 视为
   unlock 后不再锁回；真实科学过程会撤回假说、发现系统误差并降低置信度。一次没有提高 proxy
   score、但排除了错误机制的实验可能具有高信息价值。因此除 envelope 外还要报告 current-state
   regression、recovery time、belief revision 和 informative negative results。
4. **定时 tar 不是跨文件原子快照**。公开实现直接从仍在写入的 work container 打包 live
   `submit_paths`；prompt 还会告知 agent 保持文件随时可评估。多文件数据、checkpoint、数据库和
   模拟输出可能在捕获时处于不一致代际。Science snapshot 必须基于 immutable publish manifest
   或原子目录/文件系统快照，并区分 capture failure 与 artifact invalidity。
5. **事件时间不能只用一个 wall-clock**。异步 judge 下至少有 artifact capture、judge queue、
   evaluation、feedback delivery 和下一次 action 五个时间点。耗时 PDE/MD/实验任务还要区分
   agent active compute、simulator/instrument、排队、API outage 和 idle。主结果同时给真实部署
   elapsed-time 曲线与 capability-normalized active-time/oracle-cost 曲线，避免把服务抖动或评测
   延迟误写成科学学习速度。
6. **first-attempt 匹配不能决定确认性任务集**。EdgeBench 正文按 first-attempt 相近选了
   18-task slice，但公开文本不足以判断该切片是否由独立数据预先锁定。若依据同批运行的初始分数
   选任务，会产生 selection/regression-to-the-mean 风险。我们的 confirmatory cohort 必须在目标
   模型运行前按科学有效性和任务层级锁定；全任务 hierarchical model 以 baseline ability 为协变量，
   匹配切片只作 sensitivity analysis。
7. **漂亮的总体 S 曲线需要变换与选择敏感性分析**。0--100 重标定、截断、单调 historical
   maximum、只纳入 valid runs、挑选“能持续提升”的任务以及跨异质 midpoint 平均，都可能让
   曲线更平滑。除了 held-out time，还要做 held-out-task prediction、task/run bootstrap、残差
   自相关、raw-metric/rank/Pareto sensitivity 和 independent-restart null simulation；若拟合的
   `tmid` 落在观测窗外，不把它解释为已测得的学习速度或 ceiling。
8. **模型、脚手架和服务是三个不同对象**。EdgeBench 对 GPT 使用 Codex、其他模型主要使用
   Claude Code，context window 也不同；附录中的 Goal/Ralph 效果又随任务和模型变化。因此未来
   若比较模型代际，只能称为 agent-system 结果，或在相同 harness/context/tool/serving 条件下另做
   model-only 对照。
9. **强制跑满与反复提交会改变科学错误率**。公开 harness 用 stop hook 阻止自然退出，案例中
   12h 内有 224 次主动提交和 23 次 auto-eval。工程 leaderboard 可把它视为搜索预算；科学声明
   若反复查看同一 development/holdout 反馈再择优，则普通 p-value/CI 和一次性 false-discovery
   口径失效。必须预注册数据复用、sequential stopping 和 confirmation 规则，并在 null worlds 上
   实测假阳性随反馈次数的增长。
10. **复现已知目标和发现未知规律必须分开**。EdgeBench 的 gravitational-wave case study 明确
    记录 agent 数字化参考曲线并据此拟合；D-ABIC 公开任务也指定已发表方法和论文。这些是有价值的
    replication/reconstruction 能力，但不能作为未知机制发现证据。Discovery track 需要答案不可从
    supplied literature、公开网页、模型记忆或 reference artifact 直接恢复的 procedural/prospective
    confirmation worlds。
11. **grader feedback 不等于 scientific observation**。Outer loop 的分数、分项误差和 hidden-test
    diagnostics 能帮助工程迭代，但现实科学家通常获得的是仪器读数、实验失败、solver residual 或
    审稿意见，而不是对未知真值的距离。Science 主实验应让 agent 只看到可实现的观测通道；任何
    truth-relative score feedback 单列为 oracle-assisted optimization，不与自主发现混写。

## 3. Science 独有的核心向量轨迹

每个 hidden snapshot 记录同一 artifact 的向量，而不是只记录 `combined_score`：

| 轴 | 含义 | 最低证据 |
|---|---|---|
| `O` optimization | 目标/utility/Pareto hypervolume | development 与 sealed confirmation 均报告 |
| `F` fidelity | 未见输入/物理 regime 的预测或复现实度 | instance + family/regime held-out |
| `M` mechanism | 可解释参数、因果结构或守恒关系恢复 | 参数对称性/等价类感知的 metric |
| `I` information | 所选实验的 rank、conditioning、EIG 或辨识度 | 与真实 mechanism recovery 分开 |
| `V` validity | 可行性、安全、稳定性、守恒、数值收敛 | hard gate + violation magnitude |
| `R` refusal | null/OOD/model-mismatch 上正确拒绝 | false-discovery 与 over-refusal 同报 |
| `C` coverage | supported worlds 中实际提出 claim 的比例 | 防止 always-abstain 得到虚高可信度 |
| `U` uncertainty | coverage/calibration/sharpness | sealed worlds 上 proper scoring rule |
| `K` cost | oracle/tool/token/wall/energy/sample cost | 预算曲线与 AUC，而非只看终点 |

主榜至少采用 gate + Pareto/rank aggregation：协议有效、false discovery、hard safety 和 confirmation
replication 先作为门槛，再比较 `O/F/M/I/V/R/C/U/K`。不得将这些维度平均成一个“自主科学发现
分数”。

## 4. 必加的 science 实验

### E1. 三层 world split，而非普通 train/test

- `development`: 可见文档、local simulator 和有限 judge feedback；
- `sealed transfer`: 新参数、新拓扑/物种/材料家族、新边界条件与新 fidelity；
- `confirmation`: server-held procedural worlds 或独立 simulator/data source，只在最终 artifact 上
  一次评估，不返回给搜索。

分别报告 interpolation、parameter extrapolation、structural shift、model misspecification 和 null。

### E2. 信息量 × 推断质量的 2×2 实验

主动科学任务必须包含 informative/uninformative design 与 competent/weak inference 的交叉对照。
这验证 `I` 指标确实测实验几何，而 `M/F/C` 测数据解释。SeismicWaveInversion-v2 已给出第一个
反例：GPT-5.5 的 `I=0.974--1.0` 与满预算采集仍可对应 `M=0` 和 supported coverage 0。

### E3. 模型错配、null 和负对照

每个 mechanism/discovery task 至少有：supported worlds、无信号 null、可分辨的替代机制或
misspecified worlds、以及不应改变结果的 negative-control intervention。报告 false discovery、
correct refusal、over-refusal 和 unsupported confidence；always-abstain 必须因 supported coverage
为零而不能赢。

### E4. 反馈的因果消融

在相同 wall time、oracle calls、tool calls、token budget 和尽量一致的 feedback payload 下比较：

1. normal closed loop；
2. strict selection-blind open loop；
3. continuous experience；
4. independent restarts / pass@k；
5. local proxy only；
6. sparse/coarse versus rich feedback。

需要多 seed、server-side randomness（或可复现 temperature sampling）与预注册 paired estimator。
目前 Azure 无 server-side seed 的单次 normal/blind 只能是描述性 calibration。

### E5. proxy→exact promotion 与 Goodhart 曲线

对多保真任务记录每个 artifact 的 public proxy、sealed same-model、independent higher-fidelity 和
robustness score。画出随时间变化的 proxy gap、false-promotion rate 与 rank correlation，并比较
proxy-only、periodic exact、multi-fidelity acquisition 三种策略。

### E6. 机制等价类与反事实/干预测试

参数 recovery 需按可辨识的 symmetry/equivalence class 评分；额外要求 artifact 预测未见干预、
剂量、边界或传感器位置。仅在 observational fit 上高分不能称机制发现。

### E7. 独立复算和 simulator disagreement

高分 artifact 由第二实现或不同 fidelity/数值离散复算；报告两 oracle 的 agreement、排序变化和
failure taxonomy。若 oracle 之间不一致，结果降级为 simulator-specific optimization，不得升级为
scientific claim。

### E8. 随机性与可重复性

区分 model randomness、world seed、measurement noise、solver nondeterminism 和 infrastructure
failure。固定 artifact 至少跨 hidden seeds 重评，报告 mean/SD/quantiles/CVaR、paired CRN 差值、
failure rate；禁止以 best random seed 作为 artifact score。

### E9. 发现可信度阶梯

每项结果只能落在已满足的最高层级：

1. executable/protocol-valid；
2. development optimization；
3. sealed transfer；
4. mechanism/uncertainty/refusal validated；
5. independent simulator/data replication；
6. prospective wet-lab/field validation。

当前仓库大部分结果位于 2--4；simulator score 不得写成第 6 层或“自主科学发现”。

### E10. 人类与经典方法参照

除 weak baseline 和 oracle-informed ceiling 外，加入 truth-blind classical/domain expert trajectory，
并按同一时间/实验预算记录。人类参考应记录实际 effort 和工具，而非只给一个不可比终点。

### E11. 声明式 artifact 与事后 oracle envelope

每个固定 checkpoint 同时记录四条轨迹：定时捕获的 current artifact、agent 仅凭可见反馈声明的
incumbent、run 结束时声明的 terminal artifact、以及 evaluator-only retrospective best。主结论使用
terminal/declared artifact 的一次性 sealed confirmation；hidden best 只作为诊断上界。报告
`selection regret = hidden envelope - declared confirmation`、错误 promotion 率和 terminal regression。
禁止用不可见 auto-eval 最优点替 agent 做最终科学选择。

### E12. 经验保留通道的因子分解

在相同总 wall/token/tool/oracle 预算下至少比较：

1. 全部 fresh restart；
2. 只继承当前 executable artifact，不继承对话或笔记；
3. artifact + 原始观测/实验 ledger；
4. artifact + 结构化假说、证据和 negative-result notebook，但 fresh model context；
5. 完整 workspace/history/context continuous run。

这样才能区分 best-of-N、工程 warm start、数据积累、显式科学记忆和 in-context retention。另在新
sealed world 上测试 notebook transfer：若记忆只提高同一 judge 分数而不提高机制/实验选择，则不称为
可迁移科学经验。

### E13. 证伪与“未涨分但有信息”的轨迹

不能照搬 effective-submission rate 把所有非 best 更新视为 ineffective。对每次实验/提交按预注册
规则分类为：objective improvement、information gain without score gain、hypothesis refutation/
uncertainty correction、redundant、invalid。检查 negative evidence 是否改变下一实验、缩小机制
等价类或改善校准，并报告错误假说存活时间、撤回延迟和 recovery。该轨迹与 `I/M/U/R` 分轴绑定。

### E14. 原子快照与 event-time accounting

agent 通过原子 rename 或 content-addressed manifest 发布不可变 artifact bundle；bundle 至少绑定代码、
配置、环境、数据 lineage、随机种子/solver 版本和输出 hashes。Host 记录 `scheduled_at`、
`published_at`、`captured_at`、`judge_started_at`、`judge_finished_at`、`feedback_delivered_at`，曲线按
capture/publish time 归属，反馈因果分析按 delivery time 归属。快照捕获失败、judge failure、artifact
invalid 和 agent timeout 分开编码；auto-eval 频率不得改变最终 artifact 的选择规则。

### E15. Cohort、分数变换与 scaling-law 压力测试

把 exploratory pilot cohort 与 confirmatory science cohort 分离；后者不得依据同一模型是否有长程
headroom 来筛选。每个 task 的 raw metric、单调变换、clipping 和 anchor 在运行前版本化；同时报告
raw/rank/Pareto 结果。曲线模型比较使用 hierarchical task/run effects、held-out tasks + held-out time、
block/bootstrap over tasks and runs、serial-correlation-aware uncertainty，并与 independent-restart/
order-statistic null 曲线比较。`Smax/beta/tmid` 给 profile/bootstrap uncertainty；窗外参数仅标为
不可辨识，不外推成 scaling law。

### E16. Harness、上下文与恢复机制归因

主榜固定 agent harness、context/compaction、stop/resume 和外部记忆协议并报告版本。至少在小型切片
比较 base continuation、goal state 和 file-backed fresh-context loop，记录每次 resume 后是否保留
原始数据、假说 ledger、declared incumbent 和未完成实验。跨模型比较若未统一这些条件，结论对象
明确写成 model+harness+service system，而非基础模型本身。

### E17. 自适应数据复用与 anytime-valid 证据

在 null、weak-signal 和 supported worlds 上扫描 submission/feedback budget，比较：重复使用固定
holdout、轮换 hidden folds、逐次 fresh worlds，以及一次性 confirmation。记录 family-wise false
discovery、coverage、winner's curse 和 effect-size inflation。若任务输出统计显著性或置信区间，使用
预注册 alpha spending、confidence sequences/e-values 或严格冻结的最终 confirmation；普通固定样本
p-value 不能在择优后的同一数据上解释。所有 feedback 必须绑定 artifact hash 和观察时点，迟到反馈
不得错误归因给后续 artifact。

### E18. 停止规则与继续搜索的代价

比较 agent 自主停止、forced-horizon continuation 和成本/风险感知 stopping policy。报告 time-to-valid-
claim、time-to-correct-abstention、停止后的 hidden improvement/regression、追加实验的边际信息/成本和
false-discovery 变化。科学 agent 在证据不足时停止或拒绝是能力；不能用 stop hook 把理性停止都记为
失败，也不能让无限尝试免费提高 historical best。

### E19. 任务建造与成熟度审计

EdgeBench 记录的专家建造投入均值为 57.2h，说明长程 headroom 本身需要工程与领域投入。我们不照搬
固定工时阈值，但每个约 50-task inventory 条目都记录 author/reviewer domain、expert-hours、经典方法
开发轨迹、red-team 次数、oracle disagreement、独立复算和已知 shortcut。Admission 与
`long-horizon-ready` 分开：任务可先成为科学有效的 candidate，只有证明 2h 后仍有真实 headroom、
且增益不是 judge leakage/随机上尾，才进入 6h/12h cohort。任务数量不能替代成熟度证据。

### E20. 已知答案、训练污染与新颖性审计

每个 task 标注目标是否来自已发表表格/曲线、公开数据库、提供的论文、程序生成或 prospective
采集，并记录模型 knowledge-cutoff 前的公开可得性。做 internet/reference-access ablation、目标字符串
和数值指纹扫描，并用同物理规律但新参数/拓扑的程序化 twins 检查方法迁移。Replication track 可用
已知答案；discovery track 的最终 claim 必须在不可检索 confirmation world 或之后取得的独立数据上
成立。无法排除预训练记忆时，结论降级为“reconstruction/transfer”，不声称首次发现。

### E21. 环境观测与评分器反馈分离

为每条 agent-visible feedback 标注来源和现实可获得性：instrument/simulator observation、constraint/
solver diagnostic、peer-style critique、aggregate objective，或 truth-relative grader signal。主 science
condition 只开放前四类中任务现实允许的通道，sealed mechanism/robustness/false-discovery 分数永不回流。
另设 score-oracle condition 测“有评分器辅助时的可优化上界”，并报告 feedback payload 的 bit/字段
预算、提交次数和 target-reconstruction attack success。若提升只出现在 score-oracle condition，结论是
grader-assisted search，而不是从科学环境中学习。

## 5. 推荐的曲线与表格

主文可沿用 Frontier-Eng/EdgeBench 的时间或 oracle-budget best-so-far 图，但 science 论文至少再加：

1. `O/F/M/I/V/R/C` small multiples，显示同一轨迹的分歧；
2. development→sealed→confirmation slopegraph；
3. feedback/continuous/restart 的 paired gain curve；
4. proxy vs exact scatter + false-promotion 随时间曲线；
5. discovery/refusal confusion matrix（supported/null/misspecified）；
6. valid/timeout/protocol/numerical/safety failure cumulative incidence；
7. task×evidence-level heatmap，而非仅一列平均分；
8. cost frontier：quality 对 oracle calls、wall time、tokens、实验成本/能耗。
9. declared/terminal artifact 对 retrospective hidden envelope 的 selection-regret 曲线；
10. artifact/data/notebook/full-context 的 experience-channel ablation；
11. current-state regression、证伪和 recovery timeline；
12. elapsed/active/simulator/queue/API-outage 的 competing-time breakdown。
13. null-world false discovery 对累计 feedback/submission budget 的 sequential-risk 曲线；
14. autonomous-stop 与 forced-continuation 的收益、风险和成本曲线。
15. observation-only 与 truth-relative score-oracle 的 paired trajectory；
16. known-answer replication 与 procedural/prospective transfer 的 novelty matrix。

log-sigmoid 仅作为候选模型之一，与 log-linear、raw-time logistic、Gompertz、piecewise/change-point
和 hierarchical task-mixture 比较；必须用 held-out time forecasting、bootstrap over tasks 与跨 seed
复现证明，且明确它是 benchmark-population 规律，不是单个科学发现过程的普适定律。

## 6. 分阶段执行 TODO

### P0 — 当前证据闭环

- [x] Seismic 正式/欠定义报告分流，绑定 report/raw trajectory/candidate/parent hashes；
- [x] 把 information、mechanism、coverage、refusal 与 protocol failure 分轴；
- [x] clean revision `2706281` 生成 derived analysis、43-condition/22-task summary 和四类审计；
- [x] 全量回归 227/227，certification/security/baseline 刷新为 v33/v17/v23。

### P1 — Long-horizon pilot

- [ ] 增加 immutable publish manifest、原子 evaluator-only snapshots 与六类 event timestamps；
- [ ] checkpoint 同时报 current/declared/terminal/envelope，confirmation 只接收 declared artifact；
- [ ] 增加 elapsed/active/oracle-time summary、regression/recovery 和 failure-inclusive aggregation；
- [ ] 在目标模型运行前锁定 6 个代表任务：设计、逆问题、主动机制、随机优化、多保真、PDE；
- [ ] 每任务至少 3 seeds，运行 2h normal / open-loop / independent-restart pilot；
- [ ] 在 2 个任务先做 fresh/artifact/data/notebook/full-context 经验通道分解；
- [ ] 在 null worlds 扫描 feedback budget，验证 anytime-valid/one-shot confirmation 的错误率；
- [ ] 在 2 个任务比较 autonomous-stop 与 forced-horizon continuation；
- [ ] 把 agent-visible payload 分成现实观测和 truth-relative grader feedback，先跑 paired pilot；
- [ ] pilot 可按 headroom 分配后续工程资源，但 confirmatory cohort 不得据此删任务；
- [ ] 仅在 pilot 证明基础设施稳定且至少部分任务有 headroom 后扩展 6h/12h。

### P2 — 约 50 个 admissible tasks

- [ ] 先修 RankineCycleOpt、MOSFETDoping、RANSCalibration；
- [ ] 新增/重建任务按 `docs/task_expansion_v2_plan.md` 的 R2--R4 推进；
- [ ] 为约 50-task inventory 增加 author/reviewer effort、shortcut red-team 与
  `long-horizon-ready` maturity ledger；
- [ ] 为每个任务增加 known-answer/procedural/prospective provenance 和 novelty-risk 字段；
- [ ] 每个任务强制 E1--E3、E7--E9；主动/随机/多保真任务再分别强制 E2/E8/E5；
- [ ] 只有 admission DoD 全部通过才计数，目标从当前 34 提升到约 50。

### P3 — 统计与论文

- [ ] 预注册主要 estimand、失败口径、multiple-comparison 与 bootstrap unit；
- [ ] 独立重跑至少一个模型/agent harness，分离模型和脚手架效应；
- [ ] 生成向量曲线、evidence ladder、failure incidence 与 cost frontier；
- [ ] 最终论文把 simulator optimization、mechanism discovery 和 prospective validation 分层措辞。

## 7. 可核验来源

- Zhu, D. et al. (2026), *EdgeBench: Unveiling Scaling Laws of Learning from Real-World
  Environments*, arXiv:2607.05155v1, 2026-07-06. arXiv API、论文 PDF 与公开 dataset card 的题名、
  日期、作者、134/51 tasks、3×12h、约 38,000h 和 `R²=0.998` 已交叉核验。
- EdgeBench public dataset card and 51 task descriptors:
  `https://huggingface.co/datasets/ByteDance-Seed/EdgeBench`（2026-07-24 访问）。
- ByteDance-Seed/EdgeBench public SForge implementation, commit
  `a87350ab80eeb320b13cb71d1b0c3ffcc20a670f`（2026-07-24 核验）：官方 Codex 配置为
  12h、30min auto-eval、120s submission cooldown；公开文档说明 final best 包含不可见 auto-eval，
  `run_agent.py` 显示定时器直接打包 live workspace。这些实现事实用于 2.1/E11--E16 的协议审计，
  不代表官方作者对 Frontier-Science 的结论。

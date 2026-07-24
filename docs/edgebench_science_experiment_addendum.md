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
12. **目标函数和 incumbent 规则必须端到端一致**。公开 51-task contracts 中，37 个使用
    `score_first`、4 个 `valid_then_score`、1 个显式 `pass_rate_first`，另有 9 个依赖默认
    `pass_rate_first`。但 SForge 的通用 prompt 只说“所有提交中的 best score 是最终分”，容器内
    display cache 又只在 pass rate 上升时更新；authoritative judge 才执行 task-specific policy。
    visualizer 虽读取 `selection` 元数据，scanner 的 best 仍主要按 raw score direction 重算，run
    排序则优先 pass rate。对带 hard validity、robustness、mechanism 和 Pareto trade-off 的 science
    artifact，这不是显示小问题：agent、在线 selector、最终 endpoint 和论文图可能指向四个不同
    artifact。必须把 objective/direction/hard gates/material epsilon/tie-Pareto/commit policy 显式写入
    prompt 与事件，并用同一版本化 selector replay；任何环节 incumbent hash 不一致即 fail closed。
13. **摘要 history 不是可重放科学轨迹**。公开 `EvalReport` 本来含 `score_0_100`、runtime、timeout、
    `details`、`metrics` 和 `submitted_at`，但 judge-server run history 删除归一化分数，只保留
    score/pass-rate/counts/valid/summary；component metrics 和 failure/timing 只能事后再拼每个 submission
    目录。Science 需要 append-only、schema-versioned event ledger，绑定 artifact/report/evaluator hashes，
    并完整保存 raw vector metrics、实际返回给 agent 的 feedback projection、时间、成本、failure class、
    selector version 和 source revisions；论文 derived table 只能从该 ledger 和 hashed manifest 重建。
14. **固定间隔快照缺少边界哨兵**。公开实现等待一个完整 interval 后才做第一次 auto-eval，run 结束时
    先停止 auto-eval、再抽取 final archive，且不会自动把 terminal archive 送入同一路径评分。因此
    fixed-grid trajectory 不保证含 `t=0` baseline 或 terminal artifact，会偏置 first-valid、早期 gain、
    terminal regression、AUC 和 held-out-suffix forecast。必须强制捕获并计费 `t=0`、每个 scheduled
    checkpoint、每次显式 commit 和 cutoff terminal 四类 immutable sentinel artifact。
15. **agent resume 不等于实验 exactly-once recovery**。公开 judge server 把 session、submission counter、
    pending job 和 run history 保存在进程内存；agent 可自动续跑，但 judge 重启会成为独立故障域。对
    costly/stochastic science oracle，盲目 retry 会双花实验预算、重复使用证据或改变 winner。因此需
    durable write-ahead ledger，以 `artifact hash + evaluator manifest + seed/world panel` 为 idempotency key，
    恢复 counters/pending jobs，区分 retry 与 new evidence，并做 crash-injection exactly-once 测试。

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

EdgeBench 的 1M-context Opus 相对 200k 在 2h 已领先 5.8 分、到 12h 领先 4.4 分；这可靠地说明
model+context system 在整个窗口有 level advantage，但差距略缩小，不能单靠该图证明“长 context
让累计经验的学习斜率更快”。Context arm 应增加匹配 one-shot/first-valid baseline，比较 baseline-adjusted
gain、context×time interaction、证据记忆质量和新 instance transfer；若主要差异已在首次 checkpoint
出现，应优先解释为初始有效能力/状态容量，而不是 within-run learning-speed gain。

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

### E22. 联动 scientific campaign，而非孤立目录计数

EdgeBench 的 Borden/Cape Cod 任务把同一地下水系统拆成传感器故障诊断、污染源反演、监测网络和
pump-and-treat 决策。这提示我们至少建设一个可执行的端到端 campaign：
`data QC -> mechanism/inference -> experiment/monitoring design -> intervention`。每阶段用类型化、带
uncertainty/provenance 的 artifact 交接；既评分阶段局部质量，也评分最终 decision regret、安全和
false intervention。整条 campaign 按一个共享 lineage 做 holdout/bootstrap，不能把四个相关阶段当成
四个独立科学世界来放大样本量。

### E23. 从静态答案升级到 executable-method replay

发现/反演任务的最终 artifact 应同时包含可执行 preprocessing、实验选择、推断、uncertainty 和 claim
生成流程，而不只是某个 world 的拟合参数或 `answer.json`。权威 evaluator 在 fresh procedural worlds
上从原始观测重跑整条方法，并分别报告：静态答案正确率、workflow replay 成功率、method transfer、
claim--evidence consistency 和复算差异。只在一个隐藏目标上答对、但无法重放或迁移的方法，不算自主
科学发现。

### E24. Measurement-health 与 long-horizon-ready 门槛

EdgeBench 全量 science 表同时存在 100 分天花板、全模型 0 分地板，以及 SD 接近整个分数范围的 cell。
因此“看起来有 headroom”不足以分配 12h。每个 task--condition 先测 first-valid probability、weak
baseline 与 truth-blind reference 的间隔、固定 artifact 重评噪声、evaluator resolution、2h 后的 material
headroom、ceiling/floor mass 和 shortcut resistance。真实随机科学任务使用 common worlds/seeds 并按
pilot 方差增加重复；universal floor 或 evaluator noise 进入 reason-coded sampling ledger，但不进入
scaling-law 拟合。任务仍可科学有效而暂时不是 `long-horizon-ready`。

### E25. 每张汇总图绑定 cohort manifest

EdgeBench arXiv v1 源码的 task specification taxonomy 为 `36/39/19/13/19/8`，score-table taxonomy
却为 `35/34/16/13/24/12`；同一 134 个 task ID 中有 11 个换类，Science/ML 有 5 个被移到 Systems、
Optimization 或 Knowledge Work。至少对 Opus，34 个 score-table 显示行均值为 `48.494...`，四舍五入
得到 Table 2 的 Science `48.5`；加回 5 个换类显示行后为 `47.395`，即使给每行完整的一位小数舍入
区间也不可能得到 `48.5`。这不否定 134-task 总体曲线，但说明
family-level 结果不能只靠 prose category label 复现。

因此每个 curve/table 预先冻结并发布机器可读 manifest：`cohort_id`、task IDs、science track、
`lineage_id`、analysis role、权重、raw-to-report transform、run inclusion/failure policy、source revision 和
manifest hash。分析脚本若发现声明数量、task set、权重或 transform 不匹配必须 fail closed；taxonomy
变化作为显式 diff 发布，不能静默改变“science tasks”分母。
本次源码级映射与均值复算保存在
`.research/edgebench_taxonomy_audit_2026-07-24.json`。

### E26. Objective-selection contract replay

每个 task 的 agent-visible prompt、online incumbent、declared commit、terminal endpoint、dashboard 和
analysis table 必须引用同一个 versioned selection contract。Contract 至少含 raw objective direction、
validity/safety/confirmation gates、scientific materiality `epsilon`、constraint violation ordering、
Pareto/tie policy、随机任务的 expectation/quantile rule，以及允许进入 confirmation 的 endpoint policy。
在每个 event 上离线 replay selector，并逐项核对 incumbent artifact hash；任何 prompt/config/selector/
visualizer 分歧即使最终 scalar 相同也记为 protocol failure。另做 selector-sensitivity：score-first、
valid-then-score、lexicographic safety-first、material-Pareto 各自会选中多少不同 artifact，以及这些反转
如何影响 sealed/mechanism/false-discovery 结论。

### E27. 无损事件账本与 exactly-once 恢复

长期科学运行必须以 append-only ledger 为 source of truth，而不是依赖进程内 history、容器 display
cache 或可变 summary JSON。每条 evaluation event 绑定 immutable artifact、完整原始 evaluator report、
agent-visible feedback projection、world/seed panel、evaluator/container/source revisions、六类 event time、
token/tool/oracle/sample/energy cost、failure/retry lineage 和 selector decision。系统在 submission 接收前
写 durable intent，完成后原子 commit；重启时按 idempotency key 恢复或查询既有结果，不能静默重跑。
用 judge crash、work-container crash、network partition、late result 和重复 delivery 注入测试证明：预算
不丢不重、同一证据只计一次、stale feedback 不归因给错误 descendant、ledger replay 可字节级重建所有
headline tables。

### E28. 起点、提交、commit 与终点的 sentinel 快照

除固定间隔快照外，每个 run 强制记录：agent action 前的 `t=0` baseline、第一次 valid artifact、每个
agent submission、每次 signed commit/abstain、preregistered fixed-grid checkpoint 和 cutoff terminal。
所有 sentinel 都走相同 immutable capture/evaluator pipeline，且 terminal score 可以在 cutoff 后完成、
但其反馈不得回流。这样 first-attempt/first-valid gain、AUC、terminal regression、commit regret 和
observer envelope 都有共同边界；若某个 sentinel capture/judge 失败，作为 reason-coded missing outcome，
不能用邻近 best-so-far 值前向填充。

### E29. 评分粒度与任务顺序不变性

EdgeBench 的理论把 task score 写成许多带权 `score units`，其平滑极限要求大分值原子在聚合中不占
主导；正文报告“从 1 个任务到 134 个任务”时拟合误差随任务数下降，但论文/公开源码未报告不同
任务排列或子样本下的分布，因此尚不能把该图单独解释为与任务组成无关的样本量规律。Science evaluator
的分项拆法又常由作者决定：同一
机制恢复可以写成一个 40 分 gate，也可以拆成 40 个 1 分参数/世界指标。拆得更细会机械地降低跳跃、
提高曲线平滑度，却没有增加任何科学证据。

因此选择 3--4 个代表任务，在不改变 artifact、raw physical outcomes、hard gates 或总权重的前提下，
预注册 `coarse / canonical / fine` 三套等价 score partitions，离线重放同一批 sentinel-complete raw
trajectories。比较 improvement-event 数、最大 score atom、AUC、拟合优度、`Smax/tmid/beta`、模型排序和
held-out forecast；同时对 task accumulation 做大量随机排列、lineage-blocked permutation 和随机
subsample，而不是只展示一个任意前缀序列。只有科学结论对合理粒度与任务顺序稳定，才把总体曲线解释为
agent 学习规律；否则应报告 raw physical event / claim-state trajectory，并把平滑性标为 evaluator
construction effect。

### E30. 跨任务课程与科研经验迁移

EdgeBench 的 aggregate theorem 明确假设不同任务彼此不交互，而公开实验的 stateful 对照也只保留
同一个任务内部的状态。真实科研组却会把一个反问题、仪器或失败机制中学到的知识带到相关新课题。
这与 E12 的“同任务保留什么状态”不同，需要把 **任务顺序** 本身随机化并以目标任务为实验单位。

在同一 `lineage_id` 下构造 source→target procedural twins，并加入 unrelated-source 和 misleading-source
负对照；比较 target cold start、artifact-only warm start、只迁移原始 observation ledger、只迁移经审计的
hypothesis/evidence notebook、以及 full-state transfer。Source 与 target 的具体 world、最终答案和
confirmation panel 必须隔离，预算只从 target 首次 action 起计。主要结果为 target time-to-valid、early
AUC、最终 sealed/mechanism/false-discovery、adaptation/retraction delay 和 transfer half-life。进一步交叉
easy→hard、hard→easy、related→related、unrelated→target 的平衡顺序，区分真正的 scientific
meta-learning、artifact 复用、训练污染和错误假说负迁移。

### E31. 共享科研组合预算与机会成本

EdgeBench 给每个任务独立且几乎相同的长时预算，适合测单任务能力，却绕过了科研管理中的核心决定：
在多个候选假说、样品和实验并存时，下一单位 instrument/compute/human-review budget 应投在哪里，以及何时
放弃低价值线路。平均每任务曲线不能回答这个问题，甚至会奖励把昂贵预算均匀花在已饱和或无望的任务上。

建立一个小型 preregistered portfolio episode：同时给出 4--6 个 blinded candidate systems，包含有信号、
null、misspecified、cheap-proxy/high-fidelity 和不同潜在价值/安全风险的项目，共享一个 token、wall、
instrument、oracle 和 confirmation budget。比较 equal allocation、independent per-task budgets、random、
myopic expected-improvement、cost-aware VOI/knowledge-gradient 和 agent 自主 allocation。报告最终 validated
portfolio utility、discoveries per cost、false-discovery/unsafe exposure、regret against an offline
information-constrained oracle、starvation rate、time-to-drop 和 predicted value-of-information calibration。
所有被主动放弃的项目仍留在 intent-to-study 分母；不可让“只挑容易任务”提高平均分。

### E32. 非平稳、不可逆和乱序科学环境

EdgeBench 理论假设 attainable support 在拟合窗口内稳定、raw time 近似线性供给 search effort，而且不同
任务互不影响；公开 harness 的异步 judge 也主要把延迟视为吞吐问题。真实实验会有仪器漂移、样品老化/
耗尽、batch effects、不可逆干预、并行实验乱序完成以及安全边界。此时简单 retry、rollback 或把旧反馈
应用到当前 world state 都可能在科学上无效，即使软件 artifact 可以恢复。

在至少一个 active-mechanism task 和一个 physical-design task 增加 server-side hidden state：校准随时间
缓慢漂移、样品批次切换、一次 destructive measurement 消耗 specimen、某些 intervention 永久改变系统，
且 2--3 个实验以随机 latency 乱序返回。比较 stationary/reversible、drift-aware、fresh-sample、并行与串行
策略；要求 observation event 绑定 `world_state/sample_id/calibration_id/intervention_parent`，禁止跨状态
缓存复用和把不可逆实验当作可重试调用。报告 drift detection/recalibration delay、sample efficiency、
causal attribution、unsafe/invalid intervention、stale-result misuse、duplicate physical act 和最终 fresh-batch
confirmation。若 wall-time scaling 在 characteristic cycles/batches 下失效，改用样品/实验成本或 piecewise
event time，不强行解释为 log-time law。

### E33. Wall time、反馈时钟与实验时钟不变性

EdgeBench 把横轴定义为 elapsed interaction time，但其理论额外假设 raw time 近似线性供给 search effort。
公开 Codex 配置同时表明反馈机会并不完全同质：51 个公开任务中，44 个 agent submission cooldown 为
120 秒，3 个为 216 秒，D-ABIC 为 2160 秒，3 个文字冒险为 0；observer auto-eval 默认每 1800 秒一次。
因此一条按小时画出的总体曲线可能同时反映 agent 的搜索能力、judge 的反馈吞吐和实验本身的批处理节奏。
E4/F1 的 delayed-feedback 对照回答“反馈有没有因果价值”，这里进一步问“同一总信息在不同释放时刻下，
哪一个时钟才是可迁移的 scaling coordinate”。

在 2--3 个计算代价不同的任务上固定 active model/tool time、local simulator calls、权威反馈事件数、
反馈总字段/bit 预算和最终 confirmation budget，仅改变同一反馈 payload 的释放日程：即时均匀、稀疏均匀、
mini-batch burst、随机延迟和全部末端释放。分别以 wall time、active time、累计实验成本、累计反馈事件和
累计 revealed bits 重画 committed/sealed/mechanism 曲线，检验跨 cadence 的 curve collapse、排序和
held-out forecast。主要结果还包括 feedback-to-descendant latency、单位反馈的 material gain、批反馈后的
错误归因和 null-world false discovery。若曲线只在反馈事件轴而非 wall-time 轴对齐，结论应是
feedback-limited learning，而不是普适的 hour-based scaling law。

### E34. 对 latent task graph 做拓扑干预

EdgeBench 的 log-sigmoid 机制解释依赖 weighted cut mixing、近似自相似的 edge-difficulty 分布和稳定的
task graph；理论也明确预测 prerequisite chain、模块和 bottleneck 会产生平台、多拐点或 mixture，而不是
单一 sigmoid。目前的 E29 检验 score atoms，S1 检验 improvement hazard，但二者都没有直接操纵科学
问题的依赖拓扑，因而不能区分“曲线拟合得像”与“frontier-expansion 机制被验证”。

构造 answer-disjoint procedural twins，使 raw scientific outcomes、总权重、边际子问题难度、反馈容量、
oracle cost 和 reference-solver endpoint 尽量匹配，只改变可审计的依赖图：well-mixed/expander、串行链、
双模块单桥 bottleneck、层级/近自相似图。节点必须对应真实可重放的科学工作单元——例如 calibration、
辨识、干预测试和 shift validation——而不是只把同一 rubric 人为拆分。随机化节点命名并用经典方法校准
难度，避免语义提示泄露拓扑。比较 material-event hazard、路径顺序、平台/多拐点、跨模块 transfer、
committed sealed/mechanism 结果及 single/multistage/mixture 模型预测。再对 bridge availability 或一个
prerequisite observation 做预注册干预；只有曲线按理论方向发生可复现变化，才把 frontier graph 当作有
经验支持的机制，而非事后解释。

### E35. 研究问题形成，而不只是在给定目标上求解

EdgeBench 的任务都由作者预先给出目标、deliverable 和 judge；即便 agent 能长期优化，它仍未被要求决定
“什么问题值得问、怎样使问题可证伪、什么结果足以改变行动”。E31 的 portfolio 只在作者给定的项目间
分配预算，也没有覆盖开放的 question formulation。这是 scientific optimization 与 autonomous science
之间仍然缺少的一层。

在一个有多个潜在异常/机制的 rich procedural laboratory 中比较三种合同：固定研究问题、给定候选问题
菜单、开放问题形成。开放条件要求 agent 在新数据前签署 machine-readable preregistration：question、
hypothesis set、可辨识性判断、预期信息/决策价值、实验计划、证伪和停止标准；随后才获得共享实验预算。
程序化 evaluator 不以文风评分，而以 fresh worlds 上的 answerability、realized information gain、
下游 decision-regret reduction、confirmation、false discovery、trivial-question rate 和 preregistration
deviation 评分，并保留 null、不可辨识和高价值但困难的候选现象。只有开放条件能提出非平凡、可检验且
最终有确认价值的问题，才支持“研究议程形成”；在固定目标上提分仍只支持问题求解。

### E36. Starter、baseline 与错误科学先验的锚定效应

EdgeBench 为任务提供 workspace、文档和不同程度的 starter；公开 Borden 合同要求先运行 legal baseline，
D-ABIC 又直接指定论文、方法和比较路线。这样能降低 first-valid 失败，却也可能把长程轨迹变成围绕作者
先验的局部修补。K2 的 workflow-hint 消融关注文字是否指定方法，E36 单独检验初始 executable artifact
和其中隐含科学假说的路径依赖。

在同一 procedural worlds、接口、可见资料和预算下随机分配：空白但有 schema 的 scaffold、质量匹配的
中性 legal baseline、强但系统性错配的 baseline、强且方向正确的 baseline，以及两个相异 baseline
可选。错误 baseline 必须在 development 上具有迷惑性、在预注册 intervention/shift 上可证伪，并标记其
来源，不能暗含 hidden truth。报告 time-to-valid、探索 DAG/方法多样性、离开 parent basin 的时间、错误
假说存活与撤回延迟、sealed/mechanism/false-discovery、最终 artifact 与 starter 的结构距离。若强模型只
在正确 starter 下成功或长期继承错误机制，应将结果解释为 scaffold-conditioned adaptation，而不是独立
方法发现。

### E37. 原始测量到科学结论的误差传播

EdgeBench 明确排除主要难点来自视觉理解的任务，以避免 perception 混淆迭代推理；但其完整 Science/ML
设计说明又包含 sensor-fault diagnosis、dirty GNSS、ECG preprocessing、PDF evidence extraction 和
satellite-image active learning。这暴露了一个 science scope 边界：当前 Frontier-Science 多数任务直接把
干净的 simulator 数组或结构化 observation 交给 agent，尚未测量错误校准、漏检或错误特征是否会被下游
机制推断放大成高置信科学声明。E22 的 linked campaign 测阶段衔接；E37 单独随机化 **原始测量层**，
估计 measurement treatment 对最终结论的因果效应。

在一个可程序化复现的 instrument task 上比较四臂：oracle-clean features、冻结且质量已知的 reference
preprocessor、agent 自主 raw-data pipeline、以及带审计提示的 agent pipeline。原始输入注入 time jitter、
missing/censoring、baseline drift、unit/channel swaps、saturation、heteroscedastic noise 和“仪器故障 vs
真实异常”成对 worlds；同一 latent world 和 common noise seed 跨臂配对。提交物必须保留 calibration、
segmentation/event extraction、quality flags、feature uncertainty、mechanism/claim 和最终 decision。
分别报告 raw-event precision/recall、calibration error、uncertainty propagation、mechanism/confirmation、
false alarm/missed discovery、decision regret，以及 downstream success 在换回 oracle-clean features 后能否
恢复。只有从原始观测到 fresh confirmation 的整链条成立，才支持 instrument-facing autonomous science；
否则明确限定为 structured-observation benchmark。

### E38. 科学表示和单位的 metamorphic invariance

同一科学对象可用不同但等价的单位、坐标系、网格编号、传感器通道顺序、频谱表示和参数化描述。EdgeBench
的 task/score transforms 提醒我们 evaluator 表示会改变曲线，但 E29/S3 只改变 rubric 粒度与任务顺序，
没有检验 agent 的方法是否依赖表面编码。对真实科学方法，等价表示应给出等价的物理 claim、uncertainty
和 decision；仅在某个单位或列顺序上成功往往意味着 brittle implementation、memorized template 或 shortcut。

为 4--6 个任务生成保持 latent world 不变的 metamorphic twins：SI/CGS 或尺度换算、坐标平移/旋转/反射、
state-variable/网格 permutation、real-imaginary 与 magnitude-phase、频率/时间轴重采样，以及物理等价的
gauge/symmetry 参数化。Evaluator 先把 artifact 拉回 canonical physical space，再比较 feasibility、prediction、
mechanism equivalence class、uncertainty 和 selected intervention；同时加入外观相近但实际改变边界条件、
chirality、causal direction 或物性符号的非等价负对照，防止 invariant-by-ignoring-input。报告 pairwise
consistency、performance drop、claim contradiction、equivariance violation 和 negative-control sensitivity。
E38 应先作为便宜的 admission gate，再在 long-horizon pilot 中检查表示改变是否改变搜索路径和曲线结论。

### E39. 独立科研复核与群体错误相关性

EdgeBench 的主实验是一条 agent trajectory；它证明持续状态可能有价值，却没有检验多个独立研究者能否通过
盲复核降低相关错误。Science 中“多生成几个候选然后由 hidden score 选最好”不是 replication：若共享
starter、上下文和 grader，多个 agent 可能产生同一个错误机制；反之 evaluator 事后挑 winner 又引入 oracle
selection。E39 的 estimand 是独立证据生产与审查协议对 **错误相关性和可部署共识** 的影响。

固定总 token、tool、experiment、feedback 和 confirmation budget，比较：一个连续 agent；并行但共享
notebook 的分支；互不可见、starter/seed/corpus 尽量正交的独立 investigator；独立 investigator 后由
只见 claim--evidence bundles 的 blinded synthesizer 汇总；以及 generate--critic 共享上下文。团队必须在
fresh confirmation 前签署一个 claim/abstain 和 disagreement report，不能让 evaluator 从成员中事后选
最高分。报告 hypothesis/mechanism diversity、pairwise error correlation、independent convergence、minority
correctness、false consensus、synthesis calibration、validated utility per cost 和 confirmation success。
只有独立汇总相对等预算单 agent/共享上下文降低 false discovery，才支持“科研团队/多 agent”增益。

### E40. 未知下游效用下的方法复用与目标鲁棒性

EdgeBench 预先公开 objective、deliverable 和 judge；Frontier-Science 现有任务也多把一个 scalar 或固定权重
Pareto 目标交给搜索。这样测得的是对已知 rubric 的定向优化，不知道 agent 是否产生了可供不同科学决策者
复用的知识。S3 改写同一 rubric 的分项，P1 在已知项目价值下分配预算；E40 则把 **合理但未知的下游效用**
作为 sealed treatment，检验提交的是 transferable scientific method/Pareto set，还是只迎合一个公开权重。

在已有多目标任务上预先冻结一族 domain-valid utility functions（例如 efficiency/work/safety/cost，或
information/coverage/risk），比较三种合同：公开一个固定 scalar；公开 utility family 与约束但隐藏最终权重；
要求提交 calibrated response surface/Pareto archive/executable method，权重在 signed commit 后才抽取。
另设真正改变 scientific objective 的 announced-shift arm，避免把 goal ambiguity 与突发换题混为一谈。
主要结果是 sealed-utility regret、worst-case/CVaR regret、Pareto coverage、constraint/safety violations、
post-weight adaptation cost 和 method replay transfer。隐藏权重不得参与搜索、admission 或 snapshot selection；
若只有公开 scalar 臂成功，结论应是 evaluator-targeted optimization，而不是可复用科学知识。

### E41. 已知研究期限对策略的因果效应

EdgeBench 的 `@2h/@4h/.../@12h` 主表来自三条 12 小时长程运行的时间切片，而不是分别告知 agent
真实截止时间的独立 2/4/.../12 小时策略。这个口径适合描述“一条 12 小时政策走到各时点时有多强”，
但不能直接回答“只给 2 小时时 agent 会如何工作”。研究期限本身会改变探索、保守提交、实验并行、
停止以及为复核/confirmation 预留预算的策略；对 science 来说，前缀可比性尤其不是技术细节。

在 2--3 个既有 long-horizon-ready 任务上随机分配真实且明确披露的 `2h/6h/12h` 截止时间，并把每个
短期限 arm 与同一 task/world 下 12h-aware run 的匹配前缀比较；另加一个 server-side 预注册随机截断
arm，截断分布对 agent 公开但具体时点隐藏。固定单位时间/实验成本、工具、feedback policy、world panel
与 harness，只让 horizon knowledge 改变。主要结果为 exploration→confirmation 预算分配、前缀时点的
committed/sealed/mechanism/refusal、最后一次新假说与第一次复核的时间、confirmation reserve、停止质量、
`prefix regret = short-horizon terminal - long-horizon prefix` 及 task/model 排序反转。公开 51-task 表的
重算可作动机：2h 与 12h 的最高模型集合在 19/51 个任务上互不相交；这是展示 horizon-dependent
ranking 的描述性结果，不是 horizon treatment effect。只有独立 disclosed-horizon runs 才进入预算政策
结论；长程前缀继续作为部署过程的描述量。

### E42. 科学 judge 的校准、漂移与可替代性

EdgeBench 的公开 SForge 至少为 `college_english_exam_bank` 暴露可配置的 LLM grader：judge 容器由
`SFORGE_JUDGE_MODEL` 指定模型。任务镜像 hash 固定程序环境，但运行时 judge identity、endpoint、版本、
sampling/config 与响应未天然进入 task contract 的内容 hash 或公开 `run_config.json`。这不说明官方分数
发生变化，却说明任何 rubric/LLM-mediated science 评价都不能仅把 grader 当成无误差真值。当前 E7 的
独立 simulator 复算覆盖数值 oracle disagreement，但不覆盖评审者偏好、文风敏感性和 model drift。

凡开放问题、证据综合、报告或 claim-quality 需要 rubric/model judge 时，先冻结完整 judge manifest
（provider/model snapshot、prompt/rubric、sampling、tool/corpus、endpoint 日期与 response hash），再对一组
domain-expert anchor artifacts、精确重复、顺序随机化以及科学内容不变但 verbosity/style/citation-placement
改变的 metamorphic twins 做 blinded repeated scoring。至少与 deterministic executable outcomes 和一小组
独立专家 adjudication 交叉；报告固定 artifact repeatability、inter-judge agreement、anchor drift、style
sensitivity、模型/方法排序反转、可执行结果相关性与 adjudication rate。LLM judge 可作高吞吐辅评或反馈
treatment，但若主要科学结论只在单个可变 judge 上成立，应降级为 judge-specific rubric optimization；
confirmation、机制真值、单位/守恒/可行性和新实验结果仍由可执行或独立证据决定。

### E43. 自主请求外部反馈的校准与机会成本

EdgeBench 报告 effective-submission rate，并观察到更频繁提交不必然带来更高终分；但 submission 本身由
agent 在看过本地状态后内生选择。于是“有效提交比例”同时混合候选质量、何时请求 judge、反馈延迟、
cooldown 和任务难度，不能单独解释为学习效率。Science 中 authoritative loop 往往对应昂贵实验、
高保真计算、领域专家评审或破坏性测量；agent 不仅要利用反馈，还要判断 **何时值得买这一条反馈**。
E4/F1 识别反馈是否有用，S4 改变同一反馈的释放 cadence；E43 则识别自主 acquisition policy 的质量。

固定总 trusted-feedback/confirmation budget，比较 agent-requested、fixed-grid、随机、cost-aware VOI 和
end-only 五种请求策略；本地 simulator 与 active work budget 匹配。每次自主请求前，agent 必须签署
request card：当前假说/不确定性、想区分的问题、预测结果分布、预计 information/decision value、成本、
以及何种返回会改变下一步；请求结果只能用于其后 descendant。报告 predicted-vs-realized value
calibration、每单位成本的 sealed/mechanism gain、request timing regret、重复/升级调用、queue-induced stale
feedback、为一次性 confirmation 保留的预算、null-world false discovery 和最终 committed utility。若 agent
只靠高频询问 grader 提分而没有更好的 fresh confirmation，应称 evaluator querying，而不是科研判断力。

### E44. 早期 futility gate、随机续跑与 late-bloomer 偏差

E18/R3 问的是单条科研轨迹中的 agent 是否知道何时停止；这里问的是 benchmark 建造者或研究管理者在
看到 2h pilot 后，是否应继续给这个 task--condition 分配 6h/12h。二者不能共用一个 stopping estimand。
EdgeBench 的公开 51-task 表提供了直接动机：在先对每条展示序列做 cumulative-maximum 修复的保守
sensitivity 中，246 个六个 checkpoint 都存在且 2h→12h 总增益为正的 task--model cells 里，33 个
（13.4%）在同为四小时的 8h→12h 增益大于 2h→6h；其中 7 个在 2h→6h 只提升不超过 1 分，却在
6h→12h 至少提升 2 分。这是展示表上的描述性 delayed-takeoff 信号，不证明某种 continuation policy
更好，也不代表科学任务会有相同比例。

在预先锁定的 long-horizon-ready sampling frame 中，比较 fixed-12h、2h point-headroom gate、带最低
续跑概率的 randomized gate、以及使用 first-valid/噪声/不确定区间/科学事件的 uncertainty-aware futility
gate。固定总 task-hour 预算，并随机保留一个不受 2h 结果影响的 audit tranche 跑满 12h，使每个 cell 的
continuation probability 严格大于零；用 inverse-probability/doubly-robust sensitivity 重建全 sampling-frame
12h estimand。报告 task-hour 节省、late-bloomer recall、false-futility rate、12h committed sealed/mechanism
utility、continuation regret、模型排序与曲线参数偏差。Pilot 数据可以分配后续工程资源，但同一批早期
轨迹不能同时筛选 confirmatory cohort 并估计 headline 长程增益。

### M2 protocol gate. 固定 longitudinal risk set 与 envelope 单调性

论文将主量定义为 best-so-far，但公开 255 个 task--model 展示序列中有 6 条至少一次下降。由于原始
38,000h trajectory corpus 和 figure-analysis code 未公开，展示表本身无法区分 checkpoint 间 valid-run
集合变化、current-vs-envelope 口径、舍入/汇总或其他原因；这不是对官方结果错误的判定。它要求我们的
管线把如下不变量机器化：单运行、同 selector 的 observer envelope 必须逐事件非降；每个 checkpoint
绑定固定的 scheduled run IDs，并报告 scheduled/started/captured/judged/valid 数；任何 changing-risk-set
均值必须显式命名，不能标作同一 cohort 的 best-so-far。主曲线给 failure-inclusive ITT，另给固定 paired
completer sensitivity；current、terminal 和 current-claim 允许下降，但列名、artifact hash 与 envelope
严格分离。违反单运行单调性或无法重放 risk set 时，曲线分析 fail closed，而不是事后 cumulative-max
掩盖数据问题。

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
17. campaign stage-local score 到最终 decision-regret 的 error-propagation 图，并含 stage-swap
    counterfactual；
18. task measurement-health 图：first-valid、baseline/reference gap、judge noise、floor/ceiling、2h
    material headroom 与所需重复数。
19. objective-selector disagreement matrix：prompt/online/commit/terminal/dashboard/analysis 的 incumbent hash
    是否一致，以及不同 scientific selection policy 下的 sealed/mechanism reversal；
20. event-ledger completeness/recovery 图：scheduled→durably accepted→judged→feedback delivered→used，附
    duplicate/retry/crash/late-result 数和 exactly-once budget reconciliation；
21. sentinel-complete trajectory：明确标出 `t=0`、first-valid、agent submissions、signed commits、fixed-grid
    snapshots 和 terminal，禁止用 best-so-far 补齐缺失边界。
22. score-granularity/order robustness：同一 raw evidence 在 coarse/canonical/fine partitions 与 task
    permutations 下的曲线参数、排序和 forecast 分布；
23. source→target transfer matrix：cold/artifact/evidence-notebook/full-state 在 related/unrelated/misleading
    curricula 下的 target gain 与 negative-transfer；
24. shared-budget portfolio frontier：validated scientific utility 对 instrument/oracle/cost，附 starvation、
    false-discovery 和 allocation regret；
25. nonstationary laboratory timeline：sample/calibration/intervention lineage、乱序结果、漂移检测、不可逆
    行为和 fresh-batch confirmation。
26. feedback-clock collapse：同一反馈总量在不同 cadence 下，分别按 wall/active/experiment/event/bit
    时钟对齐后的曲线、排序与 forecast；
27. task-graph topology intervention：well-mixed/chain/modular/bottleneck twins 的 material-event hazard、
    多阶段曲线和 bridge-intervention 响应；
28. question-formulation frontier：fixed/menu/open contracts 下问题可辨识性、信息价值、fresh-confirmed
    decision utility、triviality 与 false discovery；
29. starter-prior anchoring matrix：blank/neutral/wrong/correct/diverse starters 下的 basin escape、机制撤回、
    探索多样性和 sealed transfer。
30. raw-measurement error cascade：calibration/extraction/QC 到 mechanism、confidence、confirmation 和 decision
    regret 的成对误差传播，并显示 oracle-clean feature rescue；
31. scientific-representation metamorphic matrix：单位/坐标/通道/网格/频谱等价 twins 的物理 claim 一致性，
    配合真正改变物理条件的 negative controls；
32. independent-team consensus panel：单 agent、共享分支、盲独立 investigators 与 blinded synthesis 的
    hypothesis diversity、错误相关性、false consensus、fresh confirmation 和 cost；
33. latent-utility robustness frontier：公开 scalar 与 sealed utility-family 权重下的 Pareto coverage、
    worst-case regret、post-weight adaptation cost 和安全约束。
34. horizon-policy matrix：独立披露的 2/6/12h runs 与 12h-aware matched prefixes 的探索/复核分配、
    prefix regret、停止质量与 task/model 排序反转。
35. judge-reliability panel：固定 anchors、重复件和 style/verbosity twins 跨 pinned judge manifests 的
    repeatability、agreement、drift、executable-outcome concordance 与 expert adjudication。
36. feedback-acquisition calibration：每次外部请求前预测与事后实际 information/decision value、单位成本
    收益、请求时机 regret、重复调用和未花掉的 confirmation reserve。
37. continuation-policy audit：fixed/randomized/headroom/uncertainty-aware gates 的 task-hour 节省、
    late-bloomer recall、false-futility、12h sealed utility 和选择后曲线偏差。
38. longitudinal risk-set audit：每个 checkpoint 的 scheduled→valid run flow、单运行 envelope
    单调性、ITT/paired-completer 敏感性与 changing-risk-set 告警。

log-sigmoid 仅作为候选模型之一，与 log-linear、raw-time logistic、Gompertz、piecewise/change-point
和 hierarchical task-mixture 比较；必须用 held-out time forecasting、bootstrap over tasks 与跨 seed
复现证明，且明确它是 benchmark-population 规律，不是单个科学发现过程的普适定律。

## 6. 分阶段执行 TODO

### P0 — 当前证据闭环

- [x] Seismic 正式/欠定义报告分流，绑定 report/raw trajectory/candidate/parent hashes；
- [x] 把 information、mechanism、coverage、refusal 与 protocol failure 分轴；
- [x] clean revision `2706281` 生成 derived analysis、43-condition/22-task summary 和四类审计；
- [x] clean revision `ce1cf4d` 生成 45-condition/23-task summary v16，并纳入可信 Rankine 正常条件；
- [x] 当前全量回归 244/244；clean revision `ec14510` 的 certification/security/baseline 刷新为
  v34/v18/v24。

### P1 — Long-horizon pilot

- [ ] 增加 immutable publish manifest、原子 evaluator-only snapshots 与六类 event timestamps；
- [ ] 增加 versioned objective-selection contract；prompt/online/commit/dashboard/analysis 用同一 selector，
  逐 event replay incumbent hash 并 fail closed on disagreement；
- [ ] 建立 append-only durable event ledger，保存完整 raw report、agent-visible projection、artifact/evaluator
  hashes、world/seed/cost/timing/failure/retry lineage；
- [ ] 强制 `t=0`、first-valid、每次 submission/commit、fixed-grid 与 terminal sentinel snapshots；
- [ ] 做 judge/work-container/network crash injection，验证 idempotent retry、exactly-once oracle budget 和
  stale/duplicate feedback lineage；
- [ ] checkpoint 同时报 current/declared/terminal/envelope，confirmation 只接收 declared artifact；
- [ ] 增加 elapsed/active/oracle-time summary、regression/recovery 和 failure-inclusive aggregation；
- [ ] 在目标模型运行前锁定 6 个代表任务：设计、逆问题、主动机制、随机优化、多保真、PDE；
- [ ] 每任务至少 3 seeds，运行 2h normal / open-loop / independent-restart pilot；
- [ ] 在 2 个任务先做 fresh/artifact/data/notebook/full-context 经验通道分解；
- [ ] 在 null worlds 扫描 feedback budget，验证 anytime-valid/one-shot confirmation 的错误率；
- [ ] 在 2 个任务比较 autonomous-stop 与 forced-horizon continuation；
- [ ] 把 agent-visible payload 分成现实观测和 truth-relative grader feedback，先跑 paired pilot；
- [ ] 在一个 procedural system 上跑 data-QC/inference/design/intervention linked-campaign pilot，并做
  baseline/agent stage-swap counterfactual；
- [ ] 在已有 sentinel raw trajectories 上离线做 coarse/canonical/fine score partition 与 task-order
  permutation audit；未通过前不解释曲线平滑性或 task-count scaling；
- [ ] 在一个同 lineage source→target pair 上做 cold/artifact/evidence-notebook/full-state transfer pilot，
  含 unrelated/misleading source 负对照；
- [ ] 实现一个 4--6 project 共享 instrument/oracle budget 的 portfolio episode，先比较 equal/random/
  cost-aware VOI，再测试 agent allocation；
- [ ] 在一个 active task 注入 calibration drift、sample depletion、irreversible intervention 与乱序结果，
  验证 world-state lineage、stale-result guard 和 fresh-batch confirmation；
- [ ] 在 2--3 个任务固定反馈总事件/bit 与 active budget，随机化 immediate/even/batched/jittered cadence，
  检验曲线究竟按 wall time、实验成本还是 feedback clock 对齐；
- [ ] 构造一个小型 well-mixed/chain/modular/bottleneck procedural-twin family，先验证 task-graph 拓扑干预
  是否按理论改变 material-event hazard 和曲线阶段，再讨论 frontier-expansion 机制；
- [ ] 在一个 instrument-facing task 随机化 oracle-clean/reference-preprocessed/agent-raw pipeline，配对注入
  calibration、missing/censoring、sensor-fault 与真实异常，量化测量误差到机制和决策的传播；
- [ ] 为 4--6 个 pilot tasks 生成单位/坐标/通道/网格等价 metamorphic twins 和非等价负对照，把表示不变性
  作为 admission gate，并检查 long-horizon 路径是否稳定；
- [ ] 在一个机制任务以等总预算比较 single/shared/independent investigators/blinded synthesis，final claim
  必须在 fresh confirmation 前由团队签署，禁止 post-hoc oracle winner selection；
- [ ] 在一个多目标任务隐藏 commit 后才抽取的 domain-valid utility weights，比较 fixed-scalar 与可复用
  Pareto/method artifact 的 sealed regret；
- [ ] 在 2--3 个任务随机分配真实披露的 2/6/12h horizon，并把独立短期限策略与 12h-aware matched
  prefixes 比较；另加隐藏具体截断时点的随机-censoring arm，报告 prefix regret、复核预算和排序反转；
- [ ] 对所有 rubric/LLM-mediated evaluator 固定完整 judge manifest，并用 blinded anchors、duplicates、
  science-content-equivalent style twins、第二 judge 与 expert/executable adjudication 先做可靠性门槛；
- [ ] 在 2 个 feedback-cost 异质任务比较 agent-requested/fixed-grid/random/VOI/end-only 请求策略；每次
  请求前冻结 request card，核对 predicted-realized value、timing regret 与 confirmation reserve；
- [ ] 对 pilot cells 先跑 measurement-health gate；任何 2h-based 续跑策略都保留一个随机
  audit tranche 无条件跑满 12h，比较 fixed/headroom/randomized/uncertainty-aware gates 的
  late-bloomer 漏检、continuation regret 与选择偏差；
- [ ] 将 M2 作为曲线硬门槛：固定 longitudinal run IDs，校验每条 observer envelope
  单调，发布 checkpoint risk-set flow，并同报 ITT 与 paired-completer sensitivity；
- [ ] 对选中的大跳变重放 parent/full-child/component-only/rollback，在同一 sealed panel
  上通过后才做“某科学思路导致增益”的因果归因；
- [ ] pilot 可按 headroom 分配后续工程资源，但 confirmatory cohort 不得据此删任务；
- [ ] 仅在 pilot 证明基础设施稳定且至少部分任务有 headroom 后扩展 6h/12h。

### P2 — 约 50 个 admissible tasks

- [x] RankineCycleOpt-v2 完成内部重建与独立 IF97 复算并进入 candidate；
- [ ] 继续修 MOSFETDoping、RANSCalibration；
- [ ] 新增/重建任务按 `docs/task_expansion_v2_plan.md` 的 R2--R4 推进；
- [ ] 为约 50-task inventory 增加 author/reviewer effort、shortcut red-team 与
  `long-horizon-ready` maturity ledger；
- [ ] 为每个任务增加 known-answer/procedural/prospective provenance 和 novelty-risk 字段；
- [ ] 对 discovery/inference 候选记录 starter provenance，并为一个 lineage 建立 blank/neutral/wrong/correct
  baseline 随机化版本，防止把 scaffold 锚定误写成方法发现；
- [ ] 增加一个可机器验证的 open-question procedural laboratory，区分 fixed question、candidate menu 和
  agent-formulated preregistered question；
- [ ] 优先新增一个 prospective evidence-synthesis task：程序化生成异质、重复、选择性报告与 publication-
  bias 文献集合，提交可执行 screening/extraction/meta-analysis/next-study method，并用 fresh prospective
  study confirmation；其统计 lineage 不与 source publications 重复计数；
- [ ] 为任务卡增加 `campaign_id/workflow_stage/lineage_id`，发现/反演任务提交可在 fresh world
  端到端重放的 method artifact；
- [ ] 为 admission、pilot、confirmatory 和每个论文 figure/table 冻结独立的 hashed cohort manifest；
- [ ] 每个任务强制 E1--E3、E7--E9；主动/随机/多保真任务再分别强制 E2/E8/E5；
- [ ] 只有 admission DoD 全部通过才计数，目标从当前 35 提升到约 50。

### P3 — 统计与论文

- [ ] 预注册主要 estimand、失败口径、multiple-comparison 与 bootstrap unit；
- [ ] 分析脚本校验 cohort/task-count/weight/transform/run-policy 与 manifest 完全一致；
- [ ] 将 scoring partition、task accumulation order、curriculum order 和 shared-budget allocation policy
  以及 feedback cadence、task-graph topology、starter arm、question-contract arm、disclosed horizon 和
  judge manifest 纳入 figure manifest 与 sensitivity report；
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
  12h、30min auto-eval；51-task 配置中 submission cooldown 为 44×120s、3×216s、1×2160s、3×0s。
  公开文档说明 final best 包含不可见 auto-eval，
  `run_agent.py` 显示定时器直接打包 live workspace。这些实现事实用于 2.1/E11--E16 的协议审计，
  不代表官方作者对 Frontier-Science 的结论。
- 51 个公开 task contracts 的 selection/parser/rescale census，以及 selection/prompt/history/visualizer/
  recovery 源码审计，保存于
  `.research/edgebench_contract_runtime_audit_2026-07-24.json`。截至 2026-07-24，arXiv/GitHub/Hugging
  Face 仍分别为 v1/`a87350a`/`47846a4`；这些是实现语义审计，不证明其影响了论文数值。
- EdgeBench arXiv v1 source package SHA-256
  `8193aeb41a3474690a40fac82e2ecbd53e651ab6b4759984b4c6845c04fbfd29`（2026-07-24
  下载核验）；taxonomy/count 差异来自源码中的 `task_by_task_specifications.tex` 与
  `category_score_tables.tex`，不是 PDF 文本提取推断。
- EdgeBench arXiv v1 `theory.tex` SHA-256
  `eaee62c9b5cf53fbd81b6b23b4053733bbfaa43a70140bd7fca47ba904c19be0`：E29--E32 所引用的
  finite score granularity、non-interacting tasks、stable attainable support、linear effort 与 characteristic
  feedback cycles，以及 E33--E34 所引用的 effort clock、weighted cut mixing、bottleneck/module failure
  modes，均来自该理论的明示假设/限制；E35--E36 来自固定任务合同与 starter/method guidance 的 scope
  差异。具体压力测试是 Frontier-Science 的推论，不是作者已做的实验或报告的结果。增量事实和 claim
  boundary 保存在 `.research/edgebench_science_third_order_audit_2026-07-24.json`。
- EdgeBench arXiv v1 `approach.tex` 与完整 Science/ML design notes 的 SHA-256 分别为
  `14cd29671b9cccccefc564aab1b053afbda585dd2fbfcd7c1573c053ff5eba74` 和
  `30b8556573c739f1120f15eb8dc56bea2bd55661f8a839e07a332dc4f6657df5`。视觉主导任务的显式排除、
  sensor-fault/dirty-GNSS/ECG/evidence-extraction/active-learning 任务范围，以及固定 objective/single-run
  scope 支撑 E37--E40 的问题边界；具体 treatment 是 Frontier-Science 提案，机器记录见
  `.research/edgebench_science_fourth_order_audit_2026-07-24.json`。
- EdgeBench v1 论文将 2--12h 主表定义为三条 12h trajectories 的时间切片；公开 README 的 51-task
  per-time table 在 2h 和 12h 的最高模型集合有 19/51 个任务互不相交。公开 SForge 还为一个 LLM-graded
  task 通过运行时 `SFORGE_JUDGE_MODEL` 配置 grader，而 `run_config.json` 不记录 judge manifest。这些
  source-level facts 只用于提出 E41--E43；它们不证明 horizon knowledge、judge choice 或 feedback-request
  policy 已改变官方结果。
  Source hashes、描述性重算与 claim boundary 保存在
  `.research/edgebench_science_fifth_order_audit_2026-07-24.json`。
- EdgeBench 公开 51-task 表的 delayed-takeoff 和单调性重算使用同一官方 README
  (`b58e38094f275b4f81bd31ec2b99014f345bcf6e65c5d6a0181a9c77a025c76a`)。展示表中 6/255
  序列下降；对序列做 cumulative-maximum 仅用于 late-bloomer sensitivity 后，246 个完整且
  总增益为正的 cell 中 33 个后段四小时增益大于前段，7 个呈现预定义的 delayed
  takeoff。原始轨迹/分析代码不可用，因此不对下降原因作官方口径外的推断。
  可重现记录与 claim boundary 保存在
  `.research/edgebench_science_sixth_order_audit_2026-07-24.json`。

# EdgeBench → Frontier-Science：长程学习实验增补

> 核验基线：ByteDance Seed, *EdgeBench: Unveiling Scaling Laws of Learning from
> Real-World Environments*, arXiv:2607.05155v1, 2026-07-06；公开数据集
> `ByteDance-Seed/EdgeBench`，2026-07-24 访问。不要与 2018/2024 年同名的
> edge-computing benchmarks 混淆。

## 1. 可以直接吸收的实验骨架

EdgeBench 的主要贡献不是某个科学 oracle，而是对长程 agent 学习的测量设计：134 个任务、
每个 task--model 三次独立 12 小时运行、约 38,000 小时交互，以及如下协议。

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

log-sigmoid 仅作为候选模型之一，与 log-linear、raw-time logistic、Gompertz、piecewise/change-point
和 hierarchical task-mixture 比较；必须用 held-out time forecasting、bootstrap over tasks 与跨 seed
复现证明，且明确它是 benchmark-population 规律，不是单个科学发现过程的普适定律。

## 6. 分阶段执行 TODO

### P0 — 当前证据闭环

- [x] Seismic 正式/欠定义报告分流，绑定 report/raw trajectory/candidate/parent hashes；
- [x] 把 information、mechanism、coverage、refusal 与 protocol failure 分轴；
- [ ] clean revision 生成 derived analysis、43-condition/22-task summary 和四类审计；
- [ ] 修正文档中的最终 revision、测试数和 report hashes。

### P1 — Long-horizon pilot

- [ ] 为 host-side evaluator-only fixed-interval snapshots 增加协议与测试；
- [ ] 增加 wall-time checkpoint summary 与 failure-inclusive aggregation；
- [ ] 选择 6 个代表任务：设计、逆问题、主动机制、随机优化、多保真、PDE；
- [ ] 每任务至少 3 seeds，运行 2h normal / open-loop / independent-restart pilot；
- [ ] 仅在 pilot 证明仍有持续 headroom 后扩展 6h/12h。

### P2 — 约 50 个 admissible tasks

- [ ] 先修 RankineCycleOpt、MOSFETDoping、RANSCalibration；
- [ ] 新增/重建任务按 `docs/task_expansion_v2_plan.md` 的 R2--R4 推进；
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

# 任务改进 TODO

日期 2026-08-09。依据：用户提出的七条要求、2026-08 文献调研、以及本轮实测出的缺口。
所有数字来自仓库内可核验 artifact。

---

## 一、用户提出的任务要求（原话归纳）

| # | 要求 | 出处 |
|---|---|---|
| U1 | 任务场景覆盖**所有科学场景** | 第一轮 |
| U2 | 形式分两种：**科学优化** 与 **科学发现** | 第一轮 |
| U3 | 评测科学场景下的 **agentic / RSI / self-evolving** 能力 | 第一轮 |
| U4 | **开放性任务、能持续优化**的任务 | 第一轮 |
| U5 | 对标 **AlphaFold / AlphaEvolve** 那一类 | 第一轮 |
| U6 | 题目要有**较好的实际科学背景** | 第二轮 |
| U7 | 题目要**符合 RSI 迭代自我提升主题** | 第二轮 |
| U8 | 题目要有**较好的评测方式** | 第二轮 |
| U9 | 任务要有**难度和区分度** | 第三轮 |

---

## 二、当前 61 个任务对这九条的达成度

| 要求 | 现状 | 证据 |
|---|---|---|
| U1 覆盖所有科学场景 | **部分**。7 学科 57 域，但 Engineering 占 18、Chemistry 13，而药物发现只有 1 个（新建）、量子只有 2 个、生物 6 个 | 学科分布实测 |
| U2 两种形式 | **未落地**。`scientific_role` 字段 0/61；约 18 个逆问题仍按"最大化单一标量"计分 | schema 扫描 |
| U3 测 RSI | **仅 2/61 测过**。Δ 只在两个新任务上测过 | 实验记录 |
| U4 开放/可持续优化 | **4/61 uncapped**，其余 clipped 在 1.0，测不了"超过人类记录" | metadata 扫描 |
| U5 对标 AlphaEvolve | **反例已实测**：certified 的 CirclePacking 被 OpenEvolve 3 次 oracle 调用解决（greedy 也到 0.999989） | E0 实验 |
| U6 实际科学背景 | **2/61** 的 oracle 用社区标准工具；**3/61** 用真实数据；**0/61** 过外部领域评审 | import 扫描 |
| U7 符合 RSI 主题 | **13 个 budget-1 就 ≥0.95**；约 18 个逆问题天然有正确答案、找到即封顶 | census |
| U8 评测方式 | **14 个 protocol blocked**（evaluator 中位数 808 行 vs near-ceiling 组 254 行） | census + 代码量 |
| U9 难度和区分度 | 50 个可评测任务里只有 **17 个**落在 difficult/discriminating 波段 | census |

波段分布：protocol blocked 14 / executable floor 6 / difficult 6 / discriminating 11 / near ceiling 13。

---

## 三、本轮实测新增的、文献里没有的判据

**开环饱和判据**（本轮从 Δ 预算扫描中导出）：

> 一个任务能测出迭代改进的程度，取决于它的**开环对照是否随预算饱和**。

实测支撑，同一搜索器同一模型：

| 任务 | 开环对照随预算 | 跨度 | 交叉点 |
|---|---|---:|---|
| MolecularLeadOptimization | 0.404 → 0.970，一路爬 | 0.565 | **budget ≈ 7.8 反超** |
| QuantumErrorDecoder | 0.747 → 0.845，budget 5 后平 | 0.122 | **budget 20 仍未反超** |

这条比 `Δ > 0` 好在三点：**只需跑单臂**（成本减半）、能解释两个任务的差异、给的是缺口持续存在的结构性理由。它直接服务 U4、U7、U9。

---

## 四、TODO（按性价比排序）

### P0 — 低成本、直接影响可信度

- [ ] **T1 用开环饱和扫全库**（服务 U4/U7/U9）
  对 50 个可评测任务各跑 `selection_blind` × budget {3, 10, 20} × 3 seed，画开环曲线。
  单臂，约 450 cell。产出：哪些任务的 best-of-N 会饱和 → 真正能测迭代改进的白名单。
  *这是唯一能一次性回答"61 个任务里到底有几个有 RSI 价值"的实验。*

- [ ] **T2 补 `scientific_role` 字段**（服务 U2）
  `optimization | discovery` 二选一，写进全部 61 个 metadata。纯 schema 改动。
  依据：约 18 个逆问题应归 discovery，其指标必须换成三元组（机制恢复 / 误设世界 FDR / 校准拒绝），不再最大化单一标量。

- [ ] **T3 加 impossible canary**（服务 U8）
  每个任务族一个物理无解目标或无机制 null 世界，显著 >0 即判 reward hacking。
  依据：ImpossibleBench (2510.20270)；robust-kbench (2509.14279) 记录了 kernel benchmark 被 eval 漏洞刷分。
  成本极低 —— 仓库多个任务已有 refusal 轴，只需提升为全库作弊探针。

- [ ] **T4 flagship 一律改 uncapped**（服务 U4/U5）
  当前 9 个 flagship 仍是 clipped。先例：RE-Bench 归一化 0=起始解、1=人类参考解、**明确允许 >1**；AlgoTune speedup 无上界。

### P1 — 中等成本、修掉最大的测量污染

- [ ] **T5 契约 linter**（服务 U8/U9）
  agent 可无限调用、只校验提交格式、不评科学、不耗 oracle 预算。分报"协议通过率"与"条件于通过的科学分"。
  依据：ABC checklist (2507.02825) 区分 task validity 与 **outcome validity**；实测 14/61 blocked，evaluator 中位数 808 行 vs 254 行，是契约复杂度不是科学难度。

- [ ] **T6 D 层 13 个 near-ceiling 重锚**（服务 U5/U9）
  把"标准方法一步可达的解析上界"换成**人类竞争记录的台阶**（值+年份+方法）。
  依据：Automated LLM Speedrunning Benchmark (2506.22419) 的逐记录台阶设计。
  实测反例：PoissonSolver2D/GateSynthesis/HartreeFockSCF budget-1 即 1.000。

- [ ] **T7 B 层逆问题换指标**（服务 U2/U7）
  约 18 个任务取消单一 maximize 的 `combined_score`，改三元组且永不平均。
  好消息：多数任务的 evaluator 已经算了 refusal / FDR / coverage 轴，改动主要在报告层。

### P2 — 高成本但决定长期价值

- [ ] **T8 程序化实例 + 难度旋钮**（服务 U4/U5，抗污染抗饱和）
  依据：Reasoning Gym (2505.24760) 的 100+ 生成器 + 算法化验证器 + 可调难度。
  **我新建的两个任务同样违反这条** —— QEC 用固定 (d,p)，Molecular 用固定药物面板和固定 profile。
  实测代价：CirclePacking 因没有难度旋钮，被种群搜索 3 步解决。

- [ ] **T9 提高社区 oracle 占比**（服务 U6）
  现状 2/61。可低成本迁移：`RNAInverseDesign` → ViennaRNA（现为 691 行自写热力学 DP）；`HartreeFockSCF` → PySCF（现为 672 行自写 RHF）；`SpinGlassGroundState` → Spin Glass Server 已知实例。
  关键可行性：oracle 跑在 trusted parent，加科学库**不触碰沙箱模型**。
  自写 oracle 保留的，必须补独立库交叉验证（模板：DiffractionGratingDesign 的 72 条件 grcwa 比对）。

- [ ] **T10 prospective / 时间留出实例**（服务 U5，抗污染）
  用模型 cutoff 之后才出现的记录做靶。依据：CASP 的 nature-sealed 性质；LiveBench (2406.19314) 的滚动刷新。
  当前污染风险最高：CapSet / CirclePacking / MatrixMultiplicationRank 正是 FunSearch / AlphaEvolve / ShinkaEvolve 的公开目标。

### P3 — 清理

- [ ] **T11 删除 9 个 quarantined**（服务 U9）
  9/9 材料缺陷已复现、0/9 达内部标准、evaluator 仅 36–70 行、Task.md 零引用。保留只让"61 个任务"这个数字虚高。

- [ ] **T12 补齐两个未建任务**（服务 U1/U6）
  `ProteinFitnessNavigation`（ProteinGym，卡在数据分发策略需要拍板）；`SymbolicRegression`（有界逆问题，按 T7 的逻辑应归 discovery 形式再建）。

---

## 五、与竞品的关系（决定哪些 TODO 不能省）

| 轴 | 占位者 | 对 TODO 的含义 |
|---|---|---|
| 对冻结 scorer 迭代优化 | **Frontier-Eng** (2604.12290)，造了 "generative optimization" 一词，47 任务、100 迭代 | 纯优化轴已被占，**T2/T7 的 discovery 形式是必须做的差异化** |
| 墙钟长跑 / 轨迹 scaling law | EdgeBench (2607.05155) | 不与之竞争，改用 token 对齐预算 |
| 跨 seed/数据集/规模泛化 | MLS-Bench (2605.08678) | 可借鉴为 sealed 层的第二指标 |
| 人类锚定 0→1 且可超 1 | RE-Bench (2411.15114) | **T4 的直接先例** |
| 单次尝试科学评测 | 上海 AI Lab：SFE / SGI-Bench / ResearchClawBench **全部 single-attempt** | 协议内给反馈这个位子空着，但 **T1 必须证明这些任务真能测出反馈价值**，否则占位无意义 |

另：MLR-Bench (2505.19955) 实测 coding agent 约 80% 产出伪造或无效结果而 LLM judge 照给高分 —— 这是冻结可执行 oracle 相对 rubric judge 的核心优势，也是 **T3 canary 必须做**的理由（自己的 oracle 也可能被刷）。

---

## 六、执行顺序建议

```
T1（开环饱和扫全库）
 ├─ 结果决定 T6/T7/T11 的具体名单
 └─ 与 T2/T3/T4 并行（纯 schema，互不阻塞）
        ↓
T5（契约 linter）→ 重测 14 个 blocked
        ↓
T8/T9/T10（重写 evaluator 级别的改造）
```

T1 是唯一的瓶颈节点：在知道"哪些任务的 best-of-N 会饱和"之前，T6 的重锚名单、T7 的改判名单、T11 的删除名单都定不下来。

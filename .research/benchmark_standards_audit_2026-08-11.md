# 任务是否符合 benchmark 标准

`scripts/audit_benchmark_standards.py`,对全部 61 个任务包逐条检查。

仓库原有两个审计:`audit_tasks.py` 查任务卡结构是否合法,`audit_task_maturity.py` 查证据是否 current 且绑定。两者都不问"这个任务本身好不好",这份补上。

## 九条标准

每条都可从任务包机械判定,不含主观打分,也不用难度当代理:

| 标准 | 含义 |
|---|---|
| oracle_is_community | evaluator 引入领域工具包(RDKit / Stim / PySCF…),而非用 NumPy 私自重实现科学 |
| anchor_recomputed | 参考值在评测时重算,而非写死为常量 |
| has_reference_record | 存在 `references/known_best.md`(uncapped 计分的必要条件) |
| has_sealed_split | evaluator 保留了不进开发分的 regime |
| declares_shortcuts | `known_shortcuts` 具体而非套话 |
| cites_literature | 卡片带可解析的 DOI / arXiv |
| states_invariants | 列出 oracle 必须满足的性质,使独立重实现可校验 |
| difficulty_parameterized | 有难度档位或程序化生成实例,饱和后不必整体报废 |
| domain_reviewed | 外部领域专家已签字 |

报告刻意不合成单一总分:这些是不同性质的缺陷,平均会把真正要紧的那个藏起来。

## 结果

| 标准 | 达标数 | 占比 |
|---|---:|---:|
| declares_shortcuts | 52 / 61 | 85% |
| states_invariants | 52 / 61 | 85% |
| cites_literature | 49 / 61 | 80% |
| has_sealed_split | 40 / 61 | 66% |
| anchor_recomputed | 8 / 61 | 13% |
| has_reference_record | 6 / 61 | 10% |
| oracle_is_community | 2 / 61 | 3% |
| difficulty_parameterized | 2 / 61 | 3% |
| domain_reviewed | 0 / 61 | 0% |

分布极不均匀,而且**弱的恰好是决定科学可信度的那几条**:文档层面(shortcuts、invariants、citations)普遍达标,科学根基层面(社区 oracle、可重算锚点、外部评审)几乎全线不达标。

只有两个任务达到 8/9(QuantumErrorDecoder、MolecularLeadOptimization),其余最高 5/9。这两个恰好是这轮新建的,不是巧合 —— 它们是按这些标准造出来的。

## 一个独立验证

得 0 分的九个任务是:ProstheticJointDesign、FlameSpeedOptimization、CzochralskiProcess、WaveguideModeSolver、StokesShapeDrag、TunnelSupportDesign、MultiEchelonStock、LaserCavityDesign、TrafficSignalTiming。

**它们恰好就是仓库里被隔离的那九个**,而这份审计完全不看 `certification.yaml`。两条独立路径给出同一个集合,说明隔离决定站得住,也说明这九条标准确实抓到了任务质量。

## 我在这份审计里自己犯的一个错

第一版 `domain_reviewed` 报出 17/61 达标。实际是 0 —— 全部 61 个 `review.domain` 取值都以 `pending_external` 开头,其中 17 个后面追加了领域名(`pending_external_photovoltaics`),我用精确匹配排除 `pending_external`,于是这 17 个漏了过去。

这类错误的方向总是一致的:**让 benchmark 看起来比实际更成熟**。已改为前缀匹配。

## 与准入判据交叉之后

`report_admission_criterion.py` 回答"任务能否测量迭代改进",这份回答"任务的科学根基是否扎实"。两者正交,一个任务可以两头都好、都差,或一头好一头差:

- QuantumErrorDecoder:标准 8/9,准入通过 —— 目前唯一两头都成立的任务。
- ProteinStabilityDesign / NMRSpectrumFitting / LowThrustTransfer:准入通过,但标准只有 4–5 分(oracle 是作者重实现、锚点未重算、无外部评审)。它们能测出反馈优势,但那个分数衡量的是"与作者 NumPy 代码的一致程度",不是与科学的一致程度。
- MolecularLeadOptimization:标准 8/9,但准入不通过(对照未耗尽,budget 7.8 交叉)。难度旋钮存在正是为此。

## 优先级

按"能改动多少个任务 × 单个改动的价值"排:

1. **oracle_is_community(3%)**。最根本的缺口。RNAInverseDesign → ViennaRNA、HartreeFockSCF → PySCF、SpinGlassGroundState → 已知实例集,是三个可做的改造,先前 T9 已识别但未执行。
2. **anchor_recomputed(13%)**。写死的常量无法校验,且会随库版本悄悄失效。改造成本比换 oracle 低。
3. **difficulty_parameterized(3%)**。当前 50 个任务饱和之后只能报废。T8 已在两个任务上验证了做法。
4. **domain_reviewed(0%)**。这条不是代码能解决的,需要外部人力,应当在对外发布前明确标注为未完成而不是留白。

## 边界

九条标准是我按这个 benchmark 自己的主张挑的,不是社区公认清单。`anchor_recomputed` 用的是启发式判定(verification/ 下多于一个 .py,或 normalization 文本含"recomputed/measured"),会有误判,应当视为筛查而非结论。`oracle_is_community` 按 AST 解析实际 import,不是子串匹配 —— 早先一次子串扫描曾把所有 evaluator 都报成用了 ASE,因为 "case"、"base"、"database" 里都有这三个字母。

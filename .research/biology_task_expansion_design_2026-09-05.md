# SLE 生物学任务扩展设计（2026-09-05）

状态：五个 candidate prototype 已注册；不构成认证、前沿难度结论或科学结果。

## 0. Review 后的实施决议

后续科学与饱和风险 review 推翻了原始 W1 排序。实际注册的五个 candidate prototype 是
MetabolicStrainDesign、BatchEffectDiscovery、MetagenomeCompositionAssignment、
FedBatchBioprocessDesign 和 PhylogeneticParsimonySearch。AllometricScalingLaw 因容易退化为固定
PGLS 配方且科学表述仍需重构，未注册；PerturbationEvidenceTriage 与 GeneNetworkIntervention 重叠，
DNABarcodeSetRecords 与 NonlinearCodeRecords 同问题类，二者也未注册。

“注册为 candidate”只表示 task 包、oracle、baseline、reference 和本地验证可运行，不表示已证明对前沿
搜索器有挑战。模型 draw、shortcut sweep、selection-blind 饱和、独立领域评审和 Linux 干净树证据仍是
后续认证门。

输入依据：用户提供的《SLE 生物学任务扩展调研（2026-09-05）》、当前 63-task
注册表、`CONTRIBUTING.md` 和现有 Biology task 包。本文把调研中的方向收紧成八个可实现的
task contract，其中五个进入第一实现波次，三个必须先通过专项预检。

## 1. 决策摘要

| 波次 | 稳定候选 ID | form / cell | 决策 | 主要理由 |
|---|---|---|---|---|
| W1 | `MetabolicEngineering/MetabolicStrainDesign` | optimization / engineering_design | 实现 | 填空格；LP oracle 便宜；设计产物与现有网络发现题边界清楚 |
| W1 | `Genomics/BatchEffectDiscovery` | discovery / evidence | 实现 | FDR 是原生科学目标；与现有 meta-analysis 和因果图题不同 |
| W1 | `Microbiology/MetagenomeCompositionAssignment` | discovery / substance | 实现 | 填空格；库内、不可分、库外三类世界自然 |
| W1 | `Bioprocess/FedBatchBioprocessDesign` | optimization / engineering_design | 实现 | 连续控制设计；可做尺度与菌株迁移；依赖仅 scipy |
| rejected | `EvolutionaryBiology/AllometricScalingLaw` | discovery / formula | 不实现 | 固定 PGLS 配方易饱和，且“发现律”表述需要重构 |
| W2 | `FunctionalGenomics/PerturbationEvidenceTriage` | discovery / evidence | 有条件实现 | 需先证明产物不是 `GeneNetworkIntervention` 的弱变体 |
| W1 | `Phylogenetics/PhylogeneticParsimonySearch` | optimization / combinatorial | 实现 prototype | verifier 干净；保留成熟启发式饱和风险作为认证阻断项 |
| W2 | `SyntheticBiology/DNABarcodeSetRecords` | optimization / combinatorial | 有条件实现 | 生化约束真实，但必须先排除与 `NonlinearCodeRecords` 同问题类 |

第一波次覆盖 Biology 的 engineering design、substance、原生 FDR evidence 和 combinatorial search。
两个 W2 方向不进入注册表；AllometricScalingLaw 在 review 后取消。

## 2. 统一设计规则

八题共同遵守以下契约：

1. task 包只含公开问题、候选接口和弱基线；真值、world label、held-out panel 和逐实例指标留在
   `verification/`。
2. procedural world 的随机数由 `(task_version, split, world_id, query)` 的稳定摘要派生，绝不依赖
   import 顺序或进程全局 RNG。
3. 每次候选调用使用独立进程和独立实验 ledger；重复、越界、非有限值和超预算一律 fail closed。
4. `combined_score` 只用于搜索选择。held-out、迁移、稳健性，以及 discovery 的机制、假发现、拒答、
   coverage 都是 evaluator-only。
5. optimization 的基线是弱但合法的固定设计；discovery 的基线是“自信地采用诱人但错误的方法”。
   discovery 的全面弃权与全面否认均归一化到 `combined_score = 0`。
6. reference 必须真值盲、能力完整但故意不打满；真值实现只用于 evaluator invariant，不作为可见参考。
7. 所有外部数据、纪录和许可在建包前从一手来源重新取得并记录摘要；本设计中的文献名只是核查目标。
8. 每题先过畸形候选、确定性、公开键文档、退化程序和低维捷径探针，再允许前沿模型 draw。

## 3. W1-1 `MetabolicStrainDesign`

### 分类与科学产物

- `scientific_role: optimization`
- taxonomy：`engineering_design`
- 候选交付的是敲除与培养基设计；评价问题是“设计有多好”，不是“真实代谢网络是什么”。即使求解中使用
  FBA、双层优化或网络分析，也不属于 discovery。
- 最近邻：`GeneNetworkIntervention` 恢复未知调控网络并在模型族外拒答；本题接受冻结的代谢网络为设计
  约束，不推断网络真值。

### 候选接口

```python
def design_strain(problem):
    return {
        "reaction_knockouts": ["R1", "R2"],
        "medium_uptake": {"EX_glc": 8.0},
    }
```

公开 `problem` 至少包含反应 ID、代谢物 ID、稀疏化学计量矩阵、上下界、gene-reaction 映射、允许敲除集、
最大敲除数、可调培养基、biomass reaction、product reaction 和数值容差。候选不得返回通量；通量由 oracle
重新求解。

### Oracle 与实例面板

对每个设计依次解三个确定性 LP：

1. 最大化生长，得到 `mu_star`；
2. 在 `mu >= mu_star - tolerance` 的最优生长面上最小化产物，得到最坏产量 `p_worst`；
3. 在固定最低生长率下最大化产物，用作偶联强度的辅助诊断。

development 使用核心碳代谢的多个碳源/产物对；held-out 更换碳源、目标产物和交换边界；sealed shifts
加入较紧敲除预算与通量上界扰动。网络与培养基均不由候选控制。

### 评分

先硬门控 `mu_star >= mu_min`、敲除数、交换反应和质量平衡。单实例 utility 使用
`p_worst * growth_coupling / intervention_cost` 的预注册单调变换。development utility 对固定合法基线和
真值盲 reference 线性归一化；`score_mode: uncapped`，超过 reference 保留 `> 1`。迁移与最差扰动单列，
不回流搜索。

### 基线、reference 与探针

- baseline：不敲除，使用默认培养基。
- reference：外层 beam search + knockout swap/TPE，内层使用上述最坏情形 LP；限制搜索次数以故意保留空间。
- shortcut probes：单敲除穷举、逐步 greedy knockout、只最大化名义产量、用任意 FBA 最优解偷取简并面。
- invariants：扩大允许通量域不能降低名义最优生长；oracle 对 reaction 顺序不敏感；最坏情形产量不高于
  同一生长面上的最好产量；删除候选声称的通量字段不改变评分。

### 实现预算与阻断项

仅需 `numpy/scipy.optimize.linprog`；目标单次评测小于 10 秒。实现前必须确认网络资产许可、从原始模型
重算 baseline/reference，并核查 OptKnock/RobustKnock 一手文献。若 greedy probe 达到 reference 的
95%，先加固实例，不进入模型标定。

## 4. W1-2 `BatchEffectDiscovery`

### 分类与科学产物

- `scientific_role: discovery`
- taxonomy：`evidence`
- 产物是哪些基因的条件效应得到证据支持，以及何时设计不可辨识；不是优化表达谱或恢复调控图。
- 最近邻：`ProspectiveMetaAnalysis` 处理研究注册、参与者血缘和跨研究异质性；本题处理同一组学实验内的
  高维多重检验、文库大小、批次混杂和补测设计。

### 候选接口

```python
def analyze_expression(problem, measure):
    # measure(batch_id, condition, replicate_count) -> count rows; charges samples
    return {
        "discoveries": [{"gene": "g17", "effect": 0.8, "confidence": 0.91}],
        "abstain": False,
        "reason_code": "supported",
    }
```

公开输入列出初始 count matrix、sample table、library sizes、batch/condition levels、候选 gene IDs、总补测
样本预算、每次最小/最大 replicate 数和合法 `reason_code`。补测只能选公开 batch × condition cell。

### 三类世界

1. `supported`：条件与批次部分交叉，存在稀疏真实响应；正确补齐设计后可恢复。
2. `nonidentifiable`：条件与批次完全共线，预算内不存在能形成对比的合法 cell，必须拒答。
3. `null_or_batch_only`：无条件效应，观察差异完全由批次和文库大小造成；宣称基因为假发现。

候选看不到 label；各类共享基因均值、离散度和边际 count 范围，防止按表面尺度识别世界。

### 评分轴

- supported mechanism：effect-sign-aware gene-set F1，加连续 effect error。
- false discovery：`FP / max(1, claimed)`，同时发布 `FP` 和 `claimed` 分母。
- calibrated refusal：不可辨识世界上的正确拒答和 supported 世界上的过度拒答分开。
- discovery coverage：supported 世界中至少提出一个非平凡 gene claim 的比例。
- experimental value：补测前后可辨识度/预测改善，单列。

`combined_score` 由 development 的逐世界科学效用相对 always-abstain 归一化，而不是直接平均上述四个
报告轴；全弃权和全盘否认恰好为 0。

### 基线、reference 与探针

- baseline：忽略 batch，对归一化均值做固定阈值差异并从不拒答。
- reference：设计矩阵秩检查 + 负二项/准似然近似 + shrinkage + BH 式 multiplicity control；优先补齐
  最大化条件正交性的 cell；故意限制 dispersion 模型。
- probes：总 count 阈值、固定 fold-change、忽略 batch 的 t-test、只看设计矩阵拒答、全弃权、全基因宣称。
- invariants：重新排列样本和 gene 不改变结果；复制同一测序行不等价于新增独立 replicate；完全共线
  设计的 condition coefficient 不可识别；null panel 中 oracle 真值 effect 全为零。

### 实现预算与阻断项

纯 `numpy/scipy`，冻结小型 count panels，目标小于 5 秒。若固定“batch-aware + BH”流水线在不做补测设计时
已达到 reference 的 95%，必须扩大低计数、异方差和近共线 panel，否则容易成为 on-ramp。

## 5. W1-3 `MetagenomeCompositionAssignment`

### 分类与科学产物

- `scientific_role: discovery`
- taxonomy：`substance`
- 输出回答混合物里有哪些 taxon/strain 及其丰度；库外或预算内不可辨识时拒绝过细归属。
- 最近邻 `CrowdedSpectrumAssignment` 处理连续谱线重叠和变焦；本题的观测是离散 marker/k-mer 计数，
  可辨识性来自参考矩阵的列空间与测序深度，而不是仪器分辨率。

### 候选接口

```python
def assign_composition(problem, sequence):
    # sequence(panel_id, read_budget) -> marker counts; charges reads
    return {
        "taxa": [{"taxon": "t4", "abundance": 0.31}],
        "ambiguous_groups": [["t7", "t8"]],
        "abstain": False,
    }
```

公开输入包括 reference taxa、marker IDs、reference detection matrix、初始 counts、合法 panel、总 read budget、
abundance tolerance、最低报告丰度和 library-adequacy 规则。

### 三类世界

1. `in_library_identifiable`：组成来自库内，预算足够时参考列可分。
2. `in_library_alias`：至少一组近缘株在所有可购买 panel/depth 下观测等价；应报告 ambiguous group，不能
   二选一。
3. `out_of_library`：主导成分含库外株，其残差方向不在非负参考锥内；应拒绝完整库内解释。

### 评分轴

- mechanism：taxon set precision/recall 先门控，再按匹配 taxon 的 abundance L1 给连续分。
- false discovery：错误的具体 taxon 指认数 / 具体指认总数；把 alias group 强行拆开计作假发现。
- refusal：库外世界拒绝完整解释，以及 alias 世界正确保留粒度。
- coverage：可辨世界中是否给出非空组成。
- read efficiency 和 held-out marker-panel transfer 单列。

全弃权归一化为 0；仅报一个包含整个参考库的 ambiguous group 也为 0，防止形式化“安全答案”。

### 基线、reference 与探针

- baseline：按单个最高 count marker 逐一指认 taxon，从不承认 alias 或库外。
- reference：panel-conditional constrained mixture fit + active marker-panel allocation + reference-cone residual test +
  null-space alias grouping；故意限制一次 refinement。
- probes：最近 reference column、unweighted NNLS、固定 top-k、只按总 reads 判拒答、永远报 genus-level group。
- invariants：taxon/marker 顺序不影响评分；同一 read budget 拆成重复相同 query 不凭空增加期望信息；完全相同
  reference columns 永远不能获得 strain-level credit；库外残差不能通过把全部 taxa 加入而消失。

### 实现预算与阻断项

纯 `numpy/scipy.optimize.nnls` 或 bounded least squares，目标小于 5 秒。建包前需从一手来源选择可再分发的
参考 marker 子集；若使用完全 procedural reference matrix，卡片必须明确不能把结果表述为真实宏基因组发现。

## 6. W1-4 `FedBatchBioprocessDesign`

### 分类与科学产物

- `scientific_role: optimization`
- taxonomy：`engineering_design`
- 产物是 feed profile 和 induction policy；动力学参数由题目给定，不要求辨识，因此不是 discovery。
- 最近邻 `DistillationColumnDesign` 是平衡级混合整数流程设计；本题是含生长、溢流代谢、氧传递和诱导负担的
  生物动力学控制。

### 候选接口

```python
def design_process(problem):
    return {
        "feed_knots": [{"time_h": 0.0, "rate_lph": 0.0}],
        "induction_time_h": 8.0,
        "harvest_time_h": 20.0,
    }
```

公开输入给定初始状态、罐体/通气参数、动力学方程、参数、feed 上界、最多 knot 数、终止时间、目标产物、
安全浓度和总 feed 约束。oracle 重新积分，不接受候选返回的轨迹或目标值。

### Oracle、评分与迁移

使用固定容差的 `solve_ivp`，并以独立固定步长积分实现作交叉 invariant。硬约束包括体积、溶氧、底物、乙酸、
feed slew 和终态活细胞量。主 utility 是可行条件下的 volumetric productivity，扣除 feed/运行时间；相对固定
合法基线与有预算的 direct-search reference 归一化，`score_mode: uncapped`。

development 覆盖两个名义菌株/罐体；held-out 更换 `mu_max`、产物负担和初始 inoculum；sealed shifts 更换
`kLa` scaling、氧传递上界与传感器偏差。报告 nominal、worst-shift feasibility、transfer 和 constraint margin，
只有 development nominal `combined_score` 可见。

### 基线、reference 与探针

- baseline：固定低速恒定进料，在固定时刻诱导和收获。
- reference：分段常数 feed 的多起点 differential evolution/SLSQP + shift-aware reranking；限制 knot 数和起点数。
- probes：恒定 feed 网格、指数 feed 两参数网格、只推迟诱导、只拉长收获、在约束边缘利用积分容差。
- invariants：零 feed 时质量守恒；负 feed 非法；加密积分网格不应改变排序；候选不能通过 NaN、瞬时脉冲或
  重复 knot 穿越约束。

### 实现预算与阻断项

仅依赖 scipy，目标单次评测小于 20 秒。若两参数指数 feed probe 达到 reference 的 90%，应增加多阶段诱导或
更强尺度迁移，而不是靠增加隐藏实例数量制造难度。

## 7. Rejected `AllometricScalingLaw`

### 分类与科学产物

- `scientific_role: discovery`
- taxonomy：`formula`
- 输出是候选标度律、指数和不确定性；关键不是“相关是否显著”，而是系统发育非独立下哪条律可辨。
- 与 `EnzymeKineticsLaw` 的差别：后者靠主动改变抑制剂区分动力学公式；本题靠选择系统发育对比并正确处理
  样本协方差，避免伪重复造成过度置信。

### 候选接口

```python
def infer_scaling(problem, measure):
    # measure(species_ids) -> trait rows; charges species
    return {
        "law": "power_3_4",  # power_2_3 | power_3_4 | fitted_power | segmented | unsupported
        "exponent": 0.75,
        "interval": [0.70, 0.80],
        "abstain": False,
    }
```

公开输入列出候选 species、系统发育树/协方差构造、已有测量、可新增物种、预算、候选 law IDs、区间格式和
trait measurement model。

### 三类世界

1. `supported`：全树共享 2/3、3/4、自由幂律或预注册分段律之一，跨 clade contrasts 可识别。
2. `phylogenetically_unresolved`：现有与可购买物种集中在少数近缘枝，候选指数在预算内不可区分，应拒答。
3. `out_of_family`：clade-specific exponent 或非幂律曲率，不应硬套一个全局指数。

各类共享质量范围、物种数和边际残差；不能从公开 species ID 或缺失模式猜 label。

### 评分轴

- mechanism：law classification，随后按 exponent/segment parameter error 连续评分。
- false discovery：unresolved/out-of-family 世界上宣称具体候选律。
- refusal：上述世界正确拒答，同时统计 supported over-refusal。
- calibration：区间覆盖与宽度分列；coverage 表示 supported 世界是否尝试具体发现。
- active design：购买物种形成的独立 phylogenetic contrast 数和 held-out clade prediction 单列。

`combined_score` 从逐世界机制效用相对全面弃权归一化；不能把窄但失覆盖的区间通过简单加分奖励。

### 基线、reference 与探针

- baseline：忽略系统发育，在 log-log 空间 OLS，选离 2/3 或 3/4 最近者并永不拒答。
- reference：PGLS/phylogenetic contrasts + condition-number-aware species acquisition + candidate-family comparison；
  故意使用近似协方差尺度而不是 oracle 真值。
- probes：OLS、按物种数阈值拒答、随机/最远质量物种采样、只比较 2/3 和 3/4、永远 fitted-power。
- invariants：在树叶顺序置换下不变；复制近缘物种不等价于独立样本；星形树极限应接近独立误差回归；
  out-of-family 的单一指数残差在 held-out clade 上系统偏移。

### 实现预算与阻断项

纯 `numpy/scipy`，小型固定树，目标小于 5 秒。建包前必须核查候选律与 PGLS 的一手文献，并避免把长期争论
简化成“3/4 对 2/3 哪个绝对正确”；任务只能声称在冻结 procedural worlds 中辨识预注册模型族。

## 8. W2-1 `PerturbationEvidenceTriage`

### 分类与边界

这是 discovery / evidence，不输出完整网络。候选只对一组预注册的“gene X 是否进入 pathway Y”声明进行
支持、反对或拒答，并提交支持该决定的确认实验 ledger。`GeneNetworkIntervention` 输出 signed network、动力学
参数和干预设计；若本题最终需要恢复多条边或权重矩阵，应取消建题而不是改名规避重叠。

### 最小合同

`triage_claims(problem, assay)` 可购买第二 guide、rescue、dose-response 和 batch-balanced replicate；返回
每条 claim 的 decision、confidence 和引用的 assay IDs。supported world 中 on-target signal 可由独立 guide 和
rescue 复现；off-target world 中 seed effect 跨多个靶点复现但 rescue 不成立；null world 无可归因信号。

机制/证据链正确性、false discovery、off-target refusal、coverage、预算效率和新批次确认分列。baseline 使用
单 guide 大效应即宣称；reference 使用 guide concordance、rescue 与剂量/批次交叉证据。

### Go/no-go

先写一个仅含公开 artifact schema 的 overlap audit，由维护者确认“单结论证据链”是值得独立评测的能力；再用
去掉所有 edge/weight 输出的 prototype 验证 reference。若 scorer 仍主要依赖隐藏网络边是否正确，则并回
`GeneNetworkIntervention`，不新增任务。

## 9. W1-5 `PhylogeneticParsimonySearch`

### 分类与合同

这是 optimization / combinatorial：比的是候选无根树的 Fitch/Sankoff 标量得分，不要求发现唯一真实进化树，
等分树也同分。接口 `build_tree(problem) -> Newick string`；oracle 独立解析 topology、拒绝重复/缺失 taxa，并按
冻结 alignment 和代价矩阵计分。

为降低公开成熟算法造成的饱和风险，首个 prototype 使用带缺失状态、重复 site compression 和至少一个加权
Sankoff panel，而不直接复制标准 DS1–DS8 题面。baseline 为固定 caterpillar/neighbor-joining tree；reference
为受限迭代次数的 stepwise addition + NNI/SPR/ratchet。score 按 baseline 到重新核实的最好已知/内部可重算
reference gap 做非负、uncapped 归一化；内部 NNI 探针必须能够超过平均连接法的 1.0 锚点，避免把改进截断。

### Go/no-go

在建完整 task 卡前完成：

1. Fitch 与独立实现逐 site 一致；
2. 小 taxa 穷举证明 scorer 正确；
3. baseline、简单 NNI、公开 ratchet-style probe、reference 形成非退化阶梯；
4. 前沿模型 budget-1 不达到 reference；
5. `selection_blind` 在预注册预算阶梯上先出现平台。

当前 procedural prototype 已注册为 candidate，但在第 4 或 5 条完成前不得认证。标准数据集分数在从原始
alignment 重算前不得写成归一化常量。

## 10. W2-3 `DNABarcodeSetRecords`

### 分类与合同

这是 optimization / combinatorial：产物是最大合法 barcode set。接口
`build_barcodes(problem) -> list[str]`；verifier 检查长度、字母表、GC 窗口、homopolymer 上限、候选间编辑
距离，以及序列与所有候选反向互补之间的距离。只评集合合法性和大小，不评构造方法。

baseline 使用短前缀固定的贪心集；reference 使用 reverse-complement orbit reduction、冲突图 independent-set
启发式和局部交换。捷径探针覆盖随机采样、lexicographic greedy、只检查 Hamming 距离、忽略 reverse
complement 和固定 GC template。

### Go/no-go

先与 `NonlinearCodeRecords` 做问题类审查。只有以下差异在消融中都有独立分值贡献才新增：编辑而非 Hamming
距离、反向互补约束、GC 窗口、homopolymer 约束。若最优策略仍等价于一般二元/四元码上的最大独立集且生化
约束不改变排序，则不新增；可改为现有码任务的 held-out variant。另需验证输出不包含可表达功能的序列，
实例只使用无功能随机 barcode 约束。

## 11. 实现顺序与验收矩阵

### 第一波次顺序

1. `BatchEffectDiscovery`：最便宜，先验证 discovery 三轴模板和原生 FDR。
2. `MetabolicStrainDesign`：补 engineering 空格，重点攻克 LP 最优面简并。
3. `MetagenomeCompositionAssignment`：补 substance 空格，先做 alias/out-of-library invariant。
4. `FedBatchBioprocessDesign`：复用成熟 optimization task 结构，做迁移和积分稳定性。
5. `PhylogeneticParsimonySearch`：先实现严格 verifier，再把成熟搜索器饱和作为认证门。

### 每题进入认证前的最低证据

| Gate | 必需产物 | 失败处置 |
|---|---|---|
| scope | 与 3–5 个仓库近邻及 Frontier-Eng/SciAgentArena/BioDesignBench 的逐项差异 | 重定义或取消 |
| oracle | 两个独立计算路径或小实例穷举交叉检查 | 不注册 |
| determinism | 同候选重复评测键和值一致，含换进程/换调用顺序 | 修复 RNG/求解器 |
| malformed | 至少十类坏候选都 `valid=0, combined_score=0`，evaluator 不崩 | 修复 fail-closed |
| contract | 所有公开输入/输出键在 `Task.md` 列出 | 补文档后再测 |
| baseline | 合法且归一化为 0 | 重做 normalization |
| reference | 真值盲、能力完整、分数显著高于各 shortcut | 加固实例或 reference |
| discovery | supported/null/misspecified，四列指标与分母完整；全弃权为 0 | 不注册 discovery |
| visibility | held-out/mechanism/refusal/robustness 不在 search-visible metrics | 修复泄漏 |
| model draw | 首提案有效但不到 reference；若无效先修合同，不称科学难 | 修接口或加固 |
| paired control | selection-blind 先饱和，normal 的增益随预算扩大 | 不晋级配对基准 |
| review | 独立领域审查 + evaluator/security 审查 | 保持 candidate |

## 12. 明确不做的方向

- 不新增 `mRNADesign`：现有 molecular design 已有三个生物学任务且 RNA 占两个。
- 不优先做 tracer/pharmacokinetic inversion：parameter inversion 已是全仓库最拥挤格。
- 不做功能增强蛋白、病原体或可表达毒性序列设计；当前八题的输出限制为分析结论、过程控制、敲除集合、
  拓扑或无功能 barcode。
- 不把 task 目录的出现当成完成。未实现 evaluator、reference、tests 和证据卡之前，设计只留在
  `.research/`，不修改 taxonomy、certification 或 `TASKS.md`。

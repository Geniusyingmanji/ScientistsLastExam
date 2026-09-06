# SLE 生物学任务扩展验证记录（2026-09-05）

> 本文为历史验证记录。按任务 PR 的范围要求，新增全局审计快照现仅本地保留，
> 不随 PR 提交；最终清单的审计由合并后的分支统一刷新。

分支：`biology-task-expansion-260905`

> 历史记录：本文数值与冻结证据对应修复前提交 997812c。后续 PR 评审复现了本文测试未覆盖的
> evaluator 崩溃、计分漏项和结构捷径；当前修复及数值见
> [PR 修复记录](biology_pr_repair_2026-09-05.md)。不要将下文原型结论当作当前版本的独立认证。

## 结论

五个任务已经达到 **candidate prototype 可运行** 标准：框架能发现和加载任务，公开合同、baseline、
reference、evaluator、held-out 指标和 fail-closed 行为都有可执行检查，弱基线均为合法 0 分，真值盲参考
均显著改善。

这不等于“已证明是前沿挑战题”。Linux 安全沙箱评测和干净提交上的冻结证据已完成；当前仍缺难度阶梯、
固定经典流水线与前沿模型饱和实验，以及独立领域评审。因此五题保持 `candidate`，没有自行认证。

## 实施范围与分类

| Task ID | form / subtype | 为什么这样分类 |
|---|---|---|
| `MetabolicEngineering/MetabolicStrainDesign` | optimization / engineering_design | 网络和动力学作为已知约束，候选交付反应敲除设计，按稳健产量优化 |
| `Genomics/BatchEffectDiscovery` | discovery / evidence | 候选从计数证据恢复条件效应，并在批次完全混杂时拒答 |
| `Microbiology/MetagenomeCompositionAssignment` | discovery / substance | 候选恢复混合物组成，并保留不可分 alias 或拒绝库外解释 |
| `Bioprocess/FedBatchBioprocessDesign` | optimization / engineering_design | 候选交付补料、诱导和收获策略，按最坏工况生产率优化 |
| `Phylogenetics/PhylogeneticParsimonySearch` | optimization / combinatorial | 目标是搜索更低 Fitch 代价的树，不声称该目标发现唯一真实历史 |

调研中的 `AllometricScalingLaw` 在 review 后取消：当前设计容易退化为固定 PGLS 配方，且“发现律”的科学
表述还不够稳固。`PerturbationEvidenceTriage` 与现有 `GeneNetworkIntervention` 重叠，
`DNABarcodeSetRecords` 与 `NonlinearCodeRecords` 同问题类，均未注册。

## 数值行为

以下是项目 `.venv` 中直接调用各 evaluator 的确定性结果。1.0 表示达到本题内部重算的 reference，
不是已证明全局最优，也不是外部 SOTA 声明；系统发育任务使用 uncapped 标尺，改进可超过 1。

| 任务 | baseline | reference development | reference held-out | 关键 discovery 轴 |
|---|---:|---:|---:|---|
| MetabolicStrainDesign | 0.000 | 1.000 | 1.000 | 整个近最优生长通量面上的最坏产量 |
| BatchEffectDiscovery | 0.000 | 0.926 | 0.969 | mechanism 0.896（含 effect 量级）；FDR 0；correct refusal 1.0；coverage 1.0 |
| MetagenomeCompositionAssignment | 0.000 | 0.903 | 0.959 | mechanism 0.903（含 abundance）；FDR 0；alias/library refusal 1.0；coverage 1.0 |
| FedBatchBioprocessDesign | 0.000 | 1.000 | 1.000 | 最坏生长/氧传递偏移下的可行生产率 |
| PhylogeneticParsimonySearch | 0.000 | 1.000 | 1.000 | 从 caterpillar 到重算聚类见证的代价缺口 |

系统发育的 truth-blind UPGMA+NNI headroom probe 在五个冻结 alignment 上都改进 reference，development
为 1.039、held-out 为 1.067。固定第一个发酵实例的策略跨实例仅得 0.250/0.000；固定取前四个允许反应的
代谢策略为 0.000/0.000。这些是针对公开实例捷径的可执行回归证据。

宏基因组 reference 的首次实现暴露出一个真实缺陷：把不同 marker panel 的条件计数直接相加会改变 panel
质量权重，导致 alias 世界误拒答。修正为 panel-conditional constrained mixture fit 后，development 从约
0.43 提升到原评分约 0.961/0.972；加入 exact-alias 与 abundance 评分并限制 panel 预算后，当前结果为
0.903/0.959，alias 与库外拒答均正确。该修复已进入 reference、
任务卡和锚点记录。

## 已通过的检查

- `tests/test_biology_task_expansion.py`：15/15。除 baseline/reference、确定性和畸形候选外，还覆盖错误
  effect、错误 reason code、过宽 alias、错误 abundance、panel 超预算、固定 knockout/发酵策略和 NNI headroom。
- 任务卡、taxonomy 与框架集成组合：22/22。
- 五次 `scripts/check_task_contribution.py --skip-eval`：全部通过；包括注册、必需文件、公开键、数值键、
  discovery `contract_lint` 文档和 candidate 状态。
- `scripts/audit_tasks.py`：执行检查通过，68/68 个任务卡通过，0 个缺失注册、孤儿或重复 ID；
  v74 报告绑定干净提交并标记为 trusted evidence。
- Linux ARM64 项目专用容器中的 `scripts/run_secure_baseline.py`：68/68 deterministic、68/68 valid、
  68/68 fail-closed，0 infrastructure failure；v57 报告为 trusted evidence。
- `scripts/audit_task_maturity.py`：68/68 任务通过 internal science admission，issues 为空；v15 报告为
  trusted evidence。
- `scripts/report_exam_taxonomy.py`：68 个任务，optimization 33、discovery 35，taxonomy issues 为空。
- `scripts/audit_benchmark_standards.py`：五题均满足 7/10 项；共同缺口是 community oracle 交叉验证、真实
  difficulty ladder 和 external domain review。
- `git diff --check` 与新增 Python 文件编译通过。

与本次更新直接相关的四组回归测试结果为 **40 passed、22 skipped**；整仓回归为
**822 passed、179 skipped**，无失败。跳过项是 macOS 上不可用的 Linux Bubblewrap 沙箱用例，它们已由
上述 Linux 安全基线实际执行覆盖。旧 Python 3.13 环境曾出现一个
SciPy 非中心 t 尾部数值失败，项目环境固定到 SciPy 1.11.4 后，该测试通过。

## 项目本地环境

环境位于 `.venv`，已由 `.gitignore` 排除；可复现依赖写在 `requirements-local.txt`。已实际导入：
NumPy 1.26.4、SciPy 1.11.4、PyYAML 6.0.3、pytest 8.4.2、ViennaRNA 2.7.2、RDKit 2024.03.5、
nmrsim 0.6.0、NetworkX 3.1、SymPy 1.13.3、QuTiP 4.7.6、Stim 1.13.0、PyMatching 2.4.0 和
Astropy 5.2.2。

```bash
/opt/homebrew/bin/python3.11 -m venv .venv
.venv/bin/python -m pip install -r requirements-local.txt
.venv/bin/python -m pytest -q
```

## 尚未完成的外部成熟度门

1. 目前是小型 deterministic procedural panel，证明了 scorer 有效，但没有证明对强模型有挑战。需要固定
   classical pipeline、shortcut ablation、budget ladder、selection-blind control 和多次 frontier-model draw。
2. 五题尚未接入领域 community toolkit 做独立 oracle 交叉验证，也没有代谢工程、统计遗传学、宏基因组、
   生物过程或系统发育专家签字。
3. 代谢和发酵仍是 clipped reference；本轮已经消除固定位置/固定策略捷径，但若强公开流水线达到 reference
   的 90–95%，仍应扩大科学机制和迁移维度，而不是仅增加隐藏随机种子。

因此当前准确结论是：**五个任务是真实科学问题的、可执行且非退化的候选实现，已通过 Linux 沙箱和内部科学准入；
它们是否达到 SLE 所需的前沿挑战强度仍待强基线/前沿模型标定和外部领域评审。**

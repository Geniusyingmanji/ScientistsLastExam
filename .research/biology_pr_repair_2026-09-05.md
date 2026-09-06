# 生物任务 PR 评审修复（2026-09-05）

> 本文为历史验证记录。按任务 PR 的范围要求，新增全局审计快照现仅本地保留，
> 不随 PR 提交；最终清单的审计由合并后的分支统一刷新。

本轮修复第一批五题的可复现问题；第二批五题只交付
[立项设计](biology_wave2_proposals_2026-09-05.md)，未新增注册或自我认证。

## 已修复的反例

| 问题 | 修复 | 可执行回归 |
|---|---|---|
| FedBatch 嵌套 feed 数组通过解析后打崩模拟 | 检查标量类型及 `(3,)` 形状；模拟异常进入无效零分分支 | 13 种错误 schedule，包括嵌套数组、布尔/字符串、非有限数和越界值 |
| Metagenome alias 世界漏罚 t3…t7 | 统计所有不被支持的具体物种；通过声明 precision 降低机制得分 | 对 reference 每个 alias 输出添加五个错误物种，FDR 与主分都变化 |
| 五题 run_eval.py 直接运行找不到 sle | 根据脚本绝对位置设置仓库 import 路径 | 清空 PYTHONPATH，用 `python -I` 从其他工作目录启动全部入口 |
| Metabolic 公开 `(0,-1)` 列规则满分 | 五个守恒池、能量消耗/供给与共享中间体旁路，保留最优生长面上的最坏产量 | 手写双旁路 LP 不变量；纯终端排放、耗还原力反应和固定位置策略探针 |
| Batch 全盘否认非零且样本数暴露世界类型 | 全部世界相同四行初始布局；有无效应世界相同 follow-up 菜单；归一化覆盖全部不发现策略 | 全弃权、全否认、布局拒答/否认均零；supported/null 公开布局一致 |
| 发现类跨进程末位分数漂移 | 对集合交集按排序顺序做浮点聚合 | PYTHONHASHSEED=1/2/7 下 baseline/reference 完整 JSON 一致 |
| FedBatch 题面缺少模型 | Task.md 公布状态单位、全部方程/常数、三种偏移、Euler 步长和事件约定、参考搜索及归一化 | 可按题面独立实现模拟；独立积分器交叉验证仍待完成 |

## 当前分数（内部开发诊断）

Linux x86_64 项目容器，Python 3.11 / NumPy 1.26.4 / SciPy 1.11.4。
直接调用仓库可信 baseline/reference 的结果；这些开发诊断不替代带 provenance 的全局冻结报告。
所有 baseline 都是合法的 combined_score=0；下表 reference 不代表外部 SOTA。

| 任务 | reference development combined_score | reference held-out |
|---|---:|---:|
| MetabolicStrainDesign | 1.000000 | 1.000000 normalized |
| BatchEffectDiscovery | 0.511369 | 0.655606 raw scientific utility |
| MetagenomeCompositionAssignment | 0.903336 | 0.959084 raw scientific utility |
| FedBatchBioprocessDesign | 1.000000 | 1.000000 normalized |
| PhylogeneticParsimonySearch | 1.000000 | 1.000000 normalized |

发现类 held-out 字段是未归一化 scientific utility，不能与 development combined_score 混为同一尺度。
Batch reference 在 unsupported 世界仍有 1 个错误声明，FDR=1/1；修复降低了原先过于乐观的数值，
没有通过抬高隐藏阈值来恢复旧分数。reference 改为平衡采样两个交叉单元，表达阈值仍为 0.55。

Metabolic：所有终端排放反应删除得 0/0，删除所有允许耗还原力反应得 0.822276/0.854729，
固定前四个反应得 0.157783/0。加入能量支路后，正确策略需要权衡保留有益能量供给和产量耦合。
**穷举仍满分**，本轮没有证明专家级难度，也没有完成系统性捷径搜索或 frontier draw。

Metagenome：额外错误物种探针把 combined_score 从 0.903336 降至 0.636460，held-out 从
0.959084 降至 0.725724；错误声明 10、声明分母 12、FDR=0.833333。

## 验证流程

新增反例均在 `tests/test_biology_task_expansion.py`，目前共 22 个测试。
静态及完整 `check_task_contribution.py` 五题均通过；五题入口在隔离 import 环境下均能启动，
BatchEffectDiscovery 的实际 run_eval.py 基线评测返回 valid=1、combined_score=0。
运行入口为当前项目的 `.venv/bin/sle-sandbox`（本机环境文件不提交）。

```bash
.venv/bin/sle-sandbox python -m pytest tests/test_biology_task_expansion.py -q -p no:cacheprovider
.venv/bin/sle-sandbox python scripts/refresh_global_evidence.py --commit
.venv/bin/sle-sandbox python -m pytest tests/ -q -p no:cacheprovider
```

历史验证记录仍保留，并明确标为旧版本；不要把旧报告中的 822 passed / 179 skipped 当成本轮结果。
刷新证据必须绑定本轮干净本地提交，不能只修改 JSON 中的哈希来伪装重新测量。

## PR 边界

本轮实现修复，不改变五题 candidate 状态。新增五题各有产物、oracle 草案、预算、最近邻、
强基线/捷径、原始文献及取消条件，但还没有实现。领域审查、系统性经典强基线与 frontier
标定是后续成熟度门；生成更多小型满分原型不能替代这些证据。


## 最终本机验证结果

修复提交 `30a1c4c`；证据刷新提交 `7d6cadb`、`4318dec`。
最终整仓测试分两组执行，选中集合互斥且覆盖所有 1008 个收集到的测试：

- 不依赖全局报告指针的 684 项：648 passed、36 skipped，526.92 秒。
- 报告、治理及其相关任务的 324 项：312 passed、12 skipped，574.25 秒。
- 合计：**960 passed、48 skipped、0 failed**。生物专项 22 项包含在第一组中。

第一组在基线复测期间运行，第二组在三份新证据及指针提交完成后运行；没有把一次中途停止的
初步全量运行计入上述结果。跳过用例保留仓库自己的条件，不通过修改 skip 或近似比较来消除失败。
本机测试不是 GitHub Actions 的 CI 结果；提交 PR 后仍需由主仓库工作流检查。

冻结证据（全部 `trusted_clean_revision`）：

- `experiments/task_certification_audit_2026-09-05_v75.json`：68/68 任务卡通过。
- `experiments/secure_baseline_determinism_2026-09-05_v58.json`：68/68 deterministic、68/68 valid、
  68/68 fail closed；infrastructure_failure_count=0。
- `experiments/task_maturity_audit_2026-09-05_v16.json`：68/68 internal science admission，issues=[]。

这些检查确认运行和记录完整性，不等于领域评审、前沿难度证明或 certified 准入。

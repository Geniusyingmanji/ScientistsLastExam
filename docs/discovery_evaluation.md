# Discovery：主张、过程证据与结果验证

发现的工作定义：在明确的新颖性范围内，通过可追溯的调查、推导或实验，对此前未确定的问题形成可检验的知识主张，并获得与主张类型匹配的验证支持。

本定义是 SLE 的评测约定。重发现可以测科学能力；它不自动等于领域新发现。优化也可能产生新的数学构造、方法或性能界，`optimization` / `discovery` 是任务组织方式，不是科学价值的互斥分类。

## 当前实现范围

- 注册表中每个 discovery 任务都有可生成的 profile；尚未审查者标记 `not_assessed`，不按名称或 kind 推断层级。
- 四个试点已静态检查，并在正式可信评测入口记录输入、callback 请求/返回/错误和最终提交：ForceFieldCalibration、InterventionalSCM、ActiveLawDiscovery、ProspectiveMetaAnalysis。
- 记录与逐世界 oracle 结果绑定，过程、结果、资源分组保存；未改变候选函数签名或现有分数公式。
- 可校验事件顺序、摘要、候选身份、callback 对应关系和记录完整性。摘要只提供内容绑定，不提供来源认证；正式证据仍需通过外层运行验证。
- 没有新增 LLM judge、过程综合分、自动领域新颖性判断或自动认证。实验是否有信息、推理是否有效、修复是否有用，仍需任务特定检查与对照实验。

四题的 profile 是 `source_inspected`，不是独立科学审核通过。所有认证状态继续来自 `sle/certification.yaml`。

## 能力档案

主张类型、开放度、验证方式、新颖性范围分别记录：

| 字段 | 含义 |
|---|---|
| `claim_types` | 参数、结构、规律、机制、预测、证据综合等主张 |
| `openness` | L1 已知模型内估计；L2 枚举解释辨别；L3 组合生成结构/规律；L4 实质扩展候选空间 |
| `given` / `unknown` | 题面已经给出的知识，以及真正需要求解的科学对象 |
| `verification` | 模拟真值、封存预测、预提交后的新确认、独立来源或证明路径 |
| `world_type` / `novelty_scope` | 模拟/真实来源及“新”是相对什么而言 |
| `source_sha256` | 本次 profile 引用的题面、任务卡、oracle 版本 |

L1–L4 描述开放度，不保证难度单调，也不代表证据强度。数学证明不需要先通过实验等级；统计关联、因果解释和领域新颖性分别验证。

```bash
python scripts/report_discovery_evidence.py --output /tmp/discovery_profiles.json
```

报告枚举全部 discovery 任务，并分别显示 `source_inspected` 和 `not_assessed`。科学问题与产物从 TASK_CARD 读取，属于任务声明，不能当作已确认的科学成果。

## 可信边界记录

`sle.secure_eval.trusted_evaluate` 为四个试点自动包装候选 RPC 接口。数据由 oracle 所在进程记录，候选的自述日志不会替换这些记录。

每个候选实例形成以下事件：

```text
input
callback_request -> callback_result | callback_error
... 可重复 ...
submission | candidate_error
```

`input` 保存候选实际收到的公开参数，callback 位置只保留工具名。请求参数在执行前快照，观测在返回候选前快照，最终提交在交给 oracle 验证前快照。NumPy 数组使用既有 RPC codec 保存 dtype、shape 和原始字节；可用 `sle.rpc_codec.decode` 读取，不执行记录中的代码。

ProspectiveMetaAnalysis 的 `confirm` 请求保留确认前提交，后续 observation 与最终 submission 分开保存。真正的提交合法性和不可变性仍由该题的 oracle 检查。请求被记录不代表确认成功，确认成功也不代表主张被证实。

ForceFieldCalibration 的请求包含其已有假说权重与保留集合，提交包含其已有 evidence IDs。SCM / ActiveLaw 当前只暴露实验决策和最终模型，未暴露中间假说，因此不得宣称已经检查了其全部假说更新。

观测与提交处在同一个实例不证明模型用了该观测。报告明确区分 `available_evidence_seq` 和未评估的证据使用质量。静态初始数据也属于可用证据，不按工具调用数量给奖励。

外层搜索轨迹记录 LLM 如何生成、选择候选程序；本记录描述生成程序在内层科学环境的行为。`candidate_sha256` 连接两者，不能把内层全部动作归因成 LLM 逐步推理。

## 结果与可见性

完整 metrics 中新增 `discovery_evidence`，包含身份、事件链、逐世界结果和完整性标记。它是 evaluator-only，既有 `search_visible_metrics` 白名单不会向搜索者暴露它。使用 task-local wrapper 时，仅在提供私有 `--full-metrics-dir` 后保存完整 metrics；公共 metrics 不含此字段。

逐世界结果保留原 split。SCM 是 `unsplit`，其封存干预是同一世界内的结果检验，不能改名为 heldout cohort。ActiveLaw 的 `validation` 和受信上下文的 `confirmation` 也保持原名。ProspectiveMetaAnalysis 的新研究是模拟确认，不是临床试验。

```bash
# 在可信 Linux 评测主机运行；输出文件必须放在搜索者不可读的位置。
python -m sle eval --task CausalDiscovery/InterventionalSCM --allow-uncertified \
  --candidate benchmarks/ComputerScience/InterventionalSCM/solution.py \
  > /private/operator/scm_full_metrics.json

python scripts/report_discovery_evidence.py \
  --metrics /private/operator/scm_full_metrics.json \
  --candidate benchmarks/ComputerScience/InterventionalSCM/solution.py \
  --output /private/operator/scm_discovery_report.json
```

`--candidate` 检查源码绑定，不提供身份认证。这个独立文件报告只输出 `structurally_consistent`；需要结合已有运行 manifest、evaluation ledger 与 `sle.run_verification` 判断是否是正式可信证据。没有记录的历史成绩标记 `not_recorded`，不倒推过程分。

原始结果指标分别放入 `process`、`result`、`resources`。过程组中若已有 lineage / acquisition 指标，仍是原 oracle 的诊断，不把它解释成经过跨学科校准的过程总分。无指标不补零。

结果正确性、预测质量、机制恢复、错误主张、拒答与覆盖仍须分开解释。经验错误比例不自动意味着理论 FDR 控制；分母和 split 遵循 TASK_CARD 的现有 metric contract，未完成的计数迁移仍是独立待办。

## 完整性、失败与限制

- 每个事件序号连续，引用前一个事件摘要；观测必须有此前匹配的请求，最终提交必须在 callback 完成后。
- 事件及整体摘要可发现意外修改，但可重算摘要的攻击者仍能伪造独立 JSON。不要把结构校验叫作来源认证。
- 记录有每次评估 32 MiB payload 与每实例 512 个事件的上限。超限或无法编码标为 `incomplete`，继续原科学评价；不能宣称完整过程证据。
- 候选 RPC 失败保留已记录的部分轨迹，公开失败分类保持不变。评测进程本身崩溃或启动失败可能无记录；这属于证据缺失，不能直接归因为模型造假。
- 当前结果绑定依赖 oracle 逐世界调用顺序与显式 split/world_index。接口或顺序变化需要同时更新适配器，并运行四题关联测试。
- 本轮给两个 oracle 补充逐世界身份字段，同时改变了共享 runtime；相应 package/runtime hashes 会变化，不自动签发历史版本等价关系。

## 后续准入与对照

下一步依次完成：四题主张语义与可辨识性审核；任务特定过程检查；独立 oracle 复核；主动/固定实验与有/无诊断重跑对照；再扩展到其余题。不能凭日志齐全就认证一个发现。

新增任务应在 TASK_CARD 明确未知量、主张、适用范围、竞争解释和验证路径；采用新主张接口或改变确认规则时发布科学新版本。没有修复机会的 Repair 是 N/A；有机会但没有完成应单独记录，不能当 N/A。

DiscoveryBench 的结构化主张提供了结果表达参考；TRACES 将过程与结果评审分开；SDABench 按不同科学主张的能力组织任务。这些工作启发本设计，并不意味着 SLE 的等级与它们等价。[DiscoveryBench](https://arxiv.org/abs/2407.01725)、[TRACES](https://www.apodex.com/blog/apodex-discovery)、[SDABench](https://arxiv.org/abs/2607.11079)。

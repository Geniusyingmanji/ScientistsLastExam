# T5 — 契约与科学的分离

两个交付：candidate 可在沙箱内调用的提交形状校验器，以及协议通过率与条件科学分的分离报告。

## 为什么需要

一个提交被拒的任务和一个科学上很难的任务都产出 0 分，budget-1 普查区分不了。实测支撑：协议失败任务的隐藏 evaluator 中位数 808 行，而饱和任务只有 254 行；最极端的一个要求九个精确命名字段带交叉一致性约束，模型全部提交无效 —— 那个 0 分说明不了模型是否懂科学。

## 交付一：`frontier_science/contract_lint.py`

candidate 可在沙箱内 `from frontier_science.contract_lint import ...`。已挂进沙箱只读挂载，与 `rpc_codec` 并列。

调用它不消耗 oracle 预算，也不泄漏任何东西 —— 每个检查都只关于形式，不碰分数、不碰隐藏世界、不碰参考值。

提供 `finite_array` / `binary_array` / `mapping` / `in_range` / `probabilities` / `sequence_of_str` / `explain`，全部返回 `(ok, reason)`，`reason` 说清楚具体错在哪（"expected shape (12000, 1), got (3, 3)"、"missing required keys: ['b']"），而不是一句 "invalid submission"。

沙箱内已验证可导入可用。

## 交付二：`scripts/report_protocol_vs_science.py`

对 52 个任务的开环轨迹（每个 12 个提案，共 624 个提案）分离报告：

```
protocol_pass_rate    有效提案 / 总提案
science_given_valid   仅在有效提案上的均值与最优
```

低通过率 + 高条件分 = 契约是障碍；高通过率 + 低条件分 = 科学确实难。

## 结果

契约受限（通过率 < 0.5）的有 10 个：

| 任务 | 通过率 | 失败构成 |
|---|---:|---|
| CalorimeterDesign | 0.00 | candidate_runtime_error ×12 |
| ForceFieldCalibration | 0.00 | candidate_runtime_error ×11 |
| ConvectionDiffusionOpt | 0.08 | candidate_runtime_error ×9 |
| OptimalPowerFlow | 0.17 | candidate_worker_exit ×10 |
| CatalystDeactivationLab | 0.25 | 未分类 ×8 |
| EnergyBalanceModel | 0.33 | 未分类 ×8 |
| GeneNetworkIntervention | 0.33 | callback_schema_error ×2, runtime_error ×3 |
| QuartzCrystalMicrobalanceLab | 0.33 | 未分类 ×8 |
| DistillationColumnDesign | 0.42 | candidate_timeout ×6 |
| HeatExchangerDesign | 0.42 | candidate_runtime_error ×6 |

全库失败构成：`candidate_runtime_error` 62、未分类 47、`candidate_timeout` 21、`candidate_worker_exit` 13、`candidate_callback_schema_error` 3、`blocked_or_missing_import` 3。

## 分离带来的判断

**`RadiativeTransferFit` 通过率 1.00 但条件科学分 0.0000。** 十二个提案全部被接受，全部得零分。这不是契约问题，是科学问题（或计分问题）—— 在只看总分的视角下它和 `CalorimeterDesign` 一样是"floor"，分离之后两者性质完全不同。

**`OptimalPowerFlow` 的失败是 `candidate_worker_exit`**，即候选进程直接退出，与"字段写错"是两回事，指向资源限制或段错误而非契约理解。

**`DistillationColumnDesign` 的失败主要是超时**，说明它的评测成本对候选不友好，和 QuantumErrorDecoder 早期遇到的问题同类。

## 一个自己的 bug

分离报告第一版把 149 次失败全标成"未分类"，我一度以为是仓库的失败分类没有落到轨迹里。实际上分类一直都在 —— 它位于每行的 `metrics` 载荷内，而不是行的顶层，是我的脚本读错了层级。仓库的仪器是完好的。

剩余 47 次"未分类"是真的没有 `candidate_failure_kind`，集中在 `CatalystDeactivationLab`、`EnergyBalanceModel`、`QuartzCrystalMicrobalanceLab` —— 这三个都是回调式 oracle，失败发生在回调协议层而非候选执行层，值得单独看。

## 边界

单 seed、budget 12、开环条件下的统计。通过率是对 `selection_blind` 提案而言的，反馈条件下可能不同（agent 看到失败反馈后有机会改正，这正是契约 linter 想提前解决的）。0.5 的阈值是本轮设定。

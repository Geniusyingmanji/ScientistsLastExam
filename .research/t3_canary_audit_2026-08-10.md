# T3 — 奖励攻击 canary 审计

`scripts/run_canary_audit.py`，2026-08-10，全部 61 个任务。

## 做法

ImpossibleBench 的思路落到仓库层：给每个 oracle 喂**按构造不可能挣到分**的候选，断言没有一个能挣到。动机是 robust-kbench 记录的事实 —— 冻结的本地 verifier 不等于安全的 verifier，被报出来的 kernel 加速有些来自 evaluator 漏洞而非 kernel。

六种探针：`raises`、`returns_none`、`returns_empty`、`returns_nan`、`returns_inf`、`returns_huge`。
判定"挣到分"= `valid == 1` 且 `combined_score > 0.05`。

## 结果

在基准参考环境（Linux，Python 3.8）：**61 个任务，0 个被标记，0 个 oracle 导入失败。**

没有任何退化候选从任何 oracle 挣到分。所有 oracle 要么显式拒绝（`valid=0`），要么以异常拒绝。

## 这个审计覆盖不到什么

必须写清楚，否则会被当成比实际更强的保证。

探针一律返回 `(8,3)` 形状的数组或空值，因此**大多数 oracle 是在形状检查这一关就拒绝的**。这证明的是"oracle 拒绝畸形输入"，而不是"oracle 无法被聪明的候选攻击"。真正的奖励攻击通常是**格式合法但语义作弊**的：命中评估器的固定 seed、利用截断边界、在随机任务上挑上尾、把不可行解伪装成可行。

所以本审计应读作**一阶健全性检查**，不是抗攻击证明。要覆盖二阶攻击需要任务感知的探针：
- 返回 baseline 自身输出（应得约 0，不应得高分）
- 形状合法但数值处在约束边界外 ε 处
- 对随机任务重复提交同一候选，检查是否被当作独立样本
- 直接返回锚点实现的输出（对已知锚点的任务）

## 顺带发现：一个 oracle 的锚点依赖优化器收敛行为

`PowerSystems/OptimalPowerFlow` 在 macOS（scipy 1.17.1）上**模块导入即失败**：

```
RuntimeError: reference DC-OPF failed: Positive directional derivative for linesearch
```

在基准环境（scipy 1.10.1）上正常。该 oracle 在模块级计算参考 DC-OPF 解作为归一化锚点，而这个解由 SLSQP 的收敛行为决定 —— 换一个 scipy 版本，锚点就可能算不出来。

这不是本次审计要找的东西，但它是同一类问题：**归一化锚点必须可复现，否则同一候选在不同环境下得分不同**。该任务的 `verification/requirements.txt` 应当 pin scipy，或者把参考解改成预计算并 hash 绑定的常量。

## 建议

1. 把 canary 审计接进 CI，与 security audit 并列。它跑完 61 个任务只需要几十秒。
2. 补任务感知的二阶探针（上面四条），特别是"重复提交同一候选"—— 对使用随机世界的任务，这直接检验是否存在上尾挑选漏洞。
3. 给 `OptimalPowerFlow` pin scipy 版本，或改为常量锚点。

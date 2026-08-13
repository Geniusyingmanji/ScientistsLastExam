# 契约负担:任务难在猜格式,不难在科学

基准自己写着一条硬约束:**契约复杂度不得成为难度轴** —— 因为"没猜中提交格式"拿的 0 分
和"科学做不出来"拿的 0 分无法区分。这条约束此前是从轶事推出来的
("协议失败的任务 evaluator 中位 808 行"),从没被测量过。

测了,而且它正在被违反。

## 测量

`scripts/report_contract_burden.py`,39 个有运行记录的任务:

**隐藏 evaluator 行数与提案有效率的秩相关 = −0.675。**

| | evaluator 行数 | 有效率 |
|---|---:|---:|
| SparseRecovery | 43 | 0.97 |
| CapSet | 68 | 0.92 |
| MultilayerThinFilm | 91 | 1.00 |
| ... | | |
| QuartzCrystalMicrobalanceLab | 1124 | 0.58 |
| CalorimeterDesign | 1264 | **0.00** |
| ForceFieldCalibration | 1541 | **0.05** |

## 根因不是长度本身,是没写下来的键名

CalorimeterDesign 拒绝了 36 个提案中的 36 个,而它**自带的 baseline 是有效的** ——
契约可满足,难的是改动解法而不破坏它。

但没有任何东西能查:账本只按哈希存候选、轨迹只存 label-blind 的失败类型,
而 `best_program.py` 在全拒时仍是 baseline。于是先补了保留机制
(每次运行留 5 份被拒候选,只写盘、不回流搜索),再跑一次,拿到真实异常:

```
File "runs/.../rejected/step_001.py", line 171, in _utility
    np.maximum(energies * sig * float(problem["light_yield_per_gev"]), 1e-30)
KeyError: 'light_yield_per_gev'
```

真实键名是 `light_yield_pe_per_active_gev`。模型伸手去拿一个**真实存在**的物理量,
名字猜错就崩。查下来:公开 `problem` 有 **27 个键,Task.md 只写了 15 个**。

## 全库审计

`scripts/audit_documented_keys.py`:从每个任务的 baseline 里 AST 抽出它读的
`problem["..."]`,查是否出现在 Task.md 或 constraints 里。

**7 / 15 个任务读了 prompt 从未提及的输入键,共 24 个。** 而且大多是**边界约束**:
`design_bounds`、`tube_count_bounds`、`depth_bounds_um`、`distillate_fraction_bounds`、
`source_position_bounds_m` —— 候选必须遵守却只能靠抄 baseline 才知道可行域。

这些任务和低有效率完全对应:DistillationColumnDesign 38%、ForceFieldCalibration 5%、
QuartzCrystalMicrobalanceLab 58%、HeatExchangerDesign 66%。

审计只看 baseline 读过的键,所以**系统性低估** —— baseline 碰巧没用到的键看不见。

## 修复与实测效果

给 7 个任务的 Task.md 补上"候选收到的输入"键表。**不动 evaluator、不动评分、不动科学。**
审计从 7/15 变成 0/15。

同一模型、同一预算重跑:

| 任务 | 修复前 有效率 / 最好分 | 修复后 |
|---|---|---|
| CalorimeterDesign | 0% / 0.0000 | **77% / 1.0000** |
| DistillationColumnDesign | 38% / 0.5822 | **29% / 0.9960** |
| ForceFieldCalibration | 5% / 0.0600 | **17% / 0.8288** |

CalorimeterDesign 从"没人交得出合法提交"变成打满锚点。它此前被列在"地板任务、需要重新标定"
里 —— 那个诊断是错的,它从来不是太难,是没告诉它输入叫什么。

## 边界与代价

**ForceFieldCalibration 部分修好。** 有效率只从 5% 升到 17%,但**落地的提案分数从 0.0600 升到 0.8288** ——
此前被读成"地板任务",实际是契约几乎不放行,放行的那些其实做得很好。
沙箱里报 `candidate_runtime_error`,但同一份被拒候选在沙箱外直接调用时干净返回 valid=0
(0.3 秒,不是超时;scipy 三个子模块在沙箱里都能导入)。这条差异未查清,单独记为待办。

**补文档改了 Task.md,而 Task.md 就是 prompt。** 冻结 cohort 的重绑工具因此
**拒绝**了 Diffraction、MOSFET、HeatExchanger 三个任务 —— 它们的冻结证据不再描述当前任务,
必须重新测量而不是重签。这是工具在正确工作,也是这次修复的真实代价。

**CalorimeterDesign 现在打到 1.0。** 按下线规则,如果所有模型都打满它就该退役。
目前只有一个模型一个 cohort 的证据,不足以判定。

## 一条更一般的教训

这个基准把大量精力花在"锚点是否够难"上,而实测下来,**在多个任务上占主导的难度来源
根本不是锚点,是提交契约**。−0.675 的相关不能证明因果,但 CalorimeterDesign 的
0% → 82% 是同一模型、同一预算、只改文档做出来的,机制也直接可见(KeyError 的键名)。

先量契约负担,再谈科学难度。

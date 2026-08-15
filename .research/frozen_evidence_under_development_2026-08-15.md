# 冻结证据与持续开发的冲突,以及一个可测的解法

同一个模式本轮出现了四次:改进一个 evaluator → 任务包哈希变 → 绑在这个任务上的**全部冻结证据
被拒**。而其中多数改进按构造不可能改变证据记录的任何数字。

## 四次

| 改动 | 性质 | 冻结证据是否真的失效 |
|---|---|---|
| 给全部任务卡加 `scientific_role` | 声明性注解 | 否 |
| 给 11 个任务补输入键表(改 Task.md) | prompt 改动 | 否 —— preflight 每项检查测的都是 evaluator |
| 新增 `verification/reference_*.py` | evaluator 从不 import | 否 |
| 新增 `references/known_best.md` | 文档 | 否 |
| **解封顶(改 evaluator)** | **行为改动** | **要测才知道** |

前四类已经在分类器里单独归类。第五类不能靠论证 —— 它确实改了 evaluator。

## 论证不够,要测

`scripts/check_evaluator_inert.py` 把冻结的固定产物分别跑过**冻结修订那版**和**当前版**的
evaluator,逐键比对两个指标字典。相同就说明这次改动没有移动这份证据记录的任何数字,
不同就说明证据必须重测,并指出是哪个指标动了。

它**不能**证明一次改动一般性地惰性 —— 只能证明它在这个任务的这份产物上没有移动任何东西,
而这恰好就是冻结证据本身声称的范围。

对冻结七任务的实测结果:

| 任务 | 结论 |
|---|---|
| RNAInverseDesign | **惰性**(21 个指标全同) |
| HeatExchangerDesign | **惰性**(15 个) |
| TrussWeightMinimization | **惰性**(11 个) |
| DiffractionGratingDesign | **变了**(`robustness_score`) |
| ElectrolyteConductivityDesign / MOSFETDoping / RANSCalibration | 未定(产物 import 了沙箱侧模块) |

一个必须说清的读法:比较的基准是**冻结修订**,那之后的全部改动都包含在内,不只解封顶。
所以"变了"的准确含义是"这份冻结证据已不再是同一个测量",而不是"解封顶改变了它"。
我一开始把 Diffraction 的差异读成了"稳健性分本来就超过 1.0 被压着",实测是 0.914,那个读法是错的。

## 结论

冻结 cohort 是**发布点**的快照机制,不是持续开发期的守卫。本轮两次把它做绿又两次弄脏,
说明正确的用法是:运行时与 evaluator 定稿 → 统一重测 → 一次性重绑。中途反复重绑是白做工。

在那之前,`check_evaluator_inert.py` 至少能把"必须重测"的范围从"所有改过 evaluator 的任务"
收窄到"实测确有指标移动的任务"。

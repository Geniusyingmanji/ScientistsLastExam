# 固定策略复验补充记录 — 2026-09-11

本记录补充已合并的 [框架 PR #81](https://github.com/Geniusyingmanji/ScientistsLastExam/pull/81)，不改动已合入 main 的运行时、任务或认证状态。五个投稿共执行 **36 次任务评测：32 次有效、4 次候选运行失败**；这是不同任务、不同固定计划的执行计数，不是可合并的性能样本。所有候选按事先固定的源码和参数运行，0 次模型调用。候选失败没有可用科学分数。

## 逐项结果

| 投稿 / 固定 task head | 本轮任务评测 | 主要观察 | 当前结论 |
|---|---:|---|---|
| [#60](https://github.com/Geniusyingmanji/ScientistsLastExam/pull/60) / `dbc2182268a44b26e383cc950457fd5f7d5aa8d1` | 6 有效 | 披露的 `(2,-3,-4)` 策略 development/heldout 为 0.481859 / 0.525816；reference 为 0.622081 / 0.793352 | 更强的历史 0.884294 策略仍缺原始源码/阈值，不能宣布已排除 |
| [#73](https://github.com/Geniusyingmanji/ScientistsLastExam/pull/73) / `c0d1f3e2419c4dc334587dcf1be4b9777bf632be` | 8 有效 | 固定代数默认策略为 0.744918 / 0.607955，公开 grid winner 为 0.754071 / 0.545685；reference 为 0.859392 / 0.743283 | 旧免费噪声 key 前提已消失；付费代数策略仍强，未证明任务难度 |
| [#74](https://github.com/Geniusyingmanji/ScientistsLastExam/pull/74) / `8193c5aa6abff91ff8cbbce9f617518ff3bb9b61` | 6 有效 | 公开固定 paired-grid 为 0.775136 / 0.814230；reference 为 0.785457 / 0.796773 | 未满足作者已声明的分离门槛；同为 16 付费 units，探针耗时更长，不能称为计算更便宜 |
| [#72](https://github.com/Geniusyingmanji/ScientistsLastExam/pull/72) / `8497bd455d3090087e6a15e99fb85f5fae75e5cd` | 8 有效 | 固定质量 57.8 为 0.290339 / 0.243942，公开四分类配置为 0.249535 / 0.130670；reference 为 0.548640 / 0.500013 | 两条固定策略明显低于 reference；不代表所有常量质量或廉价策略均已排除 |
| [#30](https://github.com/Geniusyingmanji/ScientistsLastExam/pull/30) / `90366563a7605e8f6eb6226200b1463615419b4a` | 原计划 4 有效、2 失败；独立后续 2 失败 | baseline 双跑 0，reference 双跑 0.459105；HiGHS helper 两次 `candidate_worker_exit`；只改 method 的 revised-simplex helper 两次 `candidate_runtime_error` | LP 比较仍 invalid/incomplete；失败哨兵不是分数，不能据此认定题目困难或 LP 数学方案无效 |

有效候选的成对完整指标均一致。各项 development/heldout 分数、FDR/refusal/coverage 分母和预算应在各自报告中阅读，不能跨任务直接平均。#30 是四个公开实例的 optimization 任务，不具有 discovery split。

## 来源与解释边界

- #60 使用集成提交 `68eac7248d30ca9a9f986cdfc4b4c07ee9cddf2e`，#73 使用 `bfd62be68723fa50e477eaca789a95989ab878ed`；两者共享早期运行时源摘要 `b8cf4421448c2cec02f18d094e37231fb49300fa6bc597d162424bb27620aac6`。#74/#72/#30 使用 `2660c38a413fb7281d0e7012a6446eb384a934d1`，运行时源摘要为 `8159a99d54894dd304e3ac48956cd05d4389f12a041f5d5d86a2c079641c2c86`。main 合并提交 `3069479717c2d0db0b040babb42390bdcbb60cb1` 与 `2660c38` 完整 Git tree 相同。后来的代码修复没有给早期实验重新签名。
- 五项均使用独立 Linux 沙箱、Python 3.8.10、NumPy 1.24.4、SciPy 1.10.1；没有改变原科学依赖。完整逐 world/instance 指标只在私有目录保留，公开材料包含聚合、候选/driver 源码与摘要。
- #74 精确复验作者公开的固定实现；更早的维护者原始实现仍缺失。#72 的 57.8 是从当前 reference 仅替换质量输出的忠实派生，并非缺失原探针的逐字副本。#30 使用当前 PR 中相关 SciPy helper；原 155 行纯标准库探针仍缺失。
- #72 已报告 SLE 的 mechanism、FDR、refusal 三轴与 coverage。独立参数恢复/预测分解缺失是额外科学解释的限制，不是缺少框架三轴。#74 的 oracle 将 false claims 除以 unsupported catalogs，分母不同于以全部 positive claims 为分母的 FDR，跨任务报告必须显式区分。
- #30 另做 16 次不含任务数据的沙箱 micro RPC，其中有 10 次固定微型 LP 求解尝试、0 次任务评测；不计入上表 36 次。微型 revised-simplex 成功不能代替完整候选验收。HiGHS native exit 的精确根因尚未确定，未放宽沙箱。
- 原始失败记录、第一次 driver preflight 和固定计划均保留；每个后续计划有独立候选摘要和输出目录，没有删除失败或追加参数搜索来挑选结果。

原件与复现细节：[PR60](pr60_shortcut_review_2026-09-11.md)、[PR73](pr73_shortcut_review_2026-09-11.md)、[PR74](pr74_shortcut_review_2026-09-11.md)、[PR72](pr72_shortcut_review_2026-09-11.md)、[PR30 原计划](pr30_shortcut_review_2026-09-11.md)、[LP 工程诊断](pr30_lp_compatibility_2026-09-11.md)、[独立 simplex 后续](pr30_simplex_review_2026-09-11.md)。

## 投稿队列与剩余工作

GitHub 在 2026-09-11 05:51 UTC 的最新核对为 **33 个 open PR**。#37/#66/#69 已随 #81 合并；上表五个投稿 head 未变化，仍保持 open。原 [35 项固定 head 快照](pr_intake_queue_2026-09-11.md) 保留其采集时状态，不改写历史。

新增 [#82：CacheReplacementPolicyID](https://github.com/Geniusyingmanji/ScientistsLastExam/pull/82)，head `e541403ec53421d88d05c15e2bef218fa06bf31c`，尚未审查。其完整标题是 “task: ComputerArchitecture/CacheReplacementPolicyID, identify a cache set's replacement policy from noisy hit and miss runs”。

下一批先补齐 #60/#30 等原始探针、处理 #74 的分离问题与 #30 的候选兼容性，再按已有队列复验 #11/#26/#71/#20/#27；同时推进 85 个旧任务的 shortcut 合同迁移。每项任务仍需独立模型标定、反馈配对和外部科学审查。当前记录不提升任何投稿的准入状态，也不启动正式长时模型测量。

# PR #72：固定策略的独立 Linux 沙箱复验

日期：2026-09-11。任务为 `ParticlePhysics/DarkMatterRecoilAttribution`，物理路径为 `benchmarks/Physics/DarkMatterRecoilAttribution`。本轮只复验事先已披露的两种策略，加 baseline/reference 各双跑；总计划 **8 次 `evaluate_candidate`、0 次模型调用、0 次新参数搜索**。这是固定策略诊断，不是独立模型标定、全面捷径排除或科学准入。

## 固定来源与环境

- task head：[`8497bd455d3090087e6a15e99fb85f5fae75e5cd`](https://github.com/Geniusyingmanji/ScientistsLastExam/commit/8497bd455d3090087e6a15e99fb85f5fae75e5cd)。15 个任务文件逐字导出，逐文件 hash 见 `pr72_task_sources_2026-09-11.json`。
- runtime head：`2660c38a413fb7281d0e7012a6446eb384a934d1`；runtime source SHA-256：`8159a99d54894dd304e3ac48956cd05d4389f12a041f5d5d86a2c079641c2c86`。用当前集成版本的 `load_task_spec` 与 `evaluate_candidate`，不执行 PR 自带旧 runtime/wrapper。
- 独立 g450 worktree：`/home/azureuser/workspace-gzy/zyf/sle-pr72-audit-20260911`。`ParticlePhysics → Physics` 已存在于固定 runtime，driver 显式核对该映射与完整 logical ID，没有修改 taxonomy 文件或推断 logical ID。
- 系统 `/usr/bin/python3` 3.8.10、NumPy 1.24.4、SciPy 1.10.1；OPENBLAS/OMP/MKL/NUMEXPR 均为 1。每次评测 timeout 300 秒，oracle 每 world 的实验预算为 12 units。
- 候选冻结于本地提交 `d58942aca44ba4d128af69a3d6c3096b866e5201`；driver 的已有 taxonomy 核验修正为 `4643d2c8972e8e40ed8028eb34916426f071b773`。首次 preflight 因错误要求映射必须缺失而在任何 `evaluate_candidate` 之前退出（0 次评测），原日志独立保留。候选源码与参数没有变化。

## 固定候选

| 候选 | 来源与修改范围 | SHA-256 |
|---|---|---|
| baseline | head 原始 `solution.py` | `aee48d712ad9a1a4ac557e1b9805714f607af28da1e214d322367c0b99642070` |
| reference | head 原始 `verification/reference_profile.py` | `78da166c44b216e3f69a492ba1a4aa605af0cc21d3223f2168196a9d68325d2c` |
| fixed_mass_57_8 | 整份 reference 只替换最终正信号返回中的 `"mass_gev": best[2]` 为 `"mass_gev": 57.8`；实验分配、拟合、none/abstain/law 决策均不改 | `7dde497168dee1d28b203be29db0731a94d034fded5358f5bda072624f2c502e` |
| published_four_way_probe | 逐字提取 `peak_features`、`probe_answer`；仅加 NumPy import 与固定入口 | `10d00d59ef42f48a946c4f4062e218ce0c59f4f49839cbf5c2232768ddaabbaa` |

57.8 的原 reviewer 单文件没有附在可核验记录中。因此本轮 A 是依据已披露语义制作的**忠实派生版本**，不宣称与原文件逐字一致。原始 [#78](https://github.com/Geniusyingmanji/ScientistsLastExam/issues/78) 的 0.657182 属于历史 development 分数；当前 head 已改 mass 分布和 outside controls，不能把两者当作同一任务版本。

B 的固定配置是 `[1, 1, 60, 2, 95.83680934806682, 1, 0.5]`，顺序为 target、units、excess threshold、hardness ratio、mass GeV、peak kind、peak threshold。它来自 [作者已公布的 JSON](https://github.com/Geniusyingmanji/ScientistsLastExam/blob/8497bd455d3090087e6a15e99fb85f5fae75e5cd/experiments/dark_matter_recoil_revision_2026-09-10.json#L3864)，属于此前作者在 development 选定的配置；本轮没有重新运行 233280 配置 grid，也没有使用本轮 heldout 结果选参。

两个函数的源码分别来自 [author driver 第 34–57 行](https://github.com/Geniusyingmanji/ScientistsLastExam/blob/8497bd455d3090087e6a15e99fb85f5fae75e5cd/scripts/audit_dark_matter_recoil.py#L34)。`peak_features` source segment hash 为 `cd7f6bacee544ba39d04b5fd3abb03d8c99713982310990f6d6cb13ef38ad3c1`，`probe_answer` 为 `fc612e234950bc2caf687a1be0cf8146db9967ddd7dc683e8a86d615a8871a7d`。混合 oracle 导入和 grid 搜索的作者 driver 从未导入或执行；依赖 truth 的 `constant_mass_bound` 也未运行。

## 双跑结果

已完成 **8/8** 次真实 `evaluate_candidate`，exit 0；四组完整指标双跑一致，**448/448** 个 world records 有效，无 infrastructure failure。task/runtime/candidate bytes 在运行前后均一致。另用只读 `verify_pr72_shortcut_evidence_2026-09-11.py` 核对八份私有原件的文件/canonical/per-instance hashes、逐 world 类型分母、有效性、消费 units 与归一化分数，没有追加评测；结果见 `pr72_shortcut_validation_2026-09-11.json`。

| 固定候选 | development score | heldout score | 相对 reference（dev / heldout） | 每 world 实际 units |
|---|---:|---:|---:|---:|
| baseline | 0 | 0 | 0% / 0% | 1 |
| reference | 0.5486397428 | 0.5000127063 | 100% / 100% | 12 |
| 57.8 忠实派生 | 0.2903389817 | 0.2439422043 | 52.92% / 48.79% | 12 |
| 已选四分类 | 0.2495350510 | 0.1306702190 | 45.48% / 26.13% | 1 |

两条固定策略均明显低于当前 reference。B 的 dev/heldout 绝对差为 0.2991046918 / 0.3693424873，两个 split 都满足作者事先声明的 `< 0.7 × reference` 且绝对差 `> 0.15` 门槛；这里只验证**先前选定这一组配置**，没有重新验证它在整个历史 grid 中仍最优。A 的单个 57.8 结果不能替代“全连续常量质量”上界，也不能据此证明任意捷径都已排除。

| 候选 | false claims / positive claims（dev / heldout） | 正确拒答 / unsupported（dev / heldout） | supported claims / signal（dev / heldout） |
|---|---|---|---|
| baseline | 18/28 / 18/28 | 0/4 / 0/4 | 20/20 / 20/20 |
| reference | 0/20 / 1/21 | 4/4 / 3/4 | 20/20 / 20/20 |
| 57.8 忠实派生 | 0/20 / 1/21 | 4/4 / 3/4 | 20/20 / 20/20 |
| 已选四分类 | 1/10 / 2/8 | 3/4 / 2/4 | 9/20 / 6/20 |

A 保持 reference 的分类/拒答/coverage 决策，分数下降来自其固定质量估计；B 的 supported coverage 只有 45% / 30%，其较低得分应与这些分母一起解读。两次复验累计消费 2912 个实验 units（baseline 112、reference 1344、A 1344、B 112）。callback 实测次数仍缺，不从预算 units 冒充推得观测次数。

本轮 reference 与作者文档中的旧数值存在小差异：作者 JSON 记录约 0.548485/0.499983，准备清单另记相同 NumPy/SciPy 版本约 0.548432/0.499973。本次固定当前 runtime 的实际双跑为 0.5486397428/0.5000127063；未调查该跨记录差异的具体数值来源，也没有用作者旧分数替代本轮测量。B 则与作者已公布数值在当前 oracle 的 10 位精度下一致。

结论仅为：**当前固定 head 上，这两条已披露策略没有重现历史“接近或超过 reference”的表现。** 任务仍缺独立模型标定、fresh/server-held confirmation 和外部领域审查；本轮不更新 TASK_CARD、不提升准入状态。


## 指标边界与证据保存

每个 split 固定 28 worlds：20 个 signal、4 个 none、4 个 unsupported。公开 JSON 保留各 split 聚合、false-claim/positive-claim、正确拒答/unsupported、supported-claim/supported、有效世界、实验 units 等分子分母。实验 units 是 oracle 返回的实际消费；callback 次数未被 oracle 记录，故标为 observed missing，并仅另列源码推导的预期（baseline/B 每 world 1 次，reference/A 每 world 3 次），不把推导当作遥测。

当前 oracle 的 `mechanism_score` 对正确正信号 law 乘以 mass 恢复 utility，再扣除 blanket-refusal utility 后归一化；它将机制判断与参数恢复耦合。SLE 当前 discovery 三轴是 **mechanism、FDR、refusal**，本任务已在同一 split 报告这三项，coverage 另列。独立 parameter-recovery 和 prediction 未提供，这是额外科学分解的限制，不能据此声称缺少 SLE 的三轴。

原聚合 JSON 的 `axes` 描述保留生成时的原字节；它只注记 mechanism 与额外参数/预测字段，不是框架 `scripts/report_discovery_triple.py::AXES` 的合同定义。所需 FDR/refusal 及其分母已在每次运行的 scalar metrics 和聚合计数中保留。split 聚合在 oracle 内已四舍五入至 10 位小数；私有逐 world 指标保留 oracle 返回精度，本轮未再四舍五入写入 JSON。

完整指标仅保存在 g450 的 `/home/azureuser/workspace-gzy/zyf/sle-pr72-private-20260911`（目录 0700、文件 0600），公开 `pr72_shortcut_review_2026-09-11.json` 不含逐 world 记录、kind 顺序或 candidate 回答。task package SHA-256 为 `ce48a182fdd72225869964e8daed453b8dac8688686829e8335c382c53bcde8f`，实际 driver SHA-256 为 `393f6b08880e2807c788e375372c9cc3d6ad80179baad9f921a5ce1b815cf88c`。公开报告包含 canonical full-metrics hash、私有 JSON 文件 bytes hash、per-instance hash，用于绑定留存原件。运行日志为 `/tmp/sle-pr72-fixed-replay-20260911.log`；首次零评测 preflight 为 `/tmp/sle-pr72-preflight-20260911.log`。

重放需在固定 runtime revision 的新 checkout 中仅导出指定 task head 的任务包，复制本目录 driver、候选与来源清单，并使用一个不存在的私有目录运行：

```sh
env PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
  MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 /usr/bin/python3 -B \
  .research/audit_pr72_shortcuts_2026-09-11.py --private-root /absolute/new/private-directory
```

Driver 在任何 sandbox 调用前核验 runtime/task/candidate hashes、环境与 logical ID，拒绝覆盖已有 campaign；按固定顺序每候选双跑，无自动 retry。任务包、runtime 和候选在结束后再次核对。

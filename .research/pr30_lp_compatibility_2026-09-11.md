# PR #30：无任务数据的 LP 沙箱兼容性诊断

2026-09-11。**默认 HiGHS 的退出已在一个两变量合成 LP 中稳定复现；简单添加 `linprog(options={"threads": 1})` 在当前 SciPy 1.10.1 中无效，因为该选项未传给 native wrapper。** 相同沙箱中的 revised simplex 正常求解。HiGHS 退出的更底层原因仍未确定；不能把“线程创建被拒绝”直接写成已证实的唯一根因。

本轮只有 **16 次无任务数据的 candidate sandbox RPC，0 次任务 `evaluate_candidate`、0 次模型调用**。未执行 PR30 原候选，未加载 oracle、实例、heldout 或原科学评测原件；未更改 runtime、安装包、安全策略或原6次冻结计划。

## 固定环境与输入

- 独立 g450 checkout：`/home/azureuser/workspace-gzy/zyf/sle-pr30-micro-20260911`，runtime head `2660c38a413fb7281d0e7012a6446eb384a934d1`。
- runtime source SHA-256：`8159a99d54894dd304e3ac48956cd05d4389f12a041f5d5d86a2c079641c2c86`，两轮前后均一致。
- 系统 Python 3.8.10、NumPy 1.24.4、SciPy 1.10.1；OPENBLAS/OMP/MKL/NUMEXPR 均为 1，且由候选内返回的环境值核对。
- 直接使用未修改的 `sle.secure_eval.CandidateProxy`；既有 Bubblewrap/seccomp、4096 MiB 地址空间限制、禁止新进程/线程策略均保留。每个 micro session 超时设为 15 秒；失败在约 0.6 秒发生，未命中 timeout 分类。
- 唯一 LP：最小化 `-x-2y`，约束 `x+y=1, x,y≥0`，已知唯一最优解 `(0,1)`、目标 `-2`。这些常数为本轮自写 fixture，不来自任何任务实例。
- 只读核对过 PR30 公共 adapter 中 `linprog(..., method="highs")` 无 options；其来源 hash 为 `0edd2d00f3d22286e7e33daad4ec1cfb6bc5610f1a1de1e7ceca2521a96f623d`。该候选未由本轮执行。

## 固定微实验

每行均在新 candidate worker 中双跑；完整合成结果和来源指纹见 `pr30_lp_compatibility_2026-09-11.json`。

| fixture | 结果 |
|---|---|
| NumPy/SciPy import 与环境回传 | 2/2 正常 |
| Python 创建一个空线程 | 2/2 返回线程未能创建；符合既有 seccomp 策略 |
| `linprog(method="highs")` 默认配置 | 2/2 在 `solver_entered` 后 `candidate_worker_exit` |
| `linprog(method="highs", options={"threads":1})` | 2/2 同上 |
| 直接 `_highs_wrapper(..., {"threads":1})` | 2/2 同上 |
| 直接 wrapper 的 `parallel=False,min_threads=1,max_threads=1` | 2/2 同上 |
| 候选内拦截 Python→native options，仅观察、不调用 native solver | 2/2 确认 `threads` 缺失，出现 `OptimizeWarning` |
| 同一 LP 改用 `method="revised simplex"` | 2/2 得到 `(0,1)`、`-2`；出现该旧方法的 `DeprecationWarning` |

options 拦截仅替换该 micro worker 自身导入模块中的 wrapper 引用，立即用自定义异常 结束；没有 native 求解、额外文件访问或策略改变。它核对了实际执行路径，而非仅根据版本号推断。安装目录的 `_linprog_highs.py` 同样只对 `unknown_options` 发出警告，没有把它并入传给 `_highs_wrapper` 的 options；[SciPy 官方 v1.10.1 源码](https://github.com/scipy/scipy/blob/v1.10.1/scipy/optimize/_linprog_highs.py)支持这一行为。

直接调用 wrapper 的资源选项也没有使 micro LP 成功，但尚未建立这些低层选项全部生效的证据。因此本轮既未确认单线程修复，也未确认 native 退出一定由线程创建造成。候选 worker 按现有协议把 native stderr 丢弃；未增加输出通道、syscall trace、调试权限或放开 seccomp 来追踪更深层原因。公开材料仅保留有限错误分类；native 退出细节留在私有诊断文件。

两份安装文件 SHA-256 均与当前 SciPy distribution 的 RECORD 匹配：`_linprog_highs.py` 为 `9684c61e71c5fe366612f1b108a2e1d5c99eb34db9fd7f8e965a8424ddc99e1a`，compiled `_highs_wrapper` 为 `4fb67b100c957bdb10c8ef42c7af4fe88138c222da6d42b554c7faf3cd39e20e`。未重装或替换任何库。

## 后续边界

保留 PR30 原冻结记录中的 worker failure，不能用 micro 的成功替换任务结果。若另做候选修正，应先选定可用的求解器策略，保留 exact rational reconstruction/residual 校验，冻结新源码/hash，然后另立固定任务复验计划。revised simplex 在一个小例子成功，只能证明一个可用的工程对照；它不是对 PR30 的完整可行性、正确性或速度保证，也不是无需新计划的修复。

源文件位于 `pr30_lp_micro_2026-09-11/{candidate,driver}.py` 与 `pr30_lp_micro_followup_2026-09-11/{candidate,driver}.py`。driver 只将这些自写候选交给 `CandidateProxy`，从未在宿主进程执行候选。复现应使用固定 checkout、系统解释器与上述线程环境，在新的私有目录中运行；脚本中的私有目录常量需对应新诊断位置，避免覆盖既有记录。运行日志和原始 `results.json` 应保持私有，再按公开摘要同样规则移除 native 退出细节后导出。

g450 私有原件位于 `sle-pr30-micro-private-20260911` 和 `sle-pr30-micro-followup-private-20260911`，目录 0700、原件文件 0600。公开摘要绑定原始 campaign bytes hash、候选 hash 和实际执行 driver hash。首轮 SSH 输出连接提前断开，但独立进程完成全部12项并写出结束标记，之后已只读核验；未因此重跑任何 micro。

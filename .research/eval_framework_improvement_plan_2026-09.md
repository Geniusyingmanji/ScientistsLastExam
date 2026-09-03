# 评测框架改进 code plan(2026-09)

依据 2026-09-02/03 的实测 review 写成。每一项都对应一个本轮真实踩到的坑,附文件路径与验收条件。
分三期:P0 本周必做(修正当前不一致、把这轮的坑固化成基建),P1 下两周(标定与准入自动化),
P2 下月(类型扩展与重判)。

## 现状快照

| 指标 | 值 |
|---|---|
| 任务包 | 58(optimization 29 / discovery 29;certified 5) |
| evaluator 行数 | 中位 411,P75 686,最大 1541;19 题超过 600 行 |
| 有 `reference_*.py` 参考实现 | 23 / 58 |
| 有 heldout / sealed 分层 | 40 / 58 |
| 发现类输出 FDR + 拒答双轴 | 29 / 29(coverage 列 25 / 29) |
| 暴露社区工具包 | 7 / 58 |
| 有 `references/known_best.md` | 42 / 58 |
| 本轮有前沿模型 draw 的任务 | 3 / 58 |
| certified 任务对 Opus 5 能测迭代 | 0 / 5 |

## P0:修正与固化(本周)—— 2026-09-03 状态:P0.1–P0.6 已落地(P0.5 的 runtime 哈希收窄部分除外),旧 run_eval 进程内执行路径已关闭

### P0.1 恢复 main 绿灯 ✅
`tests/test_task_maturity.py` 有 5 个测试把 12 个新任务钉为"不得进 `internal_science_admission`",
钉的是冻结证据文档过期时的快照;重出 v69/v52 后它们按门的定义(卡片 + 证书记录 + 沙箱基线)通过。
改为断言真正要保的性质:`certification_status == candidate`、`gate["blockers"] == []`、不在默认注册表。
验收:`pytest tests/test_task_maturity.py tests/test_measurement_health.py` 0 failed。

### P0.2 CI:Linux 全量 + 沙箱测试的 skip 语义 ✅(`.github/workflows/tests.yml`、`tests/_sandbox_tools.py`;仅在平台无法提供 bwrap/flock 时 skip,Linux 缺工具仍 fail)
- 新增 `.github/workflows/tests.yml`:ubuntu-22.04 虚拟机,`apt install bubblewrap util-linux`,跑 `pytest tests/`。
  **首跑教训(run 33737183216,159 failed)**:沙箱 exec 的是 `/usr/bin` 解释器且只挂 `/usr /lib /lib64`,
  而 `actions/setup-python` 把 numpy 装进 `/opt/hostedtoolcache`,沙箱内 `import numpy` 直接 ModuleNotFoundError。
  改为不用 setup-python,`sudo /usr/bin/python3 -m pip install numpy==1.24.4 scipy==1.10.1`(落在 `/usr/local/lib`,
  挂载范围内,与基准主机同构),测试也用 `/usr/bin/python3` 跑。3.8/3.11 矩阵因此取消:CI 的 Python 版本由
  runner 系统解释器决定(22.04 是 3.10);3.8 兼容以基准主机 g450 的实跑为准。要恢复 3.8 CI 得用 20.04 容器,
  但容器内 bwrap 需要非特权 user namespace,GitHub 的 Docker 默认 seccomp 不放行,暂不做。
- `tests/` 里所有需要 bwrap / flock 的测试,在缺工具时 `self.skipTest("requires bwrap")`,不再 fail。
  涉及 `test_secure_eval.py`、`test_run_cohort.py`、以及 12 个新任务的 `*_secure_path*` 测试。
验收:Mac 上全量测试只剩 skip,无环境性 fail;CI 在 PR 上有 checks(本轮三个 PR 是 0 checks)。

### P0.3 "没测到"与"测到零"必须区分(run 级不变量)✅(`summary.protocol_incomplete = no_valid_proposal`;batch_evolve 传递;准入报告 `collect` 跳过;`tests/test_protocol_incomplete_runs_are_not_evidence.py`)
- `sle/algorithms/evolve.py`:一个 run 内若全部提案都是 `no_code` / `candidate_invalid`,
  在 `summary.json` 写 `protocol_incomplete: true` 与首要失败原因,并在 stderr 打印显眼警告。
- `scripts/batch_evolve.py` 汇总里单列 `protocol_incomplete_runs`;
  `scripts/report_admission_criterion.py` 与 `audit_task_maturity.py` 把这类 run 排除出性能证据,
  不得进 best-so-far 曲线。
- `sle/llm.py` 已做的"有输出 token 却无 text 块 → RuntimeError"补单元测试覆盖 chat 与 anthropic 两条 wire。
验收:人为把 `thinking` 字段去掉复现一次,报告应显示 protocol_incomplete 而非"模型得 0 分"。

### P0.4 锚点溯源硬约束 ✅(8 个任务 `references/anchors.json`,守卫要求每个 evaluator 字面量都在账本内且带 source_url;evaluator 未改,哈希不动)
- 新增 `references/anchors.json`(每个字面锚点任务):`{name, value, source_url, retrieved_on, derivation}`;
  evaluator 的 `SIZES/INSTANCES/BEST` 从它读取,不再内联数字。
- `tests/test_external_anchors_are_checkable.py`:守卫改为"模块级 dict 里任何非零数值字面量都视为锚点",
  不再依赖键名正则(`sota_ref` 逃过守卫、CirclePacking 与 Superpermutation 各错一次是本轮教训);
  声明的任务必须有 `anchors.json` 且每条有 `source_url`。
- 新增 `scripts/check_anchor_sources.py`:对 `source_url` 做可达性与内容抽查(Packomania 坐标文件、
  OEIS 文本格式、arXiv 摘要),输出 `experiments/anchor_provenance_<date>.json`。
验收:8 个字面锚点任务全部有 anchors.json;守卫在删掉任一 source_url 时失败(阳性对照)。

### P0.5 全局证据一键刷新 ✅ 脚本 `scripts/refresh_global_evidence.py`(runtime 哈希收窄 **未做**,见下)
- 新增 `scripts/refresh_global_evidence.py`:在干净树上依次跑 `audit_tasks.py` → `run_secure_baseline.py`
  → `audit_task_maturity.py`,自动编号 vN+1,改写 `GLOBAL_REPORTS` 与 `DEFAULT_MATURITY` 指针,
  打印准入门与库存计数供更新 pin。
- 顺带把 `runtime_source_sha256` 的覆盖范围收窄到影响分数的代码路径:`secure_eval.py` 里挂载方式
  (procfs 探测)与评测语义分文件,前者不进哈希。本轮改 31 行 procfs 探测就让 26/58 任务的基线失效。
验收:改动 `secure_eval.py` 中的挂载探测后,重出证据不需要;改动 `evaluate.py` 后需要,且脚本一步完成。

### P0.6 计数类 pin 改为计算不变量 ✅
`tests/test_certification.py`、`test_benchmark_layout.py`、`test_task_maturity.py`、
`test_measurement_health.py` 里的库存 / candidate / 准入门字面量,改为
"从注册表算出 + 与报告一致"的断言;只保留策略性字面量(certified == 5)。本轮这些 pin 手改了 43→44→45→46→58 共五次。
验收:加一个任务只需注册,不需改任何测试计数。

### P0.7 关闭旧 run_eval.py 的进程内执行路径 ✅
46 个旧模板在同一进程 import 候选再调 oracle;现改为薄封装,shell 出去调 `python -m sle eval`(trusted_driver + bwrap)。
`eval_command.txt` 黑盒契约不变。代价:46 个任务包哈希变动,需一次证据刷新。
**连带伤(2026-09-03 CI 首跑暴露)**:全局证据刷了,但 7 任务冻结队列没刷 —— 物质性契约与预审 spec v8 都把
`frontier_eval/run_eval.py` 当运行时文件,重写后 7/7 解绑,`test_scientific_materiality` 4 红、`test_measurement_health_preflight` 8 红、
`test_batch_runner` 1 红。处置:(a) 该文件没有任何 `sle/` 代码执行,绑定的标定证据全由 `evaluate_candidate` 产出,故从
`_task_runtime_paths` 与 `_package_mismatch_explanation` 的行为性文件里排除(`RUNTIME_SCOPE_EXCLUDED_EVAL_FILES`,单测钉住);
(b) `evolve.py` 的 protocol_incomplete 改动确实在恢复检查的运行时范围内,在 g450 干净树重测 `evaluation_recovery_fault_audit_v4`;
(c) `rebind_measurement_health_spec.py` 重签 spec v9 / manifest v7 / artifacts v7,7 任务全部 rebound、0 refused。
教训:改任何任务包内文件后,`refresh_global_evidence.py` 之外还要跑 `pytest tests/test_measurement_health_preflight.py tests/test_scientific_materiality.py tests/test_batch_runner.py`。

## P1:标定与准入自动化(两周)

### P1.1 `scripts/calibrate_task.py`
一条命令完成一个任务的前沿模型标定:`--task --model --seeds 0,1,2 --budget 3`,
跑 normal 单臂,读参考解分数,输出首提案分布、最好分、是否触参考,自动写入 `TASK_CARD.yaml` 的
`lineage.calibrator_model_ids / calibration_runs / calibration_evidence_status`,并给出
`admission_bar: passed | saturated`。要求干净树(脏树直接拒绝,而不是产出 `source_tree_dirty` 的证据)。
验收:对 PhaseDiagramDiscovery 重跑,产出与手工记录一致的卡片字段。

### P1.2 新任务的机器准入检查
`tests/test_new_tasks_have_a_frontier_draw.py`:任何 `lineage.status == complete` 且非 on-ramp 的任务,
必须有 `calibration_runs` 且证据文档 `trusted_evidence == true`;首提案分 ≥ 参考解的任务必须在
`exam_taxonomy.yaml` 标 `on_ramp_do_not_pair`。
验收:EnzymeKineticsLaw / DiscrepantMeasurements 被标 on-ramp,PhaseDiagramDiscovery 不被标。

### P1.3 `scripts/run_delta_ladder.py`
封装 `batch_evolve.py` 的配对两臂 + `report_admission_criterion.py`,输出"任务 × 搜索器"矩阵
(`experiments/admission_matrix_<date>.json`),字段:verdict、Δ 曲线、开环终值、seed 数、trust。
白名单从这个矩阵生成,不再是任务列表。
验收:对 5 个 certified + PhaseDiagramDiscovery 跑 Opus 5,矩阵能复现本轮 0/5 的判决。

### P1.4 契约复杂度预算
`scripts/check_contract_complexity.py`:evaluator 行数、必填输出字段数、跨字段一致性约束数;
超过预算(建议 600 行 / 6 字段)必须在 `TASK_CARD.yaml` 写 `contract_complexity_waiver` 说明理由。
先对 19 个超 600 行的任务出报告,再决定哪些拆分。
验收:报告进 `audit_task_maturity.py`,协议通过率与科学分继续分开报告。

### P1.5 覆盖补齐
- heldout:为 18 个无 sealed 分层的任务补 heldout 世界(优先 certified 与 uncapped)。
- 参考实现:candidate → certified 的必要条件加上"有 `reference_*.py` 且真值盲"。
- known_best:16 个缺失的任务补齐(uncapped 任务本就必需)。
验收:三项覆盖分别到 58/58、每个 certified 有参考、58/58。

## P2:类型扩展与重判(下月)

### P2.1 扩展 `sle/conf/exam_taxonomy.yaml`
- optimization 新增 analogue:`pareto`(多目标前沿,评 hypervolume)、`robust`(制造偏差 / 分布漂移下的
  最差或期望性能)、`algorithm_engineering`(算力预算下的加速比,无上限)、`protocol`(产物是采样计划,
  评信息增益)、`prospective_record`(锚点为 cutoff 后出现的纪录,滚动刷新)。
- discovery 新增 kind:`detection`(有无信号,主轴 FDR + look-elsewhere)、`regime`(相变 / 临界 / 边界)、
  `invariant`(守恒量与对称性,耗散系统拒答)、`systematics`(仪器与系统误差:漂移、混杂、选择效应)、
  `counterfactual`(给定结构预测未做过的干预,不可识别时拒答)。
- `scripts/report_exam_taxonomy.py` 输出学科 × kind 矩阵与空格清单,作为建任务的排期依据。
验收:每个任务恰好映射一个 kind;矩阵报告进 `.research/`。

### P2.2 重判 13 个 `parameter_inversion`
逐题判定能否改成有真实拒答轴的形式:
RadialVelocityPlanets → detection;SpinSystemInference / NMRSpectrumFitting / ReactionMechanismFitting →
formula(族内选律 + 族外拒答);GravityInversion / RadiativeTransferFit / ConvectionDiffusionOpt 视误设世界
是否可判错决定留 parameter_inversion 或转 structure。改判必须伴随 evaluator 增加可判错世界,否则只是换标签。
验收:parameter_inversion 占比从 45% 降到 25% 以下,每个改判任务新增至少一种"该拒答"的世界。

### P2.3 首批新类型任务(各 2 题,均按 P1.2 准入线)
- detection 迁出 Physics:生物(差异表达 / 变异检出)、地球(前兆检出)。
- invariant:物理(从轨迹找守恒量)、化学(反应网络的守恒模)。
- substance 扩到光谱以外:混合物成分、群落组成。
验收:6 题全部有前沿 draw,首提案不触参考;进 Δ 矩阵。

## 本轮已完成、可直接复用的部分

- `sle/llm.py`:Anthropic wire 显式 `thinking: disabled`,空 text 抛错(PR #3 在 chat wire 同步)。
- `scripts/check_numeric_keys_hold_numbers.py` + 测试(带阳性对照)。
- `tests/test_external_anchors_are_checkable.py`:正则加 `sota`,声明 8 个字面锚点任务,CapSet 补出处。
- CirclePacking N=13 与 Superpermutation n=8 锚点从来源重推导。
- `scripts/run_cohort.sh` 完成性检查改 `python3`,测试 shim 转交真实解释器(g450 14/14)。
- 三份全局证据文档已刷到 58 任务(v69 / v52 / v10),准入门 58 / 58。

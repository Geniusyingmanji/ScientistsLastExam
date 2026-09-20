# Scientists' Last Exam: Scientific Discovery

`main` 维护 **discovery**：在没有预先给定正确结论的情况下，通过多轮调查、实验、推导和复核建立有边界的科学主张。
优化任务、专用数据构建与标定代码位于 [`optimization`](https://github.com/Geniusyingmanji/ScientistsLastExam/tree/optimization) 分支。
两分支共享必要的沙箱、模型传输、运行账本和历史证据读取能力。

## 发现流程

**问题 → 竞争假设 → 实验或推导 → 证据 → 检验（必要时修订）→ 有适用范围的结论。**
其中结论可以涉及规律、结构、机制或物质，也可以是对参数的有边界估计；这些是主张类型，不是这个流程的先后阶段。
负面结果、排除一种解释、发现证据不足或缩小结论都可以是有效产出。

`sle episode` 默认使用无 GT 的证据模式。支持多轮工具、持久隔离 Python 分析、假设修订，
随后冻结主张和复核计划，再开放封存观测。原生证据、预注册预测、反证披露和资源消耗可以程序化核查；
假设合理性、推理充分性、因果解释和新颖性需要独立科学审阅。
**日志齐全不等于发现成立；当前没有自动 discovery 总分。**

协议、指标、限制和 Linux 验证记录见 [发现评估](docs/discovery_evaluation.md)，
运行入口见 [科学实验环境](docs/scientific_environments.md)。
真实观测准备与分阶段审阅见 [北京 PM2.5 方法试点](docs/discovery_observational_pilot.md)；
分支切分的原始失败、跳过及定向复验见 [验证记录](docs/discovery_split_validation.md)。
该试点已完成两个 `gpt-5.6-sol` 多轮 episode（另一个槽位为网络超时），
[实际结果与方法审阅](docs/discovery_observational_pilot_results_20260920.md)单列过程记录和科学判断。
检验后的只读解释及复合主张核查仍是[下一版要求](docs/discovery_posttest_interpretation_plan.md)，尚未实现。

## 当前任务

<!-- task-inventory:start -->

当前 46 个任务包,横跨 7 个学科,0 个 certified、40 个 candidate、6 个 quarantined。
注册表中的这些任务使用历史 oracle 契约;无 GT 多轮实验环境另列,不混入认证数量。

discovery(46 个):从受预算约束的证据中建立可检验主张,或在证据不足、模型失配时保留结论。
按主张对象分为:公式 7、结构 6、证据 11、物质 6、参数反演 16。
这些是产物类型,不是从假设到发现必须依次经过的阶段。

<!-- task-inventory:end -->

另有五个未进入注册表的 discovery 实验环境。`MeasurementAudit` 支持来自真实观测的 manifest/CSV 数据包，
没有生成器、隐藏机制或答案标签；随附手工表格仅用于协议测试。
其余四个模拟环境保留为显式 oracle 构建诊断，不作为未知科学结论的真值评测。
完整注册表见 [TASKS.md](TASKS.md)。六个饱和或存在捷径的旧题由
[准入排除规则](docs/discovery_eligibility.md) 保持 quarantined。

## 运行

```bash
python -m sle list --all
python -m sle episode --list
# 无 API 调用的协议示例，报告保存在仓库外的私有目录。
python -m sle episode --task MeasurementAudit --baseline protocol \
  --output-dir /var/tmp/sle-discovery-protocol
# 真实观测、多轮工具和隔离分析。
python -m sle episode --task MeasurementAudit \
  --data-bundle /private/operator/study --llm-config /private/operator/model.yaml \
  --analysis sandbox --max-steps 32 --wall-seconds 600 --experiment-budget 20000 \
  --output-dir /var/tmp/sle-discovery-run
```

默认 `list` 只列 certified；当前 discovery 注册表为 0 certified，不能因拆分而自动提升候选认证状态。
密钥仅通过已有私有模型配置或环境变量提供，不进入候选沙箱、代码库或公开报告。
候选程序接口为 `solve(context, act)`；模型每轮发出一个 JSON action。

隔离执行要求 Linux、bubblewrap 与 util-linux flock。候选看不到宿主文件、凭证、数据包和评审器；
网络命名空间阻断连接，seccomp 阻断进程创建。每个 episode 使用新的隔离状态。
单轮内可以保留分析变量，实验费用和冻结后的复核共享预算。
沙箱不可用时不会回退到宿主执行。

```bash
python -m pip install -r requirements-host.txt
python -m pytest tests/ -q
python scripts/audit_tasks.py --output /var/tmp/discovery-task-audit.json
python scripts/report_task_inventory.py --check
```

主机 NumPy/SciPy 版本见 `requirements-host.txt`；完整历史 oracle 工具链由
`scripts/setup_oracle_env.sh` 安装，目前认证 Python 3.8。笔记本可以运行单元测试，但 Linux 隔离和
依赖精确版本的检查必须在相应环境验证，不能把 skipped 当作通过。

## 历史任务与共享工具

已有模拟任务仍可经 `sle eval --allow-uncertified` 执行；旧 `sle run` 搜索后端和配对报告工具保留，
用于历史 discovery 契约的复现。`combined_score`、机制恢复、FDR/FPR 等指标只在任务具有相应
真值和明确分母时有意义，不套用到无 GT 发现。

`experiments/` 和 `.research/` 保存拆分前的原始记录，可能含 optimization 或混合队列。
原始证据的内容、分母和绑定不因分支而重写；`sle/conf/branch_scope.yaml` 明确当前库存及迁移清单。
历史双任务预注册生成器依赖当时完整库存，不得当作本分支已执行的新实验。
旧证据不会因为能被读取就成为当前模型、当前任务或当前运行时的有效评测。

## 贡献

main 的新贡献请围绕科学问题、数据或仪器来源、可检验的竞争解释、受控工具、证据来源、
复核路径和独立审阅标准展开。优化题请以 `optimization` 为 PR base。
参见 [CONTRIBUTING.md](CONTRIBUTING.md)。任务准入、科学价值和对顶级模型的难度需要分别验证；
一个模型首轮成功不自动意味着删除，稳定被固定策略或捷径解决的题应退出难题集合。

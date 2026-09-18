# Scientists' Last Exam: Optimizing the Known, Discovering the Unknown

## 背景

Scientists' Last Exam (SLE) 是一个面向跨学科、可执行、预算受限的科学搜索基准。
它不问"模型能不能考一次高分",而问:给模型反馈和更多预算,它在科学上会不会变得更好。

每个任务是一个可运行程序加一个隐藏的、冻结的、确定性的 oracle。搜索者改程序,oracle 打分,
允许公开的反馈回到下一轮。科学结果由可执行验证器判定,不依赖 LLM judge。
部分优化任务允许超过已知参考纪录;发现任务分别报告过程证据和结果验证。

发现的评估单位是**科学主张及其证据链**:提出了什么、依据哪些观测、如何检验、结论适用于哪里。
重发现可以测科学能力,但不自动构成领域新发现;优化也可能产生新的构造、方法或性能界。
我们借鉴 DiscoveryBench 的结构化主张与 TRACES 的过程/结果分离,并使用同预算对照检验迭代收益。
相关研究、实现范围和限制见 [`docs/discovery_evaluation.md`](docs/discovery_evaluation.md)。

发现类的五个 kind —— 公式、结构、证据、物质、参数反演 —— 描述产物形式。
另外用主张类型、假设空间开放度、验证方式和新颖性范围建立能力档案;这些维度不合并成科学价值总分。

机器可读的格点账本是 `sle/conf/exam_taxonomy.yaml`(`python scripts/report_exam_taxonomy.py`)。

## 两类任务

<!-- task-inventory:start -->

当前 88 个任务包,横跨 7 个学科,5 个 certified、77 个 candidate、6 个 quarantined。
这一段的每个数字都由 `tests/test_readme_inventory_counts.py` 对着注册表核,改不动就是改错了。

optimization(42 个):在受约束的设计空间里把目标做得更好。分四类:
工程设计(换热器、桁架、薄膜、解码器等 16 题)、开放组合纪录(圆堆积、cap set、Ramsey、kissing、
张量秩、超排列等 17 题,无上限)、分子与大分子设计(5 题)、证书上界(4 题,产物是可验证的论证本身,
分数是论证证明出的界有多强)。
分数由做出来的东西有多好决定;公开纪录是 score = 1 的见证,不是封顶。

discovery(46 个):从受预算约束的证据中建立可检验主张,或在证据不足、模型失配时正确保留结论。
分五类:公式 7、结构 6、证据 11、物质 6、参数反演 16。各题分别规定可识别机制、
模型族外、null、信息不足等适用情形;不能把所有拒答都解释成“根本没有机制”。
候选看不到隐藏世界的类型标签。

<!-- task-inventory:end -->

发现类分开报告三个轴,永不平均:

| 轴 | 问的是 |
|---|---|
| 机制恢复 | 找对了多少 |
| 假发现 | 分别标注 FDR(假宣称/全部宣称)或 FPR(假宣称/不支持世界),不混用分母 |
| 校准拒答 | 在该拒的世界上拒了 |

这些轴不合成一个数。全面弃权可能获得高拒答率;零宣称时 FDR 分母为零,报告为不可用。
另有一列"是否尝试过发现",三元组说的是做得多好,它说的是到底有没有试。

四个试点额外保存可信评测侧的实验请求、观测、提交和逐世界结果,形成 evaluator-only 的
`discovery_evidence`。日志齐全不等于推理正确,结果命中也不等于形成过程已验证。
没有记录的旧运行标记为未观测;没有审核的任务档案保持 `not_assessed`。

当前六个饱和或存在捷径的旧 discovery 任务已退出前沿使用,其余任务仍须独立难度标定。
版本绑定的排除规则见 [`docs/discovery_eligibility.md`](docs/discovery_eligibility.md)。
新增 `sle episode` 支持有预算的交互实验、冻结主张、独立确认和隔离 Python 分析;
运行方法见 [`docs/scientific_environments.md`](docs/scientific_environments.md)。
两个环境原型尚未进入正式任务集合,其中酶动力学仅作为协议测试,不能计作合格难题。

```bash
python scripts/report_discovery_evidence.py --output /tmp/discovery_profiles.json
python scripts/report_discovery_evidence.py --metrics /private/operator/full_metrics.json \
  --output /private/operator/discovery_report.json
```

## 任务形式

```text
<Task>/
├── Task.md                       # 智能体可见的任务描述,须列出每一个输入键
├── TASK_CARD.yaml                # 科学证据、lineage 与评审记录
├── solution.py                   # 弱但合法的基线(通常"自信地错")
├── frontier_eval/                # metadata.yaml、entrypoint.txt、constraints.txt、run_eval.py
├── verification/
│   ├── evaluator.py              # 隐藏的冻结 oracle
│   └── reference_*.py            # 真值盲的参考实现(可运行的锚点)
└── references/
    └── known_best.md             # 锚点的来源与重推导,无上限任务必需
```

分数按各任务的归一化契约解释;基线不保证恰为 0,uncapped 任务不设上限。
发现类的归一化让全面弃权恰好得零。evaluator 至少返回有限数值的 `combined_score` 与 `valid`。

需要跨版本持续优化或发现的任务可选择加入 **frontier family**。同一
`task_family_id` 下的每个 `wave_id` 都有冻结的 `frontier_eval/wave.yaml`；运行清单同时绑定
wave、task package 与 runtime hash。固定 wave 的 `combined_score` 用于公平比较，跨 wave 的
`lifetime_frontier_credit` 只累计通过 trusted evaluator 规范化、去重且超过最小科学增量的记录。
代码拒绝候选自造 cell,并在同一 cell/namespace 内去重;跨契约的语义重复、新增容易 cell 与高保真确认由 wave 评审把关。
credit 不包含假发现/弃权惩罚,不是提交质量综合分。完整契约见
[`docs/frontier_families.md`](docs/frontier_families.md)。
`python -m sle list --all` 是权威的实时清单。

## 评测形式

核心量是可演化性差距 Δ:

```
normal            搜索者看得到分数,能据此迭代
selection_blind   种子配对、预算相同,但每个提案只看得到冻结的基线
Δ = normal − selection_blind
```

`selection_blind` 是严格的开环对照,把"best-of-N 抽样"与"真的在迭代"分开。
准入判据是两段式的:开环对照必须先饱和(否则分数高只说明抽样够多),然后 Δ 随预算扩大才算数。
一个正 Δ 若伴随着仍在上升的开环对照,会被判据拒收。

判据是"任务 × 搜索器"的联合性质:更强的模型会让任务失格。实测的一个例子:
5 个 certified 任务在 Claude Opus 5 的配对 Δ 阶梯下,能测出迭代的是 0 个。
因此新任务的准入线写进了构建流程:参考解故意不打满,且首个前沿模型提案不得够到参考。

可见性合约:搜索者只收到 `combined_score`、有效性、可行率。稳健性、机制恢复、heldout 与
逐实例指标是 evaluator-only,不能被直接优化。

执行环境:候选代码经带类型的 JSON-RPC 边界,在无网络的 Bubblewrap 内单独运行,oracle 运行在
受信父进程。只读挂载、私有临时文件系统、资源限制、seccomp 阻断进程创建,以及标签盲的失败分类,
把候选可控的异常文本从搜索反馈中剔除。

### 主机前置条件

分数要在本机可信,需要 bubblewrap 与 util-linux `flock`(见上),外加**认证过的 NumPy/SciPy**:

```bash
python -m pip install -r requirements-host.txt   # 或:pip install -e ".[host]"
```

这两个版本是录制 oracle 锚点时用的,每个候选都要 import 它们。它们不是硬性要求:版本不符时
`sle eval` 只在 stderr 给出警告并继续跑,因为比它更早失败会让整台机器上一个任务都跑不了 ——
在一个 SciPy 1.12.0 的主机上,88 个任务里 87 个在候选执行前就抛错,而错误信息只说了包名和两个
版本号。**但警告是提示,不是等价性声明**:oracle 若比较 NumPy/SciPy 的数值,未认证的主机上分数
可能与记录不同。要复现记录的分数,就必须装这一组。

任务自己声明的 toolkit(写在 `frontier_eval/candidate_packages.txt`)不受此宽容:它仍然必须精确
匹配,否则 fail closed,因为那些锚点正是对着那个版本录的。完整 oracle 环境(域 toolkit 及其审计
过的传递闭包)由 `scripts/setup_oracle_env.sh` 安装,目前只认证 Python 3.8。Python 版本下界是
3.8,见 `pyproject.toml` 的 `requires-python`。

```bash
python -m sle list                                    # 只列 certified,--all 含 candidate
python -m sle eval --task Chemistry/LennardJonesCluster

cp sle/conf/llm/anthropic.example.yaml sle/conf/llm/local.claude.yaml   # 密钥只走环境变量
python -m sle run --task Chemistry/LennardJonesCluster \
  --algorithm greedy_rewrite --budget 10 --seed 0 --workdir runs/lj/seed-0

python scripts/batch_evolve.py --tasks <Domain/Task> --all \
  --feedback-modes normal,selection_blind --seeds 0,1,2 --budget 12 \
  --llm-config sle/conf/llm/local.claude.yaml --workdir runs/<name> --output experiments/<name>.json
python scripts/report_admission_criterion.py --runs runs/<name> --output /tmp/admission.json
python scripts/report_discovery_triple.py --runs runs/<name> --split heldout --output /tmp/discovery.json
python scripts/report_discipline_scores.py --input experiments/<name>.json \
  --proposal-budget 12 --output /tmp/disciplines.json
```

可用算法:`greedy_rewrite`(内置)、`openevolve`、`abmcts`、`shinkaevolve`。指名的后端若不可用会
显式失败,绝不静默回退。实验报告按哈希绑定 Git 修订、命令、源码树状态与信任判定;
无法绑定到产出它的运行时的证据会被拒绝,而不是被悄悄复用。

报告使用实际被接受的 incumbent,包括保留的基线。发现轴每个 run 单列,默认只读取 held-out;
缺轴不从 development 补齐。`TASK_CARD.yaml` 的 `metric_contract` 声明指标、估计量、分母和方向;
报告只对 package hash 完全匹配的记录应用当前契约,旧记录保留原值并标记口径未确认。

批处理先保存完整计划及任务分类。学科报告在同一批次、算法、固定 proposal 前缀内配对
`normal`/`selection_blind`,先平均 seed 再平均任务,并分开 discipline、任务形式和 score mode。
它输出终点、相对基线增益、包含 baseline 的预算 AUC、Δ、完成率和可用的实际成本。
缺失、失败或不兼容的计划运行保留分母,完整队列估计为不可用;不会给基础设施失败补零分。
旧批次没有冻结分类时不生成正式学科汇总。成本仅覆盖最新运行的指定前缀,不代表重试总费用。
这些描述性报告不会把旧校准、smoke 或未通过科学准入的结果升级为有效模型证据。

详细的测量结果、判决与开放项见 [`.research/`](.research/)。

## 如何贡献

新任务的契约与认证要求见 [`CONTRIBUTING.md`](CONTRIBUTING.md)。要点:

- oracle 必须冻结且确定:同一个候选每次得同样的分,任何进程级随机源(包括社区库内部的)都要定种。
- 候选打不挂 evaluator:写坏的提交该得零分,不该让整个 cohort 的证据陪葬
  (`scripts/check_evaluator_survives_bad_candidates.py`)。
- 锚点要能重新推导:由 evaluator 重算,或以可运行的参考实现交付;对着字面量归一化的任务必须在
  `tests/test_external_anchors_are_checkable.py` 里声明,并在 `references/known_best.md` 写明来源
  与推导(从来源文件重算,不抄渲染出来的表)。
- 提交契约要写进 `Task.md`,且公开问题字典里读起来像数值的键不能装散文
  (`scripts/check_numeric_keys_hold_numbers.py`)。
- 发现类任务要报满三个轴,并能区分"弃权"与"尝试了但没做对"。
- 难度用真实模型 draw 标定,不用参考实现或消融阶梯:参考解故意不打满,首个前沿模型提案够到参考的
  任务只算 on-ramp。
- 在哪里跑:笔记本(macOS / Windows)只用来改代码和跑单元测试,需要沙箱的测试会自动 skip。
  任何要进仓库的证据(基线、标定、Δ 阶梯、全局证据刷新、恢复审计)都必须在装有 bubblewrap 与
  util-linux flock 的 Linux 主机上、从干净的 git 树生成;脏树或笔记本产出的文档会被标为不可信并被
  测试拒收。CI 在 Linux 上跑全量测试,是合并前唯一算数的绿灯。
- 密钥只走环境变量:LLM 配置放 `sle/conf/llm/local.*.yaml`(已忽略),里面写
  `api_key: ${ANTHROPIC_API_KEY}` 这样的引用,永远不要把密钥写进任何文件。

加一个包只是让它可被发现,不等于认证。认证描述的是证据质量,不是任务难度。

```bash
python -m pytest tests/ -q                                   # 笔记本:沙箱测试自动 skip
python scripts/audit_tasks.py --output /tmp/certification.json
python scripts/audit_benchmark_standards.py --output /tmp/standards.json
mkdir -m 700 /tmp/sle-private-evidence                      # 使用新的仓库外私有目录
python scripts/refresh_global_evidence.py --commit --private-output /tmp/sle-private-evidence/baseline.json
# 上述刷新仅限 Linux 主机、干净树；私有完整原件不可覆盖，公开报告只含选择指标和哈希。
```

## 任务汇总

全部任务包按形式与子类分组的清单,含学科、打分模式、oracle 类型与认证状态:[`TASKS.md`](TASKS.md)
(由 `scripts/report_task_inventory.py` 生成,测试保证与注册表一致)。

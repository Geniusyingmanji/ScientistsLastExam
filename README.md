# Scientists' Last Exam: Optimizing the Known, Discovering the Unknown

## 背景

Scientists' Last Exam (SLE) 是一个面向跨学科、可执行、预算受限的科学搜索基准。
它不问"模型能不能考一次高分",而问:给模型反馈和更多预算,它在科学上会不会变得更好。

每个任务是一个可运行程序加一个隐藏的、冻结的、确定性的 oracle。搜索者改程序,oracle 打分,
分数回到下一轮。没有 LLM judge,分数可以超过人类已知最好水平。

同期基准各占一格,SLE 占的是"多学科 + 可执行搜索 + 以同一搜索者的开环臂是否饱和作为任务准入判据"(同行有开环消融臂,没有人把它当准入门):

```text
Scientists' Last Exam
├── 场景
│   ├── 多学科广度 ── 本仓库(可执行搜索,不是一次作答)
│   │     SFE / HLE 占理解与闭卷;sgi-bench 占全流程写论文,都不在这里
│   └── 单学科纵深 ── NewtonBench 物理 · BioDesignBench 蛋白
├── 任务形式
│   ├── optimization ── Frontier-Eng 工程 · PMO 分子 · 开放数学纪录
│   └── discovery
│       ├── 公式   ── 在一族候选律里认出哪条成立,或判断都不成立
│       ├── 结构   ── 恢复图、网络、几何
│       ├── 证据   ── 判断一批测量到底支持什么
│       ├── 物质   ── 说出有哪些相、物种、成分
│       └── 参数反演 ── 形式已知、只差数值;占发现类近半,是最易饱和、最该重判的一类
└── 评估
    ├── 受限 oracle 预算 ── 已成标配
    ├── 弃权能力 ── 全弃权强制得零,该拒时拒才得分
    └── 可演化性差距 Δ ── 本仓库:同一搜索者,有反馈臂 vs 开环臂,开环饱和才准入
```

机器可读的格点账本是 `sle/conf/exam_taxonomy.yaml`(`python scripts/report_exam_taxonomy.py`)。

## 两类任务

当前 58 个任务包,横跨 7 个学科,5 个 certified、53 个 candidate。

optimization(29 个):在受约束的设计空间里把目标做得更好。分三类:
工程设计(换热器、桁架、薄膜、解码器等 15 题)、开放组合纪录(圆堆积、cap set、Ramsey、kissing、
张量秩、超排列等 9 题,无上限)、分子与大分子设计(5 题)。
分数由做出来的东西有多好决定;公开纪录是 score = 1 的见证,不是封顶。

discovery(29 个):从受预算约束的观测里恢复一个机制,或判断根本没有机制可恢复。
分五类:公式 5、结构 4、证据 4、物质 3、参数反演 13。每题包含三种世界:
机制在候选可表达的模型族内(该找出来)、机制在族外、根本没有机制(后两种该拒答)。
候选看不到自己面对的是哪一类。

发现类分开报告三个轴,永不平均:

| 轴 | 问的是 |
|---|---|
| 机制恢复 | 找对了多少 |
| 假发现率 | 在不该宣称的世界上宣称了机制 |
| 校准拒答 | 在该拒的世界上拒了 |

不能合成一个数:全面弃权的候选在后两个轴上都是满分,只有机制恢复是 0。
另有一列"是否尝试过发现",三元组说的是做得多好,它说的是到底有没有试。

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

分数经过归一化:0 是出厂基线,1 是参考见证解,uncapped 任务不设上限。
发现类的归一化让全面弃权恰好得零。evaluator 至少返回有限数值的 `combined_score` 与 `valid`。
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
```

可用算法:`greedy_rewrite`(内置)、`openevolve`、`abmcts`、`shinkaevolve`。指名的后端若不可用会
显式失败,绝不静默回退。实验报告按哈希绑定 Git 修订、命令、源码树状态与信任判定;
无法绑定到产出它的运行时的证据会被拒绝,而不是被悄悄复用。

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

加一个包只是让它可被发现,不等于认证。认证描述的是证据质量,不是任务难度。

```bash
python -m unittest discover -s tests -q
python scripts/audit_tasks.py --output /tmp/certification.json
python scripts/audit_benchmark_standards.py --output /tmp/standards.json
```

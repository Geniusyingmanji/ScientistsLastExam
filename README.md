# Scientist's Last Exam

Scientist's Last Exam (SLE) 是一个研究原型,面向**跨领域、可执行、预算受限的科学生成式优化**。
智能体编辑一个可运行的程序,一个冻结的确定性 oracle 为每个候选打分,基准同时记录最好的可行产物
和找到它所用的、计入成本的轨迹。

它要回答的不是"模型能不能考一次高分",而是**"给模型反馈和更多预算,它在科学上会不会变得更好"** ——
也就是 AlphaFold 式、AlphaEvolve 式结果所处的那个自我改进的智能体区间。

这两半都要紧,而同期文献恰好沿这条线分开。SEE([arXiv:2608.06931](https://arxiv.org/abs/2608.06931))
是科学 —— 专家编纂的化学、生物、材料题目,19 个多模态模型,最好准确率 48.7% —— 但它是静态题集,
说不了迭代有没有用。OPT-BENCH([arXiv:2605.08904](https://arxiv.org/abs/2605.08904))用无记忆对照臂
测量迭代式自我优化,工具是对的,但它的三十个环境是二十个机器学习任务加十个 NP-hard 问题。
**两者都不在交集上**:一个有冻结领域 oracle 的科学问题,而被测量的是反馈会不会累积。

这个交集就是本仓库的目的。判据、完整判决与"底下科学是否真实"的审计,都在
[详细发现与审计](.research/findings_and_audits_2026-08.md)。今天诚实的答案是:两边的数字都不大。

本仓库受 [Frontier-Engineering](https://github.com/EinsiaLab/Frontier-Engineering) 启发。它与
[arXiv:2601.21165](https://arxiv.org/abs/2601.21165) 中那个名为 *FrontierScience* 的文本题基准无关。

> 更高的模拟器或验证器分数,只能证明在**已登记的 oracle 内部**做了优化。它本身不能确立自主科学发现、
> 机制恢复、物理验证或真实世界效用。

## 速览

- **43 个任务包**,横跨 7 个学科 —— **24 个科学优化**任务与 **19 个科学发现**任务。发现类任务分开报告
  机制恢复、假发现率、校准拒答,因为一个被最大化的标量说不出一个发现**对不对**。
- **5 个 certified**、38 个 candidate;隔离区为空。
- 通过无网络的 Bubblewrap 沙箱做确定性黑盒评测,oracle 运行在受信父进程,搜索可见指标走严格白名单。
- 内置迭代重写基线,外加 OpenEvolve、AB-MCTS、ShinkaEvolve 三个后端。
- 实验报告按哈希绑定,携带 Git 修订、命令、源码树状态与显式的信任判定 ——
  **无法绑定到产出它的运行时的证据会被拒绝,而不是被悄悄复用**。
- **7 个 oracle 使用社区标准科学工具** —— Stim + PyMatching、RDKit、ViennaRNA、nmrsim、networkx、
  SymPy、QuTiP。其余 36 个是本项目自己写的 NumPy,这是最大的现存缺口。
- **6 个任务**目前被证明能测量迭代改进,其中 3 个依赖的饱和结论会被它们自己的补充种子推翻。

[任务形态与难度](#任务形态与难度)给出难度画像,[简要结论](#简要结论)给出覆盖度与边界。

### 范围

剩下的每个任务都是自然科学或其数学。两个运筹学条目(`MultiEchelonStock`、`TrafficSignalTiming`)
曾因可复现的缺陷被隔离,现已离开清单,隔离区为空。

默认 CLI 只暴露 certified 任务。candidate 仍可见,用于研究与校准;认证核心之外的任何一组,
默认都不具备基准准入资格。

## 任务形态与难度

一个任务是一个可运行程序加一个隐藏的确定性 oracle。搜索者编辑程序,oracle 为每个候选打分,
分数回到下一轮提案。分数经过归一化:**0 是出厂基线,1 是参考见证解,且不设上限** ——
赢过参考解必须能与追平参考解区分开。

43 个任务分布在七个学科:biology 6、chemistry 10、computer science 4、earth science 3、
engineering 10、mathematics 4、physics 6。它们分成 **24 个优化**与 **19 个发现**,
而这条分界线是数据里最尖锐的东西。

budget 3、三个种子、`greedy_rewrite` + `claude-opus-4-8` 下的最好分数:

| 区间 | 任务数 |
|---|---:|
| ≥ 1.0 —— 赢过参考见证解 | 6 |
| 0.9 – 1.0 | 5 |
| 0.5 – 0.9 | 13 |
| 0 – 0.5 | 13 |
| 恰好 0 | 6 |

| | 中位数 | 得分恰好为 0 |
|---|---:|---:|
| optimization (24) | **0.7747** | 0 |
| discovery (19) | **0.3515** | **6** |

**得零分的全部是发现类任务。** 优化类一个都没有 —— 搜索者总能把一个设计改好一点。发现类则整题弃权:
`RadiativeTransferFit`、`ProspectiveMetaAnalysis`、`ConvectionDiffusionOpt`、`ForceFieldCalibration`、
`QuartzCrystalMicrobalanceLab`、`GeneNetworkIntervention` 都返回 0.0。

这不只是题目太难。其中五个在 `verification/` 下附带 truth-blind 参考实现,只用候选能拿到的信息、
从不读取隐藏世界,得分 0.83 – 0.91。**全面弃权是模型的失败模式,不是对一道不可能的题的正确读法** ——
而在这些参考实现存在之前,两者是无法区分的。

## 简要结论

每个任务现在都是**对着它被打分所依据的那份契约**测出来的。两次扫描,均为 `greedy_rewrite` +
`claude-opus-4-8`:budget 1 下 43 次运行,budget 3 下 258 次种子配对运行(覆盖两种反馈条件),
两份报告都可信、无终局失败。

| | |
|---|---:|
| 模型测量绑定到当前契约 / 两个预算档 × 两种条件 / 三个配对重复 | 43 / 43 |
| 内部科学准入 | 43 / 43 |
| 候选无法打挂其 evaluator | 43 / 43 |
| 确定性 oracle | 43 / 43 |
| **经外部领域专家评审** | **0 / 43** |

**还给不出可演化性差距。** 准入判据是两段式的:开环对照必须先饱和,然后差距扩大才有意义 ——
两段都需要一个预算**阶梯**,而配对扫描只有一个预算点,所以 43 行里 42 行回 `unknown`。
这次买到的是绑定与覆盖度,Δ 仍需一次预算扫描。

在那个单一预算点上,配对差**负向 21 个、正向 11 个、持平 11 个**。这是"低于交叉预算"的样子 ——
三个提案不足以让迭代收回成本 —— 而**不是**反馈无用的证据。判据拒绝从单点下判断,原因正在于此。

**已跑过三个模型**:`gpt-5.5`(615 次运行)、`claude-opus-4-8`(607)、`gpt-5.6-sol`(58)。
它们对任务的排名一致(同族 Spearman 0.959),却**在共享的每一个准入判决上都不一致** ——
交叉预算是"任务与搜索者"的联合性质,所以**更强的模型可以让一个任务失去资格**。

**两个超过 1.0 的分数,都是关于基准的发现,不是关于模型的。** `CirclePacking` 的 1.4406 建立在一个
输给教科书构造 `4 + 2√3` 的错误锚点上;`CalorimeterDesign` 的 1.0121 越过参考见证解,而
`robustness_score` **恰好是 0.0** —— 搜索者在看得见的轴上赢了,在看不见的轴上一无所获。
在分数被压在 1.0 时这两个都不可见。

**最大的现存缺口是 oracle 的来源。** 43 个里只有 7 个把社区标准工具放进 oracle,36 个是本项目手写的
NumPy 降阶实现,且没有一个完成过外部领域评审。在那 36 个上,分数测量的是**与某位作者代码的一致性**,
不是与该领域的一致性。

逐项发现、准入判据的完整判决、标准审计、难度阶梯与开放项,见
[详细发现与审计](.research/findings_and_audits_2026-08.md)。

## 基准组织

任务在磁盘上按大学科分组,而其稳定的公开 ID 保留更具体的元数据 domain:

```text
benchmarks/<Discipline>/<Task>/
task id: <Domain>/<Task>
```

例如 `benchmarks/Physics/DiffractionGratingDesign/` 的稳定任务 ID 是
`Optics/DiffractionGratingDesign`。代码与报告应使用任务 ID,文件系统工具应使用学科路径。

当前的 certified 核心:

- `Chemistry/LennardJonesCluster`
- `Algorithm/MatrixMultiplicationRank`
- `Mathematics/CapSet`
- `Optimization/CirclePacking`
- `Photonics/MultilayerThinFilm`

运行 `python -m sle list --all` 获取权威的实时清单。domain 到 discipline 的映射在
[`sle/benchmark_layout.py`](sle/benchmark_layout.py),准入状态在
[`sle/certification.yaml`](sle/certification.yaml)。

## 社区 oracle 任务

多数 evaluator 只依赖 NumPy、SciPy 和标准库,那些 oracle 是作者写的降阶重实现。七个任务弥补了这个
缺口:把社区标准工具包**放进 oracle**,并在评测时重算锚点,而不是从论文里抄一个数。

| 任务 | Oracle | 类型 |
|---|---|---|
| `QuantumErrorCorrection/QuantumErrorDecoder` | **Stim** 电路 + **PyMatching 2** 最小权完美匹配 | Opt |
| `RNAEngineering/RNAEnsembleDesign` | **ViennaRNA** 配分函数;锚点是它自己的 `inverse_pf_fold` | Opt |
| `MedicinalChemistry/MolecularLeadOptimization` | **RDKit** QED、SA、Lipinski/Veber、PAINS、Tanimoto | Opt |
| `Spectroscopy/SpinSystemInference` | **nmrsim** 完整 Zeeman 加耦合 Hamiltonian | Disc |
| `Algorithm/GraphFromDistances` | **networkx** | Disc |
| `Mathematics/SequenceLawRecovery` | **SymPy** | Disc |
| `QuantumDynamics/HamiltonianLearning` | **QuTiP** | Disc |

标准看的是 **oracle 自己 import 什么**,不是 `verification/` 目录里有什么。
`Exoplanets/RadialVelocityPlanets` 因此不在表内:它的**参考实现**用 astropy 的 Lomb-Scargle,
而它的 evaluator 自己算周期图。参考实现**应该**用社区工具,正是为了能拿它去核对作者的 oracle ——
按目录整体计数会让参考替 oracle 背书,把这条标准读反。

发现类条目都把参考实现放在 `verification/` 下、打分时运行,且每个参考都**刻意不完美** ——
一个得 1.0 的参考不给任务留余量。校准阶梯在各任务的 `references/known_best.md` 里。

## 快速开始

```bash
python -m sle list          # 只列 certified
python -m sle list --all    # 含 candidate

python -m sle eval --task Chemistry/LennardJonesCluster
```

### 安装 oracle 工具包

七个社区 oracle 任务需要各自的领域工具包。`scripts/setup_oracle_env.sh` 记录了安装方式:

```bash
bash scripts/setup_oracle_env.sh --check    # 报告已装了什么
bash scripts/setup_oracle_env.sh            # 安装钉住的版本集
```

### 配置 LLM

```bash
cp sle/conf/llm/openai_compatible.example.yaml \
   sle/conf/llm/local.yaml
export OPENAI_API_KEY=your_key_here
python -m sle smoke
```

`local.yaml` 已被 git 忽略。配置解析顺序为 `--llm-config` → `FS_LLM_CONFIG` →
`conf/llm/local.yaml` → 已提交的示例。OpenAI 兼容的 Chat Completions 与 Responses 两种协议都支持。
推理模型在 chat 协议上会拒绝 `max_tokens`,这类模型需设
`chat_max_tokens_field: max_completion_tokens`。**永远不要提交凭证。**

### 跑一条优化轨迹

```bash
python -m sle run \
  --task Chemistry/LennardJonesCluster \
  --algorithm greedy_rewrite \
  --budget 10 \
  --seed 0 \
  --workdir runs/lj/seed-0
```

可用算法:`greedy_rewrite`(内置,单一在位者、整文件重写)、`openevolve`(0.2.26,Python ≥3.10)、
`abmcts`(TreeQuest AB-MCTS-A,Python ≥3.11)、`shinkaevolve`。指名的后端若不可用会**显式失败**,
绝不静默回退。

`selection_blind` 是严格的开环对照:提案永远只看到冻结的基线及其公开指标,评测结果仅保留用于
离线选择。

## 评测与安全模型

受信父进程 import 每个隐藏 oracle。候选代码通过带类型的 JSON-RPC 边界、在 Bubblewrap 内单独运行,
无网络命名空间、只读挂载、私有临时文件系统、CPU/内存/文件/描述符/进程限制、seccomp 阻断进程与线程创建、
固定数值线程数,以及一套**标签盲的失败分类** —— 它把候选可控的异常文本从搜索反馈中剔除。

site-packages 是按**实际会 import 它们的解释器**解析的,而不是按父进程 —— 当搜索后端在自己的
虚拟环境里运行 harness 时,两者不同。

这个设计降低了常见的泄漏与主机访问风险;它**不**证明不存在训练数据污染、语义捷径、模拟器误差
或隐藏的科学混淆。

## 任务包契约

```text
<Task>/
├── Task.md                       # 智能体可见的任务描述
├── TASK_CARD.yaml                # 科学证据与评审记录
├── solution.py                   # 弱但合法的基线
├── frontier_eval/
│   ├── metadata.yaml             # 逻辑 domain 与任务元数据
│   ├── initial_program.txt
│   ├── candidate_destination.txt
│   ├── entrypoint.txt
│   ├── constraints.txt
│   ├── agent_files.txt
│   ├── readonly_files.txt
│   └── candidate_packages.txt    # 可选;暴露给候选的领域工具包
├── verification/
│   ├── evaluator.py              # 隐藏的冻结 oracle
│   └── requirements.txt          # 可选;钉住的 oracle 依赖
└── references/
    └── known_best.md             # 不设上限的任务必需
```

evaluator 至少返回有限数值的 `combined_score` 与 `valid` 字段。**加一个包只是让它可被发现,
不等于认证。** 完整契约与认证要求见 [`CONTRIBUTING.md`](CONTRIBUTING.md)。

## 认证与证据

认证状态描述的是**证据质量,不是任务难度**:`certified` 已进入默认基准,`candidate` 保留用于校准但
缺少一项或多项门槛,`quarantined` 标记可复现的实质缺陷。

| 证据 | 结果 | 范围 |
|---|---|---|
| [认证审计 v66](experiments/task_certification_audit_2026-08-15_v66.json) | 5 certified / 38 candidate / 0 quarantined | 当前 43 包修订下的清单与准入门槛 |
| [安全基线 v49](experiments/secure_baseline_determinism_2026-08-18_v49.json) | 43/43 确定、有效、fail-closed | 每任务两次基线评测,取自 evaluator 修复之后 |
| [evaluator 抗崩溃](experiments/evaluator_crash_resistance_2026-08-18_v1.json) | 43 个中 0 个能被候选打挂 | 每任务三种刻意写坏的提交 |
| [重测 budget 1](experiments/recontract_2026-08_b1_s0_v2.json) | 43/43 运行,可信 | 单种子 `normal`,对当前契约 |
| [重测 budget 3 配对](experiments/recontract_2026-08_b3_paired_v2.json) | 258/258 运行,可信 | 三种子,`normal` 对 `selection_blind` |
| [安全审计 v49](experiments/security_audit_2026-07-27_v49.json) | 23/23 测试通过 | 沙箱与协议回归 |
| [GPT-5.6 50 题普查](experiments/gpt56_science_census_analysis_2026-08-06_v1.json) | 50/50 格;36/50 有效提案 | budget-1 筛查;挑战门槛未过 |
| [Track F 确证分析](experiments/track_f_analysis_2026-07-26_v1.json) | 未识别出反馈优势 | 预注册,n=48/臂,在 ActiveLawDiscovery 上 |

## 复现检查

```bash
python -m unittest -v tests.test_benchmark_layout tests.test_secure_eval
python scripts/run_security_audit.py --output /tmp/security.json
python scripts/audit_tasks.py --output /tmp/certification.json
python scripts/audit_benchmark_standards.py --output /tmp/standards.json
python scripts/audit_theme_fit.py --output /tmp/theme.json
python scripts/report_admission_criterion.py --runs runs --output /tmp/admission.json
python scripts/report_cross_model.py --runs runs --output /tmp/cross_model.json \
  --admission /tmp/admission.json
python -m unittest discover -s tests -q
```

机器可读的报告都包含自己的命令、Git 修订、限定范围的源码树状态、变更路径、执行状态与信任判定。
**一份带日期的产物,只有在它声明的检查于一个干净的已知修订上通过时,才算可信证据。**

## 贡献

见 [`CONTRIBUTING.md`](CONTRIBUTING.md)。

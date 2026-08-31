# Scientist's Last Exam

Scientist's Last Exam (SLE) 是一个研究原型,面向**跨领域、可执行、预算受限的科学生成式优化**。
智能体编辑一个可运行的程序,一个冻结的确定性 oracle 为每个候选打分,基准同时记录最好的可行产物
和找到它所用的、计入成本的轨迹。

它要回答的不是"模型能不能考一次高分",而是**"给模型反馈和更多预算,它在科学上会不会变得更好"**。

同期文献恰好沿这条线分开:SEE([arXiv:2608.06931](https://arxiv.org/abs/2608.06931))是科学,
但作为静态题集说不了迭代有没有用;OPT-BENCH([arXiv:2605.08904](https://arxiv.org/abs/2605.08904))
用无记忆对照臂测量迭代,工具是对的,但它的三十个环境是机器学习与 NP-hard 问题。
**两者都不在交集上** —— 一个有冻结领域 oracle 的科学问题,而被测量的是反馈会不会累积。

本仓库受 [Frontier-Engineering](https://github.com/EinsiaLab/Frontier-Engineering) 启发,
与 [arXiv:2601.21165](https://arxiv.org/abs/2601.21165) 中同名的文本题基准无关。

> 更高的模拟器或验证器分数,只能证明在**已登记的 oracle 内部**做了优化。它本身不能确立自主科学发现、
> 机制恢复、物理验证或真实世界效用。

## 速览

- **43 个任务包**,7 个学科,分成 **24 个优化**与 **19 个发现**。5 个 `certified`、38 个 `candidate`,
  隔离区为空;默认 CLI 只暴露 certified。
- 无网络 Bubblewrap 沙箱做确定性黑盒评测,oracle 在受信父进程,搜索可见指标走严格白名单。
- 内置迭代重写基线,外加 OpenEvolve、AB-MCTS、ShinkaEvolve 三个后端。
- 实验报告按哈希绑定 Git 修订、命令、源码树状态与信任判定 ——
  **无法绑定到产出它的运行时的证据会被拒绝,而不是被悄悄复用**。
- **7 个 oracle 使用社区标准科学工具**(Stim + PyMatching、RDKit、ViennaRNA、nmrsim、networkx、
  SymPy、QuTiP),在评测时重算锚点。
- **6 个任务**目前被证明能测量迭代改进,其中 3 个依赖的饱和结论会被它们自己的补充种子推翻。

## 任务形态与难度

一个任务是一个可运行程序加一个隐藏的确定性 oracle。搜索者编辑程序,oracle 打分,分数回到下一轮提案。
分数经过归一化:**0 是出厂基线,1 是参考见证解,且不设上限** —— 赢过参考解必须能与追平它区分开。

发现类任务另外分开报告**机制恢复、假发现率、校准拒答**,因为一个被最大化的标量说不出一个发现
**对不对**。每题包含三种世界:机制在模型族内(该找出来)、机制在族外、以及根本没有机制(该拒答)。
归一化让**全面弃权恰好得零**。

budget 3、三个种子、`greedy_rewrite` + `claude-opus-4-8` 下的最好分数:6 个任务 ≥ 1.0(赢过参考
见证解)、5 个在 0.9–1.0、13 个在 0.5–0.9、13 个在 0–0.5、6 个恰好为 0。按类型拆开:

| | 中位数 | 得零 |
|---|---:|---:|
| optimization (24) | **0.7747** | 0 |
| discovery (19) | **0.3515** | **6** |

**得零分的全部是发现类。** 优化类一个都没有 —— 搜索者总能把设计改好一点。发现类则整题弃权。
这不只是题目太难:其中五个附带 truth-blind 参考实现(只用候选能拿到的信息),得分 0.83 – 0.91。
**全面弃权是模型的失败模式,不是对一道不可能的题的正确读法** —— 而在这些参考存在之前,两者无法区分。

## 简要结论

每个任务现在都是**对着它被打分所依据的那份契约**测出来的:budget 1 下 43 次运行,
budget 3 下 258 次种子配对运行,两份报告都可信、无终局失败。

| | |
|---|---:|
| 模型测量绑定当前契约 / 两个预算档 × 两种条件 / 三个配对重复 | 43 / 43 |
| 内部科学准入 / 候选无法打挂 evaluator / 确定性 oracle | 43 / 43 |
| **经外部领域专家评审** | **0 / 43** |

**还给不出可演化性差距。** 判据是两段式的:开环对照必须先饱和,然后差距扩大才有意义 ——
两段都需要预算**阶梯**,而配对扫描只有一个预算点,所以 43 行里 42 行回 `unknown`。
单点上的配对差是负向 21 个、正向 11 个、持平 11 个,这是"低于交叉预算"的样子,
**不是**反馈无用的证据。

**已跑过三个模型**:`gpt-5.5`(615 次运行)、`claude-opus-4-8`(607)、`gpt-5.6-sol`(58)。
它们对任务排名一致(同族 Spearman 0.959),却**在共享的每一个准入判决上都不一致** ——
交叉预算是"任务与搜索者"的联合性质,所以**更强的模型可以让一个任务失去资格**。

**两个超过 1.0 的分数,都是关于基准的发现。** `CirclePacking` 的 1.4406 建立在一个输给教科书构造
`4 + 2√3` 的错误锚点上;`CalorimeterDesign` 的 1.0121 越过见证解,而 `robustness_score` 恰好是 **0.0** ——
搜索者在看得见的轴上赢了,在看不见的轴上一无所获。分数被压在 1.0 时这两个都不可见。

**oracle 的来源决定分数能被读到多远。** 7 个把社区标准工具放进 oracle,其余以 NumPy/SciPy 实现所
描述的科学 —— 后者上的分数是对该任务所建模型的一致性度量,这正是外部领域评审要覆盖的部分。

逐项发现、准入判据的完整判决、标准审计、难度阶梯与开放项,见
[详细发现与审计](.research/findings_and_audits_2026-08.md)。

## 基准组织

任务在磁盘上按大学科分组,而稳定的公开 ID 保留更具体的 domain —— 例如
`benchmarks/Physics/DiffractionGratingDesign/` 的 ID 是 `Optics/DiffractionGratingDesign`。
代码与报告用任务 ID,文件系统工具用学科路径。

当前 certified 核心:`LennardJonesCluster`、`MatrixMultiplicationRank`、`CapSet`、
`CirclePacking`、`MultilayerThinFilm`。`python -m sle list --all` 是权威的实时清单;
映射在 [`sle/benchmark_layout.py`](sle/benchmark_layout.py),准入状态在
[`sle/certification.yaml`](sle/certification.yaml)。

### 社区 oracle 任务

七个任务把社区标准工具包**放进 oracle**,并在评测时重算锚点,而不是从论文里抄一个数:

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
`Exoplanets/RadialVelocityPlanets` 因此不在表内:它的**参考实现**用 astropy,而 evaluator 自己算
周期图 —— 参考**应该**用社区工具,正是为了能拿它去核对 oracle,按目录整体计数会把这条标准读反。

## 快速开始

```bash
python -m sle list                                    # 只列 certified,--all 含 candidate
python -m sle eval --task Chemistry/LennardJonesCluster

bash scripts/setup_oracle_env.sh --check              # 社区 oracle 工具包:检查
bash scripts/setup_oracle_env.sh                      # 安装钉住的版本集

cp sle/conf/llm/openai_compatible.example.yaml sle/conf/llm/local.yaml
export OPENAI_API_KEY=your_key_here
python -m sle smoke

python -m sle run \
  --task Chemistry/LennardJonesCluster \
  --algorithm greedy_rewrite --budget 10 --seed 0 \
  --workdir runs/lj/seed-0
```

`local.yaml` 已被 git 忽略,配置解析顺序为 `--llm-config` → `FS_LLM_CONFIG` →
`conf/llm/local.yaml` → 已提交的示例。推理模型在 chat 协议上会拒绝 `max_tokens`,需设
`chat_max_tokens_field: max_completion_tokens`。**永远不要提交凭证。**

可用算法:`greedy_rewrite`(内置,单一在位者、整文件重写)、`openevolve`、`abmcts`、`shinkaevolve`。
指名的后端若不可用会**显式失败**,绝不静默回退。`--feedback-mode selection_blind` 是严格的开环对照:
提案永远只看到冻结的基线及其公开指标。

## 评测与安全模型

受信父进程 import 每个隐藏 oracle。候选代码通过带类型的 JSON-RPC 边界、在 Bubblewrap 内单独运行:
无网络命名空间、只读挂载、私有临时文件系统、CPU/内存/文件/描述符/进程限制、seccomp 阻断进程与线程创建、
固定数值线程数,以及**标签盲的失败分类** —— 把候选可控的异常文本从搜索反馈中剔除。
site-packages 按**实际会 import 它们的解释器**解析,而不是按父进程。

这降低了常见的泄漏与主机访问风险;它**不**证明不存在训练数据污染、语义捷径、模拟器误差
或隐藏的科学混淆。

## 任务包契约

```text
<Task>/
├── Task.md                       # 智能体可见的任务描述
├── TASK_CARD.yaml                # 科学证据与评审记录
├── solution.py                   # 弱但合法的基线
├── frontier_eval/                # metadata.yaml、entrypoint.txt、constraints.txt、
│                                 # candidate_packages.txt 等
├── verification/
│   └── evaluator.py              # 隐藏的冻结 oracle
└── references/
    └── known_best.md             # 不设上限的任务必需
```

evaluator 至少返回有限数值的 `combined_score` 与 `valid`。**加一个包只是让它可被发现,不等于认证。**
完整契约与认证要求见 [`CONTRIBUTING.md`](CONTRIBUTING.md)。

## 证据

认证状态描述的是**证据质量,不是任务难度**。

| 证据 | 结果 |
|---|---|
| [认证审计 v66](experiments/task_certification_audit_2026-08-15_v66.json) | 5 certified / 38 candidate / 0 quarantined |
| [安全基线 v49](experiments/secure_baseline_determinism_2026-08-18_v49.json) | 43/43 确定、有效、fail-closed |
| [evaluator 抗崩溃](experiments/evaluator_crash_resistance_2026-08-18_v1.json) | 43 个中 0 个能被候选打挂 |
| [重测 budget 1](experiments/recontract_2026-08_b1_s0_v2.json) | 43/43 运行,可信 |
| [重测 budget 3 配对](experiments/recontract_2026-08_b3_paired_v2.json) | 258/258 运行,可信 |
| [安全审计 v49](experiments/security_audit_2026-07-27_v49.json) | 23/23 测试通过 |
| [GPT-5.6 50 题普查](experiments/gpt56_science_census_analysis_2026-08-06_v1.json) | 50/50 格;36/50 有效提案 |
| [Track F 确证分析](experiments/track_f_analysis_2026-07-26_v1.json) | 未识别出反馈优势(预注册,n=48/臂) |

**一份带日期的产物,只有在它声明的检查于一个干净的已知修订上通过时,才算可信证据。**

## 复现检查

```bash
python -m unittest discover -s tests -q
python scripts/run_security_audit.py --output /tmp/security.json
python scripts/audit_tasks.py --output /tmp/certification.json
python scripts/audit_benchmark_standards.py --output /tmp/standards.json
python scripts/report_admission_criterion.py --runs runs --output /tmp/admission.json
python scripts/report_cross_model.py --runs runs --output /tmp/cross_model.json \
  --admission /tmp/admission.json
```

## 贡献

见 [`CONTRIBUTING.md`](CONTRIBUTING.md)。

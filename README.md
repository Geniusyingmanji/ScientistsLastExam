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

这个交集就是本仓库的目的。[任务是否测量迭代](#任务是否测量迭代)给出判据,
[是否满足基准自身的标准](#是否满足基准自身的标准)给出底下科学是否真实的审计。
今天诚实的答案是:两边的数字都不大。

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

[任务形态与难度](#任务形态与难度)给出难度画像,[当前状态](#当前状态)给出覆盖度,
[说明了什么,没说明什么](#说明了什么没说明什么)给出边界。

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

## 当前状态

每个任务现在都是**对着它被打分所依据的那份契约**测出来的。两次扫描,均为 `greedy_rewrite` +
`claude-opus-4-8`:budget 1 下 43 次运行,budget 3 下 258 次种子配对运行(覆盖两种反馈条件)。
两份报告都可信,无终局失败。

| | |
|---|---:|
| 模型测量绑定到当前契约的任务 | 43 / 43 |
| 两个预算档 × 两种反馈条件齐备的任务 | 43 / 43 |
| 有三个配对对照重复的任务 | 43 / 43 |
| 内部科学准入 | 43 / 43 |
| 候选无法打挂其 evaluator 的任务 | 43 / 43 |
| 确定性 oracle | 43 / 43 |
| 冻结的测量健康 cohort | 7 / 7 |
| **经外部领域专家评审的任务** | **0 / 43** |

已跑过三个模型:`gpt-5.5`(615 次记录运行)、`claude-opus-4-8`(607 次)、`gpt-5.6-sol`(58 次)。
它们对任务的排名一致 —— 同族 Spearman 0.959 —— 却**在共享的每一个准入判决上都不一致**,
因为交叉预算是"任务与搜索者"的联合性质,而不是任务单独的性质。

## 说明了什么,没说明什么

**它还给不出可演化性差距。** 准入判据是两段式的:开环对照必须先饱和,然后差距扩大才有意义。
两段都需要一个预算**阶梯**,而配对扫描只有一个预算点 —— 所以 43 行里有 42 行回 `unknown`,
原因统一是 *no open-loop run long enough to judge saturation*。这次战役买到的是**绑定与覆盖度**,
Δ 仍然需要一次预算扫描。

在那个单一预算点上,配对差**负向 21 个任务、正向 11 个、持平 11 个**。这正是"低于交叉预算"的样子 ——
三个提案不足以让迭代收回成本 —— 而**不是**反馈无用的证据。判据拒绝从单点下判断,原因正在于此。

**两个超过 1.0 的分数,结果都是关于基准的发现,不是关于模型的。** `CirclePacking` 拿到 1.4406,
装填确实合法 —— 最近的圆心距离相切只差 3.6e-15 —— 但它对的那个 N=13 锚点输给了教科书构造
`4 + 2√3`。`CalorimeterDesign` 拿到 1.0121、越过参考见证解,而 `robustness_score` **恰好是 0.0**:
它的最坏情况效用停在出厂基线。搜索者在**看得见的轴**上赢过了见证解,在**看不见的轴**上一无所获。

在分数被压在 1.0 时,这两个都不可见 —— 它们都会读成"追平了参考解"。

**oracle 大多仍是本项目自己的代码。** 43 个里只有 7 个把社区标准工具放进 oracle;36 个是作者写的
NumPy 降阶实现。没有任何任务完成过外部领域评审。在那 36 个上,分数测量的是**与某位作者代码的一致性**,
不是与该领域的一致性 —— 这是本基准最大的现存缺口。

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

多数 evaluator 只依赖 NumPy、SciPy 和标准库。任务叙述引用真实科学,但那些 oracle 是作者写的降阶
重实现,且没有一个完成过外部领域评审。**在它们上面的分数测量的是与作者 NumPy 代码的一致性,
不是与科学的一致性。**

七个任务弥补了这个缺口。每一个都把社区标准工具包**放进 oracle**,并在评测时重算锚点,而不是从论文里
抄一个数。

| 任务 | Oracle | 类型 | 锚点 |
|---|---|---|---|
| `QuantumErrorCorrection/QuantumErrorDecoder` | **Stim** rotated surface-code 电路,定种采样 | Opt | **PyMatching 2** 最小权完美匹配,每次运行重算;不设上限 |
| `RNAEngineering/RNAEnsembleDesign` | **ViennaRNA** Turner 最近邻模型配分函数;ensemble defect | Opt | ViennaRNA 自己的 `inverse_pf_fold`,三次重启取最好,每次运行重算;不设上限 |
| `MedicinalChemistry/MolecularLeadOptimization` | **RDKit** QED、Ertl–Schuffenhauer SA、Lipinski/Veber、PAINS、Morgan/Tanimoto | Opt | 20 种已上市药物面板中结构互异者的平均成药性,每个 SMILES 对照已发表分子量核验;不设上限 |
| `Spectroscopy/SpinSystemInference` | **nmrsim** 完整 Zeeman 加耦合 Hamiltonian,对角化 | Disc | nmrsim 正演模型的最小二乘拟合,打分时运行 |
| `Algorithm/GraphFromDistances` | **networkx** | Disc | truth-blind 领域参考策略,打分时运行 |
| `Mathematics/SequenceLawRecovery` | **SymPy** | Disc | truth-blind 参考恢复器;按构造正确拒答率 0.50 |
| `QuantumDynamics/HamiltonianLearning` | **QuTiP** | Disc | truth-blind 参考辨识器 |

`Exoplanets/RadialVelocityPlanets` **有意**不在这张表里,而它曾经在。它的参考检测器用 astropy 的
Lomb-Scargle,而它的 evaluator 自己实现周期图 —— 所以 oracle 仍是作者重实现,而这正是这条标准要区分的
东西。此前审计读取 `verification/` 下的所有文件,于是**参考实现替 oracle 背了书**;现在它只跟随
evaluator 自己的 import。这个方向才对:参考实现**应该**用社区工具,正是为了能拿它去核对作者的 oracle。

发现类条目都把参考实现放在 `verification/` 下、在打分时运行,且每个参考都**刻意不完美** ——
一个得 1.0 的参考不给任务留余量。`SpinSystemInference` 的参考恢复了 0.5833 的机制,假发现率 0.250。

校准阶梯在各任务的 `references/known_best.md` 里。

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

## 近期发现

完整记录在 [`.research/`](.research/),每份自带其主张边界。

**一个任务的难度往往在它的提交契约上,不在它的科学上。** 隐藏 evaluator 长度与"提案连**有效**都算不上"
的比例,秩相关是 **-0.675**(39 个任务)—— 最短的 evaluator 接受 92-100%,最长的接受 0-5%。
机制是看得见的而不是推断的:`CalorimeterDesign` 拒绝了 36 个提案中的 36 个,而它自己的基线评测正常,
原因是某个候选写了 `problem["light_yield_per_gev"]`,而键名是 `light_yield_pe_per_active_gev`。
量是真的,名字没写在文档里 —— 提示词只列出了任务传入的 27 个键中的 15 个。

`scripts/audit_documented_keys.py` 在 15 个基线会读输入映射的任务里找到 **7 个**有同样缺陷 ——
24 个未文档化的键,多数是候选必须遵守、却只能靠抄基线才能知道的边界。补上文档没有改动任何 evaluator、
任何分数、任何科学:

| 任务 | 修复前有效率 | 修复后 | 修复前最好分 | 修复后 |
|---|---:|---:|---:|---:|
| `CalorimeterDesign` | 0% | **77%** | 0.0000 | **1.0000** |
| `HeatExchangerDesign` | 66% | **96%** | 0.7665 | **1.0000** |
| `QuartzCrystalMicrobalanceLab` | 58% | **83%** | 0.0000 | 0.0000 |
| `RoomImpulseResponse` | 69% | 73% | 0.4382 | **0.6824** |
| `DistillationColumnDesign` | 38% | 29% | 0.5822 | **0.9960** |
| `ForceFieldCalibration` | 5% | **17%** | 0.0600 | **0.8288** |

`CalorimeterDesign` 此前被列为"需要重新校准的地板任务",那个诊断是错的。
`QuartzCrystalMicrobalanceLab` 把两种失败模式分得很干净:契约问题修好了(58% → 83%),分数仍是 0.0000,
因为剩下的是弃权。两件事让这个缺陷可被发现:被拒候选现在会保留(每次运行五个,只写盘、绝不回喂搜索者),
以及补文档会改动 `Task.md` —— 而它就是提示词 —— 所以重绑工具会**拒绝**为可能已变动的冻结证据重新签名。
详见 [contract_burden](.research/contract_burden_2026-08-14.md)。

**在全部五个得零分的任务上,可运行的参考实现都击败了全面弃权。** "拒绝每个世界是对一道难题的正确读法"
这个说法,此前只靠任务卡里没人执行的散文支撑。五个现在都附带 truth-blind 参考,只用候选能收到的信息:

| 任务 | 模型提案 | 参考实现 | 机制恢复 |
|---|---:|---:|---:|
| `ProspectiveMetaAnalysis` | 0.0000 | **0.9088** | 0.9266 |
| `QuartzCrystalMicrobalanceLab` | 0.0000 | **0.8330** | 0.9585 |
| `RadiativeTransferFit` | 0.0000 | **0.7910** | 0.8606 |
| `ConvectionDiffusionOpt` | 0.0000 | **0.7636** | 0.9724 |
| `GeneNetworkIntervention` | 0.0000 | **0.3926** | 0.8255 |

五个里有三个反复出现同一条教训:**对拟合模型做阈值化会把太多项标记为活跃,因为噪声落在每个参数上**,
于是在 null 世界上制造出一个并不存在的机制。改成当作模型选择问题来答 —— 对支持模式做 BIC、
对边做 BIC 反向消除 —— 把两个分数从 0.16 提到 0.79、从 0.16 提到 0.39。同样的形状还出现过两次:
overtone dispersion 是**趋势**不是离散度(诊断正确率从 10 中 6 提到 10 中 10);另一处的"超出族"检验
问的是合并效应是否落在已发表边界外,**一次都没触发过** —— 因为弯曲的调节关系照样产生完全普通的效应量。
改测二次项显著性后,分数从 0.83 到 0.91,拒答率从 0.0 到 1.0。

写参考实现还暴露了两个别的手段发现不了的 harness 缺陷。`ConvectionDiffusionOpt` 的参考在所有世界上弃权,
而它的 PDE 求解器与 evaluator 的**逐位相同** —— 差别在读传感器时用了双线性而非最近节点,
在声明噪声 6.5e-4 之下,百分之一的采样误差就是四个标准差。**由仪器模型导致的拒答,在分数上与由科学
导致的拒答无法区分。**

**关于这种弃权的三个解释已被排除,剩下的那个是模型本身。** 提示词措辞预测不了它(-0.267,符号还反了),
提交字段是有文档的,声明契约的规模也解释不了(九个任务上 +0.133,两个同为 17 字段的任务弃权率分别是
100% 与 28%)。而参考实现在同样的任务上拿到 0.39 – 0.91,**科学是做得出来的**。
在一个有拒答选项的困难推断面前,这些模型选择拒答而不是尝试,而归一化正确地不为此付钱。
详见 [floor tasks are refusals](.research/floor_tasks_are_refusals_2026-08-14.md)。

**更强的模型可以让一个任务失去资格。** 在两个模型族都跑过的 12 个任务上,准入判决**每一次**都不同,
而且是单向的:一个模型判定合格的,另一个读成 `control_not_exhausted`,因为在同样预算下它的 best-of-N
还在爬 —— 后半段增益 0.028、0.024、0.017 对 0.000。曲线长度、任务版本、搜索者都是匹配的。
交叉预算是任务**与**搜索者的联合性质,所以准入必须表述为一个联合主张。这是判据的代价,不是它的缺陷。

**决定什么可比的哈希,只能覆盖会改变分数的东西。** 两个缺陷让这个守卫拒绝了有效证据:
一行卡片注释改动了每个任务的哈希;而哈希覆盖了任务自己的 `runs/` 输出,于是**任何人跑一次,
任务的身份就变一次**。身份哈希现在排除生成产物,
[`build_task_version_equivalence.py`](scripts/build_task_version_equivalence.py) 通过从 git 对象重放
每个修订的哈希来恢复历史。20 个记录在多个哈希下的任务里,**16 个是同一个任务**。
没有这张表,跨模型比较会从 50 个共享任务掉到 6 个。

**可演化性差距取决于任务,而不只取决于预算。** 两个社区 oracle 任务上的种子配对预算扫描:

| budget | 3 | 5 | 7 | 10 | 15 | 20 |
|---|---:|---:|---:|---:|---:|---:|
| Molecular | +0.311 | **+0.371** | +0.036 | −0.093 | — | — |
| decoder | +0.135 | +0.061 | — | +0.080 | **+0.172** | +0.111 |

Molecular 的差距**不是单调的**:它在 budget 5 达到峰值 —— 八个配对种子八胜,符号检验 p=0.0078 ——
然后坍塌,在 budget 7.8 附近穿过零。decoder 的差距到 budget 20 为止在每个预算上都为正。
同一个搜索者、同一个模型、同一套协议,所以**交叉是任务的性质**。对照臂说明了原因:decoder 的开环从
budget 5 起就平了,而 molecular 的从 0.404 爬到 0.970。一次 molecular 抽样可能落进长右尾,
所以多抽有用;decoder 的单次抽样质量被"一代能写出什么"限制住,所以精炼胜过重抽。

这推出一条比 `Δ > 0` 更锐利的规则 —— 一个任务测量迭代的程度,取决于它的开环对照饱和的程度 ——
而这条规则被证明是**必要但不充分**的,反例就在本仓库里。详见
[evolvability_gap](.research/evolvability_gap_2026-08-09.md) 与
[budget dependence](.research/evolvability_gap_budget_dependence_2026-08-09.md)。

**搜索后端从来没有产出过一个数据点。** 在 2822 次记录的算法调用中,唯一真正跑过的算法是
`greedy_rewrite`。找到六个阻塞、修了四个:沙箱在任何后端虚拟环境下都没挂载任何包;chat 协议硬编码了
`max_tokens`;OpenEvolve 静默丢弃超过 10,000 字符的候选(decoder 任务 40 次迭代中的 29 次,
折合报告分数 0.054);上游 evaluator 超时会中止整个运行。修好之后,`CirclePacking` 三次 oracle 调用
就被解决 —— **从来没有任何 certified 任务被暴露给种群搜索过**,所以记录在案的每一个难度主张,
都是对着 budget 一到三的 greedy 校准出来的。详见
[E0 unblocking](.research/e0_backend_unblocking_2026-08-08.md)。

**种群搜索没有复现 greedy 的反转 —— 方向上如此。** 在 molecular 任务 budget 10 上,greedy 得 −0.093、
六个配对种子输五个,而 OpenEvolve 得 **+0.074**、十二个中赢八个。两个区间都跨零(p = 0.22 与 0.39),
所以这与锁定解释一致但没有确立它。n=10 时的中途读数是 +0.153,是最终值的两倍 ——
那两个缺失的格子是因为崩溃而缺失,但**不是随机缺失**:OpenEvolve 在它们上面得 0.990 和 1.034,
而对照恰好抽到 1.325 和 1.336。**消失的格子必须被找回来,而不是绕开它们做分析。** 详见
[population search](.research/population_search_results_2026-08-09.md)。

## 任务是否测量迭代

**判据是两段式的,两段都必要。**

1. **必要条件** —— 开环对照必须饱和。如果 best-of-N 还在爬,更高的分数只说明抽样够多。
2. **充分条件** —— 在对照已耗尽之后,种子配对的差距必须随预算扩大。

`scripts/report_admission_criterion.py` 对任意有配对运行的任务应用这条判据。当前判决:

| 判决 | 任务数 |
|---|---:|
| 测量迭代 | 7 |
| 测量迭代,但只有一个配对种子撑着 | 1 |
| 反馈**有害** | 5 |
| 反馈有害,但只有一个种子撑着 | 3 |
| 两臂无法区分 —— 差距小到无所谓 | 2 |
| 交叉点在测量范围内 | 3 |
| 对照仍在爬 —— best-of-N 未耗尽 | 12 |
| 筛查过薄(少于三个种子) | 84 行 |
| 地板 —— 对照从未离开零 | 17 |

**5 个 certified 任务没有一个在"测量迭代"名单里。** 认证核心是默认 CLI 暴露的那一组,而在当前证据下
它们全部是 `thin_screen`(各两个种子),不足以判定。认证在本仓库一贯描述的是**证据质量而非难度**,
这就是那个区分的代价:一个任务可以完全通过认证,却仍然测不出迭代改进。

**加种子会缩小合格集合,方向与脆弱性标志所预测的一致。** 必要条件是对开环对照后半段增益的阈值检验,
而报告已声明三个种子足以判定它。枚举已有运行的三种子子集,可以看到
`LowThrustTransfer`、`ProteinStabilityDesign`、`QuantumErrorDecoder` 都会翻转:
`LowThrustTransfer` 在六个种子上读 0.0053(已耗尽),在前三个种子上读 0.0193(未耗尽)。

留一法找不到这个 —— 从六个种子里去掉一个,中位数从不越过阈值,而它在一个刚被种子配对比较标出一个脆弱
判决的清单上报告了零个脆弱判决。**子集必须小到判据自己声称信任的那个规模。**

`ChemicalKinetics/ReactionMechanismFitting` 两个种子前还在这份名单上:它当时是清单里最大的差距,
+0.423、无一败绩;到四个种子时符号反转,现在读作有害,而且同样由一个种子带着。
**任务没有变,变的是证据。**

**反馈起负作用的任务,数量几乎与它明确起正作用的一样多。** `TrussWeightMinimization`、
`RANSCalibration`、`HeatExchangerDesign` 的得分明显**差于**它们自己的开环对照,另有两个在单个种子上
如此读数。这不是 harness 故障:两臂的通过率相当。最清楚的一例是 `TrussWeightMinimization` ——
它落后自己的开环对照 0.37,从 budget 8 起输掉每一个配对种子(去掉最有利的那个种子后仍为 −0.30)。
两臂各有约一半提交通过(开环 0.50 对反馈 0.40),所以不是契约在拒绝反馈臂的工作。开环臂在某个种子上
达到 0.9979,而反馈臂在全部四个种子上的最好成绩是 0.4143:**独立抽样找到了尾巴,锚定在位者则找不到。**

一个测量迭代改进的基准,必须有能力报告"迭代有时会让你付出代价"—— 这一个可以。

**留一种子守卫改变两个判决。** `ForceFieldCalibration` 在 budget 12 读到 +0.0367 的差距,
去掉一个种子后变成 +0.0000 —— 它四个配对种子里只有一个有差距;`CatalystDeactivationLab` 读到的
−0.022 在同样检验下翻正。两者都被报告为"一个种子深",而不是发现。**这个守卫刻意在两个方向上都生效:
一个有害的判决和一个有利的判决,同样容易只靠一个种子撑着。**

### 这甚至算不算对的那类问题

两个审计检查科学与证据。第三个 `scripts/audit_theme_fit.py` 检查它们共同假设的东西:
这个任务是否首先就提出了一个开放式问题。它只读任务包,所以从任务写下的那天起就适用 ——
不像准入判据需要配对运行。

| 检查 | 满足 |
|---|---|
| 连续打分而非达到阈值即付 | 43 / 43 |
| 声明了优化或发现两种形态之一 | 43 / 43 |
| 开放式 —— 锚点本身不是一个正确实现就能达到的解 | 41 / 43 |
| 发现类任务报出全部三个轴 | **19 / 19** |

## 是否满足基准自身的标准

| | |
|---|---:|
| 陈述了抗捷径论证的任务 | 43 / 43 |
| 陈述了科学不变量的任务 | 43 / 43 |
| 引用可解析文献(DOI 或 arXiv)的任务 | 42 / 43 |
| 对开发分数保留了密封划分的任务 | 35 / 43 |
| 锚点为重算而非引用的任务 | **15 / 43** |
| oracle 使用社区标准领域工具的任务 | **7 / 43** |
| 附带可运行参考记录的任务 | **27 / 43** |
| 带难度阶梯的任务 | **8 / 43**,其中一个实测有可用的台阶 |
| 经外部领域专家评审的任务 | **0 / 43** |

前几行是框架,加粗的几行是实质 —— 而实质正是这份清单薄的地方。43 个 oracle 里有 36 个是作者写的
NumPy 降阶实现,所以在它们上面的分数测量的是与那位作者代码的一致性,而不是与该领域的一致性。
任务叙述引用了真实工作;多数 oracle 并不运行它。

锚点那一行是**有意拆开的**。`verification/` 下的参考实现是 evaluator 能跑的东西;卡片里写着锚点
"经过重算"的一句话是一个**主张** —— 抽查发现这句话出现在某个任务上,而同一句话还引用了一个文献值。
把两者合并计数会给出 9,而可运行的证据是 6。

把两个审计交叉起来看,才是诚实的位置。`QuantumErrorDecoder` 是唯一一个**既**测量迭代**又**建立在
社区工具与重算锚点之上的任务。`ProteinStabilityDesign`、`NMRSpectrumFitting`、`LowThrustTransfer`
测量迭代,但打分对的是作者写的 NumPy 重实现,所以它们测的是与那段代码的一致性而非与科学的一致性。
`MolecularLeadOptimization` 则相反:根基扎实,但它的对照还没有耗尽。

详见 [standards audit](.research/benchmark_standards_audit_2026-08-11.md)。

### 最新的任务对判据说明了什么

`RNAEngineering/RNAEnsembleDesign` 是为了补社区 oracle 缺口而建的,然后像其他任务一样过了一遍准入判据。
在四个配对种子上,它的差距在 budget 3 是 +0.0135,到 budget 12 是 −0.0005,而开环均值是 1.0062 ——
搜索者正好坐在 ViennaRNA 自己的配分函数设计器上,反馈既不帮忙也不添乱。判决是 `no measurable
difference`,这是诚实的读法。

这对基准是一个有用的否定结果:一个任务可以有社区 oracle、重算锚点、密封划分和难度阶梯 ——
九项标准里满足八项 —— **却仍然测不出迭代改进**。科学根基与 RSI 适配性是两个独立的性质。

## 难度阶梯

八个任务带 `DIFFICULTY` 层级,好让一个任务饱和之后不必退役。**它们全部停在层级 1**,这意味着
`difficulty_parameterized` 目前断言的是阶梯**存在**,不是阶梯**有用**。
`scripts/report_difficulty_ladder.py` 测量这个差别:它复制任务、在副本里改写 `DIFFICULTY`、
用副本自己的 evaluator 给同一个程序打分,所以已发布的任务一行不动。

第一个这样测的是 `RNAEnsembleDesign`,选它是因为它**既**被归为饱和**又**有阶梯 ——
正是"退役还是升级"这个问题:

| 层级 | 最好候选 | 出厂基线 |
|---|---:|---:|
| 1 | **0.9971** | 0.0 |
| 2 | **0.9422** | 0.0 |
| 3 | 无效 | **无效** |

层级 2 是真台阶:任务在层级 1 上饱和、在层级 2 上不饱和,而基线在两级上都有效,所以归一化仍有锚点。
**这个任务的答案是升级,不是退役。**

层级 3 不是台阶。**基线**在那里给不出合法提交,而一个基线无效的层级什么都测不了 ——
分数以"基线 = 0"归一化,那里没有基线。所以这个三级阶梯只有两级可用。

发现这一点需要基线。只用候选去测,层级 3 读起来是"难到解不出",而在有已知合法的东西跑过去之前,
它与"坏了"无法区分。

下面两个社区 oracle 的阶梯建得更早也更深。层级 1 精确复现已发布的实例与其记录锚点;
没有实测条目的层级会直接抛错,而不是外推。

每个阶梯是一张**实测表而非公式**,因为两个任务都惩罚那个显而易见的公式:

- 在 decoder 上,难度不能靠码距提高。阈值以下,更大的码会让逻辑错误率指数下降,于是锚点不再频繁失败到
  可测量的程度 —— 第一次尝试留下了一个只有 9 次锚点失败的层级 3。每一级改为把物理错误率推向接近 1%
  的电路级阈值。此时 shot 数固定的是**解码工作量**而不是 shot 本身:探测器随 `d²` 增长,
  所以保持高 shot 数会悄悄把层级 2 变成 1.68 倍吞吐测试,而那里反馈臂 29 次失败中有 24 次是超时。
- 在 molecular 任务上,两个旋钮通过参考面板相互作用。收紧多样性上限会缩小保留的组合**并**抬高锚点,
  因为面板是按 QED 从高到低选的,更严格上限的幸存者是更好的药。过了某个点会直接破坏面板。

台阶是按**可演化性差距对预算的形状**放置的,不是按分数。molecular 任务的层级 1 实际上已被解决 ——
本基准产出过的最强提交得 1.3363,而 QED 上限接近 1.35 —— 它的差距在 budget 10 转负。
选择层级 2 是因为它的差距转为单调增长:八个配对种子上从 budget 3 的 −0.011 到 budget 12 的 +0.062。
那个端点的区间包含零;**证据是横跨五个预算点的单调趋势,不是端点本身。**

所有阶梯测量都使用 `greedy_rewrite` 配搜索者 `gpt-5.5`、`reasoning_effort: low`。各任务
`references/known_best.md` 里的校准阶梯是用 GPT-5.6 测的,两者不可比;而且因为交叉是任务与搜索者的
联合性质,台阶位置只对这一组条件成立。

## 依赖本分支前需知

以下几件事是**有意留着敞口**的,而不是被糊过去。

**冻结的测量健康 cohort 通过 7/7,而到达那里的过程才是有意思的部分。** 冻结 cohort 是发布点的快照机制,
不是持续开发期的守卫:每一次 evaluator 改进都会移动任务哈希、解绑挂在它上面的证据。行得通的顺序是
**先定稿 evaluator,测一次,重绑一次**。

`scripts/check_evaluator_inert.py` 负责"测一次":它把冻结产物分别送过冻结修订那版和当前版的 evaluator,
逐键比较两个指标字典。在这个 cohort 上结果是 **6 惰性、1 变动** —— 去掉上限不可能移动一个本来就在
上限之下的分数,除了 `DiffractionGratingDesign`,它的产物 `robustness_score` 确实越过了 1.0。
六个带着一个数字把证据带过来,第七个则把三份绑定全部在当前运行时上重测。重测校准移动了 3004 个键中的
8 个,全在 1e-15 量级。

比 7/7 更值钱的是另外两件事。实质性审计与预检在问同一个问题 —— *这次 evaluator 编辑会不会移动这份证据* ——
却给出不同答案,于是同一个任务在一份报告里通过、在另一份里失败;现在两者从同一条记录读取豁免。
以及,有个测试把校准文件名里的日期钉死了,于是证据一被正当重测它就必然失败 —— 方向完全反了。
它现在断言的是记录在案的 evaluator 哈希。

**`CirclePacking` 的 N=13 锚点是错的,而替代值还没有出处。** 该任务对着 7.6274 归一化(号称最小已知
方形边长),而 `4 + 2√3 = 7.4641` 是任何人都能写下的构造,并且有一次记录运行达到了经验证合法的
7.4632466。**一个输给教科书装填的"已知最优"不是已知最优**,所以建立在它上面的 1.4406 ——
以及随之而来的 `saturated_on_ramp` 分类 —— 在这个数字修正之前不应被引用。

两次尝试在本地推导替代值,得到的结果都**比现有锚点更差**(7.8059 与 7.7042),所以什么都没改:
交付一个更弱的参考是在降低标准,不是在纠正它。这个失败本身是有信息量的 —— 朴素搜索离 7.4632 差得远,
**说明任务是有区分度的,错的是尺子而不是题目**。
`tests/test_external_anchors_are_checkable.py` 保证这仍是清单里唯一一个对着"本地无法重新推导的字面量"
归一化的任务。详见 [write-up](.research/circle_packing_anchor_defect_2026-08-18.md)。

**受信运行时变了,而重新认证是一个没人做过的决定。** 冻结的分析产物绑定在 `runtime_source_sha256` 上,
所以编辑 `sle/evaluate.py` 或 `sle/trusted_driver.py` 会解绑它们 —— 而两者都被编辑过,
为的是把 evaluator 失败的原因带到运维日志。`tests/test_runtime_migration.py` 因此失败,这是正确的。

重跑迁移审计给出的是变化的**形状**而非判决:**14 个保留产物上 654 处数值差异,最大 0.1536,
以及零处失败分类变化**。哪些候选算有效或无效完全没动,只有分数动了 —— 这与 evaluator 修复和去掉上限
一致,而与那两处日志编辑无关。登记一份新审计等于宣布新数字才是对的。这是站得住的 ——
去掉上限本就是有意为之 —— 但它是一个**治理判断**,所以被留作判断,而不是通过改一个常量推过去。
详见 [runtime governance](.research/runtime_change_governance_2026-08-09.md)。

那九个曾与它一起失败的逐任务分析测试已经修好。它们读取的 `runs/` 路径是**产出机器上的绝对路径**,
于是其他任何检出都会撞上容纳性检查并报 "workdir is outside repository" —— 听起来像安全拒绝,
实际是可移植性缺陷。现在路径按**正在读取的那个仓库**放置,而没有运行目录的检出会**带原因跳过**
而不是报错,因为**缺数据的读者不是在看坏证据的读者**。

**重测战役的代价,以及为什么它的每一步都大声拒绝。** 结论在[当前状态](#当前状态);这一段是给维护者的。
战役之前,没有任何记录运行绑定在当前任务契约上,每一项由模型推导的健康检查都读零 ——
`ActiveLawDiscovery` 的匹配对照计数和 `RNAInverseDesign` 的首个有效步分别读 0,而它们曾读 48 和 1。
**什么都没有被撤回。** 证据是**被解绑**了,这是另一回事,而且可恢复,修法是重跑而不是重签。

随后一次修复引发了连锁,它是这些绑定应有行为最清楚的例证。修好三个"候选能打挂"的 evaluator 移动了
它们的任务契约,解绑了它们的模型证据,解绑了它们的安全基线,把内部科学准入从 43 压到 40。
在 budget 1 重跑那三个任务恢复了模型证据,而准入**仍是** 40 —— 安全基线是一份全局文档,
在档的那份早于修复。重跑它才恢复 43/43。**四个环节,四次拒绝,没有一次是静默的。**

**在看得见的轴上赢过参考解,不等于解决了任务。** `CalorimeterDesign` 拿到 **1.0121**、越过参考见证解,
而 `robustness_score` **恰好是 0.0** —— 它的最坏情况效用停在出厂基线。

这是任务在按设计工作:稳健性是 evaluator-only,正是为了不让它被直接优化。它暴露的是**饱和分类器的
盲点** —— 该分类器只凭 `combined_score`(搜索者唯一收到的指标)决定退役,会退掉一个有一半没被碰过的
任务。判决现在会说明它是关于哪个指标的,而 `scripts/report_saturation_hidden_axes.py` 会给最好的记录
候选重新打分以读出隐藏轴,因为可见性过滤在写入前就把它们剥掉了。七个饱和任务里有一个处于这种状态。

这一条和 `CirclePacking` 的锚点,在分数被压在 1.0 时都不可见 —— 两者都会读成恰好 1.0,
与"仅仅追平参考解"无法区分。这正是移除上限的目的,而它最先浮出来的两样东西,都是**基准的缺陷**
而不是模型的成绩。

**候选曾能打挂三个 evaluator,而崩溃的代价是一整个 cohort,不是一个候选。** 一次 129 块的配对扫描
返回四个终局失败,每一个只报 `trusted evaluator internal failure` —— 没有任务、没有行号、没有原因 ——
而这四个让整份战役报告作废。

那句固定措辞是**有意**的:异常字符串不得把 evaluator 内部或隐藏值带回给候选。但基础设施失败会
**中止运行**而不是给任何东西打分,所以在那条路径上没有下游搜索者需要保护。原因现在写进受信驱动的
stderr,并且只在运行已被放弃的地方附加,让这种分离由结构保证而非靠人记住。

原因一可见,一次运行就找到了:`KeyError: 'abstained'`。evaluator 在"世界评分抛异常"时构造的行,
比"评分成功"时构造的行少几个键,而后来加的 `discovery_coverage`(发现三元组的第四列)正好读其中一个。
第三个任务则**根本没有失败路径**:控制器返回字典时直接从 `float()` 抛出。

`scripts/check_evaluator_survives_bad_candidates.py` 现在对全清单问这个问题:给每个 evaluator
喂三种会失败的候选 —— 一个抛异常、一个返回 `{}`、一个返回字符串 —— 看它是把候选判零还是自己死掉。
曾经是三个任务崩溃,现在是 **43 个里 0 个**,共 129 个用例。

这个检查的结构化版本先写过一次然后扔掉了。它比较两个分支的键集合,标出了五个可执行检查刚刚放行的任务,
因为**一个键缺不缺要看聚合走的是哪个列表**。一个比它所代表的性质更严格的不变量,什么也买不到,
只会换来一个常红的测试套件。

**有一个 oracle 不是函数,而头条分数把它藏住了。** 43 任务的确定性扫描返回 42/43。
`RNAEnsembleDesign` 失败,因为 ViennaRNA 的设计器在 start 参数为 `None` 时,会从 C 库内部一个
任务自己的 `random.Random(seed)` 够不到的生成器里抽随机起始序列。看得见的症状是锚点缺陷在 1e-4 抖动;
**有破坏性的那个是:锚点落在接受带边缘的目标会在实例集合里进进出出** —— 于是**哪些实例存在**都在变,
两次打分根本不可比。而 `combined_score` 两次都是 0.0,所以头条数字什么也没显示。

定种现在**按调用输入进行**,因为候选是任意代码、可能先从同一个生成器抽走若干个;在 import 时定一次
会让其后每一次抽取都错位。三个进程现在一致到小数点后十位,
`tests/test_oracle_rng_is_pinned.py` 把这个问题问向整个清单,而不是这一个任务。

**新任务尚未登记为成熟度证据。** 它们通过 `scripts/audit_tasks.py` 且任务卡零问题、出现在实时清单里,
但它们的测量还不是 `experiments/` 下的可信产物,所以成熟度账本不把它们算作内部已准入。
每次运行都记录自己的 `task_contract_sha256`,所以基础工作已经做好。

**四个发现类任务报不出假发现率。** 它们的 evaluator 确实在测量它,但把分子作为**计数**发布、
缺少能让它成为比率的世界计数,所以发现三元组对它们无法补全。
`scripts/report_discovery_triple.py` 现在把这种情况与"某个轴从未被测量"分开,因为两者需要不同的修法。
补上分母会编辑任务包,从而重绑该任务的分析产物 —— 包括 Track F 的否定结果 ——
所以这是一个治理步骤而非清理,已留作一个刻意的决定。

沙箱本身经过验证完好:`tests.test_secure_eval` 通过,`scripts/run_security_audit.py` 以
`trusted_evidence: true` 通过 23/23。

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

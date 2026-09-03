# 为 Scientists' Last Exam 贡献

当前同时做两件事:**加固已有清单**,以及按 `sle/conf/exam_taxonomy.yaml` 的空格扩 task。
新包一律 `candidate`,被发现只让它在 `--all` 下可见;进入默认基准仍要过下面的认证门槛,
不要自我认证。SFE / HLE / sgi-bench 写在 taxonomy 的 `out_of_scope` 里,不是本仓库的题型。

> **欢迎 AI 辅助的贡献。** 但请自己核验所有 oracle 代码与参考值 —— 不要把科学正确性完全交给 AI。

---

## 任务要求

每个 certified 任务必须满足**全部七条**:

1. **博士/专家级难度下限。** 任务须要求博士层次的领域知识、进阶数值优化,或当前的研究性启发式。
   不要把教学题、教科书习题、玩具演示或入门级任务作为基准条目提交。
2. **连续、可改进的指标。** oracle 返回一个数值 `combined_score`,且它能被有意义地改进 ——
   不是二值的通过/失败。
3. **确定性的冻结 oracle。** 同一个候选程序 → 同样的分数。不用 LLM 评判,不联网,
   没有未定种的随机性。
4. **本地可运行。** 纯 CPU 的 hard 任务应在几分钟内完成;flagship 任务可以用 GPU 或更重的资产,
   前提是依赖与预算都写清楚。
5. **黑盒安全。** 智能体不得读到 oracle 代码、测试划分的答案或验证内部。候选在受限沙箱中运行,
   只有受信父进程 import oracle 并产出指标。
6. **科学意义。** 分数改进要对应真实的科学价值(更好的算法、更好的分子设计、更低的能量……)。
   为基线与已知最优值提供可引用的出处。
7. **可审计的任务卡与评审。** 提供 `TASK_CARD.yaml`,写明科学问题、产物语义、方程/oracle、
   归一化、稳定的 DOI/arXiv/URL 标识、不变量、已知捷径、许可与污染说明,以及领域与 evaluator
   两侧的评审状态。**没有这些证据的目录只能停在 `candidate`。**

### 本项目踩过的坑,已成为硬要求

以下几条都来自实际发生过的缺陷,每条都有脚本在查:

- **确定性要一直查到库内部。** 定住任务自己的 `random.Random(seed)` **不够**。社区库可能有
  Python 的 `random` 够不到的私有随机源 —— 例如 ViennaRNA 的设计器在 start 参数为 `None` 时会从
  C 库内部抽随机起始序列。曾因此让**被评测的实例集合在两次运行之间发生变化**,而头条分数看不出来。
  定种要**按调用输入进行**,不能在 import 时定一次:候选是任意代码,可能先抽走若干个随机数。
  `tests/test_oracle_rng_is_pinned.py` 扫描全清单。
- **候选打不挂 evaluator。** 写坏的提交(抛异常、返回 `{}`、返回字符串)应当**得零分**,
  而不是让 evaluator 自己崩溃。崩溃会中止整个运行,于是一个坏提交毁掉一整个 cohort 的证据。
  常见成因是"评分成功"与"评分抛异常"两条分支构造的行**键不一致**,而某个聚合读了只有前者才有的键。
  用 `python scripts/check_evaluator_survives_bad_candidates.py --task <Domain>/<Task>` 自查。
- **提交契约必须写进 `Task.md`。** 候选只能靠抄基线才能知道的输入键名或边界,会把**契约难度**
  混进**科学难度**。实测中隐藏 evaluator 的长度与"提案连有效都算不上"的比例秩相关 **-0.675**;
  补上键名文档后,有任务的有效率从 0% 升到 77%,分数从 0.0 升到 1.0,而 evaluator 一行未改。
  用 `python scripts/audit_documented_keys.py --output /tmp/keys.json` 自查。
- **锚点要可重新推导。** 由 evaluator 重算,或以 `verification/` 下可运行的参考实现交付。
  若确实要对着一个本地无法核对的字面量(例如已发表纪录)归一化,必须在 `references/known_best.md`
  里写明来源 —— 曾有一个"已知最优"输给了任何人都能写下的教科书构造。
  `tests/test_external_anchors_are_checkable.py` 保证这类任务保持有意且有界。

---

## 任务目录结构

每个任务位于 `benchmarks/<Discipline>/<Task>/`,由 harness **自动发现**。大的物理学科**有意**与
`metadata.yaml` 里更细的 `domain` 分开:后者保留稳定的公开任务 ID `<Domain>/<Task>`。
新的 metadata domain 必须先在 `sle/benchmark_layout.py` 中登记。

```
benchmarks/
└── <Discipline>/                     # 下列七个大类之一
    └── <Task>/                       # 例如 LennardJonesCluster、CapSet
        ├── Task.md                   # [必需] 智能体可见的任务描述
        ├── TASK_CARD.yaml            # [认证必需] 证据与评审
        ├── solution.py               # [必需] 弱但合法的基线程序
        ├── frontier_eval/            # [必需] 黑盒评测契约
        │   ├── metadata.yaml         # 任务元数据(见下)
        │   ├── initial_program.txt   # 指向基线文件(例如 "solution.py")
        │   ├── candidate_destination.txt  # 智能体编辑的文件
        │   ├── entrypoint.txt        # solution.py 须导出的可调用对象名
        │   ├── constraints.txt       # 展示给智能体的自然语言约束
        │   ├── agent_files.txt       # 允许智能体看到的文件
        │   └── readonly_files.txt    # 智能体不得修改的文件
        ├── verification/             # [必需] 隐藏 oracle —— 智能体绝不可见
        │   └── evaluator.py          # 冻结的打分函数
        └── references/               # [可选] 数据、配置、已知最优记录
            └── known_best.md         # 已知最优值与出处(不设上限的任务必需)
```

七个顶层学科:`Biology`、`Chemistry`、`ComputerScience`、`EarthScience`、`Engineering`、
`Mathematics`、`Physics`。

### `frontier_eval/metadata.yaml`

```yaml
domain: Chemistry                    # 稳定的逻辑 domain(不是顶层目录名)
task: LennardJonesCluster            # 任务目录名
difficulty: hard                     # hard | flagship
tier: T2                             # T2(专家)| T3(flagship)
oracle_type: analytical              # analytical | physical_sim | dataset_oracle | neural_surrogate
score_mode: clipped                  # clipped(压在 [0,1])| uncapped(相对 SoTA,>1 表示超越)
gpu_required: false
eval_time_seconds: 5                 # 单次评测的大致墙钟时间
science_metric: <name>               # 主指标的可读名称
reference_baseline: <description>    # 初始程序做了什么
reference_sota: <description>        # 已知最优结果及其出处
citation: "Author, Journal, Year"    # 可引用的出处
```

### `frontier_eval/entrypoint.txt`

其中写一个可调用对象名,例如 `build_cluster`、`solve`、`build_capset`。受信 evaluator 会 import
`verification/evaluator.py`;它**只**通过沙箱化的 JSON-RPC worker 调用候选。

### `verification/evaluator.py` 契约

oracle 须定义 `evaluate(candidate_callable)`,返回的字典**至少**包含:

```python
{
    "combined_score": float,   # 主指标(越大越好;失败时 -1e18)
    "valid": float,            # 候选给出合法结果为 1.0,否则 0.0
}
```

可选字段:`feasibility_rate`、`constraint_violations`、`raw_score`、`per_instance` 等。

**发现类任务另有要求。** 三个轴必须**分开**报出、永不平均:机制恢复、假发现率、校准拒答。
再加一列"是否尝试过发现"——没有它,"每个提案都拒绝了每个世界"与"科学太难做不出来"在报表上一样,
而这两种情况需要相反的处置。归一化要让**全面弃权恰好得零**:

```python
always_abstain = unsupported_count / len(records)
normalized = (raw_mechanism - always_abstain) / (1.0 - always_abstain)
```

比率类指标要发布**分母**。只发布计数会让三元组无法补全 —— 已有四个任务卡在这一步。

---

## 打分模式

| 模式 | 何时使用 | 分数范围 |
|---|---|---|
| `clipped` | hard 任务有一个可靠的已知参考值 | `[0, 1]` |
| `uncapped` | 已知最优值是活跃的研究前沿(flagship 任务) | `[0, ∞)` —— 追平 SoTA 为 1.0,超越 > 1.0 |

`uncapped` 任务还须提供 `references/known_best.md`,记录当前已知最优值、来源与日期。
**不要在 `uncapped` 任务里保留上限** —— 那会让"追平参考解"与"超越它"无法区分,
而这正是本基准要测的那个区别。`tests/test_uncapped_scoring.py` 会检查。

---

## 基线程序(`solution.py`)

- 必须**弱但合法**:能跑、oracle 接受它、得分接近 0。
- 保持 oracle 期望的函数签名与输出契约。
- CPU 任务只用 `numpy` 与 `scipy`。额外依赖写进 `verification/requirements.txt`。

**基线也是难度阶梯的锚。** 若任务带 `DIFFICULTY` 层级,每一级都要保证基线仍然**合法** ——
一个连基线都无效的层级什么都测不了,因为分数以"基线 = 0"归一化,那里没有基线。
只用候选去测会把"太难"与"坏掉"混为一谈。

---

## 提 PR 前的检查清单

- [ ] 先把新任务以 `candidate` 加入 `sle/certification.yaml`;**不要自我认证**未经评审的任务。
- [ ] `python -m sle eval --allow-uncertified --task <Domain>/<Task>` 能跑通,
      基线的 `combined_score` 接近 0。
- [ ] `python -m sle list --all` 能看到新任务包且元数据正确。
- [ ] oracle 确定(跑两次得同样分数)。
- [ ] `scripts/check_evaluator_survives_bad_candidates.py --task <Domain>/<Task>` 三种坏候选
      全部 `scored invalid`。
- [ ] 智能体可见文件(`Task.md`、`solution.py`、`constraints.txt`)不泄露 oracle 实现或答案,
      且**已列出候选会收到的所有输入键名**。
- [ ] 无绝对路径、无 `.env`、无 API key、无 `__pycache__`、无大数据文件。
- [ ] `metadata.yaml` 字段填全。
- [ ] flagship(`uncapped`)任务:`references/known_best.md` 存在且值有出处。
- [ ] `python scripts/audit_tasks.py` 无准入问题,不变量测试全部通过。
- [ ] 在 `sle/conf/exam_taxonomy.yaml` 里占**恰好一格**(optimization analogue 或
      discovery kind)。`python scripts/report_exam_taxonomy.py` 必须干净。
- [ ] 不与 Frontier-Eng 重合:建题前对照其论文附录 A 的 47 题与仓库 `TASK_DETAILS.md` 的全部条目,
      同一问题类(如桁架减重、光栅衍射级配、月面着陆轨迹)不再立题;同形式不同问题可以,但要在卡片
      `novelty_risk` 里写清区别。核查记录见 `.research/frontier_eng_overlap_audit_2026-09-03.md`。
- [ ] `python scripts/check_task_contribution.py --task <Domain>/<Task>` 通过
      （上面大部分检查的一条命令;不调用 LLM,也不宣称认证）。
      EnzymeKineticsLaw / DiscrepantMeasurements 已标 `on_ramp_do_not_pair`,不要拿它们
      做配对对照,也不要再加一题同构的 on-ramp。

---

## 贡献流程

1. **Fork** 本仓库并 **clone** 你的 fork。
2. **建分支**:`feat/<Domain>/<Task>`(例如 `feat/Biology/RNAInverseFolding`)。
3. **按上面的目录结构添加任务**。可拿已有任务当模板 —— `Chemistry/LennardJonesCluster`
   是 clipped,`Mathematics/CapSet` 是 uncapped。
4. **测试**(新任务包默认未认证;下面两条要在 Linux 主机上跑,见"运行环境"):
   ```bash
   python -m sle eval --allow-uncertified --task <Domain>/<Task>
   python -m sle run --allow-uncertified --task <Domain>/<Task> --budget 3
   ```
5. **提交 Pull Request** 到 `main`。PR 描述里写:
   - 科学背景(一到两句)。
   - oracle 细节:它计算什么、依赖、计算开销。
   - 基线分数与参考 SoTA。
6. **评审**:维护者会在合并前检查 oracle 正确性、黑盒安全与打分校准。

---

## 运行环境:哪里能跑什么

| 环境 | 能做什么 | 不能做什么 |
|---|---|---|
| 笔记本(macOS / Windows) | 改代码;`python -m pytest tests/ -q`(需要沙箱的测试自动 skip);写任务文档 | 跑 `sle eval / run`、标定、Δ 阶梯、任何要进仓库的证据 |
| Linux 主机(bubblewrap + util-linux flock) | 以上全部;`refresh_global_evidence.py`;恢复审计;`rebind_measurement_health_spec.py` | 在脏树上生成证据 |
| CI(GitHub Actions,ubuntu-22.04) | 全量测试 + 审计,合并前唯一算数的绿灯 | 生成证据(runner 不是可信来源) |

原因写在沙箱里:候选代码在 bubblewrap 中由 `/usr/bin` 的解释器执行,只挂载 `/usr /lib /lib64`,
所以依赖必须装进系统解释器(`sudo /usr/bin/python3 -m pip install numpy scipy pyyaml`),
`actions/setup-python` 或 conda 里的包沙箱看不见。macOS 没有 bubblewrap,沙箱路径一律不可用。

证据文档(`experiments/*.json`、`.research/*_spec_*.json`)都带 `source_provenance`:git 修订、
树是否干净、运行时源码哈希。脏树、笔记本产出、或运行时文件已变的文档会被标为不可信,测试直接拒收。
所以流程固定是:**先 commit,再在 Linux 主机上 `git pull --ff-only`,确认 `git status` 干净,再生成证据,
再 commit 证据**。改动任何任务包内文件之后,除了 `refresh_global_evidence.py`,还要跑
`pytest tests/test_measurement_health_preflight.py tests/test_scientific_materiality.py tests/test_batch_runner.py`。

团队内部的主机名、可用模型端点与密钥获取方式不在仓库里,向维护者索取内部 runbook。

---

## LLM 配置(用于测试)

harness 支持 Anthropic wire 与任何 OpenAI 兼容端点(chat 或 responses)。复制示例配置,
密钥一律通过环境变量引用,配置文件里只写 `${VAR}`:

```bash
cp sle/conf/llm/anthropic.example.yaml sle/conf/llm/local.claude.yaml
# base_url / model 按需改;api_key 保持 ${ANTHROPIC_API_KEY}
export ANTHROPIC_API_KEY=...        # 只在当前 shell,来自你们的密钥管理,不写进文件
python -m sle run --task Chemistry/LennardJonesCluster --algorithm greedy_rewrite \
  --budget 3 --seed 0 --workdir runs/smoke --llm-config sle/conf/llm/local.claude.yaml
```

`sle/conf/llm/local.yaml` 与 `local.*.yaml` 已被 git 忽略。**永远不要把 API key 写进任何会被提交的文件,
也不要写进 `.research/` 或实验文档。** Anthropic wire 会显式发送 `thinking: disabled`;
模型只返回 thinking 块、没有文本时 harness 会报错而不是记零分。

---

> 有问题?先开一个 Issue 讨论你的任务想法,再动手写代码。

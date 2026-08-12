# 第二个模型:排序一致,判据不一致

Claude Opus 4.8 在 6 个任务上跑满 36 次(3 seed × 2 臂 × 6 任务,budget 12,greedy_rewrite),
与 gpt-5.5 逐任务对照。答案分两半,而且两半的结论相反。

## 先说一个必须前置的更正

第一版跨模型报告给出的相关系数是错的:

| 对比 | 修正前 | 修正后 | 可比任务数 |
|---|---|---|---|
| gpt-5.5 vs gpt-5.6-sol(同族) | 0.371 | **0.987** | 6 → 32 |
| claude vs gpt-5.5(跨族) | 0.829 | 0.829 | 6 |
| claude vs gpt-5.6-sol | 0.200 | **不可比** | 6 → 0 |

原因是**任务契约漂移**。清单里 54 个任务中有 **20 个带不止一个 `task_package_sha256`** ——
任务在两批运行之间被改过。旧代码取三个模型的任务交集,再在交集上算相关,于是:

- gpt-5.5 与 gpt-5.6 之间真正同版本的 32 个任务被砍到 6 个,而剩下那 6 个恰好全是版本不一致的;
- claude 与 gpt-5.6 从来没跑过同一个版本的任何任务,却被算出了 0.200。

LowThrustTransfer 上 gpt-5.6 是 0.7428、gpt-5.5 是 0.0401 —— 18 倍,读起来像模型差异,
实际是两个不同的任务。哈希一直记在 manifest 里,只是比较时没人查。

现在两个报告都按 (任务, 版本) 分组,跨版本拒绝比较并显式列出被排除的部分。

## 分数排序:一致

claude-opus-4-8 vs gpt-5.5,6 个同版本任务,**Spearman ρ = 0.829**:

| 任务 | claude | gpt-5.5 |
|---|---:|---:|
| LowThrustTransfer | 0.1031 | 0.0401 |
| AlloyHardnessOptimization | 0.3205 | 0.1842 |
| ProteinStabilityDesign | 0.5668 | 0.5462 |
| QuantumErrorDecoder | 0.6690 | 0.7713 |
| NMRSpectrumFitting | 0.4360 | 0.4940 |
| TrussWeightMinimization | 0.6415 | 0.4736 |

任务的难易顺序在两个模型族之间基本保持。Claude 在 6 个里 4 个更高。
提案有效率 claude 0.89/0.89,明显高于 gpt-5.5 的 0.77/0.76。
36 次运行合计 **$4.01**。

## 准入判据:完全不一致

同样这 6 个任务,**6 个全部分歧**:

| 任务 | claude-opus-4-8 | gpt-5.5 |
|---|---|---|
| LowThrustTransfer | control_not_exhausted | measures_iteration |
| AlloyHardnessOptimization | control_not_exhausted | measures_iteration |
| ProteinStabilityDesign | no_measurable_difference | measures_iteration |
| NMRSpectrumFitting | crossover_in_range | measures_iteration |
| TrussWeightMinimization | control_not_exhausted | feedback_harmful |
| QuantumErrorDecoder | control_not_exhausted | thin_screen |

方向是一边倒的:gpt-5.5 判为合格的 4 个任务,**Claude 判的是必要条件不成立**。

机制是可量化的。饱和门槛是开环臂后半段中位增益 < 0.01:

| 任务 | claude(3 seed) | gpt-5.5(全部 seed) | gpt-5.5(限前 3 seed) |
|---|---:|---:|---:|
| LowThrustTransfer | 0.0165 | 0.0053 ✓ | **0.0193 ✗** |
| AlloyHardnessOptimization | 0.0280 | 0.0000 ✓ | 0.0000 ✓ |
| TrussWeightMinimization | 0.0242 | 0.0000 ✓ | 0.0000 ✓ |
| NMRSpectrumFitting | 0.0092 ✓ | 0.0000 ✓ | 0.0014 ✓ |

所有曲线都是 12 步,任务版本相同,搜索器相同 —— budget 与契约都不是混淆项。
**Claude 的 best-of-N 在同样预算下还在爬,而 gpt-5.5 的已经平了。**

这不是判据坏了,是判据在如实报告一件真事:交叉点是任务 × 搜索器的性质,
而模型是搜索器的一部分。**更强的模型会让任务失去准入资格** —— 因为对照臂还没被打穿。
这一条要写进方法学:合格性是"任务 + 搜索器"的联合断言,不能只挂在任务上。

## 一个顺带查出来的缺陷:判据对 seed 数不稳定

上表最后一列是关键。LowThrustTransfer 的 `measures_iteration` 依赖它恰好跑了 6 个 seed;
只用前 3 个,后半增益是 0.0193,必要条件不成立。而报告自己声明 3 个 seed
(`MIN_SEEDS_FOR_CONFIDENT_SATURATION`)就足以下结论。

先试了留一法,太钝:6 个 seed 去掉 1 个中位数不会跨过门槛,查出来 0 个。
改成**在判据自己信任的最小 seed 数上枚举子集**,若任一子集反转结论则标记。结果:

**5 个合格任务里有 3 个是 seed 脆弱的** —— LowThrustTransfer(6 seed)、
ProteinStabilityDesign(8 seed)、QuantumErrorDecoder(12 seed,gpt-5.6)。
真正不依赖"跑了哪几个 seed"的只有 AlloyHardnessOptimization 和 NMRSpectrumFitting。

## 同期做的 pipeline 修复

1. 两个报告都拒绝跨 `task_package_sha256` 比较,并列出被排除项。
2. 准入证据按 (任务, 模型, 任务版本) 分组;此前饱和证据跨 cohort 池化,
   等于把两个版本的 seed 混在一起问"best-of-N 是否停止改进"。
3. 判据一致性改为按 (任务, 版本) 分组,而不是要求所有模型共版本 ——
   后者会因为第三个模型跑了别的版本而丢掉一对本来有效的比较。
4. `scripts/run_cohort.sh`:成组运行器,锁做到每个 run 目录、可续跑、
   完成判据是 manifest 存在。带 9 个测试。

第 4 条的由来:Claude 那批是用两个 `/tmp` 脚本跑的,各持一把**以脚本命名**的锁,
互不排斥,而两份任务清单都含 LowThrustTransfer,每次运行又以 `rm -rf` 开头。
结果 36 次运行里 3 次被对方删掉 manifest,而所有报告都以 manifest 为键 ——
这 3 次不是报错,是**从比较里静默消失**。旧的续跑判据是"轨迹 ≥13 行",
恰好对被删 manifest 的目录成立,所以重跑会精准跳过唯一需要重跑的那几个。

## 边界

- Claude 只跑了 6 个任务 3 个 seed。ρ = 0.829 建立在 6 个点上,置信区间很宽。
- 上面"Claude 开环更强"的结论,seed 匹配后在 Alloy 与 Truss 上稳健,
  在 LowThrust 上则与 gpt-5.5 自身的 seed 脆弱性纠缠,不能单独归因于模型。
- claude 与 gpt-5.6-sol 之间仍然零可比任务。要回答这一对,
  必须把 gpt-5.6 在当前版本的任务上重跑,而不是复用 `saturation` cohort 的旧数据。

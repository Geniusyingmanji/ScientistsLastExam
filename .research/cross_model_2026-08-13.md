# 第二个模型:分数排序一致,准入判据不一致

Claude Opus 4.8 在 12 个任务上跑满 72 次(3 seed × 2 臂,budget 12,greedy_rewrite),与 gpt-5.5、
gpt-5.6-sol 逐任务对照。答案分两半,而且两半相反。

前 6 个任务是已有配对证据的那批;后 6 个是特意挑的 —— gpt-5.5 与 gpt-5.6 都有当前版本数据、
且分数不在天花板也不在地板,也就是有区分度的那些。

得出这个答案之前,评测流水线里有一条**任务身份**的缺陷链必须先修 —— 修之前算出来的每一个
相关系数都是错的,包括我一度写下的结论。下面先讲缺陷,因为它决定了数字能不能信。

## 缺陷链:任务身份哈希不指向任务

每次运行都把 `task_package_sha256` 写进清单,报告据此拒绝跨版本比较 ——
跨着任务改动做比较,会把改动报成模型差异。这条守卫是对的,但键取错了,而且错了两层。

**第一层:一行注解移动了全部 61 个任务的哈希。**
提交"declare scientific_role on all 61 tasks"写的是 `frontier_eval/metadata.yaml`,
而这个文件同时在 `task_package_sha256` 和更窄的 `task_contract_sha256` 的清单里。
所以换用窄哈希救不了,窄哈希还漏掉了若干任务评分时重算所依赖的 reference 实现。

**第二层:哈希把任务自己的运行产物算了进去。**
`task_package_sha256` 是 `rglob("*")` 全量哈希,只排除 `__pycache__` 与 `.pyc`。
而 58 个任务目录里有 **35 个含一个 `runs/` 子目录** —— 任务跑一次就往自己身上写一次产物。

实测 TrussWeightMinimization:含 `runs/` 得 `c88849722ee8`,正是清单里记录的哈希之一;
排除后得 `3ec2334d8c85`,任何提交都不匹配。**任务的身份取决于有没有人跑过它。**

后果三条,都实际发生了:11 个任务的清单哈希没有任何 revision 能复现;
同一个未修改任务的两次运行被记成两个版本;冻结 cohort 的 `frozen_task_package`
检查会仅仅因为"有人跑过这个任务"而失败。

**修复。** `task_package_sha256` 排除 `runs`/`__pycache__`/`.pytest_cache`/`.ipynb_checkpoints`
(4 个测试守住,含"名为 `runs.py` 的源文件不得被排除")。这只对将来的运行有效 ——
历史清单里的哈希已经把产物烙进去了,重放救不回。

**历史怎么办。** `scripts/build_task_version_equivalence.py` 从 git 历史重放每个 revision 的
包哈希;哈希实在无法复现的,退一步问历史:该任务自首次运行以来有没有提交改过任何
能改变分数的文件。两条路都走完:

| | 任务数 |
|---|---:|
| 记录下不止一个哈希 | 20 |
| 其中确认是同一个任务 | **16** |
| 确实改过(MolecularLead / QEC / RNAEnsemble) | 3 |
| 未决(CirclePacking:哈希不可复现且确有一次行为提交) | 1 |

报告改为在**等价类**上比较。可比任务数随之变化:gpt-5.5 vs gpt-5.6 从 6 → **50**,
claude vs gpt-5.6 从 0 → **6**。

## 分数排序:一致

| 对比 | ρ | 可比任务 |
|---|---:|---:|
| gpt-5.5 vs gpt-5.6-sol(同族) | **0.959** | 50 |
| claude vs gpt-5.5(跨族) | **0.811** | 12 |
| claude vs gpt-5.6-sol(跨族) | **0.559** | 12 |

| 任务 | claude | gpt-5.5 | gpt-5.6 |
|---|---:|---:|---:|
| HeatExchangerDesign | 0.9359 | 0.7665 | 0.9369 |
| DistillationColumnDesign | 0.6330 | 0.5822 | 0.8049 |
| TrussWeightMinimization | 0.6415 | 0.4736 | 0.4098 |
| QuantumErrorDecoder | 0.6690 | 0.7713 | 0.8163 |
| ProteinStabilityDesign | 0.5668 | 0.5462 | 0.5332 |
| RoomImpulseResponse | 0.5623 | 0.4382 | 0.8545 |
| NMRSpectrumFitting | 0.4360 | 0.4940 | 0.6759 |
| EnergyBalanceModel | 0.3294 | 0.6637 | 0.9776 |
| AlloyHardnessOptimization | 0.3205 | 0.1842 | 0.1993 |
| LowThrustTransfer | 0.1031 | 0.0401 | 0.7428 |
| CatalystDeactivationLab | 0.0032 | 0.0980 | 0.1722 |
| ForceFieldCalibration | 0.0000 | 0.0601 | 0.0000 |

**两条要收回的判断。**

其一:我一度把 LowThrustTransfer 上 gpt-5.5 的 0.0401 与 gpt-5.6 的 0.7428 这 18 倍差距
归因于"任务被改过"。等价表证明这两批跑的是同一个任务,**18 倍是真实的模型差异**。

其二:任务数只有 6 个时,claude vs gpt-5.6 的 ρ 是 0.200,我当时说"证据太薄不宜下结论"。
补到 12 个任务后是 **0.559** —— 那个 0.200 确实是小样本假象,而不是两族排序不一致。
12 个点仍然不多,但三对相关系数现在都落在"排序大体一致"的区间里。

提案有效率:claude 0.75/0.72,gpt-5.5 0.78/0.76,gpt-5.6 0.74/0.84。
Claude 在前 6 个任务上是 0.90/0.89,补的 6 个任务把它拉低了 —— 这 6 个是特意挑的有区分度的题,
Claude 在上面产出可用提案的比例明显更低,这本身是一个值得记的观察。
72 次运行合计 **$9.36**。

## 准入判据:不一致,而且方向一边倒

49 个可比的 (任务, 版本) 上 **33 一致 / 16 分歧**。claude 参与的任务**全部分歧**:

| 任务 | claude | gpt-5.5 |
|---|---|---|
| LowThrustTransfer | control_not_exhausted | measures_iteration |
| AlloyHardnessOptimization | control_not_exhausted | measures_iteration |
| ProteinStabilityDesign | no_measurable_difference | measures_iteration |
| NMRSpectrumFitting | crossover_in_range | measures_iteration |
| TrussWeightMinimization | control_not_exhausted | feedback_harmful |
| QuantumErrorDecoder | control_not_exhausted | thin_screen |

gpt-5.5 判为合格的 4 个,Claude 判的都是**必要条件不成立**。机制可量化 ——
饱和门槛是开环臂后半段中位增益 < 0.01:

| 任务 | claude(3 seed) | gpt-5.5(全部) | gpt-5.5(限前 3 seed) |
|---|---:|---:|---:|
| LowThrustTransfer | 0.0165 | 0.0053 ✓ | **0.0193 ✗** |
| AlloyHardnessOptimization | 0.0280 | 0.0000 ✓ | 0.0000 ✓ |
| TrussWeightMinimization | 0.0242 | 0.0000 ✓ | 0.0000 ✓ |
| NMRSpectrumFitting | 0.0092 ✓ | 0.0000 ✓ | 0.0014 ✓ |

曲线一律 12 步、任务版本相同、搜索器相同 —— budget 与契约都不是混淆项。
**Claude 的 best-of-N 在同样预算下还在爬,gpt-5.5 的已经平了。**

这不是判据坏了。交叉点是任务 × 搜索器的性质,模型是搜索器的一部分,
所以**更强的模型会让任务失去准入资格**。合格性必须写成"任务 + 搜索器"的联合断言,
不能只挂在任务上 —— 这一条要进方法学。

## 顺带查出:判据对 seed 数不稳定

上表最后一列。LowThrustTransfer 的 `measures_iteration` 依赖它恰好跑了 6 个 seed;
只用前 3 个,必要条件就不成立。而报告自己声明 3 个 seed(`MIN_SEEDS_FOR_CONFIDENT_SATURATION`)
足以下结论。

先试留一法,太钝:6 个 seed 去掉 1 个中位数跨不过门槛,查出 0 个。
改成**在判据自己信任的最小 seed 数上枚举子集**,任一子集反转结论即标记。
结果:**7 个合格任务里 3 个 seed 脆弱** —— LowThrustTransfer、ProteinStabilityDesign、
QuantumErrorDecoder。补跑之后合格任务从 5 个增加到 7 个
(新增 CatalystDeactivationLab 与 EnergyBalanceModel),脆弱的仍是那 3 个。

## pipeline 改动清单

1. `task_package_sha256` 不再哈希运行产物(`sle/algorithms/common.py`,4 测试)。
2. `scripts/build_task_version_equivalence.py` + `sle/task_versions.py`:
   哈希等价表,重放优先、历史兜底,未知哈希映射到自身而非共用桶(5 测试)。
3. 两个报告改为在等价类上比较,并列出被排除项。
4. 准入证据按 (任务, 模型, 任务版本) 分组;此前饱和跨 cohort 池化 = 混两个版本的 seed。
5. 判据一致性按 (任务, 版本) 分组,而非要求全模型共版本(后者会因第三个模型跑了别的版本
   而丢掉一对本来有效的比较)。
6. 饱和加子样本稳定性检查。
7. `scripts/audit_task_versions.py`:哪些运行测的是已不存在的版本。
8. `scripts/run_cohort.sh`:成组运行器,每 run 目录加锁、可续跑、以 manifest 为完成判据(9 测试)。

第 8 条的由来:Claude 那批原用两个 `/tmp` 脚本跑,各持一把**以脚本命名**的锁,互不排斥,
两份清单都含 LowThrustTransfer,每次运行又以 `rm -rf` 开头 —— 36 次里 3 次被对方删掉 manifest。
所有报告以 manifest 为键,这 3 次是**静默消失**而非报错;旧续跑判据"轨迹 ≥13 行"
恰好对被删目录成立,重跑会精准跳过唯一该重跑的那几个。已补齐。

## 未了

- 冻结 cohort preflight 7 个任务 0/7 全项失败,g450 上 745 个测试 30 失败 8 错误,
  集中在这一处及依赖它的分析测试。preflight 现在会说明失败原因:**7 个任务全部是"仅声明性改动"**
  —— 冻结时的科学证据仍然描述着这些任务,过期的只是绑定。所以该做的是刷新绑定而不是重新测量,
  但这属于 Track F 治理决定,未擅动。
- claude 12 个任务、每个 3 个 seed。三对 ρ 分别建立在 12、12、50 个点上,前两对区间仍宽。
- CirclePacking 的版本等价仍未决。
- MolecularLeadOptimization 与 RNAEnsembleDesign 的重配对已完成,12 次全部落盘。

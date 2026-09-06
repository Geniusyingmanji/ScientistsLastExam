# 第二批五道生物题：立项评估（2026-09-05）

状态：**原始设计提案（历史记录）；五题现已按顺序实现并以 candidate 注册。**
实际首版范围、设计偏差、测试与未完成的准入条件见
[实现报告](biology_wave2_implementation_2026-09-05.md)。以下保留原提案，
其中“拟定”“未注册”“实现前”等描述属于当时计划，不代表当前进度。
文献支持问题形式，不保证这里拟定的生成器、难度和参考值正确；所有预算均为待实测目标。

## 选题与实施顺序

| 顺序 | 拟定 ID | 中文名 | 唯一 taxonomy 格 | 最主要的未决风险 |
|---|---|---|---|---|
| 1 | Genomics/DiploidHaplotypeAssembly | 混合读段的二倍体单倍型组装 | optimization / combinatorial | 成熟求解器可能直接饱和，不能仅是小型 MaxCut 换名 |
| 2 | ConservationBiology/RobustReserveNetworkDesign | 多物种保护区网络稳健设计 | optimization / engineering_design | 动态扩散必须实际改变最优选址，不能退化为普通集合覆盖 |
| 3 | Biophysics/SingleMoleculeKinetics | 单分子荧光轨迹的动力学辨识 | discovery / parameter_inversion | 发射简并与时间分辨率可能导致不可辨识，固定 HMM 可能饱和 |
| 4 | MetabolicEngineering/IsotopeFluxIdentifiability | 同位素示踪下的代谢通量辨识 | discovery / parameter_inversion | 原子映射、交换通量、EMU 求解和可辨识性均需独立验证 |
| 5 | StructuralBiology/ProteinDistanceGeometry | 稀疏距离约束下的蛋白构象重建 | optimization / molecular_design | 几何可行不等于真实折叠，可能与通用距离几何/构象优化重叠 |

两个新增逻辑 domain（ConservationBiology、Biophysics）及 StructuralBiology 只有在实现通过后
才登记到 benchmark_layout.py；这里不提前改动 taxonomy、certification 或 TASKS.md。

## 1. DiploidHaplotypeAssembly

**问题和产物。** 给定匿名杂合位点、带测序错误率的片段观测及其覆盖关系，输出每个位点的
二进制相位 `haplotype`。互补的两条单倍型等价。使用合成位点，不下载个体基因组数据。

**公开契约草案。** `assemble_haplotypes(problem)`；问题含 `variant_ids`、`fragments`
（`positions`、`alleles`、`error_probabilities`）、`block_ids`、公开的技术噪声模型。
返回 `{"haplotype": [0,1,...]}`。断开的观测连通分量允许独立翻转，不评不可识别的跨块方向。

**冻结 oracle。** 对片段 f，已知错误率 e，最大化
`sum_f log(0.5*P(read_f|h) + 0.5*P(read_f|1-h))`，用 log-sum-exp 计算；如加入
Hi-C 跨同源体片段，必须公开对应混合似然，不隐含使用普通片段模型。主分评优化目标，
另报密封读段预测和 permutation-invariant 相位准确度，不把隐含真实序列作为优化契约。
以确定性弱合法相位为 0、冻结真值盲参考为 1；选择 uncapped 前需实测参考之上的改进。

**参考、预算和难度。** CPU 目标 1–3 分钟；规模拟从 200 到 2000 位点、覆盖率与长片段比例变化。
对照加权 MEC、图切割、局部翻转和 HapCUT2，报告相同算力下的似然与相位指标。去掉长距离
连接、技术错误校正或多起点搜索分别做消融。随机相位、固定相位、逐位多数投票不可饱和。

**区别。** 与 DemographicSFS 的群体频谱参数反演、MetagenomeCompositionAssignment 的物种混合
反演、PhylogeneticParsimonySearch 的物种树搜索不同；需要保留读段级连锁证据才成立。

**来源。** Edge, Bafna & Bansal (2017), HapCUT2，DOI
[10.1101/gr.213462.116](https://pmc.ncbi.nlm.nih.gov/articles/PMC5411775/)。作者实现：
[HapCUT2](https://github.com/vibansal/HapCUT2)。复用代码或数据前单独核对许可证；参考实现不作为
候选必需依赖。若成熟固定流程在首轮达到参考的 95%，扩大技术噪声与覆盖迁移，仍饱和则取消。

## 2. RobustReserveNetworkDesign

**问题和产物。** 在保护预算内选择空间地块；保护效果取决于各物种的生境质量、扩散范围、
源种群和气候情景。输出地块 ID 集合，不能提交自报生态收益。

**公开契约草案。** `design_reserve(problem)`；输入 `patch_ids`、`costs`、`budget`、
`species_weights`、`initial_occupancy`、各情景的 `habitat_quality`、`dispersal_matrices`、
`extinction_rates`、`time_grid`。返回 `{"protected_patches": [...]}`。

**冻结 oracle。** 拟用离散占域递推，已选地块才提供持续生境：
`p_i(t+1)=x_i*[p_i(t)*(1-e_i)+(1-p_i(t))*(1-exp(-sum_j d_ji*x_j*p_j(t)))]`。
这是待验证的 benchmark 模型假设，不能归称为 Marxan 的方程。独立检查概率界、零扩散、
零初始源和单斑块解析结果。效用取各公开情景下最终加权占域的最小值，成本硬约束。
密封新景观检验选址算法迁移，不隐藏必须知道的动力学常数。

**参考、预算和难度。** 目标 CPU 1–3 分钟，40–100 地块、4–10 物种。参考为预算内贪心+
交换搜索；强对照包括静态覆盖优化、模拟退火和小实例枚举。必须展示去掉连通性、物种专属
扩散或稳健情景会改变选址且降低真实目标，否则只是一个套生物名词的集合覆盖题。

**区别。** 与 FedBatchBioprocessDesign 的单反应器时间控制、GeneNetworkIntervention 的未知
调控网络发现、SparseRecovery 的测量恢复不同。定位为保护规划算法，不声称给出真实政策。

**来源。** [Integrating regional conservation priorities for multiple objectives into national policy](https://www.nature.com/articles/ncomms9208)，
DOI 10.1038/ncomms9208，支持成本、物种表示和连通性共同参与保护规划的问题形式。
拟定动态递推需另找原始占域/扩散模型依据及生态学评审后才能落地。

## 3. SingleMoleculeKinetics

**问题和产物。** 从多条低光子数 donor/acceptor 轨迹中恢复公开有限状态模型的转移率，
区分可辨识动力学、静态单态和仅凭现有时间分辨率不可辨识的情形。输出速率矩阵、发射参数、
声明或拒答及置信度；状态置换不改变评分。

**公开契约草案。** `infer_kinetics(problem, observe)`；问题含 `model_family`、`parameter_bounds`、
`exposure_menu`、`trace_length_menu`、`photon_budget`、公开探测器模型。`observe(exposure, length)`
返回光子计数、时间间隔和实际扣费。预算按观测总曝光和采样长度结算，超支不可捕获后继续得分。

**冻结 oracle。** 连续时间 Markov 生成矩阵 Q 的离散转移为 `expm(Q*dt)`，发射拟用状态条件
Poisson 光子模型；若模拟曝光期间多次跳转，必须公开曝光积分的实际模型，不混用瞬时发射。
机制分按最佳状态匹配后的 log-rate 误差，拒答和假发现另列分母。密封新曝光条件预测独立报告。
完全等价发射/动力学模型不能被强行要求区别；不可辨识世界要有观测等价或功效分析证据。

**参考、预算和难度。** 目标 CPU 2–5 分钟，10–50 条轨迹。多起点 HMM/EM 为固定参考，ebFRET
为社区对照；逐帧阈值、单轨迹拟合、不校正光漂白分别消融。世界类型不能决定轨迹条数或文件形状。
全面拒答和静态否认均归零。暂不凭三个状态的小 HMM 就声称专家难度。

**区别。** 与 HamiltonianLearning 的量子动力学、EnzymeKineticsLaw 的速率律选择、
GeneNetworkIntervention 的因果调控拓扑不同；核心是光子观测下的隐态动力学和时间分辨率。

**来源。** van de Meent et al. (2014),
[Empirical Bayes Methods Enable Advanced Population-Level Analyses of Single-Molecule FRET Experiments](https://pmc.ncbi.nlm.nih.gov/articles/PMC3985505/)，
DOI 10.1016/j.bpj.2013.12.055。论文支持隐态与群体轨迹推断的困难，不证明本提案的拒答集可判别。

## 4. IsotopeFluxIdentifiability

**问题和产物。** 在示踪物和采样时间预算内推断代谢支路净通量及交换通量；遇到无法区分的
等价通量族，报告可识别组合或拒答。返回的数值必须满足公开稳态质量守恒和边界。

**公开契约草案。** `infer_fluxes(problem, trace)`；输入 `reaction_ids`、`stoichiometry`、
`atom_transitions`、`pool_sizes`、`flux_bounds`、`tracer_menu`、`sampling_times`、`budget_units`。
`trace(tracer_id, time_ids)` 返回质量同位素分布和协方差模型、扣费。所有标记转移语义公开。

**冻结 oracle。** 用 EMU/同位素质量平衡传播标签；先在二碳/三碳玩具网络与全 isotopomer 枚举
逐项比对，再与 INCA 或另一独立实现交叉验证。主轴评可辨识净通量组合的相对误差；
不能仅凭同位素谱拟合好就奖励错误交换通量。错误发现、正确拒答和采样覆盖分别报告。
无法识别的子空间用等价集合距离评分，或明确拒答；不得以任意隐藏参数点作为唯一答案。

**参考、预算和难度。** 目标 CPU 2–5 分钟，小型但含循环/可逆支路的网络。固定参考为多起点
约束非线性最小二乘加 profile likelihood，消融示踪选择、时间选择、交换通量和辨识检查。
先验证纯 FBA、单标记比例、固定示踪策略不能饱和，再考虑增大规模。

**区别。** MetabolicStrainDesign 已知网络下交付敲除设计；本题交付由实验可支持的未知通量，
不是优化产量。与 ReactionMechanismFitting 的化学速率拟合、DemographicSFS 的群体史推断不同。

**来源。** Young (2014),
[INCA: a computational platform for isotopically non-stationary metabolic flux analysis](https://www.vanderbilt.edu/younglab/pdf/young14.pdf)，
DOI 10.1093/bioinformatics/btu015；[13C-based metabolic flux analysis](https://www.nature.com/articles/nprot.2009.58)，
DOI 10.1038/nprot.2009.58。首版只使用自建可审计网络，不假定商业工具许可可随仓库分发。

## 5. ProteinDistanceGeometry

**问题和产物。** 根据公开共价几何、手性约束及带不确定区间的稀疏距离约束，输出一组原子坐标。
这是约束构象优化，不把有限约束下任意一个隐藏构象当成唯一真实蛋白结构。

**公开契约草案。** `build_conformation(problem)`；输入 `atom_ids`、`bonds`、`bond_length_bounds`、
`angle_bounds`、`stereocenters`、`distance_restraints`、`excluded_volume_radii`、`coordinate_bounds`。
返回 `{"coordinates": [[x,y,z],...]}`，所有 ID、单位、手性符号和距离容忍度均须公开。

**冻结 oracle。** 独立重算距离区间违反量、键长/角偏差、排斥和有向体积手性约束。
刚体平移旋转不改变分数；镜像在有手性约束时不可等价。尺度缩放、原子碰撞不能靠距离损失
平均化获得高分。没有足够约束时仍只评满足约束的优化质量，不评无法证明的折叠准确度。

**参考、预算和难度。** CPU 目标 2–5 分钟。MDS 初始化+投影优化是弱参考，续接法、多起点和
约束优化为强对照。用小分子距离几何与独立几何验证器查真值；报告去掉手性、键连通或排斥
约束后的影响。若只需 MDS 或通用 least_squares 就能饱和，取消独立任务，避免凑数量。

**区别。** ProteinStabilityDesign 交付序列而非坐标；GraphFromDistances 恢复离散图；
ForceFieldCalibration 校准力场参数。本题必须保留化学约束，否则不能成立为独立生物问题。
Frontier-Eng 的 diverse_conformer_portfolio 是从候选构象选择组合，本提案是从约束生成几何，
但同领域重叠风险仍高，需要维护者确认问题类边界。

**来源。** Argonne 作者页 [DGSOL](https://www.mcs.anl.gov/~more/dgsol/) 及其列出的
Moré & Wu, *Distance geometry optimization for protein structures*, Journal of Global Optimization
15 (1999), 219–234。此项排最后；化学可行性和最近邻重叠未解决前不注册。

## 对照范围与统一准入条件

2026-09-05 实际阅读 Frontier-Engineering main 的 [TASK_DETAILS.md](https://github.com/Einsia/Frontier-Engineering/blob/main/TASK_DETAILS.md)
目录，对照 SingleCellAnalysis 三题、MolecularMechanics 三题及其他优化问题；未发现前四项同题。
第五项保留上述同域风险。论文附录 47 题只查到了本仓库历史审计记录，**本轮未独立重读原 PDF**，
因此不宣称完成 CONTRIBUTING A3；实现前必须补上原文与固定 revision 的逐项对照。

每个新题实现前需要：

1. 在题面冻结方程、完整输入输出、预算、单位和归一化；所有拒答世界可证明可判或等价。
2. baseline 合法且恰好零；明确 reference 的能力和缺口；10 种以上针对任务的坏提交 fail closed。
3. 小实例独立 oracle 校验、置换/尺度/对称不变量、数百次以上低维捷径搜索、能力消融。
4. 固定强经典流程与多次 frontier draw，首提案不能达到参考；达参考 90–95% 时先加固或取消。
5. 评测入口、Linux 沙箱、全量测试、干净 revision 证据全部通过后，才按 candidate 注册。

建议把第二批实现放在后续 PR，先合并第一批修复；无需等待第二批五题全部成熟才修现有评分错误。

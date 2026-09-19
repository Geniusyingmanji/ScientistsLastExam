# 任务汇总

由 `python scripts/report_task_inventory.py` 从注册表生成,`tests/test_task_inventory_document.py` 保证它不过期;不要手改。权威实时清单是 `python -m sle list --all`。

| | |
|---|---:|
| 任务包 | 46 |
| discovery | 46 |
| candidate | 40 |
| quarantined | 6 |
| 学科 | 7(Biology 6,Chemistry 8,ComputerScience 5,EarthScience 7,Engineering 5,Mathematics 4,Physics 11) |

认证描述的是证据质量,不是难度。标 on-ramp 的任务首个前沿模型提案已够到参考解,不用于配对 Δ 测量。

## Discovery(46)

### 公式(formula) — 7

| 任务 | 学科 | 领域 | 打分 | oracle | 认证 | 说明 | 中文题意 | 中文评估方法 |
|---|---|---|---|---|---|---|---|---|
| [`EnzymeKineticsLaw`](benchmarks/Biology/EnzymeKineticsLaw/)<br>酶动力学律辨识 | Biology | SystemsBiology | clipped | physical_sim | quarantined | A purified enzyme is in front of you. · on-ramp,不配对 | 在测定预算内自选底物与抑制剂浓度,判定这个酶服从六条已发表速率律中的哪条,或都不服从 | 速率律辨识 + 拒答 + 密封外推预测 |
| [`CacheReplacementPolicyID`](benchmarks/ComputerScience/CacheReplacementPolicyID/)<br>缓存替换策略辨识 | ComputerScience | ComputerArchitecture | clipped | analytical | candidate | which replacement policy does this cache set run? | 在带噪声的命中/缺失计时通道上对一个缓存组做受预算约束的访问实验,把隐藏的替换策略写成以路为输入的确定性状态机,或判定策略含随机性而拒答 | 提交的状态机与真实策略做精确的可观测等价判定;错误状态机记误发现并扣一个世界,随机策略世界须拒答,分数标尺锚在全拒答为零 |
| [`AMOCTippingRefusal`](benchmarks/EarthScience/AMOCTippingRefusal/)<br>AMOC 折叠拒答 | EarthScience | Oceanography | clipped | physical_sim | quarantined | a dip in the fingerprint is not a fold | AMOC 指纹序列里区分尚未发生的立方折叠、纯红噪声与冰约束唯一吸引子 | 折叠恢复 + 红噪声与冰约束拒答;指纹下降不等于将要崩溃 |
| [`WallClosureDiscovery`](benchmarks/Engineering/WallClosureDiscovery/)<br>壁面湍流闭合律发现 | Engineering | Turbulence | clipped | analytical | candidate | find the closure, or say the data cannot pin one | 在有限的剖面测量预算下,把湍流壁面闭合律作为公式找出来——以及在观测撑不起任何律时说出撑不起。数据驱动湍流闭合是整个领域在做的问题,它公认的批评不是拟合得不好,而是只在训练它的地方被验证过。三类世界只有一类可解:雷诺数跨度够宽时参数被钉住;跨度太窄时一整段 kappa 都拟合得同样好而在留出工况上互相矛盾;还有一类根本没有单一闭合能同时解释各条剖面。 | 三轴分开报、永不平均:机制恢复率(在从未观测的留出雷诺数上检验公式)、假发现率(带分母)、校准拒答率,外加是否尝试过的计数。总分是三者之积,全弃权与从不弃权都恰好得零。两个拒答理由是正交的:不一致那类残差大,而不可辨识那类残差反而最小、拟合看起来最漂亮,要靠答案的宽度而不是残差来识别。把教科书的 van Driest 闭合直接交上去得零分、假发现率 1.00。 |
| [`ActiveLawDiscovery`](benchmarks/Mathematics/ActiveLawDiscovery/)<br>主动定律发现 | Mathematics | DynamicalSystems | clipped | physical_sim | candidate | discover dynamical laws by choosing experiments | 自选初值与外部驱动,从候选项库里恢复二维受控系统的稀疏控制方程 | 稀疏律恢复 + 密封轨迹外推;库不足时拒答 |
| [`SequenceLawRecovery`](benchmarks/Mathematics/SequenceLawRecovery/)<br>整数序列递推恢复 | Mathematics | Mathematics | clipped | community_symbolic_sympy | candidate | Given the first terms of an integer sequence, state the linear recurrence that produced it. | 给出整数序列前若干项,说出产生它的线性递推;项数不足以定唯一最小规则时拒答 | 延续准确率;误发现率与不定性拒答分开报告 |
| [`ComplexBoseLaw`](benchmarks/Physics/ComplexBoseLaw/)<br>复玻色占据律 | Physics | Physics | clipped | physical_sim | candidate | a mixed cavity occupancy is not textbook Planck | 在模式混合下恢复玻色占据律的移位指数;费米型世界须拒答 | 指数恢复 + 费米拒答;不是教科书普朗克曲线的直接拟合 |

### 结构(structure) — 6

| 任务 | 学科 | 领域 | 打分 | oracle | 认证 | 说明 | 中文题意 | 中文评估方法 |
|---|---|---|---|---|---|---|---|---|
| [`GeneNetworkIntervention`](benchmarks/Biology/GeneNetworkIntervention/)<br>基因网络干预设计 | Biology | SystemsBiology | clipped | physical_sim | candidate | discover a dynamic regulatory network and design a phenotype intervention | 用扰动实验恢复带符号的动态调控网络,并设计达成表型的干预 | 网络恢复 + 预测 + 表型干预迁移 + 拒答 |
| [`GraphFromDistances`](benchmarks/ComputerScience/GraphFromDistances/)<br>距离查询重建图 | ComputerScience | Algorithm | clipped | community_graph_algorithms_networkx | candidate | A weighted network exists but you cannot see it. | 在有限次距离查询下重建加权网络的边:短距离不等于相邻,可能是两条短边的两跳路径 | 边恢复 F1;误发现率与不可辨识拒答分开报告 |
| [`InterventionalSCM`](benchmarks/ComputerScience/InterventionalSCM/)<br>干预式结构因果模型 | ComputerScience | CausalDiscovery | clipped | physical_sim | candidate | recover hidden causal mechanisms by experimentation | 用干预实验打破马尔可夫等价,恢复隐藏线性无环结构因果模型的有向图与系数 | 有向图与结构系数恢复;观测关联不足以定向 |
| [`SurvivorshipConfoundedDesign`](benchmarks/ComputerScience/SurvivorshipConfoundedDesign/)<br>幸存者偏差下的效应估计 | ComputerScience | CausalDiscovery | clipped | physical_sim | quarantined | association among survivors is not a treatment effect | 每一行数据都已被结果相关的筛选选中,在幸存者表里估计真实处理效应 | 处理效应恢复;混杂开启的伪关联须识别,无 T→Y 边时不得宣称效应 |
| [`BlackBoxGroupIdentification`](benchmarks/Mathematics/BlackBoxGroupIdentification/)<br>黑盒群同构辨识 | Mathematics | Mathematics | clipped | analytical | quarantined | A finite set of `order` labelled elements and a black-box product: `mul(a, b)` returns the label | 只给黑盒乘法与随机标号,在查询预算内从公开构造目录里辨识群的同构类 | 目录 id 精确门控;非群与目录外两种拒答理由分开计分,阶数分布不足以辨识 |
| [`HiddenCouplingNetwork`](benchmarks/Physics/HiddenCouplingNetwork/)<br>隐藏耦合网络重建 | Physics | Physics | clipped | physical_sim | candidate | A network of `units` observed units relaxes to a steady state under constant drive. | 实验次数少于单元数,从多单元驱动的稳态里恢复带符号的直接耦合图;存在未观测单元时拒答 | 带符号边 F1;间接路径、tanh 非线性与隐藏单元造成的稠密低秩耦合分别记误发现 |

### 证据(evidence) — 11

| 任务 | 学科 | 领域 | 打分 | oracle | 认证 | 说明 | 中文题意 | 中文评估方法 |
|---|---|---|---|---|---|---|---|---|
| [`OccupancyDetectionDesign`](benchmarks/Biology/OccupancyDetectionDesign/)<br>生态占域与探测设计 | Biology | Ecology | clipped | statistical_sim | candidate | A nondetection does not prove absence. | 在漏检条件下分配站点复访与调查方法,恢复栖息地占域效应或拒绝不充分模型 | 效应方向、效应量与平均占域率;误发现、拒答、覆盖率和留出迁移分列 |
| [`ProspectiveMetaAnalysis`](benchmarks/Biology/ProspectiveMetaAnalysis/)<br>前瞻荟萃分析 | Biology | EvidenceSynthesis | clipped | prospective_evidence_synthesis | candidate | synthesize registered evidence and design confirmation | 在注册表加文献语料里筛研究、识别同一人群血缘的重复报告与换端点,做异质性荟萃回归 | 筛选、证据血缘完整性、荟萃回归、校准拒答、下一步研究信息量与前瞻确认分列 |
| [`SparseVectorAudit`](benchmarks/ComputerScience/SparseVectorAudit/)<br>稀疏向量技术的差分隐私审计 | ComputerScience | DataPrivacy | clipped | analytical | candidate | does this deployed sparse vector technique keep the privacy it claims? | 对一个声称满足 (ε, δ) 差分隐私的稀疏向量技术部署实现做黑盒审计:在运行次数预算内选择相邻查询向量与输出事件,给出违反见证或判定没有违反;实现可能偏离公开规范,且并非每处偏离都构成违反 | 见证的精确隐私损失对照构造者锚点评分;损失不超过 ε 的见证记误发现并扣一个世界,分数标尺锚在全拒答为零 |
| [`ForcedSignalAttribution`](benchmarks/EarthScience/ForcedSignalAttribution/)<br>强迫信号检测归因 | EarthScience | ClimateScience | clipped | statistical_sim | candidate | A regional field is observed for `years` years over `regions` regions. | 在控制年预算下判断区域记录里是否含强迫响应、估其幅度与区间;模型指纹或变率不可信时拒答 | 检测率、幅度分、区间覆盖分列;红噪声假趋势与安静模型均记误发现 |
| [`UPbConcordiaInference`](benchmarks/EarthScience/UPbConcordiaInference/)<br>铀铅谐和图事件归因 | EarthScience | Geophysics | clipped | physical_sim | candidate | infer a zircon event history | 在分析预算内选择锆石域,由两套铀铅衰变比判断单一结晶或一次铅丢失历史;可分辨的多事件历史须拒答 | 事件类型 + 结晶与铅丢失年龄 + 证据血缘;误发现、拒答、覆盖率和留出迁移分列 |
| [`ModalDamageAttribution`](benchmarks/Engineering/ModalDamageAttribution/)<br>模态损伤归因 | Engineering | StructuralEngineering | clipped | physical_sim | candidate | is the modal shift damage, or the weather? | 在受预算约束的测量日里判断模态频率的偏移是不是某个内部元件的刚度损伤、是哪一个、损失多少;支座变化导致的偏移须拒答 | 定位精确门控 + 严重度容差评分;温度对频率比精确抵消,健康结构误报与支座变化误判分别记误发现,分数标尺锚在全弃权为零 |
| [`HeavyTailEvidence`](benchmarks/Mathematics/HeavyTailEvidence/)<br>重尾证据判别 | Mathematics | Mathematics | clipped | physical_sim | candidate | A positive sample is either a power law with known `xmin`, a lognormal above `xmin`, a | 在已知 xmin 下判断样本是幂律还是对数正态;指数截断或样本过短须拒答 | 家族恢复 + 截断/小样本拒答;不是质量窗口的 look-elsewhere,也不是不相容常数调和 |
| [`DiscrepantMeasurements`](benchmarks/Physics/DiscrepantMeasurements/)<br>不相容测量调和 | Physics | ParticlePhysics | clipped | statistical_sim | candidate | Eight groups have measured the same physical constant. · on-ramp,不配对 | 八组测量同一常数但彼此不相容,诊断这批证据出了什么问题并给最佳值或判定没有最佳值 | 缺陷诊断 + 收费的内部一致性检验 + 拒答 |
| [`LookElsewhereAnomaly`](benchmarks/Physics/LookElsewhereAnomaly/)<br>多窗口扫描的全局显著性 | Physics | ParticlePhysics | clipped | physical_sim | quarantined | local 5σ is not a discovery | 一张质量谱在多个窗口里扫描,判定局域 5σ 在计入试验因子后还剩多少 | look-elsewhere 后的全局显著性;边带拒绝公开本底时须拒答 |
| [`PTAHellingsDowns`](benchmarks/Physics/PTAHellingsDowns/)<br>脉冲星阵四极相关 | Physics | Gravitation | clipped | physical_sim | quarantined | a common process is not a gravitational-wave background | 脉冲星计时阵里区分 Hellings-Downs 四极相关(引力波背景)与钟差单极、星历偶极、共同红噪声 | 四极 vs 单极判别与拒答;共同过程不等于引力波背景 |
| [`TransitTimingAttribution`](benchmarks/Physics/TransitTimingAttribution/)<br>凌星时刻变化归因 | Physics | Exoplanets | clipped | physical_sim | candidate | what causes the transit-time variations? | 主动选择后续凌星时刻,区分模拟的周期、活动代理与时钟漂移族 | 机制、周期预测与拒答;误发现率和留出迁移分开报告 |

### 物质(substance) — 6

| 任务 | 学科 | 领域 | 打分 | oracle | 认证 | 说明 | 中文题意 | 中文评估方法 |
|---|---|---|---|---|---|---|---|---|
| [`MetagenomeCompositionAssignment`](benchmarks/Biology/MetagenomeCompositionAssignment/)<br>宏基因组组成指认 | Biology | Microbiology | clipped | active_marker_count_mixture | candidate | composition under sequencing resolution | 从收费 marker 计数中恢复分类单元与丰度,保留近缘别名并识别参考库不足 | 组成恢复、别名/库外拒答与假发现率分列 |
| [`CrowdedSpectrumAssignment`](benchmarks/Chemistry/CrowdedSpectrumAssignment/)<br>混叠谱物种指认 | Chemistry | Spectroscopy | clipped | physical_sim | candidate | name the library species in a blended spectrum | 在混叠谱里指认封闭库中的物种;两个近线的混合与第三个物种不可区分,变焦要花预算 | 库物种指认 + 别名拒答 |
| [`PhaseDiagramDiscovery`](benchmarks/Chemistry/PhaseDiagramDiscovery/)<br>相图发现 | Chemistry | MaterialsScience | clipped | physical_sim | candidate | An isothermal section of a binary system A-B. | 在合成预算下测定二元等温相图:哪些平衡相存在、各占哪段成分,或该体系根本达不到平衡 | 相集精确门控 + 杠杆定律边界精度;两相区叠加、杂质峰、动力学冻结须区分,冻结体系须拒答 |
| [`QuinaryConvexHull`](benchmarks/Chemistry/QuinaryConvexHull/)<br>五元凸包稳定相 | Chemistry | MaterialsScience | clipped | analytical | candidate | E_f < 0 is not a new stable | 五元体系里给出凸包上真正稳定的非一元相;生成焓小于零不等于新稳定相 | 精确非一元凸包顶点;玻璃态须拒答 |
| [`MethaneSourceAttribution`](benchmarks/EarthScience/MethaneSourceAttribution/)<br>甲烷源归因 | EarthScience | AtmosphericChemistry | clipped | analytical | candidate | say which sources moved, or say the record cannot tell | 在固定观测预算下,判断二十年里哪些甲烷排放部门发生了变化——以及在记录判不了时说出判不了。2007 年后大气甲烷重新增长、δ¹³C 变轻,驱动因素至今没有定论:同位素证据被读成主要是微生物源,而这个读法又被以源signature空间变异和汇的未解问题反驳。四类世界只有两类可答:化石与生物质燃烧会让 δ¹³C 上升、乙烷能分开;单一微生物源变化足够大时部门清单能认出;而纯汇变化和两个微生物源同时小幅变化都判不了。 | 三轴分开报、永不平均:机制恢复率、假发现率(带分母)、校准拒答率,外加是否尝试过的计数。总分是三者之积,全弃权与从不弃权都恰好得零。关键在于纯汇变化能被纯源变化复现到观测噪声以内(约化失配 0.00),而它看起来最像废弃物在小幅增加——baseline 在八个纯汇案例里点名废弃物五次。出路是买废弃物清单,发现它没变,把自上而下与自下而上的矛盾当作弃权的理由。 |
| [`TransmissionSpectrumSpecies`](benchmarks/Physics/TransmissionSpectrumSpecies/)<br>透射光谱分子判定 | Physics | Exoplanets | clipped | analytical | candidate | say which molecules are there, or say you cannot tell | 在固定的凌星次数预算下,判断系外行星大气里有哪些分子——以及在观测无法判定时说出无法判定。K2-18b 的 DMS 之争正是这个问题:多次重分析的结论是那些特征并非唯一可辨识。四类世界里有三类不可辨识,而且原因各不相同:灰云层一次压平所有特征;混淆对在任何预算分配下都分不开(单振幅误差是其和的 24.5 倍);暗弱系统把整个预算压在最好波段也到不了 1σ。只有第三类是噪声。 | 三轴分开报、永不平均:机制恢复率、假发现率(带分母)、校准拒答率,外加是否尝试过的计数。总分是三者之积,归一化到全弃权恰好得零——从不弃权因拒答率为零也得零,两种退化策略都是零,靠尝试率把它们区分开。点名混淆对里任何一方都算假发现,即使其中一个确实存在:世界不决定是哪一个。 |

### 参数反演(parameter_inversion) — 16

| 任务 | 学科 | 领域 | 打分 | oracle | 认证 | 说明 | 中文题意 | 中文评估方法 |
|---|---|---|---|---|---|---|---|---|
| [`DemographicSFS`](benchmarks/Biology/DemographicSFS/)<br>位点频率谱人口史反演 | Biology | PopulationGenetics | clipped | active_coalescent_inference | candidate | infer population history with a finite sequencing budget | 在测序预算内跨样本量分配测序,从位点频率谱恢复常量或三期人口史 | 参数恢复 + 留出样本量预测 + 模型不足拒答 + 预算设计 |
| [`CatalystDeactivationLab`](benchmarks/Chemistry/CatalystDeactivationLab/)<br>催化剂失活实验室 | Chemistry | Catalysis | clipped | stateful_reduced_order_kinetics | candidate | run a stateful catalyst laboratory under instrument drift | 在仪器漂移与不可逆失活的催化剂试片上做动力学实验,并行反应器乱序返回 | 动力学参数与漂移恢复;错认试片血缘、重试破坏性实验即失败;密封新批次决策 |
| [`ForceFieldCalibration`](benchmarks/Chemistry/ForceFieldCalibration/)<br>力场假设判别 | Chemistry | MolecularDynamics | clipped | active_pair_potential_hypothesis_laboratory | candidate | discriminate pair-potential hypotheses by active force queries | 主动查询构型的能量与力,在 Mie 12-6 与 Morse 之间判别对势律,并给参数区间 | 竞争假设保留、判别、区间恢复、密封预测与模型拒答分列;库外世界须拒答 |
| [`NMRSpectrumFitting`](benchmarks/Chemistry/NMRSpectrumFitting/)<br>核磁谱峰机制恢复 | Chemistry | Spectroscopy | clipped | physical_sim | candidate | recover supported peak mechanisms across spectra | 从一维核磁谱里恢复未知个数的重叠共振、区分线型与基线漂移;线型族不支持时拒答 | 峰机制恢复 + 移位重建 + 模型不足拒答;残差低会奖励虚假峰 |
| [`ReactionMechanismFitting`](benchmarks/Chemistry/ReactionMechanismFitting/)<br>反应机理辨识 | Chemistry | ChemicalKinetics | clipped | physical_sim | candidate | discover a reaction network by choosing assays | 自选温度、初始混合与采样时刻,从公开一阶反应库里认出稀疏反应网络与其温度依赖 | 机制恢复 + 外推;库外世界须拒答 |
| [`SpinSystemInference`](benchmarks/Chemistry/SpinSystemInference/)<br>自旋体系反演 | Chemistry | Spectroscopy | clipped | community_spin_dynamics_nmrsim | candidate | Given a high-resolution proton NMR spectrum, recover the spin system that produced it: the | 从高分辨质子谱恢复自旋体系的化学位移与两两耦合;二级体系下一级读谱失效 | 机制恢复;误发现率与校准拒答分开报告 |
| [`EnergyBalanceModel`](benchmarks/EarthScience/EnergyBalanceModel/)<br>能量平衡模型辨识 | EarthScience | ClimateScience | clipped | active_system_identification | candidate | identify climate response by choosing forcing experiments | 自选辐射强迫实验,辨识两层气候响应的五个参数;需状态依赖反馈或第三层时拒答 | 参数恢复 + 强迫迁移 + 模型不足拒答;实验预算受限 |
| [`GravityInversion`](benchmarks/EarthScience/GravityInversion/)<br>重力反演 | EarthScience | Geophysics | clipped | physical_sim | candidate | actively survey and infer subsurface density bodies | 主动布设重力测线,反演地下密度体的位置与强度;声明的源族不支持时拒答 | 源恢复 + 外场校验 + 拒答;许多密度分布产生相似地表场 |
| [`RadiativeTransferFit`](benchmarks/EarthScience/RadiativeTransferFit/)<br>辐射传输反演 | EarthScience | AtmosphericScience | clipped | physical_sim | candidate | actively select thermal channels and retrieve an atmospheric mechanism | 主动选择热红外通道与观测角,反演大气温度与光学厚度剖面;未建模的吸收体或云须拒答 | 机制恢复 + 模型不足拒答;观测预算受限,残差低不足以判对 |
| [`ConvectionDiffusionOpt`](benchmarks/Engineering/ConvectionDiffusionOpt/)<br>对流扩散辨识与加热器设计 | Engineering | HeatTransfer | clipped | active_pde_identification_and_robust_design | candidate | identify transport and design a robust heater layout | 在预算内辨识各向异性对流扩散参数,并设计使温度场达标的加热器布局 | 机制恢复 + 目标场设计 + 物理偏移稳健性 + 模型不足拒答 |
| [`IMUBiasCalibration`](benchmarks/Engineering/IMUBiasCalibration/)<br>惯性传感器偏置温漂校准 | Engineering | Sensors | clipped | physical_sim | candidate | design a temperature/pose calibration and attribute its failure | 在观测预算内选择姿态与温度,恢复偏置、温漂和尺度非正交矩阵,并定位非仿射故障轴 | 十二参数校准与迁移预测、故障类型及轴定位、误发现、拒答与覆盖率分列 |
| [`QuartzCrystalMicrobalanceLab`](benchmarks/Engineering/QuartzCrystalMicrobalanceLab/)<br>石英微天平原始信号反演 | Engineering | Sensors | clipped | raw_complex_instrument_pipeline | candidate | infer deposition from raw I/Q sweeps | 从石英微天平的原始 I/Q 扫频里标定复增益漂移、提取谐振并反演薄膜质量与沉积速率 | 原始 IQ 标定、BVD 谐振提取、质量与速率恢复、故障与模型判别、密封停止决策分列 |
| [`ActiveNoiseSpectroscopy`](benchmarks/Physics/ActiveNoiseSpectroscopy/)<br>主动非高斯噪声谱辨识 | Physics | QuantumControl | clipped | analytical_quantum_filter_function | candidate | a Lorentzian spectrum is not a noise mechanism | 在有限量子测量 shots 下选择 Ramsey、echo 与 CPMG 滤波序列,区分共享同一 Lorentzian 功率谱的高斯噪声与单随机电报源,恢复其切换率、方差和占据率 | 三参数机制恢复减不受支持宣称;密封控制外推、误发现率、拒答、尝试覆盖率与 shot 成本分列 |
| [`CriticalPhenomenaLab`](benchmarks/Physics/CriticalPhenomenaLab/)<br>有限尺寸临界现象发现 | Physics | Physics | clipped | physical_sim | candidate | discover phase transitions by choosing finite-size experiments | 主动选择有限尺寸实验,区分连续/一级相变与 crossover 或 BKT-like 世界 | 机制与有限尺寸外推;误发现、拒答与覆盖率分开报告 |
| [`HamiltonianLearning`](benchmarks/Physics/HamiltonianLearning/)<br>哈密顿量学习 | Physics | QuantumDynamics | clipped | community_quantum_dynamics_qutip | candidate | Recover the Hamiltonian of a closed quantum spin chain from the dynamics it generates. | 从自旋链的少数可观测量时间演化里恢复哈密顿量参数 | 参数恢复;误发现率与对称性不可辨识拒答分开报告 |
| [`RadialVelocityPlanets`](benchmarks/Physics/RadialVelocityPlanets/)<br>视向速度找行星 | Physics | Exoplanets | clipped | community_timeseries_astropy | candidate | A star's spectrum shows a periodic Doppler shift. | 从视向速度序列里指认哪些周期是行星:自转、谐波与采样别名不是行星 | 行星恢复;误发现率与别名拒答分开报告 |

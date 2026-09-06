# 任务汇总

由 `python scripts/report_task_inventory.py` 从注册表生成,`tests/test_task_inventory_document.py` 保证它不过期;不要手改。权威实时清单是 `python -m sle list --all`。

| | |
|---|---:|
| 任务包 | 83 |
| optimization | 44 |
| discovery | 39 |
| certified | 5 |
| candidate | 78 |
| 学科 | 7(Biology 7,Chemistry 13,ComputerScience 6,EarthScience 6,Engineering 12,Mathematics 21,Physics 18) |

认证描述的是证据质量,不是难度。标 on-ramp 的任务首个前沿模型提案已够到参考解,不用于配对 Δ 测量。

## Optimization(44)

### 工程设计(engineering_design) — 18

| 任务 | 学科 | 领域 | 打分 | oracle | 认证 | 说明 | 中文题意 | 中文评估方法 |
|---|---|---|---|---|---|---|---|---|
| [`AlloyHardnessOptimization`](benchmarks/Chemistry/AlloyHardnessOptimization/)<br>合金硬度实验设计 | Chemistry | MaterialsScience | uncapped | real_data_replay | candidate | design a study-held alloy batch | 在按论文 DOI 分组的多主元合金数据里做实验设计,选出研究外留出的硬度批次 | 留出硬度 + 多样性 + 代理失效 + 不确定性 + 来源迁移 + 稀疏独立确认;无上限 |
| [`DistillationColumnDesign`](benchmarks/Chemistry/DistillationColumnDesign/)<br>精馏塔设计 | Chemistry | ChemicalProcess | uncapped | equilibrium_stage_process_sim | candidate | robust mixed-integer equilibrium-stage design | 混合整数精馏塔设计:塔板数与进料位置离散,兼顾纯度回收约束与再沸冷凝能耗 | 年化成本;留出迁移与密封变工况分列,无上限 |
| [`ElectrolyteConductivityDesign`](benchmarks/Chemistry/ElectrolyteConductivityDesign/)<br>电解液电导率设计 | Chemistry | Electrochemistry | uncapped | real_data_replay | candidate | allocate EIS assays and select a robust formulation batch | 在高通量电解液数据回放里分配阻抗测定预算,选出稳健的配方批次 | 温度剖面电导率 + 批次多样性 + 重复稳健性 + 留出迁移;无上限 |
| [`SparseRecovery`](benchmarks/ComputerScience/SparseRecovery/)<br>压缩感知稀疏恢复 | ComputerScience | SignalProcessing | clipped | analytical | candidate | compressed sensing signal recovery | 从远少于奈奎斯特的测量里恢复 k 稀疏信号 | 平均恢复信噪比 |
| [`HeatExchangerDesign`](benchmarks/Engineering/HeatExchangerDesign/)<br>换热器帕累托设计 | Engineering | Thermodynamics | uncapped | physical_sim | candidate | discover a multi-fidelity Pareto design archive | 发现换热器的多保真帕累托设计档案,权衡换热量、成本与泵功 | 成本对换热量的帕累托超体积;密封代理一致性、留出迁移与结垢/制造/堵塞稳健性分列,无上限 |
| [`InvertedPendulumSwingUp`](benchmarks/Engineering/InvertedPendulumSwingUp/)<br>倒立摆摆起控制 | Engineering | ControlTheory | clipped | physical_sim | candidate | swing up and robustly stabilize a cart-pole | 设计小车倒立摆的摆起与稳定控制律,兼顾轨道限位与作动器约束 | 摆起效用;偏移工况稳健性分列 |
| [`LowThrustTransfer`](benchmarks/Engineering/LowThrustTransfer/)<br>小推力轨道转移 | Engineering | Astrodynamics | uncapped | physical_sim | candidate | design transferable finite-thrust orbit transfers | 设计可迁移的小推力多圈轨道转移策略,兼顾终端精度与推进剂 | 标称转移效用;留出任务相位与执行误差稳健性分列,无上限 |
| [`MOSFETDoping`](benchmarks/Engineering/MOSFETDoping/)<br>MOSFET 掺杂剖面 | Engineering | Semiconductor | uncapped | physical_sim | candidate | design transferable silicon nMOS halo-profile Pareto archives | 设计可迁移的短沟道硅 nMOS 晕环掺杂剖面帕累托档案 | 驱动电流对漏电的帕累托超体积;密封留出迁移与最差偏移稳健性分列,无上限 |
| [`NeutronDiffusionCriticality`](benchmarks/Engineering/NeutronDiffusionCriticality/)<br>中子扩散临界优化 | Engineering | NuclearEngineering | uncapped | physical_sim | candidate | optimize reactor fuel loading for maximum k-effective | 在平均富集度约束下优化堆芯燃料富集分布以最大化 k_eff | 相对均匀装载的 k_eff 提升;无上限 |
| [`RANSCalibration`](benchmarks/Engineering/RANSCalibration/)<br>RANS 封闭标定 | Engineering | Turbulence | uncapped | physical_sim | candidate | calibrate a transferable algebraic channel-flow closure | 标定可迁移的代数通道流涡黏封闭,同时匹配平均速度与雷诺剪应力 | 真实 DNS 拟合;密封高雷诺数迁移与壁面坐标稳健性分列,无上限 |
| [`RoomImpulseResponse`](benchmarks/Engineering/RoomImpulseResponse/)<br>房间声学处理设计 | Engineering | Acoustics | uncapped | physical_sim | candidate | robust room-acoustic treatment design | 布置声源、吸声与受点,让语音房间同时兼顾清晰度、混响时间与声场均匀度 | 清晰度/混响/均匀度综合效用;一阶反射代理与镜像源长程计算排序不同,含安装误差与老化偏移 |
| [`TrussWeightMinimization`](benchmarks/Engineering/TrussWeightMinimization/)<br>桁架减重 | Engineering | StructuralEngineering | uncapped | analytical | candidate | general truss sizing under physical shifts | 给出跨结构通用的桁架截面尺寸策略,在应力、位移与欧拉屈曲约束下减重 | 标称减重;密封拓扑迁移与载荷/材料/制造稳健性分列,无上限 |
| [`CalorimeterDesign`](benchmarks/Physics/CalorimeterDesign/)<br>量能器设计 | Physics | ParticlePhysics | uncapped | analytical_reduced_order_physics | candidate | graded sampling-calorimeter design curves | 设计分层取样量能器,使能量分辨、线性与簇射包容在多档成本约束下同时改善 | 多能点效用;留出探测器迁移与最差制造偏移分列,无上限 |
| [`DephrasureCodeDesign`](benchmarks/Physics/DephrasureCodeDesign/)<br>退相位擦除信道有限块码态设计 | Physics | QuantumFoundations | uncapped | physical_sim | candidate | finite-block dephrasure input-state design | 为退相位擦除信道的三次或四次使用设计输入密度矩阵因子,提高每次使用的相干信息 | 四例相干信息相对单字母率和已重算公开见证包络的进度均值,不截断;另报超过包络 1e-9 bits/use 的量,不宣称全局纪录或渐近容量 |
| [`DiffractionGratingDesign`](benchmarks/Physics/DiffractionGratingDesign/)<br>衍射光栅设计 | Physics | Optics | uncapped | fourier_modal_rcwa | candidate | polarization-tolerant multilayer relief design | 设计五层一维二元介质浮雕,把透射光导入 +1 衍射级,且对偏振与角度容差 | 开发集目标级效率;偏振/角度/波长与工艺偏移稳健性分列,无上限 |
| [`MultilayerThinFilm`](benchmarks/Physics/MultilayerThinFilm/)<br>多层减反射膜 | Physics | Photonics | clipped | physical_sim | certified | design a broadband antireflection coating | 设计可见光全谱段的多层宽带减反射膜 | 宽带减反射质量;物理下界为零平均反射 |
| [`MutuallyUnbiasedBases6`](benchmarks/Physics/MutuallyUnbiasedBases6/)<br>六维近似互无偏基 | Physics | QuantumFoundations | uncapped | analytical | candidate | optimize four approximate measurement bases exactly | 在六维复空间构造四组尽量互无偏的测量基,用有界 Gaussian 整数射线表示并精确验证正交性与跃迁概率 | 精确 ASD 对固定 Raynal 有理重构归一化且不截断;公式可廉价达到 1,真正超越另由严谨代数区间旗标判定,本表示不覆盖精确 MUB 存在性 |
| [`SuperconductorTcRecord`](benchmarks/Physics/SuperconductorTcRecord/)<br>超导临界温度纪录搜索 | Physics | Superconductivity | uncapped | allen_dynes_formula_solved_to_real_anchors | candidate | beat the published record by computing where Allen-Dynes says to look | 在真实设备压力上限下,用 Allen-Dynes 公式在五个真实超导体系间搜索已确认临界温度最高的(体系,压力)组合,并避开一个从未被实现的理论预测(隐含电子-声子耦合超过物理合理上限) | 真实Tc除以已发表记录250K的直接比值;无上限,可超过已发表记录 |

### 开放组合纪录(combinatorial,无上限) — 18

| 任务 | 学科 | 领域 | 打分 | oracle | 认证 | 说明 | 中文题意 | 中文评估方法 |
|---|---|---|---|---|---|---|---|---|
| [`MatrixMultiplicationRank`](benchmarks/ComputerScience/MatrixMultiplicationRank/)<br>矩阵乘法秩 | ComputerScience | Algorithm | uncapped | analytical | certified | discover faster matrix-multiplication algorithms | 搜索双线性张量分解,减少矩阵乘法所需的标量乘法次数 | 对最好已知乘法数的平均进度;无上限 |
| [`TensorRank555`](benchmarks/ComputerScience/TensorRank555/)<br>5x5 与 6x6 张量秩 | ComputerScience | Algorithm | uncapped | analytical | candidate | numerical complex decompositions for 5×5 and 6×6 multiplication | 为 5x5 与 6x6 矩阵乘法找有限精度复系数分解,秩低于已知构造 | 对最好已知乘法数的平均进度;无上限,实例与 MatrixMultiplicationRank 不相交 |
| [`CapSet`](benchmarks/Mathematics/CapSet/)<br>Cap Set 构造 | Mathematics | Mathematics | uncapped | analytical | certified | find large cap sets in Z_3^n | 在 Z_3^n 里构造更大的 cap set(无三点共线) | 对最好已知规模的平均进度;无上限 |
| [`CapSetFrontier`](benchmarks/Mathematics/CapSetFrontier/)<br>Cap Set 未证明维度 | Mathematics | Mathematics | uncapped | analytical | candidate | large cap sets in dimensions that are still open | 在最大值尚未证明的 n=7,8,9 上构造更大的 cap set | 对最好已知规模的平均进度;无上限,与 CapSet 的维度不相交 |
| [`CirclePacking`](benchmarks/Mathematics/CirclePacking/)<br>圆堆积 | Mathematics | Optimization | uncapped | analytical | certified | pack unit circles into the smallest square | 把 N 个单位圆装进边长最小的正方形 | 对最好已知装填的平均缺口闭合;无上限 |
| [`DegreeDiameterGraph`](benchmarks/Mathematics/DegreeDiameterGraph/)<br>度-直径极值图构造 | Mathematics | Mathematics | uncapped | analytical | candidate | build a bigger bounded-degree, bounded-diameter graph than the published record | 在三组给定的 (最大度 d, 直径 k) 上构造尽可能大的图——2026 年有论文报道通过与可浏览器访问的 LLM 交互刷新过下界 | 对度-直径问题维护表中最好已知顶点数的平均进度;无上限,均未被证明最优 |
| [`ErdosMinimumOverlap`](benchmarks/Mathematics/ErdosMinimumOverlap/)<br>Erdős 最小重叠划分 | Mathematics | Mathematics | uncapped | analytical | candidate | match the exactly-known minimum overlap at three sizes | 把 {1,...,2n} 分成两个等大小的集合,让某个差值出现的最多次数尽量小——Erdős 最小重叠问题,渐近常数在 2025-2026 年被 AlphaEvolve 等多次刷新 | 对三个 n(8、11、15)已被穷举搜索证明的精确最优值的平均进度;这三个规模都是硬上限,已披露,因为超过 n=15 没有可核实的具体最好记录 |
| [`HeilbronnTrianglePacking`](benchmarks/Mathematics/HeilbronnTrianglePacking/)<br>Heilbronn 三角形点集 | Mathematics | Mathematics | uncapped | analytical | candidate | beat the published record for well-spread points in a square | 在单位正方形内放 n 个点,让任意 3 点构成的三角形最小面积尽量大——经典的 Heilbronn 三角形问题 | 对 Erich's Packing Center 维护的记录表的平均进度;n=8 已证明最优(硬上限,已披露),n=10、n=11、n=12 仅是最好已知记录,真实无上限 |
| [`KissingNumber`](benchmarks/Mathematics/KissingNumber/)<br>接触数构造 | Mathematics | Mathematics | uncapped | analytical | candidate | pack more unit spheres around one sphere | 在 9、10、12 维构造更多与中心球相切的单位球 | 固定容差下对最好已知接触数的平均进度;无上限 |
| [`NarrowAdmissibleTuple`](benchmarks/Mathematics/NarrowAdmissibleTuple/)<br>窄可容许素数元组 | Mathematics | Mathematics | uncapped | analytical | candidate | find a narrower admissible k-tuple than Polymath8b's | 构造比 Polymath8b 已发表直径更小的可容许 k-元组(k=50、54)——有界素数间隔猜想计算核心的同一对象 | 已发表直径的归一化进度(k=50 锚点 246 一手引用确认,k=54 锚点 270 仅二手来源);无上限 |
| [`NonlinearCodeRecords`](benchmarks/Mathematics/NonlinearCodeRecords/)<br>非线性码规模纪录 | Mathematics | Mathematics | uncapped | analytical | candidate | build a bigger binary code than a linear one can be | 在四个 A(n,d) 未闭合的参数上构造尽可能大的二元码;已发表纪录全部由非线性码持有,线性构造够不到 | 从平凡分块重复构造到已发表纪录的平均进度,无上限;验证只是逐对汉明距离计数,与构造方法无关 |
| [`RamseyLowerBound`](benchmarks/Mathematics/RamseyLowerBound/)<br>Ramsey 下界染色 | Mathematics | Mathematics | uncapped | analytical | candidate | construct larger (s,t)-Ramsey colorings | 构造更大的 (s,t)-Ramsey 染色以提高下界 | 对最好已知染色阶数的平均进度;无上限 |
| [`SchurPartition`](benchmarks/Mathematics/SchurPartition/)<br>Schur 无和分拆 | Mathematics | Mathematics | uncapped | analytical | candidate | build a longer sum-free k-partition than the published record | 为给定的分组数 k 构造尽可能长的无和分拆(每组内不含 a+b=c,允许 a=b) | k=4 对照证明最优的 Schur 数(硬上限,已披露);k=6、k=7 对照尚未证明最优的最好已知下界(真实无上限空间) |
| [`ShannonCapacityConstruction`](benchmarks/Mathematics/ShannonCapacityConstruction/)<br>七环五次强积独立集构造 | Mathematics | Mathematics | uncapped | analytical | candidate | exact fixed-fifth-power C7 independent-set construction | 在七环的固定五次强积中构造更大的独立集,提交七元字母表上的五位码字;不求完整 Shannon 容量 | 逐对精确验证环距离,按码字数从 243 词乘积基线到 367 词历史构造归一化且不截断;公开重放得 1,超出仅表示超过该见证 |
| [`Superpermutation`](benchmarks/Mathematics/Superpermutation/)<br>超排列最短串 | Mathematics | Mathematics | uncapped | analytical | candidate | shorter strings that contain every permutation | 构造更短的超排列字符串,使其包含全部排列作为连续子串 | 对最短已知长度的平均进度;无上限 |
| [`VanDerWaerdenColoring`](benchmarks/Mathematics/VanDerWaerdenColoring/)<br>van der Waerden 无进染色 | Mathematics | Mathematics | uncapped | analytical | candidate | build a longer AP-free coloring than the published witness | 为给定的颜色数与等差数列长度构造尽可能长的、不含单色等差数列的染色 | 两组对照证明最优的 van der Waerden 数(硬上限,已披露)、一组对照尚未证明最优的最好已知下界(真实无上限空间) |
| [`ZarankiewiczMatrix`](benchmarks/Mathematics/ZarankiewiczMatrix/)<br>Zarankiewicz 极值矩阵 | Mathematics | Mathematics | uncapped | analytical | candidate | build a denser K3,3-free 0/1 matrix than the published record | 在三组给定的 (m,n) 规模上构造不含 3x3 全一子矩阵的更密 0/1 矩阵——2026 年 LLM 进化搜索(OpenEvolve,本仓库自带的搜索后端之一)刚刷新过的极值图论问题 | 对最新发表下界(z(m,n;3,3) 的已发表值)的平均进度;无上限,且这些是尚未被上界证明封顶的下界纪录 |
| [`QuantumErrorDecoder`](benchmarks/Physics/QuantumErrorDecoder/)<br>表面码解码器 | Physics | QuantumErrorCorrection | uncapped | stim_stabilizer_circuit_sampling | candidate | decode rotated surface-code memory below threshold | 为旋转表面码存储设计阈值以下的解码器 | 相对最小权完美匹配的逻辑错误率对数下降;无上限 |

### 分子与大分子设计(molecular_design) — 5

| 任务 | 学科 | 领域 | 打分 | oracle | 认证 | 说明 | 中文题意 | 中文评估方法 |
|---|---|---|---|---|---|---|---|---|
| [`ProteinStabilityDesign`](benchmarks/Biology/ProteinStabilityDesign/)<br>蛋白稳定性批次设计 | Biology | ProteinEngineering | uncapped | real_data_replay | candidate | allocate assays and design a stable protein batch | 在蛋白稳定性实验回放里分配测定预算,设计双点突变批次 | 留出稳定性前十分位 + 多样性 + 蛋白酶稳健性 + 结构域迁移;无上限 |
| [`RNAEnsembleDesign`](benchmarks/Biology/RNAEnsembleDesign/)<br>RNA 系综设计 | Biology | RNAEngineering | uncapped | community_thermodynamics_viennarna | candidate | Design an RNA sequence that folds into a given secondary structure — not merely as its | 设计 RNA 序列,使目标二级结构在整个玻尔兹曼系综上而非仅 MFE 上成立 | 对 ViennaRNA 反折叠的系综缺陷;密封目标,无上限 |
| [`RNAInverseDesign`](benchmarks/Biology/RNAInverseDesign/)<br>RNA 约束反折叠 | Biology | RNAEngineering | uncapped | exact_dynamic_programming | candidate | design a constrained sequence for a target ensemble | 在长度、字母表、GC 与基序约束下设计目标系综概率高的 RNA 序列 | 目标系综概率 + MFE 迁移 + 代理误升迁;配对相容只是代理,无上限 |
| [`LennardJonesCluster`](benchmarks/Chemistry/LennardJonesCluster/)<br>Lennard-Jones 团簇 | Chemistry | Chemistry | uncapped | analytical | certified | minimize the energy of atomic clusters | 求 Lennard-Jones 原子簇的最低能量几何构型 | 对全局最小的平均缺口闭合;无上限 |
| [`MolecularLeadOptimization`](benchmarks/Chemistry/MolecularLeadOptimization/)<br>分子先导组合优化 | Chemistry | MedicinalChemistry | uncapped | rdkit_cheminformatics_property_filter | candidate | build a diverse portfolio of novel, developable leads | 构建结构多样、可开发的新颖先导化合物组合,而非单个分子 | 多样性约束下的组合价值,对标已上市药物;无上限 |

### certificate_bound — 3

| 任务 | 学科 | 领域 | 打分 | oracle | 认证 | 说明 | 中文题意 | 中文评估方法 |
|---|---|---|---|---|---|---|---|---|
| [`ChowlaCosineCertificate`](benchmarks/Mathematics/ChowlaCosineCertificate/)<br>Chowla 余弦下界证书 | Mathematics | Mathematics | uncapped | analytical | candidate | certify a smaller global cosine bound | 选择有限个整数频率,并用有理平方模的完整 Laurent 恒等式证明余弦和在整条圆周上的全局下界 | 三个规模的精确证书进度取均值且 1 以上不截断;1 是公开的贪心 Sidon 构造而非全局最优,廉价局部搜索已到约 1.0074 |
| [`SpherePackingCertificate`](benchmarks/Mathematics/SpherePackingCertificate/)<br>球堆积上界证书 | Mathematics | DiscreteGeometry | uncapped | analytical | candidate | prove a packing bound, exactly | 为球堆积密度给出一份可精确验证的上界证明。Cohn-Elkies 定理把上界化为分析问题:找一个函数,它在半径外非正、其傅里叶变换处处非负。除 1/2/3/8/24 维外全部开放——12 维已知最好堆积 0.03704,最好的证明只到 0.06279。取变量 w=2π‖x‖²,拉盖尔特征基的系数是有理的,两条假设都变成有理半轴上的有理多项式,而单变量多项式在半轴非负当且仅当能写成 σ₀+wσ₁,这个刻画是完备的。 | 四个维度(8/12/16/20)取均值,不设上限。零点是闭式的二项证书——这个方法不花力气就能给出的东西;1.0 是已发表的 Cohn-Elkies 数值界,而与之等强的精确有理证书似乎在任何维度都还没有人发表过。有理数精确验证,提交浮点判零:网格线性规划这个教科书方法会给出假界(16 阶时 8 维报 0.06237,低于 E8 格实际达到的 0.0625)。 |
| [`BellBoundCertificate`](benchmarks/Physics/BellBoundCertificate/)<br>贝尔不等式上界证书 | Physics | QuantumFoundations | uncapped | analytical | candidate | prove an upper bound, do not just compute one | 为贝尔泛函的量子最大值给出一份可精确验证的上界证明:提交一组基词与若干加权平方,使它们的和恰好等于 beta*I - B。CHSH 的答案是无理数 2√2,只能逼近;I3322 的量子值至今未知,NPA 层级 1 给 0.375、层级 2 给 0.25102173、已知最好值 0.25087538 要到层级 4 以上。 | 四个实例(CHSH 与三种基词预算下的 I3322)取均值,不设上限。分数是所证界到已知量子值距离的对数进步:免费的层级 1 界记 0,已发表的层级 2 界记 1,超过则大于 1。有理数精确验证,提交浮点数直接判零——数值 SDP 解不是证明。 |

## Discovery(39)

### 公式(formula) — 6

| 任务 | 学科 | 领域 | 打分 | oracle | 认证 | 说明 | 中文题意 | 中文评估方法 |
|---|---|---|---|---|---|---|---|---|
| [`EnzymeKineticsLaw`](benchmarks/Biology/EnzymeKineticsLaw/)<br>酶动力学律辨识 | Biology | SystemsBiology | clipped | physical_sim | candidate | A purified enzyme is in front of you. · on-ramp,不配对 | 在测定预算内自选底物与抑制剂浓度,判定这个酶服从六条已发表速率律中的哪条,或都不服从 | 速率律辨识 + 拒答 + 密封外推预测 |
| [`AMOCTippingRefusal`](benchmarks/EarthScience/AMOCTippingRefusal/)<br>AMOC 折叠拒答 | EarthScience | Oceanography | clipped | physical_sim | candidate | a dip in the fingerprint is not a fold | AMOC 指纹序列里区分尚未发生的立方折叠、纯红噪声与冰约束唯一吸引子 | 折叠恢复 + 红噪声与冰约束拒答;指纹下降不等于将要崩溃 |
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
| [`SurvivorshipConfoundedDesign`](benchmarks/ComputerScience/SurvivorshipConfoundedDesign/)<br>幸存者偏差下的效应估计 | ComputerScience | CausalDiscovery | clipped | physical_sim | candidate | association among survivors is not a treatment effect | 每一行数据都已被结果相关的筛选选中,在幸存者表里估计真实处理效应 | 处理效应恢复;混杂开启的伪关联须识别,无 T→Y 边时不得宣称效应 |
| [`BlackBoxGroupIdentification`](benchmarks/Mathematics/BlackBoxGroupIdentification/)<br>黑盒群同构辨识 | Mathematics | Mathematics | clipped | analytical | candidate | A finite set of `order` labelled elements and a black-box product: `mul(a, b)` returns the label | 只给黑盒乘法与随机标号,在查询预算内从公开构造目录里辨识群的同构类 | 目录 id 精确门控;非群与目录外两种拒答理由分开计分,阶数分布不足以辨识 |
| [`HiddenCouplingNetwork`](benchmarks/Physics/HiddenCouplingNetwork/)<br>隐藏耦合网络重建 | Physics | Physics | clipped | physical_sim | candidate | A network of `units` observed units relaxes to a steady state under constant drive. | 实验次数少于单元数,从多单元驱动的稳态里恢复带符号的直接耦合图;存在未观测单元时拒答 | 带符号边 F1;间接路径、tanh 非线性与隐藏单元造成的稠密低秩耦合分别记误发现 |

### 证据(evidence) — 7

| 任务 | 学科 | 领域 | 打分 | oracle | 认证 | 说明 | 中文题意 | 中文评估方法 |
|---|---|---|---|---|---|---|---|---|
| [`ProspectiveMetaAnalysis`](benchmarks/Biology/ProspectiveMetaAnalysis/)<br>前瞻荟萃分析 | Biology | EvidenceSynthesis | clipped | prospective_evidence_synthesis | candidate | synthesize registered evidence and design confirmation | 在注册表加文献语料里筛研究、识别同一人群血缘的重复报告与换端点,做异质性荟萃回归 | 筛选、证据血缘完整性、荟萃回归、校准拒答、下一步研究信息量与前瞻确认分列 |
| [`ForcedSignalAttribution`](benchmarks/EarthScience/ForcedSignalAttribution/)<br>强迫信号检测归因 | EarthScience | ClimateScience | clipped | statistical_sim | candidate | A regional field is observed for `years` years over `regions` regions. | 在控制年预算下判断区域记录里是否含强迫响应、估其幅度与区间;模型指纹或变率不可信时拒答 | 检测率、幅度分、区间覆盖分列;红噪声假趋势与安静模型均记误发现 |
| [`ModalDamageAttribution`](benchmarks/Engineering/ModalDamageAttribution/)<br>模态损伤归因 | Engineering | StructuralEngineering | clipped | physical_sim | candidate | is the modal shift damage, or the weather? | 在受预算约束的测量日里判断模态频率的偏移是不是某个内部元件的刚度损伤、是哪一个、损失多少;支座变化导致的偏移须拒答 | 定位精确门控 + 严重度容差评分;温度对频率比精确抵消,健康结构误报与支座变化误判分别记误发现,分数标尺锚在全弃权为零 |
| [`HeavyTailEvidence`](benchmarks/Mathematics/HeavyTailEvidence/)<br>重尾证据判别 | Mathematics | Mathematics | clipped | physical_sim | candidate | A positive sample is either a power law with known `xmin`, a lognormal above `xmin`, a | 在已知 xmin 下判断样本是幂律还是对数正态;指数截断或样本过短须拒答 | 家族恢复 + 截断/小样本拒答;不是质量窗口的 look-elsewhere,也不是不相容常数调和 |
| [`DiscrepantMeasurements`](benchmarks/Physics/DiscrepantMeasurements/)<br>不相容测量调和 | Physics | ParticlePhysics | clipped | statistical_sim | candidate | Eight groups have measured the same physical constant. · on-ramp,不配对 | 八组测量同一常数但彼此不相容,诊断这批证据出了什么问题并给最佳值或判定没有最佳值 | 缺陷诊断 + 收费的内部一致性检验 + 拒答 |
| [`LookElsewhereAnomaly`](benchmarks/Physics/LookElsewhereAnomaly/)<br>多窗口扫描的全局显著性 | Physics | ParticlePhysics | clipped | physical_sim | candidate | local 5σ is not a discovery | 一张质量谱在多个窗口里扫描,判定局域 5σ 在计入试验因子后还剩多少 | look-elsewhere 后的全局显著性;边带拒绝公开本底时须拒答 |
| [`PTAHellingsDowns`](benchmarks/Physics/PTAHellingsDowns/)<br>脉冲星阵四极相关 | Physics | Gravitation | clipped | physical_sim | candidate | a common process is not a gravitational-wave background | 脉冲星计时阵里区分 Hellings-Downs 四极相关(引力波背景)与钟差单极、星历偶极、共同红噪声 | 四极 vs 单极判别与拒答;共同过程不等于引力波背景 |

### 物质(substance) — 5

| 任务 | 学科 | 领域 | 打分 | oracle | 认证 | 说明 | 中文题意 | 中文评估方法 |
|---|---|---|---|---|---|---|---|---|
| [`CrowdedSpectrumAssignment`](benchmarks/Chemistry/CrowdedSpectrumAssignment/)<br>混叠谱物种指认 | Chemistry | Spectroscopy | clipped | physical_sim | candidate | name the library species in a blended spectrum | 在混叠谱里指认封闭库中的物种;两个近线的混合与第三个物种不可区分,变焦要花预算 | 库物种指认 + 别名拒答 |
| [`PhaseDiagramDiscovery`](benchmarks/Chemistry/PhaseDiagramDiscovery/)<br>相图发现 | Chemistry | MaterialsScience | clipped | physical_sim | candidate | An isothermal section of a binary system A-B. | 在合成预算下测定二元等温相图:哪些平衡相存在、各占哪段成分,或该体系根本达不到平衡 | 相集精确门控 + 杠杆定律边界精度;两相区叠加、杂质峰、动力学冻结须区分,冻结体系须拒答 |
| [`QuinaryConvexHull`](benchmarks/Chemistry/QuinaryConvexHull/)<br>五元凸包稳定相 | Chemistry | MaterialsScience | clipped | analytical | candidate | E_f < 0 is not a new stable | 五元体系里给出凸包上真正稳定的非一元相;生成焓小于零不等于新稳定相 | 精确非一元凸包顶点;玻璃态须拒答 |
| [`MethaneSourceAttribution`](benchmarks/EarthScience/MethaneSourceAttribution/)<br>甲烷源归因 | EarthScience | AtmosphericChemistry | clipped | analytical | candidate | say which sources moved, or say the record cannot tell | 在固定观测预算下,判断二十年里哪些甲烷排放部门发生了变化——以及在记录判不了时说出判不了。2007 年后大气甲烷重新增长、δ¹³C 变轻,驱动因素至今没有定论:同位素证据被读成主要是微生物源,而这个读法又被以源signature空间变异和汇的未解问题反驳。四类世界只有两类可答:化石与生物质燃烧会让 δ¹³C 上升、乙烷能分开;单一微生物源变化足够大时部门清单能认出;而纯汇变化和两个微生物源同时小幅变化都判不了。 | 三轴分开报、永不平均:机制恢复率、假发现率(带分母)、校准拒答率,外加是否尝试过的计数。总分是三者之积,全弃权与从不弃权都恰好得零。关键在于纯汇变化能被纯源变化复现到观测噪声以内(约化失配 0.00),而它看起来最像废弃物在小幅增加——baseline 在八个纯汇案例里点名废弃物五次。出路是买废弃物清单,发现它没变,把自上而下与自下而上的矛盾当作弃权的理由。 |
| [`TransmissionSpectrumSpecies`](benchmarks/Physics/TransmissionSpectrumSpecies/)<br>透射光谱分子判定 | Physics | Exoplanets | clipped | analytical | candidate | say which molecules are there, or say you cannot tell | 在固定的凌星次数预算下,判断系外行星大气里有哪些分子——以及在观测无法判定时说出无法判定。K2-18b 的 DMS 之争正是这个问题:多次重分析的结论是那些特征并非唯一可辨识。四类世界里有三类不可辨识,而且原因各不相同:灰云层一次压平所有特征;混淆对在任何预算分配下都分不开(单振幅误差是其和的 24.5 倍);暗弱系统把整个预算压在最好波段也到不了 1σ。只有第三类是噪声。 | 三轴分开报、永不平均:机制恢复率、假发现率(带分母)、校准拒答率,外加是否尝试过的计数。总分是三者之积,归一化到全弃权恰好得零——从不弃权因拒答率为零也得零,两种退化策略都是零,靠尝试率把它们区分开。点名混淆对里任何一方都算假发现,即使其中一个确实存在:世界不决定是哪一个。 |

### 参数反演(parameter_inversion) — 15

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
| [`QuartzCrystalMicrobalanceLab`](benchmarks/Engineering/QuartzCrystalMicrobalanceLab/)<br>石英微天平原始信号反演 | Engineering | Sensors | clipped | raw_complex_instrument_pipeline | candidate | infer deposition from raw I/Q sweeps | 从石英微天平的原始 I/Q 扫频里标定复增益漂移、提取谐振并反演薄膜质量与沉积速率 | 原始 IQ 标定、BVD 谐振提取、质量与速率恢复、故障与模型判别、密封停止决策分列 |
| [`ActiveNoiseSpectroscopy`](benchmarks/Physics/ActiveNoiseSpectroscopy/)<br>主动非高斯噪声谱辨识 | Physics | QuantumControl | clipped | analytical_quantum_filter_function | candidate | a Lorentzian spectrum is not a noise mechanism | 在有限量子测量 shots 下选择 Ramsey、echo 与 CPMG 滤波序列,区分共享同一 Lorentzian 功率谱的高斯噪声与单随机电报源,恢复其切换率、方差和占据率 | 三参数机制恢复减不受支持宣称;密封控制外推、误发现率、拒答、尝试覆盖率与 shot 成本分列 |
| [`CriticalPhenomenaLab`](benchmarks/Physics/CriticalPhenomenaLab/)<br>有限尺寸临界现象发现 | Physics | Physics | clipped | physical_sim | candidate | discover phase transitions by choosing finite-size experiments | 主动选择有限尺寸实验,区分连续/一级相变与 crossover 或 BKT-like 世界 | 机制与有限尺寸外推;误发现、拒答与覆盖率分开报告 |
| [`HamiltonianLearning`](benchmarks/Physics/HamiltonianLearning/)<br>哈密顿量学习 | Physics | QuantumDynamics | clipped | community_quantum_dynamics_qutip | candidate | Recover the Hamiltonian of a closed quantum spin chain from the dynamics it generates. | 从自旋链的少数可观测量时间演化里恢复哈密顿量参数 | 参数恢复;误发现率与对称性不可辨识拒答分开报告 |
| [`RadialVelocityPlanets`](benchmarks/Physics/RadialVelocityPlanets/)<br>视向速度找行星 | Physics | Exoplanets | clipped | community_timeseries_astropy | candidate | A star's spectrum shows a periodic Doppler shift. | 从视向速度序列里指认哪些周期是行星:自转、谐波与采样别名不是行星 | 行星恢复;误发现率与别名拒答分开报告 |

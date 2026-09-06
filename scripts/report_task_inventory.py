#!/usr/bin/env python3
"""Render TASKS.md, the human-readable inventory of every task package, from the registry.

The README links to this document as "the current task summary". A hand-maintained table would
drift the first time a task is added, so the table is generated: registry (`sle.registry`) for
the packages, `sle/conf/exam_taxonomy.yaml` for the form cell each one fills, `sle/certification.yaml`
for the evidence status, `frontier_eval/metadata.yaml` for score mode and oracle type, and the first
heading of `Task.md` for the one-line description. `--check` exits non-zero when the committed file
is stale, which is what the test asserts.

Usage:
    python scripts/report_task_inventory.py            # rewrite TASKS.md
    python scripts/report_task_inventory.py --check    # exit 1 if TASKS.md is stale
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import Counter, OrderedDict
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sle.registry import list_tasks  # noqa: E402

OUTPUT = ROOT / "TASKS.md"
TAXONOMY = ROOT / "sle" / "conf" / "exam_taxonomy.yaml"
CERTIFICATION = ROOT / "sle" / "certification.yaml"

# Chinese name per task, shown in the first column beside the English directory name. The
# directory name is the identifier and never changes; this is what a Chinese reader scans for.
CHINESE_NAMES = {
    'Bioprocess/FedBatchBioprocessDesign': "补料发酵稳健设计",
    "Acoustics/RoomImpulseResponse": "房间声学处理设计",
    "Algorithm/GraphFromDistances": "距离查询重建图",
    "Algorithm/MatrixMultiplicationRank": "矩阵乘法秩",
    "Algorithm/TensorRank555": "5x5 与 6x6 张量秩",
    "Astrodynamics/LowThrustTransfer": "小推力轨道转移",
    "AtmosphericScience/RadiativeTransferFit": "辐射传输反演",
    "Catalysis/CatalystDeactivationLab": "催化剂失活实验室",
    "CausalDiscovery/InterventionalSCM": "干预式结构因果模型",
    "CausalDiscovery/SurvivorshipConfoundedDesign": "幸存者偏差下的效应估计",
    "ChemicalKinetics/ReactionMechanismFitting": "反应机理辨识",
    "ChemicalProcess/DistillationColumnDesign": "精馏塔设计",
    "Chemistry/LennardJonesCluster": "Lennard-Jones 团簇",
    "ClimateScience/EnergyBalanceModel": "能量平衡模型辨识",
    "ClimateScience/ForcedSignalAttribution": "强迫信号检测归因",
    "ControlTheory/InvertedPendulumSwingUp": "倒立摆摆起控制",
    "DynamicalSystems/ActiveLawDiscovery": "主动定律发现",
    "Electrochemistry/ElectrolyteConductivityDesign": "电解液电导率设计",
    "EvidenceSynthesis/ProspectiveMetaAnalysis": "前瞻荟萃分析",
    "Exoplanets/RadialVelocityPlanets": "视向速度找行星",
    "Physics/CriticalPhenomenaLab": "有限尺寸临界现象发现",
    "Geophysics/GravityInversion": "重力反演",
    "Gravitation/PTAHellingsDowns": "脉冲星阵四极相关",
    "HeatTransfer/ConvectionDiffusionOpt": "对流扩散辨识与加热器设计",
    "MaterialsScience/AlloyHardnessOptimization": "合金硬度实验设计",
    "MaterialsScience/PhaseDiagramDiscovery": "相图发现",
    "MaterialsScience/QuinaryConvexHull": "五元凸包稳定相",
    "Mathematics/BlackBoxGroupIdentification": "黑盒群同构辨识",
    "Mathematics/CapSet": "Cap Set 构造",
    "Mathematics/CapSetFrontier": "Cap Set 未证明维度",
    "Mathematics/ErdosMinimumOverlap": "Erdős 最小重叠划分",
    "Mathematics/HeilbronnTrianglePacking": "Heilbronn 三角形点集",
    "Mathematics/HeavyTailEvidence": "重尾证据判别",
    "Mathematics/KissingNumber": "接触数构造",
    "Mathematics/NarrowAdmissibleTuple": "窄可容许素数元组",
    "Mathematics/RamseyLowerBound": "Ramsey 下界染色",
    "Mathematics/ZarankiewiczMatrix": "Zarankiewicz 极值矩阵",
    "Mathematics/DegreeDiameterGraph": "度-直径极值图构造",
    "Mathematics/VanDerWaerdenColoring": "van der Waerden 无进染色",
    "Mathematics/SchurPartition": "Schur 无和分拆",
    "Mathematics/SequenceLawRecovery": "整数序列递推恢复",
    "Mathematics/Superpermutation": "超排列最短串",
    "AtmosphericChemistry/MethaneSourceAttribution": "甲烷源归因",
    "Turbulence/WallClosureDiscovery": "壁面湍流闭合律发现",
    "Exoplanets/TransmissionSpectrumSpecies": "透射光谱分子判定",
    "DiscreteGeometry/SpherePackingCertificate": "球堆积上界证书",
    "QuantumFoundations/BellBoundCertificate": "贝尔不等式上界证书",
    "InformationTheory/ShannonCapacityCertificate": "奇圈香农容量双侧证书",
    "Mathematics/NonlinearCodeRecords": "非线性码规模纪录",
    "MedicinalChemistry/MolecularLeadOptimization": "分子先导组合优化",
    "MolecularDynamics/ForceFieldCalibration": "力场假设判别",
    "NuclearEngineering/NeutronDiffusionCriticality": "中子扩散临界优化",
    "Oceanography/AMOCTippingRefusal": "AMOC 折叠拒答",
    "Optics/DiffractionGratingDesign": "衍射光栅设计",
    "Optimization/CirclePacking": "圆堆积",
    "ParticlePhysics/CalorimeterDesign": "量能器设计",
    "ParticlePhysics/DiscrepantMeasurements": "不相容测量调和",
    "ParticlePhysics/LookElsewhereAnomaly": "多窗口扫描的全局显著性",
    "Photonics/MultilayerThinFilm": "多层减反射膜",
    "Physics/ComplexBoseLaw": "复玻色占据律",
    "Physics/HiddenCouplingNetwork": "隐藏耦合网络重建",
    "PopulationGenetics/DemographicSFS": "位点频率谱人口史反演",
    "ProteinEngineering/ProteinStabilityDesign": "蛋白稳定性批次设计",
    "QuantumDynamics/HamiltonianLearning": "哈密顿量学习",
    "QuantumControl/ActiveNoiseSpectroscopy": "主动非高斯噪声谱辨识",
    "QuantumErrorCorrection/QuantumErrorDecoder": "表面码解码器",
    "RNAEngineering/RNAEnsembleDesign": "RNA 系综设计",
    "RNAEngineering/RNAInverseDesign": "RNA 约束反折叠",
    "Semiconductor/MOSFETDoping": "MOSFET 掺杂剖面",
    "Sensors/QuartzCrystalMicrobalanceLab": "石英微天平原始信号反演",
    "SignalProcessing/SparseRecovery": "压缩感知稀疏恢复",
    "Spectroscopy/CrowdedSpectrumAssignment": "混叠谱物种指认",
    "StructuralEngineering/ModalDamageAttribution": "模态损伤归因",
    "Spectroscopy/NMRSpectrumFitting": "核磁谱峰机制恢复",
    "Spectroscopy/SpinSystemInference": "自旋体系反演",
    "StructuralEngineering/TrussWeightMinimization": "桁架减重",
    "Superconductivity/SuperconductorTcRecord": "超导临界温度纪录搜索",
    "SystemsBiology/EnzymeKineticsLaw": "酶动力学律辨识",
    "SystemsBiology/GeneNetworkIntervention": "基因网络干预设计",
    "Thermodynamics/HeatExchangerDesign": "换热器帕累托设计",
    "Turbulence/RANSCalibration": "RANS 封闭标定",
}

# One-line Chinese brief and scoring note per task. Written by hand: the English Task.md
# cannot be machine-translated into something a reader can trust, and the table is read by
# people deciding which task to look at. A task without an entry fails the inventory test,
# so a new package cannot silently ship without one.
CHINESE_BRIEFS = {
    'Bioprocess/FedBatchBioprocessDesign': (
        "设计三阶段补料、诱导与收获时刻,在溢流代谢和氧传递限制下保持生产率",
        "跨生长与氧传递偏移的最坏生产率;体积、乙酸和终态生物量硬门控"),
    "Acoustics/RoomImpulseResponse": (
        "布置声源、吸声与受点,让语音房间同时兼顾清晰度、混响时间与声场均匀度",
        "清晰度/混响/均匀度综合效用;一阶反射代理与镜像源长程计算排序不同,含安装误差与老化偏移"),
    "Algorithm/GraphFromDistances": (
        "在有限次距离查询下重建加权网络的边:短距离不等于相邻,可能是两条短边的两跳路径",
        "边恢复 F1;误发现率与不可辨识拒答分开报告"),
    "Algorithm/MatrixMultiplicationRank": (
        "搜索双线性张量分解,减少矩阵乘法所需的标量乘法次数",
        "对最好已知乘法数的平均进度;无上限"),
    "Algorithm/TensorRank555": (
        "为 5x5 与 6x6 矩阵乘法找有限精度复系数分解,秩低于已知构造",
        "对最好已知乘法数的平均进度;无上限,实例与 MatrixMultiplicationRank 不相交"),
    "Astrodynamics/LowThrustTransfer": (
        "设计可迁移的小推力多圈轨道转移策略,兼顾终端精度与推进剂",
        "标称转移效用;留出任务相位与执行误差稳健性分列,无上限"),
    "AtmosphericScience/RadiativeTransferFit": (
        "主动选择热红外通道与观测角,反演大气温度与光学厚度剖面;未建模的吸收体或云须拒答",
        "机制恢复 + 模型不足拒答;观测预算受限,残差低不足以判对"),
    "Catalysis/CatalystDeactivationLab": (
        "在仪器漂移与不可逆失活的催化剂试片上做动力学实验,并行反应器乱序返回",
        "动力学参数与漂移恢复;错认试片血缘、重试破坏性实验即失败;密封新批次决策"),
    "CausalDiscovery/InterventionalSCM": (
        "用干预实验打破马尔可夫等价,恢复隐藏线性无环结构因果模型的有向图与系数",
        "有向图与结构系数恢复;观测关联不足以定向"),
    "CausalDiscovery/SurvivorshipConfoundedDesign": (
        "每一行数据都已被结果相关的筛选选中,在幸存者表里估计真实处理效应",
        "处理效应恢复;混杂开启的伪关联须识别,无 T→Y 边时不得宣称效应"),
    "ChemicalKinetics/ReactionMechanismFitting": (
        "自选温度、初始混合与采样时刻,从公开一阶反应库里认出稀疏反应网络与其温度依赖",
        "机制恢复 + 外推;库外世界须拒答"),
    "ChemicalProcess/DistillationColumnDesign": (
        "混合整数精馏塔设计:塔板数与进料位置离散,兼顾纯度回收约束与再沸冷凝能耗",
        "年化成本;留出迁移与密封变工况分列,无上限"),
    "Chemistry/LennardJonesCluster": (
        "求 Lennard-Jones 原子簇的最低能量几何构型",
        "对全局最小的平均缺口闭合;无上限"),
    "ClimateScience/EnergyBalanceModel": (
        "自选辐射强迫实验,辨识两层气候响应的五个参数;需状态依赖反馈或第三层时拒答",
        "参数恢复 + 强迫迁移 + 模型不足拒答;实验预算受限"),
    "ClimateScience/ForcedSignalAttribution": (
        "在控制年预算下判断区域记录里是否含强迫响应、估其幅度与区间;模型指纹或变率不可信时拒答",
        "检测率、幅度分、区间覆盖分列;红噪声假趋势与安静模型均记误发现"),
    "ControlTheory/InvertedPendulumSwingUp": (
        "设计小车倒立摆的摆起与稳定控制律,兼顾轨道限位与作动器约束",
        "摆起效用;偏移工况稳健性分列"),
    "DynamicalSystems/ActiveLawDiscovery": (
        "自选初值与外部驱动,从候选项库里恢复二维受控系统的稀疏控制方程",
        "稀疏律恢复 + 密封轨迹外推;库不足时拒答"),
    "Electrochemistry/ElectrolyteConductivityDesign": (
        "在高通量电解液数据回放里分配阻抗测定预算,选出稳健的配方批次",
        "温度剖面电导率 + 批次多样性 + 重复稳健性 + 留出迁移;无上限"),
    "EvidenceSynthesis/ProspectiveMetaAnalysis": (
        "在注册表加文献语料里筛研究、识别同一人群血缘的重复报告与换端点,做异质性荟萃回归",
        "筛选、证据血缘完整性、荟萃回归、校准拒答、下一步研究信息量与前瞻确认分列"),
    "Exoplanets/RadialVelocityPlanets": (
        "从视向速度序列里指认哪些周期是行星:自转、谐波与采样别名不是行星",
        "行星恢复;误发现率与别名拒答分开报告"),
    "Physics/CriticalPhenomenaLab": (
        "主动选择有限尺寸实验,区分连续/一级相变与 crossover 或 BKT-like 世界",
        "机制与有限尺寸外推;误发现、拒答与覆盖率分开报告"),
    "Geophysics/GravityInversion": (
        "主动布设重力测线,反演地下密度体的位置与强度;声明的源族不支持时拒答",
        "源恢复 + 外场校验 + 拒答;许多密度分布产生相似地表场"),
    "Gravitation/PTAHellingsDowns": (
        "脉冲星计时阵里区分 Hellings-Downs 四极相关(引力波背景)与钟差单极、星历偶极、共同红噪声",
        "四极 vs 单极判别与拒答;共同过程不等于引力波背景"),
    "HeatTransfer/ConvectionDiffusionOpt": (
        "在预算内辨识各向异性对流扩散参数,并设计使温度场达标的加热器布局",
        "机制恢复 + 目标场设计 + 物理偏移稳健性 + 模型不足拒答"),
    "MaterialsScience/AlloyHardnessOptimization": (
        "在按论文 DOI 分组的多主元合金数据里做实验设计,选出研究外留出的硬度批次",
        "留出硬度 + 多样性 + 代理失效 + 不确定性 + 来源迁移 + 稀疏独立确认;无上限"),
    "MaterialsScience/PhaseDiagramDiscovery": (
        "在合成预算下测定二元等温相图:哪些平衡相存在、各占哪段成分,或该体系根本达不到平衡",
        "相集精确门控 + 杠杆定律边界精度;两相区叠加、杂质峰、动力学冻结须区分,冻结体系须拒答"),
    "MaterialsScience/QuinaryConvexHull": (
        "五元体系里给出凸包上真正稳定的非一元相;生成焓小于零不等于新稳定相",
        "精确非一元凸包顶点;玻璃态须拒答"),
    "Mathematics/BlackBoxGroupIdentification": (
        "只给黑盒乘法与随机标号,在查询预算内从公开构造目录里辨识群的同构类",
        "目录 id 精确门控;非群与目录外两种拒答理由分开计分,阶数分布不足以辨识"),
    "Mathematics/CapSet": (
        "在 Z_3^n 里构造更大的 cap set(无三点共线)",
        "对最好已知规模的平均进度;无上限"),
    "Mathematics/CapSetFrontier": (
        "在最大值尚未证明的 n=7,8,9 上构造更大的 cap set",
        "对最好已知规模的平均进度;无上限,与 CapSet 的维度不相交"),
    "Mathematics/ErdosMinimumOverlap": (
        "把 {1,...,2n} 分成两个等大小的集合,让某个差值出现的最多次数尽量小——Erdős 最小重叠问题,渐近常数在 2025-2026 年被 AlphaEvolve 等多次刷新",
        "对三个 n(8、11、15)已被穷举搜索证明的精确最优值的平均进度;这三个规模都是硬上限,已披露,因为超过 n=15 没有可核实的具体最好记录"),
    "Mathematics/HeilbronnTrianglePacking": (
        "在单位正方形内放 n 个点,让任意 3 点构成的三角形最小面积尽量大——经典的 Heilbronn 三角形问题",
        "对 Erich's Packing Center 维护的记录表的平均进度;n=8 已证明最优(硬上限,已披露),n=10、n=11、n=12 仅是最好已知记录,真实无上限"),
    "Mathematics/HeavyTailEvidence": (
        "在已知 xmin 下判断样本是幂律还是对数正态;指数截断或样本过短须拒答",
        "家族恢复 + 截断/小样本拒答;不是质量窗口的 look-elsewhere,也不是不相容常数调和"),
    "Mathematics/KissingNumber": (
        "在 9、10、12 维构造更多与中心球相切的单位球",
        "固定容差下对最好已知接触数的平均进度;无上限"),
    "Mathematics/NarrowAdmissibleTuple": (
        "构造比 Polymath8b 已发表直径更小的可容许 k-元组(k=50、54)——有界素数间隔猜想计算核心的同一对象",
        "已发表直径的归一化进度(k=50 锚点 246 一手引用确认,k=54 锚点 270 仅二手来源);无上限"),
    "Mathematics/RamseyLowerBound": (
        "构造更大的 (s,t)-Ramsey 染色以提高下界",
        "对最好已知染色阶数的平均进度;无上限"),
    "Mathematics/ZarankiewiczMatrix": (
        "在三组给定的 (m,n) 规模上构造不含 3x3 全一子矩阵的更密 0/1 矩阵——2026 年 LLM 进化搜索(OpenEvolve,本仓库自带的搜索后端之一)刚刷新过的极值图论问题",
        "对最新发表下界(z(m,n;3,3) 的已发表值)的平均进度;无上限,且这些是尚未被上界证明封顶的下界纪录"),
    "Mathematics/DegreeDiameterGraph": (
        "在三组给定的 (最大度 d, 直径 k) 上构造尽可能大的图——2026 年有论文报道通过与可浏览器访问的 LLM 交互刷新过下界",
        "对度-直径问题维护表中最好已知顶点数的平均进度;无上限,均未被证明最优"),
    "Mathematics/VanDerWaerdenColoring": (
        "为给定的颜色数与等差数列长度构造尽可能长的、不含单色等差数列的染色",
        "两组对照证明最优的 van der Waerden 数(硬上限,已披露)、一组对照尚未证明最优的最好已知下界(真实无上限空间)"),
    "Mathematics/SchurPartition": (
        "为给定的分组数 k 构造尽可能长的无和分拆(每组内不含 a+b=c,允许 a=b)",
        "k=4 对照证明最优的 Schur 数(硬上限,已披露);k=6、k=7 对照尚未证明最优的最好已知下界(真实无上限空间)"),
    "Mathematics/SequenceLawRecovery": (
        "给出整数序列前若干项,说出产生它的线性递推;项数不足以定唯一最小规则时拒答",
        "延续准确率;误发现率与不定性拒答分开报告"),
    "AtmosphericChemistry/MethaneSourceAttribution": (
        "在固定观测预算下,判断二十年里哪些甲烷排放部门发生了变化——以及在记录判不了时说出判不了。"
        "2007 年后大气甲烷重新增长、δ¹³C 变轻,驱动因素至今没有定论:同位素证据被读成主要是微生物源,"
        "而这个读法又被以源signature空间变异和汇的未解问题反驳。四类世界只有两类可答:化石与生物质燃烧"
        "会让 δ¹³C 上升、乙烷能分开;单一微生物源变化足够大时部门清单能认出;而纯汇变化和两个微生物源"
        "同时小幅变化都判不了。",
        "三轴分开报、永不平均:机制恢复率、假发现率(带分母)、校准拒答率,外加是否尝试过的计数。"
        "总分是三者之积,全弃权与从不弃权都恰好得零。关键在于纯汇变化能被纯源变化复现到观测噪声以内"
        "(约化失配 0.00),而它看起来最像废弃物在小幅增加——baseline 在八个纯汇案例里点名废弃物五次。"
        "出路是买废弃物清单,发现它没变,把自上而下与自下而上的矛盾当作弃权的理由。"),
    "Turbulence/WallClosureDiscovery": (
        "在有限的剖面测量预算下,把湍流壁面闭合律作为公式找出来——以及在观测撑不起任何律时说出撑不起。"
        "数据驱动湍流闭合是整个领域在做的问题,它公认的批评不是拟合得不好,而是只在训练它的地方被验证过。"
        "三类世界只有一类可解:雷诺数跨度够宽时参数被钉住;跨度太窄时一整段 kappa 都拟合得同样好而在留出"
        "工况上互相矛盾;还有一类根本没有单一闭合能同时解释各条剖面。",
        "三轴分开报、永不平均:机制恢复率(在从未观测的留出雷诺数上检验公式)、假发现率(带分母)、"
        "校准拒答率,外加是否尝试过的计数。总分是三者之积,全弃权与从不弃权都恰好得零。两个拒答理由是"
        "正交的:不一致那类残差大,而不可辨识那类残差反而最小、拟合看起来最漂亮,要靠答案的宽度而不是"
        "残差来识别。把教科书的 van Driest 闭合直接交上去得零分、假发现率 1.00。"),
    "Exoplanets/TransmissionSpectrumSpecies": (
        "在固定的凌星次数预算下,判断系外行星大气里有哪些分子——以及在观测无法判定时说出无法判定。"
        "K2-18b 的 DMS 之争正是这个问题:多次重分析的结论是那些特征并非唯一可辨识。四类世界里有三类"
        "不可辨识,而且原因各不相同:灰云层一次压平所有特征;混淆对在任何预算分配下都分不开(单振幅"
        "误差是其和的 24.5 倍);暗弱系统把整个预算压在最好波段也到不了 1σ。只有第三类是噪声。",
        "三轴分开报、永不平均:机制恢复率、假发现率(带分母)、校准拒答率,外加是否尝试过的计数。"
        "总分是三者之积,归一化到全弃权恰好得零——从不弃权因拒答率为零也得零,两种退化策略都是零,"
        "靠尝试率把它们区分开。点名混淆对里任何一方都算假发现,即使其中一个确实存在:世界不决定是哪一个。"),
    "DiscreteGeometry/SpherePackingCertificate": (
        "为球堆积密度给出一份可精确验证的上界证明。Cohn-Elkies 定理把上界化为分析问题:找一个函数,"
        "它在半径外非正、其傅里叶变换处处非负。除 1/2/3/8/24 维外全部开放——12 维已知最好堆积 0.03704,"
        "最好的证明只到 0.06279。取变量 w=2π‖x‖²,拉盖尔特征基的系数是有理的,两条假设都变成有理半轴上的"
        "有理多项式,而单变量多项式在半轴非负当且仅当能写成 σ₀+wσ₁,这个刻画是完备的。",
        "四个维度(8/12/16/20)取均值,不设上限。零点是闭式的二项证书——这个方法不花力气就能给出的东西;"
        "1.0 是已发表的 Cohn-Elkies 数值界,而与之等强的精确有理证书似乎在任何维度都还没有人发表过。"
        "有理数精确验证,提交浮点判零:网格线性规划这个教科书方法会给出假界(16 阶时 8 维报 0.06237,"
        "低于 E8 格实际达到的 0.0625)。"),
    "InformationTheory/ShannonCapacityCertificate": (
        "为奇圈的香农容量给出一段可精确验证的区间:下界交一个强积幂里的零错码(任意两码字不得在每个坐标上都相等或相邻),上界交一份有理 Lovasz 矩阵与有理界,使 b*I - A 正定。"
        "C7 的容量自 1956 年 Shannon 提出、1979 年 Lovasz 解决 C5 之后一直未知,下端在 2026 年 7 月一个月内被改进了三次,上端 theta 自 1979 年未动过。",
        "四个奇圈(C7/C13/C19/C23)取均值,不设上限。零点不是引用而是随包发布的显式码集,oracle 用同一套独立性检验接受它;1.0 是 2026-09-06 时的已发表最好下界,四个都不是在本题允许的幂上达到的。有理数精确验证,提交浮点判零——数值特征值不是证明。"),
    "QuantumFoundations/BellBoundCertificate": (
        "为贝尔泛函的量子最大值给出一份可精确验证的上界证明:提交一组基词与若干加权平方,"
        "使它们的和恰好等于 beta*I - B。CHSH 的答案是无理数 2√2,只能逼近;I3322 的量子值至今未知,"
        "NPA 层级 1 给 0.375、层级 2 给 0.25102173、已知最好值 0.25087538 要到层级 4 以上。",
        "四个实例(CHSH 与三种基词预算下的 I3322)取均值,不设上限。分数是所证界到已知量子值距离的"
        "对数进步:免费的层级 1 界记 0,已发表的层级 2 界记 1,超过则大于 1。有理数精确验证,"
        "提交浮点数直接判零——数值 SDP 解不是证明。"),
    "Mathematics/NonlinearCodeRecords": (
        "在四个 A(n,d) 未闭合的参数上构造尽可能大的二元码;已发表纪录全部由非线性码持有,线性构造够不到",
        "从平凡分块重复构造到已发表纪录的平均进度,无上限;验证只是逐对汉明距离计数,与构造方法无关"),
    "Mathematics/Superpermutation": (
        "构造更短的超排列字符串,使其包含全部排列作为连续子串",
        "对最短已知长度的平均进度;无上限"),
    "MedicinalChemistry/MolecularLeadOptimization": (
        "构建结构多样、可开发的新颖先导化合物组合,而非单个分子",
        "多样性约束下的组合价值,对标已上市药物;无上限"),
    "MolecularDynamics/ForceFieldCalibration": (
        "主动查询构型的能量与力,在 Mie 12-6 与 Morse 之间判别对势律,并给参数区间",
        "竞争假设保留、判别、区间恢复、密封预测与模型拒答分列;库外世界须拒答"),
    "NuclearEngineering/NeutronDiffusionCriticality": (
        "在平均富集度约束下优化堆芯燃料富集分布以最大化 k_eff",
        "相对均匀装载的 k_eff 提升;无上限"),
    "Oceanography/AMOCTippingRefusal": (
        "AMOC 指纹序列里区分尚未发生的立方折叠、纯红噪声与冰约束唯一吸引子",
        "折叠恢复 + 红噪声与冰约束拒答;指纹下降不等于将要崩溃"),
    "Optics/DiffractionGratingDesign": (
        "设计五层一维二元介质浮雕,把透射光导入 +1 衍射级,且对偏振与角度容差",
        "开发集目标级效率;偏振/角度/波长与工艺偏移稳健性分列,无上限"),
    "Optimization/CirclePacking": (
        "把 N 个单位圆装进边长最小的正方形",
        "对最好已知装填的平均缺口闭合;无上限"),
    "ParticlePhysics/CalorimeterDesign": (
        "设计分层取样量能器,使能量分辨、线性与簇射包容在多档成本约束下同时改善",
        "多能点效用;留出探测器迁移与最差制造偏移分列,无上限"),
    "ParticlePhysics/DiscrepantMeasurements": (
        "八组测量同一常数但彼此不相容,诊断这批证据出了什么问题并给最佳值或判定没有最佳值",
        "缺陷诊断 + 收费的内部一致性检验 + 拒答"),
    "ParticlePhysics/LookElsewhereAnomaly": (
        "一张质量谱在多个窗口里扫描,判定局域 5σ 在计入试验因子后还剩多少",
        "look-elsewhere 后的全局显著性;边带拒绝公开本底时须拒答"),
    "Photonics/MultilayerThinFilm": (
        "设计可见光全谱段的多层宽带减反射膜",
        "宽带减反射质量;物理下界为零平均反射"),
    "Physics/ComplexBoseLaw": (
        "在模式混合下恢复玻色占据律的移位指数;费米型世界须拒答",
        "指数恢复 + 费米拒答;不是教科书普朗克曲线的直接拟合"),
    "Physics/HiddenCouplingNetwork": (
        "实验次数少于单元数,从多单元驱动的稳态里恢复带符号的直接耦合图;存在未观测单元时拒答",
        "带符号边 F1;间接路径、tanh 非线性与隐藏单元造成的稠密低秩耦合分别记误发现"),
    "PopulationGenetics/DemographicSFS": (
        "在测序预算内跨样本量分配测序,从位点频率谱恢复常量或三期人口史",
        "参数恢复 + 留出样本量预测 + 模型不足拒答 + 预算设计"),
    "ProteinEngineering/ProteinStabilityDesign": (
        "在蛋白稳定性实验回放里分配测定预算,设计双点突变批次",
        "留出稳定性前十分位 + 多样性 + 蛋白酶稳健性 + 结构域迁移;无上限"),
    "QuantumDynamics/HamiltonianLearning": (
        "从自旋链的少数可观测量时间演化里恢复哈密顿量参数",
        "参数恢复;误发现率与对称性不可辨识拒答分开报告"),
    "QuantumControl/ActiveNoiseSpectroscopy": (
        "在有限量子测量 shots 下选择 Ramsey、echo 与 CPMG 滤波序列,区分共享同一 Lorentzian 功率谱的高斯噪声与单随机电报源,恢复其切换率、方差和占据率",
        "三参数机制恢复减不受支持宣称;密封控制外推、误发现率、拒答、尝试覆盖率与 shot 成本分列"),
    "QuantumErrorCorrection/QuantumErrorDecoder": (
        "为旋转表面码存储设计阈值以下的解码器",
        "相对最小权完美匹配的逻辑错误率对数下降;无上限"),
    "RNAEngineering/RNAEnsembleDesign": (
        "设计 RNA 序列,使目标二级结构在整个玻尔兹曼系综上而非仅 MFE 上成立",
        "对 ViennaRNA 反折叠的系综缺陷;密封目标,无上限"),
    "RNAEngineering/RNAInverseDesign": (
        "在长度、字母表、GC 与基序约束下设计目标系综概率高的 RNA 序列",
        "目标系综概率 + MFE 迁移 + 代理误升迁;配对相容只是代理,无上限"),
    "Semiconductor/MOSFETDoping": (
        "设计可迁移的短沟道硅 nMOS 晕环掺杂剖面帕累托档案",
        "驱动电流对漏电的帕累托超体积;密封留出迁移与最差偏移稳健性分列,无上限"),
    "Sensors/QuartzCrystalMicrobalanceLab": (
        "从石英微天平的原始 I/Q 扫频里标定复增益漂移、提取谐振并反演薄膜质量与沉积速率",
        "原始 IQ 标定、BVD 谐振提取、质量与速率恢复、故障与模型判别、密封停止决策分列"),
    "SignalProcessing/SparseRecovery": (
        "从远少于奈奎斯特的测量里恢复 k 稀疏信号",
        "平均恢复信噪比"),
    "StructuralEngineering/ModalDamageAttribution": (
        "在受预算约束的测量日里判断模态频率的偏移是不是某个内部元件的刚度损伤、是哪一个、损失多少;支座变化导致的偏移须拒答",
        "定位精确门控 + 严重度容差评分;温度对频率比精确抵消,健康结构误报与支座变化误判分别记误发现,分数标尺锚在全弃权为零"),
    "Spectroscopy/CrowdedSpectrumAssignment": (
        "在混叠谱里指认封闭库中的物种;两个近线的混合与第三个物种不可区分,变焦要花预算",
        "库物种指认 + 别名拒答"),
    "Spectroscopy/NMRSpectrumFitting": (
        "从一维核磁谱里恢复未知个数的重叠共振、区分线型与基线漂移;线型族不支持时拒答",
        "峰机制恢复 + 移位重建 + 模型不足拒答;残差低会奖励虚假峰"),
    "Spectroscopy/SpinSystemInference": (
        "从高分辨质子谱恢复自旋体系的化学位移与两两耦合;二级体系下一级读谱失效",
        "机制恢复;误发现率与校准拒答分开报告"),
    "StructuralEngineering/TrussWeightMinimization": (
        "给出跨结构通用的桁架截面尺寸策略,在应力、位移与欧拉屈曲约束下减重",
        "标称减重;密封拓扑迁移与载荷/材料/制造稳健性分列,无上限"),
    "Superconductivity/SuperconductorTcRecord": (
        "在真实设备压力上限下,用 Allen-Dynes 公式在五个真实超导体系间搜索已确认临界温度最高的"
        "(体系,压力)组合,并避开一个从未被实现的理论预测(隐含电子-声子耦合超过物理合理上限)",
        "真实Tc除以已发表记录250K的直接比值;无上限,可超过已发表记录"),
    "SystemsBiology/EnzymeKineticsLaw": (
        "在测定预算内自选底物与抑制剂浓度,判定这个酶服从六条已发表速率律中的哪条,或都不服从",
        "速率律辨识 + 拒答 + 密封外推预测"),
    "SystemsBiology/GeneNetworkIntervention": (
        "用扰动实验恢复带符号的动态调控网络,并设计达成表型的干预",
        "网络恢复 + 预测 + 表型干预迁移 + 拒答"),
    "Thermodynamics/HeatExchangerDesign": (
        "发现换热器的多保真帕累托设计档案,权衡换热量、成本与泵功",
        "成本对换热量的帕累托超体积;密封代理一致性、留出迁移与结垢/制造/堵塞稳健性分列,无上限"),
    "Turbulence/RANSCalibration": (
        "标定可迁移的代数通道流涡黏封闭,同时匹配平均速度与雷诺剪应力",
        "真实 DNS 拟合;密封高雷诺数迁移与壁面坐标稳健性分列,无上限"),
}


FORM_TITLES = OrderedDict([("optimization", "Optimization"), ("discovery", "Discovery")])
ANALOGUE_TITLES = OrderedDict([
    ("engineering_design", "工程设计(engineering_design)"),
    ("combinatorial", "开放组合纪录(combinatorial,无上限)"),
    ("molecular_design", "分子与大分子设计(molecular_design)"),
])
KIND_TITLES = OrderedDict([
    ("formula", "公式(formula)"),
    ("structure", "结构(structure)"),
    ("evidence", "证据(evidence)"),
    ("substance", "物质(substance)"),
    ("parameter_inversion", "参数反演(parameter_inversion)"),
])


def _one_line(task_md: str) -> str:
    """The part of the first heading after the task name; failing that, the opening sentence."""
    lines = task_md.splitlines()
    for line in lines:
        if line.startswith("# "):
            title = line[2:].strip()
            for sep in (" — ", " – ", " - ", ": "):
                if sep in title:
                    return title.split(sep, 1)[1].strip()
            break
    for line in lines:
        text = line.strip()
        if not text or text.startswith(("#", "|", "-", "*", "`", ">", "```")):
            continue
        sentence = re.split(r"(?<=[.。!?])\s", text, maxsplit=1)[0].strip()
        return sentence if len(sentence) <= 140 else sentence[:137].rstrip() + "..."
    return ""


def build_rows() -> list[dict]:
    taxonomy = (yaml.safe_load(TAXONOMY.read_text()) or {}).get("tasks") or {}
    certification = (yaml.safe_load(CERTIFICATION.read_text()) or {}).get("tasks") or {}
    rows = []
    for spec in list_tasks(None):
        cell = taxonomy.get(spec.task_id) or {}
        cert = certification.get(spec.task_id) or {}
        task_md = spec.task_md if isinstance(spec.task_md, str) else (spec.task_dir / "Task.md").read_text()
        rows.append({
            "task_id": spec.task_id,
            "name": spec.task_id.split("/")[-1],
            "discipline": spec.discipline,
            "domain": spec.domain,
            "path": spec.task_dir.relative_to(ROOT).as_posix(),
            "form": cell.get("form", "unmapped"),
            "cell": cell.get("analogue") or cell.get("kind") or "unmapped",
            "note": cell.get("note") or "",
            "score_mode": str(spec.metadata.get("score_mode", "")),
            "oracle_type": str(spec.metadata.get("oracle_type", "")),
            "status": cert.get("status", "unregistered"),
            "summary": _one_line(task_md),
        })
    return sorted(rows, key=lambda r: (r["form"], r["cell"], r["discipline"], r["name"]))


def _table(rows: list[dict]) -> list[str]:
    out = ["| 任务 | 学科 | 领域 | 打分 | oracle | 认证 | 说明 | 中文题意 | 中文评估方法 |",
           "|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        note = " · on-ramp,不配对" if "on_ramp" in r["note"] else ""
        summary = (r["summary"] or "").replace("|", "\\|")
        meaning, scoring = CHINESE_BRIEFS.get(r["task_id"], ("", ""))
        chinese_name = CHINESE_NAMES.get(r["task_id"], "")
        out.append("| [`%s`](%s/)<br>%s | %s | %s | %s | %s | %s | %s%s | %s | %s |" % (
            r["name"], r["path"], chinese_name, r["discipline"], r["domain"], r["score_mode"],
            r["oracle_type"], r["status"], summary, note, meaning, scoring))
    return out


def render(rows: list[dict]) -> str:
    forms = Counter(r["form"] for r in rows)
    statuses = Counter(r["status"] for r in rows)
    disciplines = Counter(r["discipline"] for r in rows)
    lines = [
        "# 任务汇总",
        "",
        "由 `python scripts/report_task_inventory.py` 从注册表生成,`tests/test_task_inventory_document.py` 保证它不过期;"
        "不要手改。权威实时清单是 `python -m sle list --all`。",
        "",
        "| | |",
        "|---|---:|",
        "| 任务包 | %d |" % len(rows),
    ]
    for form in FORM_TITLES:
        lines.append("| %s | %d |" % (form, forms.get(form, 0)))
    for status in ("certified", "candidate", "quarantined"):
        if statuses.get(status):
            lines.append("| %s | %d |" % (status, statuses[status]))
    lines.append("| 学科 | %d(%s) |" % (
        len(disciplines), ",".join("%s %d" % (k, v) for k, v in sorted(disciplines.items()))))
    lines.append("")
    lines.append("认证描述的是证据质量,不是难度。标 on-ramp 的任务首个前沿模型提案已够到参考解,不用于配对 Δ 测量。")
    lines.append("")
    for form, title in FORM_TITLES.items():
        subset = [r for r in rows if r["form"] == form]
        lines.append("## %s(%d)" % (title, len(subset)))
        lines.append("")
        titles = ANALOGUE_TITLES if form == "optimization" else KIND_TITLES
        cells = list(titles) + sorted({r["cell"] for r in subset} - set(titles))
        for cell in cells:
            group = [r for r in subset if r["cell"] == cell]
            if not group:
                continue
            lines.append("### %s — %d" % (titles.get(cell, cell), len(group)))
            lines.append("")
            lines.extend(_table(group))
            lines.append("")
    stray = [r for r in rows if r["form"] not in FORM_TITLES]
    if stray:
        lines.append("## 未映射到 exam_taxonomy.yaml 的任务(%d)" % len(stray))
        lines.append("")
        lines.extend(_table(stray))
        lines.append("")
    return "\n".join(lines).rstrip("\n") + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="exit 1 if TASKS.md differs from the registry")
    ap.add_argument("--output", type=Path, default=OUTPUT)
    args = ap.parse_args(argv)
    content = render(build_rows())
    if args.check:
        current = args.output.read_text() if args.output.exists() else ""
        if current != content:
            print("%s is stale; run: python scripts/report_task_inventory.py" % args.output.relative_to(ROOT))
            return 1
        print("%s is current" % args.output.relative_to(ROOT))
        return 0
    args.output.write_text(content)
    print("wrote %s (%d tasks)" % (args.output.relative_to(ROOT), content.count("| [`")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

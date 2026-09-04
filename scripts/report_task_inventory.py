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
    "Geophysics/GravityInversion": "重力反演",
    "Gravitation/PTAHellingsDowns": "脉冲星阵四极相关",
    "HeatTransfer/ConvectionDiffusionOpt": "对流扩散辨识与加热器设计",
    "MaterialsScience/AlloyHardnessOptimization": "合金硬度实验设计",
    "MaterialsScience/PhaseDiagramDiscovery": "相图发现",
    "MaterialsScience/QuinaryConvexHull": "五元凸包稳定相",
    "Mathematics/BlackBoxGroupIdentification": "黑盒群同构辨识",
    "Mathematics/CapSet": "Cap Set 构造",
    "Mathematics/CapSetFrontier": "Cap Set 未证明维度",
    "Mathematics/KissingNumber": "接触数构造",
    "Mathematics/RamseyLowerBound": "Ramsey 下界染色",
    "Mathematics/SequenceLawRecovery": "整数序列递推恢复",
    "Mathematics/Superpermutation": "超排列最短串",
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
    "Mathematics/KissingNumber": (
        "在 9、10、12 维构造更多与中心球相切的单位球",
        "固定容差下对最好已知接触数的平均进度;无上限"),
    "Mathematics/RamseyLowerBound": (
        "构造更大的 (s,t)-Ramsey 染色以提高下界",
        "对最好已知染色阶数的平均进度;无上限"),
    "Mathematics/SequenceLawRecovery": (
        "给出整数序列前若干项,说出产生它的线性递推;项数不足以定唯一最小规则时拒答",
        "延续准确率;误发现率与不定性拒答分开报告"),
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

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
    'Microbiology/MetagenomeCompositionAssignment': "宏基因组组成指认",
    "Algorithm/GraphFromDistances": "距离查询重建图",
    "AtmosphericScience/RadiativeTransferFit": "辐射传输反演",
    "Catalysis/CatalystDeactivationLab": "催化剂失活实验室",
    "CausalDiscovery/InterventionalSCM": "干预式结构因果模型",
    "CausalDiscovery/SurvivorshipConfoundedDesign": "幸存者偏差下的效应估计",
    "DataPrivacy/SparseVectorAudit": "稀疏向量技术的差分隐私审计",
    "ChemicalKinetics/ReactionMechanismFitting": "反应机理辨识",
    "ClimateScience/EnergyBalanceModel": "能量平衡模型辨识",
    "ClimateScience/ForcedSignalAttribution": "强迫信号检测归因",
    "ComputerArchitecture/CacheReplacementPolicyID": "缓存替换策略辨识",
    "DynamicalSystems/ActiveLawDiscovery": "主动定律发现",
    "Ecology/OccupancyDetectionDesign": "生态占域与探测设计",
    "EvidenceSynthesis/ProspectiveMetaAnalysis": "前瞻荟萃分析",
    "Exoplanets/RadialVelocityPlanets": "视向速度找行星",
    "Physics/CriticalPhenomenaLab": "有限尺寸临界现象发现",
    "Exoplanets/TransitTimingAttribution": "凌星时刻变化归因",
    "Geophysics/GravityInversion": "重力反演",
    "Geophysics/UPbConcordiaInference": "铀铅谐和图事件归因",
    "Gravitation/PTAHellingsDowns": "脉冲星阵四极相关",
    "HeatTransfer/ConvectionDiffusionOpt": "对流扩散辨识与加热器设计",
    "MaterialsScience/PhaseDiagramDiscovery": "相图发现",
    "MaterialsScience/QuinaryConvexHull": "五元凸包稳定相",
    "Mathematics/BlackBoxGroupIdentification": "黑盒群同构辨识",
    "Mathematics/HeavyTailEvidence": "重尾证据判别",
    "Mathematics/SequenceLawRecovery": "整数序列递推恢复",
    "AtmosphericChemistry/MethaneSourceAttribution": "甲烷源归因",
    "Turbulence/WallClosureDiscovery": "壁面湍流闭合律发现",
    "Exoplanets/TransmissionSpectrumSpecies": "透射光谱分子判定",
    "MolecularDynamics/ForceFieldCalibration": "力场假设判别",
    "Oceanography/AMOCTippingRefusal": "AMOC 折叠拒答",
    "ParticlePhysics/DiscrepantMeasurements": "不相容测量调和",
    "ParticlePhysics/LookElsewhereAnomaly": "多窗口扫描的全局显著性",
    "Physics/ComplexBoseLaw": "复玻色占据律",
    "Physics/HiddenCouplingNetwork": "隐藏耦合网络重建",
    "PopulationGenetics/DemographicSFS": "位点频率谱人口史反演",
    "QuantumDynamics/HamiltonianLearning": "哈密顿量学习",
    "QuantumControl/ActiveNoiseSpectroscopy": "主动非高斯噪声谱辨识",
    "Sensors/QuartzCrystalMicrobalanceLab": "石英微天平原始信号反演",
    "Sensors/IMUBiasCalibration": "惯性传感器偏置温漂校准",
    "Spectroscopy/CrowdedSpectrumAssignment": "混叠谱物种指认",
    "StructuralEngineering/ModalDamageAttribution": "模态损伤归因",
    "Spectroscopy/NMRSpectrumFitting": "核磁谱峰机制恢复",
    "Spectroscopy/SpinSystemInference": "自旋体系反演",
    "SystemsBiology/EnzymeKineticsLaw": "酶动力学律辨识",
    "SystemsBiology/GeneNetworkIntervention": "基因网络干预设计",
}

# One-line Chinese brief and scoring note per task. Written by hand: the English Task.md
# cannot be machine-translated into something a reader can trust, and the table is read by
# people deciding which task to look at. A task without an entry fails the inventory test,
# so a new package cannot silently ship without one.
CHINESE_BRIEFS = {
    'Microbiology/MetagenomeCompositionAssignment': (
        "从收费 marker 计数中恢复分类单元与丰度,保留近缘别名并识别参考库不足",
        "组成恢复、别名/库外拒答与假发现率分列"),
    "Algorithm/GraphFromDistances": (
        "在有限次距离查询下重建加权网络的边:短距离不等于相邻,可能是两条短边的两跳路径",
        "边恢复 F1;误发现率与不可辨识拒答分开报告"),
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
    "DataPrivacy/SparseVectorAudit": (
        "对一个声称满足 (ε, δ) 差分隐私的稀疏向量技术部署实现做黑盒审计:在运行次数预算内选择相邻查询向量与输出事件,给出违反见证或判定没有违反;实现可能偏离公开规范,且并非每处偏离都构成违反",
        "见证的精确隐私损失对照构造者锚点评分;损失不超过 ε 的见证记误发现并扣一个世界,分数标尺锚在全拒答为零"),
    "ChemicalKinetics/ReactionMechanismFitting": (
        "自选温度、初始混合与采样时刻,从公开一阶反应库里认出稀疏反应网络与其温度依赖",
        "机制恢复 + 外推;库外世界须拒答"),
    "ClimateScience/EnergyBalanceModel": (
        "自选辐射强迫实验,辨识两层气候响应的五个参数;需状态依赖反馈或第三层时拒答",
        "参数恢复 + 强迫迁移 + 模型不足拒答;实验预算受限"),
    "ClimateScience/ForcedSignalAttribution": (
        "在控制年预算下判断区域记录里是否含强迫响应、估其幅度与区间;模型指纹或变率不可信时拒答",
        "检测率、幅度分、区间覆盖分列;红噪声假趋势与安静模型均记误发现"),
    "ComputerArchitecture/CacheReplacementPolicyID": (
        "在带噪声的命中/缺失计时通道上对一个缓存组做受预算约束的访问实验,把隐藏的替换策略写成以路为输入的确定性状态机,或判定策略含随机性而拒答",
        "提交的状态机与真实策略做精确的可观测等价判定;错误状态机记误发现并扣一个世界,随机策略世界须拒答,分数标尺锚在全拒答为零"),
    "DynamicalSystems/ActiveLawDiscovery": (
        "自选初值与外部驱动,从候选项库里恢复二维受控系统的稀疏控制方程",
        "稀疏律恢复 + 密封轨迹外推;库不足时拒答"),
    "Ecology/OccupancyDetectionDesign": (
        "在漏检条件下分配站点复访与调查方法,恢复栖息地占域效应或拒绝不充分模型",
        "效应方向、效应量与平均占域率;误发现、拒答、覆盖率和留出迁移分列"),
    "EvidenceSynthesis/ProspectiveMetaAnalysis": (
        "在注册表加文献语料里筛研究、识别同一人群血缘的重复报告与换端点,做异质性荟萃回归",
        "筛选、证据血缘完整性、荟萃回归、校准拒答、下一步研究信息量与前瞻确认分列"),
    "Exoplanets/RadialVelocityPlanets": (
        "从视向速度序列里指认哪些周期是行星:自转、谐波与采样别名不是行星",
        "行星恢复;误发现率与别名拒答分开报告"),
    "Physics/CriticalPhenomenaLab": (
        "主动选择有限尺寸实验,区分连续/一级相变与 crossover 或 BKT-like 世界",
        "机制与有限尺寸外推;误发现、拒答与覆盖率分开报告"),
    "Exoplanets/TransitTimingAttribution": (
        "主动选择后续凌星时刻,区分模拟的周期、活动代理与时钟漂移族",
        "机制、周期预测与拒答;误发现率和留出迁移分开报告"),
    "Geophysics/GravityInversion": (
        "主动布设重力测线,反演地下密度体的位置与强度;声明的源族不支持时拒答",
        "源恢复 + 外场校验 + 拒答;许多密度分布产生相似地表场"),
    "Geophysics/UPbConcordiaInference": (
        "在分析预算内选择锆石域,由两套铀铅衰变比判断单一结晶或一次铅丢失历史;可分辨的多事件历史须拒答",
        "事件类型 + 结晶与铅丢失年龄 + 证据血缘;误发现、拒答、覆盖率和留出迁移分列"),
    "Gravitation/PTAHellingsDowns": (
        "脉冲星计时阵里区分 Hellings-Downs 四极相关(引力波背景)与钟差单极、星历偶极、共同红噪声",
        "四极 vs 单极判别与拒答;共同过程不等于引力波背景"),
    "HeatTransfer/ConvectionDiffusionOpt": (
        "在预算内辨识各向异性对流扩散参数,并设计使温度场达标的加热器布局",
        "机制恢复 + 目标场设计 + 物理偏移稳健性 + 模型不足拒答"),
    "MaterialsScience/PhaseDiagramDiscovery": (
        "在合成预算下测定二元等温相图:哪些平衡相存在、各占哪段成分,或该体系根本达不到平衡",
        "相集精确门控 + 杠杆定律边界精度;两相区叠加、杂质峰、动力学冻结须区分,冻结体系须拒答"),
    "MaterialsScience/QuinaryConvexHull": (
        "五元体系里给出凸包上真正稳定的非一元相;生成焓小于零不等于新稳定相",
        "精确非一元凸包顶点;玻璃态须拒答"),
    "Mathematics/BlackBoxGroupIdentification": (
        "只给黑盒乘法与随机标号,在查询预算内从公开构造目录里辨识群的同构类",
        "目录 id 精确门控;非群与目录外两种拒答理由分开计分,阶数分布不足以辨识"),
    "Mathematics/HeavyTailEvidence": (
        "在已知 xmin 下判断样本是幂律还是对数正态;指数截断或样本过短须拒答",
        "家族恢复 + 截断/小样本拒答;不是质量窗口的 look-elsewhere,也不是不相容常数调和"),
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
    "MolecularDynamics/ForceFieldCalibration": (
        "主动查询构型的能量与力,在 Mie 12-6 与 Morse 之间判别对势律,并给参数区间",
        "竞争假设保留、判别、区间恢复、密封预测与模型拒答分列;库外世界须拒答"),
    "Oceanography/AMOCTippingRefusal": (
        "AMOC 指纹序列里区分尚未发生的立方折叠、纯红噪声与冰约束唯一吸引子",
        "折叠恢复 + 红噪声与冰约束拒答;指纹下降不等于将要崩溃"),
    "ParticlePhysics/DiscrepantMeasurements": (
        "八组测量同一常数但彼此不相容,诊断这批证据出了什么问题并给最佳值或判定没有最佳值",
        "缺陷诊断 + 收费的内部一致性检验 + 拒答"),
    "ParticlePhysics/LookElsewhereAnomaly": (
        "一张质量谱在多个窗口里扫描,判定局域 5σ 在计入试验因子后还剩多少",
        "look-elsewhere 后的全局显著性;边带拒绝公开本底时须拒答"),
    "Physics/ComplexBoseLaw": (
        "在模式混合下恢复玻色占据律的移位指数;费米型世界须拒答",
        "指数恢复 + 费米拒答;不是教科书普朗克曲线的直接拟合"),
    "Physics/HiddenCouplingNetwork": (
        "实验次数少于单元数,从多单元驱动的稳态里恢复带符号的直接耦合图;存在未观测单元时拒答",
        "带符号边 F1;间接路径、tanh 非线性与隐藏单元造成的稠密低秩耦合分别记误发现"),
    "PopulationGenetics/DemographicSFS": (
        "在测序预算内跨样本量分配测序,从位点频率谱恢复常量或三期人口史",
        "参数恢复 + 留出样本量预测 + 模型不足拒答 + 预算设计"),
    "QuantumDynamics/HamiltonianLearning": (
        "从自旋链的少数可观测量时间演化里恢复哈密顿量参数",
        "参数恢复;误发现率与对称性不可辨识拒答分开报告"),
    "QuantumControl/ActiveNoiseSpectroscopy": (
        "在有限量子测量 shots 下选择 Ramsey、echo 与 CPMG 滤波序列,区分共享同一 Lorentzian 功率谱的高斯噪声与单随机电报源,恢复其切换率、方差和占据率",
        "三参数机制恢复减不受支持宣称;密封控制外推、误发现率、拒答、尝试覆盖率与 shot 成本分列"),
    "Sensors/QuartzCrystalMicrobalanceLab": (
        "从石英微天平的原始 I/Q 扫频里标定复增益漂移、提取谐振并反演薄膜质量与沉积速率",
        "原始 IQ 标定、BVD 谐振提取、质量与速率恢复、故障与模型判别、密封停止决策分列"),
    "Sensors/IMUBiasCalibration": (
        "在观测预算内选择姿态与温度,恢复偏置、温漂和尺度非正交矩阵,并定位非仿射故障轴",
        "十二参数校准与迁移预测、故障类型及轴定位、误发现、拒答与覆盖率分列"),
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
    "SystemsBiology/EnzymeKineticsLaw": (
        "在测定预算内自选底物与抑制剂浓度,判定这个酶服从六条已发表速率律中的哪条,或都不服从",
        "速率律辨识 + 拒答 + 密封外推预测"),
    "SystemsBiology/GeneNetworkIntervention": (
        "用扰动实验恢复带符号的动态调控网络,并设计达成表型的干预",
        "网络恢复 + 预测 + 表型干预迁移 + 拒答"),
}


FORM_TITLES = OrderedDict([("discovery", "Discovery")])
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


README_START = "<!-- task-inventory:start -->"
README_END = "<!-- task-inventory:end -->"


CHINESE_COUNT_WORDS = {
    1: "一", 2: "二", 3: "三", 4: "四", 5: "五",
    6: "六", 7: "七", 8: "八", 9: "九",
}


def render_readme_counts(rows: list[dict]) -> str:
    statuses = Counter(r["status"] for r in rows)
    kinds = Counter(r["cell"] for r in rows)
    if any(row["form"] != "discovery" for row in rows):
        raise ValueError("main accepts discovery tasks; optimization belongs on its branch")
    return "\n".join([
        README_START, "",
        "当前 %d 个任务包,横跨 %d 个学科,%d 个 certified、%d 个 candidate、%d 个 quarantined。" % (
            len(rows), len({r["discipline"] for r in rows}), statuses["certified"],
            statuses["candidate"], statuses["quarantined"]),
        "注册表中的这些任务使用历史 oracle 契约;无 GT 多轮实验环境另列,不混入认证数量。", "",
        "discovery(%d 个):从受预算约束的证据中建立可检验主张,或在证据不足、模型失配时保留结论。" % len(rows),
        "按主张对象分为:公式 %d、结构 %d、证据 %d、物质 %d、参数反演 %d。" % (
            kinds["formula"], kinds["structure"], kinds["evidence"], kinds["substance"], kinds["parameter_inversion"]),
        "这些是产物类型,不是从假设到发现必须依次经过的阶段。", "", README_END,
    ])


def update_readme_counts(text: str, rows: list[dict]) -> str:
    if text.count(README_START) != 1 or text.count(README_END) != 1:
        raise ValueError("README requires exactly one task-inventory marker pair")
    start, end = text.index(README_START), text.index(README_END) + len(README_END)
    if end <= start:
        raise ValueError("README task-inventory markers are out of order")
    return text[:start] + render_readme_counts(rows) + text[end:]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="check TASKS.md and README counts")
    ap.add_argument("--output", type=Path, default=OUTPUT)
    ap.add_argument("--readme", type=Path, default=ROOT / "README.md")
    args = ap.parse_args(argv)
    rows = build_rows()
    outputs = {args.output: render(rows),
               args.readme: update_readme_counts(args.readme.read_text(), rows)}
    stale = []
    for path, content in outputs.items():
        if args.check:
            if not path.is_file() or path.read_text() != content:
                stale.append(path)
                print("%s is stale; run: python scripts/report_task_inventory.py" % path)
        else:
            path.write_text(content)
            print("wrote %s" % path)
    return 1 if stale else 0


if __name__ == "__main__":
    raise SystemExit(main())

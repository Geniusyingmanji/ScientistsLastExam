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
CHINESE_NAMES = {'Acoustics/RoomImpulseResponse': '房间声学处理设计',
 'Algorithm/MatrixMultiplicationRank': '矩阵乘法秩',
 'Algorithm/TensorRank555': '5x5 与 6x6 张量秩',
 'Astrodynamics/LowThrustTransfer': '小推力轨道转移',
 'ChemicalProcess/DistillationColumnDesign': '精馏塔设计',
 'Chemistry/LennardJonesCluster': 'Lennard-Jones 团簇',
 'ControlTheory/InvertedPendulumSwingUp': '倒立摆摆起控制',
 'Electrochemistry/ElectrolyteConductivityDesign': '电解液电导率设计',
 'MaterialsScience/AlloyHardnessOptimization': '合金硬度实验设计',
 'Mathematics/CapSet': 'Cap Set 构造',
 'Mathematics/CapSetFrontier': 'Cap Set 未证明维度',
 'Mathematics/ErdosMinimumOverlap': 'Erdős 最小重叠划分',
 'Mathematics/HeilbronnTrianglePacking': 'Heilbronn 三角形点集',
 'Mathematics/KissingNumber': '接触数构造',
 'Mathematics/NarrowAdmissibleTuple': '窄可容许素数元组',
 'Mathematics/RamseyLowerBound': 'Ramsey 下界染色',
 'Mathematics/ZarankiewiczMatrix': 'Zarankiewicz 极值矩阵',
 'Mathematics/DegreeDiameterGraph': '度-直径极值图构造',
 'Mathematics/VanDerWaerdenColoring': 'van der Waerden 无进染色',
 'Mathematics/SchurPartition': 'Schur 无和分拆',
 'Mathematics/Superpermutation': '超排列最短串',
 'DiscreteGeometry/SpherePackingCertificate': '球堆积上界证书',
 'QuantumFoundations/BellBoundCertificate': '贝尔不等式上界证书',
 'QuantumFoundations/FourSettingMomentCertificate': '四设置矩子集证书',
 'InformationTheory/ShannonCapacityCertificate': '奇圈香农容量双侧证书',
 'Mathematics/NonlinearCodeRecords': '非线性码规模纪录',
 'MedicinalChemistry/MolecularLeadOptimization': '分子先导组合优化',
 'NuclearEngineering/NeutronDiffusionCriticality': '中子扩散临界优化',
 'Optics/DiffractionGratingDesign': '衍射光栅设计',
 'Optimization/CirclePacking': '圆堆积',
 'ParticlePhysics/CalorimeterDesign': '量能器设计',
 'Photonics/MultilayerThinFilm': '多层减反射膜',
 'ProteinEngineering/ProteinStabilityDesign': '蛋白稳定性批次设计',
 'QuantumErrorCorrection/QuantumErrorDecoder': '表面码解码器',
 'RNAEngineering/RNAEnsembleDesign': 'RNA 系综设计',
 'RNAEngineering/RNAInverseDesign': 'RNA 约束反折叠',
 'Semiconductor/MOSFETDoping': 'MOSFET 掺杂剖面',
 'SignalProcessing/SparseRecovery': '压缩感知稀疏恢复',
 'StructuralEngineering/TrussWeightMinimization': '桁架减重',
 'Superconductivity/SuperconductorTcRecord': '超导临界温度纪录搜索',
 'Thermodynamics/HeatExchangerDesign': '换热器帕累托设计',
 'Turbulence/RANSCalibration': 'RANS 封闭标定'}

# One-line Chinese brief and scoring note per task. Written by hand: the English Task.md
# cannot be machine-translated into something a reader can trust, and the table is read by
# people deciding which task to look at. A task without an entry fails the inventory test,
# so a new package cannot silently ship without one.
CHINESE_BRIEFS = {'Acoustics/RoomImpulseResponse': ('布置声源、吸声与受点,让语音房间同时兼顾清晰度、混响时间与声场均匀度',
                                   '清晰度/混响/均匀度综合效用;一阶反射代理与镜像源长程计算排序不同,含安装误差与老化偏移'),
 'Algorithm/MatrixMultiplicationRank': ('搜索双线性张量分解,减少矩阵乘法所需的标量乘法次数', '对最好已知乘法数的平均进度;无上限'),
 'Algorithm/TensorRank555': ('为 5x5 与 6x6 矩阵乘法找有限精度复系数分解,秩低于已知构造',
                             '对最好已知乘法数的平均进度;无上限,实例与 MatrixMultiplicationRank 不相交'),
 'Astrodynamics/LowThrustTransfer': ('设计可迁移的小推力多圈轨道转移策略,兼顾终端精度与推进剂', '标称转移效用;留出任务相位与执行误差稳健性分列,无上限'),
 'ChemicalProcess/DistillationColumnDesign': ('混合整数精馏塔设计:塔板数与进料位置离散,兼顾纯度回收约束与再沸冷凝能耗',
                                              '年化成本;留出迁移与密封变工况分列,无上限'),
 'Chemistry/LennardJonesCluster': ('求 Lennard-Jones 原子簇的最低能量几何构型', '对全局最小的平均缺口闭合;无上限'),
 'ControlTheory/InvertedPendulumSwingUp': ('设计小车倒立摆的摆起与稳定控制律,兼顾轨道限位与作动器约束', '摆起效用;偏移工况稳健性分列'),
 'Electrochemistry/ElectrolyteConductivityDesign': ('在高通量电解液数据回放里分配阻抗测定预算,选出稳健的配方批次',
                                                    '温度剖面电导率 + 批次多样性 + 重复稳健性 + 留出迁移;无上限'),
 'MaterialsScience/AlloyHardnessOptimization': ('在按论文 DOI 分组的多主元合金数据里做实验设计,选出研究外留出的硬度批次',
                                                '留出硬度 + 多样性 + 代理失效 + 不确定性 + 来源迁移 + 稀疏独立确认;无上限'),
 'Mathematics/CapSet': ('在 Z_3^n 里构造更大的 cap set(无三点共线)', '对最好已知规模的平均进度;无上限'),
 'Mathematics/CapSetFrontier': ('在最大值尚未证明的 n=7,8,9 上构造更大的 cap set', '对最好已知规模的平均进度;无上限,与 CapSet 的维度不相交'),
 'Mathematics/ErdosMinimumOverlap': ('把 {1,...,2n} 分成两个等大小的集合,让某个差值出现的最多次数尽量小——Erdős 最小重叠问题,渐近常数在 2025-2026 '
                                     '年被 AlphaEvolve 等多次刷新',
                                     '对三个 n(8、11、15)已被穷举搜索证明的精确最优值的平均进度;这三个规模都是硬上限,已披露,因为超过 n=15 '
                                     '没有可核实的具体最好记录'),
 'Mathematics/HeilbronnTrianglePacking': ('在单位正方形内放 n 个点,让任意 3 点构成的三角形最小面积尽量大——经典的 Heilbronn 三角形问题',
                                          "对 Erich's Packing Center 维护的记录表的平均进度;n=8 "
                                          '已证明最优(硬上限,已披露),n=10、n=11、n=12 仅是最好已知记录,真实无上限'),
 'Mathematics/KissingNumber': ('在 9、10、12 维构造更多与中心球相切的单位球', '固定容差下对最好已知接触数的平均进度;无上限'),
 'Mathematics/NarrowAdmissibleTuple': ('构造比 Polymath8b 已发表直径更小的可容许 k-元组(k=50、54)——有界素数间隔猜想计算核心的同一对象',
                                       '已发表直径的归一化进度(k=50 锚点 246 一手引用确认,k=54 锚点 270 仅二手来源);无上限'),
 'Mathematics/RamseyLowerBound': ('构造更大的 (s,t)-Ramsey 染色以提高下界', '对最好已知染色阶数的平均进度;无上限'),
 'Mathematics/ZarankiewiczMatrix': ('在三组给定的 (m,n) 规模上构造不含 3x3 全一子矩阵的更密 0/1 矩阵——2026 年 LLM '
                                    '进化搜索(OpenEvolve,本仓库自带的搜索后端之一)刚刷新过的极值图论问题',
                                    '对最新发表下界(z(m,n;3,3) 的已发表值)的平均进度;无上限,且这些是尚未被上界证明封顶的下界纪录'),
 'Mathematics/DegreeDiameterGraph': ('在三组给定的 (最大度 d, 直径 k) 上构造尽可能大的图——2026 年有论文报道通过与可浏览器访问的 LLM 交互刷新过下界',
                                     '对度-直径问题维护表中最好已知顶点数的平均进度;无上限,均未被证明最优'),
 'Mathematics/VanDerWaerdenColoring': ('为给定的颜色数与等差数列长度构造尽可能长的、不含单色等差数列的染色',
                                       '两组对照证明最优的 van der Waerden 数(硬上限,已披露)、一组对照尚未证明最优的最好已知下界(真实无上限空间)'),
 'Mathematics/SchurPartition': ('为给定的分组数 k 构造尽可能长的无和分拆(每组内不含 a+b=c,允许 a=b)',
                                'k=4 对照证明最优的 Schur 数(硬上限,已披露);k=6、k=7 对照尚未证明最优的最好已知下界(真实无上限空间)'),
 'DiscreteGeometry/SpherePackingCertificate': ('为球堆积密度给出一份可精确验证的上界证明。Cohn-Elkies '
                                               '定理把上界化为分析问题:找一个函数,它在半径外非正、其傅里叶变换处处非负。除 1/2/3/8/24 维外全部开放——12 '
                                               '维已知最好堆积 0.03704,最好的证明只到 0.06279。取变量 '
                                               'w=2π‖x‖²,拉盖尔特征基的系数是有理的,两条假设都变成有理半轴上的有理多项式,而单变量多项式在半轴非负当且仅当能写成 '
                                               'σ₀+wσ₁,这个刻画是完备的。',
                                               '四个维度(8/12/16/20)取均值,不设上限。零点是闭式的二项证书——这个方法不花力气就能给出的东西;1.0 '
                                               '是已发表的 Cohn-Elkies '
                                               '数值界,而与之等强的精确有理证书似乎在任何维度都还没有人发表过。有理数精确验证,提交浮点判零:网格线性规划这个教科书方法会给出假界(16 '
                                               '阶时 8 维报 0.06237,低于 E8 格实际达到的 0.0625)。'),
 'InformationTheory/ShannonCapacityCertificate': ('为奇圈的香农容量给出一段可精确验证的区间:下界交一个强积幂里的零错码(任意两码字不得在每个坐标上都相等或相邻),上界交一份有理 '
                                                  'Lovasz 矩阵与有理界,使 b*I - A 正定。C7 的容量自 1956 年 Shannon 提出、1979 '
                                                  '年 Lovasz 解决 C5 之后一直未知,下端在 2026 年 7 月一个月内被改进了三次,上端 theta 自 '
                                                  '1979 年未动过。',
                                                  '四个奇圈(C7/C13/C19/C23)取均值,不设上限。零点不是引用而是随包发布的显式码集,oracle '
                                                  '用同一套独立性检验接受它;1.0 是 2026-09-06 '
                                                  '时的已发表最好下界,四个都不是在本题允许的幂上达到的。有理数精确验证,提交浮点判零——数值特征值不是证明。'),
 'QuantumFoundations/BellBoundCertificate': ('为贝尔泛函的量子最大值给出一份可精确验证的上界证明:提交一组基词与若干加权平方,使它们的和恰好等于 beta*I - '
                                             'B。CHSH 的答案是无理数 2√2,只能逼近;I3322 的量子值至今未知,NPA 层级 1 给 0.375、层级 2 给 '
                                             '0.25102173、已知最好值 0.25087538 要到层级 4 以上。',
                                             '四个实例(CHSH 与三种基词预算下的 I3322)取均值,不设上限。分数是所证界到已知量子值距离的对数进步:免费的层级 1 '
                                             '界记 0,已发表的层级 2 界记 1,超过则大于 1。有理数精确验证,提交浮点数直接判零——数值 SDP 解不是证明。'),
 'QuantumFoundations/FourSettingMomentCertificate': ('I_4422^13 的精确 SOS,额外矩必须是冻结 NPA2 池的 Hamming-k 子集,不是 '
                                                     'I3322 自由选词。',
                                                     '从精确层级 1 最优 5/8 到全池有理证书约 0.455331 的对数进度;参考约 0.58,无上限。'),
 'Mathematics/NonlinearCodeRecords': ('在四个 A(n,d) 未闭合的参数上构造尽可能大的二元码;已发表纪录全部由非线性码持有,线性构造够不到',
                                      '从平凡分块重复构造到已发表纪录的平均进度,无上限;验证只是逐对汉明距离计数,与构造方法无关'),
 'Mathematics/Superpermutation': ('构造更短的超排列字符串,使其包含全部排列作为连续子串', '对最短已知长度的平均进度;无上限'),
 'MedicinalChemistry/MolecularLeadOptimization': ('构建结构多样、可开发的新颖先导化合物组合,而非单个分子', '多样性约束下的组合价值,对标已上市药物;无上限'),
 'NuclearEngineering/NeutronDiffusionCriticality': ('在平均富集度约束下优化堆芯燃料富集分布以最大化 k_eff', '相对均匀装载的 k_eff 提升;无上限'),
 'Optics/DiffractionGratingDesign': ('设计五层一维二元介质浮雕,把透射光导入 +1 衍射级,且对偏振与角度容差',
                                     '开发集目标级效率;偏振/角度/波长与工艺偏移稳健性分列,无上限'),
 'Optimization/CirclePacking': ('把 N 个单位圆装进边长最小的正方形', '对最好已知装填的平均缺口闭合;无上限'),
 'ParticlePhysics/CalorimeterDesign': ('设计分层取样量能器,使能量分辨、线性与簇射包容在多档成本约束下同时改善', '多能点效用;留出探测器迁移与最差制造偏移分列,无上限'),
 'Photonics/MultilayerThinFilm': ('设计可见光全谱段的多层宽带减反射膜', '宽带减反射质量;物理下界为零平均反射'),
 'ProteinEngineering/ProteinStabilityDesign': ('在蛋白稳定性实验回放里分配测定预算,设计双点突变批次',
                                               '留出稳定性前十分位 + 多样性 + 蛋白酶稳健性 + 结构域迁移;无上限'),
 'QuantumErrorCorrection/QuantumErrorDecoder': ('为旋转表面码存储设计阈值以下的解码器', '相对最小权完美匹配的逻辑错误率对数下降;无上限'),
 'RNAEngineering/RNAEnsembleDesign': ('设计 RNA 序列,使目标二级结构在整个玻尔兹曼系综上而非仅 MFE 上成立',
                                      '对 ViennaRNA 反折叠的系综缺陷;密封目标,无上限'),
 'RNAEngineering/RNAInverseDesign': ('在长度、字母表、GC 与基序约束下设计目标系综概率高的 RNA 序列',
                                     '目标系综概率 + MFE 迁移 + 代理误升迁;配对相容只是代理,无上限'),
 'Semiconductor/MOSFETDoping': ('设计可迁移的短沟道硅 nMOS 晕环掺杂剖面帕累托档案', '驱动电流对漏电的帕累托超体积;密封留出迁移与最差偏移稳健性分列,无上限'),
 'SignalProcessing/SparseRecovery': ('从远少于奈奎斯特的测量里恢复 k 稀疏信号', '平均恢复信噪比'),
 'StructuralEngineering/TrussWeightMinimization': ('给出跨结构通用的桁架截面尺寸策略,在应力、位移与欧拉屈曲约束下减重',
                                                   '标称减重;密封拓扑迁移与载荷/材料/制造稳健性分列,无上限'),
 'Superconductivity/SuperconductorTcRecord': ('在真实设备压力上限下,用 Allen-Dynes '
                                              '公式在五个真实超导体系间搜索已确认临界温度最高的(体系,压力)组合,并避开一个从未被实现的理论预测(隐含电子-声子耦合超过物理合理上限)',
                                              '真实Tc除以已发表记录250K的直接比值;无上限,可超过已发表记录'),
 'Thermodynamics/HeatExchangerDesign': ('发现换热器的多保真帕累托设计档案,权衡换热量、成本与泵功',
                                        '成本对换热量的帕累托超体积;密封代理一致性、留出迁移与结垢/制造/堵塞稳健性分列,无上限'),
 'Turbulence/RANSCalibration': ('标定可迁移的代数通道流涡黏封闭,同时匹配平均速度与雷诺剪应力', '真实 DNS 拟合;密封高雷诺数迁移与壁面坐标稳健性分列,无上限')}


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
        if not forms.get(form):
            continue
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
        if not subset:
            continue
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
    forms = Counter(r["form"] for r in rows)
    statuses = Counter(r["status"] for r in rows)
    opt_cells = Counter(r["cell"] for r in rows if r["form"] == "optimization")
    disciplines = sorted({r["discipline"] for r in rows})
    opt_named = (
        "engineering_design", "combinatorial", "molecular_design", "certificate_bound",
    )
    status_bits = []
    for status in ("certified", "candidate"):
        if statuses.get(status):
            status_bits.append("%d 个 %s" % (statuses[status], status))
    for status, count in sorted(statuses.items()):
        if status not in ("certified", "candidate"):
            status_bits.append("%d 个 %s" % (count, status))
    lines = [
        README_START, "",
        "当前 %d 个任务包,横跨 %d 个学科,%s。" % (
            len(rows), len(disciplines), "、".join(status_bits)),
        "这一段的每个数字都由 `tests/test_readme_inventory_counts.py` 对着注册表核,改不动就是改错了。",
        "",
        "optimization(%d 个):在受约束的设计空间里把目标做得更好。分%s类:" % (
            forms["optimization"], CHINESE_COUNT_WORDS[len(opt_named)]),
        "工程设计(换热器、桁架、薄膜、解码器等 %d 题)、开放组合纪录(圆堆积、cap set、Ramsey、kissing、"
        % opt_cells["engineering_design"],
        "张量秩、超排列等 %d 题,无上限)、分子与大分子设计(%d 题)、证书上界(%d 题,产物是可验证的论证本身,"
        % (opt_cells["combinatorial"], opt_cells["molecular_design"],
           opt_cells["certificate_bound"]),
        "分数是论证证明出的界有多强)。",
        "分数由做出来的东西有多好决定;公开纪录是 score = 1 的见证,不是封顶。",
        "",
        "Discovery 任务与无 GT 发现环境在 main 分支维护。",
        "", README_END,
    ]
    return "\n".join(lines)


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

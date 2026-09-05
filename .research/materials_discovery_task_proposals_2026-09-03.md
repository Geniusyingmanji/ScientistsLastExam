# 材料发现类任务提案(2026-09-03)

来源:用户提出"MaterialDiscoveryGym"构想 —— 给 agent 开放材料搜索空间 + pymatgen/CHGNet/DFT
工具 + 实验反馈,自主提出候选、迭代优化、超过已有材料性能。本文档核对该构想与本仓库任务契约
(`CONTRIBUTING.md`)的兼容性,并把其中未被现有任务覆盖的部分,按仓库格式实例化为可讨论的
候选任务提案(design draft,非已认证代码)。按 `CONTRIBUTING.md` 末尾"先开 issue 讨论任务想法,
再动手写代码"的流程,本文档就是那一步。

## 1. 已有格式要求(核对结论)

任务目录结构、七条 certified 门槛、`TASK_CARD.yaml`/`metadata.yaml`/`evaluator.py` 契约、
打分模式(`clipped` vs `uncapped`)、发现类三轴分离(机制恢复/假发现率/校准拒答)—— 均见
`CONTRIBUTING.md`。关键约束,与用户原构想直接相关:

- **oracle 必须冻结、确定性、无网络、纯 CPU 数分钟内跑完**(hard 档)。live 调用 CHGNet/VASP/
  pymatgen 的"开放生成 + 实时 DFT 反馈"环路不满足这条 —— 不是不能用这些工具的*思想*,而是不能把
  它们当作*运行时 oracle*:同一候选两次运行必须得同样的分数,而 DFT/MLIP 的版本、收敛参数、
  硬件浮点行为都会漂移。
- **锚点要可重新推导**,不能只是"论文说 SOTA 是 X"。已有任务用三种模式满足这条,本文档的提案
  沿用同样三种:
  1. **真实数据 hash-bound replay**(`ElectrolyteConductivityDesign`、`AlloyHardnessOptimization`):
     下载一份公开数据集,MD5/SHA-256 锁定字节,evaluator 直接重算,不依赖外部字面量。
  2. **冻结解析/约化模型**(`QuinaryConvexHull`、`LennardJonesCluster`):公式本身就是锚点,
     evaluator 现算现验证,不引用任何外部"已知最优"数字。
  3. **程序化约化模拟器**(`CatalystDeactivationLab`、`PhaseDiagramDiscovery`):公开的简化物理
     方程 + 隐藏参数,独立数值积分/穷举核对。
- **黑盒安全**:候选拿不到 oracle 代码、拿不到测试集划分。
- **格点占位**:`sle/conf/exam_taxonomy.yaml` 里每个任务占 `(form, kind/analogue)` 网格的一格,
  同一格可以有多个任务,但新任务必须证明自己不是同格里已有任务的克隆(`note:` 字段写明区别)。

## 2. 用户构想 vs 已有任务的重叠核对

在写新任务之前先核对是否已经存在,避免重复:

| 用户提出的方向 | 仓库里已有的任务 | 重叠程度 |
|---|---|---|
| Track A 电解质发现(液态说明) | `Chemistry/ElectrolyteConductivityDesign`(真实 EIS 数据 replay,EC/PC/EMC/LiPF6) | 高,但仅液态电解质,固态电解质是空白 |
| 结构/合金材料优化 | `Chemistry/AlloyHardnessOptimization`(真实 MPEA 硬度数据 replay) | 高,已覆盖 |
| "材料生成 + 稳定性(凸包)" | `Chemistry/QuinaryConvexHull`(解析 mixing-plus-well 凸包发现) | 中,已有五元凸包发现原型,但只有稳定性,没有性能目标(电导率/Tc/催化活性) |
| 相图/物相发现 | `Chemistry/PhaseDiagramDiscovery`(二元 XRD 相图) | 中,已覆盖"物相发现"这个 substance 格 |
| 催化材料发现 | `Chemistry/CatalystDeactivationLab`(有状态动力学/失活推断) | 低 —— 这是"给定催化剂推断动力学",不是"筛选催化剂组成",两者是不同的科学问题 |
| 高温超导体发现 | 无 | 空白 |
| 光伏/钙钛矿材料 | 无 | 空白 |

结论:**固态电解质、超导体、HER 催化剂筛选、钙钛矿光伏是四个真实空白**,合金和液态电解质已经
有 certified 级别的对应任务,不需要重做。下面把这四个空白按仓库格式实例化为候选提案。

---

## 3. 提案一:固态锂离子导体筛选

`benchmarks/Chemistry/SolidStateConductorScreening/`(目录挂在 `Chemistry` 大类下,
`metadata.yaml` 里的细分 `domain: SolidStateIonics` 需要先在 `sle/benchmark_layout.py` 登记)

**科学问题**:在一个跨氧化物/硫化物/卤化物三个化学家族、掺杂比例离散化的封闭组成目录里,
同时优化室温离子电导率、稳定性(热力学 + 电化学窗口)与原材料成本 —— 这三者存在权衡
(硫化物电导率最高但空气/电化学稳定性差且成本随 Ge 类元素上升;氧化物 LLZO 类稳定但电导率低两个
数量级)。

**为什么不是 `ElectrolyteConductivityDesign` 的克隆**:后者是单一化学体系(液态碳酸酯)、单温度
曲线、纯真实数据 replay,只优化电导率一个目标。本任务是固态、多化学家族、多目标(电导率 ×
稳定性 × 成本),且用 Arrhenius 温度序列(而非单点电导率)反演活化能 —— kind 落在
`discovery/parameter_inversion` 与 `optimization/frontier_eng` 的交界,建议记为
`optimization, analogue: frontier_eng, note: solid_multiobjective_arrhenius_not_liquid_single_axis_ridge`。

**Oracle(冻结解析模型,类比 `QuinaryConvexHull` 的 mixing-plus-well)**:

```text
封闭目录: 4 个化学家族(oxide-garnet / sulfide-argyrodite / halide / phosphate-NASICON 型)
          × 每族 5 个离散掺杂比例 = 20 个候选组成 ID

sigma(T; family, x) = sigma0(family, x) * exp(-Ea(family, x) / (k_B * T))
   Ea, sigma0 由每族一条已标定曲线 + 掺杂比例的解析微扰给出,
   校准锚点(真实、可引用,不是候选可见的数字):
     LGPS 类硫化物   ~室温 1e-2 S/cm 量级,DOI 10.1038/nmat3066(Kamaya et al. 2011)
     LLZO 石榴石     ~室温 1e-4 S/cm 量级,DOI 10.1002/anie.200701144(Murugan et al. 2007)
     卤化物 Li3YCl6  ~室温 1e-3 S/cm 量级,DOI 10.1039/C8EE01053F(Asano et al. 2018)

stability_margin(family, x) = 解析"势阱深度"函数,掺杂比例越极端势阱越浅(仿 QuinaryConvexHull)
electrochem_window(family)  = 阴离子化学决定的解析区间(氧化物最宽,硫化物最窄)
cost(family, x)             = 真实元素成本表(USD/kg 数量级排序即可,不需要精确到当前市场价)
                               —— Ge、Y、La 贵,Cl、S、P、O 便宜
```

**候选契约**:

```python
def screen_solid_electrolyte(problem, assay):
    """assay(composition_id) 花一次预算,返回该组成在若干温度点的带噪电导率序列
    (重复调用同一 ID 重新抽一次测量噪声,不返回真值 Ea/sigma0)。
    返回 {"composition_ids": [三个不同 ID],
          "predicted_ea_ev": {...}, "predicted_sigma0": {...}}
    """
```

`problem` 暴露:20 个组成的家族标签、掺杂比例、历史文献代理电导率(粗略、有偏,类比
`ElectrolyteConductivityDesign` 的历史 proxy)、温度点、`assay_budget`。

**打分**:`uncapped`(固态电解质电导率纪录仍在被刷新,近年硫化物已到 >10 mS/cm 级别,DOI
10.1038/s41563-019-0286-7,Kato et al. 2016 类工作),baseline = 只按历史 proxy 选、不花 assay
预算;reference = 穷举 20 个组成 × 三目标加权效用的封闭空间见证解。三个目标(log 电导率、稳定性
裕度、成本)分开报告,不合成前置单一权重 —— 权重公开给候选,但底层三项分开留痕以支持后续复核。

**下一步**(实现前需要做的,遵照 `CONTRIBUTING.md` "锚点要可重新推导"):把上面三条锚点论文的
具体数值表重新抄一遍原始 Table/Figure,写进 `references/known_best.md`,而不是凭记忆写死进
evaluator。

---

## 4. 提案二:常压超导临界温度纪录搜索

`benchmarks/Physics/SuperconductorTcRecord/`(`metadata.yaml domain: Superconductivity`,
需要登记新 domain)

**科学问题**:在声子介导(BCS/Eliashberg,不含铜氧化物一类非常规机制)的氢化物/二硼化物族里,
在给定压力上限约束下,最大化 Allen-Dynes 公式给出的 Tc,同时满足动力学(声子)稳定性约束。

**为什么是空白 + 为什么落在 optimization/frontier_eng**:仓库里没有任何超导相关任务。
不做"发现某条经验律"(那是 `discovery/formula` 格,已有 `ActiveLawDiscovery` 等占位),而是把
Allen-Dynes 公式本身作为**已知、公开**的冻结模拟器(类比 `MOSFETDoping`/`MultilayerThinFilm`
"在冻结模拟器下做工程设计"的模式),候选要做的是在受限设计空间里找到更好的 (λ, ω_log, μ*)
组合 —— 工程优化,不是定律恢复。

**Oracle(冻结解析 + 程序化映射)**:

```text
Allen-Dynes 公式(公开,可现算,不依赖外部字面量):
  Tc = (omega_log / 1.2) * exp( -1.04*(1+lambda) / (lambda - mu_star*(1+0.62*lambda)) )

结构 -> (lambda, omega_log) 的映射:程序化、参数化于
  family ∈ {MgB2-like, LaH10-like, H3S-like, YH6-like}   (声子介导氢化物/二硼化物族)
  x = 掺杂/氢含量比例, P = 压力(GPa,上限约束,例如 <= 250 GPa)
  lambda(family, x, P), omega_log(family, x, P) 由每族一条经校准的单调曲线 + 噪声给出

动力学稳定性门:phonon_stable(family, x, P) -> bool(解析规则,某些 (x,P) 组合"虚频"不稳定,
  提交不稳定组合直接判该世界为 0,呼应 QuinaryConvexHull 的"glass 世界必须拒答"逻辑)

真实校准锚点(仅用于标定映射曲线的量级,不是候选可见数字):
  MgB2   Tc ≈ 39 K,常压,DOI 10.1038/35065039(Nagamatsu et al. 2001)
  H3S    Tc ≈ 203 K,~155 GPa,DOI 10.1038/nature14964(Drozdov et al. 2015)
  LaH10  Tc ≈ 250-260 K,~170 GPa,DOI 10.1103/PhysRevLett.122.027001(Drozdov et al. 2019)
```

**候选契约**:

```python
def search_superconductor(problem, probe, confirm):
    """probe(family, x, P) 便宜、带噪,近似给出 (lambda, omega_log);预算大。
    confirm(family, x, P) 昂贵(类比 DFT/高精度计算),预算小(例如 3 次),
    返回精确 (lambda, omega_log, mu_star, phonon_stable) —— 最终打分只认 confirm 过的提交。
    返回 {"family": ..., "x": ..., "pressure_gpa": ..., "confidence": ..., "abstain": bool}
    """
```

这个双预算(便宜 probe / 昂贵 confirm)结构直接对应用户构想里"先用 CHGNet 粗筛、再用 DFT
精算"的分层思路,但把 CHGNet/DFT 都换成冻结、确定性的程序化 stand-in,保留了"筛选-确认"这个
科学工作流的结构,又满足确定性要求。

**打分**:`uncapped`,baseline = 未优化的 Nb 单质(Tc = 9.3 K,教科书值,真实、无需外部依赖)——
reference = 约束区间内可达到的 Allen-Dynes 峰值见证解。压力惩罚项分开报告(避免"无限堆压力"
刷分)。

---

## 5. 提案三:HER 催化剂 ΔG_H* 火山图筛选

`benchmarks/Chemistry/HERVolcanoScreening/`(`metadata.yaml domain: Catalysis`,与
`CatalystDeactivationLab` 同 domain 但不同 kind)

**科学问题**:HER(析氢反应)交换电流密度与吸附自由能 ΔG_H* 呈火山形(Sabatier 原理):
|ΔG_H*| 越接近 0 活性越高。在一份真实文献 DFT 数据表(Nørskov et al. 2005, *J. Electrochem.
Soc.* 152, J23,DOI 10.1149/1.1856988;Greeley et al. 2006, *Nat. Mater.* 5, 909,
DOI 10.1038/nmat1752)覆盖的金属/合金/过渡金属化合物目录里,在有限"DFT 计算"预算下找到
|ΔG_H*| 最小、同时地壳丰度高(避开 Pt 族)的候选组合。

**为什么不是 `CatalystDeactivationLab` 的克隆**:后者是"给定一个催化剂,靠有状态实验推断动力学
参数"(discovery/parameter_inversion,重点是状态机、不可逆物理动作、漂移);本任务是"在多个
候选材料间做静态热力学描述符筛选"(optimization/frontier_eng,重点是预算分配 + 火山图权衡),
科学问题、oracle 力学、评测维度都不同。

**Oracle(真实数据 hash-bound replay,类比 `AlloyHardnessOptimization`)**:直接采用上述两篇文献
表格里的金属/合金 ΔG_H* 值作为封闭候选目录(需要从原始 Table 逐条抄录并 MD5/SHA-256 锁定,
本文档不臆造具体数字,留给实现阶段核对原始来源)。加噪声模拟"重复 DFT 计算的收敛误差",重复
查询同一候选重新抽一次噪声。

**候选契约**:

```python
def screen_her_catalyst(problem, dft):
    """dft(candidate_id) 花一次预算,返回带噪 delta_G_H(eV)。
    返回 {"candidate_ids": [三个不同 ID], "predicted_dG": {...}}
    """
```

`problem` 暴露候选目录(金属/合金名、地壳丰度粗分类、坐标近似位置提示但不给出精确值)、
`dft_budget`(远小于目录大小,逼迫用线性标度关系/火山图先验做主动学习,而不是穷举)。

**打分**:`clipped`(有限公开数据表,不是活跃前沿纪录),utility = -|ΔG_H*| 质量(90%)+
地壳丰度/去 Pt 化奖励(10%),baseline = 只选 Pt(历史默认答案,真实但不用预算),reference =
穷举目录内最优三元组合。

---

## 6. 提案四:钙钛矿光伏组成设计(带隙 × 稳定性)

`benchmarks/Chemistry/PerovskitePVDesign/`(`metadata.yaml domain: Photovoltaics`,需登记新 domain)

**科学问题**:ABX3 卤化物钙钛矿的带隙决定 Shockley–Queisser(SQ)单结效率上限(公开、
可现场数值积分复算的探测平衡公式,峰值约 33.7% @ Eg ≈ 1.34 eV,Shockley & Queisser 1961,
DOI 10.1063/1.1736034),但带隙由 A/B/X 位混合比例决定,而混合比例又受 Goldschmidt 容忍因子
`t = (r_A + r_X) / (√2 (r_B + r_X))`(公开 Shannon 离子半径表,0.8 < t < 1.0 才结构稳定)约束 ——
效率最优点往往落在容忍因子的稳定边界附近,这正是该体系的真实科学张力。

**为什么这是"可现算的锚点"而不是"抄论文数字"**:SQ 极限是一个对 AM1.5 光谱做探测平衡积分的
封闭数学问题,evaluator 可以直接数值积分复算,不依赖任何外部"已知最优"字面量 —— 这一点与
`LennardJonesCluster`/`QuinaryConvexHull` 的"公式即锚点"模式完全一致,是四个提案里锚点质量
最高的一个。

**候选契约**:

```python
def design_perovskite(problem, characterize):
    """characterize(composition_id) 花一次预算,返回带噪 (bandgap_eV, tolerance_factor,
    decomposition_stability_proxy)。
    返回 {"composition_ids": [三个不同 ID]}
    """
```

封闭目录:A 位(MA/FA/Cs 三元离散混合比例)× B 位(Pb/Sn 离散混合比例,Sn 无铅但历史上更不
稳定)× X 位(I/Br/Cl 离散混合比例)组合出的离散网格(类比 `QuinaryConvexHull` 的整数组成目录),
带隙用真实已知锚点标定 bowing 曲线(MAPbI3 ≈1.55 eV、MAPbBr3 ≈2.3 eV、FASnI3 ≈1.4 eV、
CsPbI3 ≈1.7 eV,均为文献公开值,DOI 10.1021/ja809598r 等,实现阶段需逐条核对原始来源)。

**打分**:`clipped`,score = SQ 效率(由候选组成对应带隙现场积分得到)× 稳定性门(容忍因子越界
或稳定性代理低于阈值则该候选记 0,呼应 `QuinaryConvexHull` 的"假稳定"gating 逻辑)+ 无铅奖励,
baseline = 历史起点 MAPbI3(真实但非最优),reference = 封闭目录内可行域最优见证解。

---

## 7. 与用户原构想的关键差异(需要向用户说明的取舍)

1. **"开放材料搜索空间"→"封闭但大的组成目录"**。SLE 不允许 oracle 依赖未冻结的生成式搜索
   (无法确定性复算),因此四个提案都用有限、显式列出的组成目录(20~数百量级),而不是连续/无限
   的分子式空间。这与 `QuinaryConvexHull`/`PhaseDiagramDiscovery` 的既有设计哲学一致。
2. **"CHGNet/DFT 作为运行时 reward"→"CHGNet/DFT 的角色被拆成 probe/confirm 两级冻结 stand-in"**。
   保留了"便宜代理 + 昂贵确认"的科学工作流结构(提案二尤其明显),但两级都是确定性、可重跑的
   程序化函数,不是真的调用外部 ML 库或 DFT 引擎。
3. **"超过已有材料性能"→"`uncapped` 打分模式,追平参考解为 1.0,超越 >1.0"**。提案一、二天然
   适合这个模式(固态电解质电导率、超导 Tc 都是活跃研究前沿);提案三、四数据来源是有限公开表格
   /封闭组成网格,更适合 `clipped`。
4. 四个提案目前都是 **candidate 草案**,不是可运行代码 —— 下一步需要:(a) 把文中标注的每条
   引用重新去源头核对具体数值(不能凭记忆写进 evaluator);(b) 用 `scripts/gen_task.py` 或手写
   落地成 `Task.md`/`TASK_CARD.yaml`/`evaluator.py`;(c) 跑
   `scripts/check_evaluator_survives_bad_candidates.py`、`scripts/audit_documented_keys.py`、
   `scripts/check_task_contribution.py`;(d) 先以 `candidate` 状态加入 `sle/certification.yaml`,
   不自我认证。

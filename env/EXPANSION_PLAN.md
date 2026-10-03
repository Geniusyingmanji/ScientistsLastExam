# Discovery tasks → 可交互科学环境：扩展计划

状态：仅规划，尚未创建这些新环境、调用模型或修改历史成绩。日期：2026-10-03。

## 1. 范围与结论

本计划以当前 `codex/env` 的 [46 项 discovery task](../TASKS.md) 为范围，逐项对应见后表和 [结构化清单](LEGACY_TASK_MIGRATION_PLAN.json)。优先五项及 QCM 已阅读 `Task.md`；其余主要依据任务总表进行第一轮映射，下一步还需审查前向计算代码、依赖和数值证据。此表表达可迁移方向，不代表科学有效性、实现完成或准入通过。

初步分为：5 项扩展已有环境；35 项需要新建或重构科学环境；6 项进入独立的数学、计算系统、算法审计或证据研究轨。可以为全部任务设计计算交互，但不能保证原题原样转化后都能测量开放科学发现。目录名都是候选设计，不承诺一次创建 45 个目录。

现有 `env/` 是 7 个有 GPT 结果的环境、6 个已注册实验环境，以及未注册的 optical_diffraction 原型。旧 `sle episode` 路线另外列有 MeasurementAudit、CausalTransportDiscovery、EnzymeRecoveryDesign、SurvivorshipAuditDesign、EnzymeMechanismDiscovery 五个环境/原型。这些清单有概念交叉，不应相加作为独立成熟世界数量。

旧任务主要回答“交回哪个公式、参数、类别”；新环境应提供“一个可以持续提问的实验室”。复用前向模拟、仪器及数值检查，重新设计候选可见的信息、行动和证据出口。旧 evaluator 的标签正确率、精确相集合或参数恢复分可以作为私有开发诊断，不能直接变成开放发现的判定标准。

## 2. 先补齐的公共能力

当前 [World 合同](CONTRACT.md) 每次 `run` 都重新准备实验；[research runner](RESEARCH_RUNNER.md) 已有实验、隔离分析、模型快照和两解释前瞻检验，但尚无本轮 live GPT 成绩，`finish` 仍要求完成两解释检验。[单模型适用范围检验](DOMAIN_MAPPING.md) 目前是独立 operator 工具，尚非 Agent action。

下一版本先处理以下缺口，保留历史协议不变：

1. **单模型前瞻路径。** Agent 可以先保存一个模型、封存对新条件的预测，再测量。两解释比较保持可选，避免为了完成开放发现流程而编造第二个模型。最终报告区分技术完成、证据不足、局部支持、反驳和无定论。有限网格检验不能自动声称发现连续边界。
2. **模型版本与结果留存。** 每个预测绑定代码、参数、求解器及已见数据；最终产物明确引用同一版本。修改后对旧数据的检查标成回归检查，新的前瞻证据必须来自新实验。模型目录和全部公开记录始终可在分析沙箱中读取。
3. **多种实验语义。** 保留现有重新准备的批次接口；增加版本化的持续样品会话；为观察型环境声明站点、样品或天体，以及复访共享的隐藏状态。不能靠全局缓存偷偷模拟样品历史。
4. **相应的观测与统计合同。** 不把伯努利漏检、有限 shots、缺失/截断读数和同样品重复测量都当作独立高斯误差。记录采样单位、重复层级、共享状态、校准来源、可用置信方法及不可用项目；未支持的验证方式明确拒绝。
5. **仪器说明与理论提示分开。** 默认完整公开单位、控制、噪声、准备和时间语义；是否给方程作为版本化条件。提供方程的识别实验与仅给仪器契约的研究分开报告。删掉方程不自动证明抗记忆污染。

Agent 继续通过共享 runner 的公开动作调用环境。当前没有可直接复用的统一 MCP server；如增加 MCP，只封装同一公开实验服务与权限，不向 Agent 暴露 kernel、私有参数或隐藏测试。

## 3. 首轮新增五个环境

| 优先次序 | 拟建目录 | 可以研究什么 | 实验与观测 | 必须处理的竞争解释 |
|---|---|---|---|---|
| 1 | `env/molecular_forces/` | 几个粒子靠近或分开时，力如何变化？两两作用够不够解释？ | 三粒子位置、距离、几何及温度；返回能量和力。沿用旧题已有控制，未来动力学轨迹另行开发。 | 平衡距离附近相似的势函数，在近距离、远距离或三角形几何上不同；不能限定只能选 Mie/Morse。 |
| 2 | `env/climate_response/` | 外部加热为何产生快、慢两段响应？停止加热后为何还在变化？ | 选择辐射强迫的阶跃、脉冲、斜坡和周期历史；观测表面温度与能量不平衡。 | 深层储热、状态依赖反馈和仪器/观测限制；支持局部有效模型，不要求猜层数。 |
| 3 | `env/catalyst_aging/` | 产量越来越低，是催化剂变差，还是仪器读数在漂？ | 使用新旧试片、改变温度/浓度/时长，测空白与标准件；保存试片和仪器版本。 | 不可逆失活与增益漂移；同样品反复实验不等于独立重复。先建立持续状态协议。 |
| 4 | `env/field_ecology/` | 没找到某物种，是它不在，还是方法漏检？ | 选择站点、复访次数和调查方法；返回发现/未发现及公开地点信息。 | 真实占域变化与检测率变化；复访共享占域状态，增加复访不等于增加独立站点。 |
| 5 | `env/phase_equilibria/` | 一个复杂谱代表新物质，还是已有相的混合？ | 选择组成、独立制备批次及测量；退火时间作为下一步新增控制，须先实现与校验相应动力学。 | 两相叠加、杂质和未达到平衡；有限时间下不强迫给出永久稳定相。 |

前两个最适合先跑通现有批次链路。后三个分别增加持续样品、随机调查和制备历史能力，分阶段集成。首版气候环境只是可控的简化计算世界；分子力环境只是三粒子能量/力实验，不声称实现通用分子动力学。相图先明确其热力学和制备模型，不能给静态谱生成器随意添加“退火”按钮。

每个环境优先设计三个研究入口：开放研究、一个有意义的竞争解释问题、一个新条件预测问题。模型修订与适用范围任务在相应运行器支持后再开放。入口只提出研究问题，不点明必然存在的现象；同一环境允许多个不同但有证据的发现。

## 4. 环境包结构与复用原则

```text
env/<name>/
  world.py                 # 批次 World 或明确声明的会话适配
  protocol.py              # 公开仪器、控制、单位和验证
  kernel.py                # operator 私有前向计算
  observation.py           # 噪声、采样单位与重复语义（按需）
  session.py               # 持续样品/仪器状态与事件血缘（按需）
  baseline.py              # 只读公开记录的基线
  world.json
  README.md
  SCIENTIFIC_NOTES.md
  examples/
  tests/
```

沿用 [AUTHORING.md](AUTHORING.md) 的明确适配点：注册、task profiles、claim semantics、prospective noise、calibration、evidence packet、presentation、prediction semantics。每个新增语义必须有对应支持或明确的不可用状态。不要把所有环境塞进一个不断增加条件分支的评分器，也不因名字相近强行共用前向模型。

特别保持这些区别：经典 spin_echo 不等于量子 ActiveNoiseSpectroscopy；population_drift 不等于人口史共祖推断；平衡 Ising 不等于 Hamiltonian 时间演化；一维热输运不等于二维各向异性场；六自旋枚举不支持大系统临界外推。可以共享数值组件和仪器封装，但科学合同需要分别建立。

持续样品协议至少记录 session、sample、request ID、父版本、测量版本、实际消耗和不可变事件。完全相同请求的重取只返回已保存回执，不再次改变试片；换载荷复用 ID、陈旧版本和重复破坏性执行必须有明确处理。并行返回顺序不能替代样品血缘。

## 5. 从“有模拟器”到“适合发现”的验收

每个候选先写研究问题、数值上限与检查计划，再运行开发实验：

- 至少一组具体的可区分解释：在受限设计下近似一致，但某个合法实验能区分；另外保留真正难以区分的情形，允许结果为未知。
- 前向核用解析极限或独立实现核对。处理单位、边界、事件顺序、守恒及离散误差，数值误差不能冒充现象。不要仅把同一个公式复制到测试中。
- 比较无观测、简单经验法、强固定实验设计以及知晓理论的参考方法；记录各自先验、实际预算与失败。若固定模板接近满分，保留为基础能力环境，或增加有科学意义的问题；不靠加噪声与改分数制造难度。
- 公开题面在不同隐藏实例间保持一致；排查名字、错误信息、预算和通道顺序是否泄漏家族。冻结结构划分和私有实例，并记录已公开代码/种子的暴露历史。
- 开放发现报告绑定“问题—观测—候选解释—提前预测—新观测—修订—适用范围”。定量预测验证独立于机制审阅；不要求和唯一 golden answer 同文、同公式或同标签。
- 完成率、失败类型、预测误差、前瞻支持/反驳/无定论、竞争解释与适用范围分别报告。Discovery Depth 沿用已有六维证据框架；没有新的自动深度分，也不把活动次数算作发现深度。

已有 6 个实验环境同步做上述 readiness 盘点，并保留各自未解决的问题；不能因为已经注册就直接扩入 GPT 成绩。光学衍射先完成共享接口和观测轴集成，再考虑注册。

## 6. 推进顺序与预算建议

**第一个约 8 小时迭代的目标**是拿到两个可检查的新环境原型与公共协议设计，不承诺五个环境均完成科学验证。计划内工作流可以并行：分子力、气候响应、公共运行器与验收；持续样品/离散观测先做设计。

| 时间段 | 工作 | 可交付结果 |
|---|---|---|
| 0–1 h | 核对优先任务的前向核、旧捷径、接口与依赖，冻结开发检查 | 每环境一页规格、实例/工作量计划、复用与重写清单 |
| 1–4 h | 分子力与气候响应并行做适配，公共层设计单模型前瞻路径 | 两个 prototype 包；新的运行器协议草案与兼容边界 |
| 4–6 h | 独立数值参考、歧义例、无观测/固定设计对照、隔离执行 | 保存成功及失败的有界开发结果；有问题的原型继续修复 |
| 6–8 h | 共享适配、脚本策略端到端检查、页面说明；设计后续三种接口 | 达标者标 experimental，未达标者留 prototype；不伪装成 GPT 成绩 |

后续预计再用 2–4 个同规模迭代推进催化剂、生态和相图，并对共享协议做完整集成验证。时间只是排期估计；独立数值检查、仪器语义和强基线暴露的问题决定实际进度。

之后单独建立模型试验计划：每个达标环境先选 3 个未用于开发的实例，每个实例做 2 次独立 Agent 运行。五个环境共 30 次研究运行，可按先完成的两个环境 12 次、后三个环境 18 次推进。每次至多 24 个模型请求时，合计上限 720 次；这是下一轮候选预算，不是当前已运行或已占用的调用。重复运行使用独立实验噪声，并区分实例差异与同实例 Agent 随机性。3 个实例只能用于 pilot，不能声称可靠估计总体发现率。

同一环境内固定实验、分析和观察精度预算；不同环境的仪器成本单独报告。先用一个统一接口/理论提示条件检查基本工作流程，再分别安排提示、预算或快照的单因素比较。不开多因素混杂的 scaling。

本次用户请求是规划，因此不运行上述模拟、测试面板或 API。上一轮八小时任务及其请求账本保持完成状态；新试验使用新冻结清单和新预算，旧账本不重置、不扩容。历史得分和已发布案例不重算。

## 7. 全部 46 项的迁移方向

以下是逐项初筛。`extend` 表示已有环境基础可复用，不表示改造简单；`new` 表示科学环境候选；`separate` 表示可以交互化但建议单独评价。P1 是下一轮重点或已有环境的低增量补强，P2 是后续领域扩展，P3 是独立研究轨。

### 扩展已有环境（5 项）

| 旧任务 | 目标方向 | 优先级 | 改造要点 |
|---|---|---|---|
| [GeneNetworkIntervention](../benchmarks/Biology/GeneNetworkIntervention/Task.md) | `gene_regulation` | P1 | 已有对应接口；补表型干预、隐藏通路与模型不足研究，原版本和成绩保留。 |
| [ModalDamageAttribution](../benchmarks/Engineering/ModalDamageAttribution/Task.md) | `coupled_oscillators` | P2 | 复用动力响应基础，新增温度、支座和损伤控制及传感器选择；须做结构模型独立验证。 |
| [ReactionMechanismFitting](../benchmarks/Chemistry/ReactionMechanismFitting/Task.md) | `reaction_kinetics` | P1 | 已有对应环境；增加非一级或遗漏通路的版本化研究情形，不改旧反应实例。 |
| [ConvectionDiffusionOpt](../benchmarks/Engineering/ConvectionDiffusionOpt/Task.md) | `heat_transport` | P2 | 复用热输运接口，新增二维各向异性核与加热布局；当前一维核不能原样承担旧题。 |
| [CriticalPhenomenaLab](../benchmarks/Physics/CriticalPhenomenaLab/Task.md) | `ising_spin` | P2 | 开发独立有限尺寸扩展、采样及混合诊断；当前六自旋枚举不足以支持相变外推。 |

### 新建或重构科学环境（35 项）

| 旧任务 | 目标方向 | 优先级 | 改造要点 |
|---|---|---|---|
| [EnzymeKineticsLaw](../benchmarks/Biology/EnzymeKineticsLaw/Task.md) † | `enzyme_recovery` | P2 | 接入加载、洗脱与恢复；由新条件预测验证解释，旧六选一与饱和结论不迁移。 |
| [AMOCTippingRefusal](../benchmarks/EarthScience/AMOCTippingRefusal/Task.md) † | `ocean_circulation` | P2 | 建立可控简化环流实验与长时间观测；移除历史特征捷径，不以生成器标签判发现。 |
| [WallClosureDiscovery](../benchmarks/Engineering/WallClosureDiscovery/Task.md) | `wall_flow` | P2 | 选择工况和剖面位置，研究局部闭合关系及失效范围；窄工况下允许多解。 |
| [ActiveLawDiscovery](../benchmarks/Mathematics/ActiveLawDiscovery/Task.md) | `nonlinear_dynamics` | P2 | 开放初态与驱动，允许候选自写预测模型；固定项库匹配只作开发诊断。 |
| [ComplexBoseLaw](../benchmarks/Physics/ComplexBoseLaw/Task.md) | `mode_occupancy` | P2 | 改变温度、模态选择和测量设置，检验占据关系；不用玻色/费米类别作最终答案。 |
| [InterventionalSCM](../benchmarks/ComputerScience/InterventionalSCM/Task.md) | `causal_intervention` | P2 | 观察与do干预分开，加入可识别与不可识别情形，验证新干预响应而非只交邻接矩阵。 |
| [SurvivorshipConfoundedDesign](../benchmarks/ComputerScience/SurvivorshipConfoundedDesign/Task.md) † | `causal_transport` | P2 | 复用后继CausalTransportDiscovery的取样/桥接研究思路；旧筛选表估计器保留为强对照。 |
| [HiddenCouplingNetwork](../benchmarks/Physics/HiddenCouplingNetwork/Task.md) | `relaxation_network` | P2 | 提供驱动和动态/稳态观测，研究隐藏单元与直接作用；不能等同于二阶弹簧网络。 |
| [OccupancyDetectionDesign](../benchmarks/Biology/OccupancyDetectionDesign/Task.md) | `field_ecology` | P1 | 让Agent选择站点、复访和调查方法；保留站点隐藏状态与漏检，新增离散观测协议。 |
| [ForcedSignalAttribution](../benchmarks/EarthScience/ForcedSignalAttribution/Task.md) | `climate_observatory` | P2 | 选择控制段、地区和观测；检验强迫解释在新数据上的表现，与可控气候实验区分。 |
| [UPbConcordiaInference](../benchmarks/EarthScience/UPbConcordiaInference/Task.md) | `geochronology` | P2 | 选择样本域、复测和测量精度，验证事件历史对新域的预测；不允许改写地质历史。 |
| [HeavyTailEvidence](../benchmarks/Mathematics/HeavyTailEvidence/Task.md) | `stochastic_processes` | P2 | 可追加样本和改变观察窗口，研究尾部与截断；有限样本保留多种解释。 |
| [DiscrepantMeasurements](../benchmarks/Physics/DiscrepantMeasurements/Task.md) | `measurement_audit_lab` | P2 | 新增校准、标准件、仪器交叉测量；只给八组数字不足以构成交互实验室。 |
| [LookElsewhereAnomaly](../benchmarks/Physics/LookElsewhereAnomaly/Task.md) † | `spectrum_anomaly_lab` | P2 | 选择扫描范围和后续采样，预先封存检验并保留试验次数；旧单次满分结果不认证新难度。 |
| [PTAHellingsDowns](../benchmarks/Physics/PTAHellingsDowns/Task.md) † | `timing_array` | P2 | 选择目标、时间基线和观测资源；重建多源系统误差，四模板比对保留为强捷径对照。 |
| [TransitTimingAttribution](../benchmarks/Physics/TransitTimingAttribution/Task.md) | `transit_observatory` | P2 | 选择下一次凌星观测与辅助活动观测；验证未见时刻的预测，不能随意干预恒星。 |
| [MetagenomeCompositionAssignment](../benchmarks/Biology/MetagenomeCompositionAssignment/Task.md) | `metagenome_sampling` | P2 | 选择marker、测序量与独立样本；保留近缘别名和未知成分，不把库ID当发现本身。 |
| [CrowdedSpectrumAssignment](../benchmarks/Chemistry/CrowdedSpectrumAssignment/Task.md) | `spectral_mixtures` | P2 | 选择波段、分辨率和重复采样；研究混合物与单物种解释，新增控制需要前向模型支持。 |
| [PhaseDiagramDiscovery](../benchmarks/Chemistry/PhaseDiagramDiscovery/Task.md) | `phase_equilibria` | P1 | 开放组成和重复制备；新增退火时间需建立动力学。以新配方谱和混合规律验证，不匹配相标签。 |
| [QuinaryConvexHull](../benchmarks/Chemistry/QuinaryConvexHull/Task.md) | `multicomponent_stability` | P2 | 选择组分与候选结构的能量计算；由新计算检验稳定性，保持五元凸包与二元相图的范围区别。 |
| [MethaneSourceAttribution](../benchmarks/EarthScience/MethaneSourceAttribution/Task.md) | `atmospheric_sources` | P2 | 选择同位素、乙烷、部门清单和位置/时段观测；研究源与汇的混淆，先明确可识别范围。 |
| [TransmissionSpectrumSpecies](../benchmarks/Physics/TransmissionSpectrumSpecies/Task.md) | `transmission_atmosphere` | P2 | 选择波段、分辨率和凌星次数；将云与分子混淆作为可保留的解释，不强迫命名。 |
| [DemographicSFS](../benchmarks/Biology/DemographicSFS/Task.md) | `population_history` | P2 | 选择测序量、样本量和群体；需人口史/谱前向模型，现有population_drift不等同于共祖史。 |
| [CatalystDeactivationLab](../benchmarks/Chemistry/CatalystDeactivationLab/Task.md) | `catalyst_aging` | P1 | 迁移试片与仪器状态、标准件、破坏性反应及乱序回执；必须使用新的持续状态协议。 |
| [ForceFieldCalibration](../benchmarks/Chemistry/ForceFieldCalibration/Task.md) | `molecular_forces` | P1 | 复用三粒子能量/力查询，探索距离、几何与温度；允许开放预测模型，不限定Mie/Morse答案。 |
| [NMRSpectrumFitting](../benchmarks/Chemistry/NMRSpectrumFitting/Task.md) | `nmr_spectroscopy` | P2 | 增加采集条件、分辨率和复测，区分真实峰与仪器基线；低残差不自动认证新峰。 |
| [SpinSystemInference](../benchmarks/Chemistry/SpinSystemInference/Task.md) | `nmr_spectroscopy` | P2 | 与NMR采集工具共用外层，但增加真实自旋耦合前向模型；二级谱不降格为独立峰。 |
| [EnergyBalanceModel](../benchmarks/EarthScience/EnergyBalanceModel/Task.md) | `climate_response` | P1 | 把辐射强迫实验变成开放响应研究，隐藏反馈/储热结构；检验新脉冲和时间尺度。 |
| [GravityInversion](../benchmarks/EarthScience/GravityInversion/Task.md) | `subsurface_gravity` | P2 | 选择测线、位置和高度；保留等效密度分布，优先验证未见测线而非唯一几何标签。 |
| [RadiativeTransferFit](../benchmarks/EarthScience/RadiativeTransferFit/Task.md) | `thermal_radiation` | P2 | 选择通道、角度与采样，检验大气层/云解释；可共享辐射工具，不与透射谱直接视作同一世界。 |
| [IMUBiasCalibration](../benchmarks/Engineering/IMUBiasCalibration/Task.md) | `inertial_sensor_lab` | P2 | 选择姿态和温度、安排标准测量；开放传感器校准与非仿射失效研究。 |
| [QuartzCrystalMicrobalanceLab](../benchmarks/Engineering/QuartzCrystalMicrobalanceLab/Task.md) | `deposition_qcm` | P2 | 固定IQ数据包改成可请求校准、扫频和沉积操作；需新样品/仪器状态及测量调度。 |
| [ActiveNoiseSpectroscopy](../benchmarks/Physics/ActiveNoiseSpectroscopy/Task.md) | `quantum_noise` | P2 | 保留有限shots、脉冲和噪声统计；新量子观测协议，不能用经典spin_echo直接替代。 |
| [HamiltonianLearning](../benchmarks/Physics/HamiltonianLearning/Task.md) | `quantum_dynamics` | P2 | 选择制备、演化时间和可观测量；新增量子动力学核与对称性等价处理。 |
| [RadialVelocityPlanets](../benchmarks/Physics/RadialVelocityPlanets/Task.md) | `radial_velocity_observatory` | P2 | 选择观测时刻与活动辅助量，检验别名/行星解释对未来时刻的预测；观测型环境。 |

### 独立研究轨（6 项）

| 旧任务 | 目标方向 | 优先级 | 改造要点 |
|---|---|---|---|
| [CacheReplacementPolicyID](../benchmarks/ComputerScience/CacheReplacementPolicyID/Task.md) | `cache_lab` | P3 | 保留可查询状态机，允许寻找新行为与等价反例；归为计算系统研究。 |
| [SequenceLawRecovery](../benchmarks/Mathematics/SequenceLawRecovery/Task.md) | `sequence_lab` | P3 | 增加按需查询及可验证猜想；有限前缀不能证明唯一递推，独立数学研究轨。 |
| [GraphFromDistances](../benchmarks/ComputerScience/GraphFromDistances/Task.md) | `network_probe_lab` | P3 | 开放距离查询和可实现的链路观测，报告等价图；独立离散系统轨。 |
| [BlackBoxGroupIdentification](../benchmarks/Mathematics/BlackBoxGroupIdentification/Task.md) † | `algebra_lab` | P3 | 查询乘法、提出并验证代数性质与反例；不继续要求目录编号匹配。 |
| [ProspectiveMetaAnalysis](../benchmarks/Biology/ProspectiveMetaAnalysis/Task.md) | `evidence_synthesis_lab` | P3 | 模拟研究注册、重复报告、偏差与新增确认；标明研究的是证据过程，独立证据研究轨。 |
| [SparseVectorAudit](../benchmarks/ComputerScience/SparseVectorAudit/Task.md) | `privacy_audit_lab` | P3 | 保留邻接输入、重复运行和可复验违反见证；独立算法审计轨。 |

† 标记的 6 个旧任务已有饱和、捷径或待复核限制，见 [eligibility policy](../docs/discovery_eligibility.md)。转成新 env 不自动解除原限制，也不自动继承旧任务的难度或科学认证。

## 8. 旧独立科学环境路线

| 现有原型 | 本次处理方向 |
|---|---|
| CausalTransportDiscovery | 复用公开观测、桥接采样、部分识别与新群体确认；候选目标 causal_transport。强固定设计已很强，不假设自适应优势。 |
| EnzymeRecoveryDesign | enzyme_recovery 的优先参考；保留加载、洗脱、恢复和光学干扰。已有固定设计高表现，先盘点剩余研究空间。 |
| SurvivorshipAuditDesign | 保留为历史控制，帮助检测只换接口未增加研究要求的伪扩展。 |
| EnzymeMechanismDiscovery | 保留为流程控制；已有固定设计恢复全部机制的结果，不作为新难环境直接发布。 |
| MeasurementAudit | 复用证据封存与后续确认的流程；它没有隐藏机制，不包装成一个新的物理世界。 |

本计划不依赖重新检索文献或推断现实科学有效性。证据来源为仓库现有任务契约、环境合同与开发说明；实施时如引入新物理核或依赖，再核对对应原始模型与官方实现。

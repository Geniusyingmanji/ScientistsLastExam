# 第二批生物题实现与验证（2026-09-05）

> 2026-09-06 更新：PR #13 已同步 upstream `2cbf72b`，当前清单为 86 题。
> 以下为之前的历史实现记录；本轮评审处理见 `biology_pr13_review_2026-09-06.md`。

> PR 范围调整：按用户要求，本分支新增的九份全局审计快照仅在本地保留，
> 不纳入任务 PR；审计脚本引用恢复为上游版本。下述全量通过结果是移除快照前的
> 历史验证记录，不表示上游旧快照已覆盖本分支新增任务。多人提交任务合并后，
> 需基于最终任务清单统一运行 `scripts/refresh_global_evidence.py --commit`，
> 再检查依赖全局证据的测试。本次不修改或绕过审计门槛。

五题按单倍型、保护区、单分子动力学、同位素通量、距离几何的顺序完成实现。
均注册为 candidate：当前总计 73 题，5 certified、68 candidate。
实现完成不表示博士难度、外部领域评审或正式准入已经完成。

| 任务 | 首版实现 | 沙箱参考开发分 | 已知范围限制 |
|---|---|---:|---|
| Genomics/DiploidHaplotypeAssembly | 多位点读段的等权同源体混合似然、独立区块相位对称 | 1.000000 | 200–320 位点；八起点未改善参考，成熟算法饱和风险高 |
| ConservationBiology/RobustReserveNetworkDesign | 40–52 地块、四物种、三情景动态占域、成本硬约束 | 1.000000 | 现象学离散模型，尚无真实保护案例或生态专家审定 |
| Biophysics/SingleMoleculeKinetics | 二状态 CTMC、瞬时 Poisson 发射、收费轨迹、Baum–Welch | 0.972586 | 简化二状态模型，无漂白、群体层次或积分曝光 |
| MetabolicEngineering/IsotopeFluxIdentifiability | 单碳缩合、全二碳同位素体传播、净通量与总交换辨识 | 0.989045 | 小型自建网络；未实现通用 EMU、INCA 对照或完整 profile likelihood |
| StructuralBiology/ProteinDistanceGeometry | 稀疏距离、键角、排斥、局部有向体积约束、MDS+优化 | 1.000000 | 合成 C-alpha 粗粒化主链，不是全原子构象或真实蛋白折叠 |

各题包括 Task.md、TASK_CARD.yaml、零分合法 baseline、严格 oracle、独立可运行的
input-only reference、frontier_eval 沙箱入口与七节 known_best.md。未引入新运行依赖，
仅使用现有 NumPy/SciPy。参考程序不含世界生成器、真值表或 evaluator 导入。

## 科学与计分检查

- 单倍型似然与小规模直接枚举一致；全局/区块互补、位点置换、读段顺序不改变目标。
  256 个随机相位最好 0.106985；逐位多数投票 0.138633；八起点相比参考的原始增益为零。
- 保护区递推与独立标量实现一致；单地块零扩散有解析解；无初始源不能自发出现占域。
  忽略扩散得到的设计真实效用仅为参考的 0.630596，单情景设计为 0.674500；
  256 个随机可行设计最好 0.802594。动态传播和稳健情景都有实测贡献。
- 单分子二状态转移与解析矩阵相符；状态置换不影响机制分。
  等发射隐态与静态单态观测分布相同，统一允许拒答，不要求猜出不可判的理由标签。
- 同位素全四状态模型与独立三质量峰模型在 2e-8 容差内一致；稳态化学计量守恒。
  两条反向支路映射相同，因此只要求总交换；零净流入时交换不可辨识，允许拒答。
- 距离几何的独立可行见证公开损失为零；刚体旋转/平移不变，镜像、压缩和坍塌受罚。
  修正了相对很差直线基线的线性归一化，改用逆损失质量；完全坍塌仅得 0.001207。
- 每题至少十二种畸形输出检查；两道发现题预算超支即使被候选捕获仍失效；
  全拒答及无证据全盘宣称不会获得发现分；机制、假发现、覆盖、拒答和 Brier 指标分列。

## 新颖性核对

本轮实际阅读 [Frontier-Eng 论文 v1 附录 A 的 HTML 正文](https://arxiv.org/html/2604.12290v1#A1)
的五类 47 项目录及目标/评分说明，不再仅依赖本仓库历史笔记。
另核对 [TASK_DETAILS.md 固定提交](https://github.com/EinsiaLab/Frontier-Engineering/blob/e3fa29c193356af2ce1ec8b3d23ab1a2e2410071/TASK_DETAILS.md)，
提交 e3fa29c193356af2ce1ec8b3d23ab1a2e2410071；文件 SHA-256
11be782992273d8131b077c6d7f30e78c0389e8db1d2af6494388621b043bbf5。
前四题未发现同一产物与 oracle 的条目。论文中的 predict_modality 是 RNA 到 ADT 预测；
仓库另有构象组合选择，和第五题从约束生成坐标不同，但第五题保留较高领域重叠风险，
需要维护者裁定。这里记录的是内部对照判断，不是外部新颖性认证。

文献与模型约化的关系、稳定 DOI 及未分发外部代码/数据的说明见各题契约和任务卡。

## 验证证据

- 五个 `scripts/check_task_contribution.py --task <id>` 完整 Linux 沙箱检查通过。
- 五个 standalone reference 均通过真实候选沙箱，valid=1；约 1.1、8.0、2.1、4.6、54.0 秒。
- 专用模型/任务卡/分类/目录检查：94 passed。全回归分两个互斥分组覆盖全部 141 个测试文件：
  核心组 728 passed、36 skipped（536.06 秒），报告依赖组 312 passed、12 skipped（580.92 秒）；
  合计 **1040 passed、48 skipped、0 failed**，覆盖 1088 个收集测试。
- 五个 frontier_eval/run_eval.py 从容器 /tmp 启动也全部通过，baseline valid=1、score=0。
- 全局证据刷新为 certification v76、secure baseline v59、maturity v17，均 passed、
  trusted_clean_revision；73/73 合法、确定、fail closed，基础设施失败 0，成熟度 issues=[]。
  实现提交为 52252c7；证据更新提交为 5cc48c4、cbc4b68。
- 完整内部数值见 [本地测量](biology_wave2_measurements_2026-09-05.json) 与
  [沙箱参考测量](biology_wave2_secure_references_2026-09-05.json)。宿主与容器拟合结果允许浮点
  平台末位差异；冻结容器内的重复 baseline 全 payload 一致。

## 未达到的正式准入条件

尚未完成前沿模型 draw、强经典求解器比较、广泛自适应策略捷径扫描、两小时搜索、
配对开环对照、服务器私有实例和外部领域评审。部分参考接近饱和，不能作为专家难度证据。
原提案的 Hi-C、群体 FRET、通用 EMU 与全原子几何没有在本轮暗中简化后冒充实现；
以上表格和每题题面明确标出了实际模型。实现可运行和可审阅，成熟度仍停留在 candidate。

## 集成期间的补充探针

在包内 known_best.md 与任务卡所记录的初测之后，又完成了三组基础扫描：
单分子题 16×16 固定速率猜测、同位素题 16×16 固定通量猜测，最高发现分均为零；
距离几何题 8×8×4 规则螺旋模板最高 0.359027，仅 MDS、不做约束优化为 0.060333。
这些是无自适应观测的窄范围探针，不代表强经典方法或带观测的捷径已被排除。
本补充更新了初测材料中尚无参数网格扫描的状态；候选成熟度及未完成的外部验证不变。
原始数值见 [补充探针](biology_wave2_additional_probes_2026-09-05.json)，
可用 `python .research/biology_wave2_additional_probes.py --output /tmp/wave2-probes.json` 重算。

本地保留的全局报告：任务审计 v76、沙箱基线 v59、成熟度 v17
（均为 2026-09-05 快照，已从本次 PR 差异中移除）。

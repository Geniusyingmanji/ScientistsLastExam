# 新增 10 题第二轮本地难度校准（2026-09-05）

本文件是 `tmp/hardening/IMPLEMENTATION.md` 所述第一轮加固之后的第二轮记录。四个任务的 `references/known_best.md` 版本注记指向本文件。全部为 macOS 本地调试结果，**不构成正式准入证据**；10 题仍为 candidate。

范围：古气候年代同化、BSM1 曝气控制、火山形变机制反演、供水管网泵调度四题的机制修改与捷径复测；其余六题仅复跑诊断，未改动。基线修订 8032e97 之上的本地工作区状态。

## 修改内容

| 任务 | 第二轮修改 | 意图 |
|---|---|---|
| ChronologyAssimilation | 真实年代模型改为分段线性、正变化率的 age-depth 映射（难度档 6/9/12 段）；提交契约从每记录单一偏移改为整条 8×36 单调年代曲线（旧偏移提交仍合法但按曲线评估）；参考改用保形 PCHIP 插值 5 个稀疏定年并加 35 年本征定年不确定度 | 单偏移模型不再是正确机制；参考不再隐含"每记录一个常数"这一被公开的简化 |
| BSM1AerationControl | 加入间歇性浓缩氨氮回流（3 次随机冲击，与日流量解耦）、分时电价（16–21 时 4 倍）、公开的曝气机降额窗口（可用率 0.35）；评分改流量加权出水、氨氮上十分位罚项、分时计价能耗；新增公开观测键 `electricity_price_ratio`、`aeration_availability` | 常数/开环控制不再能同时压住冲击负荷与电价；控制器必须读观测并按可用率折算指令 |
| DeformationMechanismInference | 观测加入共享三分量参考框架平移（±0.08 m）与垂直面倾斜（±0.12 m）冗余参数并公开其界；参考用变量投影（QR 基）消除冗余参数；去掉参考中一次多余的噪声测量调用 | 不处理框架误差的朴素拟合被显著惩罚；大地测量惯行的冗余参数消除成为必要能力 |
| ResilientPumpScheduling | 泵速契约改为 0 或 [0.65, 1] 的稳定运行区间、最短运行 2 小时、开启有辅助功率与启动代价；参考重写为承诺掩码块交换 + 凸调度子问题搜索 | 从纯连续调度变为真正的混合整数启停承诺问题；旧坐标搜索直接违反契约 |

## 捷径与历史方法复测（本地）

归一化分数不可跨 oracle 版本比较；本表只用于确认"简单策略低于参考线"这一准入下限。

| 任务 | 检查项 | development | heldout | 参考 |
|---|---|---:|---:|---:|
| ChronologyAssimilation | 旧单偏移方法（按曲线评估） | 0（invalid，可行性 0.83） | — | 0.736 |
| ChronologyAssimilation | 年代曲线坍缩伪候选 | 0.520 | —（留出 age MAE 90.3 年） | 0.736 |
| BSM1AerationControl | 528 组常数扫描最优（kla=1.0, recycle=1.0） | 0.896 | 0.811 | 1.0 |
| DeformationMechanismInference | 旧参考（不处理框架冗余） | 0.131 | — | 0.958 |
| ResilientPumpScheduling | 旧坐标搜索方法 | 0（invalid，违反新契约） | 0.5 可行率 | 1.0 |
| ResilientPumpScheduling | 参考去掉承诺搜索 | 0.569 | 0.494 | 1.0 |
| ActiveFullWaveformInversion | 旧固定透镜方法 | 0.250 | — | 0.357 |
| GroundwaterRemediationDesign | 源点单井捷径 | 0.031 | 0.051 | 1.0 |
| IceObservationNetworkDesign | 旧未归一化贪心 | 0.662 | 0.642 | 1.0 |
| CompositeLaminateStacking | 旧膜内模型搜索 | 0（heldout 0.599） | 0.599 | 1.0 |
| WakeAwareFarmCoDesign | 旧布局/偏航方法 | 0.491 | 0.494 | 1.0 |
| BOPTESTSupervisoryControl | 48 组温控/通风系数扫描 | 无可行方案 | — | 1.0 |
| BOPTESTSupervisoryControl | 去掉占用预测 | 0.566 | -0.449 | 1.0 |

古气候难度阶梯（参考 combined_score）：档 1 = 0.736，档 2 = 0.721，档 3 = 0.724。火山形变：0.958 / 0.957 / 0.955。

## 仍未关闭的问题

- **DeformationMechanismInference 参考接近上限**（0.958）：单源非线性最小二乘加变量投影已几乎解满当前实例族。需要扩展有科学依据的实例族（多源、流变、更密观测权衡）并重新标定，才能声称区分度。
- **BSM1 固定控制仍然很强**（0.896/0.811）：已低于参考但余量小；上十分位氨氮罚项与冲击幅度是下一处校准旋钮。
- **泵调度**参考的承诺搜索是可行启发式，不是全局最优性证书；`without_commitment_search` 0.569 说明承诺搜索贡献显著，但单泵单罐保真度仍有限。
- 逐能力消融、低维捷径全族扫描、前沿模型首提案标定、Linux 沙箱干净重放与全局证据刷新（`scripts/refresh_global_evidence.py`，需基准主机 bubblewrap）均未完成。

## 复现

```
python -m pytest tests/test_new_task_hardening.py -q
python scripts/diagnose_new_task_hardening.py --sweeps --output tmp/hardening/diagnostics.json
```

工作脚本与原始 JSON 在 `tmp/difficulty_v2/`（未入库）：`all_ten.json`（十题全量诊断与捷径对比）、`ladder.json`（难度阶梯）、`bsm_sweep.json`（常数扫描）、`edit_*.py`（机制修改脚本）。

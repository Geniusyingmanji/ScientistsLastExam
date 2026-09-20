# Discovery / optimization 分支切分验证记录

核验日期：2026-09-20。证据范围为 **测试执行与工程协议**，不包含新的模型能力评估、科学发现结论或题目难度结论。

两分支的历史全量运行均有失败与跳过。后续定向复验中，原失败测试均出现了通过记录；这不等于当前提交完成了一次全量通过运行，也不补足历史数据缺失导致的跳过。本报告保留各次运行的原始分母，不合并通过数。

## 原始运行与定向复验

所有 JUnit 均来自 g450，记录的主机名为 `t2vg-a100-G4-50`。下表时间为 JUnit 记录的 UTC 起始时间；“执行”包含通过和失败，不包含跳过。各次运行均为 0 error。

| 运行 | 运行记录关联源码 | UTC 起始时间 | 通过 | 失败 | 跳过 | 执行 / 收集 |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| main 全量 | `7c4ea55d` | 09-19 02:18:12 | 1744 | 6 | 18 | 1750 / 1768 |
| optimization 全量 | `e6134fb9` | 09-19 01:16:30 | 1290 | 1 | 37 | 1291 / 1328 |
| optimization NMR 运行时复验 | `e6134fb9` | 09-19 02:23:07 | 1 | 0 | 0 | 1 / 1 |
| main 恢复审计第一次复验 | `d3be73d9` | 09-20 07:49:52 | 1 | 2 | 0 | 3 / 3 |
| main NMR / Astropy 运行时复验 | `d3be73d9` | 09-20 07:49:52 | 12 | 0 | 0 | 12 / 12 |
| main 恢复审计修复后复验 | `d555e237` | 09-20 07:52:59 | 3 | 0 | 0 | 3 / 3 |

**源码关联局限：**上述 JUnit 未包含 commit、工作树状态或运行环境指纹的 properties。源码栏来自当时运行记录与工作树操作记录，不是 JUnit 自身的密码学绑定；文件名也不能独立证明源码版本。核验时 main 工作树已在 `d555e23742dbe662c28db465d9972eaab64ef6f4`，不能把这个当前 HEAD 倒填为历史全量运行的源码。SHA-256 仅用于定位和检查本次读取的原始文件字节。

main 运行时复验使用私有环境 `/var/tmp/sle-split-runtime-final-20260920`。核验时该环境为 Python 3.8.10、NumPy 1.24.4、SciPy 1.10.1、Astropy 5.2.2、nmrsim 0.6.0、Numba 0.58.1。这是环境当前状态的只读核对，不能替代运行时冻结的依赖清单。

## 原失败如何对应复验

| 原失败 | 原因 / 修复 | 复验边界 |
| --- | --- | --- |
| main：恢复审计 `test_all_process_fault_scenarios_pass`、`test_search_crashes_resume_without_another_evaluator_call` | 审计仍引用已移至 optimization 的 `Chemistry/LennardJonesCluster`；`d3be73d9` 改用独立协议 fixture。第一次复验仍有 2 项失败，fixture 缺少 `constraints.txt`；`d555e237` 补齐该契约文件。 | 最后恢复审计 3 / 3 通过，包含原 2 个失败测试及请求/回执边界检查。fixture 不评估科学能力。 |
| main 与 optimization：`test_serial_nmrsim_and_jit_work_while_tbb_backend_is_masked` | 候选运行时装载 nmrsim 0.6.0.post1，而约定版本为 0.6.0；使用精确版本重新验证，保留版本不匹配时拒绝运行的检查。 | main 的 12 项运行时复验包含该测试；optimization 单独 1 / 1 通过。 |
| main：`test_baseline_can_import_the_pinned_astropy_in_the_candidate_sandbox`、`test_candidate_gets_the_trusted_abi_without_the_oracle_virtualenv`、`test_oracle_setup_checks_the_pinned_astropy_version` | 历史运行分别报告受信评估器基础设施失败和 oracle 环境检查失败；在精确依赖环境中复验。原 JUnit 仅给出上述故障信息，不能单凭它断言全部失败都由同一个依赖造成。 | 12 项运行时复验包含原 3 项，均通过；并执行缺包、版本不匹配、依赖 pin 和候选 sandbox 相关检查。 |

原全量结果和中间失败结果仍保留。定向复验只能支持其实际执行测试的结论；不改变原全量记录的失败状态。

## Required admission 检查

使用仓库 `scripts/summarize_test_coverage.py` 分别解析原始 JUnit，按各分支自己的 `.github/required_admission_tests.json` 查验，不取两个分支列表的交集。

| 全量运行 | Required 总数 | 通过 | 失败 | 跳过 / 未收集 |
| --- | ---: | ---: | ---: | ---: |
| main | 77 | 76 | 1 | 0 / 0 |
| optimization | 27 | 26 | 1 | 0 / 0 |

两者唯一未通过的 required 项均为上述 NMR 运行时测试，后续各自定向通过。原全量报告仍为 `passed=false`、`coverage_complete=false`。定向报告中的 `coverage_complete=true` 仅表示其 1、3 或 12 项收集范围内没有跳过或失败；这些定向 summary 未传入完整 required 列表，`required_tests` 为空，**不代表一次完整 admission gate 通过**。

本次核对的列表与汇总器 SHA-256：

| 文件 | SHA-256 |
| --- | --- |
| main required 列表（`7c4ea55d` 与核验时 HEAD 相同） | `133c4b56285c0c0180696a666ecc09d977784b936200a389ad71b5708c08de0f` |
| optimization required 列表 | `8f6a9582dde7e8e88b7a6d913f8500400c430284f3ff83c87e7b97a9e1fb8034` |
| main `scripts/summarize_test_coverage.py` | `7caba458753b4bf215aa892e6cf324e1775f1178d8707ebf6ebc7d3096d7dd66` |

## 跳过项：未验证的内容

main 的 18 项全部因原始模型运行、轨迹或审计输入未在当前 checkout 中提供而跳过，不是 Linux sandbox 检查通过。按测试文件汇总：

| 测试文件（`tests/` 下） | 跳过数 | 缺少的输入 |
| --- | ---: | --- |
| `test_demographic_sfs_analysis.py` | 4 | DemographicSFS 原始轨迹 |
| `test_force_field_hypothesis_analysis.py` | 1 | ForceFieldHypothesis 原始运行 |
| `test_prospective_meta_analysis_analysis.py` | 6 | ProspectiveMetaAnalysis 私有模型运行目录 |
| `test_rankine_analysis.py` | 1 | 历史 RankineCycleOpt 轨迹 |
| `test_seismic_wave_analysis.py` | 4 | SeismicWaveInversion 原始轨迹 |
| `test_sentinel_smoke_audit.py` | 1 | sentinel 原始运行 |
| `test_signed_decision_smoke_audit.py` | 1 | signed-decision 原始运行 |
| **总计** | **18** | |

optimization 的 37 项中，32 项缺少历史运行/轨迹，5 项缺少固定上游数据文件：

| 测试文件（`tests/` 下） | 跳过数 | 缺少的输入 |
| --- | ---: | --- |
| `test_alloy_hardness_analysis.py` | 6 | AlloyHardnessOptimization 原始轨迹 |
| `test_alloy_hardness_optimization.py` | 3 | 固定 MPEA 上游 CSV |
| `test_alloy_hash_order_migration.py` | 1 | AlloyHardnessOptimization 原始轨迹 |
| `test_calorimeter_analysis.py` | 1 | 被忽略的原始轨迹 |
| `test_diffraction_grating_analysis.py` | 6 | DiffractionGratingDesign 原始轨迹 |
| `test_electrolyte_conductivity_analysis.py` | 4 | ElectrolyteConductivityDesign 原始轨迹 |
| `test_electrolyte_conductivity_design.py` | 1 | 固定 Zenodo 上游 CSV |
| `test_mosfet_analysis.py` | 1 | MOSFETDoping 原始轨迹 |
| `test_protein_stability_analysis.py` | 4 | ProteinStabilityDesign 原始轨迹 |
| `test_protein_stability_design.py` | 1 | 固定 ProteinGym 上游源文件 |
| `test_rankine_analysis.py` | 1 | RankineCycleOpt 原始轨迹 |
| `test_rans_analysis.py` | 1 | RANSCalibration 原始轨迹 |
| `test_room_acoustics_analysis.py` | 1 | RoomImpulseResponse 原始轨迹 |
| `test_seismic_wave_analysis.py` | 4 | 历史 SeismicWaveInversion 原始轨迹 |
| `test_sentinel_smoke_audit.py` | 1 | sentinel 原始运行 |
| `test_signed_decision_smoke_audit.py` | 1 | signed-decision 原始运行 |
| **总计** | **37** | |

历史分析涉及已移到另一分支的任务，不使该任务重新成为当前分支的可运行任务。这些记录未被删除或改写以制造通过结果。

## 原始证据定位

以下路径均在 g450 的 `/var/tmp/` 下。原始 JUnit / 日志只读核验，本轮没有重新执行全量测试。

| 原始文件名 | SHA-256 |
| --- | --- |
| `sle-split-main-20260919.xml` | `fac292693c6f1c140448d72afce0c00a4b4195ee71fa8b9c9da977a28fdaa729` |
| `sle-split-optimization-20260919.xml` | `eb2334e66bfd121794c20625b2a341ee64d37cf368b42b8305a2ff8fc3724923` |
| `sle-split-optimization-nmrsim-runtime-20260919.xml` | `7595b152d3f266e1f79a2438edde5309ed3b44ddbb0c764b3b48fe4054fb6ee4` |
| `sle-split-main-recovery-d3be-20260920.xml` | `85dd69c93eed73711807a63bf2143b45cec5b10c622f422c77a6ee20145ebcd6` |
| `sle-split-main-runtime-d3be-20260920.xml` | `1fa85605ccc9308d0840040b7a455079e32e0af19bec4df52d68f0d030e443b8` |
| `sle-split-main-recovery-d555-20260920.xml` | `159d932f83064f11362b054d571588535ce7c78dce5959f926925736e5213f55` |
| `sle-split-main-20260919.log` | `aa162ad7a7a7dd48e4dbf3b3f8a53a567c4b2e9e71d5dde0cdb4b6c8476a0798` |
| `sle-split-optimization-20260919.log` | `d82ced31d2d6d6c1a1db2286fa8e2636a9a2fef81280501121326e59629dbda5` |

已存在的派生 coverage 文件也单独保留，不回写原始 JUnit：

| 派生文件名 | SHA-256 |
| --- | --- |
| `sle-split-main-coverage-20260920.json` | `1374863d293ba06f247154d829da2474bd2bf047d5e5ac8709de1ebe5bd921b3` |
| `sle-split-main-recovery-coverage-20260920.json` | `79b985c25bfeda870e5bddbde8888df82e2dc3c554220472f1292bfc1406ba8b` |
| `sle-split-main-runtime-coverage-20260920.json` | `987bad6d9224f6586873b3a61690f71d59a7351fe417fe3229bb070c5fde2157` |
| `sle-split-optimization-nmrsim-coverage-20260920.json` | `ffa7c06c12794f390c8b564c9278ea51248e9edeee9180a3995ea65e6e86685c` |

本次独立解析用的原始 JUnit 副本及派生 JSON 位于本地非发布目录 `scratch/discovery-split-validation-20260920/`。未将这些工程测试结果解释为 GPT-5.6 的发现率、科学质量、任务难度或无 GT 发现有效性。

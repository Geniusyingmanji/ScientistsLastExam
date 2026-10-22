# SLE 当前文档

- [整体 Plan](plan.html)：信息条件 × 科研成果矩阵；纵轴为信息较充分、信息部分受限、信息强受限，横轴为现象表征、规律建构、知识拓展。另含分档依据、评价说明、通用研究 Query 模板及交付规范。
- [微生态案例](case_study.html)：机制方程、三菌研究 Query、评测接口与模型可见回复。

[V1 结果](reports/v1_results.html)保留十二环境、双模型的历史配对与评分。Plan 与 Case Study 两个主页面直接生成到 `docs/`；`reports/` 中的同名页面保留跳转及 URL 片段。

旧进度页保存在[历史进度快照](archive/reports/progress-20261022.html)，不再作为当前页面维护。`progress.html` 与 `reports/` 下的旧进度入口跳转到该快照，保留查询参数和 URL 片段。

构建命令：`python3 scripts/docs/build_reports.py`。HTML 源模板、Plan 样式与 Query 文本位于 `scripts/docs/templates/`；公开汇总和选定回复位于 `reports/data/`。环境分层与 Query 是后续新任务的设计方案，难度待校准；历史输入与成绩保持冻结。构建不再生成或更新历史进度快照。

`archive/` 保留科学协议、评测数据和审计证据；旧展示版本可通过 Git 历史追溯。`archive/reports/overview.html` 是 V1 页面的构建模板，`render_model_comparison.py` 由比较计算测试使用。私有原始轨迹不随报告发布。

# SLE 当前文档

- [整体 Plan](plan.html)：三层能力与独立过程评估、通用研究 Query 模板及交付规范。
- [当前进度](progress.html)：最新已归档结果、验证范围与剩余工作。
- [微生态案例](case_study.html)：机制方程、三菌研究 Query、评测接口与模型可见回复。

[V1 结果](reports/v1_results.html)保留十二环境、双模型的历史配对与评分。三个主页面直接生成到 `docs/`；`reports/` 中的同名页面和旧入口保留跳转及 URL 片段。

构建命令：`python3 scripts/docs/build_reports.py`。HTML 源模板与 Query 文本位于 `scripts/docs/templates/`；公开汇总和选定回复位于 `reports/data/`。Query 是后续新任务的设计稿，历史输入与成绩保持冻结。

`archive/` 保留科学协议、评测数据和审计证据；旧展示版本可通过 Git 历史追溯。`archive/reports/overview.html` 是 V1 页面的构建模板，`render_model_comparison.py` 由比较计算测试使用。私有原始轨迹不随报告发布。

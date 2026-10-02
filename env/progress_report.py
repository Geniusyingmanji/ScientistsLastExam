"""Build a self-contained, sanitized multi-cohort scientific progress report.

Raw episodes stay in the operator directory. This exporter deliberately selects
aggregate fields and never copies manifests, private targets or model traces.
Use --cohort formal=/absolute/cohort, --cohort development=/absolute/cohort,
--notes /absolute/curated-notes.json and --output /absolute/public-directory.
"""
import argparse
import base64
import binascii
import datetime
import html
import json
from pathlib import Path

from .reporting import collect_report


NAMES = {"microecology": "微生态反馈", "coupled_oscillators": "耦合振子",
         "reaction_kinetics": "反应动力学", "heat_transport": "热输运",
         "gene_regulation": "基因调控", "ising_spin": "平衡自旋",
         "hysteresis_material": "材料滞回"}

EVIDENCE_COLUMNS = (("quantitative_model", "定量模型"),
                    ("prospective_test", "前瞻检验"),
                    ("meaningful_rival", "实质竞争解释"),
                    ("changed_regime_transfer", "跨条件迁移"),
                    ("empirical_boundary", "经验适用边界"),
                    ("uncertainty_and_negative_results", "不确定性与负结果"))
EVIDENCE_LABELS = {"supported": "支持", "partial": "部分支持",
                   "not_demonstrated": "未展示", "unassessable": "无法判断"}


def _evidence_matrix(sample):
    """Display curated manual assessments; never infer grades or pooled rates."""
    if sample is None:
        return ""
    if (type(sample) is not dict or set(sample) != {"selection", "review_scope", "rows"}
            or any(type(sample[key]) is not str or not sample[key].strip()
                   for key in ("selection", "review_scope"))
            or type(sample["rows"]) is not list or not 1 <= len(sample["rows"]) <= 30):
        raise ValueError("invalid curated evidence sample")
    escape = lambda value: html.escape(value, quote=True)
    rows = []
    for row in sample["rows"]:
        if (type(row) is not dict or set(row) != {"case", "assessments", "limitation"}
                or any(type(row[key]) is not str or not row[key].strip()
                       for key in ("case", "limitation"))
                or type(row["assessments"]) is not dict
                or set(row["assessments"]) != {key for key, _ in EVIDENCE_COLUMNS}
                or any(type(value) is not str or value not in EVIDENCE_LABELS
                       for value in row["assessments"].values())):
            raise ValueError("invalid curated manual evidence row")
        cells = "".join('<td>%s</td>' % EVIDENCE_LABELS[row["assessments"][key]]
                        for key, _ in EVIDENCE_COLUMNS)
        rows.append('<tr><th>%s</th>%s<td>%s</td></tr>' %
                    (escape(row["case"]), cells, escape(row["limitation"])))
    header = "".join('<th>%s</th>' % label for _, label in EVIDENCE_COLUMNS)
    return ('<details><summary>样例证据逐维复核（%d 例）</summary>'
            '<p class="muted">%s</p><p class="caption">%s</p>'
            '<div class="table-wrap"><table class="evidence-table"><thead><tr><th>样例</th>%s'
            '<th>主要限制</th></tr></thead><tbody>%s</tbody></table></div>'
            '<p class="caption">这些是人工证据判断；引用与顺序校验不认证科学结论。'
            '未展示不等于现象不存在。各维度不相加，不生成深度等级或发现率。</p></details>' %
            (len(rows), escape(sample["selection"]), escape(sample["review_scope"]),
             header, "".join(rows)))


def _number(value, digits=1):
    return "—" if value is None else ("%.*f" % (digits, value))


def _scientific_figure(figure):
    """Embed one operator-curated PNG; no paths, URLs or active SVG content."""
    if figure is None:
        return ""
    if (type(figure) is not dict or set(figure) != {"title", "caption", "alt", "png_base64"}
            or any(type(figure[key]) is not str or not 1 <= len(figure[key]) <= 4096
                   for key in ("title", "caption", "alt"))
            or type(figure["png_base64"]) is not str
            or not 1 <= len(figure["png_base64"]) <= 2000000):
        raise ValueError("invalid curated scientific figure")
    try:
        png = base64.b64decode(figure["png_base64"], validate=True)
    except (ValueError, binascii.Error):
        raise ValueError("invalid curated PNG encoding") from None
    if (len(png) < 33 or png[:16] != b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
            or not 1 <= int.from_bytes(png[16:20], "big") <= 8192
            or not 1 <= int.from_bytes(png[20:24], "big") <= 8192):
        raise ValueError("invalid curated PNG header")
    escape = lambda value: html.escape(value, quote=True)
    return ('<details class="reference-figure"><summary>%s</summary><figure>'
            '<img style="display:block;width:100%%;height:auto" alt="%s" '
            'src="data:image/png;base64,%s"><figcaption class="caption">%s</figcaption>'
            '</figure></details>' % (escape(figure["title"]), escape(figure["alt"]),
                                   escape(figure["png_base64"]), escape(figure["caption"])))


def _rate(value):
    if not value or value.get("rate") is None:
        return "—"
    return "%d/%d · %.1f%%" % (value["numerator"], value["denominator"], value["rate"] * 100)


def _interval(value):
    return "样本不足" if value is None else "[%s, %s]" % (_number(value[0]), _number(value[1]))


def export_summary(directory, role):
    """Allowlist aggregate evidence; no raw/private content is exported."""
    summary, _ = collect_report(Path(directory))
    keys = ("cohort", "planned_runs", "started_runs", "settled_runs", "running_runs",
            "healthy_runs", "infrastructure_failures", "macro_score", "macro_bootstrap_95",
            "score_status", "model_completion", "verified_effect_rate", "end_to_end_completion",
            "by_environment", "known_response_usage_lower_bound", "cost_usd", "cost_note",
            "weights", "depth_status", "source_sha256", "score_protocol", "task_profile",
            "public_limits", "decoding", "trace_diagnostics", "analysis_protocol", "presentation_profile")
    return dict({key: summary.get(key) for key in keys}, role=role)


def build_report(cohorts, notes, output):
    """notes is operator-curated public prose, not an unfiltered review trace."""
    evidence_matrix = _evidence_matrix(notes.get("evidence_sample"))
    scientific_figure = _scientific_figure(notes.get("scientific_figure"))
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    data = {"schema": "sle-public-progress-0.1", "generated_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "cohorts": [export_summary(path, role) for role, path in cohorts], "notes": notes,
            "privacy": "Aggregate metrics and explicitly curated notes only; private seeds, targets and raw traces are excluded."}
    (output / "data.json").write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    escape = lambda value: html.escape(str(value), quote=True)
    formal = next((item for item in data["cohorts"] if item["role"] == "formal"), None)
    headline = notes.get("headline", "先验证评测是否测到了科学发现")
    cards = []
    if formal:
        cards = [("GPT-5.6 · SLE-Pilot", _number(formal["macro_score"]) + " / 100", str(len(formal["by_environment"])) + " 环境等权；95% bootstrap " + _interval(formal["macro_bootstrap_95"])),
                 ("模型完成率", _rate(formal["model_completion"]), "有效预测器 / 基础设施健康的已结束运行"),
                 ("主张复验通过率", _rate(formal["verified_effect_rate"]), "至少一个符合数值复验条件的非零效应；不是机制发现率"),
                 ("端到端完成率", _rate(formal["end_to_end_completion"]), "包含基础设施失败和正在运行的实例")]
    card_html = "".join('<article class="metric"><label>%s</label><strong>%s</strong><small>%s</small></article>' % tuple(escape(x) for x in card) for card in cards)
    table_sections = []
    role_names = {"formal": "正式批次", "development": "开发批次", "expansion": "扩展批次"}
    for cohort in data["cohorts"]:
        rows = []
        for name, row in cohort["by_environment"].items():
            errors = row.get("prediction_normalized_rmse", {})
            error_text = " / ".join(_number((errors.get(kind) or {}).get("mean"), 4) for kind in ("conditions", "interventions"))
            components = row.get("mean_subscores", {})
            rows.append('<tr><th>%s</th><td class="score">%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>' %
                        (escape(NAMES.get(name, name)), _number(row["mean_score"]), _rate(row["completion"]),
                         " / ".join(_number(components.get(kind)) for kind in ("conditions", "interventions", "claims")),
                         error_text, " · ".join(_number(score) for score in row["scores"])))
        limit = cohort.get("public_limits") or {}
        label = role_names.get(cohort["role"], cohort["role"])
        warning = "开发批次使用旧主张规则，不与正式成绩合并。" if cohort["role"] == "development" else "不同协议、预算或任务的批次分别报告。"
        table_sections.append('''<section class="cohort"><div class="section-label">%s · %s</div><h2>%s 个运行已结束，%s 个仍在运行</h2>
<p class="muted">协议 %s · 每个实例最多 %s 次请求 / %s 次实验 / %s 秒主动分析。%s</p>
<div class="table-wrap"><table><thead><tr><th>环境</th><th>综合分</th><th>完成率</th><th>条件 / 干预 / 主张</th><th>NRMSE 条件 / 干预</th><th>逐实例得分</th></tr></thead><tbody>%s</tbody></table></div>
<p class="caption">NRMSE 仅汇总产生有效数值的查询；失败仍在综合分中计 0。各分项同样包含健康失败。基础设施失败 %s；已知响应 token 下界 %s。</p>
<details><summary>协议与执行诊断</summary><pre>%s</pre></details></section>''' %
            (escape(label), escape(cohort["cohort"]), cohort["settled_runs"], cohort["running_runs"], escape(cohort["score_protocol"]),
             limit.get("rounds", "—"), limit.get("experiments", "—"), limit.get("analysis_active_seconds", "—"), escape(warning),
             "".join(rows), cohort["infrastructure_failures"], format(cohort["known_response_usage_lower_bound"]["total_tokens"], ","),
             escape(json.dumps({"source_sha256": cohort["source_sha256"], "decoding": cohort["decoding"],
                                "analysis_protocol": cohort["analysis_protocol"], "presentation_profile": cohort["presentation_profile"],
                                "model_completion_wilson_95": cohort["model_completion"]["wilson_95"],
                                "verified_effect_rate_wilson_95": cohort["verified_effect_rate"]["wilson_95"],
                                "diagnostics": cohort["trace_diagnostics"]}, ensure_ascii=False, indent=2))))
        if cohort["role"] == "development":
            table_sections[-1] = '<details><summary>开发批次记录（独立协议，不计入正式成绩）</summary>' + table_sections[-1] + '</details>'
    finding_cards = ['<article class="finding"><span>%s</span><h3>%s</h3><p>%s</p><small>%s</small></article>' %
                     tuple(escape(item.get(key, "")) for key in ("tag", "title", "body", "evidence"))
                     for item in notes.get("findings", [])]
    findings = "".join(finding_cards[:6])
    extra_findings = ('<details><summary>更多过程与校准诊断（%d 项）</summary><div class="findings">%s</div></details>' %
                      (len(finding_cards) - 6, "".join(finding_cards[6:]))) if len(finding_cards) > 6 else ""
    worlds = "".join('<tr><th>%s</th><td>%s</td><td>%s</td></tr>' % tuple(escape(item.get(key, "")) for key in ("name", "question", "status")) for item in notes.get("worlds", []))
    actions = "".join('<li><strong>%s</strong><p>%s</p></li>' % (escape(item["title"]), escape(item["body"])) for item in notes.get("next_steps", []))
    validation = "".join('<li>%s</li>' % escape(item) for item in notes.get("validation", []))
    text = ('''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>SLE · 科学环境进度与结论</title><style>
:root{--ink:#173d3a;--muted:#5a706d;--accent:#087e70;--paper:#f6f6ef;--line:#d4dfd7;--gold:#ae6a22}*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:15px/1.65 system-ui,-apple-system,sans-serif}main{max-width:1250px;margin:auto;padding:42px 30px 80px}header{padding-bottom:28px;border-bottom:2px solid var(--ink);margin-bottom:28px}.eyebrow,.section-label{font-size:12px;letter-spacing:.09em;text-transform:uppercase;color:var(--accent);font-weight:700}.status{display:inline-block;border:1px solid var(--line);border-radius:100px;padding:4px 12px;margin-top:16px;font-size:12px;background:white}h1{font-size:40px;line-height:1.25;max-width:930px;margin:13px 0}h2{font-size:25px;line-height:1.35;margin:10px 0 14px}h3{font-size:19px;margin:5px 0 9px}p{margin:8px 0}.lead{font-size:18px;max-width:1050px}.muted,small,.caption{color:var(--muted)}.caption{font-size:12px;margin-top:12px}.metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:13px}.metric{background:white;border:1px solid var(--line);padding:18px;border-radius:10px}.metric label{font-size:13px}.metric strong{display:block;font-size:27px;margin:10px 0}.metric small{display:block;font-size:11px}.notice{border-left:3px solid var(--gold);padding:14px 18px;margin:24px 0;background:#f0eadb}.cohort{margin-top:34px}table{border-collapse:collapse;background:white;width:100%%;font-size:13px}th,td{padding:12px 13px;text-align:left;border-bottom:1px solid var(--line);vertical-align:top}thead th{background:#e7eee6;font-size:12px}tbody th{white-space:nowrap;font-weight:600}.score{font-weight:700;font-size:18px}.table-wrap{overflow:auto}.evidence-table{min-width:1120px}.evidence-table th,.evidence-table td{white-space:nowrap}.evidence-table th:last-child,.evidence-table td:last-child{white-space:normal;min-width:330px}.findings{display:grid;grid-template-columns:repeat(2,1fr);gap:15px}.finding{padding:20px;background:white;border:1px solid var(--line);border-radius:10px}.finding span{font-size:11px;color:var(--accent);font-weight:700}.finding small{font-size:11px}.section{margin-top:40px}ol{padding-left:23px}li{padding-left:5px;margin:12px 0}li p{color:var(--muted)}details{margin-top:15px}summary{cursor:pointer;color:var(--accent);font-size:13px}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#eaf0e9;padding:15px;font-size:11px}footer{border-top:1px solid var(--line);margin-top:36px;padding-top:18px;font-size:12px;color:var(--muted)}a{color:var(--accent)}@media(max-width:900px){.metrics{grid-template-columns:repeat(2,1fr)}h1{font-size:31px}main{padding:27px 18px}}@media(max-width:550px){.findings,.metrics{grid-template-columns:1fr}h1{font-size:27px}.metric strong{font-size:26px}}
</style></head><body><main><header><div class="eyebrow">SCIENTISTS' LAST EXAM / COMPUTATIONAL SCIENCE WORLDS</div><h1>%s</h1><p class="lead">%s</p><div class="status">%s</div></header><div class="metrics">%s</div>
<div class="notice">综合分 = 50%% 未见条件预测 + 30%% 未见干预预测 + 20%% 自选主张复验。它是当前任务集上的 pilot 指标；高预测分、有效数值效应和机制发现深度分别报告。</div>
%s<section class="section"><div class="section-label">EVIDENCE & LIMITS</div><h2>发现了什么，证据到哪里</h2><div class="findings">%s</div>%s<p class="caption">%s</p>%s%s</section>
<section class="section"><div class="section-label">ENVIRONMENT COVERAGE</div><h2>环境与任务扩展</h2><div class="table-wrap"><table><thead><tr><th>世界</th><th>可研究的问题</th><th>当前状态</th></tr></thead><tbody>%s</tbody></table></div><p class="muted">%s</p></section>
<section class="section"><div class="section-label">BEFORE SCALING</div><h2>下一步优先修正什么</h2><ol>%s</ol></section><details><summary>验证与复现信息</summary><ul>%s</ul></details>
<footer>更新时间 %s UTC · <a href="data.json">下载结构化公开汇总</a> · 费用未知；未使用公开标价估算真实账单。私有 seed、封存目标和原始轨迹保留在操作目录。</footer></main></body></html>''' %
           (escape(headline), escape(notes.get("summary", "")), escape(notes.get("status", "工作继续进行中")), card_html,
            "".join(table_sections), findings, extra_findings, escape(notes.get("review_status", "发现深度尚待独立轨迹审核。")), evidence_matrix, scientific_figure, worlds,
            escape(notes.get("task_summary", "")), actions, validation, escape(data["generated_at_utc"][:19].replace("T", " "))))
    (output / "index.html").write_text(text, encoding="utf-8")
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cohort", action="append", required=True, help="role=/absolute/cohort")
    parser.add_argument("--notes", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    cohorts = [item.split("=", 1) for item in args.cohort]
    if any(len(item) != 2 for item in cohorts):
        parser.error("each --cohort needs role=path")
    build_report(cohorts, json.loads(Path(args.notes).read_text(encoding="utf-8")), args.output)


if __name__ == "__main__":
    main()

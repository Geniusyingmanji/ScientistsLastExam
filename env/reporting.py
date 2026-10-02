"""Compact local progress/conclusion HTML with explicit denominators."""
import html
import json
import math
import time
from pathlib import Path

import numpy as np

from .microecology.agent import save_json
from .scoring import WEIGHTS


def _rate(numerator, denominator):
    if denominator == 0:
        return {"numerator": numerator, "denominator": denominator, "rate": None, "wilson_95": None}
    p, z = numerator/denominator, 1.959963984540054
    center = (p+z*z/(2*denominator))/(1+z*z/denominator)
    radius = z*math.sqrt(p*(1-p)/denominator+z*z/(4*denominator**2))/(1+z*z/denominator)
    return {"numerator": numerator, "denominator": denominator, "rate": p,
            "wilson_95": [max(0., center-radius), min(1., center+radius)]}


def summarize(reports, expected_environments):
    settled = [r for r in reports if r.get("status") not in ("running", "exploring", "frozen")]
    healthy = [r for r in settled if r.get("infrastructure_failure") is None]
    complete = [r for r in healthy if r.get("model_completed")]
    by_environment = {}
    for name in expected_environments:
        rows = [r for r in healthy if r["environment"] == name]
        valid = [r for r in rows if r.get("model_completed")]
        scores = [float(r.get("score") or 0) for r in rows]
        baselines = {}
        for kind in ("conditions", "interventions"):
            values = [float(np.mean([p["score"] for p in r.get("baseline_panels", {}).get(kind, [])]))
                      for r in rows if r.get("baseline_panels", {}).get(kind)]
            baselines[kind] = float(np.mean(values)) if values else None
        by_environment[name] = {"healthy_runs": len(rows), "completed_runs": len(valid),
                                "mean_score": float(np.mean(scores)) if scores else None,
                                "scores": scores, "prediction_baseline_scores_on_verified_runs": baselines,
                                "verified_nonzero_effects": sum(r.get("verified_nonzero_effects", 0) for r in rows),
                                "completion": _rate(len(valid), len(rows))}
    full = all(v["scores"] for v in by_environment.values())
    macro = float(np.mean([v["mean_score"] for v in by_environment.values()])) if full else None
    interval = None
    if full and all(len(v["scores"]) >= 2 for v in by_environment.values()):
        rng = np.random.default_rng(280319)
        samples = np.array([np.mean(rng.choice(v["scores"], size=(2000, len(v["scores"])), replace=True), axis=1)
                            for v in by_environment.values()])
        interval = np.quantile(np.mean(samples, axis=0), [.025, .975]).tolist()
    usage = {k: sum((r.get("known_response_usage_lower_bound") or {}).get(k, 0) for r in reports)
             for k in ("input_tokens", "output_tokens", "total_tokens")}
    return {"created_unix": time.time(), "macro_score": macro, "macro_bootstrap_95": interval,
            "score_status": "pilot_estimate" if full else "partial_environment_coverage",
            "started_runs": len(reports), "settled_runs": len(settled), "healthy_runs": len(healthy),
            "infrastructure_failures": len(settled)-len(healthy), "running_runs": len(reports)-len(settled),
            "model_completion": _rate(len(complete), len(healthy)),
            "verified_effect_rate": _rate(sum(bool(r.get("has_verified_effect")) for r in healthy), len(healthy)),
            "end_to_end_completion": _rate(len(complete), len(reports)),
            "by_environment": by_environment, "known_response_usage_lower_bound": usage,
            "cost_usd": None, "cost_note": "Provider billing not supplied; no guessed currency cost.",
            "weights": WEIGHTS, "depth_status": "requires separate trace/evidence review",
            "notes": ["Bootstrap intervals describe this small sampled cohort, not the whole scientific capability of a model.",
                      "Verified effects are numerical replications, not automatic mechanism certificates.",
                      "Known-family simulation and hidden parameters do not by themselves establish contamination resistance."]}


def _fmt(value, digits=1):
    return "—" if value is None else ("%.*f" % (digits, value))


def _rate_text(value):
    if value["rate"] is None:
        return "— / 0"
    return "%d / %d · %.1f%%" % (value["numerator"], value["denominator"], 100*value["rate"])


def render_report(directory):
    directory = Path(directory)
    manifest = json.loads((directory/"manifest-private.json").read_text(encoding="utf-8"))
    status_path = directory/"campaign-status.json"
    campaign_status = json.loads(status_path.read_text()) if status_path.exists() else {}
    failures = {r["episode_id"]: r for r in campaign_status.get("errors", [])}
    reports = []
    for path in sorted((directory/"episodes").glob("*/started.json")):
        report_path = path.parent/"report.json"
        if report_path.exists():
            reports.append(json.loads(report_path.read_text(encoding="utf-8")))
        else:
            record = json.loads(path.read_text(encoding="utf-8"))
            reports.append(dict(record, status="running", infrastructure_failure=None))
    indexed = {r["episode_id"]: r for r in reports}
    for instance in manifest["instances"]:
        name = instance["episode_id"]
        if name in failures:
            record = indexed.get(name, {"episode_id": name, "environment": instance["environment"]})
            record.update(status="failed", infrastructure_failure="worker_or_dispatch_failure", score=None,
                          model_completed=False, stop_reason=failures[name].get("exception_type", "worker_failed"))
            indexed[name] = record
        elif name in indexed and campaign_status.get("status") == "completed" and indexed[name].get("status") in ("running", "exploring", "frozen"):
            indexed[name].update(status="failed", infrastructure_failure="worker_report_missing", score=None, model_completed=False)
    reports = list(indexed.values())
    summary = summarize(reports, manifest["environments"])
    summary.update(cohort=manifest["cohort"], planned_runs=len(manifest["instances"]), source_sha256=manifest["source_sha256"])
    save_json(directory/"summary.json", summary)
    environment_rows = []
    for name, row in summary["by_environment"].items():
        baseline = row["prediction_baseline_scores_on_verified_runs"]
        environment_rows.append("<tr><td>%s</td><td>%s</td><td>%s</td><td>%s / %s</td><td>%d</td></tr>" %
                                (html.escape(name), _fmt(row["mean_score"]), _rate_text(row["completion"]),
                                 _fmt(baseline["conditions"]), _fmt(baseline["interventions"]), row["verified_nonzero_effects"]))
    episode_rows, discoveries = [], []
    for r in reports:
        name = html.escape(r["episode_id"])
        target = "episodes/%s/report.json" % r["episode_id"]
        episode_rows.append('<tr><td><a href="%s">%s</a></td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>' %
                            (html.escape(target, quote=True), name, html.escape(r.get("status", "unknown")),
                             _fmt(r.get("score")), str(r.get("experiment_count", "—")), html.escape(r.get("stop_reason", "running"))))
        for claim in (r.get("claim_verification") or {}).get("claims", []):
            discoveries.append('<article class="claim"><div class="tag">%s · %s</div><p>%s</p><div>Δ = %s；90%% 预测区间 [%s, %s]；%s</div><small>%s</small></article>' %
                               (html.escape(r["environment"]), html.escape(claim["id"]), html.escape(claim["statement"]),
                                _fmt(claim["mean_difference"], 5), _fmt(claim["interval"][0], 5), _fmt(claim["interval"][1], 5),
                                "非零效应复验通过" if claim["verified_nonzero_effect"] else "未满足非零效应复验条件", html.escape(claim["scope"])))
    interval = summary["macro_bootstrap_95"]
    interval_text = "样本不足，暂不显示区间" if interval is None else "分层 bootstrap 95% 区间 [%s, %s]" % (_fmt(interval[0]), _fmt(interval[1]))
    html_text = """<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>SLE · 科学环境进度</title><style>
:root{color-scheme:light;--ink:#183434;--muted:#5c7372;--accent:#087f72;--line:#d8e4de;--paper:#f5f7f3}*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:15px/1.65 system-ui,-apple-system,sans-serif}main{max-width:1180px;margin:auto;padding:42px 28px 80px}header{border-bottom:2px solid var(--ink);padding-bottom:24px;margin-bottom:26px}.eyebrow{letter-spacing:.15em;font-size:12px;color:var(--accent);font-weight:700}h1{font-size:38px;line-height:1.2;margin:12px 0}h2{font-size:22px;margin-top:36px}p{max-width:900px}.muted,small{color:var(--muted)}.cards{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}.card{background:white;border:1px solid var(--line);border-radius:12px;padding:20px}.value{font-size:30px;font-weight:700;line-height:1.25;margin:10px 0}.card small{font-size:12px}table{border-collapse:collapse;width:100%%;background:white;font-size:14px}td,th{text-align:left;padding:13px;border-bottom:1px solid var(--line)}th{font-weight:600;background:#e8f0e9}a{color:var(--accent)}.scroll{overflow:auto}.claim{background:white;border-left:3px solid var(--accent);padding:15px 20px;margin:14px 0}.claim p{margin:8px 0}.tag{font-size:12px;font-weight:700;color:var(--accent)}.notice{padding:18px;background:#e9eee7;border-radius:10px}.meta{font-size:12px;overflow-wrap:anywhere}details{margin-top:20px}@media(max-width:800px){.cards{grid-template-columns:repeat(2,1fr)}h1{font-size:30px}main{padding:24px 16px}}@media(max-width:480px){.cards{grid-template-columns:1fr}}
</style><main><header><div class="eyebrow">SCIENTISTS' LAST EXAM / VIRTUAL WORLDS</div><h1>科学环境与 GPT-5.6 评测</h1><div class="muted">批次：%s · 已启动 %d / 计划 %d · 已结束 %d · 正在运行 %d</div></header>
<section class="cards"><div class="card"><div>SLE-Pilot 综合分</div><div class="value">%s <small>/ 100</small></div><small>%s</small></div><div class="card"><div>模型完成率</div><div class="value">%s</div><small>分母为环境/API 健康的已结束运行</small></div><div class="card"><div>有效数值发现率</div><div class="value">%s</div><small>至少一个非零效应经新测量复验；不等同机制发现</small></div><div class="card"><div>端到端完成率</div><div class="value">%s</div><small>分母包含全部已启动运行</small></div></section>
<h2>各环境结果</h2><div class="scroll"><table><thead><tr><th>环境</th><th>平均综合分</th><th>模型完成</th><th>基线：条件 / 干预</th><th>复验非零效应</th></tr></thead><tbody>%s</tbody></table></div>
<p class="muted">综合分 = 50%% 未见条件预测 + 30%% 未见干预预测 + 20%% 自选定量主张复验。每个环境等权；健康运行未完成记 0 分。基线列使用已进入验证的运行，不能与含失败的综合分直接等同。</p>
<h2>发现与证据</h2>%s
<div class="notice">发现深度需要依据实验轨迹单独审核。目前自动验证的是预测与数值效应。高预测分不能自动证明唯一机制、开放式科学发现或抗记忆污染。</div>
<h2>运行记录</h2><div class="scroll"><table><thead><tr><th>运行 / 原始记录</th><th>状态</th><th>得分</th><th>实验数</th><th>结束原因</th></tr></thead><tbody>%s</tbody></table></div>
<p>基础设施失败：%d；已知响应 token 合计下界：%s。计费信息未提供，不推算实际费用。</p>
<details><summary>评测边界与后续判断</summary><ul><li>先稳定不同环境的完成率、预测误差和可复验发现，再进行预算 scaling。</li><li>对比基线可识别任务过易、数据利用不足和预测器实现失败；深度审核需检查对照、机制区分、反例和适用范围。</li><li>隐藏参数和重命名不足以证明抗污染；需要隐藏结构、分布变化与全新组合的单独验证。</li><li>样本少时区间只描述当前 cohort；开发批次与正式批次分别报告。</li></ul></details>
<p class="meta muted">source SHA-256: %s · <a href="summary.json">结构化汇总</a></p></main></html>""" % (
        html.escape(manifest["cohort"]), summary["started_runs"], len(manifest["instances"]), summary["settled_runs"], summary["running_runs"],
        _fmt(summary["macro_score"]), interval_text, _rate_text(summary["model_completion"]), _rate_text(summary["verified_effect_rate"]), _rate_text(summary["end_to_end_completion"]),
        "".join(environment_rows), "".join(discoveries) or '<p class="muted">尚无完成的独立复验结果。</p>', "".join(episode_rows), summary["infrastructure_failures"], format(summary["known_response_usage_lower_bound"]["total_tokens"], ","), manifest["source_sha256"])
    (directory/"index.html").write_text(html_text, encoding="utf-8")
    return summary

"""Render a completed or interrupted operator campaign using saved reports only."""
import argparse
import html
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D


def esc(value):
    return html.escape(str(value))


def read(path):
    return json.loads(path.read_text())


def fmt(value):
    return "未提供" if value is None else "%.5f" % value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    root = args.directory
    campaign = read(root / "campaign-report.json")
    manifest = read(root / "campaign-manifest.json")
    entries = campaign["episodes"]
    total_claims = sum(e.get("claim_count", 0) for e in entries)
    supported = sum(e.get("supported", 0) for e in entries)
    covered = sum(e.get("forecast_covered", 0) for e in entries)
    forecasts = sum(e.get("forecast_count", 0) for e in entries)
    known_tokens = sum(e.get("known_response_usage_lower_bound", {}).get("total_tokens", 0) for e in entries)
    usage_complete = all(e.get("usage", {}).get("total_tokens") is not None for e in entries)
    palette = {"prediction_supported": "#17826d", "prediction_refuted": "#c44750", "inconclusive": "#b57a13"}
    status_cn = {"prediction_supported": "效应区间一致", "prediction_refuted": "效应区间被反驳", "inconclusive": "未定"}
    plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False,
                         "axes.grid": True, "grid.alpha": .18})
    sections, rows = [], []
    for entry in entries:
        number = entry["episode"]
        directory = root / ("episode-%02d" % number)
        public_path, agent_path = directory / "public-report.json", directory / "agent-report.json"
        public = read(public_path) if public_path.exists() else {}
        agent = read(agent_path) if agent_path.exists() else {}
        claims = {c["id"]: c for c in public.get("claims") or []}
        results = entry.get("results", [])
        rows.append("<tr>" + "".join("<td>" + esc(x) + "</td>" for x in (
            number, entry["state"], entry.get("api_attempts", "?"),
            "%d / %d" % (entry.get("supported", 0), entry.get("claim_count", 0)),
            "%d / %d" % (entry.get("forecast_covered", 0), entry.get("forecast_count", 0)),
            fmt(entry.get("mean_forecast_width")), fmt(entry.get("mean_interval_score")))) + "</tr>")
        parts = ["<h2>实例 %d</h2><section>" % number,
                 "<p>结束状态：%s；停止原因：%s；模型响应标识：%s。</p>" % (
                     esc(entry["state"]), esc(entry.get("stop_reason")), esc(", ".join(entry.get("reported_models", [])))),
                 "<p>耗时 %s 秒；探索消耗 %s / 800 单位；事件重放：%s。</p>" % (
                     fmt(entry.get("elapsed_seconds")), esc(entry.get("resources", {}).get("experiment_units")),
                     esc(entry.get("replay", {}).get("status", "未通过或未执行")))]
        if results:
            fig, ax = plt.subplots(figsize=(10, max(3.2, len(results) * 1.0 + 1.4)))
            for i, result in enumerate(results):
                low, high = result["expected_difference"]
                ax.plot([low, high], [i, i], color="#d5deea", lw=15, solid_capstyle="round", zorder=1)
                forecast = result.get("forecast_evaluation", {})
                if forecast:
                    ax.plot(forecast["interval"], [i - .15, i - .15], color="#246eb9", lw=4, zorder=2)
                mean = result["mean_difference"]
                ci = result["confidence_interval"]
                ax.errorbar([mean], [i + .12], xerr=[[mean - ci[0]], [ci[1] - mean]], fmt="o", capsize=4,
                            color=palette[result["status"]], ms=7, lw=2, zorder=3)
            ax.axvline(0, color="#7b8ca3", ls="--", lw=1)
            ax.set_yticks(range(len(results)), ["Claim %d" % (i + 1) for i in range(len(results))])
            ax.invert_yaxis()
            ax.set_xlabel("Treatment minus control biomass (mmol C / L)")
            ax.set_title("Instance %d | frozen predictions and fresh confirmation" % number, loc="left", weight="bold")
            ax.legend(handles=[Line2D([0], [0], color="#d5deea", lw=10, label="Effect-consistency band"),
                               Line2D([0], [0], color="#246eb9", lw=4, label="90% predictive interval"),
                               Line2D([0], [0], color="#17826d", marker="o", label="Observed mean + approximate CI")],
                      loc="upper center", bbox_to_anchor=(.5, -.18), ncol=3, frameon=False, fontsize=8)
            fig.tight_layout()
            figure = "confirmation-%02d" % number
            fig.savefig(root / (figure + ".svg"), bbox_inches="tight")
            fig.savefig(root / (figure + ".png"), dpi=145, bbox_inches="tight")
            plt.close(fig)
            parts.append('<figure><img src="%s.svg" alt="预测与确认实验对比"></figure>' % figure)
            for i, result in enumerate(results):
                claim = claims[result["claim_id"]]
                forecast = result.get("forecast_evaluation", {})
                parts.append('<details open><summary>Claim %d · %s · %s</summary><p>%s</p>' % (
                    i + 1, esc(result["claim_id"]), status_cn[result["status"]], esc(claim["statement"])))
                parts.append('<p>实际均值 %s；预测区间宽度 %s；interval score %s；本次均值是否落入预测区间：%s。</p>' % (
                    fmt(result["mean_difference"]), fmt(forecast.get("width")), fmt(forecast.get("interval_score")),
                    "是" if forecast.get("covered") else "否"))
                parts.append('<pre>%s</pre></details>' % esc(json.dumps(claim, ensure_ascii=False, indent=2)))
        interpretation = (public.get("interpretation") or {}).get("text", "未提交最终解释。")
        parts.append('<h3>模型最终解释（原文，未作机制认证）</h3><div class="prose">%s</div>' % esc(interpretation))
        parts.append('<h3>逐轮研究记录</h3>')
        for turn in agent.get("history", []):
            parts.append('<details><summary>第 %d 轮 · %s</summary><pre>%s</pre></details>' % (
                turn["round"], esc(turn.get("note", "格式错误")), esc(json.dumps(turn, ensure_ascii=False, indent=2))))
        for record in agent.get("rounds", []):
            if "error" in record:
                parts.append('<p>API 错误诊断：%s</p>' % esc(json.dumps(record, ensure_ascii=False)))
        parts.append('<p><a href="episode-%02d/public-report.json">公开证据报告</a> · <a href="episode-%02d/agent-report.json">模型回合报告</a></p></section>' % (number, number))
        sections.append("".join(parts))
    document = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>SLE · GPT-5.6 评测</title><style>
*{box-sizing:border-box}body{margin:0;background:#f1f4f8;color:#243449;font:16px/1.7 system-ui,-apple-system,sans-serif}main{max-width:1250px;margin:auto;padding:42px 26px}header{padding-bottom:20px;border-bottom:2px solid #284763}small{color:#62758b;letter-spacing:.1em}h1{font-size:34px;margin:6px 0}h2{margin-top:34px;font-size:24px}.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}.card,section{padding:22px;background:white;border-radius:12px;margin:18px 0}.card strong{display:block;font-size:25px}.card span{font-size:13px;color:#61758d}table{border-collapse:collapse;width:100%;font-size:14px}td,th{padding:12px 8px;border-bottom:1px solid #dce4ed;text-align:left}figure{margin:22px 0}figure img{width:100%;display:block}details{padding:14px 0;border-bottom:1px solid #dee6ee}summary{cursor:pointer;font-weight:600}pre{font:13px/1.6 ui-monospace,monospace;white-space:pre-wrap;overflow-wrap:anywhere;padding:18px;background:#f4f7fa}.prose{white-space:pre-wrap;overflow-wrap:anywhere}.notice{border-left:4px solid #258572;padding-left:16px}a{color:#126794}p{margin:9px 0}@media(max-width:750px){.grid{grid-template-columns:1fr 1fr}main{padding:24px 13px}table{display:block;overflow-x:auto}}
</style><main><header><small>SLE · MICROECOLOGY · PAIRED EFFECTS V2</small><h1>GPT-5.6 自主发现评测</h1><p>g450 计算与沙箱 · 无预设答案匹配 · 小规模开发评测</p></header>'''
    cards = [("完成闭环", "%d / %d" % (campaign["completed"], campaign["instances_planned"])), ("本组 API 请求", str(campaign["started_model_requests"])),
             ("效应区间一致", "%d / %d" % (supported, total_claims)), ("预测区间覆盖", "%d / %d" % (covered, forecasts))]
    document += '<div class="grid">' + ''.join('<div class="card"><strong>%s</strong><span>%s</span></div>' % (esc(v), esc(k)) for k, v in cards) + '</div>'
    document += '<section><p class="notice">本轮自动检查声明效应和区间预测。机制识别、新颖性、未见条件泛化及 Discovery Depth 未评定。实例属于同一机制家族，仅参数和匿名化学峰映射变化；复验只改变测量噪声。</p>'
    if campaign.get("operator_note"):
        document += '<p class="notice">%s</p>' % esc(campaign["operator_note"])
    if manifest.get("prior_campaign"):
        document += '<p class="notice">本组为沙箱计时修复后的独立运行。此前 %d 次请求含一个工具受损的完整运行及一个人为中止运行，均保留在<a href="../diagnostic/index.html">诊断记录</a>，不纳入本组结果。全部请求累计 %d / 48；前后轮数预算不同。协议修订在新调用前记录。</p>' % (campaign["prior_started_requests"], campaign["combined_started_requests"])
    document += '<p>已知 token 用量：%d%s。服务未配置价格，费用未知。</p>' % (known_tokens, '' if usage_complete else '（仅已返回响应的下界；完整用量未知）')
    document += '<p>预先声明 %d 例；每例最多 %d 次请求、前 %d 轮允许探索、800 探索单位；后续只接受冻结声明和解释。每条声明每臂 8 次传感器噪声重复，最多 3 条主要声明，无自动 API 重试。</p></section>' % (manifest["instances"], manifest["max_requests_per_instance"], manifest["exploration_rounds"])
    document += '<section><table><thead><tr><th>实例</th><th>状态</th><th>API 请求</th><th>效应区间一致</th><th>预测覆盖</th><th>平均预测宽度</th><th>平均 interval score ↓</th></tr></thead><tbody>' + ''.join(rows) + '</tbody></table><p>Interval score 同时惩罚宽度和失误，单位 mmol C/L。各实例的声明由模型自行选择，平均分仅用于描述本轮结果，不宜直接作为跨模型排名分数。小样本覆盖率也不等于校准度。</p></section>'
    document += '<h2>下一步计划</h2><section><ol><li>加入在新初始条件、剂量和时序上的冻结预测器，固定测试面板，与反例搜索分别计量。</li><li>支持中介依赖与时间曲线声明，检验替代机制，校准微生态世界的发现深度证据门槛。</li><li>用固定实验策略、黑盒预测器和已知机制模型校准评估器，再扩展未公开机制结构。</li></ol></section>'
    document += ''.join(sections) + '<footer><a href="campaign-report.json">完整评测 JSON</a> · <a href="campaign-manifest.json">预先固定的评测配置</a></footer></main></html>'
    (root / 'index.html').write_text(document)
    for path in root.iterdir():
        if path.is_file():
            path.chmod(0o600)
    print(json.dumps({"completed": campaign["completed"], "claims": total_claims, "supported": supported,
                      "forecast_covered": covered, "forecasts": forecasts, "known_tokens": known_tokens,
                      "usage_complete": usage_complete, "index": str(root / 'index.html')}))


if __name__ == '__main__':
    main()

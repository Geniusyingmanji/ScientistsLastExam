"""Reviewed construction demo: only public WorldSession actions select a fraction.

This is an operator-written experiment, not evidence of an LLM's discovery skill.
"""
from __future__ import annotations

from .protocol import clone


INITIAL = {"biomass": {"A": 0.06, "B": 0.04, "C": 0.06},
           "nutrient": 4.0, "volume_ml": 10.0, "temperature_c": 30.0}


def schedules(channel=None):
    result = []
    for hour in (8, 12, 16, 20):
        if channel:
            result.append({"at_h": hour, "operation": "deplete", "arguments": {"channel": channel, "fraction": 0.9}})
        if hour in (16, 20):
            result.append({"at_h": hour, "operation": "feed", "arguments": {"amount_mmol": 0.02}})
    return result


def run_demo(session):
    counter = 0

    def act(operation, arguments):
        nonlocal counter
        counter += 1
        result = session.step({"request_id": "demo-%04d" % counter, "operation": operation, "arguments": arguments})
        if not result["ok"]:
            raise RuntimeError("demo action failed: " + result["error"])
        return result

    channels = session.describe()["tools"]["deplete"]["arguments"]["channel"]
    preparations = {"ABC": clone(INITIAL), "AC": clone(INITIAL), "AB": clone(INITIAL), "A": clone(INITIAL)}
    preparations["AC"]["biomass"]["B"] = 0
    preparations["AB"]["biomass"]["C"] = 0
    preparations["A"]["biomass"].update(B=0, C=0)
    for channel in channels:
        preparations["remove-" + channel] = clone(INITIAL)
    handles = {label: act("create", {**initial, "label": label})["observation"]["vessel_id"]
               for label, initial in preparations.items()}
    traces = {label: [] for label in handles}
    endpoint_evidence = []
    for hour in range(0, 33, 2):
        if hour:
            act("advance", {"hours": 2})
        if hour in (8, 12, 16, 20):
            for label, handle in handles.items():
                if label.startswith("remove-"):
                    act("deplete", {"vessel_id": handle, "channel": label[len("remove-"):], "fraction": 0.9})
                if hour in (16, 20):
                    act("feed", {"vessel_id": handle, "amount_mmol": 0.02})
        for label, handle in handles.items():
            counts = act("measure", {"vessel_id": handle, "instrument": "counts"})["observation"]
            chemistry = act("measure", {"vessel_id": handle, "instrument": "chemistry"})["observation"]
            traces[label].append({"time_h": hour, "counts": counts["values"], "chemistry": chemistry["values"],
                                  "counts_evidence": counts["observation_id"], "chemistry_evidence": chemistry["observation_id"]})
            if hour == 24:
                endpoint_evidence.append(counts["observation_id"])
    endpoint = {label: next(row for row in rows if row["time_h"] == 24)["counts"] for label, rows in traces.items()}
    chosen = max(channels, key=lambda channel: endpoint["remove-" + channel]["C"] - endpoint["ABC"]["C"])
    c_effect = endpoint["remove-" + chosen]["C"] - endpoint["ABC"]["C"]
    a_effect = endpoint["remove-" + chosen]["A"] - endpoint["ABC"]["A"]

    def claim(cid, species, prediction, statement, initial=None):
        return {"id": cid, "statement": statement, "initial": clone(initial or INITIAL),
                "control": schedules(), "treatment": schedules(chosen),
                "readout": {"species": species, "time_h": 24}, "expected_difference": prediction,
                "replicates": 8, "evidence_ids": endpoint_evidence}

    # Intervals are frozen from exploration BEFORE confirmation is executed.
    claims = [claim("C-rescue", "C", [c_effect - 0.04, c_effect + 0.04],
                    "Removing the selected fraction increases C biomass under this schedule."),
              claim("A-response", "A", [a_effect - 0.04, a_effect + 0.04],
                    "Predict the secondary A response under the same schedule."),
              claim("C-absent-control", "A", [-0.015, 0.015],
                    "Test the hypothesis that A rescue is absent when C is not inoculated.", preparations["AB"]),
              claim("deliberately-wrong-direction", "C", [-c_effect - 0.04, -c_effect + 0.04],
                    "Negative verifier control: deliberately reverse the explored C effect.")]
    committed = act("commit", {"claims": claims})
    results = committed["verification"]["results"]
    text = ("Public fraction screening selected %s. Fresh experiments checked only the frozen paired "
            "biomass contrasts. The C-absent result tests a necessary implication of C-mediated rescue; "
            "these experiments do not establish a unique full feedback mechanism, real biology, novelty, "
            "or a Discovery Depth score. The reversed prediction is a deliberate verifier control. Results: %s."
            % (chosen, "; ".join(r["claim_id"] + "=" + r["status"] for r in results)))
    act("interpret", {"claim_sha256": committed["claim_sha256"], "text": text})
    return {"kind": "operator_construction_demo", "selected_channel": chosen,
            "selection_basis": "maximum measured C rescue at 24 h in exploration",
            "traces": traces, "verification": clone(committed["verification"]),
            "interpretation": text, "model_api_calls": 0}


def render_demo(demo, directory):
    """Export standard scientific plots from public observations only."""
    import html
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    selected = "remove-" + demo["selected_channel"]
    colors = {"ABC": "#1f647e", "AC": "#74848b", "AB": "#ae783e", selected: "#d45445"}
    fig, axes = plt.subplots(2, 2, figsize=(12, 8), layout="constrained")
    for ax, species in zip(axes.flat[:3], ("A", "B", "C")):
        for label, color in colors.items():
            rows = demo["traces"][label]
            ax.plot([r["time_h"] for r in rows], [r["counts"][species] for r in rows],
                    label=label, color=color, lw=2)
        ax.set(title="Strain " + species, xlabel="Simulation time (h)", ylabel="Biomass (mmol C/L)")
        for time_h in (16, 20):
            ax.axvline(time_h, color="#aaa", ls=":", lw=1)
        ax.grid(alpha=0.15)
    axes[0, 0].legend(fontsize=8)
    ax = axes[1, 1]
    for channel in ("peak-01", "peak-02", "peak-03"):
        rows = demo["traces"]["ABC"]
        ax.plot([r["time_h"] for r in rows], [r["chemistry"][channel] for r in rows], label=channel, lw=2)
    ax.set(title="Anonymous extracellular channels (ABC)", xlabel="Simulation time (h)", ylabel="Concentration (mmol C/L)")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.15)
    fig.suptitle("SLE Microecology | Public observations, seed-specific construction demo", fontsize=14)
    fig.savefig(directory / "trajectories.png", dpi=160)
    fig.savefig(directory / "trajectories.svg")
    plt.close(fig)
    rows = "".join("<tr><td>%s</td><td>%s</td><td>%.4f</td><td>[%.4f, %.4f]</td></tr>" % (
        html.escape(r["claim_id"]), html.escape(r["status"]), r["mean_difference"], *r["confidence_interval"])
        for r in demo["verification"]["results"])
    page = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>SLE 微生态原型</title>
<style>body{font-family:system-ui,sans-serif;max-width:1060px;margin:48px auto;padding:0 24px;color:#19323c;background:#f6f8f7}h1{font-size:36px}img{width:100%;background:white;border-radius:12px}table{width:100%;border-collapse:collapse;background:white}td,th{text-align:left;padding:14px;border-bottom:1px solid #ddd}p{line-height:1.8}.tag{color:#566b72}a{color:#196888}</style>
<p class="tag">Scientists' Last Exam · 可计算科学世界 · 原型 0.1</p><h1>一个可以实验的微生态世界</h1>
<p>七组培养条件、三种菌、匿名化学测量。实验程序根据公开测量选择去除组分，然后冻结预测，以新培养物完成确认。下图是带测量噪声的观测，不是隐藏状态。</p>
<img src="trajectories.png" alt="菌群与匿名化学信号时间序列"><p>虚线表示 16、20 小时各加入 0.02 mmol C 营养。组分去除发生于 8、12、16、20 小时；培养时间 32 小时。</p>
<h2>冻结后的数值预测检验</h2><table><tr><th>主张</th><th>结果</th><th>处理 − 对照</th><th>近似置信区间</th></tr>''' + rows + '''</table>
<p>重复实验具有相同确定性动力学和独立测量噪声。只核验指定条件下的数值效应；完整机制、发现深度、难度及抗污染能力尚未认证。反向主张是刻意设置的错误对照。本次没有调用模型 API。</p>
<p><a href="public-report.json">完整公开证据</a> · <a href="demo.json">实验数据</a> · <a href="trajectories.svg">矢量图</a></p></html>'''
    (directory / "index.html").write_text(page, encoding="utf-8")

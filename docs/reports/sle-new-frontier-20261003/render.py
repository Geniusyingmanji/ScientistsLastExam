#!/usr/bin/env python3
"""Render a self-contained Chinese research report from sanitized public data.

Usage: python3 render.py --data data.json --output index.html
Only the standard library is needed. Unknown top-level / episode fields are
excluded; private source/code/transport fields are rejected by the public-tree
filter. The caller remains responsible for semantic sanitization of its input.
No network, JavaScript dependencies, simulator imports, or model calls.
"""
import argparse
import datetime
import html
import json
import math
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOP_FIELDS = {"status", "protocol", "source_commit", "updated_at", "ledger", "episodes", "review", "cohort"}
EPISODE_FIELDS = {"episode_id", "environment", "status", "stop_reason", "rounds_count", "model_requests", "final_explanation", "steps", "tests", "review", "instance_alias", "repeat"}
PRIVATE_KEYS = {"seed", "world_seed", "instance_seed", "panel_seed", "noise_key", "predictor_code", "code", "source", "raw_response", "raw_transport", "transport", "api_key", "token", "access_token", "authorization", "private_path", "path", "directory", "operator_manifest", "future_targets"}
LABELS = {
    "planned": "计划中", "pending": "待开始", "running": "进行中", "completed": "已完成", "complete": "已完成",
    "finished": "已提交研究结论", "invalid_scientific_action": "科学动作校验失败", "research_finished": "研究已提交", "failed": "失败", "stopped": "已停止", "operator_failure": "运行设施失败",
    "budget_exhausted": "预算耗尽", "invalid_action": "实验动作无效", "invalid_action_json": "JSON动作无效",
    "schema_rejected": "格式退回，未执行实验", "analysis_ok": "分析完成", "analysis_failed": "分析失败", "observed": "获得观测",
    "candidate_prediction_failed": "预测程序失败", "initialization_unresolved": "初始化未解决", "incomplete": "尚未完成", "invalid": "无效运行",
    "model_budget": "模型轮数耗尽", "science_or_wall_budget": "实验或时长预算耗尽", "model_transport_error": "API传输失败",
    "scoped_predictive_adequacy": "所选读出达到预定容差", "scoped_predictive_discrimination": "所选读出区分了两个候选",
    "candidate_refuted": "候选预测被反驳", "both_candidates_refuted": "两个候选均被反驳", "inconclusive": "无法判定",
    "predictive_validation": "单模型前瞻检验", "mechanism_discrimination": "双候选前瞻比较", "regime_transfer": "新条件迁移检验"
}
SUPPORTED = {"scoped_predictive_adequacy", "scoped_predictive_discrimination"}
REFUTED = {"candidate_refuted", "both_candidates_refuted"}
COMPLETE = {"completed", "complete", "research_finished"}


def clean_string(value):
    # Defense in depth only; the public data producer must still remove secrets.
    text = str(value)
    text = re.sub(r"(?:gh[pousr]_[A-Za-z0-9_]{16,}|sk-[A-Za-z0-9_-]{16,}|Bearer\s+[A-Za-z0-9._-]+)", "[已省略凭据]", text)
    text = re.sub(r"/(?:Users|home|ossfs|private|var/tmp|tmp)/[^\s\"'<>]+", "[已省略私有路径]", text)
    return text


def public_tree(value):
    if isinstance(value, dict):
        return {clean_string(k): public_tree(v) for k, v in value.items()
                if str(k).lower() not in PRIVATE_KEYS and not str(k).lower().endswith("_seed")}
    if isinstance(value, (list, tuple)):
        return [public_tree(v) for v in value]
    if isinstance(value, str):
        return clean_string(value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def sanitize(data):
    if not isinstance(data, dict):
        raise ValueError("data must be a JSON object")
    result = public_tree({k: v for k, v in data.items() if k in TOP_FIELDS})
    raw = result.get("episodes", [])
    if not isinstance(raw, list) or any(not isinstance(e, dict) for e in raw):
        raise ValueError("episodes must be an array of objects")
    result["episodes"] = [{k: v for k, v in e.items() if k in EPISODE_FIELDS} for e in raw]
    return result


def esc(value):
    return html.escape(str(value), quote=True)


def label(value):
    return LABELS.get(str(value), str(value))


def number(value):
    if value is None:
        return "未提供"
    if isinstance(value, bool):
        return "是" if value else "否"
    if isinstance(value, (int, float)):
        return format(value, ".6g")
    return str(value)


def prose(value):
    if value is None or value == "":
        return '<p class="muted">尚无记录。</p>'
    if isinstance(value, (dict, list)):
        return '<pre>%s</pre>' % esc(json.dumps(value, ensure_ascii=False, indent=2))
    return '<p class="prose">%s</p>' % esc(value)


def badge(outcome):
    cls = "positive" if outcome in SUPPORTED else "negative" if outcome in REFUTED or "fail" in str(outcome) else "neutral"
    return '<span class="badge %s">%s</span>' % (cls, esc(label(outcome or "pending")))


def as_list(value):
    return value if isinstance(value, list) else []


def interval(value):
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        return "未提供"
    return "[%s, %s]" % (number(value[0]), number(value[1]))


def render_test(test):
    if not isinstance(test, dict):
        return ""
    candidates = as_list(test.get("candidates"))
    rows = []
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        supported = candidate.get("within_tolerance_on_readout") is True
        refuted = candidate.get("refuted_on_readout") is True
        conclusion = "达到容差" if supported else "被反驳" if refuted else "未判定"
        band = candidate.get("tolerance_band")
        rows.append('<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>' % (
            esc(candidate.get("id", "候选")), esc(number(candidate.get("predicted_readout", candidate.get("prediction")))),
            esc(interval(band) if band is not None else number(candidate.get("tolerance"))), esc(conclusion)))
    candidate_table = ('<div class="scroll"><table><thead><tr><th>冻结候选</th><th>提前预测</th><th>容差区间 / 容差</th><th>该读出结论</th></tr></thead><tbody>%s</tbody></table></div>' % "".join(rows)) if rows else '<p class="muted">候选预测明细尚未提供。</p>'
    stats = '<div class="test-stats"><div><span>新观测的平均读出</span><strong>%s</strong></div><div><span>数据置信区间</span><strong>%s</strong></div></div>' % (esc(number(test.get("mean_readout"))), esc(interval(test.get("confidence_interval"))))
    notes = ""
    if test.get("counterexample_candidate_ids"):
        notes += '<p class="negative-text">反例对应候选：%s</p>' % esc(", ".join(map(str, test["counterexample_candidate_ids"])))
    for key, title in (("interpretation", "结果解释"), ("limitations", "检验局限"), ("revision_of", "修订自")):
        if test.get(key):
            notes += '<h5>%s</h5>%s' % (title, prose(test[key]))
    design = test.get("design", {})
    design_details = '<details class="subdetail"><summary>查看实验条件、读出与统计设计</summary>%s</details>' % prose(design)
    return '<article class="test"><div class="test-top"><h4>%s</h4>%s</div>%s%s%s<p class="caption">数值对应预先选定的归一化加权读出，未必代表整条轨迹或全部观测通道。置信区间落入整个容差带才支持充分接近；“尚未反驳”不等于验证成功。</p>%s%s</article>' % (
        esc(test.get("test_id", "前瞻检验")), badge(test.get("outcome")), prose(test.get("scope")), stats, candidate_table, notes, design_details)


def render_episode(episode, name, sequence):
    eid = str(episode.get("episode_id", "episode-%d" % sequence))
    steps = []
    for item in as_list(episode.get("steps")):
        if not isinstance(item, dict):
            continue
        detail = ('<details class="step-detail"><summary>查看本轮证据</summary>%s</details>' % prose(item.get("detail"))) if item.get("detail") is not None else ""
        steps.append('<li><div class="step-heading"><span class="round">第%s轮</span>%s</div>%s%s</li>' % (
            esc(item.get("round", "?")), badge(item.get("outcome")), prose(item.get("note")), detail))
    chronology = '<ol class="timeline">%s</ol>' % "".join(steps) if steps else '<p class="muted">尚无公开逐轮记录；不会用最终解释倒推一个假想的发现过程。</p>'
    tests = "".join(render_test(t) for t in as_list(episode.get("tests")))
    if not tests:
        tests = '<p class="empty">尚无已完成的前瞻检验。实验调用或拟合完成本身不算预测获得支持。</p>'
    stop = '<p class="stop"><b>停止原因：</b>%s</p>' % esc(label(episode["stop_reason"])) if episode.get("stop_reason") else ""
    review = '<section class="episode-review"><h4>科学复核</h4>%s</section>' % render_review(episode["review"]) if episode.get("review") else '<p class="caption">下述最终解释由模型提交；机制含义和发现深度仍需要结合实验轨迹复核。</p>'
    return '<details class="episode" id="%s" data-world="%s"><summary><span class="episode-title"><b>%s</b><span>%s · %s轮 · %s次模型请求</span></span>%s</summary><div class="episode-body">%s%s<h3>研究过程：问题 → 实验 → 观测 → 修订</h3>%s<h3>提前冻结的预测与新观测</h3>%s<h3>模型最终提交</h3>%s</div></details>' % (
        esc(eid), esc(episode.get("environment", "")), esc(eid), esc(name), esc(episode.get("rounds_count", "—")), esc(episode.get("model_requests", "—")), badge(episode.get("status")), stop, review, chronology, tests, prose(episode.get("final_explanation")))


def evidence_text(value):
    text = esc(value)
    pattern = r"\b(?:v03-)?(?:molecular_forces|climate_response|catalyst_aging|field_ecology|phase_equilibria)-i[1-3]-r[12]\b"
    return re.sub(pattern, lambda match: '<a href="#%s">%s</a>' % (match[0], match[0]), text)


def render_review(review):
    if not isinstance(review, dict):
        return prose(review)
    titles = {"status": "复核状态", "headline": "主要结论", "worlds": "各环境实际发现了什么", "cross_cutting_shortcomings": "跨环境的共同不足", "limits": "证据边界", "summary": "当前结论", "conclusion": "当前结论",
              "supported": "现有证据支持什么", "supported_claims": "现有证据支持什么",
              "strengths": "模型已经做到的事", "shortcomings": "模型的不足",
              "limitations": "证据边界", "not_supported": "尚不能支持什么",
              "evidence_stages": "发现走到了哪一步", "next_steps": "下一步", "attempted_discovery": "试图发现什么", "evidence": "实际证据", "discovery": "发现及其范围", "failure_attribution": "停止原因归属", "depth": "发现深度的定性判断", "scope": "结论适用范围", "notes": "补充说明"}
    parts = []
    for key, value in review.items():
        if key in ("counts", "source", "raw_archive_crosscheck"): continue
        title = titles.get(key, str(key))
        if key == "worlds" and isinstance(value, list):
            body = ""
            for world in value:
                if not isinstance(world, dict): continue
                support = []
                for item in world.get("supported", []):
                    if isinstance(item, dict):
                        reference = item.get("evidence", {}).get("episode_id", "")
                        support.append(item.get("text", "") + ("（" + reference + "）" if reference else ""))
                    else: support.append(str(item))
                body += '<article class="test"><h3>%s</h3>%s%s</article>' % (esc(world.get("name", "")), prose(world.get("summary")), render_review({"supported": support, "shortcomings": world.get("shortcomings", []), "limitations": world.get("limits", [])}))
        elif key in ("cross_cutting_shortcomings", "next_steps") and isinstance(value, list) and all(isinstance(x, dict) for x in value):
            items = []
            for item in value:
                text = item.get("text", item.get("action", ""))
                if item.get("reason"): text += " " + item["reason"]
                reference = item.get("evidence", {}).get("episode_id", "")
                if reference: text += "（" + reference + "）"
                items.append('<li>%s</li>' % evidence_text(text))
            body = '<ul>%s</ul>' % ''.join(items)
        elif key == "evidence_stages" and isinstance(value, list):
            body = '<div class="scroll"><table><thead><tr><th>研究阶段</th><th>实际做到什么</th><th>证据</th></tr></thead><tbody>'
            for stage in value:
                if not isinstance(stage, dict): continue
                refs = stage.get("test_ids", []) + stage.get("evidence_ids", [])
                body += '<tr><td>%s</td><td>%s</td><td class="caption">%s</td></tr>' % (esc(stage.get("stage", "")), esc(stage.get("assessment", "")), '<br>'.join(esc(x) for x in refs))
            body += '</tbody></table></div>'
        elif isinstance(value, list) and all(isinstance(v, str) for v in value):
            body = "<ul>%s</ul>" % "".join("<li>%s</li>" % evidence_text(v) for v in value)
        else:
            body = prose(value)
        parts.append("<h4>%s</h4>%s" % (esc(title), body))
    return "".join(parts)


def render_world(world):
    distractions = "".join('<li>%s</li>' % esc(x) for x in world["distractors"])
    return '<article class="world" id="world-%s"><div class="world-top"><span class="eyebrow">虚拟实验室</span><h3>%s</h3><p class="subtitle">%s</p></div><p>%s</p><div class="rule"><h4>预埋规律，用直白的话说</h4><p>%s</p></div><details class="world-detail"><summary>如何隐藏 · 干扰项 · 可用操作 · 适用范围</summary><h4>如何隐藏</h4><p>%s</p><h4>容易误判的地方</h4><ul>%s</ul><h4>模型能做什么</h4><p>%s</p><h4>能看到什么</h4><p>%s</p><p class="caption">%s</p><h4>控制与成本</h4><p>%s</p><h4>有信息量的下一次实验</h4><p>%s</p><p class="limit"><b>局限：</b>%s</p></details><a class="textlink" href="#cases-%s">查看该环境的研究运行 ↓</a></article>' % tuple(esc(x) if i not in (6,) else x for i,x in enumerate([
        world["id"],world["name"],world["subtitle"],world["setup"],world["hidden_rules"],world["how_hidden"],distractions,world["actions"],world["observations"],world["noise"],world["controls"],world["informative_test"],world["limits"],world["id"]]))


CSS = r'''
:root{--ink:#172a36;--muted:#617482;--line:#dce5e9;--paper:#f3f6f5;--card:#fff;--teal:#006b62;--blue:#285fa4;--red:#9b3940}*{box-sizing:border-box}html{scroll-behavior:smooth;scroll-padding-top:24px}body{margin:0;background:var(--paper);color:var(--ink);font:15px/1.75 system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif}a{color:var(--teal);text-decoration:none}a:hover{text-decoration:underline}.wrap{max-width:1240px;margin:auto;padding:36px 28px 72px}.hero{background:#142e39;color:#fff;padding:44px 0 32px}.hero .wrap{padding-top:0;padding-bottom:0}.eyebrow{font-size:11px;letter-spacing:1.6px;text-transform:uppercase;font-weight:750;color:#83d4c0}.hero h1{font-size:38px;line-height:1.25;margin:12px 0}.hero p{max-width:850px;color:#d0e1e3;font-size:17px}.hero nav{display:flex;flex-wrap:wrap;gap:12px 24px;margin-top:24px}.hero a{color:#9ce4d4}.hero-meta{font-size:12px!important;color:#b0c9cf!important}.section-title{display:flex;align-items:baseline;justify-content:space-between;gap:20px;margin-top:36px}.section-title h2{font-size:25px;margin:0}.muted,.caption{color:var(--muted)}.caption{font-size:12px}.notice{background:#e8f0ec;border-left:4px solid var(--teal);padding:17px 20px;border-radius:0 10px 10px 0;margin:22px 0}.metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin:24px 0}.metric{background:white;border:1px solid var(--line);border-radius:12px;padding:20px}.metric strong{display:block;font-size:29px;line-height:1.25}.metric span{font-size:12px;color:var(--muted)}.metric p{font-size:12px;margin:8px 0 0;color:var(--muted)}.world-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px;margin:22px 0}.world{border:1px solid var(--line);background:white;border-radius:16px;padding:25px;display:flex;flex-direction:column;min-width:0}.world:last-child{grid-column:1/-1}.world-top .eyebrow{color:var(--teal)}.world h3{font-size:24px;margin:6px 0 4px}.subtitle{font-weight:650;color:var(--muted);margin:0}.world p{margin:10px 0}.rule{background:#eef5f2;border-radius:10px;padding:16px;margin:8px 0 14px}.rule h4{color:var(--teal);margin:0}.world-detail h4{margin:18px 0 5px}.world-detail ul{padding-left:21px}.limit{border-left:3px solid #c7ac79;padding-left:13px;background:#faf8f1}.textlink{font-size:13px;font-weight:700;margin-top:auto;padding-top:14px}.world-detail{margin-bottom:12px}details>summary{cursor:pointer;list-style-position:outside}details>summary:hover{color:var(--teal)}.scroll{overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:13px;margin:15px 0;background:white}th{background:#eaf0f2;color:#465d69;font-size:12px;text-align:left}td,th{padding:12px 14px;border-bottom:1px solid var(--line);vertical-align:top}td:first-child{font-weight:650}.summary-table{border:1px solid var(--line);border-radius:12px;overflow:hidden}.process{display:grid;grid-template-columns:repeat(4,1fr);gap:13px;margin:20px 0}.process>div{padding:18px;border-top:3px solid var(--teal);background:white;border-radius:0 0 8px 8px}.process b{display:block;margin-bottom:6px}.process p{font-size:13px;margin:0;color:var(--muted)}.action-list{display:flex;flex-wrap:wrap;gap:8px}.action-list code{background:white;border:1px solid var(--line);border-radius:7px;padding:5px 10px;font-size:12px}code{font-family:ui-monospace,monospace}.case-group{margin-top:30px}.case-group h3{font-size:21px}.episode{margin:12px 0;background:white;border:1px solid var(--line);border-radius:13px;overflow:hidden}.episode>summary{padding:18px 22px;display:flex;align-items:center;justify-content:space-between;gap:16px;list-style:none}.episode>summary:before{content:"＋";color:var(--teal);font-size:18px}.episode[open]>summary:before{content:"−"}.episode[open]>summary{background:#edf4f1;border-bottom:1px solid var(--line)}.episode-title{flex:1;min-width:0}.episode-title b{display:block;overflow-wrap:anywhere}.episode-title span{display:block;color:var(--muted);font-size:12px}.episode-body{padding:22px}.episode-body h3{font-size:19px;margin:25px 0 12px}.episode-body h3:first-child{margin-top:0}.badge{font-size:11px;border-radius:6px;padding:3px 9px;display:inline-block;line-height:1.6;white-space:normal}.positive{background:#dff1e9;color:#066746}.negative{background:#fae6e5;color:var(--red)}.neutral{background:#e9eef3;color:#496073}.negative-text{color:var(--red)}.timeline{list-style:none;margin:0;padding:0 0 0 18px;border-left:2px solid #ccdcd7}.timeline li{position:relative;border-bottom:1px solid var(--line);padding:0 0 18px 12px;margin-bottom:18px}.timeline li:before{content:"";position:absolute;left:-25px;top:7px;width:12px;height:12px;border-radius:50%;background:#438d7b;border:3px solid white}.step-heading{display:flex;gap:12px;align-items:center}.round{font-weight:750;font-size:12px}.prose{white-space:pre-wrap;overflow-wrap:anywhere}.step-detail{font-size:13px}.step-detail summary,.subdetail summary{font-size:12px;color:var(--muted)}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f3f6f7;border-radius:8px;padding:16px;font:12px/1.65 ui-monospace,monospace;max-height:520px;overflow:auto}.test{background:#f8fbfa;border:1px solid #d8e5df;border-radius:12px;padding:18px;margin:15px 0}.test-top{display:flex;justify-content:space-between;gap:16px;align-items:center}.test h4{font-size:16px;margin:0}.test h5{margin:15px 0 5px}.test-stats{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin:16px 0}.test-stats>div{background:white;padding:14px;border-radius:8px;border:1px solid var(--line)}.test-stats span{font-size:12px;color:var(--muted);display:block}.test-stats strong{font-size:19px;overflow-wrap:anywhere}.empty{color:var(--muted);border:1px dashed #bccdca;border-radius:9px;padding:15px}.placeholder{background:#f8faf9;color:var(--muted)}.stop{padding:10px;background:#fff6ed;border-radius:7px;font-size:13px}.review-card{background:white;border-radius:13px;border:1px solid var(--line);padding:22px}.toolbar{display:flex;flex-wrap:wrap;gap:10px;margin:18px 0}.toolbar button{font:inherit;font-size:12px;background:white;border:1px solid #b9cdc6;border-radius:7px;padding:7px 13px;cursor:pointer;color:var(--teal)}footer{font-size:12px;color:var(--muted);border-top:1px solid var(--line);margin-top:36px;padding-top:18px}section[id],article[id]{scroll-margin-top:20px}@media(max-width:760px){.wrap{padding:24px 16px 50px}.hero{padding:30px 0 25px}.hero h1{font-size:29px}.hero p{font-size:15px}.metrics,.process{grid-template-columns:repeat(2,1fr)}.metric{padding:15px}.metric strong{font-size:24px}.world-grid{grid-template-columns:1fr}.world:last-child{grid-column:auto}.world{padding:20px}.episode>summary{padding:15px 13px;flex-wrap:wrap}.episode>summary>.badge{margin-left:28px}.episode-body{padding:15px}.test-stats{grid-template-columns:1fr}.test{padding:13px}.test-top{align-items:flex-start;flex-direction:column}.section-title{display:block}.section-title h2{font-size:22px}.world h3{font-size:22px}td,th{padding:10px}.summary-table table{min-width:760px}}@media print{body{background:white}.hero{background:white;color:#172a36}.hero p,.hero a,.hero .eyebrow{color:#496073}.wrap{max-width:none;padding:20px}.toolbar,nav{display:none}.world,.episode,.test{break-inside:avoid}.world-grid{display:block}.world{margin-bottom:15px}pre{max-height:none}.badge{border:1px solid #aaa}}
'''


def render(data, catalog):
    data = sanitize(data)
    worlds = catalog["worlds"]
    names = {w["id"]: w["name"] for w in worlds}
    episodes = data["episodes"]
    ledger = data.get("ledger") or {}
    tests = [t for e in episodes for t in as_list(e.get("tests")) if isinstance(t, dict)]
    completed = sum(e.get("status") in COMPLETE for e in episodes)
    support = sum(t.get("outcome") in SUPPORTED for t in tests)
    refuted = sum(t.get("outcome") in REFUTED for t in tests)
    uncertain = sum(t.get("outcome") == "inconclusive" for t in tests)
    started = ledger.get("started_attempts")
    limit = ledger.get("attempt_limit", catalog["request_cap"])
    updated = data.get("updated_at") or datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    commit = str(data.get("source_commit") or "待冻结")
    rows, cases = [], []
    for world in worlds:
        selected = [e for e in episodes if e.get("environment") == world["id"]]
        selected_tests = [t for e in selected for t in as_list(e.get("tests")) if isinstance(t, dict)]
        ns = sum(t.get("outcome") in SUPPORTED for t in selected_tests)
        nr = sum(t.get("outcome") in REFUTED for t in selected_tests)
        ni = sum(t.get("outcome") == "inconclusive" for t in selected_tests)
        requests = [e.get("model_requests") for e in selected]
        requests_value = sum(requests) if requests and all(isinstance(x, int) for x in requests) else "—"
        rows.append('<tr><td><a href="#world-%s">%s</a></td><td>3 × 2 = 6</td><td>%d / %d</td><td>%s</td><td>%d</td><td>%d / %d / %d</td><td><a href="#cases-%s">展开过程 ↓</a></td></tr>' % (esc(world["id"]),esc(world["name"]),sum(e.get("status") in COMPLETE for e in selected),len(selected),esc(requests_value),len(selected_tests),ns,nr,ni,esc(world["id"])))
        rendered = "".join(render_episode(e, world["name"], i) for i,e in enumerate(selected, 1))
        pending = max(0, 6-len(selected))
        for i in range(pending):
            rendered += '<details class="episode placeholder" data-world="%s"><summary><span class="episode-title"><b>计划运行 · %s · %d</b><span>尚未提供运行记录，不计为失败或科学无定论。</span></span>%s</summary><div class="episode-body"><p>等待运行及公开结果。每环境计划3个实例，每个实例独立运行2次。</p></div></details>' % (esc(world["id"]),esc(world["name"]),len(selected)+i+1,badge("pending"))
        cases.append('<section class="case-group" id="cases-%s"><h3>%s <span class="caption">%d条已记录运行 / 6条计划</span></h3>%s</section>' % (esc(world["id"]),esc(world["name"]),len(selected),rendered))
    unknown = [e for e in episodes if e.get("environment") not in names]
    if unknown:
        cases.append('<section class="case-group"><h3>未匹配环境的公开记录</h3>%s</section>' % "".join(render_episode(e,str(e.get("environment","未知")),i) for i,e in enumerate(unknown,1)))
    review = data.get("review")
    review_html = render_review(review) if review else '<p>尚无正式科学复核结论。下方可查看模型原始研究步骤、冻结预测、独立新观测与最终解释；不能根据工具调用次数或单个容易读出自动认定深度发现。</p>'
    cohort = data.get("cohort") or {}
    cohort_requests = sum(e.get("model_requests", 0) for e in episodes)
    cohort_html = '<div class="notice"><b>%s</b>%s<p>本页请求：%d；每次运行最多%s轮。两版使用不同新实例，不能把完成率差异解释成修复的因果效果。</p><p><a href="index.html">修正版研究流程（v0.3）</a> · <a href="original.html">原始研究流程（v0.2，保留全部失败）</a></p></div>' % (esc(cohort.get("title", "独立报告的研究运行")), prose(cohort.get("description", "")), cohort_requests, esc(cohort.get("round_limit", 24)))
    api_details = '<details class="subdetail"><summary>查看API调用账本摘要</summary>%s</details>' % prose(ledger)
    embedded = json.dumps({"report":data,"environment_introductions":catalog},ensure_ascii=False,allow_nan=False).replace("<","\\u003c").replace(">","\\u003e").replace("&","\\u0026")
    header = '<header class="hero"><div class="wrap"><span class="eyebrow">Scientists’ Last Exam · Prospective Research Pilot</span><h1>在新世界里，GPT 怎样做研究</h1><p>先建立解释，再冻结预测，最后用新实验检验。这里保留支持、反例、修订与未知，不要求模型复述预埋机制，也不把研究压成一个总分。</p><p class="hero-meta">状态：%s · 更新：%s · 协议：%s · 运行源码：%s</p><nav><a href="#overview">当前进度</a><a href="#worlds">五个实验室</a><a href="#workflow">研究与验证方式</a><a href="#cases">逐次发现过程</a><a href="#review">结论与不足</a><a href="../sle-env-pilot-20261003/index.html">此前探索报告 ↗</a></nav></div></header>' % (esc(label(data.get("status","planned"))),esc(updated),esc(data.get("protocol","待提供")),esc(commit[:12]))
    metrics = '<div class="metrics"><div class="metric"><strong>%d / 30</strong><span>研究已提交 / 计划运行</span><p>当前有%d条运行记录；提交不等于科学成功。</p></div><div class="metric"><strong>%s / %s</strong><span>API请求已启动 / 硬上限</span><p>包括失败尝试；以共享账本为准。</p></div><div class="metric"><strong>%d</strong><span>已完成的前瞻检验</span><p>计量单位是检验，不是世界或发现。</p></div><div class="metric"><strong>%d · %d · %d</strong><span>局部支持 · 反驳 · 无法判定</span><p>仅对应预先选择的读出及容差。</p></div></div>' % (completed,len(episodes),esc(started if started is not None else "待同步"),esc(limit),len(tests),support,refuted,uncertain)
    overview = '<section id="overview"><div class="section-title"><h2>当前进度</h2><span class="caption">5个环境 × 3个实例 × 每实例2次运行</span></div>%s<div class="notice"><b>这是一轮探索性试验。</b>环境难度尚未标定，三个实例不能可靠估计总体发现率。API完成、研究提交、预测获得局部支持、机制解释成立是不同层次；本报告分别保留证据，不沿用此前0–100综合分。</div><div class="scroll summary-table"><table><thead><tr><th>环境</th><th>计划实例×重复</th><th>已提交 / 已记录</th><th>模型请求</th><th>前瞻检验</th><th>支持 / 反驳 / 无定论</th><th>详细记录</th></tr></thead><tbody>%s</tbody></table></div>%s</section>' % (cohort_html + metrics,"".join(rows),api_details)
    worlds_html = '<section id="worlds"><div class="section-title"><h2>五个实验室：能做什么，内部藏了什么</h2></div><p class="muted">以下预埋规律供报告读者理解实验设计。研究时，模型只看到仪器说明和自己取得的观测；没有获得这些隐藏机制介绍。</p><div class="world-grid">%s</div></section>' % "".join(render_world(w) for w in worlds)
    workflow = '<section id="workflow"><div class="section-title"><h2>一条可核查的研究路径</h2></div><div class="process"><div><b>01 · 形成解释</b><p>从已取得的观测出发，记录问题、证据和待排除的解释。</p></div><div><b>02 · 冻结预测</b><p>保存候选代码与参数，预先选新实验、读出、容差及重复次数。</p></div><div><b>03 · 获得新观测</b><p>独立准备和测量；按已固定的统计规则计算区间，不在看到结果后改容差。</p></div><div><b>04 · 保留结果</b><p>支持、反驳或无法判定都留下记录；修订后需要新的前瞻实验。</p></div></div><p><b>环境调用方式：</b>当前通过运行器的JSON动作调用，不是已部署的MCP服务器。不同环境拥有各自的实验spec，分析与预测代码在隔离环境中运行。</p><div class="action-list"><code>experiments → 取得公开观测</code><code>analyze → 分析与保存模型</code><code>preregister → 冻结并执行前瞻检验</code><code>finish → 提交结论与证据</code></div><p class="caption">单模型检验无需编造第二个解释；双模型比较仍需复核候选是否合理、差异是否涉及科学问题。生态调查使用相关的有限面板比例及保守方差界，不能套用独立高斯读数假设。已知仪器恒等式、只预测空白或单个易读出，不能自动证明机制发现。</p></section>'
    case_html = '<section id="cases"><div class="section-title"><h2>逐次研究：保留发现的真实顺序</h2></div><p class="muted">每个案例是一整次研究运行，包含多轮实验。展开后先看实验轨迹，再看提前预测与新观测，最后看模型结论。两次重复用于观察同一实例的运行差异；不能当成两个独立世界。</p><div class="toolbar"><button type="button" id="expand">展开全部研究运行</button><button type="button" id="collapse">收起全部研究运行</button></div>%s</section>' % "".join(cases)
    review_section = '<section id="review"><div class="section-title"><h2>结论、不足与下一步</h2></div><div class="review-card">%s</div></section>' % review_html
    footer = '<footer>单文件离线报告：内容、样式与已清理JSON均已内嵌；不加载外部脚本或字体。源代码与预埋规律不进入候选分析环境。<br>此前报告与本轮协议、预算和实例不同，应分别阅读；本轮不提供自动发现深度分或通用模型排名。</footer>'
    script = '<script>document.getElementById("expand").addEventListener("click",function(){document.querySelectorAll("details.episode").forEach(function(x){x.open=true;});});document.getElementById("collapse").addEventListener("click",function(){document.querySelectorAll("details.episode").forEach(function(x){x.open=false;});});function revealCase(){var x=document.getElementById(location.hash.slice(1));if(x&&x.matches("details.episode")){x.open=true;x.scrollIntoView();}}window.addEventListener("hashchange",revealCase);revealCase();</script>'
    return '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>%s</title><style>%s</style></head><body>%s<main class="wrap">%s%s%s%s%s%s</main><script type="application/json" id="report-data">%s</script>%s</body></html>' % (esc(catalog["title"]),CSS,header,overview,worlds_html,workflow,review_section,case_html,footer,embedded,script)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data",type=Path,default=HERE/"data.json")
    parser.add_argument("--output",type=Path,default=HERE/"index.html")
    parser.add_argument("--worlds",type=Path,default=HERE/"worlds.json")
    args = parser.parse_args()
    data = json.loads(args.data.read_text(encoding="utf-8"))
    catalog = json.loads(args.worlds.read_text(encoding="utf-8"))
    result = render(data,catalog)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(result,encoding="utf-8")
    print("Rendered self-contained report: %s (%d bytes)" % (args.output,len(result.encode("utf-8"))))


if __name__ == "__main__":
    main()

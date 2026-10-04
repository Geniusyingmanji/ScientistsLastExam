#!/usr/bin/env python3
"""Render a standalone 12-world report from public, curated evidence only.

Optional --unified-data accepts sle-unified-public-1 campaign aggregates. Missing
scores remain missing: historical scores never populate the unified score table.
No model calls, private traces, seeds or simulator targets are read.
"""
import argparse
import copy
import hashlib
import html
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
NAMES = {
    "microecology": "微生态（三菌株）", "coupled_oscillators": "耦合振子",
    "reaction_kinetics": "反应动力学", "heat_transport": "热输运",
    "gene_regulation": "基因调控", "ising_spin": "伊辛自旋",
    "hysteresis_material": "材料滞回", "molecular_forces": "分子作用力",
    "climate_response": "气候响应", "catalyst_aging": "催化剂老化",
    "field_ecology": "野外生态", "phase_equilibria": "材料相图",
}

def esc(value):
    return html.escape(str(value), quote=True)


def para(value, cls=""):
    return '<p%s>%s</p>' % ((' class="%s"' % cls) if cls else '', esc(value)) if value else ''


def items(values):
    return '<ul>' + ''.join('<li>%s</li>' % esc(v) for v in values) + '</ul>' if values else ''


def detail(title, body):
    return '<details><summary>%s</summary><div class="detail-body">%s</div></details>' % (esc(title), body)


def score(value):
    return '—' if value is None else '%.1f' % value


def display_time(value):
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00')).astimezone(
            ZoneInfo('Asia/Shanghai')).strftime('%Y-%m-%d %H:%M:%S（UTC+8）')
    except (ValueError, TypeError, AttributeError):
        return value


def validate_campaign(data):
    if data.get('schema') != 'sle-unified-public-1':
        raise ValueError('Expected sanitized schema sle-unified-public-1')
    if data.get('planned_episodes', 72) != 72 or data.get('call_cap_per_episode', 16) != 16:
        raise ValueError('This report expects the frozen 72-episode / 16-call campaign')
    unknown = set(data.get('by_environment', {})) - set(NAMES)
    if unknown:
        raise ValueError('Unknown campaign environments: %r' % unknown)
    for env, row in data.get('by_environment', {}).items():
        if row.get('planned', 6) != 6:
            raise ValueError('%s: expected six planned episodes' % env)
        for key in ('started', 'settled', 'completed', 'failed', 'infrastructure_failures', 'scored_runs'):
            value = row.get(key, 0)
            if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= 6:
                raise ValueError('%s.%s must be an integer in [0, 6]' % (env, key))
        if row.get('settled', 0) > row.get('started', 0):
            raise ValueError('%s: settled exceeds started' % env)
        for key in ('score_mean', 'condition_score', 'intervention_score', 'claim_score', 'model_only_score_mean'):
            value = row.get(key)
            if value is not None and (isinstance(value, bool) or not isinstance(value, (float, int))
                                      or not math.isfinite(value) or not 0 <= value <= 100):
                raise ValueError('%s.%s must be null or a finite score in [0, 100]' % (env, key))
        component_keys = ('condition_score', 'intervention_score', 'claim_score')
        if row.get('score_mean') is not None and all(row.get(k) is not None for k in component_keys):
            weighted = sum(w * row[k] for w, k in zip((.5, .3, .2), component_keys))
            if abs(weighted - row['score_mean']) > .051:
                raise ValueError('%s: weighted component score inconsistent' % env)
    return data


def normalize(old, frontier, worlds, summary):
    old_catalog = {w['id']: w for w in old['notes']['environment_catalog']['worlds']}
    dossiers = {w['id']: w for w in old['notes']['discovery_dossier']['worlds']}
    new_catalog = {w['id']: w for w in worlds['worlds']}
    new_reviews = {w['environment']: w for w in frontier['review']['worlds']}
    historical = {}
    for cohort in old['cohorts']:
        if cohort['role'] in ('formal', 'expansion'):
            for env, row in cohort['by_environment'].items():
                historical[env] = dict(kind='historical_prediction_score', score=row['mean_score'],
                    protocol=cohort['score_protocol'], completed=row['completed_runs'],
                    denominator=row['healthy_runs'], rounds=cohort['public_limits']['rounds'])
    for env, row in summary['repair']['by_environment'].items():
        outcomes = row['test_outcomes']
        assert sum(outcomes.values()) == row['completed_tests']
        supported = outcomes.get('scoped_predictive_adequacy', 0)
        distinguished = outcomes.get('scoped_predictive_discrimination', 0)
        historical[env] = dict(kind='historical_prospective_support_index',
            score=100 * (supported + distinguished) / row['completed_tests'],
            completed=row['statuses'].get('completed', 0), denominator=row['episodes'],
            tests=row['completed_tests'], supported=supported, distinguished=distinguished,
            outcomes=outcomes, protocol=frontier['protocol'])
    catalog = []
    for env, name in NAMES.items():
        if env in old_catalog:
            w, d = old_catalog[env], dossiers[env]
            stories = d.get('stories', [])
            catalog.append(dict(id=env, name=name, setup=w['question'], hidden_rules=w['mechanism'],
                how_hidden=w['hidden'], distractors=[w['confounds']], actions=w['actions'],
                result=w['result'], mechanism_detail=w.get('mechanism_detail'),
                evidence_summary=d['overall'], stories=stories,
                shortcomings=d.get('shortcomings', []), historical=historical[env],
                source='sle-env-pilot-20261003/index.html#world-' + env,
                evidence_origin='历史评测：原有七环境', evidence_updated=old['generated_at_utc']))
        else:
            w, r = new_catalog[env], new_reviews[env]
            episodes = [dict(episode_id=e['episode_id'], status=e['status'], review=e.get('review', {}))
                        for e in frontier['episodes'] if e['environment'] == env]
            catalog.append(dict(id=env, name=name, setup=w['setup'], hidden_rules=w['hidden_rules'],
                how_hidden=w['how_hidden'], distractors=w['distractors'], actions=w['actions'],
                observations=w['observations'], noise=w['noise'], controls=w['controls'],
                informative_test=w['informative_test'], result=r['summary'], evidence_summary=r['summary'],
                supported=r.get('supported', []), shortcomings=r.get('shortcomings', []),
                limits=r.get('limits', []) + [w['limits']], episodes=episodes,
                historical=historical[env], source='sle-new-frontier-20261003/index.html#world-' + env,
                evidence_origin='历史评测：前瞻研究流程 v0.3', evidence_updated=frontier['updated_at']))
    assert len(catalog) == 12
    return catalog


def render_world(w, campaign_row, episodes=()):
    env = w['id']
    parts = ['<article class="world" id="world-%s"><div class="eyebrow">%s</div><h2>%s</h2>' %
             (esc(env), esc(env.replace('_', ' ')), esc(w['name'])), para(w['setup'])]
    parts += ['<div class="two-col"><section><h3>预埋规律</h3>', para(w['hidden_rules']),
              '</section><section><h3>如何藏起来</h3>', para(w['how_hidden']), '</section></div>']
    body = '<h4>干扰项与辨识困难</h4>' + items(w['distractors']) + '<h4>实验接口</h4>' + para(w['actions'])
    for key, title in [('observations', '读数'), ('noise', '测量噪声'), ('controls', '可控范围'),
                       ('informative_test', '有区分力的实验'), ('mechanism_detail', '机制细节')]:
        if w.get(key):
            body += '<h4>%s</h4>%s' % (title, para(w[key]))
    parts.append(detail('仪器、干扰项与实现边界', body))
    if episodes:
        statuses = {'completed': '完成', 'failed': '运行失败', 'invalid_predictor': '预测程序失败',
                    'pending': '待启动', 'running': '运行中', 'exploring': '探索中'}
        rows = []
        for ep in episodes:
            rows.append('<tr><td>实例 %s · 第 %s 次</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>' % (
                esc(ep['instance_index']), esc(ep['repeat_index']),
                esc(statuses.get(ep['status'], ep['status'])), score(ep.get('score')),
                esc(ep.get('requests', 0)), esc(ep.get('observations', 0)),
                esc(ep.get('verified_nonzero_effects', 0)),
                esc(ep.get('infrastructure_failure') or ep.get('stop_reason') or '—')))
        body = '<div class="scroll"><table><thead><tr><th>运行</th><th>状态</th><th>综合分</th><th>模型调用</th><th>实验</th><th>通过效应复验</th><th>结束原因</th></tr></thead><tbody>' + ''.join(rows) + '</tbody></table></div>'
        body += para('效应复验与预测程序验证分别记录。即使存在通过复验的效应，最终程序失败仍按冻结协议将该次主成绩计零；通过项要求区间覆盖复验均值、宽度不超过0.2倍通道尺度，且效应绝对值超过3个标准误。未通过不等于不存在效应，通过数也不等于发现深度。', 'muted')
        cluster_means = []
        for index in (1, 2, 3):
            pair = [ep['score'] for ep in episodes if ep['instance_index'] == index and ep.get('settled')]
            cluster_means.append(mean(pair) if len(pair) == 2 else None)
        if all(value is not None for value in cluster_means):
            body += para('三个独立实例各自的两次平均分：%s。这里展示实例间差异；仅三个实例，不能据此建立稳定排名。' %
                         ' / '.join('%.2f' % value for value in cluster_means), 'muted')
        parts.append(detail('本次补测：6 次运行明细', body))
    discoveries = campaign_row.get('discoveries', [])
    if discoveries:
        parts.append('<h3>本次补测的发现与不足</h3>')
        for d in discoveries:
            ep = next((e for e in episodes if e['episode_id'] == d['episode_id']), {})
            title = '实例 %s · 第 %s 次：%s' % (ep.get('instance_index', '?'), ep.get('repeat_index', '?'),
                    d.get('summary', '').split('。')[0])
            body = para(d.get('summary')) + '<h4>证据支持</h4>' + items(d.get('supported', []))
            body += '<h4>不足与边界</h4>' + items(d.get('limits', [])) + para(d.get('episode_id'), 'muted')
            parts.append(detail(title, body))
    else:
        parts.append(para('统一协议补测：尚无已发布的逐例科学审阅。下方发现来自历史记录。', 'pending'))
    parts += ['<h3>历史发现与不足</h3>', '<span class="badge">%s · 不属于本次补测</span>' % esc(w['evidence_origin']),
              para(w['result'])]
    if w.get('stories'):
        stories = para(w['evidence_summary'])
        for story in w['stories']:
            body = para(story.get('question')) + '<h4>有证据支持</h4>' + para(story.get('supported'))
            body += '<h4>尚未支持</h4>' + para(story.get('not_supported'))
            body += '<ol class="steps">' + ''.join('<li><strong>%s · %s</strong>%s</li>' %
                    (esc(s.get('stage', '')), esc(s.get('round', '')), para(s.get('body')))
                    for s in story.get('steps', [])) + '</ol>'
            body += '<h4>最终交付</h4>' + para(story.get('final_artifact'))
            stories += detail(story['title'] + ' · ' + story['case_id'], body)
        parts.append(detail('展开两条发现过程：假设、实验、反例与交付', stories))
    if w.get('supported'):
        parts.append(items(s['text'] for s in w['supported']))
    if w.get('episodes'):
        body = ''
        for ep in w['episodes']:
            r = ep['review']
            content = para(r.get('summary')) + '<h4>支持什么</h4>' + items(r.get('supported', []))
            content += '<h4>尚未支持什么</h4>' + items(r.get('not_supported', []))
            content += '<h4>不足</h4>' + items(r.get('shortcomings', []))
            content += ''.join('<p><strong>%s：</strong>%s</p>' %
                     (esc(s.get('stage', '')), esc(s.get('assessment', '')))
                     for s in r.get('evidence_stages', []))
            body += detail(ep['episode_id'] + ' · ' + ep['status'], content)
        parts.append(detail('展开全部 6 次历史运行的逐例审阅', body))
    if w.get('shortcomings'):
        body = ''
        for problem in w['shortcomings']:
            if isinstance(problem, dict):
                body += '<h4>%s</h4>' % esc(problem['title'])
                body += para(problem.get('observed')) + para(problem.get('consequence'))
                body += para('改进方向：' + problem['improvement']) if problem.get('improvement') else ''
            else:
                body += para(problem)
        body += items(w.get('limits', []))
        parts.append(detail('局限与需要补上的证据', body))
    if campaign_row.get('model_only_score_mean') is not None:
        parts.append(detail('补充成绩：排除基础设施失败', para('模型成绩 %.1f / 100；仅作辅助解释，不替代包含失败计零的主成绩。' % campaign_row['model_only_score_mean'])))
    h = w['historical']
    if h['kind'] == 'historical_prediction_score':
        body = para('历史综合分 %.1f / 100；有效预测器 %d / %d 个可评分运行；最多 %d 轮。协议 %s。' %
                    (h['score'], h['completed'], h['denominator'], h['rounds'], h['protocol']))
    else:
        body = para('历史支持指数 %.1f / 100；完成 %d / %d 次运行。%d 项已完成自选检验中，%d 项局部预测支持、%d 项特定候选区分。协议 %s。' %
                    (h['score'], h['completed'], h['denominator'], h['tests'], h['supported'], h['distinguished'], h['protocol']))
    body += para('此数值沿用历史口径，不进入统一评分或跨环境排名。')
    body += '<a href="%s">查看来源完整报告</a>' % esc(w['source'])
    parts += [detail('历史成绩与来源（不计入本次总分）', body), '</article>']
    return ''.join(parts)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--unified-data', type=Path, help='Sanitized sle-unified-public-1 aggregate JSON')
    parser.add_argument('--review-data', type=Path, help='Curated sle-unified-review-1 findings, tied to closed report hashes')
    parser.add_argument('--output-dir', type=Path, default=HERE)
    args = parser.parse_args()
    paths = [HERE / p for p in ('sle-env-pilot-20261003/data.json', 'sle-new-frontier-20261003/data.json',
                               'sle-new-frontier-20261003/worlds.json', 'sle-new-frontier-20261003/summary.json')]
    old, frontier, worlds, summary = [json.loads(p.read_text()) for p in paths]
    catalog = normalize(old, frontier, worlds, summary)
    campaign = validate_campaign(json.loads(args.unified_data.read_text())) if args.unified_data else {
        'schema': 'sle-unified-public-1', 'protocol': 'sle-unified-score-1.0', 'model': 'gpt-5.6-sol',
        'status': '已选择统一协议并补跑；尚无已发布的补测结果', 'planned_episodes': 72,
        'call_cap_per_episode': 16, 'by_environment': {}, 'updated_at': None}
    by_env = copy.deepcopy(campaign.get('by_environment', {}))
    review = None
    if args.review_data:
        review = json.loads(args.review_data.read_text())
        if review.get('schema') != 'sle-unified-review-1' or review.get('protocol') != campaign.get('protocol'):
            raise ValueError('Review schema/protocol mismatch')
        endpoints = {e['episode_id']: e for e in campaign.get('episodes', [])}
        seen = set()
        for finding in review.get('episodes', []):
            eid = finding['episode_id']
            ep = endpoints.get(eid, {})
            if eid in seen or not ep.get('settled') or ep.get('report_sha256') != finding.get('report_sha256'):
                raise ValueError('Review does not match a unique closed report: ' + eid)
            seen.add(eid)
            by_env[ep['environment']].setdefault('discoveries', []).append(finding)
    settled = sum(row.get('settled', 0) for row in by_env.values())
    started = sum(row.get('started', 0) for row in by_env.values())
    scored = sum(row.get('scored_runs', 0) for row in by_env.values())
    completed = sum(row.get('completed', 0) for row in by_env.values())
    total_infrastructure_failures = sum(row.get('infrastructure_failures', 0) for row in by_env.values())
    ready = all(by_env.get(env, {}).get('settled', 0) == 6 and
                by_env.get(env, {}).get('scored_runs', 0) == 6 and
                by_env.get(env, {}).get('score_mean') is not None for env in NAMES)
    total = mean(by_env[env]['score_mean'] for env in NAMES) if ready else None
    model_only_total = mean(by_env[env]['model_only_score_mean'] for env in NAMES) if ready and all(
        by_env[env].get('model_only_score_mean') is not None for env in NAMES) else None
    generated = datetime.now(timezone.utc).isoformat()
    result = dict(schema='sle-unified-report-1', generated_at_utc=generated,
                  source_sha256={str(p.relative_to(HERE)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
                  campaign=campaign, total_score=total, total_score_ready=ready, worlds=catalog,
                  model_only_macro_score=model_only_total,
                  completion=dict(valid=completed, planned=72, settled=settled,
                                  infrastructure_failures=total_infrastructure_failures),
                  score_formula='0.50 * condition_score + 0.30 * intervention_score + 0.20 * claim_score',
                  score_unit='0–100; all six planned episodes per environment; failed/no-submission/API-failed episodes contribute zero at closure; equal environment weighting after all 72 settle',
                  historical_evidence_notice='All catalog discoveries without an explicit unified campaign label are historical.')
    if args.unified_data:
        result['campaign_source_sha256'] = hashlib.sha256(args.unified_data.read_bytes()).hexdigest()
    if review is not None:
        result['review'] = review
        result['review_source_sha256'] = hashlib.sha256(args.review_data.read_bytes()).hexdigest()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / 'overview-data.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    rows = []
    for env, name in NAMES.items():
        row = by_env.get(env, {})
        done = row.get('settled', 0)
        run_state = '待评测' if not row.get('started', 0) else ('已结束' if done == 6 else '进行中')
        failures = row.get('failed', 0)
        infra = row.get('infrastructure_failures', 0)
        run_state += '<br><small>未完成 %d（其中基础设施 %d）</small>' % (failures, infra) if failures or infra else ''
        suffix = '' if row.get('scored_runs', 0) == 6 else ' <small>阶段值</small>'
        total_cell = score(row.get('score_mean')) + (suffix if row.get('score_mean') is not None else '')
        rows.append('<tr><td><a href="#world-%s">%s</a></td><td>%s</td><td>%s</td><td>%s</td>'
                    '<td><strong>%s</strong></td><td>%d / 6<br><small>计分 %d / 6</small></td><td>%s</td></tr>' %
                    (env, name, score(row.get('condition_score')), score(row.get('intervention_score')),
                     score(row.get('claim_score')), total_cell, done, row.get('scored_runs', 0), run_state))
    cards = ''.join(render_world(w, by_env.get(w['id'], {}),
                    [ep for ep in campaign.get('episodes', []) if ep['environment'] == w['id']]) for w in catalog)
    if ready:
        rows.append('<tr><td><strong>12 环境等权平均</strong></td><td>%s</td><td>%s</td><td>%s</td>'
                    '<td><strong>%.2f</strong></td><td>72 / 72</td><td>有效完成 %d / 72</td></tr>' %
                    (score(mean(by_env[e]['condition_score'] for e in NAMES)),
                     score(mean(by_env[e]['intervention_score'] for e in NAMES)),
                     score(mean(by_env[e]['claim_score'] for e in NAMES)), total, completed))
    total_label = ('%.2f / 100' % total) if total is not None else '待评测' if not started else '尚未出齐'
    timestamp = campaign.get('updated_at') or '尚无补测数据'
    policy = campaign.get('score_policy', {})
    policy_html = detail('运行与计分政策', '<pre>%s</pre>' % esc(json.dumps(policy, ensure_ascii=False, indent=2))) if policy else ''
    page = '''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>SLE · 12 环境统一评测与发现报告</title><style>
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:#f4f5ef;color:#173d3a;font:16px/1.75 system-ui,-apple-system,sans-serif}main{max-width:1180px;margin:auto;padding:36px 24px 80px}h1{font-size:clamp(27px,4vw,42px);line-height:1.3;margin:14px 0}h2{font-size:25px;margin:10px 0 18px}h3{font-size:18px;margin:22px 0 8px}h4{font-size:15px;margin:18px 0 5px}a{color:#07776b;text-underline-offset:3px}p{margin:10px 0 16px}small,.muted{color:#647570;font-size:13px}.eyebrow{font-size:12px;letter-spacing:.14em;color:#65716b;text-transform:uppercase}nav{display:flex;gap:12px 24px;flex-wrap:wrap;margin:20px 0}.metrics{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin:26px 0}.metric{padding:22px;background:#fff;border:1px solid #d9e2d8;border-radius:14px}.metric strong{display:block;font-size:34px;line-height:1.5}.notice{padding:18px 22px;background:#e9eee5;border-left:4px solid #56836c;border-radius:4px;margin:22px 0}.pending{font-size:14px;padding:12px 16px;background:#f2f1e9;border-radius:7px}.scroll{overflow:auto;border-radius:12px;border:1px solid #d9e2d8;margin:22px 0}table{width:100%;border-collapse:collapse;font-size:14px;background:white;min-width:810px}th,td{padding:13px 14px;text-align:left;border-bottom:1px solid #e0e6df;vertical-align:top}th{background:#e7eee4;white-space:nowrap}td:first-child{min-width:140px}.world{margin:24px 0;padding:30px;background:white;border:1px solid #d9e2d8;border-radius:16px;scroll-margin-top:20px}.two-col{display:grid;grid-template-columns:1fr 1fr;gap:28px}.badge{display:inline-block;color:#7c5f25;background:#f3eddc;padding:3px 10px;border-radius:5px;font-size:12px}details{border-top:1px solid #e2e8df;padding:14px 0}summary{cursor:pointer;font-size:15px;font-weight:600}.detail-body{padding:6px 0 4px}li{margin:8px 0}ul,ol{padding-left:23px}.steps p{margin:6px 0 15px}.protocol{padding:24px 30px;background:#fff;border:1px solid #d9e2d8;border-radius:14px}.protocol code{background:#edf1e8;padding:3px 6px}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:13px}footer{margin-top:30px;border-top:1px solid #ccd8ce;padding-top:20px;font-size:13px;color:#65736d}@media(max-width:700px){main{padding:24px 14px}.metrics,.two-col{grid-template-columns:1fr}.metric{padding:15px 20px}.metric strong{font-size:29px}.world,.protocol{padding:20px}nav{gap:10px 18px}}
</style></head><body><main><div class="eyebrow">Scientists’ Last Exam · GPT-5.6</div><h1>12 个科学环境<br>统一评测与发现报告</h1>
<p>从三菌株微生态到分子作用力，12 个环境使用共同的评分公式与评测预算重新检验。本页统一展示环境设定、隐藏规律、每次运行的成绩及科学证据；历史结果另附于各环境详情。</p>
<nav><a href="#scores">统一成绩</a><a href="#protocol">评分与接口</a><a href="#world-microecology">12 个环境详解</a><a href="overview-data.json">完整公开汇总数据</a></nav>
<div class="metrics"><div class="metric">12 环境统一总分<strong>@@TOTAL@@</strong><small>全部 72 次计划运行计分后，按环境等权汇总。</small></div><div class="metric">补测进度<strong>@@SETTLED@@ / 72</strong><small>已启动 @@STARTED@@ 次；已计分 @@SCORED@@ 次。每环境 3 个实例 × 2 次运行。</small></div><div class="metric">每次模型调用上限<strong>16 次</strong><small>12 × 3 × 2，共最多 1,152 次模型调用；实际实验成本另行记录。</small></div></div>
<div class="notice"><strong>@@STATUS@@</strong><br>新成绩表只接收统一协议补测结果。原有七环境的综合分、五环境的支持指数均保留在各环境的历史详情中，不进入新总分。科学发现的深度仍由实验、反例及适用范围的证据说明。</div>
<section id="scores"><h2>统一成绩 · 12 环境使用相同列与权重</h2><div class="scroll"><table><thead><tr><th>环境</th><th>新条件预测<br>50%</th><th>控制条件变化预测<br>30%</th><th>定量声明复验<br>20%</th><th>综合分 / 100</th><th>结束 / 计划</th><th>状态</th></tr></thead><tbody>@@ROWS@@</tbody></table></div><p class="muted">“—”表示尚无该项补测成绩，不代表零分。阶段值仅基于已经计分的运行。主成绩覆盖每环境全部 6 次计划运行：结束后，无有效提交、程序失败与 API／基础设施失败均计 0 分，并分别披露原因；尚未结束的运行保持待定。排除基础设施失败的模型成绩仅作补充。3 个独立实例各重复 2 次，不能视为 6 个独立世界。</p></section>
<section id="protocol" class="protocol"><h2>共同评测协议</h2><p><strong>综合分 = 50% 新条件预测 + 30% 控制条件变化预测 + 20% 定量声明复验。</strong>三个分项均为 0–100 分，这是误差与区间损失转换出的指数，不是正确率或已发现规律的百分比。新条件与控制变化由宿主生成；模型提交冻结的预测程序，并提出最多 3 条开放的定量效应区间，再由宿主用新观测复验；声明分固定按 3 个槽位平均，缺失或重复声明计零。主成绩在全部运行结束后，将每环境全部 6 次计划运行（含失败计零）求均值，再对 12 环境等权平均。它衡量端到端系统表现，不能单独归因于模型能力；排除基础设施失败的模型成绩作为补充披露。</p>
<p>模型可以自由探索、建立任意可执行解释；不按隐藏机制名称或预设答案匹配计分。控制变化在各世界有不同物理含义：野外生态中的栖息地条件变化不自动具有因果干预含义。共同权重也不意味着各领域难度或先验信息相同；原有部分环境在题面公开了方程族，这些先验会保留并披露。</p>
<h3>分数如何计算</h3><p>预测部分逐实验计算保留输出格子的归一化均方根误差，再转成 <code>100 × exp(−误差 / 0.1)</code>，实验间等权。宿主预先排除仅复述已知输入、初始值或仪器约束的输出格子，静态构型编号 0 等有效读数仍保留。</p><p>每条定量声明给出“处理减对照”的平均差的 90% 预测区间。宿主每组独立重复 32 次，区间越窄且越准确分数越高；未覆盖新观测均值时，每单位区间外偏差增加 20 倍损失。先按通道尺度归一化，再使用同样的指数变换。这个有界指数用于汇总数值表现，不能认证机制唯一性。</p>
<h3>环境的工具接口 / MCP</h3><p>环境通过 Python runner 提供结构化 JSON 动作，目前不是独立部署的 MCP server。<code>experiments</code> 获取合法实验观测；<code>analyze</code> 在隔离 Python 中分析已观测数据；计分流程通过 <code>submit</code> 冻结自包含预测程序、量化声明与解释。宿主随后执行私有验证，模型不能查询封存目标、隐藏参数或模拟器源码。</p>
<p>历史前瞻研究流程另有 <code>preregister</code> 和 <code>finish</code>，用于先封存预测、再获取新实验；其中的局部支持、候选区分和反驳是历史科学证据，不换算成本次计分。下方公开的是设计者预埋的机制家族；实际实例的私有 seed、参数和测试目标不会出现在本页。</p>@@POLICY@@
<p class="muted">补测协议：@@PROTOCOL@@ · 模型：@@MODEL@@ · 源码版本：@@COMMIT@@<br>补测数据更新：@@UPDATED@@</p></section>
@@CARDS@@
<footer><strong>来源与复核范围</strong><p>原有七环境：公开环境目录和 14 条精选发现过程；前瞻五环境：公开环境设定、全部 30 次 v0.3 运行的逐例审阅。精选故事用于展示发现路径，不是随机样本或发现率。历史审阅为同模型家族的暂定判断，保留适用范围与不足。</p><nav><a href="sle-env-pilot-20261003/index.html">原有七环境完整档案</a><a href="sle-new-frontier-20261003/index.html">前瞻五环境完整档案</a></nav><p>本页可离线阅读，无外部脚本、字体或网络资源依赖。来源文件 SHA-256 与公开数据存于 overview-data.json。页面生成：@@GENERATED@@</p></footer>
</main></body></html>'''
    status_text = {'frozen': '统一协议已冻结，等待开始补测', 'running': '正在执行 12 环境同口径补测',
                   'completed': '72 次计划运行已结束，统一成绩已发布',
                   'stopped_infrastructure': '因基础设施故障停止后续启动；未完成运行仍保留在计划分母'}
    page = page.replace('<section id="scores"><h2>',
        '<p><strong>有效完成 %d / 72 次%s。</strong>有效完成要求提交可通过验证的预测程序；它不是发现成功率。已结束运行中，基础设施失败 %d 次，其他未完成 %d 次。%s</p><section id="scores"><h2>' %
        (completed, ('（%.1f%%）' % (100 * completed / 72)) if ready else '，其余仍在评测或已失败',
         total_infrastructure_failures, settled - completed - total_infrastructure_failures,
         '' if ready else '全部运行结束后再解释最终完成率。'))
    if ready:
        page = page.replace('每次模型调用上限<strong>16 次</strong><small>12 × 3 × 2，共最多 1,152 次模型调用；实际实验成本另行记录。</small>',
            '有效完成率<strong>%.1f%%</strong><small>%d / 72 次提交有效预测程序。实际模型调用 %d / 1,152 次；每次运行上限 16 次。</small>' %
            (100 * completed / 72, completed, campaign.get('ledger', {}).get('started_attempts', 0)))
    if review is not None:
        page = page.replace('<section id="scores"><h2>',
            '<p class="muted">本次科学证据已逐例审阅 %d 次；审阅为同模型家族的暂定判断。每条摘要绑定对应运行的原始报告 SHA-256，高分和模型自述均不自动认定为机制发现。</p><section id="scores"><h2>' % len(review['episodes']))
        overview = review.get('overview', {})
        if overview:
            page = page.replace('<a href="#protocol">评分与接口</a>',
                '<a href="#findings">发现与下一步</a><a href="#protocol">评分与接口</a>')
            findings = '<section id="findings" class="protocol"><h2>本次评测看到什么</h2>'
            findings += para(overview.get('summary')) + items(overview.get('findings', []))
            findings += '<h3>结论边界</h3>' + items(overview.get('limits', []))
            findings += '<h3>下一步优先改进</h3>' + items(overview.get('next_steps', [])) + '</section>'
            page = page.replace('<section id="protocol" class="protocol">', findings + '<section id="protocol" class="protocol">')
    if model_only_total is not None:
        page = page.replace('<section id="scores"><h2>',
            '<p class="muted">辅助成绩：每个环境排除基础设施失败后再等权平均，为 %.2f / 100。它保留模型程序失败和无效提交，仅用于区分服务可靠性影响，不替代全部计划运行的主成绩。</p><section id="scores"><h2>' % model_only_total)
    replacements = dict(TOTAL=total_label, SETTLED=settled, STARTED=started, SCORED=scored,
                        STATUS=status_text.get(campaign.get('status'), campaign.get('status', '待评测')), ROWS=''.join(rows), CARDS=cards,
                        POLICY=policy_html, PROTOCOL=campaign.get('protocol', '待冻结'),
                        MODEL=campaign.get('model', 'gpt-5.6-sol'), COMMIT=campaign.get('source_commit', '尚未发布'),
                        UPDATED=display_time(timestamp), GENERATED=display_time(generated))
    for key, value in replacements.items():
        page = page.replace('@@%s@@' % key, str(value) if key in ('ROWS', 'CARDS', 'POLICY') else esc(value))
    assert '@@' not in page
    (args.output_dir / 'overview.html').write_text(page)
    print(json.dumps(dict(worlds=len(catalog), settled=settled, scored=scored, total_score=total,
                          output=str(args.output_dir / 'overview.html')), ensure_ascii=False))


if __name__ == '__main__':
    main()

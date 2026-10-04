#!/usr/bin/env python3
"""Paired comparison of sanitized fixed-design campaigns; no private targets."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import html
import json
import math
from pathlib import Path
import random
from statistics import mean

NAMES = {'microecology':'微生态（三菌株）','coupled_oscillators':'耦合振子','reaction_kinetics':'反应动力学',
         'heat_transport':'热输运','gene_regulation':'基因调控','ising_spin':'伊辛自旋','hysteresis_material':'材料滞回',
         'molecular_forces':'分子作用力','climate_response':'气候响应','catalyst_aging':'催化剂老化',
         'field_ecology':'野外生态','phase_equilibria':'材料相图'}
COMPONENTS = ('condition_score','intervention_score','claim_score')


def slot(e):
    return e['environment'], e['instance_index'], e['repeat_index']


def check(data):
    if data['schema'] != 'sle-unified-public-1' or data['planned_episodes'] != 72:
        raise ValueError('Expected fixed 72-episode public campaign')
    expected={(w,i,r) for w in NAMES for i in (1,2,3) for r in (1,2)}
    if len(data['episodes'])!=72 or {slot(e) for e in data['episodes']}!=expected:
        raise ValueError('Missing or duplicated paired slots')
    for e in data['episodes']:
        if e['settled']:
            if not isinstance(e['score'],(int,float)) or not math.isfinite(e['score']) or not 0<=e['score']<=100:
                raise ValueError('Invalid closed score')
            if not e['completed'] and e['score']!=0:
                raise ValueError('Failure must remain zero')
            if not math.isclose(e['score'],sum(e[k]*w for k,w in zip(COMPONENTS,(.5,.3,.2))),abs_tol=1e-8):
                raise ValueError('Score components do not match')
        elif e['score'] is not None:
            raise ValueError('Pending score must remain missing')


def bootstrap_clusters(world_clusters, n=20000):
    """Fixed-world stratified cluster bootstrap; retain both repeats together."""
    rng=random.Random(20261004)
    draws=sorted(mean(mean(rng.choices(values,k=3)) for values in world_clusters) for _ in range(n))
    def q(p):
        index=p*(len(draws)-1);lo=int(index);hi=math.ceil(index)
        return draws[lo]+(draws[hi]-draws[lo])*(index-lo)
    return [q(.025),q(.975)]


def describe(es, complete):
    closed=[e for e in es if e['settled']]
    valid=sum(e['completed'] for e in closed)
    infra=sum(bool(e['infrastructure_failure']) for e in closed)
    out=dict(settled=len(closed),valid=valid,infrastructure_failures=infra,
             statuses=dict(Counter(e['status'] for e in closed)),calls=sum(e['requests'] for e in es),
             provider_models=sorted({m for e in closed for m in e.get('provider_reported_models',[])}),
             effects=sum(e['verified_nonzero_effects'] for e in closed),
             score=mean(e['score'] for e in closed) if complete else None,
             components={k:mean(e[k] for e in closed) if complete else None for k in COMPONENTS})
    out['floor_count']=sum(e['score']<=5 for e in closed) if complete else None
    out['ceiling_count']=sum(e['score']>=95 for e in closed) if complete else None
    return out


def compare(reference,candidate):
    check(reference);check(candidate)
    if reference['protocol']!=candidate['protocol'] or reference['score_policy']!=candidate['score_policy']:
        raise ValueError('Score protocols differ')
    if reference['limits']!=candidate['limits']:
        raise ValueError('Evaluation budgets differ')
    if candidate.get('comparison',{}).get('reference_manifest_sha256')!=reference['manifest_sha256']:
        raise ValueError('Candidate is not bound to this reference')
    if not all(e['settled'] for e in reference['episodes']):
        raise ValueError('Reference must be complete')
    refs={slot(e):e for e in reference['episodes']};cands={slot(e):e for e in candidate['episodes']}
    ready=all(e['settled'] for e in cands.values())
    pairs=[]
    for key,a in refs.items():
        b=cands[key]
        if a['episode_id']!=b['episode_id']:
            raise ValueError('Observation-index noise identities changed')
        pairs.append(dict(environment=key[0],instance=key[1],repeat=key[2],reference=a,candidate=b,
                          delta=b['score']-a['score'] if b['settled'] else None))
    worlds=[];clusters=[];matched=[];model_only=[]
    for w in NAMES:
        ps=[p for p in pairs if p['environment']==w]
        full=all(p['candidate']['settled'] for p in ps)
        row=dict(environment=w,name=NAMES[w],reference=describe([p['reference'] for p in ps],True),
                 candidate=describe([p['candidate'] for p in ps],full),pairs=ps)
        row['delta']=mean(p['delta'] for p in ps) if full else None
        row['cluster_deltas']=[mean(p['delta'] for p in ps if p['instance']==i) for i in (1,2,3)] if full else None
        if full:
            clusters.append(row['cluster_deltas'])
            row['wins_ties_losses']=[sum(p['delta']>1e-9 for p in ps),sum(abs(p['delta'])<=1e-9 for p in ps),sum(p['delta']< -1e-9 for p in ps)]
            eligible=[p for p in ps if not p['reference']['infrastructure_failure'] and not p['candidate']['infrastructure_failure']]
            row['matched_noinfra_pairs']=len(eligible)
            row['matched_noinfra_delta']=mean(p['delta'] for p in eligible) if eligible else None
            matched.append(row['matched_noinfra_delta'])
            healthy=[p['candidate']['score'] for p in ps if not p['candidate']['infrastructure_failure']]
            model_only.append(mean(healthy) if healthy else None)
        worlds.append(row)
    a=describe(list(refs.values()),True);b=describe(list(cands.values()),ready)
    # Equal six runs in every environment makes the episode mean equal the macro.
    delta=b['score']-a['score'] if ready else None
    return dict(schema='sle-paired-comparison-1',protocol=reference['protocol'],ready=ready,
                reference_model=reference['model'],candidate_model=candidate['model'],
                reference=a,candidate=b,worlds=worlds,delta=delta,
                paired_cluster_bootstrap_95=bootstrap_clusters(clusters) if ready else None,
                bootstrap_scope='20,000 fixed-seed draws; resample 3 instance pairs within each fixed world; two repeats averaged; descriptive, not population-wide',
                matched_noinfra_delta=mean(matched) if ready and all(x is not None for x in matched) else None,
                candidate_model_only_macro=mean(model_only) if ready and all(x is not None for x in model_only) else None,
                design=candidate['comparison'],candidate_ledger=candidate['ledger'],candidate_status=candidate['status'])


def esc(x):return html.escape(str(x),quote=True)
def num(x):return '—' if x is None else '%.2f'%x
def signed(x):return '—' if x is None else '%+.2f'%x
def ul(xs):return '<ul>'+''.join('<li>'+esc(x)+'</li>' for x in xs)+'</ul>'
def details(title,body):return '<details><summary>'+esc(title)+'</summary>'+body+'</details>'


def render(d,review=None):
    a,b=d['reference'],d['candidate'];rows=[];cards=[]
    for w in d['worlds']:
        x,y=w['reference'],w['candidate']
        def bar(score,color):
            return '' if score is None else '<span class="bar" style="width:%.3f%%;background:%s"></span>'%(score,color)
        rows.append('<tr><td><a href="#%s">%s</a></td><td>%s%s</td><td>%s%s</td><td><strong>%s</strong></td><td>%d / 6</td><td>%d / 6</td></tr>'%
                    (w['environment'],esc(w['name']),num(x['score']),bar(x['score'],'#7387b2'),num(y['score']),bar(y['score'],'#258570'),signed(w['delta']),x['valid'],y['valid']))
        body='<h3>三个分项</h3><table><tr><th>模型</th><th>新条件 50%</th><th>控制变化 30%</th><th>效应区间 20%</th></tr>'
        for label,z in [('GPT-5.6',x),('DeepSeek V4 Pro',y)]:
            body+='<tr><td>'+label+'</td>'+''.join('<td>'+num(z['components'][k])+'</td>' for k in COMPONENTS)+'</tr>'
        body+='</table><h3>六次配对运行</h3><div class="scroll"><table><tr><th>实例 / 重复</th><th>GPT 分数 / 状态</th><th>V4 分数 / 状态</th><th>V4 − GPT</th><th>调用 GPT / V4</th><th>效应通过 GPT / V4</th></tr>'
        for p in w['pairs']:
            u,v=p['reference'],p['candidate']
            body+='<tr><td>%d / %d</td><td>%s<br><small>%s</small></td><td>%s<br><small>%s</small></td><td>%s</td><td>%d / %d</td><td>%d / %d</td></tr>'%(p['instance'],p['repeat'],num(u['score']),esc(u['status']),num(v['score']),esc(v['status']),signed(p['delta']),u['requests'],v['requests'],u['verified_nonzero_effects'],v['verified_nonzero_effects'])
        body+='</table></div>'
        if w['cluster_deltas']:
            body+='<p>三个实例分别平均两次运行后的分差：'+ ' / '.join(signed(z) for z in w['cluster_deltas'])+'。</p>'
            body+='<p>六次运行胜 / 平 / 负：%s；这六次不独立，不能直接当成六个世界。</p>'%(' / '.join(map(str,w['wins_ties_losses'])))
            body+='<p>分数 ≤5：GPT %d / 6，V4 %d / 6；分数 ≥95：GPT %d / 6，V4 %d / 6。</p>'%(x['floor_count'],y['floor_count'],x['ceiling_count'],y['ceiling_count'])
        if review:
            for r in review.get('worlds',[]):
                if r['environment']==w['environment']:
                    body+='<h3>科学证据与差异来源</h3><p>'+esc(r['summary'])+'</p>'+ul(r.get('findings',[]))+ul(r.get('limits',[]))
        cards.append('<article id="%s"><h2>%s</h2>%s</article>'%(w['environment'],esc(w['name']),details('展开分项、配对运行与证据',body)))
    if d['ready']:
        ci=d['paired_cluster_bootstrap_95']
        conclusion='<p>配对总分差 <strong>%s</strong>；固定十二环境、按独立实例聚类的描述性 95%% bootstrap 区间为 <strong>[%s, %s]</strong>。仅每环境三个独立实例，不能据此建立稳定总体排名。</p>'%(signed(d['delta']),signed(ci[0]),signed(ci[1]))
        conclusion+='<p>排除任一模型发生基础设施故障的配对后，环境等权分差为 %s。DeepSeek 单独排除基础设施故障后的辅助均分为 %s；这些筛选结果不替代主分，也不是故障消除的因果估计。</p>'%(signed(d['matched_noinfra_delta']),num(d['candidate_model_only_macro']))
        conclusion+='<p>整体分数 ≤5：GPT %d/72，V4 %d/72；分数 ≥95：GPT %d/72，V4 %d/72。低分也可能来自程序或 API 失败，不能直接解释为科学任务难度。</p>'%(a['floor_count'],b['floor_count'],a['ceiling_count'],b['ceiling_count'])
    else:
        conclusion=('<p>因基础设施故障停止，未派发的运行保持空缺，不计算72次总分，也不能据此判断模型区分度。</p>' if d['candidate_status']=='stopped_infrastructure' else '<p>评测进行中；尚未计算总分差和区间。已完成环境可先查看六次运行，未结束项保持空缺。</p>')
    if review:
        conclusion+='<h3>审阅结论</h3><p>'+esc(review.get('summary',''))+'</p>'+ul(review.get('findings',[]))+'<h3>边界与下一步</h3>'+ul(review.get('limits',[]))+ul(review.get('next_steps',[]))
    if review and review.get('workflow_metrics'):
        metrics=review['workflow_metrics']
        conclusion+='<h3>差距发生在研究流程的哪一步</h3><div class="scroll"><table><tr><th>过程指标</th><th>GPT-5.6</th><th>DeepSeek V4 Pro</th></tr>'
        for key,label in [('requests','API 请求数'),('experiment_count','实际实验数'),('empty_visible_replies','完整回复但没有可见答案'),('length_stops','输出达到长度上限'),('invalid_actions','无效动作次数'),('analysis_ok','成功执行的分析次数'),('analysis_failed','分析执行失败次数')]:
            conclusion+='<tr><td>%s</td><td>%d</td><td>%d</td></tr>'%(label,metrics['reference'][key],metrics['candidate'][key])
        conclusion+='</table></div><p>这些次数可以重叠，例如同一次回复可能既达到长度上限又形成无效动作。分析执行成功仅表示程序运行成功，不等于科学结论成立。</p>'
    pilot=d['design'].get('transport_pilot')
    if pilot:
        conclusion+='<h3>传输诊断单独保留</h3><p>先前非流式批次已停止：%d 次运行结束，%d 次基础设施失败，共 %d 次请求；未派发后续运行，不存在完整总分。本页展示另外冻结的流式批次，两者不合并。另有 1 次连通性请求和 1 次流式诊断请求，均不计科学成绩。</p>'%(pilot['settled'],pilot['infrastructure_failures'],pilot['calls'])
    if d['design'].get('transport',{}).get('candidate_stream') and not d['design'].get('empty_output_policy'):
        conclusion+='<p><strong>这是修复前的流式试跑，不能用于判断模型区分度。</strong>已发现客户端把完整空答案误标为传输错误；修正后的评测将另行冻结，保留这里的全部记录。</p>'
    client_pilot=d['design'].get('client_pilot')
    if client_pilot:
        conclusion+='<h3>客户端分类修复前的试跑</h3><p>另一次流式试跑结束 %d 次运行、调用 %d 次。旧客户端把没有可见答案的完整回复误标为传输错误，触发停止。这批记录单独保留，不作为科学分数。本次空答案与 GPT 非流式路径一致：消耗一轮无效动作，保留 token 用量，不重试、不使用思考文本作为答案。</p>'%(client_pilot['settled'],client_pilot['calls'])
    monitor=d.get('monitor_status')
    if monitor:
        conclusion=conclusion.replace('评测进行中；尚未计算总分差和区间。已完成环境可先查看六次运行，未结束项保持空缺。','完整结果尚未取回，暂不计算总分差和区间；未派发的运行保持空缺。')
        conclusion='<p><strong>最新远端查询：首轮 12 次后已停止。</strong>查询到 94 次请求，其中 84 次返回、10 次中断；10 次运行失败、2 次未完成，后续 60 次未派发。连接再次中断，完整文件尚未同步，逐例原因和原始报告哈希待核验。以下数据为上一次成功同步的旧快照，不代表当前进度。</p>'+conclusion
    status=('全部 72 次已结束' if d['ready'] else '基础设施故障达到阈值，已停止后续派发' if d['candidate_status']=='stopped_infrastructure' else '进行中 · '+d['candidate_status'])
    if monitor:status='远端已停止；页面计数仍为旧快照，原始结果待同步核验'
    return '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>SLE · GPT-5.6 与 DeepSeek V4 配对评测</title><style>
*{box-sizing:border-box}body{background:#f4f5ef;color:#173d3a;font:16px/1.75 system-ui,sans-serif;margin:0}main{max-width:1180px;margin:auto;padding:36px 24px 70px}h1{font-size:clamp(28px,4vw,42px);line-height:1.3}h2{font-size:23px}h3{font-size:18px}a{color:#07776b}small,.muted{font-size:13px;color:#647570}.metrics{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}.metric,article,.panel{background:#fff;border:1px solid #d9e2d8;border-radius:14px;padding:24px;margin:18px 0}.metric strong{display:block;font-size:32px}.notice{background:#e9eee5;padding:20px;border-left:4px solid #56836c}.scroll{overflow:auto}table{width:100%;min-width:720px;border-collapse:collapse;background:#fff;font-size:14px}td,th{text-align:left;padding:12px;border-bottom:1px solid #d9e2d8;vertical-align:top}th{background:#e7eee4}.bar{display:block;height:6px;margin-top:7px;border-radius:3px}details{margin-top:10px}summary{cursor:pointer;font-weight:600}li{margin:8px 0}nav{display:flex;flex-wrap:wrap;gap:18px}@media(max-width:700px){main{padding:20px 14px}.metrics{grid-template-columns:1fr}.metric{margin:0}.metric,article,.panel{padding:18px}}
</style><main><small>SCIENTISTS’ LAST EXAM · PAIRED MODEL COMPARISON</small><h1>同一批科学世界<br>GPT-5.6 × DeepSeek V4 Pro</h1><p>12 环境 × 3 隐藏实例 × 2 次运行。同样的世界、面板、提示、评分与预算，两模型独立选择实验和提交预测。</p>
<nav><a href="#comparison">配对成绩</a><a href="#findings">区分度与证据</a><a href="overview.html">GPT 完整发现报告</a><a href="comparison-data.json">公开对照数据</a></nav>
<div class="metrics"><div class="metric">GPT-5.6 主分<strong>'''+num(a['score'])+''' / 100</strong><small>有效完成 62 / 72；原批次保留全部失败。</small></div><div class="metric">DeepSeek V4 Pro 主分<strong>'''+num(b['score'])+'''</strong><small>已结束 %d / 72；有效完成 %d / 72。</small></div><div class="metric">配对分差 · V4 − GPT<strong>%s</strong><small>共同协议：新条件 50%% + 控制变化 30%% + 定量声明 20%%。</small></div></div>
<div class="notice"><strong>%s</strong><p>DeepSeek 请求型号 %s。实际调用 %d / 1152；基础设施失败 %d；其他未完成 %d。有效完成不是科学发现成功率。</p></div>
<section id="comparison"><h2>各环境是否拉开差距</h2><div class="scroll"><table><tr><th>环境</th><th>GPT-5.6</th><th>V4 Pro</th><th>分差</th><th>GPT 有效</th><th>V4 有效</th></tr>%s</table></div></section>
<section id="findings" class="panel"><h2>怎样解释区分度</h2>%s</section>
<section class="panel"><h2>共同条件与比较边界</h2><p>两模型都限制为每次运行 16 次请求、8,000 输出 token 上限、48 次实验和相同分析及墙钟预算。DeepSeek 使用 high / max_tokens，GPT 使用 medium / max_completion_tokens；厂商思考档位不等价，因此这是共同外部预算下的系统比较。DeepSeek 使用流式传输，GPT 使用非流式传输；修正后的对照将完整空答案按无效动作消耗预算。</p><p>同一实例的两次重复共同构成一个独立实例簇。复用 episode 标识和确认密钥使相同实验索引及指定对比可共享观测随机性；模型探索路线仍各自决定。主分包括所有失败计零。</p><p>这是先后执行的两批服务调用，并非同时随机分配的服务试验。单个对照模型只能说明样本上的分离、相近或分数饱和情况，不能认证一般科学能力、抗污染或发现深度。预埋方程族、候选菜单和难度差异仍然存在。</p><p class="muted">原始隐藏 seed、参数、测试目标、API 凭证与模型完整轨迹不公开。科学证据审阅若存在，为同模型家族的暂定判断；算术核验不是机制认证。</p></section>%s<footer class="muted">本页无外部资源，可离线阅读。固定对照设计见 env/PAIRED_COMPARISON.md。生成时间 %s UTC。</footer></main></html>'''%(b['settled'],b['valid'],signed(d['delta']),esc(status),esc(d['candidate_model']),d['candidate_ledger']['started_attempts'],b['infrastructure_failures'],b['settled']-b['valid']-b['infrastructure_failures'],''.join(rows),conclusion,''.join(cards),datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M'))


def main():
    p=argparse.ArgumentParser();p.add_argument('--reference',type=Path,required=True);p.add_argument('--candidate',type=Path,required=True);p.add_argument('--output-dir',type=Path,default=Path(__file__).parent);p.add_argument('--review',type=Path);a=p.parse_args()
    ref=json.loads(a.reference.read_text());cand=json.loads(a.candidate.read_text())
    if cand['comparison']['reference_public_sha256']!=hashlib.sha256(a.reference.read_bytes()).hexdigest():
        raise ValueError('Reference bytes differ from paired freeze')
    d=compare(ref,cand);review=json.loads(a.review.read_text()) if a.review else None
    d['source_sha256']={'reference':hashlib.sha256(a.reference.read_bytes()).hexdigest(),'candidate':hashlib.sha256(a.candidate.read_bytes()).hexdigest()}
    monitor_path=a.candidate.parent/'monitor-status.json'
    if monitor_path.exists():
        monitor=json.loads(monitor_path.read_text())
        if monitor.get('manifest_sha256')!=cand['manifest_sha256']:
            raise ValueError('Monitor status belongs to another campaign')
        if cand['settled_episodes']<monitor['remote_closed']:
            d['monitor_status']=monitor
    if review:
        if review.get('source_sha256') != d['source_sha256']:
            raise ValueError('Review does not bind these exact public results')
        d['review']=review
    a.output_dir.mkdir(parents=True,exist_ok=True)
    (a.output_dir/'comparison-data.json').write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
    (a.output_dir/'comparison.html').write_text(render(d,review))
    print(json.dumps({'settled':d['candidate']['settled'],'score':d['candidate']['score'],'delta':d['delta'],'ci':d['paired_cluster_bootstrap_95']}))

if __name__=='__main__':main()

"""Insert audited two-system results into the existing world catalog."""
import html
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent

def esc(x): return html.escape(str(x), quote=True)
def num(x): return '%.2f' % x

def status(e):
    if e.get('infrastructure_failure'): return 'API / 基础设施故障'
    return {'completed':'有效提交', 'invalid_predictor':'预测程序失败', 'incomplete':'未完成提交'}.get(e['status'], e['status'])

def integrate(page, comparison, repair, notes):
    assert comparison['ready'] and comparison['candidate']['settled'] == 72
    assert notes['review_independence'] == 'same-family' and notes['acceptance_status'] == 'provisional'
    page=page.replace('SCIENTISTS’ LAST EXAM · GPT-5.6','SCIENTISTS’ LAST EXAM · GPT-5.6 × DEEPSEEK')
    page=page.replace('12 个环境使用共同的评分公式与评测预算重新检验。','12 个环境使用共同的科学任务与评分公式；两模型输出及时间预算不同，详见对比说明。')
    page=page.replace('12 环境统一总分','GPT 基线总分').replace('统一成绩 · 12 环境使用相同列与权重','GPT 基线成绩 · 12 环境使用相同列与权重')
    a,b=comparison['reference'],comparison['candidate'];s=repair['comparison'];ci=comparison['paired_cluster_bootstrap_95']
    header='<section class="protocol" id="paired-results"><h2>GPT-5.6 × DeepSeek：十二环境逐题对比</h2>'
    header+='<p>同一批科学任务、三个实例与两次重复。GPT 使用 8k 输出上限 / 1 小时运行预算；DeepSeek 使用 32k / 4 小时，原生思考档位与传输方式也不同。这是不同预算的系统比较。</p>'
    header+='<div class="scroll"><table><thead><tr><th>口径</th><th>总分</th><th>新条件</th><th>干预预测</th><th>声明</th></tr></thead><tbody>'
    for label,x in [('GPT 原始72次',a),('DeepSeek 原始72次',b),('DeepSeek 单次故障补齐后',s['candidate'])]:
        header+='<tr><td>'+label+'</td>'+''.join('<td>'+num(v)+'</td>' for v in [x['score'],x['components']['condition_score'],x['components']['intervention_score'],x['components']['claim_score']])+'</tr>'
    header+='</tbody></table></div>'
    header+=f'<p>原始配对差（DeepSeek − GPT）{comparison["delta"]:+.2f}，三个实例聚类的描述性区间 [{ci[0]:.2f}, {ci[1]:.2f}]。剔除任一模型基础设施故障的配对后，按环境等权的辅助差为 {comparison["matched_noinfra_delta"]:+.2f}。均不能视作普适排名或发现深度。</p>'
    sci=s['paired_cluster_bootstrap_95'];header+=f'<p>用户授权仅补一次反应动力学 API 故障：补跑 {repair["repair_episode"]["score"]:.2f} 分、15 次请求。替换该指定失败后的敏感性差为 {s["delta"]:+.2f}，描述性区间 [{sci[0]:.2f}, {sci[1]:.2f}]。原失败与原始总分保留；GPT 的服务故障未补跑，因此该补齐口径并不对称，也不是择优取分。</p>'
    header+='<p>原始请求数：GPT 1,052；DeepSeek 995，另补跑15次，共1,010次。原始有效完成：62/72 与69/72；补齐后DeepSeek为70/72，两次预测器无效仍计零。</p>'
    header+='<h3>结论：预测与声明应分别看</h3><p>DeepSeek的两项预测分更高，GPT的声明分更高。审阅发现：高预测分可以与错误的效应方向、过宽区间或无效机制声明并存；局部声明成立也不代表整体机制已经重建。</p><p class="muted">独立上下文审阅：部分支持（partial），置信度中等；同模型家族、暂定结论。144份原始报告哈希与分数已核验，但不等于完整实验完整性认证。每题以下轨迹说明基于代表性案例，不代表全部运行都采取相同策略。</p><nav><a href="deepseek-extended.html">完整原始比较</a><a href="deepseek-repair-data.json">单次补齐公开数据</a><a href="paired-world-notes.json">逐题审阅摘要</a><a href="environment-expansion.html">新环境筛选与原型</a></nav></section>'
    page=page.replace('<section id="scores"><h2>',header+'<section id="scores"><h2>',1)
    page=page.replace('<a href="#scores">统一成绩</a>','<a href="#paired-results">双模型对比</a><a href="#scores">GPT基线成绩</a>',1)
    for world in comparison['worlds']:
        env=world['environment'];n=notes['worlds'][env];a,b=world['reference'],world['candidate']
        block='<section class="paired-world"><h3>本题：两模型运行对比</h3><div class="scroll"><table><thead><tr><th>模型（原始六次）</th><th>总分</th><th>新条件</th><th>干预</th><th>声明</th></tr></thead><tbody>'
        for label,x in [('GPT-5.6',a),('DeepSeek V4 Pro',b)]:
            block+='<tr><td>'+label+'</td>'+''.join('<td>'+num(v)+'</td>' for v in [x['score'],x['components']['condition_score'],x['components']['intervention_score'],x['components']['claim_score']])+'</tr>'
        block+='</tbody></table></div><div class="two-col"><section><h4>GPT：如何研究</h4><p>'+esc(n['gpt'])+'</p></section><section><h4>DeepSeek：如何研究</h4><p>'+esc(n['deepseek'])+'</p></section></div><h4>不足与下一步环境改进</h4><p>'+esc(n['limits'])+'</p>'
        block+='<details><summary>六次配对明细：同实例、同重复</summary><div class="scroll"><table><thead><tr><th>实例 / 重复</th><th>GPT 总分</th><th>GPT 状态</th><th>DeepSeek 总分</th><th>DeepSeek 状态</th><th>差</th><th>请求 / 实验（GPT；DS）</th></tr></thead><tbody>'
        for p in world['pairs']:
            x,y=p['reference'],p['candidate'];block+=f'<tr><td>{p["instance"]} / {p["repeat"]}</td><td>{x["score"]:.2f}</td><td>{esc(status(x))}</td><td>{y["score"]:.2f}</td><td>{esc(status(y))}</td><td>{p["delta"]:+.2f}</td><td>{x["requests"]} / {x["observations"]}；{y["requests"]} / {y["observations"]}</td></tr>'
        block+='</tbody></table></div></details>'
        if env=='reaction_kinetics':
            rw=next(w for w in s['worlds'] if w['environment']==env)
            block+=f'<p class="pending">指定补跑：实例1 / 重复1，原始API故障0分，单独补跑 {repair["repair_episode"]["score"]:.2f} 分；替换后本题六次均分 {rw["candidate"]["score"]:.2f}，有效6/6。上表保留原始结果。</p>'
        block+='</section>'
        start=page.index('<article class="world" id="world-'+env+'">');anchor=page.index('</section></div>',start)+len('</section></div>');page=page[:anchor]+block+page[anchor:]
    progress_path=HERE/'completion-repair-status.json'
    if progress_path.exists():
        progress=json.loads(progress_path.read_text())
        if progress['status']=='running':
            banner='<section class="notice" id="completion-repair"><h2>补齐运行已启动</h2><p>保留成功运行，补跑GPT的10项和DeepSeek的2项未完成项目；此前反应动力学补跑已经完成。沿用各模型原预算，未启动GPT 32k对齐实验。补齐并核验后更新本页总分与逐题结果。</p><p>下面成绩暂为补跑前参考；原始失败记录与额外请求成本保留在审计明细，补跑不按最高分择优。</p></section>'
            begin=page.index('<div class="metrics">');end=page.index('<section class="protocol" id="paired-results">',begin)
            page=page[:begin]+banner+'<details id="original-run-summary"><summary>原始运行审计（补跑前）</summary>'+page[begin:end]+'</details>'+page[end:]
            begin=page.index('<section id="scores">');end=page.index('</section>',begin)+len('</section>')
            page=page[:begin]+'<details><summary>GPT原始单次评测明细</summary>'+page[begin:end]+'</details>'+page[end:]
            page=page.replace('GPT-5.6 × DeepSeek：十二环境逐题对比','GPT-5.6 × DeepSeek：补跑前参考成绩')
            page=page.replace('<p>原始请求数：GPT 1,052；DeepSeek 995，另补跑15次，共1,010次。原始有效完成：62/72 与69/72；补齐后DeepSeek为70/72，两次预测器无效仍计零。</p>','<details><summary>原始请求与失败审计</summary><p>原始请求数：GPT 1,052；DeepSeek 995，此前另补跑15次。原始GPT有10项未完成；DeepSeek的剩余2项预测器无效也已纳入本次补齐。</p></details>')
    return page

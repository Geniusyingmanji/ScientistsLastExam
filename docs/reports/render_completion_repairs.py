"""Render audited replacement slots, keeping unresolved results explicitly pending."""
import html
import re


def esc(x): return html.escape(str(x),quote=True)
def num(x): return '%.2f' % x

def section_end(page,start):
    depth=0
    for match in re.finditer(r'</?section\b[^>]*>',page[start:]):
        depth += -1 if match.group().startswith('</') else 1
        if depth==0:return start+match.end()
    raise ValueError('unbalanced section')


def apply(page,data,review):
    assert review['review_independence']=='same-family' and review['acceptance_status']=='provisional'
    d=data['comparison'];missing={(r['model'],r['episode_id']) for r in data['missing_slots']}
    missing_worlds={(r['model'],r['environment']) for r in data['missing_slots']}
    banner='<section class="notice" id="completion-repair"><h2>补跑结果已核验</h2><p>DeepSeek已补齐全部预定项目。GPT本轮补齐9项，伊辛自旋实例3／重复2再次遇到API断连，尚待补齐；GPT总分暂不作为完整结果发布。未启动GPT 32k对齐实验。</p><p>主表采用成功原运行及预先指定补跑的首个有效结果；失败记录和所有请求成本保留在下方审计，不按最高分择优。</p></section>'
    start=page.index('<div class="metrics">');end=page.index('<section class="protocol" id="paired-results">',start)
    page=page[:start]+banner+'<details><summary>原始单次运行审计</summary>'+page[start:end]+'</details>'+page[end:]
    for marker,label in [('<section id="scores">','GPT原始单次成绩'),('<section id="findings"','原始单次研究结论与局限')]:
        start=page.index(marker);end=section_end(page,start)
        page=page[:start]+'<details><summary>'+label+'</summary>'+page[start:end]+'</details>'+page[end:]
    header='<section class="protocol" id="paired-results"><h2>GPT-5.6 × DeepSeek：补齐后的逐题结果</h2><p>保留同一任务、实例、评分与各自原预算：GPT为8k / medium / 1小时；DeepSeek为32k / high / 4小时。补跑使用额外资源，本页不代表等预算排名或单次运行可靠性。</p><div class="scroll"><table style="min-width:600px"><tr><th>模型</th><th>总分</th><th>新条件</th><th>干预</th><th>声明</th></tr>'
    for model,side in [('gpt','reference'),('deepseek','candidate')]:
        row=d[side];pending=any(x[0]==model for x in missing)
        values=[row['score']]+[row['components'][k] for k in ('condition_score','intervention_score','claim_score')]
        header+='<tr><td>'+('GPT-5.6' if model=='gpt' else 'DeepSeek V4 Pro')+'</td>'+''.join('<td>'+('待最后一项补齐' if pending and i==0 else '—' if pending else num(v))+'</td>' for i,v in enumerate(values))+'</tr>'
    header+='</table></div><p>实际累计请求：GPT '+str(data['actual_requests']['gpt'])+' 次；DeepSeek '+str(data['actual_requests']['deepseek'])+' 次。包含原始失败、此前反应动力学补跑及本轮补跑。</p><p>审阅为独立上下文、同模型家族的暂定结论。预测准确、效应区间通过与机制发现仍分别解释；补跑成功本身不等于发现成功。</p><p><a href="completion-repair-results.json">补齐数据与请求审计</a> · <a href="completion-repair-review.json">补跑科学审阅</a></p></section>'
    start=page.index('<section class="protocol" id="paired-results">');end=section_end(page,start)
    old=page[start:end].replace('id="paired-results"','id="original-paired-results"')
    page=page[:start]+header+'<details><summary>原始对照与此前单次补跑口径</summary>'+old+'</details>'+page[end:]
    for w in d['worlds']:
        env=w['environment'];start=page.index('<article class="world" id="world-'+env+'">');start=page.index('<section class="paired-world">',start);end=section_end(page,start)
        old=page[start:end]
        block='<section class="paired-world"><h3>本题：补齐后两模型结果</h3><div class="scroll"><table style="min-width:600px"><tr><th>模型</th><th>总分</th><th>新条件</th><th>干预</th><th>声明</th></tr>'
        for model,side,label in [('gpt','reference','GPT-5.6'),('deepseek','candidate','DeepSeek V4 Pro')]:
            x=w[side];pending=(model,env) in missing_worlds;values=[x['score']]+[x['components'][k] for k in ('condition_score','intervention_score','claim_score')]
            block+='<tr><td>'+label+'</td>'+''.join('<td>'+('待补齐' if pending else num(v))+'</td>' for v in values)+'</tr>'
        block+='</table></div>'
        notes=[n for n in review['episode_notes'] if n['environment']==env]
        if notes:
            block+='<h4>这轮补跑怎样研究、还有什么不足</h4>'
            for n in notes:block+='<p><strong>'+esc(n['model']+' · '+n['episode_id'])+'</strong>：'+esc(n['summary'])+'</p>'
        else:block+='<p>本题没有新增补跑，保留原运行结果与科学证据。</p>'
        block+='<details><summary>六次配对与补跑来源</summary><div class="scroll"><table><tr><th>实例 / 重复</th><th>GPT</th><th>来源</th><th>DeepSeek</th><th>来源</th></tr>'
        for p in w['pairs']:
            block+='<tr><td>'+str(p['instance'])+' / '+str(p['repeat'])+'</td>'
            for model,side in [('gpt','reference'),('deepseek','candidate')]:
                x=p[side];pending=(model,x['episode_id']) in missing
                block+='<td>'+('待补齐' if pending else num(x['score']))+'</td><td>'+('补跑API断连' if pending else '指定补跑' if x.get('replacement_phase') else '原运行')+'</td>'
            block+='</tr>'
        block+='</table></div></details><details><summary>原始轨迹解读与补跑前结果</summary>'+old+'</details></section>'
        page=page[:start]+block+page[end:]
    page=page.replace('主成绩在全部运行结束后，将每环境全部 6 次计划运行（含失败计零）求均值，再对 12 环境等权平均。它衡量端到端系统表现，不能单独归因于模型能力；排除基础设施失败的模型成绩作为补充披露。','原始单次成绩按每环境6次计划运行（失败计零）求均值，再对12环境等权平均。当前补齐视图保留成功原运行，并用预先指定的首个有效补跑替换失败槽位；仍有缺项的总体成绩暂不发布。这是补跑后的交付表现，不代表单次可靠性。')
    return page

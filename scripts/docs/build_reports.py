"""Build Plan and Case Study; preserve links to archived reports."""
from pathlib import Path
import json,re,html
R=Path(__file__).resolve().parents[2]; D=R/'docs'; P=D/'reports'; A=D/'archive/reports'
T=R/'scripts/docs/templates'
esc=html.escape
old=(A/'overview.html').read_text();style=re.search(r'<style>(.*?)</style>',old,re.S).group(1)
style+='\npre{background:#edf2ec;padding:20px;border-radius:8px;overflow:auto}blockquote{border-left:3px solid #56836c;margin:16px 0;padding:8px 20px;background:#f3f6f0}section{scroll-margin-top:20px}.equation{font:16px/1.9 ui-monospace,monospace}.toc{position:sticky;top:0;background:#f4f5eff5;z-index:2;padding:8px 0}.tag{font-size:13px;color:#6a562c}svg{max-width:100%;height:auto}'
nav='<nav class="toc"><a href="plan.html">整体 Plan</a><a href="case_study.html">Case Study</a></nav>'
style+='\ntable{min-width:0}.scroll table{min-width:810px}.query{white-space:pre-wrap;overflow-wrap:anywhere;font-size:14px;line-height:1.85}section,h3[id]{scroll-margin-top:90px}'
def page(title,body,extra_style=""):
 body=body.replace('href="v1_results.html','href="reports/v1_results.html')
 return '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+title+'</title><style>'+style+extra_style+'</style></head><body><main>'+nav+'<div class="eyebrow">Scientists’ Last Exam</div><h1>'+title+'</h1>'+body+'<footer>来源：已冻结 V1 公开汇总、模拟器实现及经筛选的可见回复。历史过程材料移入 docs/archive；原始私有评测资料不随页面发布。</footer></main></body></html>'
def section(i,title,body):return f'<section class="world" id="{i}"><h2>{title}</h2>{body}</section>'
def table(headers,rows):return '<div class="scroll"><table><tr>'+''.join('<th>'+x+'</th>' for x in headers)+'</tr>'+''.join('<tr>'+''.join('<td>'+str(x)+'</td>' for x in row)+'</tr>' for row in rows)+'</table></div>'
# Public allowlisted summaries only; private evidence and reviewer transcripts stay outside reports.
def scientific_assessment():
 path=P/'data/three-stage-supplement.json'
 if not path.exists():return ''
 data=json.loads(path.read_text())
 rows=[]
 for item in data['environments']:
  rows.append([esc(item['name']),*[f"{item[k]:.2f}" for k in ['phenomena','laws','application','result','process']]])
 return '<h3>冻结提交的三层补充评审</h3><p>对已完成提交作事后三层评审，原协议和成绩不变；不是新三层协议的前瞻实测。独立评审为 same-family / provisional，分数尚未跨评审校准。结果与过程分别报告。</p>'+table(['环境','现象20%','规律40%','应用40%','结果分','过程分'],rows)+''.join('<p><strong>'+esc(x['name'])+'：</strong>'+esc(x['finding'])+'</p><details><summary>查看逐项评分</summary>'+table(['评分项','得分'],[[esc(c['name']),f"{c['score']:.2f}"] for c in x['criteria']])+'</details>' for x in data['environments'])+'<p>评分核验模型封存哈希及证据文件；每项保留判断依据。规律分固定包含全部科学模块，遗漏机制不能从分母删除。语义正确性由独立评审判断，文件哈希不代替科学审查。</p>'

# V1 retains all twelve task descriptions and paired results. History remains collapsible.
v=old.replace('<main>','<main>'+nav.replace('href="','href="../'),1).replace('Scientists’ Last Exam · GPT-5.6','Scientists’ Last Exam · GPT-5.6 × DeepSeek')
v=v.replace('仍有缺项的总体成绩暂不发布。','本轮全部预定槽位已补齐。')
def relink(m):
 u=m.group(1)
 if u.startswith(('#','http','mailto:')):return m.group(0)
 if u.startswith('../../reports/'):
  u=u[len('../../reports/'):]
 if u.split('#')[0] in ['plan.html','case_study.html']:
  return 'href="../'+u+'"'
 if u.startswith('../') or u.split('#')[0]=='v1_results.html':return 'href="'+u+'"'
 if u.split('#')[0] in ['overview-data.json','completion-repair-results.json','completion-repair-review.json']:u='data/'+u
 elif u.split('#')[0] in ('progress.html','environment-expansion.html','progress-v2.html'):u='../archive/reports/progress-20261022.html'+('#'+u.split('#',1)[1] if '#' in u else '')
 elif u in ('comparison.html','deepseek-continuation.html','deepseek-extended.html'):u='v1_results.html#paired-results'
 else:u='../archive/reports/'+u
 return 'href="'+u+'"'
v=re.sub(r'href="([^"]+)"',relink,v)
v=v.replace('<a href="archive/reports/comparison.html">GPT × DeepSeek 对照</a><a href="archive/reports/deepseek-continuation.html">DeepSeek 接续诊断</a><a href="archive/reports/deepseek-extended.html">DeepSeek 32k 正式评测</a>','<a href="case_study.html">微生态详细案例</a>')
(P/'v1_results.html').write_text(v)
plan_body=(T/'overall_plan.html').read_text()
plan_body=plan_body.replace('{{RESEARCH_QUERY}}',esc((T/'research_query.txt').read_text()))
claim_example=json.loads((T/'research_claim_example.json').read_text())
plan_body=plan_body.replace('{{CLAIM_EXAMPLE}}',esc(json.dumps(claim_example,ensure_ascii=False,indent=2)))
(D/'plan.html').write_text(page('科学发现评测 · 整体 Plan',plan_body,(T/'plan.css').read_text()))
body=(T/'microecology_case.html').read_text()
body=body.replace('{{CASE_QUERY}}',esc((T/'ecology_query.txt').read_text()))
body=body.replace('{{HISTORICAL_ASSESSMENT}}',scientific_assessment())
case_page=page('微生态（三菌株）完整案例',body)
case_page=case_page.replace('Scientists’ Last Exam · 2026-10-07','Scientists’ Last Exam')
case_page=case_page.replace('来源：已冻结 V1 公开汇总、模拟器实现及经筛选的可见回复。历史过程材料移入 docs/archive；原始私有评测资料不随页面发布。','来源：模拟器实现、冻结提交与独立审阅。原始轨迹、实例参数和封存目标不随页面发布。')
(D/'case_study.html').write_text(case_page)
# Retired progress URLs resolve to the fixed archive; other bookmarks keep their fragments.
def redirect(path,destination):
 path.write_text(f'<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>报告已迁移</title><script>location.replace("{destination}"+location.search+location.hash)</script><meta http-equiv="refresh" content="1;url={destination}"></head><body><a href="{destination}">打开报告新地址</a></body></html>\n')

redirect(D/'progress.html','archive/reports/progress-20261022.html')
redirects={'overview.html':'v1_results.html','index.html':'../plan.html',
           **{name:'../archive/reports/progress-20261022.html' for name in ['progress.html','progress-v2.html','environment-expansion.html']},
           **{name:'../'+name for name in ['plan.html','case_study.html']}}
for name,destination in redirects.items():
 redirect(P/name,destination)

"""Build the three public report entries from immutable public summaries/excerpts."""
from pathlib import Path
import json,re,html
R=Path(__file__).resolve().parents[2]; P=R/'docs/reports'; A=R/'docs/archive/reports'
esc=html.escape
d=json.loads((P/'data/completion-repair-results.json').read_text())
w=next(x for x in d['comparison']['worlds'] if x['environment']=='microecology')
old=(A/'overview.html').read_text();style=re.search(r'<style>(.*?)</style>',old,re.S).group(1)
style+='\npre{background:#edf2ec;padding:20px;border-radius:8px;overflow:auto}blockquote{border-left:3px solid #56836c;margin:16px 0;padding:8px 20px;background:#f3f6f0}section{scroll-margin-top:20px}.equation{font:16px/1.9 ui-monospace,monospace}.toc{position:sticky;top:0;background:#f4f5eff5;z-index:2;padding:8px 0}.tag{font-size:13px;color:#6a562c}svg{max-width:100%;height:auto}'
nav='<nav class="toc"><a href="progress.html">当前进度</a><a href="v1_results.html">V1 双模型结果</a><a href="case_study.html">微生态 Case Study</a></nav>'
def page(title,body):return '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+title+'</title><style>'+style+'</style></head><body><main>'+nav+'<div class="eyebrow">Scientists’ Last Exam · 2026-10-07</div><h1>'+title+'</h1>'+body+'<footer>来源：已冻结 V1 公开汇总、模拟器实现及经筛选的可见回复。历史过程材料移入 docs/archive；原始私有评测资料不随页面发布。</footer></main></body></html>'
def section(i,title,body):return f'<section class="world" id="{i}"><h2>{title}</h2>{body}</section>'
def table(headers,rows):return '<div class="scroll"><table><tr>'+''.join('<th>'+x+'</th>' for x in headers)+'</tr>'+''.join('<tr>'+''.join('<td>'+str(x)+'</td>' for x in row)+'</tr>' for row in rows)+'</table></div>'
# V1 retains all twelve task descriptions and paired results. History remains collapsible.
v=old.replace('<main>','<main>'+nav,1).replace('Scientists’ Last Exam · GPT-5.6','Scientists’ Last Exam · GPT-5.6 × DeepSeek')
v=v.replace('仍有缺项的总体成绩暂不发布。','本轮全部预定槽位已补齐。')
def relink(m):
 u=m.group(1)
 if u.startswith(('#','http','mailto:')):return m.group(0)
 if u.startswith('../../reports/'):
  return 'href="'+u[len('../../reports/'):]+'"'
 if u in ['progress.html','v1_results.html','case_study.html']:return m.group(0)
 if u.split('#')[0] in ['overview-data.json','completion-repair-results.json','completion-repair-review.json']:u='data/'+u
 elif u in ('environment-expansion.html','progress-v2.html'):u='progress.html'
 elif u in ('comparison.html','deepseek-continuation.html','deepseek-extended.html'):u='v1_results.html#paired-results'
 else:u='archive/reports/'+u
 return 'href="'+u+'"'
v=re.sub(r'href="([^"]+)"',relink,v)
v=v.replace('<a href="archive/reports/comparison.html">GPT × DeepSeek 对照</a><a href="archive/reports/deepseek-continuation.html">DeepSeek 接续诊断</a><a href="archive/reports/deepseek-extended.html">DeepSeek 32k 正式评测</a>','<a href="case_study.html">微生态详细案例</a>')
(P/'v1_results.html').write_text(v)
progress='''<div class="notice"><strong>持续扩展已暂停。</strong>本页是当前工作快照；未启动 GPT 预算对齐实验，也没有新增付费模型评测。下一阶段先整理环境质量与文档，再由用户决定恢复。</div>'''
progress+=section('results','已完成：V1 十二环境双模型评测',table(['项目','GPT-5.6','DeepSeek V4 Pro'],[['补齐后总分','72.84','73.33'],['新条件预测','73.90','80.63'],['干预预测','73.60','79.95'],['定量声明','69.05','45.14'],['输出 / 时间上限','8k / 1 小时','32k / 4 小时'],['累计请求（含失败、补跑）','1226','1034']])+'''<p>每模型 12 环境 × 3 实例 × 2 次重复。成功原运行保留，失败槽位使用预先指定补跑的首个有效结果；不是按最高分挑选。两模型总分接近，但分项特点不同，预算也不同，不能据此认定普适模型排名或发现深度。</p><p><a href="v1_results.html#paired-results">查看逐题成绩、六次配对、环境规律与评分</a> · <a href="case_study.html">查看三菌株完整案例</a></p>''')
progress+=section('candidate-decisions','V2 候选与成熟度',table(['候选','当前证据 / 状态','尚未完成'],[
['非线性容量输运 retention_capacity','独立非线性修订原型；控制注入量和流量历史，观察回收比例。竞争解释为储留或出口的饱和，具体机制及系数隐藏','拟合参考复核通过，Linux6测试通过；4次配对运行已结束，3次有成绩、1次连接故障；完整审阅暂不认证高难，未共享注册'],
['自适应信号 adaptive_signaling','独立原型；研究适应响应背后的竞争解释','双模型4次已结束；预测近满分，需增加科学区分度，未共享注册'],
['滞留输运 retention_transport','独立原型；研究表观延迟来自何种机制','双模型4次已结束；先分离分析预算与科学失败，再改进任务'],
['同位素配对 isotope_pairing','原型与前瞻工作流、预算预览、请求示例；Linux 隔离执行验证','显式 driver 已完成双模型实测；评分更正与新难度版本筛选见上方；未作共享注册'],
['谱系记忆 lineage_memory','已做有限样本筛选；强信号可分，弱信号及零信号尚不能可靠区分','暂缓；需要候选可获得的不确定性估计'],
['地震孔径 seismic_aperture','竞争模型的数值辨识见证；新噪声确认中分层结构不可行、均匀对照可行','仍为算子验证；不是已注册世界、独立新世界泛化或机制唯一性证明']
])+'''<p>上述四个输运、信号与同位素环境原型均未完成共享任务注册。前两原型合计定义四个任务；候选验证、算子演示、完整环境和模型测评分别统计，避免把数量当成熟度。同位素已有模型结果；自适应信号和滞留输运本轮8次实测已结束。</p>''')
progress+=section('findings','已核验的进展与限制','''<ul><li>同位素：59 项相关本地测试通过；另有请求示例预览测试。Linux smoke 记录 5 个观测、96 预算单位、2 次隔离预测和 32 个接收记录；这些是工程验证，不是科学发现成功率。</li><li>地震：单点拟合在新条件失效，不足以排除整个模型家族；后续联合约束检验发现，逐点区间重叠仍可能不存在同一组共同参数。新噪声确认支持这一有限数值结论，审阅为同模型家族暂定。</li><li>谱系记忆：作者知道方差不等于科学 agent 能从预算内数据估计方差；候选因此暂缓，避免制造不可解“难题”。</li><li>已区分科学困难、接口/程序失败和服务故障。V1 预测分、声明分与机制发现分别解释。</li></ul><details><summary>工程审计事项</summary><p>曾发生 Linux 下载覆盖一部分旧 macOS 失败归档的事件，已记录；独立 Linux 归档已校验。历史开发记录保留在归档区，不能把缺失的旧证据当作已恢复。</p></details>''')
progress+=section('next','持续迭代优先事项','''<ol><li>依据同位素实测高分设计有竞争机制的新版本，验证可辨识性后用新开发实例筛选。</li><li>对自适应信号、滞留输运逐一补足竞争解释、可区分实验、未解决区间和带先验标记的参考解。</li><li>用无观测、经验拟合与作者参考区分“科学难”与“接口难”；不以低分直接认证高难度。</li><li>正式新实例与评分在见模型结果前冻结。持续开展已授权的双模型 API 筛选；GPT 对齐实验继续暂缓。</li></ol>''')
live_path=P/'data/difficulty-round1-progress.json'
if live_path.exists():
 live=json.loads(live_path.read_text())
 progress=progress.replace('持续扩展已暂停。','双模型难度筛选已恢复。').replace('本页是当前工作快照；未启动 GPT 预算对齐实验，也没有新增付费模型评测。下一阶段先整理环境质量与文档，再由用户决定恢复。','首轮冻结批次已结束或中断，证据保留。持续迭代已获授权：目标总并发16，累计请求与预算不设上限；GPT预算对齐实验仍暂缓。')
 if live.get('monitoring_notice'):
  progress=progress.replace('双模型难度筛选已恢复。','双模型难度筛选：详见上方核验状态。').replace('Stage A运行微生态与伊辛自旋；','Stage A已启动微生态与伊辛自旋，运行状态见上方；')
 rows=[[e['environment'],e['model'],e['status'],f"{e['score']:.2f}" if isinstance(e.get('score'),(int,float)) else '—'] for e in live['episodes']]
 progress=section('live-screening','首轮实测进度', ('<div class="notice">'+esc(live['monitoring_notice'])+'</div>' if live.get('monitoring_notice') else '')+'<p>Stage A 原始快照：'+esc(live['updated_at'])+'；已结束 '+str(live['closed'])+'/8。已计入请求 '+str(live['ledger']['started_attempts'])+'/128，同位素独立批次上限64请求，状态见上方。以下为单次开发运行，未汇总为最终难度结论。</p>'+table(['环境','模型','状态','单次分数'],rows)+'<p>GPT8k/1小时，DeepSeek32k/4小时；不同预算。已结束报告已归档并核验SHA-256。零API沙箱启动故障单独留档；不混入本表。低分仍需科学轨迹与参考可解性审阅。</p>')+progress
 if live.get('catalyst_matched_task'):
  progress=section('catalyst-matched-task','催化剂老化 · 配对任务接入','<p>'+esc(live['catalyst_matched_task']['note'])+'</p><p>这是已有环境的新任务，不要求唯一机制或参数恢复；模型结果仍需独立审阅，不能仅凭低分认证高难。</p>')+progress
 if live.get('catalyst_postjump'):
  cj=live['catalyst_postjump']
  progress=section('catalyst-postjump','催化剂老化 · 跳变后检验','<p>保留旧拟合，不重新训练。在原缺少校准读数的事件位置，通过独立重置历史测空白和标准；另将留出四臂读数移至所有允许跳变之后。</p><p>'+esc(cj['note'])+'</p><p>600次模拟器调用、48次参考前向预测，0拟合、0API；每臂16次独立噪声读数全部归档。插入空白/标准未增加试片反应暴露，所以这里只补充仪器事件位置迁移证据，不是新的动力学外推或高难认证。</p>')+progress
 if live.get('catalyst_inverse'):
  ci=live['catalyst_inverse']
  progress=section('catalyst-inverse','催化剂老化 · 有界参考拟合','<p>作者已知单群体/双群体公式与参数范围，使用公开观测拟合仪器与反应历史；不读取实例真实系数或生成标签。不是GPT/DeepSeek新成绩。</p><p>'+esc(ci['note'])+'</p><p>3个已暴露实例，各4条训练历史、2组留出配对。3684次优化前向调用，另48次留出参考调用、36次模拟器观测；28项本地测试通过，本轮API为0。计划max_nfev按family表述、实现按start设置；实际各family累计15–48未越100，差异留档。</p>')+progress
 if live.get('catalyst_audit'):
  ca=live['catalyst_audit']
  progress=section('catalyst-audit','催化剂老化 · 既有轨迹与新诊断','<p>这是已有V1环境，不是新增环境。研究活性损失与仪器共同漂移的混杂；V1补齐口径GPT65.66、DeepSeek70.05，各6运行，原分数不改。</p><p>'+esc(ca['note'])+'</p><p>新增未注册诊断：四次独立重置实验使用相同准备历史，在同一事件位置测用过试片、新试片、空白和标准。按模拟器的共同仿射仪器假设校正增益和偏置。9个已暴露开发条件、36次干净仿真通过；26项本地测试通过。另完成固定高斯噪声假设下9个条件的比值不确定性检查，每条件2000次抽样，95%区间覆盖率93.85%–95.40%。首次结果序列化失败留档，独立恢复仅修布尔输出。尚缺逆问题参考和新任务模型实测；这些不证明高难或唯一机制。</p>')+progress
 if live.get('capacity_order_round4'):
  co=live['capacity_order_round4']
  progress=section('order-task-screening','新顺序任务 · 双模型确认','<p>同一容量输运世界的新任务：预测绝对回收量和仅改变流速次序的有符号差。两项各占50%，尺度0.1/0.05；差分来自相同两臂预测。内部机制、参数和未来结果隐藏；不计声明分。</p><p>'+esc(co['notice'])+'</p>'+table(['模型','实例','绝对预测','顺序差','总分'],[[x['model'],str(x['instance']),f"{x['absolute']:.2f}" if x.get('absolute') is not None else '—',f"{x['order']:.2f}" if x.get('order') is not None else '—',f"{x['score']:.2f}" if x.get('score') is not None else '预测器失败'] for x in co.get('runs',[])])+'<p>'+esc(co.get('review',''))+'</p><p>Linux11项通过，包含新driver真实隔离实验、分析与冻结预测器评分。两新开发实例×GPT/DeepSeek，共4运行。GPT8k/1小时、DeepSeek32k/4小时，非等预算比较。旧结果不覆盖；低分须区分程序、服务与科学失败。</p>')+progress
 if live.get('capacity_order_baselines'):
  ob=live['capacity_order_baselines']
  names={'clock':'累计流量时钟','linear_memory':'线性记忆','load_memory':'负载相关记忆','informed_reference':'带公式先验的参考','zero':'无观测：零预测','constant_half':'无观测：固定0.5','nearest':'最近公开观测'}
  progress=section('order-task-baselines','新顺序任务 · 共同数据基线','<p>同时预测两臂回收量与其有符号差，绝对和差分各占50%，RMSE尺度分别0.1和0.05。4个暴露开发实例，每例6个训练臂、4个留出配对；以下均为数值拟合参考，不是GPT或DeepSeek新成绩。</p>'+table(['方法','四实例得分范围'],[[names[k],f'{v[0]:.2f}–{v[1]:.2f}'] for k,v in ob['scores'].items()])+'<p>'+esc(ob['note'])+'</p><p>新task未共享注册；显式driver已完成Linux真实隔离验证，新实例模型确认状态见本页。</p>')+progress
 if live.get('capacity_round3',{}).get('runs'):
  cr=live['capacity_round3']; rows=[]
  for x in cr['runs']:
   rows.append([x['model'],x['instance'],x['status'],*[f"{x['subscores'][k]:.2f}" if x.get('subscores') else '—' for k in ('conditions','interventions','claims')],f"{x['score']:.2f}" if isinstance(x.get('score'),(int,float)) else '—'])
  progress=section('capacity-screening','非线性容量输运 · 实测结果','<p>控制注入量和流量历史，预测回收比例。隐藏机制与系数；评分50%新条件、30%干预、20%声明。本批已结束并完成独立审阅：保留开发候选，尚不认证高难度。</p>'+table(['模型','实例','状态','新条件','干预','声明','总分'],rows)+'<p>快照：'+esc(cr['checked_at'])+'。GPT实例1服务/传输故障无科学成绩；实例2分析预算耗尽且有无效动作。两模型输出与时间预算不同。原始失败保留。</p><p>'+esc(cr.get('partial_review',''))+'</p><p>'+esc(cr.get('connection_notice',''))+'</p>')+progress
 if live.get('history_round2'):
  hr=live['history_round2']; names={'adaptive_signaling':'自适应信号','retention_transport':'滞留输运'}
  rows=[]
  for x in hr.get('runs',[]):
   rows.append([names[x['environment']],x['model'],x['instance'],x['status'],*[f"{x['subscores'][k]:.2f}" if x.get('subscores') else '—' for k in ('conditions','interventions','claims')],f"{x['score']:.2f}" if 'score' in x else '—'])
  progress=section('history-screening','自适应信号与滞留输运 · 双模型实测','<p>每环境2个实例，每实例GPT与DeepSeek配对。预测权重50%新条件、30%干预、20%声明复验；排除已知零响应和无效因果对照。</p><p>自适应信号：只能看到刺激后的报告信号，需用内部辅助状态的部分重置来检验竞争解释；生成机制与系数不告诉模型。滞留输运：只能测总回收量，需用停流、恢复和改变流速研究表观延迟；内部储留位置不可直接观测。</p>'+table(['环境','模型','实例','状态','新条件','干预','声明','总分'],rows)+'<p>本批已结束 '+str(hr['closed'])+'/8；'+str(hr['requests'])+' 次请求，'+str(hr['returned'])+' 次返回。</p><p>'+esc(hr.get('review','结果审阅待完成'))+'</p><p>'+esc(hr['claim_caveat'])+'</p>')+progress
 if live.get('isotope_sidecar'):
  side=live['isotope_sidecar']
  sr=[[x['model'],x['instance'],*[f"{x[k]:.2f}" for k in ('conditions','interventions','claims','score')]] for x in side['runs']]
  sr.append(['GPT-5.6','开发实例2','—','—','—','连接断开，缺失'])
  progress=section('isotope-correction','同位素 · 封存预测器评分更正', '<p>三个已提交预测器原样重放，仅修正评分器对合法数值数组的兼容性。原报告未覆盖；这不是新一轮模型实验。声明分沿用原冻结复验，避免评分版本号改变随机噪声样本。</p>'+table(['模型','实例','新条件','干预','声明','总分'],sr)+'<p>48 个预测面板全部有效；更正未新增 API 请求。独立审阅状态：'+esc(side['status'])+'。这些开发实例上的高分不能证明机制辨识或发现深度，也不支持将当前版本称为高难；两模型资源预算仍不同。</p>')+progress

progress = '<section class="world" id="paused-status"><h2>旧多环境循环暂停快照 · 2026-10-09</h2><p>旧自动跟进保持暂停；当时无活跃评测，旧批累计 API 请求450次。2026-10-15三菌case的新授权实测另列于上方。独立 GPU 循环不属于本评测任务，未操作。</p><h3>当前结果与结论</h3><p>催化剂配对任务：GPT 两例 49.69 / 7.26，DeepSeek 两例 53.71 / 16.53；60 次请求全部返回。四个总分与 128 个冻结预测经独立复核，审阅为 same-family/provisional。低分包含准备条件建模不足、观测与最终预测不一致及拟合导出问题，暂不能认证高难。</p><p>容量输运顺序任务：GPT 92.45 / 91.59；DeepSeek 99.86 / 0。零分来自参数读取错误，三份有效高分不支持高难判断。同位素与自适应信号也尚无高难证据。</p><h3>暂停时未完成事项</h3><p>催化剂辅助协议已实现共同观测、公共导出检查、结构探测与按观测类型反馈。本地最近测试 30 项通过、1 项 Linux 跳过；真实 Linux 闭环尚未通过，新一批 API 未启动。待用启动脚本仍有待核验源码字段。当前外部阻塞为 ssctl 登录凭证过期；恢复任务后需先恢复登录、完成 Linux 验证，再冻结新实例配对实验。旧结果与 V1 冻结数据不变。</p></section>' + progress
context_path=P/'data/context-pilot.json'
context_summary=''
if context_path.exists():
 context=json.loads(context_path.read_text())
 context_summary=section('context-pilot','三菌环境新版 · GPT＋Codex 实测完成', '<p>2026-10-15：运行的 '+esc(context['model'])+' / '+esc(context['harness'])+'。完成 '+str(context['experiments'])+' 次实验尝试（38次有效、10次无效格式），并提交方程报告、机制清单和可执行预测器。</p><p>冻结模型的 '+str(context['valid_panels'])+' 个新条件/干预诊断面板均有效，RMSE 范围 0.001924–0.010048 mmol C/L。'+esc(context['scope'])+'。</p><p>'+esc(context['review'])+'。</p><p>'+esc(context['transport'])+'。'+esc(context['cost'])+'。本轮单独记账，48次模拟实验不等于48次模型API请求；旧450请求口径保持。</p><p><a href="case_study.html#intro">查看新版方程、发现评测与案例</a>。旧自动循环仍暂停。</p>')
 progress=context_summary+progress
progress=section('discovery-matrix','多环境科学发现矩阵', '<p>新一轮完整任务实测已启动：三菌显式三体作用与耦合振子各一个新开发实例，GPT＋Codex，每项48次实验尝试、1800秒，非法尝试计入预算。已通过5项Linux测试及真实隔离MCP登记→含噪观测→最终封存→拒绝追加闭环；首次测试因缺pytest失败，原记录保留。模型已有返回，尚无最终成绩。预测器哈希必须与封存提交一致；独立隔离评测分别记录轨迹、三菌A×B差分和振子切边效应，不按声明齐全度评分。首次完成后归档与独立内容审阅，不重启旧批。</p><p>振子切边对照已完成：两个固定开发实例、全部六条候选边、静止与单端点位移两种准备，共24组、192次模拟调用、0模型调用；每组保留三次独立含噪重复和清洁算子对照。静止条件清洁差分全部为零，有激励的最大绝对响应范围0–0.2346（位移/速度各自单位，不能混作单一评分）。完整观测与分通道效应已归档；独立审阅进行中，不据零效应判无边，不认证结构发现或高难。</p><p>跨环境推进至耦合振子：新增单连接切断配对设计与校验，要求仅新增一条切边，质量、阻尼、驱动、初态和采样时刻全部一致；拒绝端点夹持及仅零时刻观测。3项测试通过，0模拟/模型调用。非零配对效应可支持局部连接作用；零效应不能证明连接不存在，尚未形成结构发现分数。下一振子单元冻结有激励/无激励对照与观测噪声预算，检查结构证据的可辨识范围；三菌独立审阅完成后再安排后续实验。</p><p>新增四臂重复观测差分不确定性工具：保留每个重复块的条件效应与A×B差分，报告均值及标准误，允许块内配对但要求块间独立。2项合成测试通过；未应用于旧队列，无新模拟或模型调用。标准误只描述重复读数波动，不代表模型无偏、机制可辨识或发现分数。</p><p>三菌共同含噪对照已执行：4个固定开发案例，每例12条训练观测和4个留出端点，共64次模拟调用、0模型调用。训练记录、拟合系数、预测及目标全部归档，预测先写入再生成目标。三体案例整体RMSE约0.0116–0.0118，两个响应面接近；单看C的A×B端点差分，固定尺度归一化误差由加性模型约0.099–0.103降至交互模型约0.035–0.045。此为插值端点诊断，不代表局部方程恢复或正式发现分；独立审阅进行中，旧成绩不变。</p><p>三菌公共观测响应面对照已实现：加性项与A×B交互项使用相同全部训练记录（含重复观测），固定温度、终点及其他初始池；秩不足、混杂或非法观测显式失败。保存系数、训练预测与分通道残差，JSON封存后可复用；3项合成测试通过，0模拟/模型调用。此为端点响应面，不是局部动力学方程恢复，也尚无真实含噪留出成绩。下一单元冻结共同含噪训练/留出设计并执行这两个对照，保留失败，再独立审阅；不追加已完成电学简单实例。</p><p>持续任务每小时检查。三菌显式三体内核已完成；48条数值轨迹及合成重复观测已独立复核（same-family/provisional）：3个固定实例检测到三体调节，9个对照未越阈值；不证明机制唯一或高难。事前预测登记已接入独立实验服务：4项相关本地测试通过，Linux隔离MCP登记→实验闭环通过；本轮1次模拟实验、0模型调用。矩阵提交与证据核验已实现：区分事前/事后证据，拒绝不适用格与无效凭据；2项测试通过。最终矩阵提交入口已实现：封存声明、证据审计及声明的模型哈希，提交后关闭实验；6项相关本地测试通过；Linux隔离MCP登记→实验→封存提交→拒绝追加实验闭环通过，1次模拟实验、0模型调用。哈希不等于已核验可执行文件，原证据判据聚合器已有2项测试，但其0–3分不作为发现程度成绩。现按预设动力学模块设计结构、形式和定量恢复评分，权重与阈值待校准；新开发实例GPT＋Codex矩阵实验已完成：527.78秒，48次实验全部有效，8条声明已封存，最终模型哈希一致。4个预定诊断面板RMSE为0.000326、0.023887、0.000663、0.025549 mmol C/L；独立逐格审阅进行中，尚不发布科学发现分数。</p><p>已有电阻抗环境的新任务原型已实现：分别记录频率、外部电路和联合迁移；幅度单独变化不计发现。失败计入分母，内部拓扑不要求唯一恢复。共同数据检查完成：3个固定开发实例、相同8频率观测。端口参考/经验插值平均分：频率44.42/70.79，外部配置99.99/2.65，联合80.85/2.93；18预测全部有效。独立审阅same-family/provisional；三个实例同属一种电路族，只支持这组描述性比较，不证明高难或agent能力。12次模拟调用，0模型调用；独立带噪实验服务与预算账本已接入，4项episode/task测试通过；Linux隔离MCP登记→测量闭环通过，1次带噪测量正确扣28单位；GPT＋Codex单实例开发实验已结束：178.45秒、4次实验、279单位。冻结模型隔离评测的频率/外部配置/联合面板分别99.9985/99.9995/99.9996分；独立审阅（same-family/provisional）确认20个评分配置点均未测量，但协议尚未强制不重叠。三次事前登记预测的带噪观测RMSE为0.001142V；仅支持单实例端口规律与有限迁移，不认证高难或唯一结构。“外部配置”面板同时包含未测频率，不能当纯配置迁移。已实现按实际观测逐点分类的独立审计，3项测试通过；它区分仅频率、仅配置、联合变化与已测点，旧分数保持不变。独立受限采集入口已通过Linux隔离MCP验证：合法采样扣28单位、越界拒绝扣1单位且无观测；该准入检查0模型调用；受限采集的新实例GPT＋Codex实测已完成，10次实验有效；三面板RMSE约0.000161/0.000070/0.000076V，独立审阅完成（same-family/provisional）：支持单实例端口规律的有限迁移；留出频率仍在采集范围内，未开展竞争机制区分，不支持高难或唯一内部结构。端口参考因仅接受单条源记录而失败，保留空结果，不据此排名。供未来批次使用的共用接口已实现：同仪器重复观测先统一平均，再同时交给经验基线与端口参考；3项合成测试通过，旧批次不重评。这属于共同数据比较，不称独立等资源agent比较。模型请求数与货币成本尚未核实。</p>')+progress
(P/'progress.html').write_text(page('当前进度与下一步',progress))
body=(R/'scripts/docs/templates/microecology_case.html').read_text()
case_page=page('微生态（三菌株）完整案例',body)
case_page=case_page.replace('Scientists’ Last Exam · 2026-10-07','Scientists’ Last Exam')
case_page=case_page.replace('来源：已冻结 V1 公开汇总、模拟器实现及经筛选的可见回复。历史过程材料移入 docs/archive；原始私有评测资料不随页面发布。','来源：模拟器实现、冻结提交与独立审阅。原始轨迹、实例参数和封存目标不随页面发布。')
(P/'case_study.html').write_text(case_page)
# Short compatibility entries preserve common bookmarked URLs and fragments.
for src,dst in [('overview.html','v1_results.html'),('progress-v2.html','progress.html'),('environment-expansion.html','progress.html'),('index.html','progress.html')]:
 (P/src).write_text(f'<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>报告已整合</title><meta http-equiv="refresh" content="0;url={dst}"><script>location.replace("{dst}"+location.hash)</script><a href="{dst}">打开整合报告</a></html>')

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
['自适应信号 adaptive_signaling','独立原型；研究适应响应背后的竞争解释','显式双模型driver已启动；结果待回收，共享注册尚未完成'],
['滞留输运 retention_transport','独立原型；研究表观延迟来自何种机制','显式双模型driver已启动；辨识与泛化表现待回收'],
['同位素配对 isotope_pairing','原型与前瞻工作流、预算预览、请求示例；Linux 隔离执行验证','显式 driver 已完成双模型实测；评分更正与新难度版本筛选见上方；未作共享注册'],
['谱系记忆 lineage_memory','已做有限样本筛选；强信号可分，弱信号及零信号尚不能可靠区分','暂缓；需要候选可获得的不确定性估计'],
['地震孔径 seismic_aperture','竞争模型的数值辨识见证；新噪声确认中分层结构不可行、均匀对照可行','仍为算子验证；不是已注册世界、独立新世界泛化或机制唯一性证明']
])+'''<p>目前三个环境原型均未作为新的正式模型评测任务注册。前两原型合计定义四个任务；候选验证、算子演示、完整环境和模型测评分别统计，避免把数量当成熟度。同位素已有模型结果；自适应信号和滞留输运正在双模型实测。</p>''')
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
 if live.get('history_round2'):
  progress=section('history-screening','自适应信号与滞留输运 · 双模型实测中','<p>8次运行：每环境2个实例，每实例GPT与DeepSeek配对。预测权重50%新条件、30%干预、20%声明复验；排除已知零响应和无效因果对照。尚无最终分数。</p><p>'+esc(live['history_round2']['claim_caveat'])+'</p>')+progress
 if live.get('isotope_sidecar'):
  side=live['isotope_sidecar']
  sr=[[x['model'],x['instance'],*[f"{x[k]:.2f}" for k in ('conditions','interventions','claims','score')]] for x in side['runs']]
  sr.append(['GPT-5.6','开发实例2','—','—','—','连接断开，缺失'])
  progress=section('isotope-correction','同位素 · 封存预测器评分更正', '<p>三个已提交预测器原样重放，仅修正评分器对合法数值数组的兼容性。原报告未覆盖；这不是新一轮模型实验。声明分沿用原冻结复验，避免评分版本号改变随机噪声样本。</p>'+table(['模型','实例','新条件','干预','声明','总分'],sr)+'<p>48 个预测面板全部有效；更正未新增 API 请求。独立审阅状态：'+esc(side['status'])+'。这些开发实例上的高分不能证明机制辨识或发现深度，也不支持将当前版本称为高难；两模型资源预算仍不同。</p>')+progress

(P/'progress.html').write_text(page('当前进度与下一步',progress))
body='''<p>一个可以干预、采样和预测的虚拟封闭培养舱。研究者只看到三种未知菌株与三个匿名化学信号，要从实验中识别它们的相互作用，并预测未做过的条件。</p><div class="notice">本页是设计者视角的公开案例说明，包含机制方程族；它不是提供给被测模型的题面。实际评测实例参数、随机种子、通道映射和封存测试目标不公开。模型已经看到本页后，不宜再用同一机制作为“完全未知”的测试。</div><nav><a href="#intro">简介</a><a href="#equations">隐藏方程</a><a href="#concealment">如何隐藏</a><a href="#noise">随机干扰</a><a href="#construction">评测构建</a><a href="#tools">工具 / MCP</a><a href="#results">结果</a><a href="#replies">真实回复</a><a href="#depth">发现深度</a></nav>'''
body+=section('intro','1 · 三种菌如何互相影响','''<p>甲菌 A 吃外界营养 S，产生可供乙菌使用的 X，同时排出废物 Z。乙菌 B 利用 X 并产生 Y。Y 抑制丙菌 C 对 Z 的利用；而 C 平时通过清除 Z 帮助 A。于是 B 的增长可能经由 Y、C、Z，延迟影响 A。</p><pre class="equation">营养 S → A → X → B → Y ┤ C
             A → Z ┤ A    C 清除 Z

正向支持：A 提供 X → B 得到底物
间接抑制：B 产生 Y → C 清除能力下降 → Z 积累 → A 受抑制</pre><p>这里的延迟来自分子积累、消耗与菌量变化，不是方程里直接写入固定“延迟 τ”。看见两条曲线先后变化，只是提出反馈假说的线索。</p><p>这是一套虚构、可计算的碳流模型，不是对某种真实菌群的拟合。所有状态统一按 mmol C/L 表示，时间用小时。</p>''')
body+=section('equations','2 · 隐藏规律的方程','''<p>状态为 (S,A,B,C,X,Y,Z,W)。W 是不可观测惰性碳池。θ = 2<sup>(T−30)/10</sup> 表示温度倍率；u 为最大摄取率，K 为半饱和常数，I 为抑制尺度，d 为死亡率，δ 为分解率。所有符号参数取正值。</p><pre class="equation">qA = θ uA A · S/(KS + S) · 1/[1 + (Z/IA)²]
qB = θ uB B · X/(KX + X)
qC = θ uC C · Z/(KZ + Z) · 1/[1 + (Y/IC)²]

S′ = −qA
A′ = 0.40 qA − θ d A
B′ = 0.45 qB − θ d B
C′ = 0.50 qC − θ d C
X′ = 0.35 qA − qB − θ δX X
Y′ = 0.55 qB − θ δY Y
Z′ = 0.25 qA − qC
W′ = 0.50 qC + θ d(A+B+C) + θ δX X + θ δY Y</pre><p>A 摄取碳后，40% 转为自身、35% 转为 X、25% 转为 Z；B 将 X 分成自身和 Y；C 将 Z 分成自身和惰性碳。死亡与分解转入 W。因此在没有外部事件时，八个状态总量守恒。</p><p>实现使用 DOP853 积分，rtol=10⁻⁹、atol=10⁻¹¹、最大步长 0.5 小时；检查有限值、负值和碳守恒。补料增加总碳，移除分子减少总碳，不能跨这些外部事件强行要求总量不变。</p><p>代码：<a href="https://github.com/Geniusyingmanji/ScientistsLastExam/blob/codex/env/env/microecology/kernel.py">kernel.py</a>（动力学），<a href="https://github.com/Geniusyingmanji/ScientistsLastExam/blob/codex/env/env/microecology/world.py">world.py</a>（可观测接口与噪声）。</p><div class="notice"><h3>这些方程描述了什么</h3><p>可以把培养舱想成一个只有三类居民的小社区。A 靠外面投放的食物生活，吃东西后留下两类物质：一种能喂养 B，另一种积多了会妨碍 A 自己。C 能清理后一种物质，因此 C 虽然没有直接给 A 喂食，却在帮助 A 生长。</p><p>B 吃掉 A 留下的食物，又产生一种会让 C 清理变慢的物质。于是，B 的活动可能先影响 C，再让废物积起来，最后影响 A。这几步需要时间，所以系统不会在 B 增多的瞬间就出现全部后果。</p><p>公式中的 qA、qB、qC 就是三种菌“每小时吃掉多少”的速度。食物越多，吃得通常越快，但会逐渐接近上限；抑制物越多，相关菌的摄取速度就越低。A′、B′、C′ 表示菌量此刻是在增加还是减少：吃进去后长出的部分，减去死亡的部分。</p><p>最后的 W 像一个不再参与生长的碳储存池。菌死后、分子分解后，碳没有凭空消失，而是转入这里。把八个量一起算，才能检查这个虚拟世界有没有“无中生有”。</p></div>''')
body+=section('concealment','3 · 规律如何藏起来',table(['设计','模型能够看到什么','需要解决什么'],[['匿名信号','peak-01 / peak-02 / peak-03；同一实例映射固定','不能根据名字直接知道谁是底物、抑制物或废物'],['部分可观测','A、B、C、营养和三个峰；没有 W','看不到全部碳池，需避免把缺失质量误判成新反应'],['实例变化','每参数在默认值的 0.9–1.1 倍独立采样','同一实验内参数固定，不允许靠背一组数值过关'],['有限实验','单培养、混合培养、温度、补料、选择性移除','要区分相关性、资源支持与间接抑制'],['连续动力学','有噪声离散采样','需要捕捉先后次序、剂量关系和时滞，而非只比较终点']])+'''<p>源代码与封存面板由宿主持有；隔离分析与预测执行器只接收允许的数据。公开机制文档是解释材料，并不构成抗污染保证：后续正式版本还需新的机制组合、私有实例与隔离检查。</p><div class="notice"><h3>模型实际面对的谜题</h3><p>设计者知道谁在喂养谁、谁在抑制谁，但模型拿到的不是这张关系图。它看到的是 A、B、C 的数量，以及三个只有编号的化学信号。就像看到三盏仪表灯一起变化，却不知道每盏灯连着哪一段管道。</p><p>例如，某个峰升高时 A 恰好减少，不能立刻认定“这个峰毒害了 A”：也可能是食物快吃完了，或者另一个菌先发生变化，间接影响了 A。模型需要主动改变条件——只养一种菌、拿掉一种菌，或移除某个峰——再看后面的变化是否符合自己的解释。</p><p>不同实例会轻微改变反应速度，还会重新排列三个峰的编号。因此，记住“第一个峰一定是什么”不够；模型需要在当前世界里重新找证据。同一实例内部的规则保持稳定，让重复实验和对照仍然有意义。</p><p>真正要解开的不是三个名字，而是：改变哪一步，会先影响谁、再影响谁？如果换一个起始条件或干预时刻，这个解释还能预测结果吗？</p></div>''')
body+=section('noise','4 · 现有随机性与拟增加的干扰','''<h3>V1 已实现</h3><p>动力学本身确定性。每次观测加入独立高斯测量误差，再截断为非负：ŷⱼ = max(0, hⱼ(x) + εⱼ)。菌量噪声标准差 0.002，营养与匿名峰为 0.004 mmol C/L。零附近的截断会使读数均值产生偏差；重复观测不会完全恢复未截断均值。另有跨实例参数变化和匿名峰排列。</p><h3>下一版本方案：尚未加入、不改变 V1 成绩</h3>'''+table(['随机干扰','候选形式','如何避免把噪声当难度'],[['仪器漂移','ŷⱼ(t)=max(0,(1+bⱼ)xⱼ(t)+aⱼ(t)+εⱼ)','提供空白/标准校准；处理与对照交错执行'],['无因果作用的杂峰','额外 D 满足 D′=输入−衰减，对菌量无反馈','允许针对 D 的负对照；不能只靠峰数量迷惑'],['批次差异','log uᵦ = log u + ηᵦ，同批次共享扰动','显式批次标签、配对与独立重复，声明目标总体'],['过程噪声','随机通量而非直接独立扰动各状态','保持非负和碳流守恒；先验证预算内可辨识性']])+'''<p>先独立筛选每种干扰，再做组合；冻结噪声幅度、重复预算和校准协议，检查竞争机制能否区分。不能一边看模型成绩一边增大噪声，也不能把无解或服务失败算作发现难度。</p>''')
body+=section('construction','5 · 评测环境如何构建','''<ol><li>为每个实例固定机制参数与匿名峰映射，同实例不同实验共享同一世界；不同调用从新的培养批次开始，不继承前一次培养状态。</li><li>模型收到公共规则、合法实验结构与预算，自选实验并获得带噪观测。</li><li>在隔离 Python 中分析已得数据，提交冻结预测程序或已保存模型快照，以及最多三条效应区间声明。</li><li>宿主在预先封存的新条件与干预面板上运行预测器；预测目标为无噪声期望响应。</li><li>声明使用新噪声重复验证，保存原始证据和哈希；公开报告只放汇总和选定可见回复。</li></ol>'''+table(['资源','本批规则'],[['每环境实例 / 重复','3 个实例 × 2 次运行'],['每次动作轮数','最多 16 次请求，探索轮上限 14'],['实验','最多 48 个、每批最多 8 个、总实验单位 30000'],['分析 / 预测','分析活跃时间 180 秒；每个条件预测器 15 秒'],['运行时间 / 输出','GPT 1 小时 / 8k；DeepSeek 4 小时 / 32k']])+'''<p>上述共同限制不能消除输出与时间预算差异。本页结果使用补齐后的成功交付口径；原始失败和补跑成本仍保留在 <a href="v1_results.html">V1 审计详情</a>。</p>''')
body+=section('tools','6 · 实验工具与 MCP 边界','''<p><strong>当前评测使用 Python runner 的 JSON 动作协议，并非独立部署的 MCP server。</strong>概念上可映射为 run_experiments、analyze、submit 三个 MCP 工具，但这里不声称该封装已经实现。</p>'''+table(['动作','功能 / 边界'],[['experiments','每条是新批次；初始菌量各 0–1，营养 0–10，温度 20–40°C，1–32 个递增采样点，最长 72 小时'],['events','最多 4 个；补营养 0–3、移除某峰比例 0–1、改变温度；同一采样时刻先执行事件再读数'],['analyze','隔离 Python 分析已观察记录；不能读取隐藏机制或封存目标'],['submit','冻结预测器、最多 3 条定量声明与解释；之后宿主验证']])+'''<p>每实验成本 = 8 + 采样点数 + 2×事件数 + ceil(末次时间/12)。本批没有上清转移、任意分子添加或持续培养舱库存；其他原型接口不能混写进这次模型能力。</p><h3>合法动作示例（说明用，不是历史模型调用）</h3><pre>{"note":"比较移除匿名峰后的延迟响应", "experiments":[
 {"initial":{"A":0.05,"B":0.05,"C":0.05,"nutrient":5},
  "temperature_c":30,"times_h":[0,6,12,24,48],
  "events":[{"time_h":12,"deplete":{"channel":"peak-01","fraction":0.8}}]}
]}</pre><p>观测返回采样轴、通道名、数值矩阵和观测编号。每条声明应绑定既有观测编号、明确处理与对照、输出通道、时间和区间；不是提交一个隐藏机制名称。</p>''')
body+=section('scoring','7 · 评分标准','''<p><strong>总分 = 0.5 × 新条件预测 + 0.3 × 干预预测 + 0.2 × 声明复验。</strong>它是数值表现指数，不是发现率。</p><h3 id="new-condition-score">7.1 新条件预测：换一组起始条件，还能预测生长曲线吗？</h3>
<p><strong>含义：</strong>在同一个隐藏世界里，宿主给出新的起始菌量、营养量、温度和采样时刻，模型用已冻结的预测器预测各时刻的菌量与化学信号。微生态这一组没有培养过程中的事件。它考查从已做实验迁移到新条件的能力；“新”不一定意味着超出训练范围，也可能是范围内未实验过的组合。</p>
<p><strong>说明例子：</strong>探索时做过几组 30°C 培养；评测给出另一组初始菌量、4 单位营养、28°C，要求预测随后各时刻 A、B、C、营养及三个峰的数值。这里的数字只用于解释，不是实际封存试题。</p>
<p><strong>计算：</strong>① 将预测值与模拟器的无噪声响应逐格比较；② 用对应通道尺度除误差；③ 对本实验保留的所有“时间 × 通道”格子计算均方根误差；④ 转为 0–100 分；⑤ 对这一类实验的分数等权平均。不是先把所有实验的误差混合后再转换。</p>
<h3 id="intervention-score">7.2 干预预测：培养中途动一下系统，还能预测后果吗？</h3>
<p><strong>含义：</strong>除起始条件外，宿主还给出中途操作，例如补营养、移除某个匿名峰的一部分，或者改变温度。预测器必须把事件时间、力度与后续动力学一起考虑，预测整个实验的观测轨迹。</p>
<p><strong>说明例子：</strong>在第 12 小时移除 peak-01 的 80%，预测第 24、48 小时三种菌及其他化学信号如何变化。峰立刻减少是操作直接规定的；更有科学意义的是后续影响能否沿相互作用传播。这是说明例子，不披露实际测试面板。</p>
<p><strong>计算：</strong>与新条件预测使用相同的归一化误差和指数转换，只是评分实验包含干预。当前微生态分项评的是<strong>带事件的轨迹数值</strong>，不是单独对“处理减对照”的因果效应打分，也不是仅检查事件后的一个终点。两类预测分别求均分，再按 50% 与 30% 加权。</p>
<h3>两类预测共用的计算式与算例</h3>
<pre>保留格子集合 Mₑ；通道尺度 sⱼ；模拟器目标 y；模型预测 ŷ：
NRMSEₑ = sqrt( Σ[(ŷₜⱼ − yₜⱼ)/sⱼ]² / |Mₑ| )，求和只含 Mₑ
单实验分 = 100 × exp(−NRMSEₑ / 0.1)
新条件分 = 所有新条件实验分的平均
干预分   = 所有干预实验分的平均</pre>
<p>菌量与峰尺度为 1，营养尺度为 5。因此菌量误差 0.05 与营养误差 0.25 都对应归一化误差 0.05。若一个实验的 NRMSE 为 0.05，得分约 60.65；若为 0.10，约 36.79；误差为零得 100。两实验分别为 60.65 和 36.79 时，该组均分为 48.72。以上是公式算例，不是模型实测结果。</p>
<p>微生态不计 t=0、未接种菌株的全列，以及完全移除某峰在事件瞬间的已知零值。其他保留格子不保证都能辨识机制。探索观测带噪，但这两项预测评分针对无噪声目标。</p>
<h3 id="claim-score">7.3 声明复验：模型自己提出的定量结论，能被新实验复现吗？</h3>
<p><strong>含义：</strong>模型自主选择最多三条定量效应声明，写清处理、对照、读数通道、读数时间、证据编号和适用范围，并提交“处理减对照”的均值的 90% 预测区间。宿主按这些条件重新实验，而不是把自然语言结论与某个标准机制名称比对。</p>
<p><strong>说明例子：</strong>“其他条件相同，在第 12 小时补营养，相比不补料，第 24 小时 A 的增加量落在 [0.10, 0.14]。”宿主分别运行 32 次处理与 32 次对照，用新观测计算 32 个差值的平均 z。这验证的是该条件下的数值效应；即使通过，也不等于证明了整条反馈链。</p>
<p><strong>计算：</strong>区间宽度是基本损失，防止随便报一个很宽的范围；新复验均值落在区间外时，再加入 20 倍的越界距离。损失按通道尺度归一化并转成指数分。缺失、重复或不符合资格的声明槽位为零，固定除以三个槽位，而不是除以实际提交条数。</p>
<pre>z = (1/32) Σᵣ (处理读数ᵣ − 对照读数ᵣ)
区间损失 IS = (U−L) + 20 max(L−z, 0) + 20 max(z−U, 0)
单声明分 = 100 × exp(−IS / (0.1 × 通道尺度))
声明复验分 = (声明1分 + 声明2分 + 声明3分) / 3</pre>
<p>仍用菌量尺度 1、区间 [0.10, 0.14] 举例：若 z=0.12，损失为 0.04，得 67.03 分；若 z=0.16，越界 0.02，损失为 0.04+20×0.02=0.44，得 1.23 分。报 [0,1] 虽能覆盖很多结果，但宽度损失为 1，仅得约 0.0045 分。只提交一条 67.03 分的声明，其余两槽缺失，声明分为 22.34。</p>
<p>“90%”描述提交区间的统计目标，不代表覆盖一次就自动得到 90 分；复验使用的是带噪重复的均值。原始区间损失具有适当评分性质，指数变换后的汇总不继承这种保证。</p>
<h3>7.4 三项怎样合成最后的成绩？</h3>
<p>每次运行先算三项，再计算 <strong>0.5×新条件分 + 0.3×干预分 + 0.2×声明分</strong>。例如三项为 60、40、80，总分就是 30+12+16=58。每环境展示六次预定槽位成绩的均值，十二环境总分再按环境等权平均；当前主表采用已说明的补齐口径。</p>
<p><strong>阅读结果时：</strong>新条件分回答“换条件预测得准不准”；干预分回答“施加操作后预测得准不准”；声明分回答“自选的局部定量结论能否复现”。三者都不能单独证明机制唯一性或发现深度。</p>
''')
rows=[]
for label,k in [('GPT-5.6','reference'),('DeepSeek V4 Pro','candidate')]:
 x=w[k];c=x['components'];rows.append([label,f"{x['score']:.2f}",*[f'{c[t]:.2f}' for t in ['condition_score','intervention_score','claim_score']]])
body+=section('results','8 · 两模型在微生态上的结果',table(['模型','总分','新条件','干预','声明'],rows)+table(['实例 / 重复','GPT','DeepSeek','差值 DS−GPT'],[[f"i{x['instance']} / r{x['repeat']}",f"{x['reference']['score']:.2f}",f"{x['candidate']['score']:.2f}",f"{x['delta']:+.2f}"] for x in w['pairs']])+'''<p>两模型在这个环境的新条件与干预预测均较弱。DeepSeek 的局部声明表现较高，不能解释为已经发现整条反馈链。GPT 不同运行波动明显；六次成绩也不足以认证稳定能力差异。</p>''')
ex=json.loads((P/'data/microecology-visible-excerpts.json').read_text());parts='''<p>以下选择同一配对 i2-r1 说明方法差异，未按高分选例，也不代表六次运行都采用相同策略。引文仅为模型公开可见的 note 与最终解释；不是内部思考。note 描述计划，不等于操作或拟合成功。</p>'''
translations=json.loads((P/'data/microecology-translations-zh.json').read_text())
def bilingual(zh,en):
 return '<p><strong>中文翻译：</strong>'+esc(zh)+'</p><details><summary>英文原文</summary><p>'+esc(en)+'</p></details>'
parts+='<p class="notice">中文为报告补充的翻译，英文原文可展开核对。翻译保留模型的自述语气；其中“已完成”“稳健”等表述不代表评审确认。</p>'
for x in ex:
 t=translations[x['model']]
 parts+='<h3>'+x['model']+f" · 本次 {x['score']:.2f} 分</h3>"
 parts+=table(['轮次','模型可见回复 · 中文 / 原文','请求动作'],[[a['round'],bilingual(t['notes'][str(a['round'])],a['note']),esc(', '.join(a['action']) or '仅 note')] for a in x['visible_notes']])
 parts+='<h4>最终解释</h4>'+bilingual(t['explanation'],x['explanation'])
 parts+=table(['提交的定量声明 · 中文 / 原文','区间','模型自述适用范围 · 中文 / 原文'],[[bilingual(z['statement'],c['statement']),esc(str(c['interval'])),bilingual(z['scope'],c['scope'])] for c,z in zip(x['claims'],t['claims'])])
 parts+='<p class="muted">来源报告 SHA-256：'+x['report_sha256']+'</p>'
parts+='''<p>GPT 完成 48 个实验，最后提交动力学预测器，但声明集中在“补料后一小时还剩多少营养”；这是可复验的效应，不是对反馈链的决定性检验。DeepSeek 获得 40 个观测，最终使用记忆型 surrogate；提出的是单菌营养/温度效应及一个同时改变多因素的混合培养对比。它自己承认第三条存在混杂，不能据此定位单一路径。</p><p>两个模型都曾请求 ODE 拟合，不能仅凭 note 认定拟合成功或机制恢复。最终解释与实际低预测分需要并列阅读。逐轮完整原始轨迹保留私有，本页公开经过筛选的引文。</p>'''
body+=section('replies','9 · 模型实际怎样研究与回答',parts)
body+=section('depth','10 · 发现深度与下一步改进','''<p>现有证据支持局部响应发现和探索尝试；不能确认两个模型都重建了完整延迟反馈机制。</p>'''+table(['证据层次','本例需要什么','当前结论'],[['现象','单菌/混合曲线、营养和温度响应','两模型都探索到局部差异'],['局部效应','配对处理/对照、延迟测量、重复不确定性','部分声明可复验；补料余量等容易效应占比高'],['竞争机制区分','直接抑制 vs 底物耗尽 vs 间接反馈的分歧实验','提交文字不足以排除竞争解释'],['组合外推','不同组成、温度、事件时间和多事件组合','两模型预测分较低，仍不稳定']])+'''<h3>建议的辨识实验（未在本次追加运行）</h3><p>先用去掉 B 或 C 的培养确定依赖背景，再在匹配起始条件中移除匿名峰，连续观察 C、另一峰和 A 的后续变化。通过多种事件时间与剂量检查效应顺序。只看被移除分子立即下降没有辨识价值；应要求预测下游菌量变化和竞争解释相反的条件。未来若加入分子 add-back 工具，必须作为新版本重新冻结。</p><p>评分改进应把数值预测、局部效应校准、竞争模型排除分开报告，奖励能排除替代解释的实验；同时保留允许“证据不足”的开放发现结论。当前分数不追溯改动。</p>''')
(P/'case_study.html').write_text(page('微生态（三菌株）完整案例',body))
# Short compatibility entries preserve common bookmarked URLs and fragments.
for src,dst in [('overview.html','v1_results.html'),('progress-v2.html','progress.html'),('environment-expansion.html','progress.html'),('index.html','progress.html')]:
 (P/src).write_text(f'<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>报告已整合</title><meta http-equiv="refresh" content="0;url={dst}"><script>location.replace("{dst}"+location.hash)</script><a href="{dst}">打开整合报告</a></html>')

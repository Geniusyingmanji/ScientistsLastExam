"""Public stdio MCP bridge: no kernel imports or operator filesystem reads."""
import json,sys,urllib.request,os
URL=os.environ['SLE_EXPERIMENT_URL']
TOOLS=[{'name':'describe','description':'Read public apparatus and budget.','inputSchema':{'type':'object','properties':{},'additionalProperties':False}},
 {'name':'experiment','description':'Execute fresh vessel; experiment_id required, invalid attempts count.','inputSchema':{'type':'object','properties':{'experiment_id':{'type':'string'},'spec':{'type':'object'}},'required':['experiment_id','spec'],'additionalProperties':False}},
 {'name':'register_prediction','description':'Immutable prospective time-major prediction for a future experiment. No observation or hidden feedback.','inputSchema':{'type':'object','properties':{'experiment_id':{'type':'string'},'spec':{'type':'object'},'prediction':{'type':'array','items':{'type':'number'}},'model_sha256':{'type':'string'}},'required':['experiment_id','spec','prediction','model_sha256'],'additionalProperties':False}}]
for line in sys.stdin:
 try:
  q=json.loads(line)
  if 'id' not in q:continue
  m=q.get('method')
  if m=='initialize':r={'protocolVersion':'2024-11-05','capabilities':{'tools':{}},'serverInfo':{'name':'ecology-lab','version':'0.1'}}
  elif m=='tools/list':r={'tools':TOOLS}
  elif m=='tools/call':
   p=q['params'];name=p['name']
   if name not in ('describe','experiment','register_prediction'):raise ValueError('unknown tool')
   body={'tool':name}
   if name!='describe':body.update(p['arguments'])
   body['tool']=name
   req=urllib.request.Request(URL,data=json.dumps(body).encode(),headers={'Content-Type':'application/json'})
   with urllib.request.urlopen(req,timeout=30) as response:content=response.read().decode()
   r={'content':[{'type':'text','text':content}]}
  elif m=='ping':r={}
  else:raise ValueError('unsupported method')
  out={'jsonrpc':'2.0','id':q['id'],'result':r}
 except Exception:out={'jsonrpc':'2.0','id':q.get('id'),'error':{'code':-32602,'message':'tool request failed'}}
 print(json.dumps(out),flush=True)

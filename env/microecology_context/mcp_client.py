"""Public stdio MCP bridge: no kernel imports or operator filesystem reads."""
import json,sys,urllib.request,os
URL=os.environ['SLE_EXPERIMENT_URL']
TOOLS=[{'name':'describe','description':'Read apparatus contract and experimental budget.','inputSchema':{'type':'object','properties':{},'additionalProperties':False}},
       {'name':'experiment','description':'Run a fresh vessel experiment; all preparation events execute. Each attempt spends one of48 experiments.','inputSchema':{'type':'object','properties':{'spec':{'type':'object'}},'required':['spec'],'additionalProperties':False}}]
for line in sys.stdin:
 try:
  q=json.loads(line)
  if 'id' not in q:continue
  m=q.get('method')
  if m=='initialize':r={'protocolVersion':'2024-11-05','capabilities':{'tools':{}},'serverInfo':{'name':'ecology-lab','version':'0.1'}}
  elif m=='tools/list':r={'tools':TOOLS}
  elif m=='tools/call':
   p=q['params'];name=p['name']
   if name not in ('describe','experiment'):raise ValueError('unknown tool')
   body={'tool':name}
   if name=='experiment':body['spec']=p['arguments']['spec']
   req=urllib.request.Request(URL,data=json.dumps(body).encode(),headers={'Content-Type':'application/json'})
   with urllib.request.urlopen(req,timeout=30) as response:content=response.read().decode()
   r={'content':[{'type':'text','text':content}]}
  elif m=='ping':r={}
  else:raise ValueError('unsupported method')
  out={'jsonrpc':'2.0','id':q['id'],'result':r}
 except Exception:out={'jsonrpc':'2.0','id':q.get('id'),'error':{'code':-32602,'message':'tool request failed'}}
 print(json.dumps(out),flush=True)

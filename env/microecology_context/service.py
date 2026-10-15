"""Trusted experimental HTTP endpoint. Run outside the candidate filesystem."""
import argparse,json,threading,time
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from .world import World,CHANNELS

DESCRIPTION={
 'units':'mmol carbon/L; time hours; temperature Celsius',
 'channels':list(CHANNELS),'chemical_identity':'m1..m4 are independently measurable and manipulable anonymous chemical pools; residue is inert carbon',
 'reset':'Each experiment starts a fresh vessel. All hidden adaptation states start at the same rested state. Every scheduled preparation executes even if not observed.',
 'initial':'dictionary of channel concentrations; omitted=0. A/B/C0..1, substrate0..5, other channels0..2',
 'times':'strictly increasing array of1..25 times in0..48h',
 'temperature':'optional20..40, default30',
 'events':'optional <=8 ordered events: {time,temperature} or {time,channel,add} or {time,channel,remove}. add0..2(total<=8),remove fraction0..1. Events precede measurement at same time. Addition/removal changes carbon inventory. Cell removal leaves dissolved pools intact.',
 'noise':'independent Gaussian measurement noise sd.002 per channel, clipped at0; no process noise in this version',
 'budget':'48 experiment attempts, invalid attempts also count; no clean-output or hidden-state access',
 'task':'Discover quantitative dynamics, context dependence and unresolved alternatives. Submit equations with units and scope, experimental evidence, uncertainty and executable model. Do not assume any named biological species or equation family.'}

def main():
 p=argparse.ArgumentParser();p.add_argument('--seed',type=int,required=True);p.add_argument('--family',required=True);p.add_argument('--port',type=int,required=True);p.add_argument('--out',required=True);a=p.parse_args()
 world=World(a.seed,a.family);lock=threading.Lock();root=Path(a.out);root.mkdir(parents=True,exist_ok=True);count=0
 class Handler(BaseHTTPRequestHandler):
  def log_message(self,*args):pass
  def do_POST(self):
   nonlocal count
   with lock:
    try:
     length=int(self.headers.get('Content-Length',0))
     if not 0<length<=65536:raise ValueError('invalid request length')
     obj=json.loads(self.rfile.read(length));tool=obj['tool']
     if tool=='describe':result=DESCRIPTION
     elif tool=='experiment':
      if count>=48:raise ValueError('experiment budget exhausted')
      count+=1;start=time.time()
      try:result=world.run(obj['spec']);result.update(observation_id='obs-%03d'%count,remaining=48-count)
      except (ValueError,TypeError,KeyError):result={'error':'invalid experiment; see describe','remaining':48-count}
      with (root/'observations.jsonl').open('a') as f:f.write(json.dumps(dict(at=start,request=obj,response=result))+'\n')
     else:raise ValueError('unknown tool')
    except (ValueError,TypeError,KeyError,json.JSONDecodeError):result={'error':'request rejected'}
    body=json.dumps(result).encode();self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
 ThreadingHTTPServer(('127.0.0.1',a.port),Handler).serve_forever()
if __name__=='__main__':main()

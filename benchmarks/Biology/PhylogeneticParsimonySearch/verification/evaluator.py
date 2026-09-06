"""Maximum-parsimony verifier over deterministic synthetic alignments."""
from __future__ import annotations
import re
import numpy as np
from scipy.cluster.hierarchy import linkage
from scipy.spatial.distance import squareform

N=18; SITES=240; SPECS=(501,502,503,504,505); DEV=range(3); HELD=range(3,5)

def _alignment(seed):
 rng=np.random.default_rng(seed); root=rng.integers(0,4,SITES); seqs=[]
 for i in range(N):
  x=root.copy(); crng=np.random.default_rng((seed,i//5,17)); mask=crng.random(SITES)<.10; x[mask]=crng.integers(0,4,mask.sum())
  mask=rng.random(SITES)<(.025+.004*(i%5)); x[mask]=rng.integers(0,4,mask.sum()); seqs.append(x)
 return np.asarray(seqs,dtype=int)

def _problem(seed):
 a=_alignment(seed); alphabet=np.array(list("ACGT"))
 return {"taxa":[f"t{i}" for i in range(N)],"alignment":["".join(alphabet[row]) for row in a],
         "criterion":"unordered_fitch_parsimony","missing_symbol":"?"}

def _parse_newick(text,taxa):
 if not isinstance(text,str) or len(text)>10000: raise ValueError("bad tree")
 tokens=re.findall(r"[(),;]|[A-Za-z][A-Za-z0-9_]*",text.strip())
 if "".join(tokens)!=re.sub(r"\s+","",text): raise ValueError("unsupported Newick token")
 pos=0; next_node=[0]; adj={}; labels={}
 def node():
  nonlocal pos
  me=next_node[0]; next_node[0]+=1; adj[me]=[]
  if pos<len(tokens) and tokens[pos]=="(":
   pos+=1; children=[]
   while True:
    children.append(node())
    if pos<len(tokens) and tokens[pos]==",": pos+=1
    else: break
   if pos>=len(tokens) or tokens[pos]!=")" or len(children)!=2: raise ValueError("tree must be binary")
   pos+=1
   for c in children: adj[me].append(c); adj[c].append(me)
  else:
   if pos>=len(tokens) or tokens[pos] in "(),;": raise ValueError("missing leaf")
   labels[me]=tokens[pos]; pos+=1
  return me
 root=node()
 if pos<len(tokens) and tokens[pos]==";": pos+=1
 if pos!=len(tokens) or sorted(labels.values())!=sorted(taxa) or len(labels)!=len(taxa): raise ValueError("taxa mismatch")
 return root,adj,labels

def _fitch(text,problem):
 root,adj,labels=_parse_newick(text,problem["taxa"]); encoded={c:i for i,c in enumerate("ACGT")}; seq=dict(zip(problem["taxa"],problem["alignment"])); total=0
 def walk(u,parent,site):
  nonlocal total
  if u in labels: return {encoded[seq[labels[u]][site]]}
  children=[v for v in adj[u] if v!=parent]; sets=[walk(v,u,site) for v in children]
  inter=sets[0]&sets[1]
  if inter: return inter
  total+=1; return sets[0]|sets[1]
 for site in range(len(problem["alignment"][0])): walk(root,-1,site)
 return total

def _caterpillar(taxa):
 tree=f"({taxa[0]},{taxa[1]})"
 for x in taxa[2:]: tree=f"({tree},{x})"
 return tree+";"

def _upgma(problem):
 seq=problem["alignment"]; n=len(seq); d=np.zeros((n,n))
 for i in range(n):
  for j in range(i): d[i,j]=d[j,i]=sum(a!=b for a,b in zip(seq[i],seq[j]))/len(seq[i])
 z=linkage(squareform(d),method="average"); nodes={i:problem["taxa"][i] for i in range(n)}
 for k,row in enumerate(z): nodes[n+k]=f"({nodes[int(row[0])]},{nodes[int(row[1])]})"
 return nodes[2*n-2]+";"

def evaluate(build_tree):
 rows=[]
 for seed in SPECS:
  p=_problem(seed); baseline=_fitch(_caterpillar(p["taxa"]),p); reference=_fitch(_upgma(p),p)
  try: tree=build_tree(p); score_value=_fitch(tree,p); valid=True
  except Exception: score_value=baseline; valid=False
  score=float(max(0.0,(baseline-score_value)/max(1,baseline-reference)))
  rows.append({"seed":seed,"valid":valid,"parsimony":score_value,"baseline":baseline,"reference":reference,"score":score})
 dev=[rows[i] for i in DEV]; held=[rows[i] for i in HELD]
 return {"combined_score":float(np.mean([r["score"] for r in dev])),"valid":1.0 if all(r["valid"] for r in dev) else 0.0,
         "feasibility_rate":float(np.mean([r["valid"] for r in dev])),"heldout_score":float(np.mean([r["score"] for r in held])),"per_instance":rows}

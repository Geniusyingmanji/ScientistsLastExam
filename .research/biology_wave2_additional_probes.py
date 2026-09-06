"""Reproduce narrow wave-two shortcut probes; run from the project environment."""
from pathlib import Path
import importlib.util,json
import numpy as np
root=Path(__file__).resolve().parents[1]
def load(name):
 s=importlib.util.spec_from_file_location('probe',root/'benchmarks/Biology'/name/'verification/evaluator.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
results={}
m=load('SingleMoleculeKinetics');best=0
for a in np.geomspace(.1,3,16):
 for b in np.geomspace(.1,3,16):
  out=dict(abstain=False,rates=[float(a),float(b)],efficiencies=[.2,.8],confidence=1.)
  best=max(best,m.evaluate(lambda p,o:out)['combined_score'])
results['SingleMoleculeKinetics']={'constant_rate_grid_256_best':best}
m=load('IsotopeFluxIdentifiability');best=0
for v in np.linspace(0,1.2,16):
 for x in np.linspace(0,2,16):
  out=dict(abstain=False,fluxes=dict(net=float(v),exchange_total=float(x)),confidence=1.)
  best=max(best,m.evaluate(lambda p,t:out)['combined_score'])
results['IsotopeFluxIdentifiability']={'constant_flux_grid_256_best':best}
m=load('ProteinDistanceGeometry');p,_=m._world(0);n=len(p['atom_ids']);best=0
for angle in np.linspace(1.1,2.2,8):
 for radius in np.linspace(1.5,3.2,8):
  for pitch in np.linspace(1.,2.,4):
   xyz=np.column_stack([radius*np.cos(angle*np.arange(n)),radius*np.sin(angle*np.arange(n)),pitch*np.arange(n)]);xyz-=xyz.mean(axis=0)
   best=max(best,m._score_output(0,p,dict(coordinates=xyz.tolist()))[0])
results['ProteinDistanceGeometry']={'helix_grid_256_best':best,'mds_without_refinement_score':m._score_output(0,p,m.reference(p,max_nfev=1))[0]}
import argparse
parser = argparse.ArgumentParser()
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
args.output.write_text(json.dumps(results,indent=2)+'\n')
print(json.dumps(results,indent=2),flush=True)

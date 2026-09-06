"""Independent model checks for the second biology wave."""
import importlib.util
import itertools
from pathlib import Path
import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
def module(name):
 path=ROOT/'benchmarks/Biology'/name/'verification/evaluator.py'
 spec=importlib.util.spec_from_file_location(name,path)
 mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
 return mod

@pytest.mark.parametrize('bad',[None,[],{}, {'haplotype':None},{'haplotype':[]},{'haplotype':[0]}, {'haplotype':[False]*200}, {'haplotype':[0.]*200}, {'haplotype':[2]*200}, {'haplotype':[float('nan')]*200}, {'haplotype':[[0]]*200}, {'haplotype':[0]*200,'score':1}])
def test_haplotype_bad(bad):
 m=module('DiploidHaplotypeAssembly'); p,_,_=m._world(0)
 assert m._score_output(0,p,bad)==(0.,False)

def test_haplotype_independent_enumeration_and_symmetry():
 m=module('DiploidHaplotypeAssembly')
 p=dict(variant_ids=['a','b','c'],fragments=[dict(positions=[0,1,2],alleles=[1,0,1],error_probabilities=[.1,.2,.3])])
 for bits in itertools.product([0,1],repeat=3):
  expected=np.log(sum(np.prod([1-e if a==(b^flip) else e for a,b,e in zip([1,0,1],bits,[.1,.2,.3])]) for flip in (0,1))/2)
  assert m.likelihood(p,bits)==pytest.approx(expected)
  assert m.likelihood(p,bits)==pytest.approx(m.likelihood(p,[1-b for b in bits]))

def test_haplotype_reference_and_disconnected_blocks():
 m=module('DiploidHaplotypeAssembly'); p,truth,_=m._world(0)
 out=m.reference(p); score,valid=m._score_output(0,p,out)
 assert valid and score==pytest.approx(1)
 assert m._score_output(0,p,{'haplotype':[0]*200})==(0.,True)
 h=np.array(out['haplotype']); h[np.array(p['block_ids'])==1]^=1
 assert m.likelihood(p,h)==pytest.approx(m.likelihood(p,out['haplotype']))
 assert any(any(a!=truth[i] for i,a in zip(f['positions'],f['alleles'])) for f in p['fragments'])

@pytest.mark.parametrize('bad',[None,[],{}, {'protected_patches':None},{'protected_patches':'p0'},{'protected_patches':[0]}, {'protected_patches':[False]}, {'protected_patches':['unknown']}, {'protected_patches':[['p0']]}, {'protected_patches':['p0','p0']}, {'protected_patches':[],'score':1}, {'protected_patches':[f'p{i}' for i in range(40)]}])
def test_reserve_bad(bad):
 m=module('RobustReserveNetworkDesign'); assert m._score_output(0,m._problem(0),bad)==(0.,False)

def test_reserve_analytic_and_sources():
 m=module('RobustReserveNetworkDesign')
 p=dict(patch_ids=['x'],habitat_quality=[[[.7]]],initial_occupancy=[[.8]],dispersal_matrices=[[[[0.]]]],extinction_rates=[[[.2]]],time_grid=list(range(6)),species_weights=[2.])
 assert m.utility(p,['x'])==pytest.approx(2*.7*.8*.8**5)
 assert m.utility(p,[])==0
 p['initial_occupancy']=[[0.]]; p['dispersal_matrices']=[[[[100.]]]]
 assert m.utility(p,['x'])==0

def test_reserve_reference_and_connectivity():
 m=module('RobustReserveNetworkDesign'); p=m._problem(0); out=m.reference(p)
 assert m._score_output(0,p,out)==(1.,True)
 assert m._score_output(0,p,{'protected_patches':[]})==(0.,True)
 assert np.all(m.scenario_utilities(p,out['protected_patches'])>=0)
 raw=m.utility(p,out['protected_patches'])
 p['dispersal_matrices']=np.zeros_like(p['dispersal_matrices']).tolist()
 assert m.utility(p,out['protected_patches'])<raw*.5

@pytest.mark.parametrize('bad',[None,[],{}, {'abstain':True}, {'abstain':1,'rates':[],'efficiencies':[],'confidence':.5}, {'abstain':True,'rates':[1,1],'efficiencies':[],'confidence':.5}, {'abstain':False,'rates':[1,1],'efficiencies':[.2,.8],'confidence':float('nan')}, {'abstain':False,'rates':[[1],[1]],'efficiencies':[.2,.8],'confidence':.5}, {'abstain':False,'rates':[True,1],'efficiencies':[.2,.8],'confidence':.5}, {'abstain':False,'rates':[0,1],'efficiencies':[.2,.8],'confidence':.5}, {'abstain':False,'rates':[1,1],'efficiencies':[.2,2],'confidence':.5}, {'abstain':True,'rates':[],'efficiencies':[],'confidence':2}])
def test_kinetics_bad(bad):
 assert module('SingleMoleculeKinetics')._parse(bad) is None

def test_kinetics_transition_and_label_symmetry():
 m=module('SingleMoleculeKinetics'); a,b,dt=.7,1.4,.2
 off=a/(a+b)*(1-np.exp(-(a+b)*dt))
 assert m.transition([a,b],dt)[0,1]==pytest.approx(off)
 assert m.transition([a,b],dt).sum(axis=1)==pytest.approx([1,1])
 o=dict(rates=[a,b],efficiencies=[.18,.78])
 assert m._mechanism(0,o)==1
 assert m._mechanism(0,dict(rates=[b,a],efficiencies=[.78,.18]))==1

def test_kinetics_alias_emissions_and_budget():
 m=module('SingleMoleculeKinetics')
 # With identical emissions every latent path has the same observation likelihood.
 for index in (1,2): assert m.SPECS[index][3:]==(.5,.5)
 lab=m._Lab(0); lab(.4,400)
 with pytest.raises(RuntimeError): lab(.1,400)
 assert lab.violated and lab.spent==1600
 def caught(p,observe):
  for _ in range(2):
   try: observe(.4,400)
   except RuntimeError: pass
  return dict(abstain=True,rates=[],efficiencies=[],confidence=.5)
 assert m.evaluate(caught)['valid']==0
 assert m.evaluate(lambda p,o:dict(abstain=True,rates=[],efficiencies=[],confidence=.5))['combined_score']==0

def test_kinetics_reference_recovers_and_refuses():
 m=module('SingleMoleculeKinetics')
 out=m.reference(m._problem(),m._Lab(0))
 assert not out['abstain'] and m._mechanism(0,out)>.65
 assert m.reference(m._problem(),m._Lab(2))['abstain']

@pytest.mark.parametrize('bad',[None,[],{}, {'abstain':True}, {'abstain':1,'fluxes':{},'confidence':.5}, {'abstain':False,'fluxes':{},'confidence':.5}, {'abstain':True,'fluxes':{},'confidence':float('inf')}, {'abstain':False,'fluxes':{'net':True,'exchange_total':1},'confidence':.5}, {'abstain':False,'fluxes':{'net':[1],'exchange_total':1},'confidence':.5}, {'abstain':False,'fluxes':{'net':2,'exchange_total':1},'confidence':.5}, {'abstain':False,'fluxes':{'net':1,'exchange_total':-1},'confidence':.5}, {'abstain':False,'fluxes':{'net':1,'exchange_total':1,'x1':.5},'confidence':.5}])
def test_isotope_bad(bad):
 assert module('IsotopeFluxIdentifiability')._parse(bad) is None

def test_isotope_reduced_mass_balance_and_conservation():
 from scipy.integrate import solve_ivp
 m=module('IsotopeFluxIdentifiability'); p=m._problem(); v,x=.35,.8
 def rhs(t,y):
  q=1-np.exp(-2*v*t)
  source=np.array([(1-q)**2,2*q*(1-q),q*q])
  return np.r_[(v*source+x*y[3:]-(v+x)*y[:3])/1.5,(v+x)*(y[:3]-y[3:])/2]
 times=p['sampling_times']; independent=solve_ivp(rhs,(0,16),[1,0,0,1,0,0],t_eval=times,rtol=1e-10,atol=1e-12).y.T.reshape(-1,2,3)
 full=m.isotopomers(p,v,x,1,times)
 assert np.all(full>=-1e-9) and np.allclose(full.sum(axis=2),1)
 assert np.allclose(m.distributions(p,v,x,1,times),independent,atol=2e-8)
 for x1 in [0,.1,.8]:
  flux=[2*v,v,v+x,x1,x-x1,v]
  assert np.allclose(np.array(p['stoichiometry'])@flux,0)
 assert np.allclose(m.distributions(p,0,0,1,times),m.distributions(p,0,2,1,times))

def test_isotope_reference_and_budget():
 m=module('IsotopeFluxIdentifiability'); out=m.reference(m._problem(),m._Lab(0))
 assert not out['abstain'] and m._mechanism(0,out)>.8
 assert m.reference(m._problem(),m._Lab(1))['abstain']
 lab=m._Lab(0); lab('full',list(range(6)))
 with pytest.raises(RuntimeError): lab('full',[0])
 assert lab.violated
 assert m.evaluate(lambda p,t:dict(abstain=True,fluxes={},confidence=.5))['combined_score']==0

@pytest.mark.parametrize('bad',[None,[],{}, {'coordinates':None}, {'coordinates':[]}, {'coordinates':[[0,0,0]]}, {'coordinates':[[0,0]]*24}, {'coordinates':[[True,0,0]]*24}, {'coordinates':[[float('nan'),0,0]]*24}, {'coordinates':[[251,0,0]]*24}, {'coordinates':[[[0],0,0]]*24}, {'coordinates':[[0,0,0]]*24,'loss':0}])
def test_geometry_bad(bad):
 m=module('ProteinDistanceGeometry'); p,_=m._world(0)
 assert m._score_output(0,p,bad)==(0.,False)

def test_geometry_witness_rigid_invariance_chirality_and_collapse():
 m=module('ProteinDistanceGeometry'); p,xyz=m._world(0)
 assert m.loss(p,xyz)<1e-15
 rng=np.random.default_rng(15); rotation=np.linalg.qr(rng.normal(size=(3,3)))[0]
 rotation[:,0]*=np.linalg.det(rotation)
 assert m.loss(p,xyz@rotation+[3,4,5])<1e-15
 mirror=xyz.copy(); mirror[:,0]*=-1
 assert m.loss(p,mirror)>.1
 assert m.loss(p,xyz*.5)>.1
 assert m.loss(p,np.zeros_like(xyz))>1
 # Independent scalar signed-volume check.
 row=p['stereocenters'][0]; a,b,c,d=xyz[row['atoms']]
 assert row['sign']*np.linalg.det(np.stack([b-a,c-a,d-a]))/3.8**3>=row['minimum_volume']

@pytest.mark.parametrize('name',['SingleMoleculeKinetics','IsotopeFluxIdentifiability'])
def test_discovery_all_claims_without_evidence_do_not_earn_refusal(name):
 m=module(name)
 if name=='SingleMoleculeKinetics':
  output=dict(abstain=False,rates=[1,1],efficiencies=[.5,.5],confidence=1.)
 else:
  output=dict(abstain=False,fluxes=dict(net=0.,exchange_total=0.),confidence=1.)
 result=m.evaluate(lambda p,lab:output)
 assert result['development_correct_refusal_rate']==0
 assert result['development_false_discovery_count']>0
 assert result['development_claim_count']>result['development_false_discovery_count']
 assert result['combined_score']==0

def test_isotope_caught_overbudget_and_unsorted_queries():
 m=module('IsotopeFluxIdentifiability')
 def caught(p,trace):
  trace('full',list(range(6)))
  try: trace('half',[0])
  except RuntimeError: pass
  return dict(abstain=True,fluxes={},confidence=.5)
 result=m.evaluate(caught)
 assert result['valid']==0 and result['combined_score']==0
 a=m._Lab(0)('full',[2,0,1]);b=m._Lab(0)('full',[0,1,2])
 assert a['counts']==[b['counts'][2],b['counts'][0],b['counts'][1]]

def test_haplotype_permutation_and_read_order():
 from copy import deepcopy
 m=module('DiploidHaplotypeAssembly');p,truth,_=m._world(0)
 rng=np.random.default_rng(9);perm=rng.permutation(len(truth));inv=np.argsort(perm)
 changed=deepcopy(p)
 for f in changed['fragments']:f['positions']=inv[f['positions']].tolist()
 changed['fragments'].reverse()
 assert m.likelihood(changed,truth[perm])==pytest.approx(m.likelihood(p,truth))

def test_reserve_independent_scalar_recurrence_and_species_ablation():
 from copy import deepcopy
 m=module('RobustReserveNetworkDesign');p=m._problem(0);selected=p['patch_ids'][:5]
 x=np.array([float(name in selected) for name in p['patch_ids']]);occupancy=np.array(p['initial_occupancy'])*x
 d=np.array(p['dispersal_matrices'])[0];e=np.array(p['extinction_rates'])[0]
 for _ in range(12):
  nxt=occupancy.copy()
  for s in range(4):
   for i in range(len(x)):
    pressure=sum(d[s,j,i]*x[j]*occupancy[s,j] for j in range(len(x)))
    nxt[s,i]=x[i]*(occupancy[s,i]*(1-e[s,i])+(1-occupancy[s,i])*(1-np.exp(-pressure)))
  occupancy=nxt
  assert np.all((occupancy>=0)&(occupancy<=1))
 expected=np.sum(occupancy*np.array(p['habitat_quality'])[0]*np.array(p['species_weights'])[:,None])
 assert m.scenario_utilities(p,selected)[0]==pytest.approx(expected)
 changed=deepcopy(p);changed['species_weights']=[1,0,0,0]
 assert m.utility(changed,selected)<m.utility(p,selected)

@pytest.mark.parametrize('name',['DiploidHaplotypeAssembly','RobustReserveNetworkDesign','SingleMoleculeKinetics','IsotopeFluxIdentifiability','ProteinDistanceGeometry'])
def test_wave2_subprocess_determinism(name):
 import os,subprocess,sys
 script='''import importlib.util,json
from pathlib import Path
name=NAME
p=Path('benchmarks/Biology')/name
def load(path):
 s=importlib.util.spec_from_file_location('loaded',path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
m=load(p/'verification/evaluator.py');b=load(p/'solution.py')
entry=(p/'frontier_eval/entrypoint.txt').read_text().strip()
print(json.dumps(m.evaluate(getattr(b,entry)),sort_keys=True,allow_nan=False))
'''.replace('NAME',repr(name))
 outputs=[subprocess.check_output([sys.executable,'-c',script],cwd=ROOT,env={**os.environ,'PYTHONHASHSEED':str(seed),'OPENBLAS_NUM_THREADS':'1'},text=True) for seed in (1,7)]
 assert outputs[0]==outputs[1]

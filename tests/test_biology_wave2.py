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
 assert not out['abstain'] and m._mechanism(0,out)>.5
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


@pytest.mark.parametrize('name',['SingleMoleculeKinetics','IsotopeFluxIdentifiability','ProteinDistanceGeometry'])
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


@pytest.mark.parametrize('name', ['SingleMoleculeKinetics', 'IsotopeFluxIdentifiability', 'ProteinDistanceGeometry'])
def test_reference_calibration_and_legal_zero_baseline(name):
    m = module(name)
    def load_file(filename):
        spec = importlib.util.spec_from_file_location('calibration_candidate', ROOT/'benchmarks/Biology'/name/filename)
        candidate = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(candidate)
        return candidate
    entry = (ROOT/'benchmarks/Biology'/name/'frontier_eval/entrypoint.txt').read_text().strip()
    baseline = m.evaluate(getattr(load_file('solution.py'), entry))
    reference = m.evaluate(getattr(load_file('references/reference.py'), entry))
    assert baseline['valid'] == reference['valid'] == 1
    assert baseline['combined_score'] == 0
    assert .5 <= reference['combined_score'] <= .8


def test_precision_endpoints_and_geometry_perfect_witness():
    kinetics = module('SingleMoleculeKinetics')
    _, a, b, e0, e1 = kinetics.SPECS[0]
    exact = dict(rates=[a,b], efficiencies=[e0,e1])
    shifted = dict(rates=[a*np.exp(.05),b*np.exp(.05)], efficiencies=[e0,e1])
    assert kinetics._mechanism(0, exact) == 1
    assert kinetics._mechanism(0, shifted) == pytest.approx(.5)
    isotope = module('IsotopeFluxIdentifiability')
    v,x = isotope.SPECS[0]
    assert isotope._mechanism(0, dict(fluxes=dict(net=v,exchange_total=x))) == 1
    assert isotope._mechanism(0, dict(fluxes=dict(net=v*1.025,exchange_total=x*1.025))) == pytest.approx(0, abs=1e-12)
    geometry = module('ProteinDistanceGeometry')
    p, xyz = geometry._world(0)
    score, valid = geometry._score_output(0, p, dict(coordinates=xyz.tolist()))
    assert valid and score == pytest.approx(1)
    assert geometry._score_output(0, p, dict(coordinates=np.zeros_like(xyz).tolist()))[0] < .01

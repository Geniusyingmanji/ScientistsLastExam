"""Scientific regressions exposed by the ten-task construction review."""


import ast


import importlib.util


from pathlib import Path


import numpy as np


import pytest


ROOT = Path(__file__).resolve().parents[1]


def load(domain, task, file="verification/evaluator.py"):
    path=ROOT/"benchmarks"/domain/task/file
    spec=importlib.util.spec_from_file_location(task+file.replace('/','_'),path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def test_groundwater_mass_conservation_and_time_refinement():
    m=load('EarthScience','GroundwaterRemediationDesign')
    p=m._public_problem(m.DEVELOPMENT_SPECS[0]);x,y=p['source_location_m']
    wells=np.array([[x+1400,y,2.13,800.]])
    coarse=m._plan_metrics(p,wells)
    fine=m._plan_metrics(dict(p,transport_step_days=15.),wells)
    assert coarse['mass_balance_error_kg']<1e-8
    assert fine['mass_balance_error_kg']<1e-8
    assert coarse['captured_mass_kg']>0
    assert abs(coarse['remaining_mass_kg']-fine['remaining_mass_kg'])<.001*p['initial_contaminant_mass_kg']
    no_pumping=m._plan_metrics(p,np.array([[x,y,0.,0.]]))
    assert no_pumping['captured_mass_kg']==0
    assert no_pumping['remaining_mass_kg']>coarse['remaining_mass_kg']


def test_source_well_shortcut_no_longer_beats_groundwater_reference():
    m=load('EarthScience','GroundwaterRemediationDesign')
    def source(p):
        x,y=p['source_location_m']
        return {'plans':[[[x,y,0.,rate]] for rate in np.linspace(80.,950.,16)]}
    result=m.evaluate(source)
    assert result['valid']==1
    assert result['combined_score']<.5
    assert result['heldout_score']<.5


def test_ice_public_selection_is_invariant_to_forecast_units():
    ref=load('EarthScience','IceObservationNetworkDesign','verification/reference_solver.py')
    m=load('EarthScience','IceObservationNetworkDesign')
    p=m._public_problem(m._world(m.DEVELOPMENT_SEEDS[0]))
    changed=dict(p,forecast_matrix=p['forecast_matrix']*np.array([.001,1.,1000.])[:,None])
    a=ref.design_ice_observation_network(p)['plans']
    b=ref.design_ice_observation_network(changed)['plans']
    assert len(a)==len(b)
    for x,y in zip(a,b):np.testing.assert_array_equal(x,y)


@pytest.mark.parametrize('domain,task', [('EarthScience', 'ActiveFullWaveformInversion'), ('EarthScience', 'ChronologyAssimilation'), ('EarthScience', 'GroundwaterRemediationDesign'), ('EarthScience', 'IceObservationNetworkDesign')])
def test_twelve_malformed_candidates_fail_closed(domain,task):
    m=load(domain,task)
    invalid=[None,{},'',True,12,float('nan'),float('inf'),[],[0],{'plans':[]},
             {'abstain':'yes'},{'confidence':float('nan')}]
    for value in invalid:
        result=m.evaluate(lambda *args,**kwargs:value)
        assert result['valid']==0,(task,value)
        assert result['combined_score']==0,(task,value)


def test_caught_malformed_instrument_call_still_invalidates_world():
    fwi=load('EarthScience','ActiveFullWaveformInversion')
    def bad_shot(*args):
        try:args[-2](3.5)
        except ValueError:pass
        return {'velocity_m_s':[],'confidence':0.,'abstain':True}
    assert fwi.evaluate(bad_shot)['valid']==0
    chronology=load('EarthScience','ChronologyAssimilation')
    def bad_date(grid,catalog,lab,budget):
        try:lab(0,['not an index'])
        except (ValueError,TypeError):pass
        return {'temperature_mean':[],'temperature_std':[],'age_offsets_years':[],'confidence':0.,'abstain':True}
    assert chronology.evaluate(bad_date)['valid']==0


def test_nonlinear_chronology_requires_curves_and_enforces_monotonicity():
    m=load('EarthScience','ChronologyAssimilation')
    ref=load('EarthScience','ChronologyAssimilation','verification/reference_solver.py')
    world=m._world(m.DEVELOPMENT_SPECS[0])
    truth=np.asarray(world['true_ages'])
    nominal=np.array([r['nominal_age_years'] for r in world['catalog']])
    # Even the best constant offset cannot explain variable accumulation.
    best_offsets=np.median(truth-nominal,axis=1)
    assert np.mean(np.abs(truth-nominal-best_offsets[:,None]))>50.
    lab=m._DatingLab(world)
    answer=ref.reconstruct_climate(m.TIME_GRID,m._public_catalog(world),lab.date_sample,m.BUDGET_UNITS)
    curves=m._validate(answer)[2]
    assert curves.shape==(8,36)
    assert np.mean(np.abs(curves-truth))<np.mean(np.abs(truth-nominal-best_offsets[:,None]))
    invalid=dict(answer,sample_ages_years=np.asarray(answer['sample_ages_years'])[:,::-1])
    with pytest.raises(ValueError,match='monotone'):
        m._validate(invalid)
    # Score covers all sample ages, not only the queried dates or a fitted mean shift.
    perfect=lambda *args:dict(temperature_mean=world['climate'],temperature_std=np.full(81,.01),
                             sample_ages_years=truth,confidence=1.,abstain=False)
    assert m._evaluate_world(perfect,m.DEVELOPMENT_SPECS[0],'development',0)['age_mae_years']==0.

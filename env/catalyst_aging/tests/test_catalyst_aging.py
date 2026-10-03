"""Independent ODE checks and explicit history-contract tests."""
import copy
import math
import numpy as np
import pytest
from scipy.integrate import solve_ivp
from env.catalyst_aging.kernel import GAS_CONSTANT, instrument, reaction_integral, reaction_step, run_history
from env.catalyst_aging.protocol import example, reaction, validate_spec
from env.catalyst_aging.world import World, baseline


def fixture():
    return {"rate_ref": .08, "activation_j_mol": 60000., "deactivation_ref": .016,
            "deactivation_activation_j_mol": 30000., "saturation": .4,
            "gain": 1.02, "offset": .012, "gain_slope": -.003,
            "offset_slope": .0008, "jump_event": 7, "gain_jump": 0., "offset_jump": 0.,
            "fractions": [1.], "decay_multipliers": [1.]}


def independent_ode(activity, temperature, concentration, duration, multiplier=1.):
    # Constants fixed in the precheck plan; does not call production helpers.
    q = .08 * math.exp(60000./8.31446261815324*(1./500.-1./temperature))*concentration/(1.+.4*concentration)
    decay = .016*concentration*math.exp(30000./8.31446261815324*(1./500.-1./temperature))*multiplier
    def rhs(time, state):
        return [-decay*state[0], q*state[0]]
    solution = solve_ivp(rhs, (0.,duration), [activity,0.], method="DOP853", rtol=1e-11, atol=1e-13)
    assert solution.success
    return float(solution.y[1,-1]), float(solution.y[0,-1]), solution.nfev


@pytest.mark.parametrize("temperature,concentration,duration", [(440.,.1,2.),(500.,.6,8.),(560.,1.2,15.)])
@pytest.mark.parametrize("multiplier", [0.,1.,4.5])
def test_independent_ode_reference(temperature, concentration, duration, multiplier):
    p = fixture();p["decay_multipliers"]=[multiplier]
    e = reaction(temperature=temperature,concentration=concentration,duration=duration)
    product, activities = reaction_step([.1],e,p)
    rp,ra,_ = independent_ode(.1,temperature,concentration,duration,multiplier)
    assert abs(product-rp)<1e-10
    assert abs(activities[0]-ra)<1e-10
    assert product>=0 and 0<=activities[0]<=.1


def test_analytic_zero_and_small_decay_limits_and_semigroup():
    assert reaction_integral(.6,.4,0.,8.) == (.6*.4*8., .6)
    value, state = reaction_integral(.6,.4,1e-30,8.)
    assert abs(value-.6*.4*8.)<1e-15
    assert state == .6
    whole, final = reaction_integral(.6,.4,.12,12.)
    first, middle = reaction_integral(.6,.4,.12,4.)
    second, later = reaction_integral(middle,.4,.12,8.)
    assert abs(first+second-whole)<1e-15
    assert abs(later-final)<1e-15


def test_coupon_history_separates_from_instrument_and_resets():
    p = fixture();p.update(gain=1.,offset=0.,gain_slope=0.,offset_slope=0.)
    spec = {"events":[reaction("A"),reaction("A"),reaction("B"),reaction("A")],"event_indices":[1,2,3,4]}
    y = run_history(validate_spec(spec),p)[:,0]
    assert y[0] > y[1] > y[3] > 0.
    assert y[0] == y[2]
    np.testing.assert_array_equal(run_history(spec,p)[:,0],y)
    # Inserting calibrations does not expose coupons, but changes instrumentclock.
    inserted = {"events":[reaction("A"),{"kind":"blank"},{"kind":"standard"},reaction("A")],"event_indices":[1,4]}
    np.testing.assert_allclose(run_history(inserted,p)[:,0],y[:2],atol=0,rtol=0)
    p["gain_slope"] = -.01
    drifted = run_history(inserted,p)[:,0]
    assert drifted[1] < y[1]


def test_step_instrument_and_two_population_superposition():
    p = fixture();p.update(gain_jump=.12,offset_jump=-.03)
    assert instrument(p,6) == (1.02-.003*5,.012+.0008*5)
    np.testing.assert_allclose(instrument(p,7),(1.02-.003*6+.12,.012+.0008*6-.03))
    p.update(fractions=[.6,.4],decay_multipliers=[.22,4.5])
    e = reaction()
    product, state = reaction_step([1.,.1],e,p)
    pieces=[]
    for a,m in zip([1.,.1],p["decay_multipliers"]):
        single=copy.deepcopy(p);single.update(fractions=[1.],decay_multipliers=[m])
        pieces.append(reaction_step([a],e,single))
    assert abs(product-(.6*pieces[0][0]+.4*pieces[1][0]))<1e-15
    np.testing.assert_allclose(state,[x[1][0] for x in pieces],atol=0,rtol=0)


def test_public_invariance_cost_noise_prefix_and_observation_subset():
    w = World(72001);spec=example()
    assert all(World(s).describe()==w.describe() for s in (72002,72003))
    all_rows = w.run(spec,noise_key="one")
    subset=copy.deepcopy(spec);subset["event_indices"]=[3,8]
    assert w.cost(spec)==w.cost(subset)==8
    assert w.run(subset,noise_key="one")["values"]==[all_rows["values"][2],all_rows["values"][7]]
    prefix={"events":spec["events"][:3],"event_indices":[3]}
    assert w.run(prefix,noise_key="one")["values"]==[all_rows["values"][2]]
    assert w.run(spec,noise_key="one")==World(72001).run(spec,noise_key="one")
    assert w.run(spec,noise_key="two")!=all_rows
    assert set(all_rows)=={"axis","channels","values"}
    assert all_rows["axis"]==list(range(1,9))
    # Even the first standard/blank are observed instrument responses, not known assignments.
    clean=w.run(spec)["values"]
    assert clean[0][0]!=0. and clean[1][0]!=1.5


@pytest.mark.parametrize("mutation", [lambda s:s.update(extra=True),lambda s:s.update(event_indices=[0]),lambda s:s.update(event_indices=[2,1]),lambda s:s.update(event_indices=[1,1]),lambda s:s["events"][2].update(temperature_k=True),lambda s:s["events"][2].update(temperature_k=561.),lambda s:s["events"][2].update(coupon_id="secret"),lambda s:s["events"][0].update(coupon_id="A"),lambda s:s.update(events=[reaction()]*7,event_indices=[1]),lambda s:s.update(events=[{"kind":"blank"}]*25,event_indices=[1])])
def test_invalid_requests_are_stateless(mutation):
    w=World(72001);spec=example();expected=w.run(spec)
    invalid=copy.deepcopy(spec);mutation(invalid)
    with pytest.raises(ValueError):w.run(invalid)
    assert w.run(spec)==expected


def test_panels_and_baseline_public_shape():
    w=World(72001);spec=example();obs=w.run(spec,noise_key="training")
    assert baseline([{"spec":spec,"observation":obs}],spec)==obs["values"]
    assert np.asarray(baseline([],spec)).shape==(8,1)
    for kind in ("development","conditions","interventions"):
        panels=w.panel(82001,kind,2)
        assert panels==World(72002).panel(82001,kind,2)
        for p in panels:assert w.validate(p)==p

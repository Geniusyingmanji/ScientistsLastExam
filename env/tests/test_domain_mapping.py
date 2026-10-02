"""Pure finite-family tests; never execute a World, network or predictor."""
from copy import deepcopy
from fractions import Fraction
from itertools import product
import pytest
from env import domain_mapping as dm
from env.analysis_api import ModelSnapshots


def proposal(points=(.5, 1.), noise=.0015):
    public = {"environment": "orbital_dynamics", "world_version": "fixture-1", "axis_field": "times",
              "channels": ["x", "y", "vx", "vy"], "scales": [2., 2., 1.5, 1.5],
              "noise_std": [noise, noise, .002, .002], "noise_mean_bias_bound": [0., 0., 0., 0.]}
    store = ModelSnapshots()
    receipt = store.save_model("fixture", "v1", {"a": 0.},
        "raise RuntimeError('candidate must never execute')\ndef predict(spec):\n    return []\n")
    snapshot = store.read_model("fixture", "v1")
    snapshot.pop("reference")
    request = {"protocol": dm.PROTOCOL, "scope": "Finite endpoint-x fixture only.",
        "model_snapshot": {k: receipt[k] for k in ("name", "version", "sha256")},
        "provenance": {"source_history_sha256": dm.digest([]), "source_cutoff_receipt": "external-fixture-cutoff",
            "source_observation_ids": [], "author_priors": "Human supplied inert fixture, no fitting.",
            "readout_nontriviality": "Dynamic endpoint, not an assigned initial state."},
        "domain": {"mode": "readout_horizon", "name": "horizon", "unit": "T", "lower": .25,
            "upper": 8., "varied_paths": ["/times/0"]},
        "points": [{"id": "p%d" % i, "u": t, "spec": {"position": [1.2, 0.], "velocity": [0., .8], "times": [t]},
            "readout": [{"row": 0, "channel": "x", "coefficient": 1.}], "replicates": 4} for i,t in enumerate(points)],
        "tolerance": .015, "tolerance_rationale": "Human engineering accuracy 0.03 L; not a mechanism criterion.",
        "family_alpha": .05}
    return request, public, snapshot, []


def canonical(spec):
    result = deepcopy(spec)
    result.setdefault("impulses", [])
    return result


def registration(noise=.0015):
    request, public, snapshot, source = proposal(noise=noise)
    plan = dm.validate_plan(request, public, canonical, source)
    values = {p["id"]: [[0.,0.,0.,0.]] for p in plan["points"]}
    return dm.seal(plan, snapshot, values, deepcopy(values), "a"*64)


def observations(reg, values=(0.,.2)):
    records=[]
    for p,value in zip(reg["plan"]["points"], values):
        for k in range(p["replicates"]):
            key="%s-%d"%(p["id"],k)
            records.append({"id":"obs-"+key,"point_id":p["id"],"replica":k,"spec_sha256":dm.digest(p["spec"]),
                "noise_key":key,"observation":{"axis":p["spec"]["times"],"channels":reg["plan"]["public"]["channels"],
                                              "values":[[value,0.,0.,0.]]}})
    return records


def replay(reg, records):
    return dm.recompute(reg,records,expected_seal=reg["seal_sha256"],expected_observations_sha256=dm.digest(records))


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def fail(*a,**k): pytest.fail("pure tests cannot use network")
    monkeypatch.setattr("socket.socket",fail)
    monkeypatch.setattr("socket.create_connection",fail)


def test_finite_scalar_classification_and_no_boundary_claim():
    reg=registration(); result=replay(reg,observations(reg))
    assert [p["classification"] for p in result["points"]]==["adequate","inadequate"]
    assert result["complete_family"]
    assert all(not result[k] for k in ("boundary_identified","continuity_certified","mechanism_identified","discovery_depth_certified"))
    assert "finite clean scalar" in result["coverage_object"]


@pytest.mark.parametrize("mean,radius,tolerance,label",[(0,1,1,"adequate"),(1,1,1,"inconclusive"),(2,1,1,"inconclusive"),
    (Fraction(201,100),1,1,"inadequate"),(-2,1,1,"inconclusive"),(-3,1,1,"inadequate"),(0,2,1,"inconclusive"),(0,0,1,"adequate")])
def test_closed_band_equality_and_strict_failure(mean,radius,tolerance,label):
    assert dm.classify(Fraction(mean),Fraction(0),Fraction(radius),Fraction(tolerance))["classification"]==label


@pytest.mark.parametrize("power",[-1200,-500,-200,-20,0,200,500,1200])
def test_square_root_certificate_extremes(power):
    q=Fraction(2)**power/3; root=dm.sqrt_upper(q)
    assert q <= root*root < q*Fraction(1000000000001,1000000000000)


def test_exact_threshold_and_outward_display():
    for exact in (Fraction(1,10),Fraction(1,10**500)):
        assert Fraction(dm.outward(exact,-1)) <= exact <= Fraction(dm.outward(exact,1))
    assert dm.classify(Fraction(1,10)+Fraction(1,10**100),Fraction(0),Fraction(0),Fraction(1,10))["classification"]=="inadequate"


def test_signed_weights_clipping_bias_and_worst_correlation():
    request,public,_,source=proposal(points=(2.,))
    public.update(environment="microecology",axis_field="times_h",channels=["A","B"],scales=[2.,4.],
                  noise_std=[.02,.04],noise_mean_bias_bound=[.02/(2*3.141592653589793)**.5,.04/(2*3.141592653589793)**.5])
    request["domain"].update(varied_paths=["/times_h/0"],lower=1.,upper=4.)
    request["points"][0].update(spec={"times_h":[2.],"events":[]},readout=[
        {"row":0,"channel":"A","coefficient":.1},{"row":0,"channel":"B","coefficient":-.9}])
    plan=dm.validate_plan(request,public,deepcopy,source); point=plan["points"][0]
    weights=[dm.unratio(t["weight"]) for t in point["readout"]]
    assert sum(map(abs,weights))==1
    sd=abs(weights[0])*Fraction(.02)/2+abs(weights[1])*Fraction(.04)/4
    d4=dm.design(plan,point,[[0.,0.]])
    assert dm.unratio(d4["variance_bound"])==sd**2
    assert dm.unratio(d4["certified_bias_bound"])==Fraction(2,5)*sd
    assert dm.unratio(d4["certified_bias_bound"])>dm.unratio(d4["raw_bias_bound"])
    point["replicates"]=16; d16=dm.design(plan,point,[[0.,0.]])
    assert d4["certified_bias_bound"]==d16["certified_bias_bound"]
    assert dm.unratio(d16["certified_bias_bound"])<dm.unratio(d16["confidence_radius"])<dm.unratio(d4["confidence_radius"])


def test_all_inconclusive_and_partial_original_family_alpha():
    reg=registration(noise=.1); records=observations(reg,(0.,0.)); full=replay(reg,records)
    assert full["complete_family"] and {p["classification"] for p in full["points"]}=={"inconclusive"}
    partial=replay(reg,records[:5])
    assert not partial["complete_family"] and partial["points"][1]["classification"]=="not_evaluated_incomplete"
    assert partial["points"][0]["design"]["alpha"]==dm.ratio(Fraction(.05)/2)


def test_exact_enumerable_noise_coverage_not_monte_carlo():
    n,alpha=4,Fraction(1,4); radius=dm.sqrt_upper(Fraction(1)/(n*alpha)); failure=false_label=Fraction(0)
    # This non-Gaussian mean-zero distribution has variance exactly one and
    # nonzero tail/misclassification mass, so the inequality is exercised.
    support=((Fraction(-2),Fraction(1,8)),(Fraction(0),Fraction(3,4)),(Fraction(2),Fraction(1,8)))
    for draws in product(support,repeat=n):
        mean=sum(x for x,p in draws)/n; probability=Fraction(1)
        for x,p in draws:probability*=p
        failure+=probability*int(abs(mean)>radius)
        false_label+=probability*int(dm.classify(mean,Fraction(2),radius,Fraction(1))["classification"]=="adequate")
    assert 0 < failure <= alpha and 0 < false_label <= alpha


@pytest.mark.parametrize("mutation",[
    lambda r:r.update(family_alpha=True),lambda r:r.update(family_alpha=.06),lambda r:r.update(tolerance=float("nan")),
    lambda r:r.update(tolerance=.3),lambda r:r.update(tolerance_rationale=""),lambda r:r.update(unknown=1),
    lambda r:r["points"][0].update(replicates=3),lambda r:r["points"][1].update(u=.5),
    lambda r:r["points"][0]["readout"].append(deepcopy(r["points"][0]["readout"][0])),
    lambda r:r["points"][0]["readout"][0].update(coefficient=0),lambda r:r["points"][1]["readout"][0].update(channel="y"),
    lambda r:r["points"][1]["spec"].update(position=[1.,0.]),lambda r:r["domain"].update(varied_paths=["/position/0"]),
    lambda r:r["provenance"].update(source_observation_ids=["missing"]),lambda r:r["model_snapshot"].update(sha256="bad")])
def test_invalid_plan_without_execution(mutation):
    request,public,_,source=proposal(); mutation(request)
    with pytest.raises(ValueError): dm.validate_plan(request,public,canonical,source)


@pytest.mark.parametrize("time",[0.,.1,.249])
def test_t0_and_pre_resolution_exclusion(time):
    request,public,_,source=proposal(points=(time,)); request["domain"]["lower"]=0.
    with pytest.raises(ValueError,match="ineligible"): dm.validate_plan(request,public,canonical,source)


def test_direct_assignment_event_clamp_and_unknown_world():
    request,public,_,source=proposal(points=(.5,)); request["points"][0]["spec"]["impulses"]=[{"time":.5,"delta_v":[.1,0.]}]
    with pytest.raises(ValueError,match="ineligible"): dm.validate_plan(request,public,canonical,source)
    public.update(environment="coupled_oscillators",channels=["x_A"],scales=[1.],noise_std=[.01],noise_mean_bias_bound=[0.])
    request["points"][0].update(spec={"times":[.5],"clamp":["A"]},readout=[{"row":0,"channel":"x_A","coefficient":1.}])
    with pytest.raises(ValueError,match="public_clamp"): dm.validate_plan(request,public,deepcopy,source)
    public["environment"]="unaudited_world"
    with pytest.raises(ValueError,match="unsupported_world"): dm.validate_plan(request,public,deepcopy,source)


@pytest.mark.parametrize("change",["snapshot","prediction","repeat","seal","record","noise_key","replica","axis"])
def test_artifact_tampering(change):
    reg=registration(); records=observations(reg); anchor=reg["seal_sha256"]; obs_anchor=dm.digest(records)
    if change=="snapshot":reg["snapshot"]["parameters"]["a"]=2
    if change=="prediction":reg["predictions"]["p0"][0][0]=1
    if change=="repeat":reg["repeat_predictions_sha256"]="b"*64
    if change=="seal":anchor="b"*64
    if change=="record":records[0]["observation"]["values"][0][0]=2
    if change=="noise_key":records[1]["noise_key"]=records[0]["noise_key"]
    if change=="replica":records[1]["replica"]=records[0]["replica"]
    if change=="axis":records[0]["observation"]["axis"]=[3.]
    if change in ("noise_key","replica","axis"):obs_anchor=dm.digest(records)
    with pytest.raises(ValueError):dm.recompute(reg,records,expected_seal=anchor,expected_observations_sha256=obs_anchor)


def test_missing_or_nondeterministic_second_pass_cannot_seal():
    request,public,snapshot,source=proposal(); plan=dm.validate_plan(request,public,canonical,source)
    first={p["id"]:[[0.,0.,0.,0.]] for p in plan["points"]}
    with pytest.raises(ValueError,match="all point"):dm.seal(plan,snapshot,first,{},"a"*64)
    second=deepcopy(first); second["p1"][0][0]=.01
    with pytest.raises(ValueError,match="nondeterministic"):dm.seal(plan,snapshot,first,second,"a"*64)


def test_mapping_ids_do_not_collide_with_source_evidence():
    request,public,_,source=proposal();source=[{"id":"obs-p0-00"}]
    request["provenance"]["source_history_sha256"]=dm.digest(source)
    with pytest.raises(ValueError,match="overlap source"):dm.validate_plan(request,public,canonical,source)

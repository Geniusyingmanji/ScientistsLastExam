"""Small bounded fixtures only; the four-seed calibration runs on the CPU host."""

import ast
from copy import deepcopy
import json
import math
from pathlib import Path

import numpy as np
import pytest
from scipy.special import ndtr

from env.microecology_causal import strong_baseline as strong
from env.microecology_causal import strong_calibration as calibration
from env.microecology_causal.protocol import CHANNELS, NOISE_STD


def model(structure="direct_toxin_detox", roles=None):
    return {"structure": structure, "peak_roles": roles or ["Z","X","Y"], "parameters": dict(strong.NOMINAL)}


def record(spec, value):
    clean = np.asarray(strong.predict(value,spec))
    sigma=np.asarray(NOISE_STD)
    z=clean/sigma
    expected=clean*ndtr(z)+sigma*np.exp(-.5*z*z)/math.sqrt(2*math.pi)
    return {"spec":spec,"observation":{"axis":spec["times_h"],"channels":list(CHANNELS),"values":expected.tolist()}}


@pytest.fixture(autouse=True)
def block_private_instance_access_and_network(monkeypatch):
    def fail(*args, **kwargs):
        pytest.fail("fitter must not use World, parameter sampling, seed RNG or network")
    monkeypatch.setattr("env.microecology_causal.world.World.__init__",fail)
    monkeypatch.setattr("env.microecology_causal.kernel.Parameters.generate",fail)
    monkeypatch.setattr("env.microecology_causal.kernel.random_generator",fail)
    monkeypatch.setattr("socket.socket",fail)


def test_explicit_parameter_predictor_matches_independent_starvation_temperature_clock():
    spec={"initial":{"A":.2,"B":.1,"C":.3,"nutrient":0}, "times_h":[0,1,2,3],
          "events":[{"time_h":1,"temperature_c":40}]}
    predicted=np.asarray(strong.predict(model(),spec))
    expected=np.exp(-strong.NOMINAL["death"]*np.array([0,1,3,5]))[:,None]*np.array([.2,.1,.3])
    assert predicted[:,:3] == pytest.approx(expected,abs=2e-10)
    assert np.max(np.abs(predicted[:,3:])) == 0


def test_explicit_peak_map_honors_public_depletion_before_measurement():
    spec=calibration.source_specs()[0]
    spec["times_h"]=[0,9,12]
    reference=np.asarray(strong.predict(model(),spec))
    spec["events"]=[{"time_h":9,"deplete":{"channel":"peak-02","fraction":.8}}]
    changed=np.asarray(strong.predict(model(),spec))
    expected=reference[1].copy()
    expected[5]*=.2
    assert changed[1] == pytest.approx(expected,abs=2e-8)
    empty={"initial":{"A":0,"B":0,"C":0,"nutrient":0},"times_h":[0,1,2],
           "events":[{"time_h":0,"feed":1},{"time_h":2,"feed":2}]}
    assert np.asarray(strong.predict(model(),empty))[:,3] == pytest.approx([1,1,3])


def test_nominal_menu_screen_recovers_peak_permutation_from_records_only():
    specs=calibration.source_specs()
    records=[record(specs[0],model()),record(specs[2],model())]
    original=deepcopy(records)
    result=strong.fit(records,limits={"residual_attempts":18,"local_fits":1})
    assert result["model"]["structure"] == "direct_toxin_detox"
    assert result["model"]["peak_roles"] == ["Z","X","Y"]
    assert result["training_noise_weighted_mse"] < 1e-12
    assert len(result["screening"]) == 18
    assert result["usage"]["residual_attempts"] == 18
    assert records == original and not result["autonomous_discovery"]
    assert not result["converged"]  # Screening alone is not optimization convergence.
    assert json.loads(json.dumps(result,allow_nan=False)) == result


def test_small_analytic_fixture_fits_death_but_does_not_identify_full_structure():
    spec={"initial":{"A":.2,"B":.1,"C":.3,"nutrient":0},"times_h":[0,4,8,16]}
    value=model("inhibitory_feedback",["X","Y","Z"])
    value["parameters"]["death"]*=1.06
    result=strong.fit([record(spec,value)],limits={"local_fits":1,"residual_attempts":90,"attempts_per_local_fit":72})
    screened=min(row["training_noise_weighted_mse"] for row in result["screening"])
    assert result["training_noise_weighted_mse"] < screened * .01
    assert result["model"]["parameters"]["death"] == pytest.approx(value["parameters"]["death"],rel=1e-3)
    # All menu structures have the same starvation limit. Fit is not a unique
    # mechanism recovery, even when the best residual is near machine precision.
    losses=[row["training_noise_weighted_mse"] for row in result["screening"]]
    assert max(losses)-min(losses) < 1e-12
    assert result["usage"]["residual_attempts"] <= 90


def test_attempt_exhaustion_preserves_best_completed_candidate_without_false_convergence():
    item=record(calibration.source_specs()[0],model())
    result=strong.fit([item],limits={"residual_attempts":1})
    assert result["stop_reason"] == "residual_attempt_limit"
    assert result["usage"]["completed_residuals"] == 1 and len(result["screening"]) == 1
    assert result["model"] is not None and not result["converged"]


def test_cpu_exhaustion_before_first_solve_is_reported_not_hidden(monkeypatch):
    item=record(calibration.source_specs()[0],model())
    clock=iter([0.,1.,1.,1.])
    monkeypatch.setattr(strong.time,"process_time",lambda:next(clock))
    monkeypatch.setattr(strong,"_simulate",lambda *a,**k:pytest.fail("solve after CPU budget"))
    result=strong.fit([item],limits={"cpu_seconds":.1})
    assert result["model"] is None and result["stop_reason"] == "cpu_limit"
    assert result["usage"]["residual_attempts"] == 0


@pytest.mark.parametrize("change",[{"cpu_seconds":61},{"wall_seconds":91},{"residual_attempts":235},{"local_fits":4},
                                    {"seed":7},{"cpu_seconds":float("nan")},{"local_fits":True},{"cpu_seconds":10**1000}])
def test_limits_only_reduce_declared_budget(change):
    with pytest.raises(ValueError): strong.fit([],limits=change)


@pytest.mark.parametrize("mutation",[
    lambda r:r.update(seed=7),lambda r:r.update(stratum="inhibitory_feedback"),
    lambda r:r["observation"].update(truth_parameters={}),
    lambda r:r["observation"]["values"][0].__setitem__(0,float("nan")),
    lambda r:r["observation"]["values"][0].__setitem__(0,True),
    lambda r:r["observation"]["values"][0].__setitem__(0,-.1),
    lambda r:r["observation"]["values"].pop(),
    lambda r:r["observation"].update(axis=[True]),
    lambda r:r["observation"]["channels"].reverse(),
])
def test_records_reject_private_payloads_nonfinite_values_and_wrong_shapes(mutation):
    item=record(calibration.source_specs()[0],model())
    mutation(item)
    with pytest.raises(ValueError): strong.fit([item])


def test_sources_are_fixed_legal_disjoint_nested_and_not_hidden_adaptive():
    first=calibration.source_specs()
    assert len(first)==16 and len({json.dumps(spec,sort_keys=True) for spec in first})==16
    first[0]["initial"]["A"]=999
    assert calibration.source_specs()[0]["initial"]["A"]==.05
    assert set(calibration.DEVELOPMENT_SEEDS)=={7,46,1439,8743}
    assert calibration.RECORD_BUDGETS==(8,16)


def test_operator_evaluation_occurs_only_after_fit_freeze(tmp_path,monkeypatch):
    folder=tmp_path/"job"
    source=calibration._source_hash()
    class FakeWorld:
        def __init__(self,seed): self.channels=CHANNELS
        def run(self,spec,noise_key=None):
            if noise_key is None: assert (folder/"fit-private.json").exists()
            return {"axis":spec["times_h"],"channels":list(CHANNELS),"values":[[0.]*7 for _ in spec["times_h"]]}
        def cost(self,spec): return 1
        def panel(self,seed,kind,count):
            assert (folder/"fit-private.json").exists()
            return [{"initial":{"A":0,"B":0,"C":0,"nutrient":0},"times_h":[0,2]}]*count
        def operator_stratum(self):
            assert (folder/"fit-private.json").exists()
            return "PRIVATE_TEST_LABEL"
    def fitted(records,limits):
        assert len(records)==8 and all(set(record)=={"id","spec","observation","cost"} for record in records)
        assert not (folder/"fit-private.json").exists()
        return {"model":model(),"converged":False,"usage":{"cpu_seconds":0.,"wall_seconds":0.}}
    monkeypatch.setattr(calibration,"World",FakeWorld)
    monkeypatch.setattr(calibration,"fit",fitted)
    result=calibration._one((7,8,dict(strong.DEFAULT_LIMITS),1,str(folder),source))
    public=calibration._public_summary([result],[{"record_budget":16}],strong.DEFAULT_LIMITS,2,1)
    assert public["job_failures"]==1 and public["unconverged_fits"]==1
    missing=[row for row in public["metrics"] if row["record_budget"]==16]
    assert all(row["planned_experiments"]==1 and row["experiments"]==0 for row in missing)
    text=json.dumps(public)
    assert "PRIVATE_TEST_LABEL" not in text and "parameters" not in text and "peak_roles" not in text and "seed" not in text


def test_operator_rejects_unplanned_seed_or_budget_before_any_output(tmp_path):
    for changes in ({"seeds":[99]},{"budgets":[4]},{"seeds":[7,7]},{"budgets":[8,16,32]},{"workers":5}):
        with pytest.raises(ValueError): calibration.calibrate(tmp_path/"unwritten",**changes)
        assert not (tmp_path/"unwritten").exists()


def test_fitter_has_no_world_seed_sampler_file_or_network_access():
    source=Path(strong.__file__).read_text()
    tree=ast.parse(source,feature_version=(3,8))
    imports=[]
    for node in ast.walk(tree):
        if isinstance(node,ast.Import): imports.extend(alias.name for alias in node.names)
        elif isinstance(node,ast.ImportFrom): imports.append(node.module)
    assert set(imports)=={"dataclasses","itertools","math","time","numpy","scipy.optimize","scipy.special","kernel","protocol"}
    calls={node.func.attr for node in ast.walk(tree) if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute)}
    assert not calls & {"generate","default_rng","read_text","read_bytes","open","request","operator_stratum"}
    assert "World" not in {node.id for node in ast.walk(tree) if isinstance(node,ast.Name)}
    assert "random_generator" not in {node.id for node in ast.walk(tree) if isinstance(node,ast.Name)}

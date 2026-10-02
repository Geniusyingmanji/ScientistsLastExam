"""Fixture transport only: no real Worlds, candidate processes or API."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import pytest
from env import domain_mapping as dm
from env import domain_mapping_runner as runner
from env import prospective_runner as legacy
from env.tests.test_domain_mapping import canonical, proposal


class FixtureWorld:
    name,version,axis_field="orbital_dynamics","fixture-1","times"
    channels,scales=("x","y","vx","vy"),(2.,2.,1.5,1.5)
    noise_std=(.0015,.0015,.002,.002)
    validate=staticmethod(canonical)
    def __init__(self):self.calls=[];self.after_return=None
    def cost(self,spec):return 1
    def run(self,spec,*,noise_key):
        self.calls.append((deepcopy(spec),noise_key))
        if self.after_return:self.after_return()
        return {"axis":spec["times"],"channels":list(self.channels),
                "values":[[0. if t==.5 else .2,0.,0.,0.] for t in spec["times"]]}


class NonexecutingProxy:
    calls=[];transform=None;fail_call=None
    def __init__(self,path,entrypoint,timeout_s,memory_mb,packages):
        assert entrypoint=="predict" and packages==()
        assert "candidate must never execute" in Path(path).read_text()
        self.closed=False
    def __call__(self,spec):
        self.calls.append(deepcopy(spec))
        if type(self).fail_call==len(self.calls):raise ValueError("fixture candidate failure")
        values=[[0.,0.,0.,0.] for _ in spec["times"]]
        return type(self).transform(values) if type(self).transform else values
    def close(self,*,kill):assert kill;self.closed=True


class FixtureClock:
    def __init__(self):self.value=0.
    def __call__(self):return self.value
    def advance(self,seconds):self.value+=seconds


@pytest.fixture
def fixture(monkeypatch):
    def forbidden(*a,**k):pytest.fail("real World/candidate/network/old prospective session forbidden")
    monkeypatch.setattr("socket.socket",forbidden);monkeypatch.setattr("socket.create_connection",forbidden)
    monkeypatch.setattr(legacy,"load_world",forbidden);monkeypatch.setattr(legacy,"ProspectiveSession",forbidden)
    monkeypatch.setattr(legacy,"CandidateProxy",NonexecutingProxy)
    monkeypatch.setattr(legacy,"call_with_deadline",lambda f,seconds:f())
    world=FixtureWorld();monkeypatch.setattr(runner,"load_world",lambda *a:(world,None))
    world.clock=FixtureClock();monkeypatch.setattr(legacy.time,"monotonic",world.clock)
    def binding(world):
        return {"fixture_only":True,"binding_schema":runner.BINDING_SCHEMA,"origin_root":"/remote/production/checkout",
                "source_files":{logical:hashlib.sha256(runner._source_path(logical).read_bytes()).hexdigest()
                                for logical in runner.REPLAY_SOURCE_IDS}}
    monkeypatch.setattr(runner,"_runtime_binding",binding)
    NonexecutingProxy.calls,NonexecutingProxy.transform,NonexecutingProxy.fail_call=[],None,None
    return world


def setup(tmp_path,limits=None):
    request,_,snapshot,source=proposal()
    task=runner.DomainMappingTask("orbital_dynamics",7,tmp_path/"domain",limits=limits)
    return task,request,snapshot,source


def entries(task):
    return [runner.read_json(p) for p in sorted((task.directory/"receipts").glob("[0-9]*.json"))]


def test_complete_family_sealed_before_any_data_and_read_only_replay(tmp_path,fixture):
    task,request,snapshot,source=setup(tmp_path);report=task.run(request,snapshot,source)
    assert report["status"]=="completed"
    assert [p["classification"] for p in report["evidence"]["points"]]==["adequate","inadequate"]
    assert report["usage"]["predictor_attempts"]==len(NonexecutingProxy.calls)==4
    assert report["usage"]["experiment_attempts"]==len(fixture.calls)==8
    log=entries(task);seal=next(e["sequence"] for e in log if e["kind"]=="domain_sealed")
    assert all(e["sequence"]<seal for e in log if e["kind"]=="domain_prediction")
    assert all(e["sequence"]>seal for e in log if e["kind"]=="observation_attempt_started")
    assert len({key for spec,key in fixture.calls})==8
    assert all(set(spec)=={"position","velocity","times","impulses"} for spec in NonexecutingProxy.calls)
    verified=runner.verify_domain_directory(task.directory,expected_head=report["receipt_head"])
    assert verified["evidence"]==report["evidence"] and verified["status"]=="completed"
    assert "private_world_seed" not in json.dumps(report) and "noise_key" not in json.dumps(report)
    assert "noise_key" not in json.dumps(task.public_records())
    with pytest.raises(RuntimeError):task.run(request,snapshot,source)


def test_count_admission_rejects_before_any_execution(tmp_path,fixture):
    task,request,snapshot,source=setup(tmp_path,{"experiments":7})
    with pytest.raises(legacy.TaskBudgetExceeded):task.run(request,snapshot,source)
    assert not NonexecutingProxy.calls and not fixture.calls
    report=task.public_report();assert report["status"]=="incomplete"
    verified=runner.verify_domain_directory(task.directory,expected_head=report["receipt_head"])
    assert verified["status"]=="incomplete" and verified["evidence"] is None


@pytest.mark.parametrize("mode",["failure","nonfinite","nondeterministic"])
def test_prediction_problem_retained_without_new_data(tmp_path,fixture,mode):
    task,request,snapshot,source=setup(tmp_path)
    if mode=="failure":NonexecutingProxy.fail_call=3
    if mode=="nonfinite":NonexecutingProxy.transform=lambda values:[[float("nan"),0.,0.,0.]]
    if mode=="nondeterministic":NonexecutingProxy.transform=lambda values:[[float(len(NonexecutingProxy.calls)),0.,0.,0.]]
    with pytest.raises((ValueError,legacy.CandidateExecutionFailed)):task.run(request,snapshot,source)
    assert not fixture.calls and task.public_report()["status"]=="failed"
    assert not any(e["kind"]=="domain_sealed" for e in entries(task))
    verified=runner.verify_domain_directory(task.directory,expected_head=task.public_report()["receipt_head"])
    assert verified["status"]=="failed" and verified["evidence"] is None


def test_returned_raw_prefix_survives_finally_budget_failure(tmp_path,fixture):
    task,request,snapshot,source=setup(tmp_path)
    def after_return():
        if len(fixture.calls)==5:fixture.clock.advance(301.)
    fixture.after_return=after_return
    with pytest.raises(legacy.TaskBudgetExceeded):task.run(request,snapshot,source)
    report=task.public_report();assert report["status"]=="incomplete" and len(fixture.calls)==5
    assert [p["classification"] for p in report["evidence"]["points"]]==["adequate","not_evaluated_incomplete"]
    assert report["evidence"]["points"][0]["design"]["alpha"]==dm.ratio(dm.fraction(.05)/2)
    log=entries(task)
    assert len([e for e in log if e["kind"]=="observation_returned"])==5
    assert len([e for e in log if e["kind"]=="domain_observation"])==4
    verified=runner.verify_domain_directory(task.directory,expected_head=report["receipt_head"])
    assert verified["raw_returned_but_unclassified"] and not verified["evidence"]["complete_family"]
    with pytest.raises(RuntimeError):task.run(request,snapshot,source)


def test_seal_persistence_failure_blocks_observation(tmp_path,fixture,monkeypatch):
    task,request,snapshot,source=setup(tmp_path);original=task._event
    def event(kind,payload):
        if kind=="domain_sealed":raise OSError("fixture disk failure")
        return original(kind,payload)
    monkeypatch.setattr(task,"_event",event)
    with pytest.raises(OSError):task.run(request,snapshot,source)
    assert not fixture.calls
    verified=runner.verify_domain_directory(task.directory,expected_head=task.public_report()["receipt_head"])
    assert verified["status"]=="failed" and verified["evidence"] is None


@pytest.mark.parametrize("target",["registration","snapshot","source","candidate","runtime","journal","head"])
def test_tampering_and_external_anchor_rejected(tmp_path,fixture,target):
    task,request,snapshot,source=setup(tmp_path);report=task.run(request,snapshot,source)
    if target=="head":
        with pytest.raises(ValueError,match="external receipt"):
            runner.verify_domain_directory(task.directory,expected_head="0"*64)
        return
    path={"registration":task.directory/"registration.json","snapshot":task.directory/"input-snapshot.json",
          "source":task.directory/"source-history.json","candidate":next((task.directory/"candidates").glob("*.py")),
          "runtime":next((task.directory/"runtime-sources").glob("*.src")),"journal":task.directory/"receipts"/"000001.json"}[target]
    path.chmod(0o600);path.write_text("[1]")
    with pytest.raises((ValueError,KeyError,TypeError,AttributeError)):
        runner.verify_domain_directory(task.directory,expected_head=report["receipt_head"])


def test_old_entrypoints_disabled_and_preseal_observation_forbidden(tmp_path,fixture):
    task,request,snapshot,source=setup(tmp_path)
    with pytest.raises(RuntimeError):task.observe_source({})
    with pytest.raises(RuntimeError):task.preregister({})
    with pytest.raises(RuntimeError):task._observe(request["points"][0]["spec"],noise_key="bad")
    with pytest.raises(ValueError):task.finish()
    assert not fixture.calls
    report=task.close()
    assert runner.verify_domain_directory(task.directory,expected_head=report["receipt_head"])["status"]=="incomplete"


def test_fixture_cli_original_bytes_and_explicit_verify_anchor(tmp_path,fixture,capsys):
    request,_,snapshot,source=proposal();paths=[]
    for name,value in (("plan",request),("snapshot",snapshot),("source",source)):
        p=tmp_path/(name+".json");p.write_text(json.dumps(value,indent=3)+"\n");paths.append(p)
    output=tmp_path/"cli"
    assert runner.main(["run","--environment","orbital_dynamics","--seed","7","--plan",str(paths[0]),
        "--snapshot",str(paths[1]),"--source-history",str(paths[2]),"--output",str(output)])==0
    report=json.loads(capsys.readouterr().out)
    assert (output/"original-plan.json").read_bytes()==paths[0].read_bytes()
    assert runner.main(["verify",str(output),"--expected-head",report["receipt_head"]])==0
    assert json.loads(capsys.readouterr().out)["status"]=="completed"


def test_bad_json_and_existing_directory_fail_closed(tmp_path,fixture):
    p=tmp_path/"bad.json";p.write_text('{"a":1,"a":2}')
    with pytest.raises(ValueError,match="duplicate"):runner.read_json(p)
    p.write_text('{"a":1e999}')
    with pytest.raises(ValueError,match="nonfinite"):runner.read_json(p)
    occupied=tmp_path/"occupied";occupied.mkdir()
    with pytest.raises(FileExistsError):runner.DomainMappingTask("orbital_dynamics",7,occupied)
    assert not fixture.calls


def _rewrite_chain(task, log):
    previous=None
    for index,entry in enumerate(log,1):
        entry.update(sequence=index,previous_sha256=previous)
        entry.pop("sha256",None);entry["sha256"]=dm.digest(entry);previous=entry["sha256"]
        (task.directory/"receipts"/("%06d.json"%index)).write_text(json.dumps(entry))
    (task.directory/"receipts"/"head.json").write_text(json.dumps({"sequence":len(log),"sha256":previous}))
    report=runner.read_json(task.directory/"report.json");report["receipt_head"]=previous
    (task.directory/"report.json").write_text(json.dumps(report))
    return previous


@pytest.mark.parametrize("mutation,message",[("order","before complete seal"),("replica","acquisition order"),
                                             ("report","public report"),("finish","execution continued")])
def test_consistent_hash_chain_does_not_replace_event_grammar(tmp_path,fixture,mutation,message):
    task,request,snapshot,source=setup(tmp_path);report=task.run(request,snapshot,source);log=entries(task)
    if mutation=="order":
        item=next(e for e in log if e["kind"]=="domain_observation_planned");log.remove(item)
        log.insert(next(i for i,e in enumerate(log) if e["kind"]=="domain_sealed"),item)
    elif mutation=="replica":
        next(e for e in log if e["kind"]=="domain_observation_planned")["payload"]["replica"]=1
    elif mutation=="finish":
        next(e for e in log if e["kind"]=="observation_attempt_finished")["payload"]["ok"]=False
    head=_rewrite_chain(task,log)
    if mutation=="report":
        changed=runner.read_json(task.directory/"report.json");changed["evidence"]["points"][0]["classification"]="inadequate"
        (task.directory/"report.json").write_text(json.dumps(changed))
    with pytest.raises(ValueError,match=message):runner.verify_domain_directory(task.directory,expected_head=head)


def test_caller_mutation_cannot_replace_sealed_model_or_family(tmp_path,fixture):
    task,request,snapshot,source=setup(tmp_path)
    def change_originals():
        request["tolerance"]=.2;request["points"][0]["replicates"]=16
        snapshot["parameters"]["a"]=999
    fixture.after_return=change_originals
    report=task.run(request,snapshot,source)
    assert report["status"]=="completed" and len(fixture.calls)==8
    assert report["public_plan"]["tolerance"]==.015
    assert report["public_plan"]["points"][0]["replicates"]==4
    assert "source_cutoff_receipt" not in report["public_plan"]["provenance"]
    assert runner.verify_domain_directory(task.directory,expected_head=report["receipt_head"])["status"]=="completed"


def test_complete_data_without_terminal_receipt_remains_interrupted(tmp_path,fixture):
    task,request,snapshot,source=setup(tmp_path);task.run(request,snapshot,source);log=entries(task)
    last=log.pop();assert last["kind"]=="domain_terminal"
    (task.directory/"receipts"/("%06d.json"%last["sequence"])).unlink()
    head=_rewrite_chain(task,log)
    verified=runner.verify_domain_directory(task.directory,expected_head=head)
    assert verified["status"]=="interrupted_prefix" and verified["evidence"]["complete_family"]


def _replace_metadata(task,log,report,metadata):
    (task.directory/"operator-private.json").write_text(json.dumps(metadata))
    log[0]["payload"]["operator_metadata_sha256"]=dm.digest(metadata)
    report["limits"]=deepcopy(metadata["limits"])
    (task.directory/"report.json").write_text(json.dumps(report))


@pytest.mark.parametrize("mutation",["small_counts","extra_limit","missing_limit","raised_limit","tiny_bytes",
    "terminal_huge","negative_prediction","negative_observation","sum_mismatch","false_boolean","boolean_attempt",
    "bad_reservation","bad_remaining","over_wall","nonmonotone_wall","missing_audit","stale_admission_elapsed"])
def test_independent_review_resource_mutations_rejected(tmp_path,fixture,mutation):
    task,request,snapshot,source=setup(tmp_path);report=task.run(request,snapshot,source);log=entries(task)
    meta=runner.read_json(task.directory/"operator-private.json")
    if mutation=="small_counts":meta["limits"].update(experiments=1,predictor_calls=1,experiment_units=1)
    if mutation=="extra_limit":meta["limits"]["unapproved"]=1
    if mutation=="missing_limit":meta["limits"].pop("wall_seconds")
    if mutation=="raised_limit":meta["limits"]["wall_seconds"]=1000
    if mutation=="tiny_bytes":meta["limits"]["artifact_bytes"]=1
    if mutation=="terminal_huge":
        log[-1]["payload"]["usage"].update(predictor_seconds_actual=1e300,simulation_seconds_actual=1e300)
        report["usage"]=deepcopy(log[-1]["payload"]["usage"])
    if mutation in ("negative_prediction","negative_observation","sum_mismatch","false_boolean"):
        name="observation_attempt_finished" if mutation=="negative_observation" else "prediction_attempt_finished"
        payload=next(e["payload"] for e in log if e["kind"]==name)
        if mutation=="false_boolean":payload["ok"]=1
        else:payload["elapsed_seconds"]=.01 if mutation=="sum_mismatch" else -10
    if mutation=="boolean_attempt":next(e for e in log if e["kind"]=="prediction_attempt_started")["payload"]["attempt"]=True
    if mutation=="bad_reservation":next(e for e in log if e["kind"]=="domain_admitted")["payload"]["prediction_seconds_reserved"]=1
    if mutation=="bad_remaining":next(e for e in log if e["kind"]=="domain_admitted")["payload"]["wall_seconds_remaining_at_admission"]=1e300
    if mutation=="over_wall":log[-1]["payload"]["_domain_audit"]["wall_elapsed_seconds"]=901
    if mutation=="nonmonotone_wall":log[1]["payload"]["_domain_audit"]["wall_elapsed_seconds"]=1
    if mutation=="missing_audit":log[1]["payload"].pop("_domain_audit")
    if mutation=="stale_admission_elapsed":
        meta["limits"]["wall_seconds"]=75.
        seen_input=False
        for entry in log:
            if entry["kind"]=="domain_input":seen_input=True
            if seen_input:entry["payload"]["_domain_audit"]["wall_elapsed_seconds"]+=10.
            if entry["kind"]=="domain_admitted":
                entry["payload"]["wall_elapsed_at_admission"]=0.
                entry["payload"]["wall_seconds_remaining_at_admission"]=75.
    _replace_metadata(task,log,report,meta);head=_rewrite_chain(task,log)
    with pytest.raises(ValueError):runner.verify_domain_directory(task.directory,expected_head=head)


@pytest.mark.parametrize("mutation",["axis","channels","values","extra","boolean_axis"])
def test_raw_finally_failure_schema_is_checked_even_without_promotion(tmp_path,fixture,mutation):
    task,request,snapshot,source=setup(tmp_path)
    def overrun():
        if len(fixture.calls)==5:fixture.clock.advance(301.)
    fixture.after_return=overrun
    with pytest.raises(legacy.TaskBudgetExceeded):task.run(request,snapshot,source)
    report=task.public_report()
    assert runner.verify_domain_directory(task.directory,expected_head=report["receipt_head"])["raw_returned_but_unclassified"]
    log=entries(task);raw=[e["payload"]["observation"] for e in log if e["kind"]=="observation_returned"][-1]
    if mutation=="axis":raw["axis"]=["WRONG"]
    if mutation=="channels":raw["channels"]=["WRONG"]
    if mutation=="values":raw["values"]=[["nonnumeric"]]
    if mutation=="extra":raw["extra"]=1
    if mutation=="boolean_axis":raw["axis"]=[True]
    head=_rewrite_chain(task,log)
    with pytest.raises(ValueError):runner.verify_domain_directory(task.directory,expected_head=head)


@pytest.mark.parametrize("mutation",["valid_other_root","missing_identity","ambiguous_identity","changed_helper","legacy_binding"])
def test_repository_relative_runtime_binding_is_portable_and_strict(tmp_path,fixture,mutation):
    task,request,snapshot,source=setup(tmp_path);report=task.run(request,snapshot,source)
    meta=runner.read_json(task.directory/"operator-private.json")
    assert meta["runtime_binding"]["origin_root"]!="" and meta["runtime_binding"]["origin_root"]!=str(runner._repo_root())
    assert all(not key.startswith("/") for key in meta["runtime_binding"]["source_files"])
    if mutation=="valid_other_root":
        assert runner.verify_domain_directory(task.directory,expected_head=report["receipt_head"])["status"]=="completed"
        return
    log=entries(task);binding=meta["runtime_binding"]
    if mutation=="missing_identity":binding["source_files"].pop("env/analysis_api.py")
    if mutation=="ambiguous_identity":binding["source_files"]["env/./analysis_api.py"]=binding["source_files"]["env/analysis_api.py"]
    if mutation=="changed_helper":
        altered=b"# a changed helper\n";digest=hashlib.sha256(altered).hexdigest()
        (task.directory/"runtime-sources"/(digest+".src")).write_bytes(altered)
        binding["source_files"]["env/analysis_api.py"]=digest
    if mutation=="legacy_binding":binding.pop("binding_schema")
    meta["runtime_id"]=dm.digest(binding)
    _replace_metadata(task,log,report,meta);head=_rewrite_chain(task,log)
    with pytest.raises(ValueError):runner.verify_domain_directory(task.directory,expected_head=head)


def test_real_receipted_per_call_overrun_is_incomplete_not_lost_or_retried(tmp_path,fixture):
    task,request,snapshot,source=setup(tmp_path)
    def overrun():
        if len(fixture.calls)==1:fixture.clock.advance(3.25)
    fixture.after_return=overrun
    with pytest.raises(legacy.TaskBudgetExceeded):task.run(request,snapshot,source)
    report=task.public_report();verified=runner.verify_domain_directory(task.directory,expected_head=report["receipt_head"])
    assert verified["status"]=="incomplete" and verified["raw_returned_but_unclassified"]
    assert report["usage"]["simulation_seconds_actual"]==3.25 and len(fixture.calls)==1
    assert verified["evidence"]["points"][0]["classification"]=="not_evaluated_incomplete"


def test_nonzero_elapsed_sums_replay_and_elapsed_tampering_is_rejected(tmp_path,fixture):
    task,request,snapshot,source=setup(tmp_path)
    fixture.after_return=lambda:fixture.clock.advance(.125)
    def prediction(values):
        fixture.clock.advance(.25)
        return values
    NonexecutingProxy.transform=prediction
    report=task.run(request,snapshot,source)
    assert report["usage"]["predictor_seconds_actual"]==1.
    assert report["usage"]["simulation_seconds_actual"]==1.
    assert runner.verify_domain_directory(task.directory,expected_head=report["receipt_head"])["status"]=="completed"
    log=entries(task)
    # The replacement still fits both per-call and wall limits. Only summation
    # against actual terminal usage reveals this inconsistent resource record.
    event=next(e for e in log if e["kind"]=="prediction_attempt_finished")
    event["payload"]["elapsed_seconds"] = .125
    head=_rewrite_chain(task,log)
    with pytest.raises(ValueError,match="attempt accounting"):
        runner.verify_domain_directory(task.directory,expected_head=head)

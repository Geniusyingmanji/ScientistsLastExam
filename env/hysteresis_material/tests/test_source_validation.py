"""Array/JSON/fake-boundary fixtures only: no real World or candidate execution."""
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from scipy.stats import ncx2

from env.hysteresis_material import source_validation as validation


@pytest.mark.parametrize("nc", [0., 5., 128., 1280., 5120.])
def test_parameter_interval_inverts_cdf_and_contains_median_nc(nc):
    q = float(ncx2.ppf(.5, validation.CELLS, nc))
    answer = validation.noncentrality_interval(q)
    assert answer["lower"] <= nc <= answer["upper"]
    if not answer["lower_boundary_clamped"]:
        assert abs(ncx2.cdf(q, 80, answer["lower"]) - (1-validation.MODEL_ALPHA/2)) < 1e-9
    if not answer["upper_boundary_clamped"]:
        assert abs(ncx2.cdf(q, 80, answer["upper"]) - validation.MODEL_ALPHA/2) < 1e-9


@pytest.mark.parametrize("q", [0., float(ncx2.ppf(.001, 80, 0))])
def test_small_q_boundary_is_closed_nonnegative_interval(q):
    answer = validation.noncentrality_interval(q)
    assert answer["lower"] == answer["upper"] == 0.
    assert answer["lower_boundary_clamped"] and answer["upper_boundary_clamped"]


@pytest.mark.parametrize("q", [float("nan"), float("inf"), -1., True])
def test_invalid_statistic_fails_closed(q):
    with pytest.raises(ValueError):
        validation.noncentrality_interval(q)


def test_nonfinite_cdf_and_hard_bracket_limit_fail_closed(monkeypatch):
    with pytest.raises(validation.NumericalFailure, match="bracket"):
        validation.noncentrality_interval(1e12)
    monkeypatch.setattr(validation.ncx2, "cdf", lambda *args: float("nan"))
    with pytest.raises(validation.NumericalFailure, match="cdf"):
        validation.noncentrality_interval(80.)


def test_nonmonotone_cdf_fails_closed(monkeypatch):
    monkeypatch.setattr(validation.ncx2, "cdf", lambda q, df, nc: .9 if nc == 0 else .99)
    with pytest.raises(validation.NumericalFailure, match="monotonicity"):
        validation.noncentrality_interval(80.)


def test_statistic_excludes_time_zero_and_has_no_fit_df_subtraction():
    p = np.full((8, 11, 1), validation.SIGMA)
    y = np.zeros((8, 16, 11, 1))
    p[:, 0, :] = 1e4
    y[:, :, 0, :] = -1e4
    result = validation.bias_diagnostic(p, y)
    assert result["Q"] == 16 * 80
    assert result["degrees_of_freedom"] == 80
    assert result["normalized_true_bias_rms_interval"][0] < 1 < result["normalized_true_bias_rms_interval"][1]
    assert result["classification"] == "inconclusive"
    assert result["per_model_alpha"] * 8 == validation.FAMILY_ALPHA


def test_shape_nonfinite_and_tolerance_boundaries():
    with pytest.raises(ValueError):
        validation.bias_diagnostic(np.zeros((8, 10, 1)), np.zeros((8, 16, 11, 1)))
    y = np.zeros((8, 16, 11, 1))
    y[0, 0, 1, 0] = float("nan")
    with pytest.raises(ValueError):
        validation.bias_diagnostic(np.zeros((8, 11, 1)), y)
    assert validation.classify_bias(.5, 1.) == "compatible_at_declared_tolerance"
    assert validation.classify_bias(1., 1.2) == "inconclusive"
    assert validation.classify_bias(1.001, 1.2) == "incompatible_at_declared_tolerance"
    with pytest.raises(validation.NumericalFailure):
        validation.classify_bias(float("nan"), 1.)


def synthetic_d1(tmp_path):
    """Create hashes/snapshots as inert text, never execute even fixture code."""
    root = tmp_path / "synthetic-d1"
    root.mkdir()
    paths = []

    def put(relative, value):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(validation._encoded(value))
        paths.append(path)
        return path

    reference = root / "reference-source.py"
    reference.write_text("# inert synthetic fixture reference, never executed\n")
    paths.append(reference)
    manifests = []
    for index, seed in enumerate(validation.SEEDS, 1):
        stem = "instance-%02d/" % index
        manifest = {"private_world_seed": seed, "reference": {"source_sha256": validation._sha(reference.read_bytes())}}
        manifests.append(manifest)
        put(stem + "manifest-private.json", manifest)
        models = {}
        for name in validation.MODELS:
            diagnostic = {"evidence_ids": ["source-%d" % j for j in range(8)], "source_rmse": .006}
            snapshot = {"protocol": "sle-analysis-snapshots-0.1", "name": name, "version": "v1",
                        "parameters": {"kind": name, "fixture_index": index, "diagnostics": diagnostic},
                        "predictor_code": "def predict(spec):\n    return [[0.] for _ in spec['times']]\n"}
            sha = validation._digest(snapshot)
            put(stem + "models/" + sha + ".json", snapshot)
            models[name] = dict(diagnostic, model_snapshot={"name": name, "version": "v1", "sha256": sha})
        put(stem + "driver-receipts/000009.json", {"payload": {"analysis": {"ok": True, "result": {"failures": {}, "models": models}}}})
        for j, spec in enumerate(validation.source_specs()):
            put(stem + "science/receipts/%06d.json" % (6+5*j), {"kind": "source_evidence", "payload": {"spec": spec}})
    put("plan-private.json", {"manifests": manifests})
    plan = {"input_relative_sha256": {str(p.relative_to(root)): validation._sha(p.read_bytes()) for p in paths}}
    plan_path = tmp_path / "fixture-plan.json"
    plan_path.write_bytes(validation._encoded(plan))
    return root, plan_path, plan


def test_exact_snapshot_restore_and_source_tamper_rejected(tmp_path):
    root, _, plan = synthetic_d1(tmp_path)
    cases, before = validation._load_inputs(root, plan)
    assert len(cases) == 4 and len(before) == 50
    assert all(len(case["snapshots"]) == 2 for case in cases)
    for case in cases:
        for snapshot in case["snapshots"].values():
            assert snapshot["code"].startswith("import json as _sle_model_json\nMODEL = ")
            assert validation._sha(snapshot["code"].encode()) == snapshot["bound_source_sha256"]
    (root / "reference-source.py").write_text("changed")
    with pytest.raises(ValueError, match="hash mismatch"):
        validation._load_inputs(root, plan)


def fake_boundaries(monkeypatch, output, fail_prediction=False):
    counters = {"prediction": 0, "observation": 0, "world": 0}
    keys = set()

    def predict(path, spec, seconds):
        assert Path(path).is_file() and 0 < seconds <= 15
        counters["prediction"] += 1
        assert counters["observation"] == counters["world"] == 0
        if fail_prediction:
            raise RuntimeError("private diagnostic must not appear in public output")
        return [[0.] for _ in spec["times"]]

    def new_world(seed):
        assert counters["prediction"] == 128
        seal = validation._read_json(output / "private/predictions-sealed.json")
        assert seal["sha256"] == validation._digest({k: v for k, v in seal.items() if k != "sha256"})
        assert seal["new_observation_calls"] == 0
        counters["world"] += 1
        return SimpleNamespace(noise_std=(.006,), channels=("response",))

    def observe(world, spec, key, seconds):
        assert counters["prediction"] == 128 and key not in keys
        keys.add(key)
        counters["observation"] += 1
        return {"axis": spec["times"], "channels": ["response"], "values": [[0.] for _ in spec["times"]]}

    monkeypatch.setattr(validation, "_predict_isolated", predict)
    monkeypatch.setattr(validation, "_new_world", new_world)
    monkeypatch.setattr(validation, "_observe", observe)
    return counters


def test_fixed_fake_run_seals_every_prediction_before_any_observation(tmp_path, monkeypatch):
    root, plan_path, _ = synthetic_d1(tmp_path)
    monkeypatch.setattr(validation, "EXPECTED_PLAN_SHA256", validation._sha(plan_path.read_bytes()))
    output = tmp_path / "new-run"
    counters = fake_boundaries(monkeypatch, output)
    report = validation.run(root, output, plan_path)
    assert counters == {"prediction": 128, "observation": 512, "world": 4}
    assert report["status"] == "completed" and report["conclusions_valid"]
    assert report["inputs_unchanged"] and report["completed_instances"] == 4
    assert all(r["prediction_calls"] == 32 and r["observation_calls"] == 128 for r in report["rows"])
    assert all(m["classification"] == "compatible_at_declared_tolerance" for r in report["rows"] for m in r["models"])
    assert report["model_api_calls"] == report["refits"] == 0
    with pytest.raises(FileExistsError):
        validation.run(root, output, plan_path)


def test_prediction_failure_has_zero_world_calls_and_retains_all_cases(tmp_path, monkeypatch):
    root, plan_path, _ = synthetic_d1(tmp_path)
    monkeypatch.setattr(validation, "EXPECTED_PLAN_SHA256", validation._sha(plan_path.read_bytes()))
    output = tmp_path / "failed-run"
    counters = fake_boundaries(monkeypatch, output, fail_prediction=True)
    report = validation.run(root, output, plan_path)
    assert counters == {"prediction": 1, "observation": 0, "world": 0}
    assert report["status"] == "failed" and not report["conclusions_valid"]
    assert len(report["rows"]) == 4 and report["rows"][0]["status"] == "failed"
    assert all(r["status"] == "not_attempted_after_failure" for r in report["rows"][1:])
    assert "private diagnostic" not in json.dumps(report)
    assert not (output / "private/predictions-sealed.json").exists()


def test_plan_mismatch_fails_without_executors_or_world(tmp_path, monkeypatch):
    root, plan_path, _ = synthetic_d1(tmp_path)
    output = tmp_path / "wrong-plan"
    counters = fake_boundaries(monkeypatch, output)
    report = validation.run(root, output, plan_path)
    assert report["status"] == "failed" and not report["conclusions_valid"]
    assert counters == {"prediction": 0, "observation": 0, "world": 0}


def test_nondeterminism_stops_before_seal_and_world(tmp_path, monkeypatch):
    root, plan_path, _ = synthetic_d1(tmp_path)
    monkeypatch.setattr(validation, "EXPECTED_PLAN_SHA256", validation._sha(plan_path.read_bytes()))
    output = tmp_path / "nondeterministic-run"
    counters = fake_boundaries(monkeypatch, output)
    original = validation._predict_isolated

    def changed_prediction(*args):
        values = original(*args)
        values[1][0] = float(counters["prediction"])
        return values

    monkeypatch.setattr(validation, "_predict_isolated", changed_prediction)
    report = validation.run(root, output, plan_path)
    assert report["status"] == "failed"
    assert counters == {"prediction": 2, "observation": 0, "world": 0}
    assert not (output / "private/predictions-sealed.json").exists()


def test_observation_failure_stops_without_retry_and_keeps_seal(tmp_path, monkeypatch):
    root, plan_path, _ = synthetic_d1(tmp_path)
    monkeypatch.setattr(validation, "EXPECTED_PLAN_SHA256", validation._sha(plan_path.read_bytes()))
    output = tmp_path / "observation-failure"
    counters = fake_boundaries(monkeypatch, output)
    original = validation._observe

    def failed_observation(*args):
        value = original(*args)
        if counters["observation"] == 2:
            raise RuntimeError("fixture observation failure")
        return value

    monkeypatch.setattr(validation, "_observe", failed_observation)
    report = validation.run(root, output, plan_path)
    assert report["status"] == "failed" and not report["conclusions_valid"]
    assert counters == {"prediction": 128, "observation": 2, "world": 1}
    assert report["prediction_seal_sha256"] is not None
    assert len(report["rows"]) == 4
    assert report["rows"][0]["status"] == "failed"


def test_failed_postcheck_invalidates_all_public_classifications(tmp_path, monkeypatch):
    root, plan_path, _ = synthetic_d1(tmp_path)
    monkeypatch.setattr(validation, "EXPECTED_PLAN_SHA256", validation._sha(plan_path.read_bytes()))
    output = tmp_path / "postcheck-failure"
    counters = fake_boundaries(monkeypatch, output)
    original = validation._observe

    def change_input_at_end(*args):
        value = original(*args)
        if counters["observation"] == 512:
            (root / "reference-source.py").write_text("changed source fixture")
        return value

    monkeypatch.setattr(validation, "_observe", change_input_at_end)
    report = validation.run(root, output, plan_path)
    assert report["status"] == "failed" and not report["inputs_unchanged"]
    assert not report["conclusions_valid"]
    assert all(m["classification"] is None and not m["conclusion_valid"] for r in report["rows"] for m in r["models"])
    assert (output / "private/computed-rows.json").is_file()


def test_numerical_failure_does_not_publish_partial_affirmative_label(tmp_path, monkeypatch):
    root, plan_path, _ = synthetic_d1(tmp_path)
    monkeypatch.setattr(validation, "EXPECTED_PLAN_SHA256", validation._sha(plan_path.read_bytes()))
    output = tmp_path / "numerical-failure"
    counters = fake_boundaries(monkeypatch, output)
    original = validation.bias_diagnostic
    calls = [0]

    def fail_second_statistic(*args):
        calls[0] += 1
        if calls[0] == 2:
            raise validation.NumericalFailure("fixture failure")
        return original(*args)

    monkeypatch.setattr(validation, "bias_diagnostic", fail_second_statistic)
    report = validation.run(root, output, plan_path)
    assert report["status"] == "failed" and not report["conclusions_valid"]
    assert counters == {"prediction": 128, "observation": 128, "world": 1}
    assert report["rows"][0]["models"][0]["classification"] is None


def test_exhausted_work_budget_has_no_executor_or_world_calls(tmp_path, monkeypatch):
    root, plan_path, _ = synthetic_d1(tmp_path)
    monkeypatch.setattr(validation, "EXPECTED_PLAN_SHA256", validation._sha(plan_path.read_bytes()))
    monkeypatch.setattr(validation, "WORK_SECONDS", 0.)
    output = tmp_path / "exhausted-run"
    counters = fake_boundaries(monkeypatch, output)
    report = validation.run(root, output, plan_path)
    assert report["status"] == "failed" and not report["conclusions_valid"]
    assert counters == {"prediction": 0, "observation": 0, "world": 0}


@pytest.mark.parametrize("boundary", ["prediction", "observation"])
def test_returned_data_survives_work_deadline_without_starting_next_call(tmp_path, monkeypatch, boundary):
    root, plan_path, _ = synthetic_d1(tmp_path)
    monkeypatch.setattr(validation, "EXPECTED_PLAN_SHA256", validation._sha(plan_path.read_bytes()))
    output = tmp_path / (boundary + "-deadline")
    counters = fake_boundaries(monkeypatch, output)
    now = [0.]
    monkeypatch.setattr(validation.time, "monotonic", lambda: now[0])
    name = "_predict_isolated" if boundary == "prediction" else "_observe"
    original = getattr(validation, name)

    def crosses_work_deadline(*args):
        value = original(*args)
        now[0] = validation.WORK_SECONDS + .001
        return value

    monkeypatch.setattr(validation, name, crosses_work_deadline)
    report = validation.run(root, output, plan_path)
    entries = [json.loads(p.read_text()) for p in sorted((output / "private/receipts").glob("[0-9]*.json"))]
    returned = [e for e in entries if e["kind"] == boundary + "_returned"]
    assert len(returned) == 1
    payload = returned[0]["payload"]
    assert (payload["values"] if boundary == "prediction" else payload["observation"]["values"]) == [[0.]] * 11
    expected = {"prediction": 1, "observation": 0, "world": 0} if boundary == "prediction" else {"prediction": 128, "observation": 1, "world": 1}
    assert counters == expected
    assert report["status"] == "failed" and not report["conclusions_valid"]
    assert report["failure"]["exception_type"] == "TimeoutError"
    assert (output / "private/failure.json").is_file()

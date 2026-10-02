"""Prospective evidence tests use synthetic numeric callbacks, never model APIs."""

import copy
import json
import math
import subprocess
import sys

import numpy as np
import pytest

from env.prospective import (ProspectiveSession, digest, recompute_result,
                             replay_predictors)


def code(coefficient):
    return ('def predict(spec):\n'
            '    return [[%s * spec["drive"] * t] for t in spec["times"]]\n' % coefficient)


CODES = {code(value): value for value in (0, 1, 2, 3, 1.005)}


def spec(drive=1, times=None):
    return {"drive": drive, "times": [0, 1, 2] if times is None else times}


def public():
    return {"environment": "numeric_fixture", "world_version": "fixture-1", "axis_field": "times",
            "channels": ["response"], "scales": [1.0], "noise_std": [0.001],
            "noise_mean_bias_bound": [0.0]}


def prior():
    return [{"id": "obs-0001", "spec": spec(0),
             "observation": {"axis": [0, 1, 2], "channels": ["response"], "values": [[0], [0], [0]]}}]


def request(*, coefficients=(1, 2), tolerance=0.03, profile="mechanism_discrimination", drive=1):
    return {"profile": profile, "scope": "Only the selected one-hour response under the stated drive.",
            "rivals": [{"id": "model-%d" % i, "predictor_code": code(value),
                        "rationale": "A distinct response coefficient consistent with the zero-drive source.",
                        "evidence_ids": ["obs-0001"], "tolerance": tolerance}
                       for i, value in enumerate(coefficients)],
            "experiments": [{"id": "target", "role": "target", "spec": spec(drive)}],
            "readout": [{"experiment_id": "target", "row": 1, "channel": "response", "weight": 1.0}],
            "replicates": 8, "revision_of": None, "change_note": ""}


class Fixture:
    def __init__(self, truth=1.0, contract=None, predictor=None, max_tests=3):
        self.events, self.observed, self.predicted = [], [], []
        self.truth = truth
        self.public = contract or public()
        self.session = ProspectiveSession(self.public, validate_spec=self.validate,
                                          predict=predictor or self.predict, observe=self.observe,
                                          persist=self.persist, runtime_id="deterministic-test-callback-v1",
                                          max_tests=max_tests)

    @staticmethod
    def validate(s):
        if set(s) != {"drive", "times"} or not -3 <= s["drive"] <= 3:
            raise ValueError("invalid fixture spec")
        if not isinstance(s["times"], list) or not 1 <= len(s["times"]) <= 256:
            raise ValueError("invalid fixture axis")
        return copy.deepcopy(s)

    def predict(self, source, s):
        self.predicted.append((source, copy.deepcopy(s)))
        return [[CODES[source] * s["drive"] * time] for time in s["times"]]

    def observe(self, s, *, noise_key):
        assert any(e["kind"] == "registered" for e in self.events)
        assert any(e["kind"] == "collection_started" for e in self.events)
        self.observed.append((copy.deepcopy(s), noise_key))
        return {"axis": s["times"], "channels": ["response"],
                "values": [[self.truth * s["drive"] * time] for time in s["times"]]}

    def persist(self, event):
        self.events.append(copy.deepcopy(event))
        return "fixture-receipt-%d" % len(self.events)


def completed(fixture, proposal=None):
    registration = fixture.session.register(proposal or request(), records=prior())
    result = fixture.session.collect(registration["test_id"])
    return registration, result, fixture.session.snapshot()["tests"][-1]


def test_prospective_seals_code_and_full_outputs_before_observation_and_replays():
    fixture = Fixture()
    registration = fixture.session.register(request(), records=prior())
    assert fixture.observed == []
    assert len(fixture.predicted) == 4  # Each frozen candidate replayed twice.
    assert fixture.events[-1]["kind"] == "registered"
    assert registration["rivals"][0]["predictions"]["target"] == [[0.0], [1.0], [2.0]]
    assert len(registration["rivals"][0]["code_sha256"]) == 64
    assert registration["design"]["planned_separation"]
    result = fixture.session.collect(registration["test_id"])
    assert result["outcome"] == "scoped_predictive_discrimination"
    assert result["predictive_discrimination_supported"]
    assert result["supported_candidate"] == "model-0"
    assert result["counterexample_candidate_ids"] == ["model-1"]
    assert not result["mechanism_identified"] and not result["discovery_depth_certified"]
    assert len(set(key for _, key in fixture.observed)) == 8
    record = fixture.session.snapshot()["tests"][0]
    replay = recompute_result(registration, record["observations"], expected_seal=registration["seal_sha256"],
                              expected_observations_sha256=record["observations_sha256"])
    assert replay == result
    assert all(item["matches_frozen_outputs"] for item in replay_predictors(registration, fixture.predict,
                                                                           expected_seal=registration["seal_sha256"]))
    json.dumps(fixture.session.snapshot(), allow_nan=False)


def test_prospective_actual_fixture_codes_run_in_fresh_python_processes():
    # The wrapper only exercises fixed test-fixture programs. It is deliberately
    # not exported as an executor or claimed to be a production security sandbox.
    wrapper = ('import json, sys\n'
               'payload = json.load(sys.stdin)\n'
               'namespace = {}\n'
               'exec(payload["code"], namespace)\n'
               'print(json.dumps(namespace["predict"](payload["spec"])))\n')

    def isolated_fixture(source, s):
        assert source in CODES
        output = subprocess.run([sys.executable, "-I", "-c", wrapper],
                                input=json.dumps({"code": source, "spec": s}), text=True,
                                capture_output=True, check=True, timeout=5)
        return json.loads(output.stdout)

    fixture = Fixture(predictor=isolated_fixture)
    _, result, _ = completed(fixture)
    assert result["predictive_discrimination_supported"]


def test_prospective_not_refuted_is_not_equivalence_and_both_can_fail():
    _, marginal, _ = completed(Fixture(truth=1.031))
    assert not marginal["candidates"][0]["refuted_on_readout"]
    assert not marginal["candidates"][0]["within_tolerance_on_readout"]
    assert marginal["candidates"][1]["refuted_on_readout"]
    assert not marginal["predictive_discrimination_supported"]
    _, wrong, _ = completed(Fixture(truth=1.5))
    assert wrong["outcome"] == "both_candidates_refuted"
    assert wrong["counterexample_candidate_ids"] == ["model-0", "model-1"]
    assert wrong["supported_candidate"] is None


def test_prospective_indistinguishable_predictions_and_wide_tolerances_do_not_count():
    _, close, _ = completed(Fixture(), request(coefficients=(1, 1.005)))
    assert not close["design"]["planned_separation"]
    assert not close["predictive_discrimination_supported"]
    _, wide, _ = completed(Fixture(), request(tolerance=0.1))
    assert wide["design"]["planned_separation"]
    assert wide["design"]["wide_tolerance"] == [True, True]
    assert wide["candidates"][0]["within_tolerance_on_readout"]
    assert not wide["predictive_discrimination_supported"]
    with pytest.raises(ValueError, match="tolerance"):
        Fixture().session.register(request(tolerance=0.20001), records=prior())


def test_prospective_reference_only_disagreement_cannot_count_as_new_target_discrimination():
    def reference_only(source, s):
        offset = 1 if source == code(2) and s["drive"] == 0 else 0
        return [[s["drive"] * t + offset for _ in [0]] for t in s["times"]]

    fixture = Fixture(predictor=reference_only)
    proposal = request()
    proposal["experiments"].append({"id": "reference", "role": "reference", "spec": spec(0)})
    proposal["readout"].append({"experiment_id": "reference", "row": 1, "channel": "response", "weight": -1})
    registration, result, _ = completed(fixture, proposal)
    assert registration["design"]["separation_margin"] > 0
    assert registration["design"]["target_separation_margin"] < 0
    assert not result["predictive_discrimination_supported"]


def test_prospective_confidence_radius_scales_bias_correlation_and_replication():
    contract = public()
    contract.update(scales=[2.0], noise_std=[0.02], noise_mean_bias_bound=[0.003])
    fixture = Fixture(contract=contract, max_tests=2)
    proposal = request(tolerance=0.04)
    proposal["experiments"].append({"id": "reference", "role": "reference", "spec": spec(0)})
    proposal["readout"] = [
        {"experiment_id": "target", "row": 1, "channel": "response", "weight": 0.5},
        {"experiment_id": "target", "row": 2, "channel": "response", "weight": 0.5},
        {"experiment_id": "reference", "row": 1, "channel": "response", "weight": -1.0},
    ]
    registered = fixture.session.register(proposal, records=prior())
    design = registered["design"]
    # Two target rows can be correlated: sum their SD contributions before
    # squaring, then add the independent reference experiment's variance.
    variance = (0.5 * 0.02 / 2 + 0.5 * 0.02 / 2) ** 2 + (0.02 / 2) ** 2
    bias = (0.5 + 0.5 + 1) * 0.003 / 2
    assert design["variance_bound_per_replicate"] == pytest.approx(variance)
    assert design["mean_bias_bound"] == pytest.approx(bias)
    assert design["confidence_radius"] == pytest.approx(bias + math.sqrt(variance / (8 * 0.025)))
    assert design["predicted_readouts"] == pytest.approx([0.75, 1.5])
    assert design["hard_tolerance_max"] == pytest.approx(0.4)
    assert fixture.session.collect(registered["test_id"])["mean_readout"] == pytest.approx(0.75)


def test_prospective_refinement_keeps_counterexample_and_old_predictor_tests_new_regime():
    fixture = Fixture(truth=3)
    parent, failed_models, first_record = completed(fixture)
    assert failed_models["outcome"] == "both_candidates_refuted"
    revised = request(coefficients=(1, 3), drive=2)
    revised["revision_of"] = parent["test_id"]
    revised["change_note"] = "Counterexample suggests stronger response; retain the old law and test the revision under a new drive."
    revised["rivals"][1]["evidence_ids"].append(first_record["observations"][0]["id"])
    registration = fixture.session.register(revised, records=prior())
    result = fixture.session.collect(registration["test_id"])
    assert result["supported_candidate"] == "model-1"
    tests = fixture.session.snapshot()["tests"]
    assert tests[0]["result"] == failed_models
    assert tests[1]["registration"]["revision_of"] == parent["test_id"]
    assert tests[1]["registration"]["rivals"][0]["code_sha256"] == parent["rivals"][0]["code_sha256"]
    assert fixture.session.snapshot()["alpha_reserved"] == pytest.approx(2 * 0.05 / 3)


def test_prospective_refinement_cannot_refit_and_retest_same_observed_target():
    fixture = Fixture(truth=3)
    parent, _, old = completed(fixture)
    revision = request(coefficients=(1, 3))
    revision["revision_of"] = parent["test_id"]
    revision["change_note"] = "Refitted on the counterexample."
    revision["rivals"][1]["evidence_ids"].append(old["observations"][0]["id"])
    with pytest.raises(ValueError, match="previously unobserved"):
        fixture.session.register(revision, records=prior())


def test_prospective_rejects_known_readout_disguised_by_sampling_and_transfer_axis_only():
    fixture = Fixture()
    proposal = request(drive=0)
    proposal["experiments"][0]["spec"]["times"] = [0, 1, 3]
    with pytest.raises(ValueError, match="previously unobserved"):
        fixture.session.register(proposal, records=prior())
    proposal = request(profile="regime_transfer", drive=0)
    proposal["experiments"][0]["spec"]["times"] = [0, 3, 4]
    with pytest.raises(ValueError, match="change previously observed controls"):
        fixture.session.register(proposal, records=prior())
    _, result, _ = completed(Fixture(), request(profile="regime_transfer"))
    assert result["predictive_discrimination_supported"]


@pytest.mark.parametrize("mutation", [
    lambda r: r.update(timestamp="before any results"),
    lambda r: r.update(profile="open_discovery"),
    lambda r: r.update(replicates=17),
    lambda r: r.update(replicates=True),
    lambda r: r["readout"][0].update(row=0),
    lambda r: r["readout"][0].update(weight=0),
    lambda r: r["readout"][0].update(weight=float("nan")),
    lambda r: r["readout"].append(copy.deepcopy(r["readout"][0])),
    lambda r: r["rivals"][0].update(evidence_ids=["future-observation"]),
    lambda r: r["rivals"][0].update(predictor_code="def broken("),
    lambda r: r["rivals"][0].update(predictor_code="x = 1"),
    lambda r: r["rivals"][1].update(predictor_code=r["rivals"][0]["predictor_code"]),
    lambda r: r.update(revision_of="unknown", change_note="Changed my mind."),
])
def test_prospective_invalid_requests_never_observe(mutation):
    fixture = Fixture()
    proposal = request()
    mutation(proposal)
    with pytest.raises(ValueError):
        fixture.session.register(proposal, records=prior())
    assert fixture.observed == []


def test_prospective_hash_anchors_detect_code_output_and_observation_tampering():
    fixture = Fixture()
    registration, result, record = completed(fixture)
    for location in ("code", "prediction", "tolerance"):
        altered = copy.deepcopy(registration)
        if location == "code":
            altered["rivals"][0]["predictor_code"] += "# post-result edit\n"
        elif location == "prediction":
            altered["rivals"][0]["predictions"]["target"][1][0] = 123
        else:
            altered["rivals"][0]["tolerance"] = 0.19
        # Even recomputing the artifact's own hash cannot change the trusted seal.
        altered["seal_sha256"] = digest({k: v for k, v in altered.items() if k != "seal_sha256"})
        with pytest.raises(ValueError, match="seal mismatch"):
            recompute_result(altered, record["observations"], expected_seal=registration["seal_sha256"],
                             expected_observations_sha256=record["observations_sha256"])
    changed_data = copy.deepcopy(record["observations"])
    changed_data[0]["observation"]["values"][1][0] = 2
    with pytest.raises(ValueError, match="observation artifact"):
        recompute_result(registration, changed_data, expected_seal=registration["seal_sha256"],
                         expected_observations_sha256=record["observations_sha256"])
    registration["scope"] = "mutated returned copy"
    assert fixture.session.snapshot()["tests"][0]["result"] == result


def test_prospective_nonfinite_or_nondeterministic_predictors_fail_before_data():
    for mode in ("nan", "nondeterministic", "shape", "boolean", "mixed_boolean", "wide_row"):
        calls = []

        def bad(source, s):
            calls.append(source)
            if mode == "mixed_boolean":
                return [[0.0], [True], [1.0]]
            if mode == "wide_row":
                return [[0] * 1000 for _ in s["times"]]
            value = float("nan") if mode == "nan" else len(calls) if mode == "nondeterministic" else True
            return [[value] for _ in s["times"]] if mode != "shape" else [[1]]

        fixture = Fixture(predictor=bad)
        with pytest.raises(ValueError):
            fixture.session.register(request(), records=prior())
        snapshot = fixture.session.snapshot()
        assert snapshot["tests"][0]["status"] == "failed"
        assert fixture.events[-1]["kind"] == "failed"
        assert fixture.observed == []
        assert snapshot["alpha_reserved"] == pytest.approx(0.05 / 3)


def test_prospective_durable_registration_failure_blocks_collection():
    fixture = Fixture()

    def no_receipt(event):
        raise OSError("fixture storage failure")

    fixture.session._persist = no_receipt
    with pytest.raises(OSError):
        fixture.session.register(request(), records=prior())
    failed = fixture.session.snapshot()["tests"][0]
    assert failed["failure_receipt_missing"]
    with pytest.raises(ValueError):
        fixture.session.collect(failed["test_id"])
    assert fixture.observed == []


def test_prospective_partial_collection_is_retained_and_cannot_retry():
    fixture = Fixture()
    registration = fixture.session.register(request(), records=prior())
    real_observe = fixture.observe

    def failing(s, *, noise_key):
        if fixture.observed:
            raise RuntimeError("fixture read failure")
        return real_observe(s, noise_key=noise_key)

    fixture.session._observe = failing
    with pytest.raises(RuntimeError):
        fixture.session.collect(registration["test_id"])
    record = fixture.session.snapshot()["tests"][0]
    assert record["status"] == "failed" and len(record["observations"]) == 1
    assert "result" not in record
    assert fixture.events[-1]["kind"] == "failed"
    with pytest.raises(ValueError):
        fixture.session.collect(registration["test_id"])


def test_prospective_fixed_test_budget_event_order_and_defensive_snapshots():
    fixture = Fixture(max_tests=1)
    registration = fixture.session.register(request(), records=prior())
    with pytest.raises(ValueError, match="pending"):
        fixture.session.register(request(drive=2), records=prior())
    fixture.session.collect(registration["test_id"])
    with pytest.raises(ValueError, match="exhausted"):
        fixture.session.register(request(drive=2), records=prior())
    with pytest.raises(ValueError):
        fixture.session.collect(registration["test_id"])
    events = fixture.session.snapshot()["events"]
    for index, event in enumerate(events):
        assert event["sequence"] == index + 1
        assert event["previous_event_sha256"] == (events[index - 1]["event_sha256"] if index else None)
        assert digest({k: v for k, v in event.items() if k not in ("event_sha256", "receipt")}) == event["event_sha256"]
    snapshot = fixture.session.snapshot()
    snapshot["tests"].clear()
    assert len(fixture.session.snapshot()["tests"]) == 1


def test_prospective_changed_prior_record_rejected_and_public_contract_required():
    fixture = Fixture()
    completed(fixture)
    changed = prior()
    changed[0]["observation"]["values"][1][0] = 10
    with pytest.raises(ValueError, match="changed prior"):
        fixture.session.register(request(drive=2), records=changed)
    for field, value in [("scales", [0]), ("noise_std", [-1]), ("channels", ["y", "y"]),
                         ("noise_mean_bias_bound", [float("nan")])]:
        contract = public()
        contract[field] = value
        with pytest.raises(ValueError):
            Fixture(contract=contract)

"""Model-free protocol tests; no network or private predictor sandbox required."""
import copy
import hashlib
import io
import json
import math
import multiprocessing
import sqlite3
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import pytest

from env.ledger import AttemptBudgetExceeded, CampaignLedger
from env.runner import DEFAULT_LIMITS, _predict, run_episode
from env.scoring import (aggregate_episode, prediction_metrics, validate_submission,
                         verify_claims)
from env.transport import CampaignClient
from env.reporting import render_report, summarize
from env.campaign import _run_one
from sle.llm import LLMConfig


@pytest.fixture(autouse=True)
def synthetic_world_claim_policy(monkeypatch):
    """Keep the transparent scoring fixture out of production world policy."""
    from env.claim_semantics import claim_eligibility as real_eligibility

    def eligibility(world_name, control, treatment, readout, axis_field):
        if world_name == "linear-test":
            return {"eligible": True, "reason": "synthetic_test_world"}
        return real_eligibility(world_name, control, treatment, readout, axis_field)

    monkeypatch.setattr("env.scoring.claim_eligibility", eligibility)


class LinearWorld:
    name, version = "linear-test", "linear-test-1"
    axis_field = "times"
    channels, scales, noise_std = ("y",), (2.0,), (0.01,)

    def __init__(self):
        self.calls = []
        self.panel_calls = []
        self.before_panel = lambda: None

    def describe(self):
        return {"name": self.name, "channels": list(self.channels), "scales": list(self.scales),
                "schema": {"times": "sorted list in [0,4]", "rate": "number in [-3,3]"}}

    def validate(self, spec):
        if not isinstance(spec, dict) or set(spec) != {"times", "rate"}:
            raise ValueError("requires times and rate")
        if not isinstance(spec["times"], list) or not 1 <= len(spec["times"]) <= 5:
            raise ValueError("invalid times")
        if not isinstance(spec["rate"], (float, int)) or isinstance(spec["rate"], bool) or not -3 <= spec["rate"] <= 3:
            raise ValueError("invalid rate")
        times = spec["times"]
        if any(not isinstance(t, (int, float)) or not math.isfinite(t) or not 0 <= t <= 4 for t in times) or any(a >= b for a, b in zip(times, times[1:])):
            raise ValueError("invalid times")
        return {"times": [float(t) for t in times], "rate": float(spec["rate"])}

    def cost(self, spec):
        self.validate(spec)
        return 1

    def run(self, spec, *, noise_key=None):
        spec = self.validate(spec)
        self.calls.append((copy.deepcopy(spec), noise_key))
        values = np.asarray(spec["times"], dtype=float)[:, None] * spec["rate"]
        if noise_key is not None:
            seed = int.from_bytes(hashlib.sha256(noise_key.encode()).digest()[:8], "big")
            values += np.random.default_rng(seed).normal(0, 0.01, values.shape)
        return {"axis": spec["times"], "channels": ["y"], "values": values.tolist()}

    def panel(self, panel_seed, kind, count):
        self.before_panel()
        self.panel_calls.append((panel_seed, kind, count))
        return [{"times": [0.0, 1.0, 2.0], "rate": (1 if kind == "conditions" else -1) * (0.5 + i / count)} for i in range(count)]


def linear_baseline(records, spec):
    return [[0.0] for _ in spec["times"]]


def spec(rate=1.0, times=None):
    return {"times": [0.0, 1.0, 2.0] if times is None else times, "rate": rate}


def claim(identifier="effect", **changes):
    value = {"id": identifier, "statement": "Doubling rate increases y at one second by 1.",
             "control": spec(1), "treatment": spec(2), "readout": {"row": 1, "channel": "y"},
             "interval": [0.97, 1.03], "evidence_ids": ["obs-0001"], "scope": "Only the specified one-second contrast."}
    value.update(changes)
    return value


def submission(claims=None):
    return {"predictor_code": "def predict(spec):\n    return [[t*spec['rate']] for t in spec['times']]\n",
            "claims": [] if claims is None else claims, "explanation": "A linear model fitted from public observations."}


class FakeClient:
    def __init__(self, replies, transport_error=None):
        self.config = SimpleNamespace(model="reported-model", timeout_seconds=1)
        self.replies, self.prompts = iter(replies), []
        self.last_usage = {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15}
        self.total_usage = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
        self.last_response_metadata = {"provider_reported_models": ["reported-model"]}
        self.last_stop_reason = "stop"
        self.last_transport_error = transport_error

    def complete(self, prompt, system=None):
        self.prompts.append(json.loads(prompt))
        reply = next(self.replies)
        if isinstance(reply, Exception):
            raise reply
        for key, value in self.last_usage.items():
            self.total_usage[key] += value
        return reply if isinstance(reply, str) else json.dumps(reply)

    def transport_summary(self):
        return {"attempts": len(self.prompts), "automatic_retries": 0}


class FakeAnalysis:
    def __init__(self, seconds):
        self.remaining, self.calls, self.closed = seconds, [], False

    def run(self, code, problem, records, history):
        self.calls.append(copy.deepcopy((code, problem, records, history)))
        self.remaining -= 0.1
        return {"ok": True, "result": {"number_of_observations": len(records)}}

    def close(self):
        self.closed = True


def episode(tmp_path, replies, *, predict=None, world=None, changes=None, client=None):
    world = world or LinearWorld()
    world.before_panel = lambda: None if (tmp_path / "submission.json").exists() else pytest.fail("holdout generated before freeze")
    client = client or FakeClient(replies)
    analyzer = FakeAnalysis(2.0)
    limits = dict(DEFAULT_LIMITS, rounds=4, exploration_rounds=3, experiments=3,
                  experiment_units=3, analysis_active_seconds=2, panel_count=2, wall_seconds=300,
                  verification_reserve_seconds=0)
    limits.update(changes or {})
    instance = {"episode_id": "episode-test", "environment": "linear-test", "world_seed": 7654321,
                "panel_seed": 654321, "confirmation_key": "private-confirmation-canary", "cohort": "test"}
    if predict is None:
        def predict(path, query, seconds):
            assert path.read_text() == submission()["predictor_code"]
            return [[t * query["rate"]] for t in query["times"]]
    with patch("env.runner.load_world", return_value=(world, linear_baseline)), patch("env.runner.source_digest", return_value="0" * 64):
        result = run_episode(instance, limits, tmp_path, client,
                             analysis_factory=lambda seconds: analyzer, predict_fn=predict)
    assert analyzer.closed
    return result, client, analyzer, world


def test_scoring_uses_public_scales_and_excludes_only_initial_row():
    observed = {"axis": [0, 1, 2], "values": [[100, 100], [2, 4], [2, 4]]}
    metric = prediction_metrics([[999, -999], [4, 4], [2, 8]], observed, [2, 4])
    assert metric["scored_rows"] == 2
    assert metric["normalized_rmse"] == pytest.approx(math.sqrt(0.5))
    assert metric["score"] == pytest.approx(100 * math.exp(-math.sqrt(0.5) / 0.1))
    assert metric["channel_normalized_rmse"] == pytest.approx([math.sqrt(0.5)] * 2)
    single = prediction_metrics([[2]], {"axis": [0], "values": [[0]]}, [2])
    assert single["scored_rows"] == 1 and single["normalized_rmse"] == 1
    for bad in ([[float("nan")]], [[1e13]], [1, 2], [[1, 2]]):
        with pytest.raises(ValueError):
            prediction_metrics(bad, {"axis": [1], "values": [[0]]}, [2])


def test_aggregation_weights_experiments_equally_and_fixed_claim_slots():
    panel = {"conditions": [{"score": 100}, {"score": 0}], "interventions": [{"score": 20}]}
    result = aggregate_episode(panel, {"score": 30})
    assert result["score"] == pytest.approx(37)
    world = LinearWorld()
    reports = verify_claims(world, [claim()], "fresh")
    first = reports["claims"][0]
    assert reports["score"] == pytest.approx(first["score"] / 3)
    assert first["verified_nonzero_effect"] and not first["mechanism_certified"]
    keys = [key for _, key in world.calls]
    assert len(keys) == len(set(keys)) == 16
    assert all(key.startswith("fresh:claim:") for key in keys)
    assert verify_claims(world, [], "other")["score"] == 0


def test_claims_require_prior_evidence_postinitial_readout_and_deduplicate_reversal():
    world = LinearWorld()
    records = [{"id": "obs-0001"}]
    validate_submission(submission([claim()]), world, records)
    for change in ({"evidence_ids": ["obs-unknown"]}, {"readout": {"row": 0, "channel": "y"}},
                   {"readout": {"row": 999, "channel": "y"}}, {"interval": [2, 1]},
                   {"control": spec(2)}):
        with pytest.raises(ValueError):
            validate_submission(submission([claim(**change)]), world, records)
    reverse = claim("reverse", control=spec(2), treatment=spec(1), interval=[-1.03, -0.97])
    result = verify_claims(world, [claim(), reverse], "confirmation")
    assert result["claims"][1]["duplicate"]
    assert result["claims"][1]["score"] == 0
    assert result["verified_nonzero_effects"] == 1


def test_episode_freezes_before_holdouts_and_keeps_public_analysis_separate(tmp_path):
    replies = [{"note": "Observe", "experiments": [spec()]},
               {"note": "Fit", "analyze": {"code": "result = len(records)"}},
               {"note": "Freeze", "submit": submission([claim()])}]
    report, client, analyzer, world = episode(tmp_path, replies)
    assert report["status"] == "completed" and report["score"] > 80
    assert report["experiment_count"] == report["experiment_units"] == 1
    assert report["provider_reported_models"] == ["reported-model"]
    assert len(analyzer.calls) == 1 and len(analyzer.calls[0][2]) == 1
    public = json.dumps([client.prompts, analyzer.calls])
    for private in ("7654321", "654321", "private-confirmation-canary", "clean_truth", "world_seed", "panel_seed"):
        assert private not in public
    assert len(world.panel_calls) == 2
    assert json.loads((tmp_path / "report.json").read_text()) == report
    assert json.loads((tmp_path / "submission.json").read_text())["claims"][0]["id"] == "effect"
    assert (tmp_path / "instance-private.json").exists()
    confirmation = [key for _, key in world.calls if key and "claim:" in key]
    assert len(set(confirmation)) == 16
    assert "episode-test:obs-0001" not in confirmation
    assert report["usage"]["total_tokens"] == 45


@pytest.mark.parametrize("reply", ["", "{broken", {"note": "no submission", "experiments": []}])
def test_healthy_incomplete_model_runs_count_zero(tmp_path, reply):
    report, _, _, world = episode(tmp_path, [reply, reply], changes={"rounds": 2, "exploration_rounds": 1})
    assert report["status"] == "incomplete"
    assert report["score"] == 0 and report["infrastructure_failure"] is None
    assert not report["model_completed"] and not world.panel_calls


def test_invalid_frozen_predictor_zeroes_entire_episode(tmp_path):
    count = [0]
    def predict(path, query, seconds):
        count[0] += 1
        if count[0] == 1:
            raise RuntimeError("private path should not surface")
        return [[t * query["rate"]] for t in query["times"]]
    report, _, _, _ = episode(tmp_path, [{"note": "Freeze", "submit": submission()}], predict=predict)
    assert report["status"] == "invalid_predictor"
    assert report["score"] == 0 and report["infrastructure_failure"] is None
    assert count[0] == 4
    assert report["panels"]["conditions"][1]["score"] == 100
    assert "private path" not in report["panels"]["conditions"][0]["error"]


def test_partial_batches_preserve_charges_and_closing_phase_blocks_experiments(tmp_path):
    replies = [{"note": "Three requests", "experiments": [spec(), spec(2), spec(3)]},
               {"note": "Closing misuse", "experiments": [spec()]}]
    report, client, _, _ = episode(tmp_path, replies, changes={"rounds": 2, "exploration_rounds": 1,
                                                             "experiments": 1, "experiment_units": 1})
    assert report["experiment_count"] == report["experiment_units"] == 1
    assert len(report["history"][0]["observations"]) == 1
    assert report["history"][0]["error"] == "experiment_count_exhausted"
    assert report["history"][1]["error"] == "submission_required_in_closing_phase"
    assert client.prompts[1]["budget"]["experiments_remaining"] == 0


def test_transport_failures_are_infrastructure_with_no_invented_score(tmp_path):
    client = FakeClient([RuntimeError("network failed")], {"stage": "request", "http_status": 503})
    report, _, _, _ = episode(tmp_path, [], client=client)
    assert report["score"] is None and report["status"] == "failed"
    assert report["infrastructure_failure"] == "api_transport_or_provider"


def test_predictor_worker_is_fresh_for_every_query():
    workers = []
    class Worker:
        def __init__(self, path, entrypoint, timeout_s):
            self.closed = False
            workers.append(self)
        def __call__(self, query):
            return query
        def close(self):
            self.closed = True
    with patch("env.runner.CandidateProxy", Worker):
        assert _predict("candidate.py", {"x": 1}, 1) == {"x": 1}
        assert _predict("candidate.py", {"x": 2}, 1) == {"x": 2}
    assert len(workers) == 2 and all(worker.closed for worker in workers)


def _reserve_process(path, queue):
    try:
        ledger = CampaignLedger(path)
        attempt = ledger.reserve("concurrent", "hash", active_limit=50, rpm=1000, wait_seconds=0)
        ledger.finish(attempt, "returned", {})
        queue.put("reserved")
    except AttemptBudgetExceeded:
        queue.put("capped")
    except Exception as exc:
        queue.put(type(exc).__name__)


def test_campaign_ledger_process_concurrency_cannot_exceed_quota(tmp_path):
    path = tmp_path / "campaign.sqlite"
    ledger = CampaignLedger(path, limit=5)
    context = multiprocessing.get_context("spawn")
    queue = context.Queue()
    processes = [context.Process(target=_reserve_process, args=(str(path), queue)) for _ in range(12)]
    for process in processes:
        process.start()
    outcomes = [queue.get(timeout=30) for _ in processes]
    for process in processes:
        process.join(timeout=30)
        assert process.exitcode == 0
    assert outcomes.count("reserved") == 5 and outcomes.count("capped") == 7
    assert ledger.summary()["remaining_attempts"] == 0
    assert ledger.summary()["status_counts"] == {"returned": 5}
    with pytest.raises(ValueError, match="immutable"):
        CampaignLedger(path, limit=6)


def test_campaign_active_rpm_and_uncertain_attempts_remain_charged(tmp_path):
    ledger = CampaignLedger(tmp_path / "campaign.sqlite", limit=4)
    first = ledger.reserve("a", "hash", active_limit=1, rpm=10, wait_seconds=0)
    with pytest.raises(TimeoutError):
        ledger.reserve("b", "hash", active_limit=1, rpm=10, wait_seconds=0)
    assert ledger.summary()["started_attempts"] == 1
    ledger.finish(first, "failed", {"exception_type": "TimeoutError"})
    with pytest.raises(TimeoutError):
        ledger.reserve("b", "hash", active_limit=1, rpm=1, wait_seconds=0)
    second = ledger.reserve("b", "hash", active_limit=1, rpm=10, wait_seconds=0)
    ledger.finish(second, "interrupted", {})
    with pytest.raises(ValueError, match="already finalized"):
        ledger.finish(second, "returned", {})
    assert ledger.summary()["remaining_attempts"] == 2


def test_campaign_transport_reserves_before_network_and_never_retries(tmp_path):
    ledger = CampaignLedger(tmp_path / "campaign.sqlite", limit=2)
    client = CampaignClient(LLMConfig(api_key="PRIVATE-KEY", model="requested"), tmp_path, ledger, "test", max_attempts=2)
    reply = {"model": "provider-model", "choices": [{"message": {"content": "{}"}, "finish_reason": "stop"}],
             "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}}
    def fake_open(*args, **kwargs):
        assert ledger.summary()["started_attempts"] == 1
        assert ledger.summary()["status_counts"] == {"started": 1}
        assert '"event": "started"' in (tmp_path / "model-transport.jsonl").read_text()
        return io.BytesIO(json.dumps(reply).encode())
    with patch("urllib.request.urlopen", fake_open):
        assert client.complete("public") == "{}"
    with patch("urllib.request.urlopen", side_effect=TimeoutError("sensitive endpoint")) as request:
        with pytest.raises(TimeoutError):
            client.complete("public2")
        assert request.call_count == 1
    assert ledger.summary()["status_counts"] == {"failed": 1, "returned": 1}
    assert client.transport_summary()["attempts"] == 2
    assert client.total_usage["total_tokens"] is None
    artifacts = (tmp_path / "model-transport.jsonl").read_text()
    assert "PRIVATE-KEY" not in artifacts and "sensitive endpoint" not in artifacts


def test_finite_extreme_claim_interval_cannot_break_report_serialization():
    world = LinearWorld()
    value = submission([claim(interval=[-1e308, 1e308])])
    try:
        checked = validate_submission(value, world, [{"id": "obs-0001"}])
    except ValueError:
        return  # Rejecting intervals beyond supported numeric work is valid.
    verified = verify_claims(world, checked["claims"], "fresh")
    json.dumps(verified, allow_nan=False)


def test_huge_model_interval_is_validation_error_not_operator_failure():
    with pytest.raises(ValueError):
        validate_submission(submission([claim(interval=[0, 10**1000])]), LinearWorld(), [{"id": "obs-0001"}])


def test_pathological_bounded_predictor_ast_is_validation_error():
    value = submission()
    value["predictor_code"] = "def predict(spec):\n return " + "+" * 10000 + "1"
    with pytest.raises(ValueError):
        validate_submission(value, LinearWorld(), [])


def test_provider_model_mismatch_is_reported_without_running_experiments(tmp_path):
    client = FakeClient([{"note": "Observe", "experiments": [spec()]}])
    client.config.model = "different-requested-model"
    report, _, _, world = episode(tmp_path, [], client=client)
    assert report["infrastructure_failure"] == "provider_model_mismatch"
    assert report["score"] is None and report["experiment_count"] == 0
    assert not world.calls


def test_claim_validation_does_not_call_hidden_simulation():
    world = LinearWorld()
    validate_submission(submission([claim()]), world, [{"id": "obs-0001"}])
    assert world.calls == []


def test_padded_observation_grid_does_not_create_an_independent_claim():
    world = LinearWorld()
    repeated = claim("same-effect-padded", control=spec(1, [0, 0.5, 1, 2, 3]),
                     treatment=spec(2, [0, 0.5, 1, 2, 3]), readout={"row": 2, "channel": "y"})
    checked = validate_submission(submission([claim(), repeated]), world, [{"id": "obs-0001"}])
    report = verify_claims(world, checked["claims"], "fresh-grid")
    assert report["claims"][1]["duplicate"]
    assert report["claims"][1]["score"] == 0
    assert report["verified_nonzero_effects"] == 1


def _report(identifier, environment, status="completed", score=80, infrastructure=None):
    return {"episode_id": identifier, "environment": environment, "status": status,
            "score": score, "infrastructure_failure": infrastructure,
            "model_completed": status == "completed", "has_verified_effect": status == "completed",
            "verified_nonzero_effects": 1 if status == "completed" else 0,
            "known_response_usage_lower_bound": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
            "baseline_panels": {"conditions": [{"score": 20}], "interventions": [{"score": 10}]}}


def test_reporting_denominators_include_healthy_failures_and_macro_environment_weights():
    rows = [_report("a1", "a", score=80), _report("a2", "a", "invalid_predictor", 0),
            _report("b1", "b", "incomplete", 0), _report("b2", "b", score=60),
            _report("b3", "b", "failed", None, "provider"), _report("b4", "b", "running", None)]
    result = summarize(rows, ["a", "b"])
    assert result["healthy_runs"] == 4 and result["infrastructure_failures"] == 1
    assert result["started_runs"] == 6 and result["settled_runs"] == 5
    assert result["model_completion"]["denominator"] == 4
    assert result["model_completion"]["numerator"] == 2
    assert result["end_to_end_completion"]["rate"] == pytest.approx(2 / 6)
    assert result["macro_score"] == pytest.approx(35)
    assert result["by_environment"]["a"]["scores"] == [80, 0]
    assert result["by_environment"]["b"]["scores"] == [0, 60]
    assert result["known_response_usage_lower_bound"]["total_tokens"] == 90
    assert result["cost_usd"] is None
    assert result["macro_bootstrap_95"] == summarize(rows, ["a", "b"])["macro_bootstrap_95"]
    assert summarize(rows, ["a", "b", "absent"])["macro_score"] is None
    assert summarize([], ["a"])["model_completion"]["rate"] is None


def _write_report_inputs(directory, instances, reports, errors=None, started=None):
    (directory / "episodes").mkdir()
    manifest = {"cohort": "review-test", "environments": ["a"], "instances": instances,
                "source_sha256": "a" * 64}
    (directory / "manifest-private.json").write_text(json.dumps(manifest))
    (directory / "campaign-status.json").write_text(json.dumps({"status": "completed", "errors": errors or [],
                                                               "finished": [{"episode_id": r["episode_id"]} for r in reports]}))
    for identifier in started or [r["episode_id"] for r in reports]:
        folder = directory / "episodes" / identifier
        folder.mkdir()
        (folder / "started.json").write_text(json.dumps({"episode_id": identifier, "environment": "a"}))
    for report in reports:
        folder = directory / "episodes" / report["episode_id"]
        (folder / "report.json").write_text(json.dumps(report))


def test_report_artifacts_preserve_denominators_and_escape_model_text(tmp_path):
    report = _report("good", "a")
    report["claim_verification"] = {"claims": [{"id": "claim-id", "statement": "<script>bad()</script>",
                                               "scope": "Only this & that", "mean_difference": 1,
                                               "interval": [0.9, 1.1], "verified_nonzero_effect": True}]}
    _write_report_inputs(tmp_path, [{"episode_id": "good", "environment": "a"}], [report])
    summary = render_report(tmp_path)
    assert json.loads((tmp_path / "summary.json").read_text())["macro_score"] == 80
    assert summary["planned_runs"] == summary["started_runs"] == 1
    page = (tmp_path / "index.html").read_text()
    assert "<script>bad()" not in page and "&lt;script&gt;bad()&lt;/script&gt;" in page
    assert "episodes/good/report.json" in page and "summary.json" in page


def test_report_renders_bootstrap_interval_after_multiple_instances(tmp_path):
    rows = [_report("a1", "a", score=80), _report("a2", "a", score=60)]
    _write_report_inputs(tmp_path, [{"episode_id": r["episode_id"], "environment": "a"} for r in rows], rows)
    summary = render_report(tmp_path)
    assert summary["macro_bootstrap_95"] is not None
    assert "95% 区间" in (tmp_path / "index.html").read_text()


def test_apparatus_presentation_reaches_model_and_analysis_with_real_world(tmp_path):
    from env.coupled_oscillators.world import World
    from env.presentation_profiles import present_system
    from env.runner import SYSTEM
    world = World(7)
    analyzer = FakeAnalysis(2)
    class CaptureClient(FakeClient):
        def complete(self, prompt, system=None):
            self.system = system
            return super().complete(prompt, system)
    client = CaptureClient([{"note": "Inspect instrument", "analyze": {"code": "result = problem['name']"}},
                            {"note": "Freeze", "submit": {"predictor_code": "def predict(spec): return []", "claims": [], "explanation": "Fixture"}}])
    instance = {"episode_id": "instrument-test", "environment": world.name, "world_seed": 7,
                "panel_seed": 17, "confirmation_key": "private", "presentation_profile": "apparatus_only"}
    limits = dict(DEFAULT_LIMITS, rounds=2, exploration_rounds=1, panel_count=1)
    with patch("env.runner.load_world", return_value=(world, lambda records, query: world.run(query)["values"])):
        report = run_episode(instance, limits, tmp_path, client, analysis_factory=lambda seconds: analyzer,
                             predict_fn=lambda path, query, seconds: world.run(query)["values"])
    assert report["model_completed"]
    assert client.prompts[0]["problem"]["name"] == "apparatus"
    assert analyzer.calls[0][1] == client.prompts[0]["problem"]
    assert "coupled_oscillators" not in json.dumps(client.prompts[0]["problem"])
    assert client.system == present_system(SYSTEM, "apparatus_only")
    assert report["public_system_sha256"] == report["rounds"][0]["system_sha256"]


@pytest.mark.parametrize("has_started_marker", [False, True])
def test_worker_failure_does_not_disappear_or_remain_running_in_report(tmp_path, has_started_marker):
    instances = [{"episode_id": "good", "environment": "a"}, {"episode_id": "broken", "environment": "a"}]
    started = ["good", "broken"] if has_started_marker else ["good"]
    _write_report_inputs(tmp_path, instances, [_report("good", "a")],
                         errors=[{"episode_id": "broken", "exception_type": "RuntimeError"}], started=started)
    summary = render_report(tmp_path)
    assert summary["started_runs"] == 2
    assert summary["running_runs"] == 0
    assert summary["infrastructure_failures"] == 1
    assert summary["model_completion"]["denominator"] == 1
    assert summary["end_to_end_completion"]["rate"] == 0.5


def test_precommitted_panel_mismatch_stops_before_model_or_analysis_calls(tmp_path):
    world = LinearWorld()
    client = FakeClient([])
    instance = {"episode_id": "mismatched", "environment": "linear-test", "world_seed": 1,
                "panel_seed": 2, "confirmation_key": "private", "panel_hashes": {"conditions": "wrong-hash"}}
    with patch("env.runner.load_world", return_value=(world, linear_baseline)), patch("env.runner.source_digest", return_value="0" * 64):
        with patch("env.runner.IsolatedAnalysis") as analyzer:
            result = run_episode(instance, dict(DEFAULT_LIMITS), tmp_path, client, analysis_factory=analyzer)
    assert result["infrastructure_failure"] is not None and result["score"] is None
    assert not client.prompts and not world.calls
    analyzer.assert_not_called()


def test_campaign_worker_checks_frozen_source_before_network_or_config_read(tmp_path):
    instance = {"episode_id": "source-check", "environment": "heat_transport", "cohort": "test"}
    folder = tmp_path / "episode"
    with patch("env.campaign.source_digest", return_value="changed"), patch("env.campaign.CampaignClient") as client:
        with pytest.raises(ValueError, match="source changed"):
            _run_one(instance, DEFAULT_LIMITS, folder, tmp_path / "nonexistent-config.json",
                     tmp_path / "unused.sqlite", 1, 60, "frozen", {})
    assert (folder / "started.json").exists()
    client.assert_not_called()


def test_campaign_worker_rejects_decoding_drift_before_transport(tmp_path):
    instance = {"episode_id": "config-check", "environment": "heat_transport", "cohort": "test"}
    folder, config = tmp_path / "episode", tmp_path / "config.json"
    config.write_text(json.dumps({"model": "gpt-5.6-sol", "reasoning_effort": "high", "api_key": "PRIVATE-KEY"}))
    with patch("env.campaign.source_digest", return_value="frozen"), patch("env.campaign.CampaignClient") as client:
        with pytest.raises(ValueError, match="decoding differs"):
            _run_one(instance, DEFAULT_LIMITS, folder, config, tmp_path / "unused.sqlite", 1, 60,
                     "frozen", {"reasoning_effort": "medium"})
    assert "PRIVATE-KEY" not in (folder / "started.json").read_text()
    client.assert_not_called()

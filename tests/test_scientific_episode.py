"""Protocol adversarial checks using no model endpoint or scientific simulator."""
from __future__ import annotations

import copy
import contextlib
import io
import json
from pathlib import Path
import stat
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from sle.scientific_episode import (
    EpisodeSession, digest, parse_action, prepare_output, run_llm,
    run_policy, save_report, validate_episode_report,
)


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


class FakeEnvironment:
    task_id = "Test/Discovery"
    budget_units = 3

    def __init__(self):
        self.private_seed = "PRIVATE_SEED_907311"
        self.experiments = []
        self.confirmations = []
        self.evaluations = []

    def public_problem(self):
        return {"budget_units": self.budget_units, "claim_schema": {"prediction": "number"}}

    def action_cost(self, tool, arguments):
        if tool != "measure" or not isinstance(arguments, dict) or set(arguments) != {"value"}:
            raise ValueError("bad input " + self.private_seed)
        value = arguments["value"]
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise ValueError("bad value " + self.private_seed)
        return value

    def experiment(self, tool, arguments):
        self.experiments.append(copy.deepcopy(arguments))
        return {"sample_id": "exploration-%d" % len(self.experiments), "measurement": 0.25}

    def validate_claim(self, claim):
        if not isinstance(claim, dict) or set(claim) != {"prediction"} or not isinstance(claim["prediction"], (int, float)):
            raise ValueError("invalid claim " + self.private_seed)

    def confirm(self, claim):
        self.confirmations.append(copy.deepcopy(claim))
        claim["prediction"] = -999  # Trusted callbacks must still receive detached values.
        return {"sample_id": "independent-confirmation", "measurement": 0.3}

    def evaluate(self, claim, confirmation):
        self.evaluations.append((copy.deepcopy(claim), copy.deepcopy(confirmation)))
        claim["prediction"] = -111
        confirmation["sample_id"] = "mutated-inside-evaluator"
        return {"mechanism_score": 0.5, "private_truth": self.private_seed}


class FakeLLM:
    last_usage = {"prompt_tokens": 2, "completion_tokens": 3}
    last_stop_reason = "stop"

    def __init__(self, replies, before_reply=None):
        self.replies = iter(replies)
        self.prompts = []
        self.before_reply = before_reply

    def complete(self, prompt, system):
        self.prompts.append({"prompt": prompt, "system": system})
        if self.before_reply:
            self.before_reply()
        return next(self.replies)


def measurement(value=1):
    return {"action": "experiment", "tool": "measure", "arguments": {"value": value}}


def commit(value=0.5):
    return {"action": "commit", "claim": {"prediction": value}}


def rehash_report(report):
    report["sha256"] = digest({key: value for key, value in report.items() if key != "sha256"})
    return report


def rehash_events(report):
    previous = None
    for seq, event in enumerate(report["events"]):
        event["seq"] = seq
        event["previous_sha256"] = previous
        event["sha256"] = digest({key: value for key, value in event.items() if key != "sha256"})
        previous = event["sha256"]
    return rehash_report(report)


class ScientificEpisodeTests(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.env = FakeEnvironment()
        self.session = EpisodeSession(self.env, clock=self.clock, wall_seconds=10,
                                      binding={"task_id": self.env.task_id, "seed": self.env.private_seed})

    def completed(self):
        self.session.step(measurement())
        self.session.step(commit())
        return self.session.report()

    def test_commit_is_detached_immutable_and_confirmation_follows_exploration(self):
        request = commit()
        self.session.step(measurement())
        response = self.session.step(request)
        request["claim"]["prediction"] = 88
        response["confirmation"]["measurement"] = 99
        self.assertEqual(self.session.claim, {"prediction": 0.5})
        self.assertEqual(self.session.confirmation["measurement"], 0.3)
        self.assertEqual(self.env.evaluations[0][0], {"prediction": 0.5})
        self.assertEqual(self.env.evaluations[0][1]["sample_id"], "independent-confirmation")
        self.assertEqual(self.session.step(commit(77))["error"], "episode_closed")
        self.assertEqual(self.session.step(measurement())["error"], "episode_closed")
        self.assertEqual(len(self.env.confirmations), 1)
        self.assertEqual(len(self.env.experiments), 1)
        self.assertEqual(validate_episode_report(self.session.report())["status"], "structurally_consistent")

    def test_private_binding_and_metrics_never_reach_model_or_transcript(self):
        model = FakeLLM([json.dumps(measurement()), json.dumps(commit())])
        report = run_llm(self.session, model)
        public = json.dumps({"prompts": model.prompts, "transcript": self.session.transcript,
                             "observation": self.session.observation()})
        self.assertNotIn(self.env.private_seed, public)
        self.assertNotIn("private_truth", public)
        self.assertEqual(report["metrics"]["private_truth"], self.env.private_seed)
        self.assertEqual(report["status"], "completed")
        self.assertEqual(len(model.prompts), 2)

    def test_request_and_response_mutations_do_not_rewrite_recorded_evidence(self):
        request = measurement()
        response = self.session.step(request)
        request["arguments"]["value"] = 99
        response["observation"]["measurement"] = 99
        self.assertEqual(self.session.transcript[0]["request"]["arguments"]["value"], 1)
        self.assertEqual(self.session.transcript[0]["response"]["observation"]["measurement"], 0.25)
        self.session.step(commit())
        report = self.session.report()
        report["claim"]["prediction"] = 99
        self.assertEqual(self.session.report()["claim"]["prediction"], 0.5)

    def test_invalid_inputs_consume_steps_and_overbudget_call_never_executes(self):
        self.assertEqual(self.session.step({"action": "experiment", "tool": "measure", "arguments": {}})["error"], "invalid_experiment_arguments")
        self.assertEqual(self.session.units, 0)
        self.assertEqual(self.session.steps, 1)
        self.assertTrue(self.session.step(measurement(2))["ok"])
        self.assertEqual(self.session.step(measurement(2))["error"], "experiment_budget_exceeded")
        self.assertEqual(self.session.units, 2)
        self.assertEqual(self.session.steps, 3)
        self.assertEqual(len(self.env.experiments), 1)
        self.assertTrue(self.session.step(commit())["ok"])

    def test_failed_experiment_is_charged_and_does_not_expose_exception(self):
        with patch.object(self.env, "experiment", side_effect=RuntimeError(self.env.private_seed)):
            response = self.session.step(measurement(2))
        self.assertEqual(self.session.units, 2)
        self.assertEqual(self.session.experiments, 1)
        self.assertEqual(self.session.state, "infrastructure_error")
        self.assertIsNone(self.session.metrics)
        self.assertNotIn(self.env.private_seed, json.dumps(response))
        self.assertNotIn(self.env.private_seed, self.session.error)

    def test_malformed_and_oversized_actions_cannot_extend_step_budget(self):
        session = EpisodeSession(FakeEnvironment(), max_steps=2, clock=self.clock)
        session.step({"action": "unknown", "value": float("nan")})
        with patch("sle.scientific_episode.MAX_JSON_BYTES", 1024):
            response = session.step({"action": "analyze", "code": "x" * 2000})
        self.assertFalse(response["ok"])
        self.assertEqual(session.steps, 2)
        self.assertEqual(session.step(commit())["error"], "budget_exhausted")
        self.assertIsNone(session.metrics)

    def test_last_allowed_action_may_commit_but_following_action_cannot(self):
        session = EpisodeSession(FakeEnvironment(), max_steps=1, clock=self.clock)
        self.assertTrue(session.step(commit())["ok"])
        self.assertEqual(session.steps, 1)
        self.assertEqual(session.step(commit())["error"], "episode_closed")

    def test_late_model_commit_gets_no_confirmation_or_scientific_score(self):
        def expire():
            self.clock.now = 10.0
        model = FakeLLM([json.dumps(commit())], before_reply=expire)
        report = run_llm(self.session, model)
        self.assertEqual(report["status"], "budget_exhausted")
        self.assertIsNone(report["metrics"])
        self.assertEqual(self.env.confirmations, [])
        self.assertEqual(len(model.prompts), 1)

    def test_operator_confirmation_is_reserved_after_timely_commit(self):
        original = self.env.confirm
        def slow(claim):
            self.clock.now = 11
            return original(claim)
        with patch.object(self.env, "confirm", side_effect=slow):
            self.session.step(commit())
        self.assertEqual(self.session.state, "completed")
        self.assertIsNotNone(self.session.metrics)
        validate_episode_report(self.session.report())

    def test_candidate_analysis_failure_differs_from_environment_failure(self):
        def broken(*_args):
            raise RuntimeError("candidate failure")
        session = EpisodeSession(FakeEnvironment(), analysis=broken, clock=self.clock)
        session.step({"action": "analyze", "code": "raise RuntimeError()"})
        self.assertEqual(session.state, "invalid_candidate")
        self.assertIsNone(session.metrics)
        session = EpisodeSession(FakeEnvironment(), analysis=lambda *_args: (_ for _ in ()).throw(TimeoutError()), clock=self.clock)
        session.step({"action": "analyze", "code": "while True: pass"})
        self.assertEqual(session.state, "budget_exhausted")

    def test_failed_model_transport_has_no_scientific_score(self):
        model = FakeLLM([])
        report = run_llm(self.session, model)
        self.assertEqual(report["status"], "model_error")
        self.assertIsNone(report["metrics"])

    def test_program_sandbox_timeout_is_a_budget_outcome(self):
        def timed_out(_problem, _experiment):
            raise TimeoutError("candidate timeout")
        report = run_policy(self.session, timed_out)
        self.assertEqual(report["status"], "budget_exhausted")
        self.assertIsNone(report["metrics"])

    def test_oversized_model_reply_is_accounted_and_terminates_with_report(self):
        session = EpisodeSession(FakeEnvironment(), max_steps=1, clock=self.clock)
        model = FakeLLM(["x" * 3000])
        with patch("sle.scientific_episode.MAX_JSON_BYTES", 1024):
            report = run_llm(session, model)
        self.assertEqual(len(model.prompts), 1)
        self.assertNotEqual(report["status"], "completed")
        self.assertIsNone(report["metrics"])
        validate_episode_report(report)

    def test_model_json_parser_rejects_duplicate_nonfinite_and_nonobject(self):
        for value in ('{"action":"commit","action":"experiment"}', '{"x":NaN}',
                      '{"x":Infinity}', '[1]', '```json\n{}\n```'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_action(value)

    def test_evidence_limit_returns_a_report_instead_of_crashing(self):
        model = FakeLLM([json.dumps(measurement())])
        with patch("sle.scientific_episode.MAX_EVIDENCE_BYTES", self.session.evidence_bytes + 1):
            report = run_llm(self.session, model)
        self.assertNotEqual(report["status"], "completed")
        self.assertIsNone(report["metrics"])
        validate_episode_report(report)

    def test_rehashed_metrics_must_match_recorded_evaluator_outcome(self):
        report = self.completed()
        report["metrics"]["mechanism_score"] = 1.0
        rehash_report(report)
        with self.assertRaises(ValueError):
            validate_episode_report(report)

    def test_pilot_cannot_self_promote_or_invent_terminal_status(self):
        for key, value in (("frontier_eligible", True), ("difficulty", "hard"),
                           ("kind", "certified"), ("status", "passed")):
            report = self.completed()
            report[key] = value
            rehash_report(report)
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_episode_report(report)

    def test_evidence_limit_during_transport_failure_still_returns_unscored_report(self):
        with patch("sle.scientific_episode.MAX_EVIDENCE_BYTES", self.session.evidence_bytes):
            report = run_llm(self.session, FakeLLM([]))
        self.assertEqual(report["status"], "evidence_limit")
        self.assertIsNone(report["metrics"])
        validate_episode_report(report)

    def test_unhashed_and_rehashed_event_tampering_is_detected(self):
        report = self.completed()
        altered = copy.deepcopy(report)
        altered["metrics"]["mechanism_score"] = 1.0
        with self.assertRaises(ValueError):
            validate_episode_report(altered)
        altered = copy.deepcopy(report)
        altered["events"][1]["payload"]["arguments"]["value"] = 3
        rehash_report(altered)
        with self.assertRaises(ValueError):
            validate_episode_report(altered)

    def test_rehashed_resource_inconsistency_is_rejected(self):
        report = self.completed()
        for field, bad in (("steps", 1000), ("steps", -1), ("experiment_calls", 99),
                           ("experiment_units", True), ("analysis_calls", -1)):
            altered = copy.deepcopy(report)
            altered["resources"][field] = bad
            rehash_report(altered)
            with self.subTest(field=field, bad=bad), self.assertRaises(ValueError):
                validate_episode_report(altered)

    def test_rehashed_report_missing_start_is_rejected(self):
        report = self.completed()
        report["events"].pop(0)
        rehash_events(report)
        with self.assertRaises(ValueError):
            validate_episode_report(report)

    def test_public_storage_api_cannot_write_private_report_inside_git(self):
        report = self.completed()
        with TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            (root / ".git").mkdir()
            output = root / "private"
            output.mkdir(mode=0o700)
            with self.assertRaises(ValueError):
                save_report(output, report)
            self.assertFalse((output / "episode.json").exists())

    def test_public_storage_api_rejects_nonprivate_or_symlink_directory(self):
        report = self.completed()
        with TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            shared = root / "shared"
            shared.mkdir(mode=0o755)
            shared.chmod(0o755)
            with self.assertRaises(ValueError):
                save_report(shared, report)
            private = root / "private"
            private.mkdir(mode=0o700)
            link = root / "link"
            link.symlink_to(private, target_is_directory=True)
            with self.assertRaises(ValueError):
                save_report(link, report)

    def test_private_report_is_created_once_with_owner_only_mode(self):
        report = self.completed()
        with TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            directory = prepare_output(root / "private")
            path = save_report(directory, report)
            self.assertEqual(stat.S_IMODE(directory.stat().st_mode), 0o700)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            with self.assertRaises((FileExistsError, ValueError)):
                save_report(directory, report)
            self.assertEqual(json.loads(path.read_text())["sha256"], report["sha256"])

    def test_action_replay_rejects_duplicate_keys_before_they_are_discarded(self):
        from sle import episode_cli
        with TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            actions = root / "actions.json"
            actions.write_text('[{"action":"experiment","action":"commit","claim":{"prediction":0.5}}]')
            args = SimpleNamespace(list=False, task=self.env.task_id, output_dir=str(root / "private"),
                                   baseline=None, actions=str(actions), program=None, llm_config=None,
                                   seed=0, max_steps=3, wall_seconds=10, analysis="none")
            with patch.object(episode_cli, "source_binding", return_value={"task_id": self.env.task_id}), \
                 patch.object(episode_cli, "create_environment", return_value=self.env), \
                 contextlib.redirect_stdout(io.StringIO()):
                try:
                    result = episode_cli.command(args)
                except ValueError:
                    return
            self.assertNotEqual(result, 0, "replay accepted a duplicate-key action rejected by the live protocol")


class EpisodeAnalysisWorkerTests(unittest.TestCase):
    def test_analysis_only_receives_explicit_public_data_and_persists_scratch(self):
        import sle.episode_analysis_worker as worker
        payload = {"problem": {"public_value": 2}, "history": [], "public_files": {}}
        with patch.object(worker, "_namespace", {"__name__": "test_episode"}):
            first = worker.analyze({**payload, "code": "scratch = problem['public_value'] + 1\nresult = scratch"})
            second = worker.analyze({**payload, "code": "result = scratch + 1"})
        self.assertEqual(first["result"], 3)
        self.assertEqual(second["result"], 4)

    def test_stdout_is_bounded_and_nonfinite_output_returns_fixed_error(self):
        import sle.episode_analysis_worker as worker
        payload = {"problem": {}, "history": [], "public_files": {}}
        with patch.object(worker, "_namespace", {"__name__": "test_episode"}):
            output = worker.analyze({**payload, "code": "print('x' * 200000)\nresult = 1"})
            failed = worker.analyze({**payload, "code": "result = float('nan')"})
        self.assertLessEqual(len(output["stdout"]), 64000)
        self.assertEqual(output["result"], 1)
        self.assertFalse(failed["ok"])
        self.assertEqual(failed["error"], "ValueError")


if __name__ == "__main__":
    unittest.main()

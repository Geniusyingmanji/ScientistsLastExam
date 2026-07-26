from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path

from frontier_science.algorithms.evolve import _build_prompt
from frontier_science.metric_visibility import score_only_metrics, search_visible_metrics
from frontier_science.protocol import sha256_text
from frontier_science.registry import find_task


ROOT = Path(__file__).resolve().parents[1]


def _module():
    path = ROOT / "scripts/analyze_feedback_measurement_pilot.py"
    spec = importlib.util.spec_from_file_location(
        "feedback_measurement_analysis_test", path,
    )
    if spec is None or spec.loader is None:
        raise ImportError("cannot load feedback measurement analysis")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MODULE = _module()


def _fixture(mode):
    spec = find_task("DynamicalSystems/ActiveLawDiscovery", include_uncertified=True)
    baseline = spec.initial_program_path.read_text(encoding="utf-8")
    sources = {
        0: baseline,
        1: baseline + "\n# proposal one\n",
        2: baseline + "\n# proposal two\n",
        3: baseline + "\n# proposal three\n",
    }
    scores = [0.1, 0.4, 0.3, 0.5]
    events = []
    best = -1.0
    for step, score in enumerate(scores):
        best = max(best, score)
        event = {
            "schema_version": 2,
            "step": step,
            "oracle_calls": step + 1,
            "budget_units": step + 1,
            "score": score,
            "best_score": best,
            "valid": True,
            "accepted": step in (0, 1, 3),
            "wall_seconds": 1.0,
            "cumulative_wall_seconds": float(step + 1),
            "candidate_sha256": sha256_text(sources[step]),
            "parent_sha256": None,
            "metrics": {
                "combined_score": score,
                "valid": 1.0,
                "feasibility_rate": 1.0,
                "raw_score": score,
                "mechanism_score": score / 2,
                "development_prediction_score": score / 2,
                "validation_prediction_score": score / 2,
                "robustness_score": score / 2,
                "development_false_discoveries": 0,
                "validation_false_discoveries": 0,
                "development_correct_abstentions": 1,
                "validation_correct_abstentions": 1,
            },
            "llm": {} if step == 0 else {
                "input_tokens": 10, "output_tokens": 5, "total_tokens": 15,
            },
            "algorithm_metadata": {},
            "error": None,
        }
        events.append(event)
    policy = (
        "offline_best_of_open_loop_batch" if mode == "selection_blind"
        else "delayed_online_parent_offline_final_best" if mode == "delayed_replay"
        else "online_incumbent"
    )
    semantics = (
        "offline_best_update" if mode == "selection_blind"
        else "observer_best_update_not_immediate_parent_release" if mode == "delayed_replay"
        else "online_incumbent_update"
    )
    for event in events[1:]:
        step = event["step"]
        parent_step, released, metrics = MODULE._expected_prompt_state(events, mode, step)
        source = sources[parent_step]
        rendered = json.dumps(metrics, indent=2)
        prompt = _build_prompt(
            spec, source, metrics, proposal_slot=step, proposal_budget=3,
        )
        event["parent_sha256"] = sha256_text(source)
        event["algorithm_metadata"] = {
            "selection_policy": policy,
            "accepted_semantics": semantics,
            "proposal_slot": step,
            "prompt_source_step": parent_step,
            "feedback_released_through_step": released,
            "prompt_sha256": sha256_text(prompt),
            "prompt_utf8_bytes": len(prompt.encode("utf-8")),
            "prompt_program_utf8_bytes": len(source.encode("utf-8")),
            "prompt_metrics_sha256": sha256_text(rendered),
            "prompt_metrics_utf8_bytes": len(rendered.encode("utf-8")),
            "prompt_metric_keys": ",".join(sorted(metrics)),
        }
    checkpoint = {
        "evaluated_candidates": [
            {
                "step": step,
                "program": source,
                "sha256": sha256_text(source),
                "score": scores[step],
                "valid": True,
                "metrics": search_visible_metrics(events[step]["metrics"]),
            }
            for step, source in sources.items()
        ]
    }
    return spec, events, checkpoint


class FeedbackMeasurementAnalysisTests(unittest.TestCase):
    def test_observer_best_step_is_strict_and_first_on_ties(self):
        _, events, _ = _fixture("normal")
        events[3]["score"] = events[1]["score"]
        self.assertEqual(MODULE._observer_best_step(events, 3), 1)

    def test_all_four_lineage_and_prompt_contracts_reconstruct(self):
        expected_parents = {
            "normal": [0, 1, 1],
            "score_only": [0, 1, 1],
            "delayed_replay": [0, 0, 1],
            "selection_blind": [0, 0, 0],
        }
        for mode, parents in expected_parents.items():
            with self.subTest(mode=mode):
                spec, events, checkpoint = _fixture(mode)
                report = MODULE._validate_lineage_and_prompts(
                    events, checkpoint, spec, mode, 3,
                )
                self.assertEqual(
                    [row["parent_step"] for row in report["prompt_records"]],
                    parents,
                )
                if mode == "score_only":
                    self.assertTrue(all(
                        row["prompt_metric_keys"] == "combined_score"
                        for row in report["prompt_records"]
                    ))

    def test_prompt_or_parent_mutation_fails_closed(self):
        spec, events, checkpoint = _fixture("selection_blind")
        events[2]["algorithm_metadata"]["prompt_utf8_bytes"] += 1
        with self.assertRaisesRegex(ValueError, "prompt/lineage"):
            MODULE._validate_lineage_and_prompts(
                events, checkpoint, spec, "selection_blind", 3,
            )

        spec, events, checkpoint = _fixture("normal")
        events[2]["parent_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "parent source"):
            MODULE._validate_lineage_and_prompts(
                events, checkpoint, spec, "normal", 3,
            )

    def test_common_token_horizon_excludes_unfinished_call(self):
        records = []
        for mode, total in zip(MODULE.EXPECTED_MODES, (45, 60, 75, 90)):
            _, events, _ = _fixture(mode)
            per_call = total // 3
            for event in events[1:]:
                event["llm"] = {
                    "input_tokens": per_call - 5,
                    "output_tokens": 5,
                    "total_tokens": per_call,
                }
            records.append({
                "task": "DynamicalSystems/ActiveLawDiscovery",
                "replicate_id": 0,
                "condition": mode,
                "total_tokens": total,
                "events": events,
            })
        groups = MODULE._token_horizon_records(records)
        self.assertEqual(groups[0]["common_total_token_horizon"], 45)
        cells = {row["condition"]: row for row in groups[0]["cells"]}
        self.assertEqual(cells["normal"]["selected_step"], 3)
        self.assertEqual(cells["selection_blind"]["selected_step"], 1)

    def test_score_only_fixture_has_only_scalar_feedback(self):
        _, events, _ = _fixture("score_only")
        for step in range(1, 4):
            parent, _, metrics = MODULE._expected_prompt_state(
                events, "score_only", step,
            )
            self.assertEqual(metrics, score_only_metrics(events[parent]["metrics"]))


if __name__ == "__main__":
    unittest.main()

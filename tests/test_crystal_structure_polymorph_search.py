import importlib.util
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT / "benchmarks/Chemistry/CrystalStructurePolymorphSearch"


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_baseline_and_reference_are_deterministic_anchors():
    evaluator = _load(TASK / "verification/evaluator.py", "csp_eval_anchor")
    baseline = _load(TASK / "solution.py", "csp_baseline")
    reference = _load(TASK / "verification/reference_multistart.py", "csp_reference")
    first = evaluator.evaluate(baseline.search_crystals)
    second = evaluator.evaluate(baseline.search_crystals)
    witness = evaluator.evaluate(reference.search_crystals)
    assert first == second
    assert first["valid"] == 1.0
    assert first["combined_score"] == 0.0
    assert witness["valid"] == 1.0
    assert abs(witness["combined_score"] - 1.0) < 1e-12
    assert abs(witness["heldout_policy_score"] - 1.0) < 1e-12


def test_periodic_energy_is_common_translation_invariant():
    evaluator = _load(TASK / "verification/evaluator.py", "csp_eval_periodic")
    world = evaluator.WORLDS[0]
    seed = evaluator._baseline_seed(world, 0)
    lengths = np.asarray(seed["cell_lengths"])
    coords = np.asarray(seed["fractional_coordinates"])
    shifted = (coords + np.asarray([0.231, 0.417, 0.119])) % 1.0
    assert abs(evaluator._enthalpy(world, lengths, coords) -
               evaluator._enthalpy(world, lengths, shifted)) < 1e-10


def test_malformed_candidates_score_zero_without_crashing():
    evaluator = _load(TASK / "verification/evaluator.py", "csp_eval_bad")

    def empty(_problem, _callback):
        return {}

    def collision(problem, callback):
        n = problem["atom_count"]
        try:
            callback({"cell_lengths": [2.2, 2.2, 2.2],
                      "fractional_coordinates": [[0.0, 0.0, 0.0]] * n})
        except ValueError:
            pass
        return {"candidate_ids": ["invented-a", "invented-b", "invented-c"]}

    def overrun(problem, callback):
        seed = _load(TASK / "solution.py", "csp_bad_seed")._seed(problem, 0)
        rows = []
        for _ in range(evaluator.CALL_BUDGET + 1):
            try:
                rows.append(callback(seed))
            except ValueError:
                pass
        return {"candidate_ids": [row["candidate_id"] for row in rows[:3]]}

    for candidate in (empty, collision, overrun):
        result = evaluator.evaluate(candidate)
        assert result["valid"] == 0.0
        assert result["combined_score"] == 0.0


def test_world_boundary_resets_candidate_session():
    evaluator = _load(TASK / "verification/evaluator.py", "csp_eval_reset")

    class SessionProbe:
        def __init__(self):
            self.resets = 0
            self.calls_in_session = 99

        def reset_session(self):
            self.resets += 1
            self.calls_in_session = 0

        def __call__(self, problem, callback):
            self.calls_in_session += 1
            assert self.calls_in_session == 1
            return {}

    probe = SessionProbe()
    for index, world in enumerate(evaluator.WORLDS):
        evaluator._evaluate_world(probe, world, index)
        assert probe.calls_in_session == 1
    assert probe.resets == len(evaluator.WORLDS)


def test_malformed_submission_matrix_and_caught_overrun_fail_closed(monkeypatch):
    evaluator = _load(TASK / "verification/evaluator.py", "csp_eval_contract")
    world = evaluator.WORLDS[0]
    seed = evaluator._baseline_seed(world, 0)
    # The expensive minimizer is irrelevant to the submission and charged-state checks.
    monkeypatch.setattr(evaluator, "_relax", lambda world, structure: (seed, -1.0))
    malformed = [None, False, 1, "bad", [], {}, {"extra": []},
                 {"candidate_ids": None}, {"candidate_ids": "abc"},
                 {"candidate_ids": []}, {"candidate_ids": [1, 2, 3]},
                 {"candidate_ids": ["a", "a", "a"]},
                 {"candidate_ids": ["a", "b", "c"]},
                 {"candidate_ids": ["a", "b", "c"], "extra": 1}]
    for answer in malformed:
        row = evaluator._evaluate_world(lambda p, cb: answer, world, 0)
        assert not row["valid"]
        assert row["failure_kind"] == "invalid_submission"

    def overrun(problem, callback):
        rows = [callback(seed) for _ in range(evaluator.CALL_BUDGET)]
        try:
            callback(seed)
        except ValueError:
            pass
        return {"candidate_ids": [row["candidate_id"] for row in rows[:3]]}

    row = evaluator._evaluate_world(overrun, world, 0)
    assert not row["valid"]
    assert row["failure_kind"] == "budget_exceeded"
    assert row["calls"] == evaluator.CALL_BUDGET

def test_real_sandbox_resets_globals_and_tmp_between_worlds(tmp_path):
    import shutil
    import sys
    import pytest
    if sys.platform != "linux" or not shutil.which("bwrap"):
        pytest.skip("requires the canonical Linux bubblewrap runtime")
    from sle.evaluate import evaluate_candidate
    from sle.registry import find_task

    code = (TASK / "solution.py").read_text().replace(
        "def search_crystals(", "def baseline_search(")
    code += '''\n_seen = 0

def search_crystals(problem, relax_structure):
    global _seen
    from pathlib import Path
    marker = Path("/tmp/csp-world-sentry")
    _seen += 1
    if _seen != 1 or marker.exists():
        return {}
    marker.write_text("one world")
    return baseline_search(problem, relax_structure)
'''
    candidate = tmp_path / "session_sentry.py"
    candidate.write_text(code)
    spec = find_task("MaterialsScience/CrystalStructurePolymorphSearch", include_uncertified=True)
    metrics = evaluate_candidate(spec, candidate, timeout_s=300)
    assert not metrics.get("infrastructure_failure"), metrics
    assert metrics["valid"] == 1.0, metrics
    assert metrics["combined_score"] == 0.0
    assert len(metrics["per_world"]) == 5
    assert all(row["valid"] for row in metrics["per_world"])

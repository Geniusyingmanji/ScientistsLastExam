"""Regression checks for the four PR #22 candidate contracts.

These are local oracle tests; actual candidate isolation is tested on Linux.
"""

import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
TASKS = (
    ("Biology", "HodgkinHuxleyCurrentID"),
    ("Chemistry", "ChronoamperometryLawID"),
    ("Chemistry", "MassFragmentationTree"),
    ("Chemistry", "ThermochemicalCycleAudit"),
)


def load_task(discipline, name):
    path = ROOT / "benchmarks" / discipline / name / "verification/evaluator.py"
    spec = importlib.util.spec_from_file_location("review_" + name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def null_submission(name, problem):
    if name == "ThermochemicalCycleAudit":
        return {"verdict": "underdetermined", "flagged_measurements": [],
                "drift_instrument": "", "confidence": 0.5,
                "corrected_enthalpies": {r["id"]: r["value_kj_per_mol"]
                                         for r in problem["measurements"]}}
    result = {"abstain": True, "confidence": 0.5}
    if name == "MassFragmentationTree":
        result.update(nodes=[], edges=[])
    else:
        result["parameters"] = None
    if name == "ChronoamperometryLawID":
        result["family_probabilities"] = {f: 1 / len(problem["families"])
                                          for f in problem["families"]}
    return result


@pytest.mark.parametrize("discipline,name", TASKS)
def test_full_refusal_is_valid_and_zero(discipline, name):
    ev = load_task(discipline, name)
    result = ev.evaluate(lambda problem, *args: null_submission(name, problem))
    assert result["valid"] == 1.0
    assert result["combined_score"] == 0.0
    assert result["robustness_score"] == 0.0
    assert result["discovery_attempt_count"] == 0
    assert result["development_false_discovery_rate"] == 0.0


@pytest.mark.parametrize("discipline,name", TASKS)
def test_invalid_outputs_do_not_count_as_scientific_attempts(discipline, name):
    ev = load_task(discipline, name)
    result = ev.evaluate(lambda *args: {})
    assert result["valid"] == 0.0
    assert result["combined_score"] == 0.0
    assert result["discovery_attempt_count"] == 0
    assert result["development_discovery_coverage"] == 0.0


@pytest.mark.parametrize("discipline,name", TASKS)
def test_caught_overspending_still_invalidates_submission(discipline, name):
    ev = load_task(discipline, name)

    def candidate(problem, *args):
        query, budget = args[0], args[-1]
        parameters = {"HodgkinHuxleyCurrentID": (0.0, 5.0),
                      "ChronoamperometryLawID": (0.5,),
                      "MassFragmentationTree": (20.0,),
                      "ThermochemicalCycleAudit": ("R01",)}[name]
        for _ in range(budget + 1):
            try:
                query(*parameters)
            except Exception:
                pass
        return null_submission(name, problem)

    result = ev.evaluate(candidate)
    assert result["valid"] == 0.0
    assert result["combined_score"] == 0.0
    assert result["robustness_score"] == 0.0


@pytest.mark.parametrize("discipline,name", TASKS)
def test_malformed_candidate_battery(discipline, name):
    ev = load_task(discipline, name)

    def raises(*args):
        raise RuntimeError("malformed candidate")

    candidates = [raises]
    candidates.extend(lambda *args, value=value: value
                      for value in (None, {}, [], "junk", 42, False))
    for confidence in (None, float("nan"), float("inf"), -0.1, 1.1, []):
        def malformed(problem, *args, confidence=confidence):
            output = null_submission(name, problem)
            output["confidence"] = confidence
            return output
        candidates.append(malformed)
    for candidate in candidates:
        result = ev.evaluate(candidate)
        assert result["valid"] == 0.0
        assert result["combined_score"] == 0.0


@pytest.mark.parametrize("discipline,name", TASKS)
def test_published_rate_denominators_reconstruct_counts(discipline, name):
    ev = load_task(discipline, name)
    result = ev.evaluate(lambda problem, *args: null_submission(name, problem))
    if name == "ThermochemicalCycleAudit":
        fdr_den = result["false_discovery_world_count"]
        refusal_den = result["refusing_world_count"]
    else:
        fdr_den = refusal_den = result["unsupported_world_count"]
    assert result["development_false_discovery_rate"] * fdr_den == result["false_discovery_count"]
    assert result["development_correct_refusal_rate"] * refusal_den == result["correct_refusal_count"]

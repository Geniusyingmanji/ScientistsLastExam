from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest


ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT / "benchmarks" / "EarthScience" / "ChronologyAssimilation"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _modules(suffix: str):
    evaluator = _load(TASK / "verification" / "evaluator.py", "chronology_ev_" + suffix)
    baseline = _load(TASK / "solution.py", "chronology_base_" + suffix)
    reference = _load(TASK / "verification" / "reference_solver.py", "chronology_ref_" + suffix)
    return evaluator, baseline, reference


def test_baseline_and_reference_are_deterministic_and_separated():
    evaluator, baseline, reference = _modules("scores")
    first = evaluator.evaluate(baseline.reconstruct_climate)
    second = evaluator.evaluate(baseline.reconstruct_climate)
    witness = evaluator.evaluate(reference.reconstruct_climate)
    assert first["valid"] == 1.0
    assert first["combined_score"] == 0.0
    assert json.dumps(first, sort_keys=True, default=str) == json.dumps(second, sort_keys=True, default=str)
    assert witness["combined_score"] > 0.5
    assert witness["development_false_discovery_rate"] == 0.0
    assert witness["development_correct_refusal_rate"] == 1.0


def _collapsed_candidate(reference, mode):
    def candidate(grid, catalog, lab, budget):
        answer = dict(reference.reconstruct_climate(grid, catalog, lab, budget))
        if answer.get("abstain"):
            return answer
        curves = np.asarray(answer["sample_ages_years"], dtype=float)
        collapsed = []
        if mode == "affine":
            for row, curve in zip(catalog, curves):
                nominal = np.asarray(row["nominal_age_years"], dtype=float)
                fitted = np.polyval(np.polyfit(nominal, curve, 1), nominal)
                collapsed.append(np.maximum.accumulate(np.clip(fitted, grid[0], grid[-1])))
        else:
            knots = np.linspace(grid[0], grid[-1], 3)
            sampled_warps = []
            for row, curve in zip(catalog, curves):
                nominal = np.asarray(row["nominal_age_years"], dtype=float)
                sampled_warps.append(np.interp(knots, nominal, curve) - knots)
            shared_warp = np.mean(sampled_warps, axis=0)
            for row, curve in zip(catalog, curves):
                nominal = np.asarray(row["nominal_age_years"], dtype=float)
                base = nominal + np.interp(nominal, knots, shared_warp)
                fitted = base + np.mean(curve - base)
                collapsed.append(np.maximum.accumulate(np.clip(fitted, grid[0], grid[-1])))
        answer["sample_ages_years"] = np.asarray(collapsed)
        return answer
    return candidate


def test_affine_and_shared_knot_shortcuts_remain_below_reference():
    evaluator, _, reference = _modules("shortcut")
    full = evaluator.evaluate(reference.reconstruct_climate)
    affine = evaluator.evaluate(_collapsed_candidate(reference, "affine"))
    shared = evaluator.evaluate(_collapsed_candidate(reference, "shared"))
    assert affine["combined_score"] < full["combined_score"]
    assert shared["combined_score"] < full["combined_score"]


def test_chronology_artifact_is_monotone_and_beats_a_constant_offset():
    evaluator, _, reference = _modules("artifact")
    world = evaluator._world(evaluator.DEVELOPMENT_SPECS[0])
    truth = np.asarray(world["true_ages"])
    nominal = np.array([row["nominal_age_years"] for row in world["catalog"]])
    offsets = np.median(truth - nominal, axis=1)
    lab = evaluator._DatingLab(world)
    answer = reference.reconstruct_climate(
        evaluator.TIME_GRID, evaluator._public_catalog(world), lab.date_sample, evaluator.BUDGET_UNITS
    )
    curves = evaluator._validate(answer)[2]
    assert curves.shape == (8, 36)
    assert np.all(np.diff(curves, axis=1) >= 0.0)
    assert np.mean(np.abs(curves - truth)) < np.mean(np.abs(truth - nominal - offsets[:, None]))


def test_malformed_and_caught_bad_dating_calls_fail_closed():
    evaluator, _, _ = _modules("invalid")
    for value in (None, {}, "", True, 12, [], {"abstain": "yes"}):
        result = evaluator.evaluate(lambda *args, value=value, **kwargs: value)
        assert result["valid"] == 0.0
        assert result["combined_score"] == 0.0

    def bad_date(grid, catalog, lab, budget):
        del grid, catalog, budget
        try:
            lab(0, ["not an index"])
        except (TypeError, ValueError):
            pass
        return {"temperature_mean": [], "temperature_std": [], "age_offsets_years": [],
                "confidence": 0.0, "abstain": True}

    assert evaluator.evaluate(bad_date)["valid"] == 0.0


def test_joint_chronology_beats_date_only_interpolation_on_shape():
    evaluator, _, reference = _modules('joint_shape')
    full = evaluator.evaluate(reference.reconstruct_climate)
    reduced = evaluator.evaluate(lambda *a: reference.solve(*a, joint=False))
    assert reduced['valid'] == 1.0
    assert full['development_age_increment_mae_years'] < .6 * reduced['development_age_increment_mae_years']
    assert full['combined_score'] > reduced['combined_score'] + .15


def test_correct_endpoints_do_not_hide_wrong_internal_accumulation():
    evaluator, _, _ = _modules('endpoints')
    spec = evaluator.DEVELOPMENT_SPECS[0]
    world = evaluator._world(spec)
    true_ages = np.asarray(world['true_ages'])
    def candidate(grid, catalog, lab, budget):
        wrong = np.asarray([np.linspace(a[0], a[-1], len(a)) for a in true_ages])
        return {'temperature_mean': world['climate'], 'temperature_std': np.full_like(grid, .04),
                'sample_ages_years': wrong, 'abstain': False, 'confidence': .8}
    row = evaluator._evaluate_world(candidate, spec, 'development', 0)
    assert row['valid']
    assert row['age_increment_mae_years'] > 5.
    assert row['mechanism_score'] < .7


@pytest.mark.parametrize('exception', [SystemExit, KeyboardInterrupt])
def test_direct_diagnostic_base_exceptions_fail_closed(exception):
    evaluator, _, _ = _modules('base_exception')
    def candidate(*args):
        raise exception()
    result = evaluator.evaluate(candidate)
    assert result['valid'] == 0.
    assert result['combined_score'] == 0.

"""Numerical correctness and spatial-search regressions for PR20 FWI."""
import importlib.util
from pathlib import Path

import numpy as np
import pytest
from fwi_test_support import reference_result

ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT / "benchmarks/EarthScience/ActiveFullWaveformInversion"


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_batched_forward_and_tangent_match_independent_oracle():
    oracle = load(TASK / "verification/evaluator.py", "tangent_oracle")
    reference = load(TASK / "verification/reference_solver.py", "tangent_reference")
    rng = np.random.default_rng(823)
    velocity = oracle._background() + rng.uniform(-200.0, 200.0, oracle.GRID_SHAPE)
    sources = [3, 15, 28]
    model = reference._Acoustic(oracle.GRID_SHAPE, oracle.SPACING_M,
                               np.arange(oracle.N_TIME) * oracle.DT_S, sources,
                               oracle.RECEIVER_X_M)
    expected = np.asarray([oracle.simulate_waveforms(velocity, s) for s in sources])
    np.testing.assert_allclose(model.forward(velocity), expected, atol=1e-12, rtol=1e-12)
    # Include dense random and boundary-localized directions; the latter catches
    # mistakes in the damped stencil's boundary and source-injection derivatives.
    directions = rng.normal(size=(*oracle.GRID_SHAPE, 3))
    directions[:, :, 2] = 0.0
    directions[1:4, 2:5, 2] = 1.0
    prediction, jacobian = model.jacobian(velocity, directions.reshape((-1, 3)))
    np.testing.assert_allclose(prediction, expected, atol=1e-12, rtol=1e-12)
    step = 0.01
    for i in range(3):
        plus = np.asarray([oracle.simulate_waveforms(velocity + step * directions[:, :, i], s)
                           for s in sources])
        minus = np.asarray([oracle.simulate_waveforms(velocity - step * directions[:, :, i], s)
                            for s in sources])
        numerical = (plus - minus) / (2 * step)
        relative_error = np.linalg.norm(jacobian[:, :, :, i] - numerical) / np.linalg.norm(numerical)
        assert relative_error < 1e-6


def test_spatial_probe_propagation_matches_oracle():
    oracle = load(TASK / "verification/evaluator.py", "spatial_probe_oracle")
    probe = load(ROOT / ".research/pr20_fwi_spatial_probe.py", "spatial_probe_forward")
    models = np.asarray([oracle._background(), oracle._world(oracle.DEVELOPMENT_SPECS[0])["velocity"]])
    sources = [3, 15, 28]
    expected = np.asarray([[oracle.simulate_waveforms(v, s) for s in sources] for v in models])
    actual = probe.simulate(models, sources, oracle.SPACING_M,
                            np.arange(oracle.N_TIME) * oracle.DT_S, oracle.RECEIVER_X_M)
    np.testing.assert_allclose(actual, expected, atol=1e-12, rtol=1e-12)


def test_paired_velocity_controls_have_independent_reproducible_noise():
    oracle = load(TASK / "verification/evaluator.py", "independent_noise_oracle")
    seed = 41023
    worlds = [oracle._world((seed, kind, 2))
              for kind in ("supported", "structured_attenuation")]
    np.testing.assert_array_equal(worlds[0]["velocity"], worlds[1]["velocity"])
    standardized = []
    for world, attenuation in zip(worlds, (0.0, worlds[1]["attenuation"])):
        a = oracle._Acquisition(world).acquire(15)
        b = oracle._Acquisition(world).acquire(15)
        np.testing.assert_array_equal(a["pressure"], b["pressure"])
        clean = oracle.simulate_waveforms(world["velocity"], 15, 12.0, attenuation)
        standardized.append((a["pressure"] - clean).ravel() / a["noise_std"])
    # The previous implementation reused exactly the same normal draws.
    assert abs(np.corrcoef(standardized)[0, 1]) < 0.10
    assert not np.allclose(standardized[0], standardized[1])


def test_worlds_cover_deep_structure_without_reusing_split_seeds():
    oracle = load(TASK / "verification/evaluator.py", "world_diversity_oracle")
    dev_seeds = {s[0] for s in oracle.DEVELOPMENT_SPECS}
    hold_seeds = {s[0] for s in oracle.HELDOUT_SPECS}
    assert not dev_seeds & hold_seeds
    for specs in (oracle.DEVELOPMENT_SPECS, oracle.HELDOUT_SPECS):
        supported = [s for s in specs if s[1] == "supported"]
        assert len(supported) >= 10
        assert list(specs[:len(supported)]) == supported
        for spec in supported:
            correction = oracle._world(spec)["velocity"] - oracle._background()
            # A blanket deep-background prior must actually discard signal.
            assert np.linalg.norm(correction[14:]) > .15 * np.linalg.norm(correction)


@pytest.mark.parametrize("kind", ["null", "misspecified", "structured_attenuation"])
def test_unsupported_structure_and_responses_vary_with_seed(kind):
    oracle = load(TASK / "verification/evaluator.py", "unsupported_diversity_oracle")
    worlds = [oracle._world((seed, kind, 2)) for seed in (81013, 81017, 81019)]
    traces = [oracle._Acquisition(w).acquire(15)["pressure"] for w in worlds]
    for i in (1, 2):
        assert not np.array_equal(worlds[0]["velocity"], worlds[i]["velocity"])
        assert not np.array_equal(traces[0], traces[i])
    if kind == "null":
        # The nuisance structure is a near-null rather than an identical grid.
        assert all(np.std(w["velocity"] - oracle._background()) < 1 for w in worlds)
    else:
        assert all(np.std(w["velocity"] - oracle._background()) > 100 for w in worlds)


def test_near_null_is_below_joint_not_just_per_sample_noise():
    oracle = load(TASK / "verification/evaluator.py", "joint_null_oracle")
    cases = [s for s in oracle.DEVELOPMENT_SPECS + oracle.HELDOUT_SPECS if s[1] == "null"]
    cases += [(61201, "null", 0), (71201, "null", 0)]
    for spec in cases:
        world = oracle._world(spec)
        distances = []
        for source in oracle.SOURCE_INDICES:
            clean = oracle.simulate_waveforms(world["velocity"], int(source))
            background = oracle.simulate_waveforms(oracle._background(), int(source))
            sigma = world["noise"] * max(float(np.std(clean)), 1e-8)
            distances.append(float(np.sum(((clean-background)/sigma)**2)))
        # Independent repeats of the most informative source upper-bound any
        # allowed three-shot sequence. This is a conditional waveform separation
        # using the stated noise, not a claim about all possible side information.
        assert oracle.BUDGET_UNITS * max(distances) < .001


def test_continuous_probe_forward_is_independent_and_correct():
    oracle = load(TASK / "verification/evaluator.py", "continuous_forward_oracle")
    probe = load(ROOT / ".research/pr20_fwi_continuous_probe.py", "continuous_forward")
    models = np.asarray([oracle._world(oracle.DEVELOPMENT_SPECS[0])["velocity"]])
    sources = [3, 15, 28]
    actual = probe.simulate(models, sources, oracle.SPACING_M,
                            np.arange(oracle.N_TIME) * oracle.DT_S, oracle.RECEIVER_X_M)
    expected = np.asarray([[oracle.simulate_waveforms(v, s) for s in sources] for v in models])
    np.testing.assert_allclose(actual, expected, atol=1e-12, rtol=1e-12)


@pytest.mark.parametrize("sources,budget,expected", [
    ([3, 9, 15, 21, 28], 3, [9, 15, 21]),
    ([3, 9, 15, 21, 28], 1, [15]),
    ([3, 28], 2, [3, 28]), ([9, 21], 2, [9, 21]), ([28], 1, [28]),
])
def test_reference_preserves_explicit_source_subsets(sources, budget, expected):
    oracle = load(TASK / "verification/evaluator.py", "source_policy_oracle")
    reference = load(TASK / "verification/reference_solver.py", "source_policy_reference")
    calls = []

    def acquire(source):
        calls.append(source)
        if len(calls) == len(expected):
            raise RuntimeError("stop before the expensive inversion")
        return {}

    with pytest.raises(RuntimeError, match="stop before"):
        reference.invert_velocity_model(
            oracle.GRID_SHAPE, oracle.SPACING_M, oracle._background(), oracle.VELOCITY_BOUNDS,
            np.asarray(sources), oracle.RECEIVER_X_M, np.arange(oracle.N_TIME)*oracle.DT_S,
            acquire, budget)
    assert calls == expected


@pytest.fixture(scope="module")
def reference_metrics():
    return reference_result()


@pytest.mark.parametrize("refine,threshold,lenses", [(False, 0.12, 1), (False, 0.24, 1), (True, 0.20, 1), (False, 0.20, 2), (False, 0.20, 3)])
def test_spatial_search_is_below_reference_on_both_splits(reference_metrics, refine, threshold, lenses):
    oracle = load(TASK / "verification/evaluator.py", "spatial_comparison_oracle")
    probe = load(ROOT / ".research/pr20_fwi_spatial_probe.py", "spatial_comparison_probe")
    probe.REFINE = refine
    probe.THRESHOLD = threshold
    probe.LENSES = lenses
    result = oracle.evaluate(probe.invert_velocity_model)
    assert result["valid"] == 1.0
    # Spatial degrees of freedom are essential here: the earlier regression only
    # swept a fixed lens's amplitude. Require a margin on BOTH evaluation splits.
    for metric in ("combined_score", "robustness_score"):
        assert reference_metrics[metric] > result[metric] + 0.15
        assert result[metric] < 0.7 * reference_metrics[metric]


@pytest.mark.parametrize("lenses,stop,depth", [(1, 0, 1), (3, 0, 1), (5, 5, 1), (5, 5, .7)])
def test_continuous_gaussian_search_is_below_reference(reference_metrics, lenses, stop, depth):
    oracle = load(TASK / "verification/evaluator.py", "continuous_comparison_oracle")
    probe = load(ROOT / ".research/pr20_fwi_continuous_probe.py", "continuous_comparison")
    probe.LENSES, probe.STOP_NOISE, probe.DEPTH_CAP = lenses, stop, depth
    result = oracle.evaluate(probe.invert_velocity_model)
    assert result["valid"] == 1.0
    for metric in ("combined_score", "robustness_score"):
        assert reference_metrics[metric] > result[metric] + .15
        assert result[metric] < .7 * reference_metrics[metric]

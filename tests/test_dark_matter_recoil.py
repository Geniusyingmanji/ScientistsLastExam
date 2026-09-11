"""Scientific and adversarial invariants for ParticlePhysics/DarkMatterRecoilAttribution."""
import importlib.util
import math
import platform
from pathlib import Path
import numpy as np
import pytest
from scipy.integrate import quad
from sle.metric_visibility import search_visible_metrics
ROOT = Path(__file__).resolve().parents[1]

def load(path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
MODULE = load(ROOT / 'benchmarks/Physics/DarkMatterRecoilAttribution/verification/evaluator.py')


def test_public_detector_design_is_identical_across_worlds_and_splits():
    problems = [w['problem'] for split in MODULE.SPLIT_SEEDS for w in MODULE.split_worlds(split)]
    problems.extend(MODULE.make_world(seed, kind)['problem']
                    for seed in range(20) for kind in (*MODULE.LAWS, 'none', 'unsupported'))
    assert all(problem == problems[0] for problem in problems)


@pytest.mark.parametrize('failing_split', ['development', 'heldout'])
def test_public_validity_does_not_reveal_heldout_validation(monkeypatch, failing_split):
    original = MODULE.score_world
    affected = {w['seed'] for w in MODULE.split_worlds(failing_split)}
    baseline = search_visible_metrics(MODULE.evaluate(lambda *_: {'abstain': True}))

    def reject_selected(world, answer):
        # Trusted fault injection; no split identifier is given to the candidate.
        return original(world, {} if world['seed'] in affected else answer)

    monkeypatch.setattr(MODULE, 'score_world', reject_selected)
    result = MODULE.evaluate(lambda *_: {'abstain': True})
    assert result[failing_split+'_valid_rate'] == 0
    assert result[failing_split+'_correct_refusal_count'] == 0
    if failing_split == 'heldout':
        assert search_visible_metrics(result) == baseline
    else:
        assert result['valid'] == result['feasibility_rate'] == 0


def test_recoil_kernel_matches_independent_speed_integral():
    (mass, ratio, t, energy) = (43.0, 0.83, 1, MODULE.ENERGIES)
    (_, a, z) = MODULE.TARGETS[t]
    nucleus = 0.9315 * a
    reduced = mass * nucleus / (mass + nucleus)
    for j in (0, 8, 17):
        q = math.sqrt(2 * nucleus * energy[j] * 1e-06)
        threshold = 299792.458 * q / (2 * reduced)
        speed = MODULE.SPEEDS[1]
        integral = quad(lambda v: 4 / math.sqrt(math.pi) * v / speed ** 3 * math.exp(-(v / speed) ** 2), threshold, 15 * speed, epsabs=1e-14)[0]
        eta = integral * 260 * math.sqrt(math.pi) / 2
        form = math.exp(-(q * 1.2 * a ** (1 / 3) / 0.1973269804) ** 2 / 3)
        want = MODULE.bin_widths(energy)[j] * ((z + (a - z) * ratio) / 100) ** 2 * form * (q / 0.05) ** 2 * eta
        assert MODULE.recoil_kernel(mass, ratio, 2, t, energy)[j, 1] == pytest.approx(want, rel=1e-08)

def test_recoil_q2_is_rate_factor_and_target_sensitive():
    for (t, (_, a, _)) in enumerate(MODULE.TARGETS):
        base = MODULE.recoil_kernel(50, 1, 0, t, MODULE.ENERGIES)
        dependent = MODULE.recoil_kernel(50, 1, 2, t, MODULE.ENERGIES)
        assert np.allclose(dependent / base, (2 * 0.9315 * a * MODULE.ENERGIES * 1e-06 / 0.05 ** 2)[:, None])
    assert not np.allclose(MODULE.recoil_kernel(40, 1, 0, 0, MODULE.ENERGIES), MODULE.recoil_kernel(40, 1, 0, 2, MODULE.ENERGIES))

def test_counter_seeded_batch_and_query_order_equivalence():
    w = MODULE.make_world(23, 'q2')
    (a, b) = (MODULE.Campaign(w), MODULE.Campaign(w))
    batch = a({'target': 0, 'units': 2})
    first = b({'target': 0, 'units': 1})
    b({'target': 2, 'units': 1})
    second = b({'target': 0, 'units': 1})
    for key in ('counts', 'background_counts', 'calibration_counts'):
        assert np.array_equal(np.array(batch[key]), np.array(first[key]) + second[key])
    assert first != second
BAD = [None, {}, [], 'model', {'abstain': 1}, {'confidence': float('nan')}, {'model': []}, {'model': 'invalid'}, {'abstain': False, 'confidence': True}, {'abstain': True, 'confidence': float('inf')}, {'abstain': True, 'confidence': -1}, {'model': 'contact', 'mass_gev': float('nan')}, {'model': 'q2', 'mass_gev': True}, {'model': 'contact', 'mass_gev': 9.9}]

@pytest.mark.parametrize('answer', BAD)
def test_malformed_answers_do_not_crash_or_gain_refusal_credit(answer):
    result = MODULE.evaluate(lambda *args: answer)
    assert result['combined_score'] == result['valid'] == 0
    assert result['development_correct_refusal_rate'] == 0
    assert all((not r['valid'] for r in result['per_instance']))

def test_exceptions_are_sanitized():

    def candidate(*args):
        raise RuntimeError('candidate-controlled-token-do-not-echo')
    result = MODULE.evaluate(candidate)
    assert result['valid'] == result['combined_score'] == 0
    assert 'candidate-controlled' not in str(result)

def test_caught_overbudget_is_sticky():

    def candidate(problem, experiment):
        req = {'target': 0, 'units': problem['budget_units'] + 1}
        try:
            experiment(req)
        except ValueError:
            pass
        return {'abstain': True}
    result = MODULE.evaluate(candidate)
    assert result['valid'] == result['combined_score'] == 0

def test_degenerate_strategies_and_global_rng_independence():
    for answer in ({'abstain': True}, {'model': 'none'}):
        first = MODULE.evaluate(lambda *args: answer)
        np.random.seed(777)
        np.random.random(1000)
        second = MODULE.evaluate(lambda *args: answer)
        assert first == second
        assert first['combined_score'] == 0 and first['valid'] == 1
        assert first['development_claim_count'] == 0
        assert first['development_false_discovery_rate'] == 0
        visible = search_visible_metrics(first)
        assert not any((k.startswith('heldout') or 'refusal' in k for k in visible))
        assert 'per_instance' not in visible

def test_correct_law_wrong_parameter_not_reclassified_as_false_discovery():
    w = MODULE.make_world(72, 'contact')
    row = MODULE.score_world(w, {'model': 'contact', 'mass_gev': 250})
    assert row['mechanism'] == 0 and row['false_claim'] is False


@pytest.mark.parametrize('answer', [
    {'abstain': True}, {'model': 'none'},
    {'model': 'contact', 'mass_gev': 10}, {},
])
def test_publication_diagnostics_recompute_from_world_counts(answer):
    metrics = MODULE.evaluate(lambda *args: answer)
    for split in MODULE.SPLIT_SEEDS:
        rows = [r for r in metrics['per_instance'] if r['split'] == split]
        expected = {
            'false_discovery_count': sum(r['false_claim'] for r in rows),
            'claim_count': sum(r['claim'] for r in rows),
            'correct_refusal_count': sum(r['correct_refusal'] for r in rows),
            'refusal_world_count': sum(r['kind'] == 'unsupported' for r in rows),
            'supported_claim_count': sum(r['claim'] for r in rows if r['kind'] in MODULE.LAWS),
            'supported_world_count': sum(r['kind'] in MODULE.LAWS for r in rows),
            'none_correct_count': sum(r['model'] == 'none' for r in rows if r['kind'] == 'none'),
            'none_world_count': sum(r['kind'] == 'none' for r in rows),
            'valid_world_count': sum(r['valid'] for r in rows),
            'world_count': len(rows), 'experiment_units_sum': sum(r['units'] for r in rows),
        }
        for name, count in expected.items():
            assert metrics[split + '_' + name] == count
        for rate, numerator, denominator in [
            ('false_discovery_rate', 'false_discovery_count', 'claim_count'),
            ('correct_refusal_rate', 'correct_refusal_count', 'refusal_world_count'),
            ('discovery_coverage', 'supported_claim_count', 'supported_world_count'),
            ('none_correct_rate', 'none_correct_count', 'none_world_count'),
            ('valid_rate', 'valid_world_count', 'world_count'),
            ('mean_units', 'experiment_units_sum', 'world_count'),
        ]:
            want = expected[numerator] / expected[denominator] if expected[denominator] else 0
            assert metrics[split + '_' + rate] == pytest.approx(want, abs=1e-10)
        assert not any(split + '_' + name in search_visible_metrics(metrics) for name in expected)

@pytest.mark.parametrize('kind', ['contact', 'q2', 'none', 'unsupported'])
def test_oracle_ceiling_recomputable_without_reference_score_literal(kind):
    world = MODULE.make_world(512, kind)
    answer = {'abstain': True} if kind == 'unsupported' else {'model': kind}
    if kind in MODULE.LAWS:
        answer['mass_gev'] = world['mass']
    assert MODULE.score_world(world, answer)['mechanism'] == 1


def test_mutating_public_problem_cannot_raise_budget():

    def candidate(problem, experiment):
        problem['budget_units'] = 10 ** 9
        try:
            experiment({'target': 0, 'units': 999})
        except ValueError:
            pass
        return {'abstain': True}
    assert MODULE.evaluate(candidate)['valid'] == 0

def test_world_boundaries_reset_candidate_session_including_split():

    class StatefulProxy:
        resets = 0
        calls = 0

        def reset_session(self):
            self.resets += 1

        def __call__(self, problem, experiment):
            assert self.resets == self.calls
            self.calls += 1
            return {'abstain': True}
    candidate = StatefulProxy()
    result = MODULE.evaluate(candidate)
    assert result['valid'] == 1
    assert candidate.calls == 2 * MODULE.WORLD_COUNT and candidate.resets == candidate.calls - 1

@pytest.mark.skipif(platform.system() != 'Linux', reason='Bubblewrap requires Linux')
def test_secure_worlds_cannot_share_globals_or_tmpfs(tmp_path):
    from sle.evaluate import evaluate_candidate
    from sle.registry import find_task
    path = tmp_path / 'candidate.py'
    path.write_text("from pathlib import Path\nseen = False\ndef infer_recoil(problem, experiment):\n    global seen\n    marker = Path('/tmp/previous_world')\n    if seen or marker.exists():\n        return []\n    seen = True\n    marker.write_text('visited')\n    return {'model': 'none'}\n")
    result = evaluate_candidate(find_task('ParticlePhysics/DarkMatterRecoilAttribution', include_uncertified=True), path, timeout_s=60)
    assert result['valid'] == 1 and result['combined_score'] == 0
    assert result['development_valid_rate'] == result['heldout_valid_rate'] == 1


@pytest.mark.parametrize('split', ['development', 'heldout'])
def test_mass_coverage_is_stratified_for_each_law(split):
    worlds = list(MODULE.split_worlds(split))
    for law in MODULE.LAWS:
        masses = np.array([w['mass'] for w in worlds if w['kind'] == law])
        assert len(masses) >= 20 // len(MODULE.LAWS)
        positions = np.log(masses / 22) / np.log(125 / 22)
        assert sorted(np.floor(positions * len(masses)).astype(int)) == list(range(len(masses)))
        assert masses.max() / masses.min() > 4
    other = 'heldout' if split == 'development' else 'development'
    assert {w['seed'] for w in worlds}.isdisjoint(w['seed'] for w in MODULE.split_worlds(other))


@pytest.mark.parametrize('split', ['development', 'heldout'])
def test_unsupported_has_exact_supported_single_target_twins(split):
    # Even all exposure units cannot tell these paired worlds apart on one target:
    # same rates, controls, calibration AND sampled observations. Joint inference
    # is needed; a generic narrow-peak detector cannot certify misspecification.
    for world in MODULE.split_worlds(split):
        if world['kind'] != 'unsupported':
            continue
        assert max(world['target_masses']) / min(world['target_masses']) > 3
        for t in range(3):
            twin = MODULE.make_world(world['seed'], 'q2' if world['power'] else 'contact',
                                     signal_mass=world['target_masses'][t])
            np.testing.assert_array_equal(world['rates'][t], twin['rates'][t])
            request = {'target': t, 'units': MODULE.BUDGET}
            assert MODULE.Campaign(world)(request) == MODULE.Campaign(twin)(request)


@pytest.fixture(scope='module')
def reference_metrics():
    reference = load(ROOT / 'benchmarks/Physics/DarkMatterRecoilAttribution/verification/reference_profile.py')
    return MODULE.evaluate(reference.infer_recoil)


def test_every_constant_mass_even_with_perfect_decisions_stays_far_below_reference(reference_metrics):
    audit = load(ROOT / 'scripts/audit_dark_matter_recoil.py')
    for split in MODULE.SPLIT_SEEDS:
        bound = audit.constant_mass_bound(MODULE, list(MODULE.split_worlds(split)))
        # This exact continuous bound includes perfect law/null/refusal decisions,
        # so it dominates the reviewer's reference-decisions + constant-mass attack.
        assert bound['score'] <= .6 * reference_metrics[split + '_mechanism_score']


def test_full_four_way_single_target_probe_stays_below_reference(reference_metrics):
    from sle.registry import find_task
    audit = load(ROOT / 'scripts/audit_dark_matter_recoil.py')
    probe = audit.shortcut_probe(find_task('ParticlePhysics/DarkMatterRecoilAttribution', include_uncertified=True))
    for split, value in [('development', probe['development_best']), ('heldout', probe['heldout_selected_once'])]:
        reference = reference_metrics[split + '_mechanism_score']
        assert value < .7 * reference
        assert reference - value > .15


def test_null_refusal_and_scientific_ceiling_follow_the_actual_mixture():
    for split in MODULE.SPLIT_SEEDS:
        worlds = list(MODULE.split_worlds(split))
        for answer in [{'abstain': True}, {'model': 'none'}]:
            assert MODULE.normalized_score([MODULE.score_world(w, answer)['mechanism'] for w in worlds]) == 0
        assert MODULE.normalized_score([1] * len(worlds)) == 1

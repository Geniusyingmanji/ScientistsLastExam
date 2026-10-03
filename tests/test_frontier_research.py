"""Prospective frontier contract checks and an API-free native sandbox workflow.

Numeric fixtures below interpret a closed set of literal programs; they do not
execute candidate code on the host or claim that stand-ins validate physics.
The Linux-only test exercises real isolated analysis and prediction callbacks.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from _sandbox_tools import skip_unless_sandbox
from env.prospective import ProspectiveSession, FRONTIER_PROTOCOL, PROTOCOL, digest
from env.molecular_forces.protocol import validate_spec
from env import research_runner as runner
from env import prospective_runner as task_runner


def _spec(length=3.):
    return {'configurations': [[[0., 0., 0.], [float(length), 0., 0.],
                                [float(length)/2, float(length)*3**.5/2, 0.]]],
            'configuration_ids': [0], 'temperature_k': 450.}


def _code(coefficient):
    return ('def predict(spec):\n'
            '    return [[%r * p[1][0]] for p in spec["configurations"]]\n' % coefficient)


_CODES = {_code(v): v for v in (0., 1., 2.)}


class NumericFrontier:
    def __init__(self, truth=1., frontier=True):
        self.truth = truth
        self.events, self.predictions, self.observations = [], [], []
        self.public = {'environment': 'molecular_forces', 'world_version': 'numeric-stand-in',
                       'axis_field': 'configuration_ids', 'channels': ['energy_ev'],
                       'scales': [1.], 'noise_std': [.001], 'noise_mean_bias_bound': [0.]}
        self.session = ProspectiveSession(self.public, validate_spec=validate_spec,
                                         predict=self.predict, observe=self.observe,
                                         persist=self.persist, runtime_id='trusted-literal-fixture',
                                         max_tests=3, family_alpha=.05, frontier=frontier)
        prior_spec = _spec(2.5)
        self.prior = [{'id': 'obs-source-0001', 'spec': prior_spec,
                       'observation': self.response(prior_spec)}]

    def response(self, spec):
        return {'axis': spec['configuration_ids'], 'channels': ['energy_ev'],
                'values': [[self.truth*p[1][0]] for p in spec['configurations']]}

    def predict(self, code, spec):
        self.predictions.append((code, deepcopy(spec)))
        return [[_CODES[code]*p[1][0]] for p in spec['configurations']]

    def observe(self, spec, *, noise_key):
        assert self.events[-1]['kind'] in ('collection_started', 'fresh_observation')
        assert any(e['kind'] == 'registered' for e in self.events)
        self.observations.append((deepcopy(spec), noise_key))
        return self.response(spec)

    def persist(self, event):
        self.events.append(deepcopy(event))
        return 'fixture-receipt-%d' % len(self.events)

    def request(self, coefficients=(1.,), length=3., profile='predictive_validation'):
        return {'profile': profile, 'scope': 'Literal numeric fixture, one configuration energy only.',
                'rivals': [{'id': 'account-%d' % i, 'predictor_code': _code(v),
                            'rationale': 'Protocol fixture account; no scientific validity claim.',
                            'evidence_ids': [self.prior[0]['id']], 'tolerance': .03}
                           for i, v in enumerate(coefficients)],
                'experiments': [{'id': 'target', 'role': 'target', 'spec': _spec(length)}],
                'readout': [{'experiment_id': 'target', 'row': 0, 'channel': 'energy_ev', 'weight': 1.}],
                'replicates': 8, 'revision_of': None, 'change_note': ''}

    def complete(self, request=None):
        registered = self.session.register(request or self.request(), records=self.prior)
        assert not self.observations or any(e['kind'] == 'completed' for e in self.events)
        result = self.session.collect(registered['test_id'])
        return registered, result, self.session.snapshot()['tests'][-1]


@pytest.mark.parametrize('truth,outcome', [(1., 'scoped_predictive_adequacy'),
                                           (2., 'candidate_refuted'), (1.01, 'inconclusive')])
def test_frontier_single_account_outcomes_and_preobservation_seal(truth, outcome):
    fixture = NumericFrontier(truth)
    registration = fixture.session.register(fixture.request(), records=fixture.prior)
    assert fixture.observations == []
    assert len(fixture.predictions) == 2
    assert fixture.events[-1]['kind'] == 'registered'
    assert registration['protocol'] == FRONTIER_PROTOCOL
    assert registration['alpha'] == pytest.approx(.05/3)
    assert registration['rivals'][0]['predictions']['target'] == [[3.]]
    result = fixture.session.collect(registration['test_id'])
    assert result['outcome'] == outcome
    assert result['predictive_discrimination_supported'] is False
    assert result['mechanism_identified'] is False
    assert result['discovery_depth_certified'] is False
    assert len(fixture.observations) == 8
    assert len({key for _, key in fixture.observations}) == 8
    if outcome == 'inconclusive':
        assert result['candidates'][0]['within_tolerance_on_readout'] is False
        assert result['candidates'][0]['refuted_on_readout'] is False
    json.dumps(fixture.session.snapshot(), allow_nan=False)


def test_frontier_two_account_discrimination_and_old_protocol_preserved():
    fixture = NumericFrontier()
    registration, result, _ = fixture.complete(fixture.request((1., 2.), profile='mechanism_discrimination'))
    assert result['outcome'] == 'scoped_predictive_discrimination'
    assert len(registration['rivals']) == 2
    old = NumericFrontier(frontier=False)
    with pytest.raises(ValueError, match='unsupported prospective profile'):
        old.session.register(old.request(), records=old.prior)
    old_request = old.request((1., 2.), profile='mechanism_discrimination')
    # Static index zero is legal only in the new audited workflow. This preserves
    # the older broad zero-coordinate exclusion rather than silently regrading it.
    with pytest.raises(ValueError, match='initial-coordinate'):
        old.session.register(old_request, records=old.prior)
    assert old.session.snapshot()['protocol'] == PROTOCOL
    assert old.observations == []
    # A nonzero row label still exercises the historical two-rival protocol.
    legacy_target = old.request((1., 2.), profile='mechanism_discrimination')
    legacy_target['experiments'][0]['spec']['configurations'].append(_spec(3.2)['configurations'][0])
    legacy_target['experiments'][0]['spec']['configuration_ids'] = [0, 1]
    legacy_target['readout'][0]['row'] = 1
    old_registration, old_result, _ = old.complete(legacy_target)
    assert old_registration['protocol'] == PROTOCOL
    assert old_result['outcome'] == 'scoped_predictive_discrimination'


def test_frontier_revision_retains_prior_failure_and_requires_new_cited_counterexample():
    fixture = NumericFrontier(truth=2.)
    parent, first_result, old_test = fixture.complete()
    revision = fixture.request((2.,), length=4.)
    revision.update(revision_of=parent['test_id'], change_note='Revise coefficient after the sealed counterexample.')
    with pytest.raises(ValueError, match='refinement'):
        fixture.session.register(revision, records=fixture.prior)
    revision['rivals'][0]['evidence_ids'].append(old_test['observations'][0]['id'])
    reused = deepcopy(revision)
    reused['experiments'][0]['spec'] = _spec(3.)
    with pytest.raises(ValueError, match='previously unobserved'):
        fixture.session.register(reused, records=fixture.prior)
    unchanged = deepcopy(revision)
    unchanged['rivals'][0]['predictor_code'] = _code(1.)
    with pytest.raises(ValueError, match='refinement'):
        fixture.session.register(unchanged, records=fixture.prior)
    registered = fixture.session.register(revision, records=fixture.prior)
    second_result = fixture.session.collect(registered['test_id'])
    assert second_result['outcome'] == 'scoped_predictive_adequacy'
    tests = fixture.session.snapshot()['tests']
    assert tests[0]['result'] == first_result
    assert tests[1]['registration']['revision_of'] == parent['test_id']
    assert len(tests[1]['registration']['rivals']) == 1
    assert fixture.session.snapshot()['alpha_reserved'] == pytest.approx(2*.05/3)


def test_frontier_revision_requires_a_refuted_parent():
    fixture = NumericFrontier()
    parent, _, old_test = fixture.complete()
    revision = fixture.request((2.,), length=4.)
    revision.update(revision_of=parent['test_id'], change_note='Unsupported revision lineage.')
    revision['rivals'][0]['evidence_ids'].append(old_test['observations'][0]['id'])
    with pytest.raises(ValueError, match='refinement'):
        fixture.session.register(revision, records=fixture.prior)


def test_frontier_manifest_freezes_workflow_model_and_source(monkeypatch):
    manifest = runner.create_manifest('frontier-freeze-fixture', 'climate_response', 73101,
                                      workflow='frontier', limits={'rounds': 4})
    assert manifest['protocol'] == runner.FRONTIER_PROTOCOL
    assert manifest['system_sha256'] == digest(runner.FRONTIER_SYSTEM)
    assert manifest['requested_model'] == 'gpt-5.6-sol'
    assert manifest['score'] is None
    assert manifest['automatic_depth_certification'] is False
    runner.validate_manifest(manifest)
    changed = deepcopy(manifest)
    changed['requested_model'] = 'different-model'
    with pytest.raises(ValueError, match='changed after freeze'):
        runner.validate_manifest(changed)
    monkeypatch.setattr(runner, 'source_digest', lambda: 'changed-source')
    with pytest.raises(ValueError, match='changed after freeze'):
        runner.validate_manifest(manifest)


ZERO_CLIMATE = ('def predict(spec):\n'
                '    return [[MODEL["zero"], MODEL["zero"]] for _ in spec["times_years"]]\n')


class FrontierReferenceClient:
    client_kind = 'scripted_reference'

    def __init__(self, manifest, analysis_code):
        self.reference_id = manifest['reference']['id']
        self.reference_source_sha256 = manifest['reference']['source_sha256']
        self.analysis_code, self.prompts = analysis_code, []
        self.last_usage, self.last_response_metadata, self.last_stop_reason = None, {}, None

    def complete(self, encoded, *, system):
        assert system == runner.FRONTIER_SYSTEM
        prompt = json.loads(encoded)
        self.prompts.append(prompt)
        step = len(self.prompts)
        if step == 1:
            action = {'note': 'Measure a short source preparation.', 'experiments': [
                {'forcing_w_m2': [1.]*4, 'times_years': [1, 4]}]}
        elif step == 2:
            action = {'note': 'Check isolation and save the deliberately weak zero predictor.',
                      'analyze': {'code': self.analysis_code}}
        elif step == 3:
            snapshot = prompt['model_snapshots'][0]
            action = {'note': 'Preregister one weak account before a fresh strong heating experiment.',
                      'preregister': {'profile': 'predictive_validation',
                                      'scope': 'Surface temperature at year10 under constant commanded forcing8.',
                                      'rivals': [{'id': 'zero', 'model_snapshot': {key: snapshot[key] for key in ('name', 'version', 'sha256')},
                                                  'rationale': 'Deliberately weak authored plumbing control; it can be refuted.',
                                                  'evidence_ids': [prompt['observation_catalog'][0]['id']], 'tolerance': .03}],
                                      'experiments': [{'id': 'new-heating', 'role': 'target',
                                                       'spec': {'forcing_w_m2': [8.]*10, 'times_years': [1, 10]}}],
                                      'readout': [{'experiment_id': 'new-heating', 'row': 1,
                                                   'channel': 'surface_temperature_anomaly_k', 'weight': 1.}],
                                      'replicates': 8, 'revision_of': None, 'change_note': ''}}
        else:
            assert step == 4
            action = {'note': 'Preserve a negative result without a discovery claim.',
                      'finish': {'explanation': 'The frozen zero predictor was refuted on its registered fresh readout. This authored test checks execution and does not establish autonomous discovery.',
                                 'evidence_ids': [prompt['observation_catalog'][0]['id']],
                                 'test_ids': [prompt['scientific_task']['results'][0]['test_id']]}}
        self.last_stop_reason = 'reference_action'
        return json.dumps(action)


@skip_unless_sandbox('bwrap')
def test_frontier_linux_real_source_analysis_snapshot_preregister_and_finish(tmp_path):
    manifest = runner.create_reference_manifest(
        'frontier-native-fixture', 'climate_response', 73101, workflow='frontier',
        reference_id='frontier-native-zero-0.1',
        reference_source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        limits={'rounds': 4, 'analysis_seconds': 60, 'wall_seconds': 300},
        science_limits={'wall_seconds': 300, 'predictor_seconds_per_call': 30})
    secret = tmp_path/'operator-private-canary.json'
    secret.write_text('"private-canary"')
    analysis_code = ('from pathlib import Path\n'
                     'assert not Path(%r).exists()\n' % str(secret) +
                     'assert not Path(%r).exists()\n' % str(Path(runner.__file__).parent) +
                     'assert "private_world_seed" not in str(problem)\n'
                     'assert len(records) == 1\n'
                     'save_model("zero-climate", "v1", {"zero": 0.0}, %r)\n' % ZERO_CLIMATE +
                     'result = list_models()\n')
    client = FrontierReferenceClient(manifest, analysis_code)
    report = runner.run_research(manifest, tmp_path/'native-run', lambda _: client)
    assert report['status'] == 'completed', report
    assert report['infrastructure_failure'] is None
    assert report['history'][1]['outcome'] == 'analysis_ok'
    assert report['history'][2]['outcome'] == 'candidate_refuted'
    assert report['requested_model'] is None
    assert report['provider_reported_models'] == []
    assert report['client_kind'] == 'scripted_reference'
    assert report['autonomous_discovery'] is False
    assert report['usage']['model_request_attempts'] == 0
    assert report['usage']['reference_request_attempts'] == 4
    assert report['scientific_task']['usage']['experiment_attempts'] == 9
    assert report['scientific_task']['usage']['predictor_attempts'] == 2
    assert len(client.prompts) == 4
    assert task_runner.verify_directory(tmp_path/'native-run/science')['replayed_tests'] == 1
    receipts = [json.loads(p.read_text()) for p in sorted((tmp_path/'native-run/driver-receipts').glob('[0-9]*.json'))]
    kinds = [r['kind'] for r in receipts]
    assert kinds.count('reference_request_started') == 4
    assert 'model_request_started' not in kinds


@pytest.mark.parametrize("environment", runner.FRONTIER_ENVIRONMENTS)
def test_new_world_uses_explicit_new_profile_without_promoting_legacy(environment):
    from env.registry import ENVIRONMENTS, EXPERIMENTAL_ENVIRONMENTS
    from env.task_profiles import get_task_profile
    assert environment in ENVIRONMENTS and environment in EXPERIMENTAL_ENVIRONMENTS
    with pytest.raises(ValueError, match="not applicable"):
        get_task_profile("open_discovery", environment)
    manifest = runner.create_manifest("catalog-check", environment, 73101, workflow="frontier")
    assert manifest["profile"]["catalog_version"] == "frontier-research-profiles-0.1"
    assert manifest["profile"]["applicable_environments"] == list(runner.FRONTIER_ENVIRONMENTS)
    runner.validate_manifest(manifest)

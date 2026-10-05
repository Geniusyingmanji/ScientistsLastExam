"""Model comparison must preserve the frozen scientific design and isolation."""
import copy
import json
from pathlib import Path
import shutil

import pytest

from env import unified_campaign as campaign
from env.ledger import CampaignLedger
from env.scoring import canonical_hash


@pytest.fixture
def reference(tmp_path):
    exclusions = tmp_path / 'exclusions.json'
    exclusions.write_text(json.dumps({'seeds': []}))
    root = tmp_path / 'gpt'
    campaign.freeze(root, exclusions, 'reference-commit')
    public = json.loads((root / 'public-progress.json').read_text())
    public.update(status='completed', settled_episodes=72)
    campaign.write(root / 'public-progress.json', public)
    config = tmp_path / 'model.json'
    cfg = dict(campaign.DECODING, model='deepseek-v4-pro-0813',
               reasoning_effort='high', chat_max_tokens_field='max_tokens', temperature=None)
    config.write_text(json.dumps(cfg))
    return root, config, Path(campaign.__file__).resolve().parents[1]


def test_pairing_preserves_every_private_design_field_and_reference(reference, tmp_path):
    root, config, source = reference
    before = (root / 'manifest-private.json').read_bytes()
    target = tmp_path / 'deepseek'
    campaign.freeze_paired(target, root, source, config, 'paired-commit')
    original, paired = campaign.load_manifest(root), campaign.load_manifest(target)
    assert (root / 'manifest-private.json').read_bytes() == before
    assert paired['instances'] == original['instances']
    for key in ('limits', 'score_contract', 'workers', 'rpm', 'planned_max_api_attempts'):
        assert paired[key] == original[key]
    assert CampaignLedger(target / 'attempts.sqlite').summary()['started_attempts'] == 0
    public = json.loads((target / 'public-progress.json').read_text())
    assert public['settled_episodes'] == 0 and public['total_score'] is None
    assert public['model'] == 'deepseek-v4-pro-0813'
    assert public['comparison']['reference_manifest_sha256'] == original['manifest_sha256']
    assert 'world_seed' not in json.dumps(public) and 'confirmation_key' not in json.dumps(public)
    with pytest.raises(FileExistsError):
        campaign.freeze_paired(target, root, source, config, 'paired-commit')


@pytest.mark.parametrize('change', [dict(model='deepseek-v3'), dict(reasoning_effort='max'),
                                   dict(max_output_tokens=16000), dict(temperature=.7)])
def test_undeclared_model_or_budget_changes_rejected(reference, tmp_path, change):
    root, config, source = reference
    cfg = json.loads(config.read_text()); cfg.update(change); config.write_text(json.dumps(cfg))
    with pytest.raises(ValueError):
        campaign.freeze_paired(tmp_path / 'bad', root, source, config, 'new')
    assert not (tmp_path / 'bad').exists()


@pytest.mark.parametrize("cap,profile", [(16000,"extended-output-v1"),(32000,"extended-output-32k-v1")])
def test_extended_budget_is_explicit_frozen_and_does_not_change_science(reference, tmp_path, cap, profile):
    root, config, source = reference
    prior = tmp_path / 'stopped'
    campaign.freeze_paired(prior, root, source, config, 'old')
    public = json.loads((prior / 'public-progress.json').read_text())
    public.update(status='stopped_infrastructure', settled_episodes=12)
    public['ledger']['started_attempts'] = 94
    campaign.write(prior / 'public-progress.json', public)
    cfg = json.loads(config.read_text())
    cfg.update(stream=True, chat_empty_response_as_text=True, max_output_tokens=cap, timeout_seconds=900)
    config.write_text(json.dumps(cfg))
    before = (prior / 'public-progress.json').read_bytes()
    with pytest.raises(ValueError, match='declared adapter'):
        campaign.freeze_paired(tmp_path / 'implicit', root, source, config, 'new', prior)
    target = tmp_path / 'extended'
    probe = tmp_path / 'probe.json'
    probe.write_text(json.dumps(dict(scored=False, attempts=1, status='terminal', sse_valid=True, max_tokens=cap,
                                    deadline_seconds=965, visible_characters=1200, terminal_seconds=310.)))
    campaign.freeze_paired(target, root, source, config, 'new', prior,
                          budget_profile=profile, prior_campaign=prior, readiness_probe=probe)
    old, new = campaign.load_manifest(root), campaign.load_manifest(target)
    assert (prior / 'public-progress.json').read_bytes() == before
    assert new['instances'] == old['instances']
    assert new['score_contract'] == old['score_contract']
    assert new['limits'] == dict(old['limits'], wall_seconds=14400)
    assert new['planned_max_api_attempts'] == 1152
    assert new['workers'] == old['workers'] == 8
    assert new['comparison']['budget_change']['equal_budget'] is False
    assert new['comparison']['previous_stopped_campaign']['calls'] == 94
    assert new['decoding']['max_output_tokens'] == cap
    assert new['decoding']['timeout_seconds'] == 900
    assert CampaignLedger(target / 'attempts.sqlite').summary()['started_attempts'] == 0
    # Even the explicit profile cannot silently expand beyond its fixed limits.
    cfg['max_output_tokens'] = 64000
    config.write_text(json.dumps(cfg))
    with pytest.raises(ValueError, match='declared adapter'):
        campaign.freeze_paired(tmp_path / 'too-large', root, source, config, 'new', prior,
                              budget_profile=profile, prior_campaign=prior, readiness_probe=probe)
    probe.write_text(json.dumps(dict(scored=False, attempts=1, status='interrupted', max_tokens=cap,
                                    deadline_seconds=965, visible_characters=1200)))
    with pytest.raises(ValueError, match='complete visible response'):
        campaign.freeze_paired(tmp_path / 'not-ready', root, source, config, 'new', prior,
                              budget_profile=profile, prior_campaign=prior, readiness_probe=probe)


def test_extended_budget_requires_preserved_predecessor(reference, tmp_path):
    root, config, source = reference
    with pytest.raises(ValueError, match='preserved stopped campaign'):
        campaign.freeze_paired(tmp_path / 'bad', root, source, config, 'new',
                              budget_profile='extended-output-v1')


def test_scientific_source_change_rejected_even_with_valid_reference_hash(reference, tmp_path):
    root, config, source = reference
    archived = tmp_path / 'old-source'
    for pkg in ('env', 'sle'):
        shutil.copytree(source / pkg, archived / pkg, ignore=shutil.ignore_patterns('__pycache__'))
    target = archived / 'env/unified_scoring.py'
    target.write_text(target.read_text() + '\n# Different scientific source\n')
    manifest = campaign.load_manifest(root)
    manifest['source_sha256'] = campaign.source_digest(archived)
    manifest.pop('manifest_sha256')
    manifest['manifest_sha256'] = canonical_hash(manifest)
    campaign.write(root / 'manifest-private.json', manifest)
    with pytest.raises(ValueError, match='changed scientific source'):
        campaign.freeze_paired(tmp_path / 'bad', root, archived, config, 'new')


def test_run_rejects_model_change_after_freeze_before_any_attempt(reference, tmp_path):
    root, config, source = reference
    target = tmp_path / 'deepseek'
    campaign.freeze_paired(target, root, source, config, 'new')
    cfg = json.loads(config.read_text()); cfg['model'] = 'gpt-5.6-sol'; config.write_text(json.dumps(cfg))
    with pytest.raises(ValueError, match='model/decoding differs'):
        campaign.run(target, config)
    assert CampaignLedger(target / 'attempts.sqlite').summary()['started_attempts'] == 0
    assert not (target / 'started.json').exists()


def test_streaming_requires_preserved_failed_pilot(reference, tmp_path):
    root, config, source=reference
    cfg=json.loads(config.read_text());cfg['stream']=True;cfg['chat_empty_response_as_text']=True;config.write_text(json.dumps(cfg))
    with pytest.raises(ValueError,match='bind its failed nonstream'):
        campaign.freeze_paired(tmp_path/'stream',root,source,config,'new')
    pilot=tmp_path/'pilot';pilot.mkdir()
    prior=json.loads((root/'public-progress.json').read_text())
    prior.update(status='stopped_infrastructure',model=cfg['model'],settled_episodes=12)
    prior['ledger']['started_attempts']=24
    campaign.write(pilot/'public-progress.json',prior)
    campaign.freeze_paired(tmp_path/'stream',root,source,config,'new',pilot)
    frozen=campaign.load_manifest(tmp_path/'stream')
    assert frozen['decoding']['stream'] is True
    assert frozen['comparison']['transport_pilot']['calls']==24
    assert frozen['instances']==campaign.load_manifest(root)['instances']

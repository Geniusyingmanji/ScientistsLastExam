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

import json

import pytest

from env.campaign import create_manifest
from env.registry import load_world


def test_balanced_hidden_families_are_frozen_but_not_disclosed():
    manifest = create_manifest("balanced-test", ["hysteresis_material"], instances=2,
                               rounds=4, exploration_rounds=2, balanced_strata=["hysteresis_material"])
    rows = manifest["instances"]
    assert [row["operator_sampling_stratum"] for row in rows] == ["relaxation", "bistable"]
    assert len({row["world_seed"] for row in rows}) == 2
    for row in rows:
        assert row["world_seed"] not in manifest["reserved_development_world_seeds"]
        world, _ = load_world(row["environment"], row["world_seed"])
        assert world.operator_stratum() == row["operator_sampling_stratum"]
        public = json.dumps(world.describe())
        assert "operator_sampling_stratum" not in public
        assert '"bistable"' not in public and '"relaxation"' not in public


def test_stratification_cannot_silently_invent_unknown_world_labels():
    with pytest.raises(ValueError, match="operator strata"):
        create_manifest("unsupported", ["microecology"], instances=1, balanced_strata=["microecology"])
    with pytest.raises(ValueError, match="selected environments"):
        create_manifest("not-selected", ["hysteresis_material"], instances=1, balanced_strata=["microecology"])


def test_presentation_rejects_unsupported_world_before_any_model_call():
    with pytest.raises(ValueError, match="not audited"):
        create_manifest("unsupported-presentation", ["gene_regulation"], instances=1, presentation_profile="apparatus_only")

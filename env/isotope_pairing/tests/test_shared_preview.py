from types import SimpleNamespace
import pytest
from env.isotope_pairing.world import World
from env.prospective_runner import ProspectiveTask, PublicSchemaRejected, PredictorInfrastructureFailed


def preview(world, spec):
    # Read-only method fixture: no task startup, sampling, predictor or ledger.
    return ProspectiveTask._preview_validate(SimpleNamespace(_world=world, _frontier=True), spec)


def test_preview_public_feedback_and_detached_controls():
    w = World(0)
    s = w.example()
    result = preview(w, s)
    assert result == s and result is not s
    for invalid in ({}, dict(s, times=[2., 1.]), dict(s, times=[-1.]),
                    dict(s, source=[{'at': 0., 'fractions': [1., 1., 0., 0.]}])):
        with pytest.raises(PublicSchemaRejected):
            preview(w, invalid)


def test_preview_internal_error_is_not_candidate_feedback():
    class Broken(World):
        def validate(self, spec):
            raise ValueError('PRIVATE_CANARY_OPERATOR_PATH')
    with pytest.raises(PredictorInfrastructureFailed) as error:
        preview(Broken(0), World.example())
    assert 'PRIVATE_CANARY' not in str(error.value)

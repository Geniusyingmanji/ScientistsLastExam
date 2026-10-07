from env.isotope_pairing.presentation import research_task
from env.isotope_pairing.world import World


def test_presentation_detached_and_apparatus_invariant():
    a = research_task()
    a['workflow'].clear()
    assert len(research_task()['workflow']) == 4
    assert World(0).describe() == World(1234).describe()
    assert 'scrambling' not in repr(research_task()).lower()
    assert 'operator_prototype' in research_task()['status']

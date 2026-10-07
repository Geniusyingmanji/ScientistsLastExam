"""Explicit operator entry; not registry admission or authorization for API calls."""
from env.runner import run_episode
from . import campaign_scoring
from .world import World, baseline


def load_isotope(name, seed):
    if name != 'isotope_pairing':
        raise ValueError('isotope driver requires isotope_pairing')
    return World(seed), baseline


def run_model_episode(instance, limits, directory, client, **testing):
    if instance.get('scoring_protocol') != campaign_scoring.PROTOCOL:
        raise ValueError('explicit isotope score protocol required')
    if set(testing) - {'analysis_factory', 'predict_fn'}:
        raise ValueError('unsupported driver argument')
    return run_episode(instance, limits, directory, client,
                       world_factory=load_isotope, scoring_adapter=campaign_scoring, **testing)

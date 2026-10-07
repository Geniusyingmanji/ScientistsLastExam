"""Explicit operator driver; not shared registry admission."""
from env.runner import run_episode
from env import history_scoring
from .world import World,baseline


def load_world(name,seed):
    if name != 'retention_transport':raise ValueError('driver world mismatch')
    return World(seed),baseline


def run_model_episode(instance,limits,directory,client,**testing):
    if instance.get('scoring_protocol')!=history_scoring.PROTOCOL:
        raise ValueError('explicit history scoring protocol required')
    if set(testing)-{'analysis_factory','predict_fn'}:raise ValueError('unsupported driver argument')
    return run_episode(instance,limits,directory,client,world_factory=load_world,
                       scoring_adapter=history_scoring,**testing)

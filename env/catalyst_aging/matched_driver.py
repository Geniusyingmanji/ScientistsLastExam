"""Explicit matched catalyst task admission, without changing shared profiles."""
from env.runner import run_episode, SYSTEM
from .world import World, baseline
from . import matched_scoring as scoring

scoring.CANDIDATE_SYSTEM = SYSTEM.replace(
    'Avoid duplicate claims; every omitted claim slot scores zero.',
    'For this task submit claims: []; no claim score or omission penalty applies.')
scoring.TASK_PROFILE = {
    'name': 'open_discovery', 'version': scoring.PROTOCOL,
    'public_prompt': 'Investigate catalyst reaction history and instrument drift. Predict terminal signals after executing every preparation event; paired effects are derived from those same predictions. Explain alternatives and unresolved mechanisms; submit claims: [].',
    'automatic_depth_certification': False}


def load_world(name, seed):
    if name != 'catalyst_aging':
        raise ValueError('driver world mismatch')
    return World(seed), baseline


def run_model_episode(instance, limits, directory, client, **testing):
    if instance.get('scoring_protocol') != scoring.PROTOCOL:
        raise ValueError('explicit matched scoring protocol required')
    if set(testing)-{'analysis_factory','predict_fn'}:
        raise ValueError('unsupported driver argument')
    return run_episode(instance, limits, directory, client,
                       world_factory=load_world, scoring_adapter=scoring, **testing)

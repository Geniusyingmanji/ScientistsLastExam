"""Explicit order-task integration, without shared registry admission."""
from env.runner import run_episode, SYSTEM
from .model_driver import load_world
from . import order_scoring

# All presentation changes are confined to this new opt-in task.
order_scoring.CANDIDATE_SYSTEM = SYSTEM.replace(
    'Avoid duplicate claims; every omitted claim slot scores zero.',
    'For this task submit claims: []; no claim score or omission penalty applies.')
order_scoring.TASK_PROFILE = {
    'name': 'open_discovery', 'version': order_scoring.PROTOCOL,
    'public_prompt': 'Investigate recovery and effects of flow ordering. Freeze a predictor for individual arm specifications; the evaluator derives paired contrasts from the same frozen predictions. Explain alternatives and uncertainty; claims must be [].',
    'automatic_depth_certification': False}


def run_model_episode(instance, limits, directory, client, **testing):
    if instance.get('scoring_protocol') != order_scoring.PROTOCOL:
        raise ValueError('explicit order scoring protocol required')
    if set(testing) - {'analysis_factory', 'predict_fn'}:
        raise ValueError('unsupported driver argument')
    return run_episode(instance, limits, directory, client,
                       world_factory=load_world, scoring_adapter=order_scoring, **testing)

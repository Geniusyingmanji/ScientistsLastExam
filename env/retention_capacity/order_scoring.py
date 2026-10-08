"""Explicit paired endpoint adapter; historical scoring remains unchanged."""
import numpy as np
from . import scoring, order_task

PROTOCOL = order_task.VERSION
CONFIRMATION_REPLICATES = 0
CLAIM_SYSTEM = 'This task scores only frozen endpoint predictions and their derived signed differences. Claims must be an empty list. Explain evidence and limitations in explanation. '


def score_contract():
    return dict(order_task.describe(), protocol=PROTOCOL,
                weights={'absolute': .5, 'order': .5},
                prediction='Pool all paired endpoints before computing RMSE; no average of per-arm scores. Left-minus-right contrasts use those same predictions.',
                claims='No claim slots or missing-claim penalty; submit claims: [].')


def public_panel_domain(environment):
    if environment != 'retention_capacity':
        raise ValueError('capacity world required')
    return {'protocol': PROTOCOL, 'domain': 'Paired reversed three-segment schedules, equal segment duration 0.5..2, load 0.1..3, rates 0..3, common tail 0..3, final time from end of third segment to 12. Predict each ordinary single-arm spec; pairs are assembled privately.',
            'scope': 'Order effects alone do not identify nonlinear or unique internal mechanisms.'}


def generate_panel(world, seed, kind, count=8):
    if world.name != 'retention_capacity' or kind not in ('conditions', 'interventions'):
        raise ValueError('capacity paired panel required')
    if type(count) is not int or not 1 <= count <= 64:
        raise ValueError('1..64 pairs required')
    rng = np.random.default_rng(seed)
    result = []
    for _ in range(count):
        duration = float(rng.uniform(.5, 2))
        design = order_task.pair(float(rng.uniform(.1, 3)),
                                rng.uniform(0, 3, 3).tolist(), duration,
                                float(rng.uniform(3*duration, 12)),
                                float(rng.uniform(0, 3)))
        design = order_task.validate_pair(world, design)
        result.append(design['left' if kind == 'conditions' else 'right'])
    return result


def validate_submission(value, world, records):
    if not isinstance(value, dict) or value.get('claims') != []:
        raise ValueError('this prediction task requires claims: []')
    return scoring.validate_submission(value, world, records)


def verify_claims(world, claims, confirmation_key):
    if claims != []:
        raise ValueError('no claim slots in this task')
    return {'protocol': PROTOCOL, 'score': 0., 'verified_nonzero_effects': 0, 'claims': []}


def prediction_metrics(predicted, observed, scales, *, world, spec):
    # Single-arm metrics are diagnostics only. Final score pools all paired arms.
    return scoring.prediction_metrics(predicted, observed, scales, world=world, spec=spec)


def aggregate_episode(panel_reports, claim_report):
    a, b = (panel_reports[k] for k in ('conditions', 'interventions'))
    if not a or len(a) != len(b):
        raise ValueError('matching nonempty paired panels required')
    predicted, targets = [], []
    for left, right in zip(a, b):
        if left['index'] != right['index']:
            raise ValueError('pair index mismatch')
        predicted.append([left['prediction_values'][0][0], right['prediction_values'][0][0]])
        targets.append([left['clean_truth']['values'][0][0], right['clean_truth']['values'][0][0]])
    metrics = order_task.score(predicted, targets)
    return {'protocol': PROTOCOL, 'score': metrics['score'],
            'subscores': {'absolute': metrics['absolute_score'], 'order': metrics['contrast_score']},
            'paired_metrics': metrics}

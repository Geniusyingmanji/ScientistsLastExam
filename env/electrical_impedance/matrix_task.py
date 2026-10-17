"""Unregistered port-law task: prediction metrics separate from explanation.

All categories and the voltage scale are frozen task conditions, not fitted on
candidate results. Internal topology is not a numeric recovery target.
"""
import numpy as np
from .protocol import validate_spec

VOLTAGE_SCALE = .05
APPLICABILITY = {
    'law/deduction': 'frequency response predictions; known amplitude scaling alone excluded',
    'law/mechanism': 'requires independent scoped explanation review; no automatic score',
    'law/unification': 'one frozen predictor across external source/load settings',
    'law/counterfactual': 'unseen external circuit settings, not internal component surgery',
    'structure/deduction': 'observable equivalence constraints; numerical values need a law',
    'structure/mechanism': 'equivalent internal realizations accepted; unique topology not identifiable',
    'structure/unification': 'same terminal representation across apparatus settings',
    'structure/counterfactual': None,
}


def transfer_kind(source, query):
    source, query = validate_spec(source), validate_spec(query)
    changed_frequency = query['frequencies_hz'] != source['frequencies_hz']
    changed_circuit = any(source[k] != query[k] for k in ('source_ohm','load_ohm'))
    if changed_circuit:
        return 'joint_transfer' if changed_frequency else 'apparatus_transfer'
    if changed_frequency:
        return 'frequency_transfer'
    raise ValueError('same frequencies and circuit: amplitude-only scaling is not discovery transfer')


def prediction_metrics(panels):
    """Trusted panels contain source/query, frozen prediction and target.

    Every invalid prediction is retained as a failed panel with score zero;
    successful-only RMSE is explicitly conditional, never an overall score.
    """
    if not panels: raise ValueError('nonempty frozen panel set required')
    results = []
    for panel in panels:
        kind = transfer_kind(panel['source'],panel['query'])
        n = len(validate_spec(panel['query'])['frequencies_hz'])
        target = np.asarray(panel['target'], dtype=float)
        if target.shape != (n,2) or not np.isfinite(target).all():
            raise ValueError('invalid trusted target')
        try:
            pred = np.asarray(panel['prediction'], dtype=float)
            if pred.shape != target.shape or not np.isfinite(pred).all():
                raise ValueError('invalid frozen prediction')
            mse = float(np.mean((pred-target)**2))
            if not np.isfinite(mse): raise ValueError('nonfinite squared error')
            rmse = float(np.sqrt(mse))
            results.append(dict(kind=kind, valid=True, rmse=rmse, score=100/(1+(rmse/VOLTAGE_SCALE)**2)))
        except (ValueError,TypeError,OverflowError):
            results.append(dict(kind=kind, valid=False, rmse=None, score=0.))
    groups = {}
    for kind in ('frequency_transfer','apparatus_transfer','joint_transfer'):
        rows = [x for x in results if x['kind']==kind]
        if rows:
            groups[kind] = dict(total=len(rows),valid=sum(x['valid'] for x in rows),
                score_including_failures=sum(x['score'] for x in rows)/len(rows))
    return dict(panels=results, groups=groups, scientific_matrix_scores=None,
                scope='Predictive transfer only; does not establish equation recovery or unique topology.')

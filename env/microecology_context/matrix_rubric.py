"""Review-backed matrix ratings; never infer science from citation counts.

A reviewer supplies an explicit decision on each criterion. This module only
validates those records and aggregates within cells, without an overall score.
"""
from .matrix_submission import CELLS

RUBRIC = {
 'law/deduction': ('quantitative_scoped_law', 'derivation_with_units', 'independent_prediction'),
 'law/mechanism': ('coupled_state_equations', 'conserved_flux_account', 'discriminating_control'),
 'law/unification': ('one_frozen_parameterization', 'multiple_regimes_predicted', 'rival_and_failure_scope'),
 'law/counterfactual': ('legal_intervention_defined', 'prospective_effect_prediction', 'matched_control_supported'),
 'structure/deduction': ('operational_dependency_graph', 'graph_implies_observables', 'alternative_graph_compared'),
 'structure/mechanism': ('operational_pathway_claim', 'mediator_or_context_control', 'equivalence_limit_stated'),
 'structure/unification': ('shared_graph_across_regimes', 'context_dependence_accounted', 'competing_graph_scope'),
 'structure/counterfactual': ('legal_node_or_context_change', 'prospective_structural_consequence', 'matched_control_supported'),
}
VERSION = 'ecology-matrix-rubric-1'


def summarize_review(claims, decisions, applicable=CELLS):
    """Partial review remains null; explicit rejected criteria score zero.

    Evidence locators must refer to a trusted review archive, checked by the
    reviewer. Their presence is not automated scientific verification.
    """
    if set(applicable) - set(CELLS):
        raise ValueError('unknown cell')
    claim_map = {c['id']: c for c in claims}
    if len(claim_map) != len(claims):
        raise ValueError('duplicate claims')
    seen = {}
    for d in decisions:
        cell, criterion = d['cell'], d['criterion']
        if cell not in applicable or criterion not in RUBRIC[cell]:
            raise ValueError('criterion outside rubric')
        if (cell, criterion) in seen:
            raise ValueError('duplicate criterion')
        if type(d['supported']) is not bool or not isinstance(d['reason'], str) or not d['reason'].strip():
            raise ValueError('explicit judgment and reason required')
        refs = d['claim_ids']
        if not isinstance(refs, list) or len(set(refs)) != len(refs) or any(r not in claim_map or claim_map[r]['cell'] != cell for r in refs):
            raise ValueError('invalid claim references')
        locators = d['evidence']
        if not isinstance(locators, list) or any(not isinstance(x, str) or not x.strip() for x in locators):
            raise ValueError('invalid evidence')
        if d['supported'] and (not refs or not locators):
            raise ValueError('supported criterion needs claim and evidence')
        seen[cell, criterion] = d['supported']
    result = {}
    for cell in CELLS:
        missing = [k for k in RUBRIC[cell] if (cell, k) not in seen]
        result[cell] = {'applicable': cell in applicable,
            'score': None if cell not in applicable or missing else sum(seen[cell,k] for k in RUBRIC[cell]),
            'max_score': 3 if cell in applicable else None,
            'unreviewed': missing if cell in applicable else []}
    return {'rubric': VERSION, 'cells': result, 'overall_score': None,
            'review_independence': 'same-family', 'acceptance_status': 'provisional'}

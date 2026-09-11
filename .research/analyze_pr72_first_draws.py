"""Read-only decomposition of all three retained first proposals; no model/oracle calls."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DRAW = ROOT/'experiments/dark_matter_recoil_first_draw_review_2026-09-11.json'
REFERENCE = ROOT/'.research/pr72_admission_contribution_2026-09-11.json'


def main():
    draw = json.loads(DRAW.read_text())
    gate = json.loads(REFERENCE.read_text())
    refs = [r for r in gate['records'] if r['candidate'] == 'verification/reference_profile.py']
    assert len(refs) == 2 and refs[0]['full_metrics_sha256'] == refs[1]['full_metrics_sha256']
    assert draw['source_revision'] == gate['source_revision']
    assert len(draw['cells']) == draw['scheduled_first_proposals']
    reference = refs[0]['scalar_metrics']
    rows = []
    for cell in draw['cells']:
        first = [e for e in cell['events'] if e['step'] == 1]
        assert len(first) == 1
        event = first[0]
        row = dict(seed_label=cell['seed_label'], candidate_sha256=event['candidate_sha256'],
                   all_worlds_valid=event['all_worlds_valid'], valid_worlds=event['valid_worlds'],
                   reference_reached=event['reference_reached'])
        if event['all_worlds_valid']:
            metrics = event['scalar_metrics']
            row['splits'] = {}
            for split in ('development', 'heldout'):
                prefix = split+'_'
                score_delta = metrics[prefix+'mechanism_score'] - reference[prefix+'mechanism_score']
                decision_delta = (metrics[prefix+'correct_refusal_count'] + metrics[prefix+'none_correct_count']
                                  - reference[prefix+'correct_refusal_count'] - reference[prefix+'none_correct_count'])
                # The frozen score is (utility_sum - 4) / 24 when positive.
                assert metrics[prefix+'mechanism_score'] > 0 and reference[prefix+'mechanism_score'] > 0
                row['splits'][split] = dict(score_delta=score_delta,
                    null_refusal_score_delta=decision_delta/24,
                    supported_utility_mean_delta=(24*score_delta-decision_delta)/20,
                    mean_units=metrics[prefix+'mean_units'],
                    false_claims=metrics[prefix+'false_discovery_count'])
        else:
            row['interpretation'] = 'Incomplete first proposal retained; not a low-scoring difficulty sample.'
        rows.append(row)
    result = dict(source_revision=draw['source_revision'],
                  input_hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (DRAW, REFERENCE)},
                  rows=rows, criterion_D16=draw['criterion_D16'],
                  interpretation='Aggregate attribution only; does not identify the candidate algorithm. All three first proposals retained.',
                  model_calls=0, oracle_calls=0)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()

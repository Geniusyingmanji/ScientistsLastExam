import json
import pytest
from env.microecology_context.prospective import ProspectiveJournal


def test_registration_cannot_follow_attempt_or_change_target(tmp_path):
    j=ProspectiveJournal(tmp_path/'journal.jsonl')
    j.reserve('old', {'dose':1})
    with pytest.raises(ValueError): j.register('old', {'dose':1}, [1.], 'a'*64)
    j.register('future', {'dose':2}, [3.], 'a'*64)
    with pytest.raises(ValueError): j.register('future', {'dose':2}, [4.], 'b'*64)
    with pytest.raises(ValueError): j.reserve('future', {'dose':3})
    j.reserve('future', {'dose':2})
    with pytest.raises(ValueError): j.reserve('future', {'dose':2})
    assert len((tmp_path/'journal.jsonl').read_text().splitlines())==3


def test_corruption_and_nonfinite_rejected(tmp_path):
    p=tmp_path/'journal.jsonl'; j=ProspectiveJournal(p)
    with pytest.raises(ValueError): j.register('x', {}, [float('nan')], 'a'*64)
    j.register('x', {}, [1.], 'a'*64)
    row=json.loads(p.read_text()); row['prediction']=[2.]
    p.write_text(json.dumps(row)+'\n')
    with pytest.raises(ValueError, match='integrity'): j.reserve('x', {})

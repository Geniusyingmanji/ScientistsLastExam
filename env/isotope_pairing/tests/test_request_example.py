import json
from pathlib import Path
from env.prospective_runner import ProspectiveTask
from env.isotope_pairing.world import World


def test_request_example_read_only_preview(tmp_path):
    task = ProspectiveTask('isotope_pairing', 0, tmp_path/'task', frontier=True, prototype=True)
    s = World.example()
    # Explicit inert schema fixture, never a scored experiment or scientific data.
    task._records = [{'id':'obs-source-0001','spec':s,'observation':{'axis':s['times'],'channels':list(World.channels),'values':[[1.,0.,0.] for _ in s['times']]}}]
    request = json.loads((Path(__file__).parents[1]/'examples/prospective_request.json').read_text())
    before = dict(task._usage)
    assert task.preview_preregistration(request) == request
    assert task._usage == before
    task.close('driver_stopped')

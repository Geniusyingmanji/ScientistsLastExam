"""Offline record-contamination probe. Never extracts heldout structures."""
import hashlib, importlib.util, itertools, json, sys
from pathlib import Path
root=Path(sys.argv[1]); out=Path(sys.argv[2]); v=root/'benchmarks/Chemistry/CrystalStructurePolymorphSearch/verification'
spec=importlib.util.spec_from_file_location('csp_record_builder',v/'evaluator.py'); e=importlib.util.module_from_spec(spec); spec.loader.exec_module(e)
records={}
for w in e.WORLDS:
 if w['split']!='development': continue
 selected=e._reference_records(w)
 records[e._formula(w['species'])]=[r['relaxed_structure'] for r in selected]
 print('record_built',w['name'],e._utility(w,selected)[0],flush=True)
source='''"""Replay public-development witness structures; unknown compositions use baseline seeds.

Built offline from development worlds only by build_record_replay.py. This is an
explicit contamination attack, not a truth-blind reference or hidden-world search.
"""\nimport numpy as np\n\nRECORDS = '''+repr(records)+'\n\n'
baseline=(v.parent/'solution.py').read_text(); start=baseline.index('def _seed('); end=baseline.index('def search_crystals(')
source+=baseline[start:end]
source+='''def search_crystals(problem, relax_structure):
    structures = RECORDS.get(problem["formula"])
    if structures is None:
        structures = [_seed(problem, index) for index in range(3)]
    rows = []
    low, high = problem["cell_volume_bounds"]
    for seed in structures:
        lengths = np.asarray(seed["cell_lengths"], dtype=float)
        volume = np.prod(lengths)
        # Move roundoff at a cell-volume boundary into the valid interval.
        safe_volume = np.clip(volume, low + 1e-8, high - 1e-8)
        lengths = lengths * (safe_volume / volume) ** (1.0 / 3.0)
        rows.append(relax_structure({"cell_lengths": lengths.tolist(),
                                    "fractional_coordinates": seed["fractional_coordinates"]}))
    return {"candidate_ids": [row["candidate_id"] for row in rows]}
'''
out.write_text(source)
Path(str(out)+'.provenance.json').write_text(json.dumps({'source_evaluator_sha256':hashlib.sha256((v/'evaluator.py').read_bytes()).hexdigest(),'worlds':'development only','candidate_sha256':hashlib.sha256(source.encode()).hexdigest(),'offline_calls':72,'selection':'original witness exact archive objective; no heldout extraction'},indent=2))

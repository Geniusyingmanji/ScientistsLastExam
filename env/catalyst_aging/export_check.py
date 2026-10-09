"""Public-only export comparison primitive for a future assisted task.

Does not execute code, call the world, or certify fitting/scientific correctness.
The trusted caller must obtain sandbox outputs independently and enforce budget.
Not connected to the historical runner or registered as a candidate capability.
"""
import hashlib
import json
import numpy as np

PROTOCOL = 'catalyst-public-export-check-0.1'
TOLERANCE = 1e-10


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                     allow_nan=False).encode()).hexdigest()


def compare_export(reference, bound_source, specs, analysis_predictions, sandbox_predictions):
    if not isinstance(reference, dict) or set(reference) != {'name','version','sha256'}:
        raise ValueError('snapshot reference required')
    if not isinstance(bound_source, str) or not bound_source:
        raise ValueError('exact bound source required')
    if not specs or len(specs) != len(analysis_predictions) or len(specs) != len(sandbox_predictions):
        raise ValueError('one prediction per public specification required')
    maximum = 0.
    failures = []
    for i,(spec, a,b) in enumerate(zip(specs,analysis_predictions,sandbox_predictions)):
        a,b = np.asarray(a,dtype=float),np.asarray(b,dtype=float)
        shape=(len(spec['event_indices']),1)
        if a.shape != shape or b.shape != shape or not np.isfinite(a).all() or not np.isfinite(b).all():
            failures.append({'index':i,'reason':'shape_or_nonfinite'})
            continue
        difference=float(np.max(np.abs(a-b)))
        maximum=max(maximum,difference)
        if difference>TOLERANCE:
            failures.append({'index':i,'reason':'prediction_mismatch'})
    return {'protocol':PROTOCOL,'snapshot':json.loads(json.dumps(reference)),
            'bound_source_sha256':hashlib.sha256(bound_source.encode()).hexdigest(),
            'public_specs_sha256':digest(specs),'tolerance':TOLERANCE,
            'max_abs_difference':maximum,'failures':failures,'passed':not failures}


def require_validated_submission(submission, resolved_source, receipt):
    """Caller supplies its own trusted receipt, never a candidate-supplied one."""
    if set(submission) != {'model_snapshot','claims','explanation'}:
        raise ValueError('submit exact saved snapshot without replacement code')
    if receipt.get('protocol') != PROTOCOL or receipt.get('passed') is not True:
        raise ValueError('successful public export validation required')
    if submission['model_snapshot'] != receipt['snapshot']:
        raise ValueError('validated snapshot mismatch')
    if hashlib.sha256(resolved_source.encode()).hexdigest()!=receipt['bound_source_sha256']:
        raise ValueError('validated source mismatch')
    return True

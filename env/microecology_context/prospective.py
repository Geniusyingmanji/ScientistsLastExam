"""Trusted, append-only episode journal for prospective experimental evidence.

The runner must register predictions before execute and reserve experiment IDs
before obtaining observations. Candidate processes must not access this file.
This primitive does not grade scientific correctness or provide hidden feedback.
"""
import hashlib
import json
import math
import os
from pathlib import Path


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


class ProspectiveJournal:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _append(self, event, validate):
        import fcntl
        with self.path.open('a+', encoding='utf-8') as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            f.seek(0)
            entries = [json.loads(line) for line in f]
            previous = '0' * 64
            for index, item in enumerate(entries):
                digest = item.pop('sha256')
                if item['sequence'] != index or item['previous'] != previous or hashlib.sha256(canonical(item).encode()).hexdigest() != digest:
                    raise ValueError('journal integrity failure')
                item['sha256'] = digest
                previous = digest
            validate(entries)
            record = dict(event, sequence=len(entries), previous=previous)
            record['sha256'] = hashlib.sha256(canonical(record).encode()).hexdigest()
            f.write(canonical(record) + '\n')
            f.flush()
            os.fsync(f.fileno())
            return record

    def register(self, experiment_id, specification, prediction, model_sha256):
        if not isinstance(experiment_id, str) or not experiment_id:
            raise ValueError('experiment ID required')
        if not isinstance(prediction, list) or not prediction or not all(type(x) in (int, float) and math.isfinite(x) for x in prediction):
            raise ValueError('finite numeric prediction vector required')
        if not isinstance(model_sha256, str) or len(model_sha256) != 64 or any(c not in '0123456789abcdef' for c in model_sha256):
            raise ValueError('model SHA256 required')
        # Canonicalize/copy all supplied objects before storing.
        event = json.loads(canonical(dict(kind='prediction', experiment_id=experiment_id,
            specification=specification, prediction=prediction, model_sha256=model_sha256)))
        def validate(entries):
            if any(x['experiment_id'] == experiment_id for x in entries):
                raise ValueError('experiment already registered or attempted')
        return self._append(event, validate)

    def reserve(self, experiment_id, specification):
        """Call before execution, including executions that will fail."""
        if not isinstance(experiment_id, str) or not experiment_id:
            raise ValueError('experiment ID required')
        event = json.loads(canonical(dict(kind='attempt', experiment_id=experiment_id, specification=specification)))
        def validate(entries):
            matching = [x for x in entries if x['experiment_id'] == experiment_id]
            if any(x['kind'] == 'attempt' for x in matching):
                raise ValueError('experiment already attempted')
            if matching and canonical(matching[0]['specification']) != canonical(specification):
                raise ValueError('registered specification mismatch')
        return self._append(event, validate)

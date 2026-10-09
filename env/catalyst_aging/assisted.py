"""Opt-in public data/export assistance. Hidden panels are never accepted here."""
import copy
import json
import time
from .export_check import compare_export, require_validated_submission, digest


class Assistance:
    def __init__(self, common_records):
        self.records=copy.deepcopy(common_records)
        self.attempts=0
        self.receipt=None

    def initialize(self,world,instance,limits):
        if len(self.records)!=6 or digest(self.records)!=instance.get('initial_records_sha256'):
            raise ValueError('six committed common records required')
        for r in self.records:
            spec=world.validate(r['spec'])
            if r['cost']!=world.cost(spec): raise ValueError('initial cost mismatch')
            if r['observation']['axis']!=spec['event_indices']: raise ValueError('initial axis mismatch')
        if len({r['id'] for r in self.records})!=6: raise ValueError('duplicate initial ids')
        if limits['experiments']<6 or sum(r['cost'] for r in self.records)>limits['experiment_units']:
            raise ValueError('initial data exceeds budget')
        return copy.deepcopy(self.records)

    def contract(self):
        return {'protocol':'catalyst-assisted-export-0.1','initial_records_debited':6,
                'validation':'At most two validate_export actions, only during exploration. Save a model with predictor_code and parameters. Return {note,validate_export:{model_snapshot:{name,version,sha256},analysis_predictions:[values per common record]}}. Predictions must come from your analysis-side fitted function on the six common specs. Validation spends active analysis time and returns public-only consistency feedback.',
                'final':'Submit exactly that successfully validated model_snapshot, claims:[], explanation; no replacement predictor_code. Equality does not certify scientific correctness.'}

    def public_data(self):
        return {'common_records':self.records,'export_attempts':self.attempts,'latest_receipt':self.receipt}

    def parse(self,raw,default):
        value=json.loads(raw)
        if isinstance(value,dict) and set(value)=={'note','validate_export'}:
            if not isinstance(value['note'],str) or len(value['note'])>16000:raise ValueError('invalid note')
            return value
        return default(raw)

    def validate_export(self,action,store,analysis,predict_fn,directory):
        if self.attempts>=2: raise ValueError('export validation allowance exhausted')
        self.attempts+=1
        self.receipt=None
        if not isinstance(action,dict) or set(action)!={'model_snapshot','analysis_predictions'}:
            raise ValueError('invalid export action')
        if store is None:raise ValueError('snapshot API required')
        resolved,_=store.resolve_submission({'model_snapshot':action['model_snapshot'],'claims':[],'explanation':'public validation'})
        specs=[r['spec'] for r in self.records]
        code=resolved['predictor_code'];path=directory/('public-export-%d.py'%self.attempts)
        path.write_text(code)
        started=time.monotonic();available=analysis.remaining
        try:
            outputs=[]
            for spec in specs:
                remaining=available-(time.monotonic()-started)
                if remaining<=0:raise ValueError('active analysis budget exhausted')
                outputs.append(predict_fn(path,spec,min(15.,remaining)))
            self.receipt=compare_export(action['model_snapshot'],code,specs,action['analysis_predictions'],outputs)
            return self.receipt
        finally:
            analysis.remaining=max(0.,available-(time.monotonic()-started))

    def require_submission(self,submission,source):
        return require_validated_submission(submission,source,self.receipt or {})

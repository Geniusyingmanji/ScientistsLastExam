"""Opt-in public data/export assistance. Hidden panels are never accepted here."""
import copy
import json
import time
import numpy as np
from .export_check import compare_export, require_validated_submission, digest


def public_probes():
    """Fixed public histories; no World calls or private instance information."""
    terminal={'kind':'reaction','coupon_id':'A','temperature_k':500.,'feed_concentration':.6,'duration_min':8.}
    probes=[]
    for temperature, duration in ((450.,3.),(550.,14.)):
        prep=dict(terminal,temperature_k=temperature,duration_min=duration)
        events=[prep,{'kind':'blank'},{'kind':'standard'},terminal]
        for indices in ([1,2,3,4],[4]):
            probes.append({'events':copy.deepcopy(events),'event_indices':indices})
    return probes


class Assistance:
    def __init__(self, common_records):
        self.records=copy.deepcopy(common_records)
        self.attempts=0
        self.receipt=None
        self.probes=public_probes()

    def initialize(self,world,instance,limits):
        if len(self.records)!=6 or digest(self.records)!=instance.get('initial_records_sha256'):
            raise ValueError('six committed common records required')
        for spec in self.probes: world.validate(spec)
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
                'validation':'At most two validate_export actions, only during exploration. Save a model with predictor_code and parameters. Return {note,validate_export:{model_snapshot:{name,version,sha256},analysis_predictions:[values per validation_specs entry]}}. Predictions must come from your analysis-side fitted function on the six common specs followed by four public structural probes. Validation spends active analysis time and returns public-only consistency feedback.',
                'final':'Submit exactly that successfully validated model_snapshot, claims:[], explanation; no replacement predictor_code. Equality does not certify scientific correctness.'}

    def public_data(self):
        return {'validation_specs':[r['spec'] for r in self.records]+self.probes,'common_records':self.records,'export_attempts':self.attempts,'latest_receipt':self.receipt}

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
        specs=[r['spec'] for r in self.records]+self.probes
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
            residuals={}
            for record, prediction in zip(self.records,outputs):
                observed=np.asarray(record['observation']['values'],dtype=float)
                predicted=np.asarray(prediction,dtype=float)
                if observed.shape!=predicted.shape or not np.isfinite(predicted).all():
                    continue
                for row,event_index in enumerate(record['spec']['event_indices']):
                    kind=record['spec']['events'][event_index-1]['kind']
                    residuals.setdefault(kind,[]).extend((predicted[row]-observed[row]).tolist())
            self.receipt['visible_residuals_by_kind']={
                kind:{'count':len(values),'rmse':float(np.sqrt(np.mean(np.square(values))))}
                for kind,values in residuals.items()}
            self.receipt['structural_terminal_differences']=[
                float(np.asarray(outputs[6+i])[-1,0]-np.asarray(outputs[7+i])[-1,0])
                for i in (0,2)] if self.receipt['passed'] else []
            return self.receipt
        finally:
            analysis.remaining=max(0.,available-(time.monotonic()-started))

    def require_submission(self,submission,source):
        return require_validated_submission(submission,source,self.receipt or {})

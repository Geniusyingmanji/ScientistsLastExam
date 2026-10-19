"""Frozen numeric diagnostics, separate from semantic discovery judgments."""
import math

def score(grading, environment):
    n=9 if environment=='ecology' else 8
    scale=.1 if environment=='ecology' else .05
    def utility(row):
        v=row.get('rmse_by_channel')
        if not isinstance(v,list) or len(v)!=n or any(not isinstance(x,(int,float)) or not math.isfinite(x) or x<0 for x in v): return 0.
        return sum(100*max(0,1-x/scale) for x in v)/n
    def mean(rows):return sum(map(utility,rows))/len(rows) if rows else None
    return {'prediction_utility':mean(grading['rows']),'effect_utility':mean(grading['effects']),
            'scientific_score':None,'scope':'numeric diagnostic; semantic review and acquisition overlap required'}

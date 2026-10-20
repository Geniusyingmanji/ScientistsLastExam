"""New prospective protocol; historical layer contracts remain unchanged."""
from .protocol import summarize

VERSION='scientific-three-stage-process-1'
RESULT={'phenomena':20,'laws':40,'application':40}
PROCESS={'hypothesis':20,'design':30,'update':30,'verification':20}

def contract(environment):
    if environment not in ('ecology','oscillator'):raise ValueError('unsupported environment')
    return {'protocol':VERSION,'environment':environment,'objects':['law','structure'],
      'result':{'protocol':VERSION,'weights':RESULT.copy(),'criteria':{
        'phenomena':{'effect':50,'conditions':30,'uncertainty':20},
        'laws':{'dependencies':30,'functional_form':40,'quantitative_recovery':30},
        'application':{'unseen_prediction':50,'intervention':30,'scope':20}}},
      'process':{'protocol':VERSION,'weights':PROCESS.copy(),'criteria':{k:{'quality':100} for k in PROCESS}},
      'rules':['No points for counts, verbosity or private reasoning.',
        'Mechanistic correctness belongs to laws; discriminating experiment design belongs to process.',
        'No combined result/process score. Pending review is null.',
        'Public priors are not discoveries; preserve equivalence and nonidentifiability.',
        'Use only observable statements, experiments, receipts and model snapshots.']}

def review(frozen,result_decisions,process_decisions):
    return {'protocol':frozen['protocol'],
      'result':summarize(frozen['result'],result_decisions),
      'process':summarize(frozen['process'],process_decisions),
      'combined_score':None}

"""Exposed operator design; no hidden targets or claim of unseen structural holdout."""
from .world import World


def design():
    times=[0.,1.,3.,6.,12.]
    def spec(q,events=()):
        return World(0).validate({'times':times[:],'source':[{'at':0.,'fractions':q}]+list(events)})
    return {
        'schema':'isotope-exposed-design-1',
        'exposure':'public development fixtures; never label these as sealed evaluation',
        'training':[spec([.25]*4),spec([.5,0,0,.5]),spec([0,.5,.5,0]),spec([.5,0,0,.5],[{'at':3.,'fractions':[1.,0,0,0]}])],
        'panels':[
            {'kind':'new_recipe','scope':'New static recipes, same legal apparatus; not structural extrapolation.',
             'specs':[spec([.4,.1,.1,.4]),spec([.1,.4,.4,.1])]},
            {'kind':'new_history','scope':'Three-segment histories absent from training; same model family and control range.',
             'specs':[spec([.5,0,0,.5],[{'at':2.,'fractions':[1.,0,0,0]},{'at':5.,'fractions':[0,.5,.5,0]}]),spec([0,.5,.5,0],[{'at':4.,'fractions':[.5,0,0,.5]},{'at':8.,'fractions':[1.,0,0,0]}])]},
            {'kind':'ambiguity_control','scope':'Independent-position recipe cannot discriminate the two pairing accounts.',
             'specs':[spec([.16,.24,.24,.36])]},
        ],
        'structural_holdout':False,
        'scoring_status':'Design fixture only. No model score or new calibration run.'
    }

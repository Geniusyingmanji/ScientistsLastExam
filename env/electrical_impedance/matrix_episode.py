"""Trusted opt-in port-law episode; immutable ledger and no clean candidate action."""
import json
import threading
from pathlib import Path
from .world import World
from .protocol import validate_spec
from env.microecology_context.prospective import ProspectiveJournal


class MatrixEpisode:
    def __init__(self, seed, root, budget=280, max_attempts=16):
        if type(budget) is not int or budget<=0 or type(max_attempts) is not int or max_attempts<=0:
            raise ValueError('positive integer budgets required')
        self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True)
        with (self.root/'episode.json').open('x') as f:
            json.dump(dict(budget=budget,max_attempts=max_attempts),f)
        self.world=World(seed);self.budget=budget;self.max_attempts=max_attempts
        self.spent=0;self.count=0;self.ids=set();self.lock=threading.Lock()
        self.journal=ProspectiveJournal(self.root/'prospective.jsonl')

    def validate_acquisition(self, spec):
        return validate_spec(spec)

    def call(self, tool, **args):
        with self.lock:
            if tool=='describe':
                return dict(self.world.describe(),budget=dict(units=self.budget,max_attempts=self.max_attempts,
                    invalid_cost=1),prospective='Optional register_prediction before experiment: experiment_id, spec, flattened frequency-major two-channel prediction, model_sha256. No hidden feedback.')
            if tool=='register_prediction':
                spec=self.validate_acquisition(args['spec']);eid=args['experiment_id']
                if eid in self.ids:raise ValueError('already attempted')
                if len(args['prediction'])!=2*len(spec['frequencies_hz']):raise ValueError('prediction shape')
                receipt=self.journal.register(eid,spec,args['prediction'],args['model_sha256'])
                return dict(registered=eid,receipt=receipt['sha256'])
            if tool!='experiment':raise ValueError('unknown tool')
            if self.count>=self.max_attempts or self.spent>=self.budget:raise ValueError('budget exhausted')
            self.count+=1;charge=1;eid=args.get('experiment_id')
            try:
                if not isinstance(eid,str) or not eid or eid in self.ids:raise ValueError('new ID required')
                self.ids.add(eid);spec=self.validate_acquisition(args['spec']);cost=self.world.cost(spec)
                if cost>self.budget-self.spent:raise ValueError('insufficient units')
                receipt=self.journal.reserve(eid,spec)
                charge=cost
                response=self.world.run(spec,noise_key=f'attempt-{self.count}')
                response.update(experiment_id=eid,receipt=receipt['sha256'])
            except (ValueError,TypeError,KeyError):
                response={'error':'invalid request, changed registered specification, or insufficient units'}
            except Exception:
                import traceback
                with (self.root/'execution-errors.log').open('a') as f:f.write(traceback.format_exc())
                response={'error':'execution failure'}
            self.spent+=charge
            response.update(remaining_units=self.budget-self.spent,remaining_attempts=self.max_attempts-self.count)
            with (self.root/'observations.jsonl').open('a') as f:
                f.write(json.dumps(dict(attempt=self.count,cost=charge,request=args,response=response),allow_nan=False)+'\n')
            return response

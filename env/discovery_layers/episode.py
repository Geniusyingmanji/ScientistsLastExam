"""Full experiment/register/seal entry point for new layered cohorts only."""
import hashlib,json,re
from pathlib import Path
from env.microecology_context.prospective import canonical
from env.microecology_context.matrix_episode import MatrixEpisode as Ecology
from env.coupled_oscillators.matrix_episode import MatrixEpisode as Oscillator
from .protocol import contract

class LayeredEpisode:
    def __init__(self, environment, seed, root, budget=48, interaction='three_body'):
        self.base=Ecology(seed,interaction,root,budget=budget) if environment=='ecology' else Oscillator(seed,root,budget=budget)
        self.contract=contract(environment)
        with (Path(root)/'layer-contract.json').open('x') as f: json.dump(self.contract,f)

    def call(self, tool, **args):
        if tool=='describe':
            value=self.base.call(tool)
            value.pop('applicable_cells',None)
            value.update(discovery_contract=self.contract,submission='submit_discovery: claims with id, object (law/structure), level (L1..L4), statement, scope, evidence_ids; model_sha256. Final seal closes experiments. Scientific judgment is private after completion.')
            return value
        if tool=='submit_matrix': raise ValueError('use submit_discovery in this protocol')
        if tool!='submit_discovery': return self.base.call(tool,**args)
        with self.base.lock:
            if self.base.closed: raise ValueError('episode sealed')
            digest=args.get('model_sha256','')
            if not isinstance(digest,str) or not re.fullmatch('[0-9a-f]{64}',digest): raise ValueError('model hash required')
            claims=args['submission']['claims']; ids=set()
            if not isinstance(claims,list): raise ValueError('claims required')
            for c in claims:
                if c['id'] in ids or c['object'] not in ('law','structure') or c['level'] not in self.contract['weights']: raise ValueError('invalid claim')
                ids.add(c['id'])
                if any(not isinstance(c[k],str) or not c[k].strip() for k in ('id','statement','scope')): raise ValueError('claim text required')
                if not isinstance(c['evidence_ids'],list) or any(not isinstance(x,str) for x in c['evidence_ids']): raise ValueError('invalid references')
            record={'protocol':self.contract['protocol'],'submission':args['submission'],'declared_model_sha256':digest,'attempts':self.base.count,'reference_validation':'pending trusted archive review'}
            encoded=canonical(record)
            with (self.base.root/'submission.json').open('x') as f:f.write(encoded+'\n')
            self.base.closed=True
            return {'sealed':True,'receipt':hashlib.sha256(encoded.encode()).hexdigest(),'scientific_score':None}

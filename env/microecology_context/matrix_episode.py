"""Opt-in trusted episode for direct-interaction prospective experiments.

No matrix scientific scores are assigned here. Existing frozen service is unchanged.
The journal and receipts must remain outside candidate filesystem access.
"""
import json
import threading
from pathlib import Path
from .direct_kernel import DirectKernel
from .world import World, CHANNELS, validate
from .prospective import ProspectiveJournal
from .service import DESCRIPTION


class MatrixEpisode:
    def __init__(self, seed, interaction, root, budget=48):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        # Never reset budget/noise counters by reopening a prior episode.
        self.marker = self.root / 'episode.json'
        with self.marker.open('x') as f:
            json.dump({'budget': budget, 'protocol': 'prospective-direct-1'}, f)
        self.world = World(seed, 'fixed')
        self.world.kernel = DirectKernel(seed, interaction)
        self.journal = ProspectiveJournal(self.root / 'prospective.jsonl')
        self.lock = threading.Lock()
        self.budget, self.count, self.attempted = budget, 0, set()

    def call(self, tool, **args):
        with self.lock:
            if tool == 'describe':
                return dict(DESCRIPTION, budget=f'{self.budget} attempts; invalid attempts count',
                    prospective='register_prediction binds experiment_id, spec, flattened time-major channel predictions and model_sha256 before experiment. Registering is optional and provides no outcome. Predictions are immutable; no hidden feedback. experiment requires experiment_id and spec.')
            if tool == 'register_prediction':
                spec = validate(args['spec'])
                if args['experiment_id'] in self.attempted:
                    raise ValueError('experiment already attempted')
                if len(args['prediction']) != len(spec['times']) * len(CHANNELS):
                    raise ValueError('prediction must match time-major channel shape')
                receipt = self.journal.register(args['experiment_id'], spec, args['prediction'], args['model_sha256'])
                return {'registered': args['experiment_id'], 'receipt': receipt['sha256']}
            if tool != 'experiment':
                raise ValueError('unknown tool')
            if self.count >= self.budget:
                raise ValueError('experiment budget exhausted')
            self.count += 1
            experiment_id = args.get('experiment_id')
            try:
                if not isinstance(experiment_id, str) or not experiment_id or experiment_id in self.attempted:
                    raise ValueError('new experiment_id required')
                self.attempted.add(experiment_id)
                spec = validate(args['spec'])
                # This is durably recorded before observing the world.
                reservation = self.journal.reserve(experiment_id, spec)
                result = self.world.run(spec)
                result.update(experiment_id=experiment_id, receipt=reservation['sha256'])
            except (ValueError, TypeError, KeyError):
                result = {'error': 'invalid experiment or registered specification mismatch'}
            except Exception:
                # Execution failure also consumes the ID and budget; retain cause privately.
                result = {'error': 'execution failure'}
                import traceback
                with (self.root/'execution-errors.log').open('a') as f:
                    f.write(traceback.format_exc())
            result['remaining'] = self.budget - self.count
            with (self.root/'observations.jsonl').open('a') as f:
                f.write(json.dumps({'attempt': self.count, 'request': args, 'response': result}, allow_nan=False)+'\n')
            return result

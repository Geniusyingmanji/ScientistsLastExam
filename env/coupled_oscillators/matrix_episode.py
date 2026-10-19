"""Opt-in complete oscillator episode with prospective records and final seal.

Attempt-budget protocol, independent of old shared-runner cohorts. Candidate
observations always use unique noisy keys; clean targets remain operator-only.
"""
from env.microecology_context.matrix_episode import MatrixEpisode as BaseEpisode
from .world import World, CHANNELS, _validate


class MatrixEpisode(BaseEpisode):
    channels = CHANNELS

    def __init__(self, seed, root, budget=48):
        super().__init__(seed, 'pairwise', root, budget=budget)
        self.world = World(seed)

    def validate_spec(self, spec):
        return _validate(spec)

    def public_description(self):
        return dict(self.world.describe(), cost='This opt-in task uses 48 attempt units, one per experiment including invalid requests; no separate cost-unit budget.')

    def observe(self, spec):
        return self.world.run(spec, noise_key=f'matrix-attempt-{self.count}')

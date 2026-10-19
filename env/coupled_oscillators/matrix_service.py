"""Trusted oscillator HTTP service; public bridge mounts no operator code."""
import argparse
from env.microecology_context.matrix_service import serve
from .matrix_episode import MatrixEpisode

if __name__ == '__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--seed',type=int,required=True)
    p.add_argument('--out',required=True)
    p.add_argument('--port',type=int,required=True)
    a=p.parse_args()
    serve(MatrixEpisode(a.seed,a.out),a.port).serve_forever()

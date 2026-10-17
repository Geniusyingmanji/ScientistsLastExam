"""Independent electrical port service using the shared JSON HTTP transport."""
import argparse
from .matrix_episode import MatrixEpisode
from env.microecology_context.matrix_service import serve


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--seed',type=int,required=True)
    p.add_argument('--out',required=True)
    p.add_argument('--port',type=int,required=True)
    a=p.parse_args()
    serve(MatrixEpisode(a.seed,a.out),a.port).serve_forever()

if __name__=='__main__':main()

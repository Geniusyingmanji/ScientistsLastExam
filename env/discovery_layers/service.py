"""New opt-in service, preserves all old services."""
import argparse
from env.microecology_context.matrix_service import serve
from .episode import LayeredEpisode

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--environment',choices=['ecology','oscillator'],required=True)
    p.add_argument('--seed',type=int,required=True);p.add_argument('--out',required=True)
    p.add_argument('--port',type=int,required=True)
    a=p.parse_args();serve(LayeredEpisode(a.environment,a.seed,a.out),a.port).serve_forever()
if __name__=='__main__':main()

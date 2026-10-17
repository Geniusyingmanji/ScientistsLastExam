"""Trusted opt-in HTTP service; no changes to the frozen service protocol."""
import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from .matrix_episode import MatrixEpisode


def serve(episode, port):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args): pass
        def do_POST(self):
            try:
                length=int(self.headers.get('Content-Length',0))
                if not 0<length<=65536: raise ValueError('request size')
                obj=json.loads(self.rfile.read(length), parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite')))
                if not isinstance(obj,dict):raise ValueError('request object')
                tool=obj.pop('tool')
                result=episode.call(tool,**obj)
            except (ValueError,TypeError,KeyError):
                result={'error':'request rejected'}
            body=json.dumps(result,allow_nan=False).encode()
            self.send_response(200);self.send_header('Content-Type','application/json')
            self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
    return ThreadingHTTPServer(('127.0.0.1',port),Handler)


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--seed',required=True,type=int);p.add_argument('--interaction',choices=['pairwise','three_body'],required=True)
    p.add_argument('--out',required=True);p.add_argument('--port',required=True,type=int)
    a=p.parse_args();serve(MatrixEpisode(a.seed,a.interaction,a.out),a.port).serve_forever()

if __name__=='__main__':main()

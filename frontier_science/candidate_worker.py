"""Worker for one top-level task-instance session inside the candidate sandbox."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
import traceback

from frontier_science.rpc_codec import decode, encode


class RemoteCallback:
    """Candidate-side proxy for a callable explicitly exposed by the oracle."""

    def __init__(self, callback_id: str, rpc, requests):
        self.callback_id = callback_id
        self.rpc = rpc
        self.requests = requests

    def __call__(self, *args, **kwargs):
        message = {
            "type": "callback",
            "id": self.callback_id,
            "args": encode(list(args)),
            "kwargs": encode(kwargs),
        }
        print(json.dumps(message, allow_nan=False, separators=(",", ":")),
              file=self.rpc, flush=True)
        line = self.requests.readline()
        if not line:
            raise RuntimeError("callback channel closed")
        response = json.loads(line)
        if response.get("type") != "callback_result" or response.get("id") != self.callback_id:
            raise RuntimeError("invalid callback response")
        if not response.get("ok"):
            raise RuntimeError(str(response.get("error", "trusted callback failed")))
        return decode(response.get("result"))


def _decode_call(value, rpc, requests):
    if isinstance(value, dict) and value.get("__fs_type__") == "callback":
        if set(value) != {"__fs_type__", "id"} or not isinstance(value["id"], str):
            raise TypeError("invalid callback handle")
        return RemoteCallback(value["id"], rpc, requests)
    if isinstance(value, list):
        return [_decode_call(v, rpc, requests) for v in value]
    if isinstance(value, dict):
        if value.get("__fs_type__") == "tuple":
            return tuple(_decode_call(v, rpc, requests) for v in value.get("items", []))
        if value.get("__fs_type__") == "mapping":
            return {_decode_call(pair[0], rpc, requests): _decode_call(pair[1], rpc, requests)
                    for pair in value.get("items", [])}
        if value.get("__fs_type__") in {"ndarray", "complex"}:
            return decode(value)
        return {k: _decode_call(v, rpc, requests) for k, v in value.items()}
    return decode(value)


def _encode_result(value, functions):
    if callable(value):
        handle = "fn%d" % len(functions)
        functions[handle] = value
        return {"__fs_type__": "remote_callable", "id": handle}
    if isinstance(value, list):
        return [_encode_result(v, functions) for v in value]
    if isinstance(value, tuple):
        return {"__fs_type__": "tuple", "items": [_encode_result(v, functions) for v in value]}
    if isinstance(value, dict):
        if all(isinstance(k, str) for k in value):
            return {k: _encode_result(v, functions) for k, v in value.items()}
        return {"__fs_type__": "mapping", "items": [
            [_encode_result(k, functions), _encode_result(v, functions)] for k, v in value.items()
        ]}
    return encode(value)


def _load_callable(path: str, entrypoint: str):
    spec = importlib.util.spec_from_file_location("fs_candidate", path)
    if spec is None or spec.loader is None:
        raise ImportError("cannot load candidate")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    fn = getattr(module, entrypoint)
    if not callable(fn):
        raise TypeError("candidate entrypoint is not callable")
    return fn


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--entrypoint", required=True)
    args = parser.parse_args()
    # Candidate stdout/stderr must never share the framed RPC channel.  A duplicate
    # of the original stdout is retained privately for worker responses.
    rpc_fd = os.dup(sys.stdout.fileno())
    rpc = os.fdopen(rpc_fd, "w", buffering=1)
    sink_fd = os.open("/dev/null", os.O_WRONLY)
    os.dup2(sink_fd, 1)
    os.dup2(sink_fd, 2)
    os.close(sink_fd)
    try:
        fn = _load_callable(args.candidate, args.entrypoint)
    except BaseException as exc:
        print(json.dumps({"ready": False, "error": "%s: %s" % (type(exc).__name__, exc)}), file=rpc, flush=True)
        return 2
    print(json.dumps({"ready": True}), file=rpc, flush=True)
    functions = {"entrypoint": fn}
    for line in sys.stdin:
        try:
            request = json.loads(line)
            call_args = _decode_call(request.get("args", []), rpc, sys.stdin)
            call_kwargs = _decode_call(request.get("kwargs", {}), rpc, sys.stdin)
            if not isinstance(call_args, list) or not isinstance(call_kwargs, dict):
                raise TypeError("bad call payload")
            target = request.get("target", "entrypoint")
            if target not in functions:
                raise KeyError("unknown callable handle")
            result = functions[target](*call_args, **call_kwargs)
            response = {"ok": True, "result": _encode_result(result, functions)}
        except BaseException as exc:
            response = {
                "ok": False,
                "error": "%s: %s" % (type(exc).__name__, exc),
                "traceback": traceback.format_exc(limit=8)[-4000:],
            }
        print(json.dumps(response, allow_nan=False, separators=(",", ":")), file=rpc, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

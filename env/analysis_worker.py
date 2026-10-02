"""Only this file is mounted as candidate code; no simulator or operator state."""
import contextlib
import io
import json

_namespace = {"__name__": "__scientific_analysis__"}


class _BoundedText(io.StringIO):
    def write(self, text):
        super().write(str(text)[:max(0, 32000-self.tell())])
        return len(text)


def analyze(payload):
    _namespace.update({k: payload[k] for k in ("problem", "records", "history")})
    # Optional RPC capabilities refer only to this episode's candidate-owned
    # snapshot store. They carry no filesystem or simulator authority.
    model_api = payload.get("model_api", {})
    for name in ("save_model", "read_model", "list_models"):
        _namespace.pop(name, None)
        if name in model_api:
            _namespace[name] = model_api[name]
    _namespace["result"] = None
    out = _BoundedText()
    phase = "execution"
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            exec(payload["code"], _namespace, _namespace)
        phase = "result_serialization"
        encoded = json.dumps(_namespace.get("result"), allow_nan=False)
        if len(encoded) > 64000:
            return {"ok": False, "error": "result_too_large", "stdout": out.getvalue()}
        return {"ok": True, "result": json.loads(encoded), "stdout": out.getvalue()}
    except Exception as exc:
        # Candidate code and its public payload are the only inputs here. Give
        # enough feedback to repair an analysis without exposing operator traces.
        line = None
        trace = exc.__traceback__
        while trace is not None:
            if trace.tb_frame.f_code.co_filename == "<string>":
                line = trace.tb_lineno
            trace = trace.tb_next
        if isinstance(exc, SyntaxError) and exc.filename == "<string>":
            line = exc.lineno
        return {"ok": False, "error": type(exc).__name__,
                "message": str(exc)[:600], "phase": phase,
                "candidate_line": line, "stdout": out.getvalue()}

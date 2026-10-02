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
    _namespace["result"] = None
    out = _BoundedText()
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            exec(payload["code"], _namespace, _namespace)
        encoded = json.dumps(_namespace.get("result"), allow_nan=False)
        if len(encoded) > 64000:
            return {"ok": False, "error": "result_too_large", "stdout": out.getvalue()}
        return {"ok": True, "result": json.loads(encoded), "stdout": out.getvalue()}
    except Exception as exc:
        return {"ok": False, "error": type(exc).__name__, "stdout": out.getvalue()}

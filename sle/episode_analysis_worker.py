"""Executed only inside the existing CandidateProxy Linux sandbox."""
import contextlib
import io
import json

_namespace = {"__name__": "__episode_analysis__"}


class _BoundedText(io.StringIO):
    def write(self, text):
        remaining = max(0, 64000 - self.tell())
        super().write(str(text)[:remaining])
        return len(text)


def analyze(payload):
    _namespace.update({key: payload[key] for key in ("problem", "history", "public_files")})
    _namespace["result"] = None
    out = _BoundedText()
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            exec(payload["code"], _namespace, _namespace)
        # The scalar/structured result must be explicitly chosen by the agent.
        result = json.loads(json.dumps(_namespace.get("result"), allow_nan=False))
        return {"ok": True, "stdout": out.getvalue(), "result": result}
    except Exception as exc:
        return {"ok": False, "stdout": out.getvalue(), "error": type(exc).__name__}

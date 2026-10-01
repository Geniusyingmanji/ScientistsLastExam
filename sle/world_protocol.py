"""Small public JSON contract shared by the first virtual-world prototype."""
from __future__ import annotations

import hashlib
import json
import math


API_VERSION = "sle-world-v1"


class InvalidAction(ValueError):
    """Messages contain public argument/handle information only."""


def clone(value):
    text = json.dumps(value, allow_nan=False, ensure_ascii=False, sort_keys=True)
    if len(text.encode()) > 2_000_000:
        raise InvalidAction("payload_too_large")
    return json.loads(text)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def number(value, low, high, name):
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value) or not low <= value <= high):
        raise InvalidAction("invalid_" + name)
    return float(value)


def keys(value, required, optional=()):
    if not isinstance(value, dict) or not set(required) <= set(value) or set(value) - set(required) - set(optional):
        raise InvalidAction("invalid_fields")


def identifier(value):
    if not isinstance(value, str) or not 1 <= len(value) <= 100 or not all(c.isalnum() or c in "-_." for c in value):
        raise InvalidAction("invalid_identifier")
    return value


class EventLog:
    def __init__(self):
        self.events = []

    def append(self, kind, payload):
        event = {"seq": len(self.events), "kind": kind, "payload": clone(payload),
                 "previous_sha256": self.events[-1]["sha256"] if self.events else None}
        event["sha256"] = digest(event)
        self.events.append(event)
        return event["sha256"]

    @staticmethod
    def validate(events):
        previous = None
        for seq, event in enumerate(events):
            if event["seq"] != seq or event["previous_sha256"] != previous:
                raise ValueError("broken_event_order")
            if digest({k: v for k, v in event.items() if k != "sha256"}) != event["sha256"]:
                raise ValueError("altered_event")
            previous = event["sha256"]
        return True

"""Durable process-safe attempt accounting, shared by all campaign cohorts."""
import json
import os
import sqlite3
import time
from pathlib import Path


class AttemptBudgetExceeded(RuntimeError):
    pass


class CampaignLedger:
    def __init__(self, path, limit=None):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS metadata (name TEXT PRIMARY KEY, value TEXT NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS attempts (id INTEGER PRIMARY KEY, episode TEXT NOT NULL, started REAL NOT NULL, finished REAL, status TEXT NOT NULL, request_sha256 TEXT NOT NULL, detail TEXT)")
            row = db.execute("SELECT value FROM metadata WHERE name='attempt_limit'").fetchone()
            if row is None:
                if type(limit) is not int or limit <= 0:
                    raise ValueError("new ledger requires a positive attempt limit")
                db.execute("INSERT INTO metadata VALUES ('attempt_limit',?)", (str(limit),))
            elif limit is not None and int(row[0]) != limit:
                raise ValueError("existing campaign cap is immutable; never reset a ledger")
        os.chmod(str(self.path), 0o600)

    def _connect(self):
        db = sqlite3.connect(str(self.path), timeout=20)
        db.execute("PRAGMA busy_timeout=20000")
        return db

    def reserve(self, episode, request_sha256, *, active_limit=8, rpm=60, wait_seconds=180):
        """Reserve once before any network I/O; uncertain calls remain charged."""
        deadline = time.monotonic() + wait_seconds
        while True:
            with self._connect() as db:
                db.execute("BEGIN IMMEDIATE")
                limit = int(db.execute("SELECT value FROM metadata WHERE name='attempt_limit'").fetchone()[0])
                total = db.execute("SELECT count(*) FROM attempts").fetchone()[0]
                if total >= limit:
                    raise AttemptBudgetExceeded("campaign attempt budget exhausted")
                active = db.execute("SELECT count(*) FROM attempts WHERE status='started'").fetchone()[0]
                recent = db.execute("SELECT count(*) FROM attempts WHERE started>?", (time.time()-60,)).fetchone()[0]
                if active < active_limit and recent < rpm:
                    cursor = db.execute("INSERT INTO attempts (episode,started,status,request_sha256) VALUES (?,?,'started',?)", (episode, time.time(), request_sha256))
                    return cursor.lastrowid
            if time.monotonic() >= deadline:
                raise TimeoutError("campaign admission deadline exhausted before network I/O")
            time.sleep(.25)

    def finish(self, attempt_id, status, detail):
        if status not in ("returned", "failed", "interrupted"):
            raise ValueError("invalid terminal attempt status")
        encoded = json.dumps(detail, ensure_ascii=False, allow_nan=False)
        with self._connect() as db:
            changed = db.execute("UPDATE attempts SET finished=?,status=?,detail=? WHERE id=? AND status='started'", (time.time(), status, encoded, attempt_id)).rowcount
            if changed != 1:
                raise ValueError("attempt missing or already finalized")

    def summary(self):
        with self._connect() as db:
            limit = int(db.execute("SELECT value FROM metadata WHERE name='attempt_limit'").fetchone()[0])
            counts = dict(db.execute("SELECT status,count(*) FROM attempts GROUP BY status"))
            per_episode = dict(db.execute("SELECT episode,count(*) FROM attempts GROUP BY episode"))
        total = sum(counts.values())
        return {"attempt_limit": limit, "started_attempts": total, "remaining_attempts": limit-total,
                "status_counts": counts, "attempts_by_episode": per_episode, "automatic_retries": 0}

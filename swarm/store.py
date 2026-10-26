"""Durable run records and evidence, without transient success claims."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import sqlite3
import threading
from datetime import datetime, timezone
import uuid


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


class RunStore:
    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir).resolve()
        self.data_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        self._lock = threading.RLock()
        self._db = sqlite3.connect(self.data_dir / "runs.sqlite3", check_same_thread=False)
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("PRAGMA synchronous=FULL")
        self._db.executescript("""
            CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, data TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL, timestamp TEXT NOT NULL,
                kind TEXT NOT NULL, actor TEXT NOT NULL,
                message TEXT NOT NULL, detail TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS events_run ON events(run_id, id);
        """)
        self._db.commit()

    def create_run(self, values: dict) -> dict:
        now = utc_now()
        run = dict(values)
        run.update(id="r_" + uuid.uuid4().hex[:16], status="queued", stage="queued",
                   created_at=now, updated_at=now, model_calls=0, attempt=0,
                   checks=[], artifacts=[], workers={}, pause_requested=False,
                   cancel_requested=False)
        run.setdefault("max_attempts", 3)
        run.setdefault("max_model_calls", 24)
        run.setdefault("test_timeout", 120)
        run.setdefault("symbol", "")
        run.setdefault("test_command", "")
        with self._lock:
            self._db.execute("INSERT INTO runs(id,data) VALUES (?,?)", (run["id"], json.dumps(run)))
            self._db.commit()
        return run

    def get_run(self, run_id: str) -> dict:
        self._validate_id(run_id)
        with self._lock:
            row = self._db.execute("SELECT data FROM runs WHERE id=?", (run_id,)).fetchone()
        if row is None:
            raise KeyError("Run was not found.")
        return json.loads(row[0])

    def list_runs(self) -> list[dict]:
        with self._lock:
            rows = self._db.execute("SELECT data FROM runs ORDER BY rowid DESC").fetchall()
        return [json.loads(row[0]) for row in rows]

    def update_run(self, run_id: str, **fields) -> dict:
        if "id" in fields and fields["id"] != run_id:
            raise ValueError("A run identifier cannot change.")
        with self._lock:
            run = self.get_run(run_id)
            run.update(fields)
            run["updated_at"] = utc_now()
            encoded = json.dumps(run, allow_nan=False)
            self._db.execute("UPDATE runs SET data=? WHERE id=?", (encoded, run_id))
            self._db.commit()
            return run

    def add_event(self, run_id: str, kind: str, actor: str, message: str, detail=None) -> dict:
        timestamp = utc_now()
        detail = {} if detail is None else detail
        with self._lock:
            self.get_run(run_id)
            cursor = self._db.execute(
                "INSERT INTO events(run_id,timestamp,kind,actor,message,detail) VALUES (?,?,?,?,?,?)",
                (run_id, timestamp, kind, actor, message, json.dumps(detail, allow_nan=False)))
            self._db.commit()
            return dict(id=cursor.lastrowid, run_id=run_id, timestamp=timestamp,
                        kind=kind, actor=actor, message=message, detail=detail)

    def events(self, run_id: str, after: int = 0) -> list[dict]:
        self.get_run(run_id)
        if not isinstance(after, int) or after < 0:
            raise ValueError("The event cursor must be a nonnegative integer.")
        with self._lock:
            rows = self._db.execute(
                "SELECT id,timestamp,kind,actor,message,detail FROM events WHERE run_id=? AND id>? ORDER BY id LIMIT 500",
                (run_id, after)).fetchall()
        return [dict(id=r[0], run_id=run_id, timestamp=r[1], kind=r[2], actor=r[3],
                     message=r[4], detail=json.loads(r[5])) for r in rows]

    @staticmethod
    def _validate_id(run_id: str):
        if not isinstance(run_id, str) or not re.fullmatch(r"r_[a-f0-9]{16}", run_id):
            raise ValueError("Invalid run identifier.")

    def artifact_path(self, run_id: str, name: str) -> Path:
        self._validate_id(run_id)
        if not isinstance(name, str) or len(name) > 240 or "\\" in name:
            raise ValueError("Invalid evidence filename.")
        parts = PurePosixPath(name).parts
        if not parts or any(not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", p) for p in parts):
            raise ValueError("Evidence must stay inside its run folder.")
        base = self.data_dir / "runs" / run_id / "artifacts"
        candidate = base.joinpath(*parts)
        if not candidate.resolve().is_relative_to(base.resolve()):
            raise ValueError("Evidence path is outside its run folder.")
        return candidate

    def save_artifact(self, run_id: str, name: str, text: str) -> str:
        self.get_run(run_id)
        path = self.artifact_path(run_id, name)
        contents = text.encode("utf-8")
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with self._lock:
            temporary = path.with_name(path.name + ".writing-" + uuid.uuid4().hex[:8])
            with open(temporary, "xb") as handle:
                os.chmod(temporary, 0o600)
                handle.write(contents)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
            run = self.get_run(run_id)
            artifacts = [a for a in run.get("artifacts", []) if a.get("name") != name]
            artifacts.append(dict(name=name, size_bytes=len(contents),
                                  sha256=hashlib.sha256(contents).hexdigest(), updated_at=utc_now()))
            self.update_run(run_id, artifacts=artifacts)
        return name

    def read_artifact(self, run_id: str, name: str) -> str:
        run = self.get_run(run_id)
        if name not in {a["name"] for a in run.get("artifacts", [])}:
            raise KeyError("Evidence was not found.")
        return self.artifact_path(run_id, name).read_text(encoding="utf-8")

    def mark_interrupted(self):
        for run in self.list_runs():
            if run["status"] in {"queued", "running", "reviewing", "pausing", "paused", "stopping"}:
                self.update_run(run["id"], status="interrupted", pause_requested=False,
                                cancel_requested=False, next_action="Resume this run to continue from its saved evidence.")
                self.add_event(run["id"], "interrupted", "system",
                               "The server restarted. Saved work and evidence are available.")

    def close(self):
        with self._lock:
            self._db.close()

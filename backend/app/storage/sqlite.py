"""SQLite persistence and audit ledger."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Generator, Optional

from app.models import Incident, RemediationAction, ReplayEvent

SCHEMA = """
CREATE TABLE IF NOT EXISTS dataset_imports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    row_count INTEGER NOT NULL,
    imported_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS replay_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    dataset_id INTEGER,
    current_seq INTEGER DEFAULT 0,
    status TEXT DEFAULT 'idle',
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS incidents (
    incident_id TEXT PRIMARY KEY,
    started_at TEXT NOT NULL,
    status TEXT NOT NULL,
    payload TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS remediation_actions (
    action_id TEXT PRIMARY KEY,
    incident_id TEXT NOT NULL,
    payload TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (incident_id) REFERENCES incidents(incident_id)
);

CREATE TABLE IF NOT EXISTS audit_ledger (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    prev_hash TEXT NOT NULL,
    entry_hash TEXT NOT NULL,
    event_type TEXT NOT NULL,
    payload TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS replay_events (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    payload TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS remediation_feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    action_id TEXT NOT NULL,
    incident_id TEXT NOT NULL,
    grade TEXT NOT NULL,
    outcome TEXT NOT NULL,
    detail TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


class Storage:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @contextmanager
    def _conn(self) -> Generator[sqlite3.Connection, None, None]:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.executescript(SCHEMA)
            conn.execute(
                "INSERT OR IGNORE INTO replay_state (id, current_seq, status) VALUES (1, 0, 'idle')"
            )

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _append_audit(self, conn: sqlite3.Connection, event_type: str, payload: dict) -> None:
        row = conn.execute(
            "SELECT entry_hash FROM audit_ledger ORDER BY seq DESC LIMIT 1"
        ).fetchone()
        prev_hash = row["entry_hash"] if row else "0" * 64
        body = json.dumps({"event_type": event_type, "payload": payload}, sort_keys=True)
        entry_hash = hashlib.sha256((prev_hash + body).encode()).hexdigest()
        conn.execute(
            "INSERT INTO audit_ledger (prev_hash, entry_hash, event_type, payload, created_at) VALUES (?,?,?,?,?)",
            (prev_hash, entry_hash, event_type, body, self._now()),
        )

    def reset_for_replay(self) -> None:
        """Clear run-scoped rows so each replay starts from a clean slate."""
        with self._conn() as conn:
            conn.execute("DELETE FROM replay_events")
            conn.execute("DELETE FROM incidents")
            conn.execute("DELETE FROM remediation_actions")
            conn.execute("DELETE FROM remediation_feedback")
            conn.execute(
                "UPDATE replay_state SET current_seq=0, status='replaying', updated_at=? WHERE id=1",
                (self._now(),),
            )
            self._append_audit(conn, "replay_reset", {"reason": "new_replay_session"})

    def import_dataset(self, path: str, content_hash: str, row_count: int) -> int:
        with self._conn() as conn:
            existing = conn.execute(
                "SELECT id FROM dataset_imports WHERE content_hash=? ORDER BY id DESC LIMIT 1",
                (content_hash,),
            ).fetchone()
            if existing:
                conn.execute(
                    "UPDATE replay_state SET dataset_id=?, status='ready', updated_at=? WHERE id=1",
                    (existing["id"], self._now()),
                )
                conn.execute("DELETE FROM replay_events")
                conn.execute("DELETE FROM incidents")
                conn.execute("DELETE FROM remediation_actions")
                conn.execute("DELETE FROM remediation_feedback")
                return existing["id"]
            cur = conn.execute(
                "INSERT INTO dataset_imports (path, content_hash, row_count, imported_at) VALUES (?,?,?,?)",
                (path, content_hash, row_count, self._now()),
            )
            dataset_id = cur.lastrowid
            conn.execute(
                "UPDATE replay_state SET dataset_id=?, current_seq=0, status='ready', updated_at=? WHERE id=1",
                (dataset_id, self._now()),
            )
            conn.execute("DELETE FROM replay_events")
            conn.execute("DELETE FROM incidents")
            conn.execute("DELETE FROM remediation_actions")
            self._append_audit(conn, "dataset_import", {"dataset_id": dataset_id, "path": path})
            return dataset_id

    def save_incident(self, incident: Incident) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO incidents (incident_id, started_at, status, payload, created_at) VALUES (?,?,?,?,?)",
                (
                    incident.incident_id,
                    incident.started_at,
                    incident.status,
                    incident.model_dump_json(),
                    self._now(),
                ),
            )
            self._append_audit(conn, "incident", incident.model_dump())

    def save_action(self, action: RemediationAction) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO remediation_actions (action_id, incident_id, payload, created_at) VALUES (?,?,?,?)",
                (action.action_id, action.incident_id, action.model_dump_json(), self._now()),
            )
            self._append_audit(conn, "remediation", action.model_dump())

    def append_replay_event(self, event: ReplayEvent) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO replay_events (event_type, timestamp, payload) VALUES (?,?,?)",
                (event.event_type, event.timestamp, json.dumps(event.data)),
            )
            conn.execute(
                "UPDATE replay_state SET current_seq=current_seq+1, updated_at=? WHERE id=1",
                (self._now(),),
            )

    def get_replay_state(self) -> dict:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM replay_state WHERE id=1").fetchone()
            return dict(row) if row else {}

    def list_incidents(self) -> list[Incident]:
        with self._conn() as conn:
            rows = conn.execute("SELECT payload FROM incidents ORDER BY started_at").fetchall()
            return [Incident.model_validate_json(r["payload"]) for r in rows]

    def list_actions(self) -> list[RemediationAction]:
        with self._conn() as conn:
            rows = conn.execute("SELECT payload FROM remediation_actions ORDER BY created_at").fetchall()
            return [RemediationAction.model_validate_json(r["payload"]) for r in rows]

    def get_audit_chain(self, limit: int = 50) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT seq, prev_hash, entry_hash, event_type, payload, created_at FROM audit_ledger ORDER BY seq DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]

    def record_feedback(
        self,
        action_id: str,
        incident_id: str,
        grade: str,
        outcome: str,
        detail: str,
    ) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO remediation_feedback (action_id, incident_id, grade, outcome, detail, created_at) VALUES (?,?,?,?,?,?)",
                (action_id, incident_id, grade, outcome, detail, self._now()),
            )
            self._append_audit(
                conn,
                "remediation_feedback",
                {"action_id": action_id, "incident_id": incident_id, "grade": grade, "outcome": outcome, "detail": detail},
            )

    def feedback_outcomes(self) -> dict[str, str]:
        """Map domain:verdict keys to latest outcome for planner learning."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT grade, outcome FROM remediation_feedback ORDER BY id DESC LIMIT 100"
            ).fetchall()
        return {r["grade"]: r["outcome"] for r in rows}

    def list_feedback(self, limit: int = 50) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM remediation_feedback ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]

from __future__ import annotations

import csv
import hashlib
import html
import io
import json
import os
import re
import shutil
import sqlite3
import tempfile
import threading
import uuid
import zipfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from paths import USER_DATA_DIR


RESEARCH_SCHEMA_VERSION = "1.0"
SESSION_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{7,127}$")
USERNAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{1,31}$")
SENSITIVE_KEY_PATTERN = re.compile(
    r"password|passwd|secret|token|api[_-]?key|authorization|cookie",
    re.IGNORECASE,
)
MAX_STRING_LENGTH = 250_000
MAX_COLLECTION_ITEMS = 1_000


def research_enabled() -> bool:
    return os.getenv("APP_RESEARCH_LOGGING_ENABLED", "false").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def research_consent_required() -> bool:
    return os.getenv("APP_RESEARCH_CONSENT_REQUIRED", "true").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def research_consent_version() -> str:
    return os.getenv("APP_RESEARCH_CONSENT_VERSION", "2026-09-01-v1").strip()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def safe_username(username: str) -> str:
    normalized = str(username or "").strip().lower()
    if not USERNAME_PATTERN.fullmatch(normalized):
        raise ValueError("invalid research username")
    return normalized


def safe_session_id(session_id: str | None) -> str:
    normalized = str(session_id or "").strip()
    if not SESSION_ID_PATTERN.fullmatch(normalized):
        raise ValueError("invalid research session id")
    return normalized


def sanitize_payload(value: Any, *, key: str = "", depth: int = 0) -> Any:
    if SENSITIVE_KEY_PATTERN.search(key):
        return "[redacted]"
    if depth > 12:
        return "[maximum depth reached]"
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        if len(value) <= MAX_STRING_LENGTH:
            return value
        return value[:MAX_STRING_LENGTH] + f"...[truncated {len(value) - MAX_STRING_LENGTH} chars]"
    if isinstance(value, dict):
        return {
            str(item_key)[:200]: sanitize_payload(
                item_value,
                key=str(item_key),
                depth=depth + 1,
            )
            for item_key, item_value in list(value.items())[:MAX_COLLECTION_ITEMS]
        }
    if isinstance(value, (list, tuple, set)):
        return [
            sanitize_payload(item, depth=depth + 1)
            for item in list(value)[:MAX_COLLECTION_ITEMS]
        ]
    return sanitize_payload(str(value), key=key, depth=depth + 1)


def _json(value: Any) -> str:
    return json.dumps(
        sanitize_payload(value),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _csv_bytes(rows: list[dict[str, Any]], fieldnames: list[str]) -> bytes:
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({field: _csv_safe(row.get(field, "")) for field in fieldnames})
    return output.getvalue().encode("utf-8-sig")


def _csv_safe(value: Any) -> Any:
    if isinstance(value, str) and value.startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


class ResearchStore:
    def __init__(self, root: Path | None = None):
        self.root = Path(root or (USER_DATA_DIR / "research"))
        self.root.mkdir(parents=True, exist_ok=True)
        self.db_path = self.root / "research.sqlite3"
        self._schema_lock = threading.Lock()
        self._write_lock = threading.RLock()
        self._schema_ready = False
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA synchronous = NORMAL")
        return connection

    @contextmanager
    def _connection(self):
        connection = self._connect()
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def _ensure_schema(self) -> None:
        if self._schema_ready:
            return
        with self._schema_lock:
            if self._schema_ready:
                return
            with self._connection() as connection:
                connection.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS participants (
                        username TEXT PRIMARY KEY,
                        first_login_at TEXT,
                        last_login_at TEXT,
                        last_seen_at TEXT,
                        login_count INTEGER NOT NULL DEFAULT 0,
                        consent_version TEXT,
                        consented_at TEXT,
                        created_at TEXT NOT NULL
                    );

                    CREATE TABLE IF NOT EXISTS sessions (
                        session_id TEXT PRIMARY KEY,
                        username TEXT NOT NULL,
                        started_at TEXT NOT NULL,
                        ended_at TEXT,
                        last_seen_at TEXT NOT NULL,
                        active_ms INTEGER NOT NULL DEFAULT 0,
                        idle_ms INTEGER NOT NULL DEFAULT 0,
                        end_reason TEXT,
                        client_metadata_json TEXT NOT NULL DEFAULT '{}',
                        FOREIGN KEY(username) REFERENCES participants(username)
                    );

                    CREATE TABLE IF NOT EXISTS events (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        event_id TEXT UNIQUE,
                        username TEXT NOT NULL,
                        session_id TEXT,
                        event_type TEXT NOT NULL,
                        source TEXT NOT NULL,
                        occurred_at TEXT NOT NULL,
                        received_at TEXT NOT NULL,
                        stage TEXT,
                        payload_json TEXT NOT NULL DEFAULT '{}',
                        FOREIGN KEY(username) REFERENCES participants(username),
                        FOREIGN KEY(session_id) REFERENCES sessions(session_id)
                    );

                    CREATE TABLE IF NOT EXISTS artifacts (
                        artifact_id TEXT PRIMARY KEY,
                        username TEXT NOT NULL,
                        session_id TEXT,
                        category TEXT NOT NULL,
                        original_name TEXT,
                        stored_path TEXT NOT NULL,
                        mime_type TEXT,
                        byte_size INTEGER NOT NULL,
                        sha256 TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        metadata_json TEXT NOT NULL DEFAULT '{}',
                        FOREIGN KEY(username) REFERENCES participants(username),
                        FOREIGN KEY(session_id) REFERENCES sessions(session_id)
                    );

                    CREATE INDEX IF NOT EXISTS idx_sessions_username_started
                        ON sessions(username, started_at);
                    CREATE INDEX IF NOT EXISTS idx_events_username_received
                        ON events(username, received_at);
                    CREATE INDEX IF NOT EXISTS idx_events_session_received
                        ON events(session_id, received_at);
                    CREATE INDEX IF NOT EXISTS idx_events_type
                        ON events(event_type);
                    CREATE INDEX IF NOT EXISTS idx_artifacts_username_created
                        ON artifacts(username, created_at);
                    """
                )
            self._schema_ready = True

    def ensure_participant(self, username: str) -> str:
        username = safe_username(username)
        now = utc_now()
        with self._write_lock, self._connection() as connection:
            connection.execute(
                """
                INSERT INTO participants(username, created_at, last_seen_at)
                VALUES (?, ?, ?)
                ON CONFLICT(username) DO UPDATE SET last_seen_at = excluded.last_seen_at
                """,
                (username, now, now),
            )
        return username

    def record_auth_event(
        self,
        username: str,
        event_type: str,
        *,
        payload: dict[str, Any] | None = None,
        consent_version: str | None = None,
        consented_at: str | None = None,
    ) -> None:
        username = safe_username(username)
        now = utc_now()
        login_event = event_type == "auth_login_succeeded"
        with self._write_lock, self._connection() as connection:
            connection.execute(
                """
                INSERT INTO participants(
                    username, first_login_at, last_login_at, last_seen_at,
                    login_count, consent_version, consented_at, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(username) DO UPDATE SET
                    first_login_at = COALESCE(participants.first_login_at, excluded.first_login_at),
                    last_login_at = COALESCE(excluded.last_login_at, participants.last_login_at),
                    last_seen_at = excluded.last_seen_at,
                    login_count = participants.login_count + excluded.login_count,
                    consent_version = COALESCE(excluded.consent_version, participants.consent_version),
                    consented_at = COALESCE(excluded.consented_at, participants.consented_at)
                """,
                (
                    username,
                    now if login_event else None,
                    now if login_event else None,
                    now,
                    1 if login_event else 0,
                    consent_version,
                    consented_at,
                    now,
                ),
            )
            connection.execute(
                """
                INSERT INTO events(
                    event_id, username, session_id, event_type, source,
                    occurred_at, received_at, stage, payload_json
                ) VALUES (?, ?, NULL, ?, 'backend', ?, ?, NULL, ?)
                """,
                (uuid.uuid4().hex, username, event_type, now, now, _json(payload or {})),
            )

    def start_session(
        self,
        username: str,
        requested_session_id: str,
        *,
        client_started_at: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        username = safe_username(username)
        session_id = safe_session_id(requested_session_id)
        now = utc_now()
        started_at = str(client_started_at or now)[:64]
        with self._write_lock, self._connection() as connection:
            connection.execute(
                """
                INSERT INTO participants(username, created_at, last_seen_at)
                VALUES (?, ?, ?)
                ON CONFLICT(username) DO UPDATE SET last_seen_at = excluded.last_seen_at
                """,
                (username, now, now),
            )
            existing = connection.execute(
                "SELECT username, ended_at FROM sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            if existing and (existing["username"] != username or existing["ended_at"]):
                session_id = f"session-{uuid.uuid4().hex}"
            connection.execute(
                """
                INSERT INTO sessions(
                    session_id, username, started_at, last_seen_at, client_metadata_json
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    last_seen_at = excluded.last_seen_at,
                    client_metadata_json = excluded.client_metadata_json
                """,
                (session_id, username, started_at, now, _json(metadata or {})),
            )
            connection.execute(
                """
                INSERT OR IGNORE INTO events(
                    event_id, username, session_id, event_type, source,
                    occurred_at, received_at, stage, payload_json
                ) VALUES (?, ?, ?, 'session_started', 'backend', ?, ?, NULL, ?)
                """,
                (
                    f"session-start-{session_id}",
                    username,
                    session_id,
                    started_at,
                    now,
                    _json(metadata or {}),
                ),
            )
        return session_id

    def _assert_session(
        self,
        connection: sqlite3.Connection,
        username: str,
        session_id: str,
    ) -> None:
        row = connection.execute(
            "SELECT username FROM sessions WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        if not row or row["username"] != username:
            raise ValueError("research session does not belong to the authenticated user")

    def append_events(
        self,
        username: str,
        session_id: str,
        events: Iterable[dict[str, Any]],
    ) -> int:
        username = safe_username(username)
        session_id = safe_session_id(session_id)
        now = utc_now()
        accepted = 0
        with self._write_lock, self._connection() as connection:
            self._assert_session(connection, username, session_id)
            for event in events:
                event_id = str(event.get("event_id") or uuid.uuid4().hex)[:128]
                event_type = str(event.get("event_type") or "unknown")[:120]
                source = str(event.get("source") or "frontend")[:40]
                occurred_at = str(event.get("occurred_at") or now)[:64]
                stage = str(event.get("stage") or "")[:40] or None
                cursor = connection.execute(
                    """
                    INSERT OR IGNORE INTO events(
                        event_id, username, session_id, event_type, source,
                        occurred_at, received_at, stage, payload_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        event_id,
                        username,
                        session_id,
                        event_type,
                        source,
                        occurred_at,
                        now,
                        stage,
                        _json(event.get("payload") or {}),
                    ),
                )
                accepted += int(cursor.rowcount > 0)
            connection.execute(
                "UPDATE sessions SET last_seen_at = ? WHERE session_id = ?",
                (now, session_id),
            )
            connection.execute(
                "UPDATE participants SET last_seen_at = ? WHERE username = ?",
                (now, username),
            )
        return accepted

    def record_server_event(
        self,
        username: str,
        event_type: str,
        *,
        session_id: str | None = None,
        stage: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        username = self.ensure_participant(username)
        now = utc_now()
        normalized_session = None
        if session_id:
            try:
                normalized_session = safe_session_id(session_id)
            except ValueError:
                normalized_session = None
        with self._write_lock, self._connection() as connection:
            if normalized_session:
                row = connection.execute(
                    "SELECT username FROM sessions WHERE session_id = ?",
                    (normalized_session,),
                ).fetchone()
                if not row or row["username"] != username:
                    normalized_session = None
            connection.execute(
                """
                INSERT INTO events(
                    event_id, username, session_id, event_type, source,
                    occurred_at, received_at, stage, payload_json
                ) VALUES (?, ?, ?, ?, 'backend', ?, ?, ?, ?)
                """,
                (
                    uuid.uuid4().hex,
                    username,
                    normalized_session,
                    str(event_type)[:120],
                    now,
                    now,
                    str(stage or "")[:40] or None,
                    _json(payload or {}),
                ),
            )

    def heartbeat(
        self,
        username: str,
        session_id: str,
        *,
        active_ms: int,
        idle_ms: int,
        payload: dict[str, Any] | None = None,
    ) -> None:
        username = safe_username(username)
        session_id = safe_session_id(session_id)
        now = utc_now()
        active_ms = max(0, int(active_ms or 0))
        idle_ms = max(0, int(idle_ms or 0))
        with self._write_lock, self._connection() as connection:
            self._assert_session(connection, username, session_id)
            connection.execute(
                """
                UPDATE sessions SET
                    last_seen_at = ?,
                    active_ms = MAX(active_ms, ?),
                    idle_ms = MAX(idle_ms, ?)
                WHERE session_id = ?
                """,
                (now, active_ms, idle_ms, session_id),
            )
            connection.execute(
                "UPDATE participants SET last_seen_at = ? WHERE username = ?",
                (now, username),
            )
        if payload:
            self.record_server_event(
                username,
                "session_heartbeat",
                session_id=session_id,
                payload={"active_ms": active_ms, "idle_ms": idle_ms, **payload},
            )

    def end_session(
        self,
        username: str,
        session_id: str,
        *,
        active_ms: int,
        idle_ms: int,
        reason: str,
        payload: dict[str, Any] | None = None,
    ) -> None:
        self.heartbeat(
            username,
            session_id,
            active_ms=active_ms,
            idle_ms=idle_ms,
        )
        now = utc_now()
        with self._write_lock, self._connection() as connection:
            connection.execute(
                """
                UPDATE sessions SET ended_at = COALESCE(ended_at, ?), end_reason = ?
                WHERE session_id = ? AND username = ?
                """,
                (now, str(reason or "unknown")[:80], session_id, username),
            )
        self.record_server_event(
            username,
            "session_ended",
            session_id=session_id,
            payload={
                "active_ms": max(0, int(active_ms or 0)),
                "idle_ms": max(0, int(idle_ms or 0)),
                "reason": reason,
                **(payload or {}),
            },
        )

    def archive_bytes(
        self,
        username: str,
        session_id: str | None,
        content: bytes,
        *,
        category: str,
        original_name: str,
        mime_type: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        username = safe_username(username)
        self.ensure_participant(username)
        normalized_session = safe_session_id(session_id) if session_id else None
        if normalized_session:
            with self._connection() as connection:
                self._assert_session(connection, username, normalized_session)
        artifact_id = f"artifact-{uuid.uuid4().hex}"
        suffix = Path(original_name or "").suffix.lower()
        if not re.fullmatch(r"\.[a-z0-9]{1,9}", suffix):
            suffix = ".bin"
        safe_category = re.sub(r"[^a-z0-9_-]+", "_", category.lower()).strip("_") or "artifact"
        session_folder = normalized_session or "unassigned"
        directory = self.root / "participants" / username / "sessions" / session_folder / "artifacts"
        directory.mkdir(parents=True, exist_ok=True)
        filename = f"{safe_category}_{artifact_id.removeprefix('artifact-')[:12]}{suffix}"
        destination = directory / filename
        destination.write_bytes(content)
        digest = hashlib.sha256(content).hexdigest()
        created_at = utc_now()
        relative_path = destination.relative_to(self.root).as_posix()
        with self._write_lock, self._connection() as connection:
            connection.execute(
                """
                INSERT INTO artifacts(
                    artifact_id, username, session_id, category, original_name,
                    stored_path, mime_type, byte_size, sha256, created_at, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    artifact_id,
                    username,
                    normalized_session,
                    safe_category,
                    str(original_name or "")[:255],
                    relative_path,
                    str(mime_type or "")[:120] or None,
                    len(content),
                    digest,
                    created_at,
                    _json(metadata or {}),
                ),
            )
        return {
            "artifact_id": artifact_id,
            "category": safe_category,
            "stored_path": relative_path,
            "byte_size": len(content),
            "sha256": digest,
            "created_at": created_at,
        }

    def archive_file(
        self,
        username: str,
        session_id: str | None,
        source_path: Path,
        *,
        category: str,
        original_name: str | None = None,
        mime_type: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        source = Path(source_path)
        if not source.is_file():
            raise ValueError("research artifact source file does not exist")
        return self.archive_bytes(
            username,
            session_id,
            source.read_bytes(),
            category=category,
            original_name=original_name or source.name,
            mime_type=mime_type,
            metadata=metadata,
        )

    def participant_summaries(self, configured_usernames: Iterable[str] = ()) -> list[dict[str, Any]]:
        configured = {safe_username(item) for item in configured_usernames}
        with self._connection() as connection:
            participants = {
                row["username"]: dict(row)
                for row in connection.execute("SELECT * FROM participants").fetchall()
            }
            session_counts = {
                row["username"]: dict(row)
                for row in connection.execute(
                    """
                    SELECT username, COUNT(*) AS session_count,
                           COALESCE(SUM(active_ms), 0) AS active_ms,
                           COALESCE(SUM(idle_ms), 0) AS idle_ms
                    FROM sessions GROUP BY username
                    """
                ).fetchall()
            }
            event_counts = {
                row["username"]: int(row["event_count"])
                for row in connection.execute(
                    "SELECT username, COUNT(*) AS event_count FROM events GROUP BY username"
                ).fetchall()
            }
            artifact_counts = {
                row["username"]: int(row["artifact_count"])
                for row in connection.execute(
                    "SELECT username, COUNT(*) AS artifact_count FROM artifacts GROUP BY username"
                ).fetchall()
            }
        usernames = sorted(configured | set(participants))
        result = []
        for username in usernames:
            participant = participants.get(username, {})
            sessions = session_counts.get(username, {})
            result.append({
                "username": username,
                "first_login_at": participant.get("first_login_at"),
                "last_login_at": participant.get("last_login_at"),
                "last_seen_at": participant.get("last_seen_at"),
                "login_count": int(participant.get("login_count") or 0),
                "consent_version": participant.get("consent_version"),
                "consented_at": participant.get("consented_at"),
                "session_count": int(sessions.get("session_count") or 0),
                "event_count": event_counts.get(username, 0),
                "artifact_count": artifact_counts.get(username, 0),
                "active_seconds": round(int(sessions.get("active_ms") or 0) / 1000, 3),
                "idle_seconds": round(int(sessions.get("idle_ms") or 0) / 1000, 3),
            })
        return result

    def _table_rows(
        self,
        connection: sqlite3.Connection,
        table: str,
        usernames: list[str],
    ) -> list[dict[str, Any]]:
        placeholders = ",".join("?" for _ in usernames)
        order_column = {
            "participants": "username",
            "sessions": "started_at",
            "events": "received_at",
            "artifacts": "created_at",
        }[table]
        rows = connection.execute(
            f"SELECT * FROM {table} WHERE username IN ({placeholders}) ORDER BY {order_column}",
            usernames,
        ).fetchall()
        return [dict(row) for row in rows]

    def build_export(
        self,
        usernames: Iterable[str],
        *,
        configured_usernames: Iterable[str] = (),
    ) -> Path:
        selected = sorted({safe_username(item) for item in usernames})
        if not selected:
            raise ValueError("at least one participant is required for export")
        for username in selected:
            self.ensure_participant(username)
        with self._connection() as connection:
            participant_rows = self._table_rows(connection, "participants", selected)
            session_rows = self._table_rows(connection, "sessions", selected)
            event_rows = self._table_rows(connection, "events", selected)
            artifact_rows = self._table_rows(connection, "artifacts", selected)

        export_dir = self.root / "exports"
        export_dir.mkdir(parents=True, exist_ok=True)
        descriptor = selected[0] if len(selected) == 1 else f"all-{len(selected)}-participants"
        temporary = tempfile.NamedTemporaryFile(
            prefix=f"vividwrite-{descriptor}-",
            suffix=".zip",
            dir=export_dir,
            delete=False,
        )
        temporary.close()
        export_path = Path(temporary.name)

        participant_fields = [
            "username", "first_login_at", "last_login_at", "last_seen_at",
            "login_count", "consent_version", "consented_at", "created_at",
        ]
        session_fields = [
            "session_id", "username", "started_at", "ended_at", "last_seen_at",
            "active_ms", "idle_ms", "end_reason", "client_metadata_json",
        ]
        event_fields = [
            "id", "event_id", "username", "session_id", "event_type", "source",
            "occurred_at", "received_at", "stage", "payload_json",
        ]
        artifact_fields = [
            "artifact_id", "username", "session_id", "category", "original_name",
            "stored_path", "mime_type", "byte_size", "sha256", "created_at",
            "metadata_json",
        ]
        essay_rows = []
        for event in event_rows:
            if event["event_type"] not in {"essay_edit", "essay_snapshot"}:
                continue
            try:
                payload = json.loads(event["payload_json"] or "{}")
            except json.JSONDecodeError:
                payload = {}
            essay_rows.append({
                "username": event["username"],
                "session_id": event["session_id"],
                "event_type": event["event_type"],
                "occurred_at": event["occurred_at"],
                "stage": event["stage"],
                "edit_source": payload.get("edit_source", ""),
                "word_count": payload.get("word_count", ""),
                "character_count": payload.get("character_count", ""),
                "text": payload.get("text", ""),
                "inserted_text": payload.get("inserted_text", ""),
                "deleted_text": payload.get("deleted_text", ""),
                "change_start": payload.get("change_start", ""),
            })

        summaries = [
            item
            for item in self.participant_summaries(configured_usernames)
            if item["username"] in selected
        ]
        generated_at = utc_now()
        html_rows = "".join(
            "<tr>"
            + "".join(
                f"<td>{html.escape(str(summary.get(field, '') or ''))}</td>"
                for field in (
                    "username", "login_count", "session_count", "event_count",
                    "artifact_count", "active_seconds", "idle_seconds", "last_seen_at",
                )
            )
            + "</tr>"
            for summary in summaries
        )
        summary_html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>VividWrite research export</title>
<style>body{{font:14px system-ui;margin:32px;color:#1d1d1f}}table{{border-collapse:collapse;width:100%}}th,td{{border:1px solid #ddd;padding:8px;text-align:left}}th{{background:#f4f4f5}}code{{background:#f4f4f5;padding:2px 4px}}</style></head>
<body><h1>VividWrite research export</h1><p>Generated: {html.escape(generated_at)}</p>
<p>Open the CSV files in Excel for analysis. Exact chronological events are also available in <code>raw/events.jsonl</code>.</p>
<table><thead><tr><th>Username</th><th>Logins</th><th>Sessions</th><th>Events</th><th>Artifacts</th><th>Active seconds</th><th>Idle seconds</th><th>Last seen</th></tr></thead>
<tbody>{html_rows}</tbody></table></body></html>"""

        readme = (
            "VividWrite research data export\n"
            f"Schema version: {RESEARCH_SCHEMA_VERSION}\n"
            f"Generated at: {generated_at}\n\n"
            "participants.csv: account-level login and consent metadata\n"
            "sessions.csv: session start/end, active time, idle time, and device metadata\n"
            "events.csv: full chronological event timeline with JSON payloads\n"
            "essay_versions.csv: essay snapshots and exact edit deltas\n"
            "artifacts.csv: image/file manifest with SHA-256 checksums\n"
            "raw/events.jsonl: one lossless JSON record per event\n"
            "artifacts/: uploaded task images, generated charts, and annotated originals\n\n"
            "Passwords, cookies, API keys, and authorization headers are never recorded.\n"
        )

        with zipfile.ZipFile(export_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("README.txt", readme.encode("utf-8"))
            archive.writestr("summary.html", summary_html.encode("utf-8"))
            archive.writestr("summary.json", json.dumps(summaries, ensure_ascii=False, indent=2))
            archive.writestr("participants.csv", _csv_bytes(participant_rows, participant_fields))
            archive.writestr("sessions.csv", _csv_bytes(session_rows, session_fields))
            archive.writestr("events.csv", _csv_bytes(event_rows, event_fields))
            archive.writestr("artifacts.csv", _csv_bytes(artifact_rows, artifact_fields))
            archive.writestr(
                "essay_versions.csv",
                _csv_bytes(
                    essay_rows,
                    [
                        "username", "session_id", "event_type", "occurred_at", "stage",
                        "edit_source", "word_count", "character_count", "text",
                        "inserted_text", "deleted_text", "change_start",
                    ],
                ),
            )
            archive.writestr(
                "raw/events.jsonl",
                "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in event_rows),
            )
            archive.writestr(
                "raw/sessions.json",
                json.dumps(session_rows, ensure_ascii=False, indent=2),
            )
            archive.writestr(
                "raw/artifacts.json",
                json.dumps(artifact_rows, ensure_ascii=False, indent=2),
            )
            for artifact in artifact_rows:
                source = (self.root / artifact["stored_path"]).resolve()
                if not source.is_file() or not source.is_relative_to(self.root.resolve()):
                    continue
                archive.write(
                    source,
                    f"artifacts/{artifact['username']}/{artifact['session_id'] or 'unassigned'}/{source.name}",
                )
        return export_path


_default_store: ResearchStore | None = None
_default_store_lock = threading.Lock()


def get_research_store() -> ResearchStore:
    global _default_store
    if _default_store is None:
        with _default_store_lock:
            if _default_store is None:
                _default_store = ResearchStore()
    return _default_store

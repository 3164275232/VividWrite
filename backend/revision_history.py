"""Private, immutable analysis snapshots for a learner's revision comparisons."""

import hashlib
import json
import sqlite3
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request

from auth import authenticated_username
from paths import USER_DATA_DIR
from record_time import beijing_now, normalise_record_times


router = APIRouter(prefix="/api/revision-history")


class RevisionHistoryStore:
    def __init__(self, path: Path | None = None):
        self.path = path or USER_DATA_DIR / "revision_history.sqlite3"

    def _connect(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=15)
        connection.row_factory = sqlite3.Row
        connection.execute("""
            CREATE TABLE IF NOT EXISTS analysis_revisions (
                id TEXT PRIMARY KEY, username TEXT NOT NULL, task_id TEXT NOT NULL,
                sequence INTEGER NOT NULL, snapshot TEXT NOT NULL,
                UNIQUE (username, task_id, sequence)
            )
        """)
        return connection

    def save(self, username, image_bytes, chart_type, reference_text, essay, chart_data,
             chart_url, original_url, submission_id=None):
        task_id = hashlib.sha256(image_bytes + b"\0" + chart_type.encode()).hexdigest()
        reference_id = hashlib.sha256(" ".join(reference_text.split()).encode()).hexdigest()
        snapshot = {
            "id": uuid.uuid4().hex,
            "submission_id": submission_id,
            "task_id": task_id,
            "reference_id": reference_id,
            "created_at": beijing_now(),
            "essay": essay,
            "chart_type": chart_type,
            "title": chart_data.get("title", ""),
            "chart_url": chart_url,
            "original_url": original_url,
            "assessments": chart_data.get("move_feedback", {}).get("assessments", []),
            "feedback_version": chart_data.get("move_feedback", {}).get("version"),
            "records": chart_data.get("records", []),
            "unit": chart_data.get("axes", {}).get("unit", ""),
            "value_tolerance": chart_data.get("comparison", {}).get("accepted_value_tolerance"),
            "analysis_model": chart_data.get("style", {}).get("analysis_model"),
        }
        connection = self._connect()
        try:
            with connection:
                # Serialise version allocation across concurrent successful analyses.
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute(
                    "SELECT COALESCE(MAX(sequence), 0) + 1 FROM analysis_revisions "
                    "WHERE username = ? AND task_id = ?", (username, task_id),
                ).fetchone()
                snapshot["sequence"] = row[0]
                connection.execute(
                    "INSERT INTO analysis_revisions VALUES (?, ?, ?, ?, ?)",
                    (snapshot["id"], username, task_id, snapshot["sequence"],
                     json.dumps(snapshot, ensure_ascii=False, allow_nan=False)),
                )
        finally:
            connection.close()
        return snapshot

    def list(self, username, task_id, before=None, limit=30):
        connection = self._connect()
        try:
            rows = connection.execute(
                "SELECT snapshot FROM analysis_revisions WHERE username = ? AND task_id = ? "
                "AND sequence < ? ORDER BY sequence DESC LIMIT ?",
                (username, task_id, before or 2**63 - 1, min(max(limit, 1), 30)),
            ).fetchall()
            return [normalise_record_times(json.loads(row["snapshot"])) for row in rows]
        finally:
            connection.close()


def history_username(request):
    return getattr(request.state, "username", None) or authenticated_username(request)


@router.get("/{task_id}")
def list_revisions(task_id: str, request: Request, before: int | None = None):
    username = history_username(request)
    if not username:
        raise HTTPException(status_code=401, detail="Sign in to view your revision history.")
    revisions = RevisionHistoryStore().list(username, task_id, before)
    return {
        "revisions": revisions,
        "next_before": revisions[-1]["sequence"] if len(revisions) == 30 else None,
    }

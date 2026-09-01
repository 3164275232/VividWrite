from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.background import BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from auth import configured_users
from research_data import (
    get_research_store,
    research_enabled,
    safe_username,
    sanitize_payload,
    utc_now,
)


RESEARCH_SESSION_HEADER = "x-vividwrite-session"
ADMIN_KEY_HEADER = "x-research-admin-key"
MAX_EVENT_BATCH = 200
MAX_EVENT_BYTES = 750_000
MAX_ARTIFACT_BYTES = 15 * 1024 * 1024

router = APIRouter(prefix="/api/research", tags=["research"])


class ResearchSessionStart(BaseModel):
    session_id: str
    client_started_at: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ResearchEventInput(BaseModel):
    event_id: str
    event_type: str
    source: str = "frontend"
    occurred_at: str
    stage: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class ResearchEventBatch(BaseModel):
    session_id: str
    events: list[ResearchEventInput]


class ResearchHeartbeat(BaseModel):
    session_id: str
    active_ms: int = 0
    idle_ms: int = 0
    visible: bool | None = None
    stage: str | None = None
    last_activity_at: str | None = None


class ResearchSessionEnd(ResearchHeartbeat):
    reason: str = "unknown"


def _require_enabled() -> None:
    if not research_enabled():
        raise HTTPException(status_code=404, detail="Research data collection is disabled.")


def _authenticated_username(request: Request) -> str:
    username = getattr(request.state, "username", None)
    if not username:
        raise HTTPException(status_code=401, detail="Authentication required.")
    return safe_username(username)


def research_session_id(request: Request) -> str | None:
    return request.headers.get(RESEARCH_SESSION_HEADER) or None


def _client_fingerprint(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "").split(",", 1)[0].strip()
    client_ip = forwarded or (request.client.host if request.client else "unknown")
    user_agent = request.headers.get("user-agent", "")
    salt = (
        os.getenv("APP_SESSION_SECRET", "")
        or os.getenv("APP_RESEARCH_ADMIN_KEY", "")
        or "vividwrite-research"
    )
    return hashlib.sha256(f"{salt}|{client_ip}|{user_agent}".encode("utf-8")).hexdigest()


def request_metadata(request: Request) -> dict[str, Any]:
    return {
        "client_fingerprint": _client_fingerprint(request),
        "user_agent": request.headers.get("user-agent", "")[:1_000],
        "accept_language": request.headers.get("accept-language", "")[:500],
        "referer": request.headers.get("referer", "")[:2_000],
        "forwarded_proto": request.headers.get("x-forwarded-proto", "")[:30],
    }


def _admin_key() -> str:
    return os.getenv("APP_RESEARCH_ADMIN_KEY", "").strip()


def require_research_admin(request: Request) -> None:
    _require_enabled()
    expected = _admin_key()
    supplied = request.headers.get(ADMIN_KEY_HEADER, "")
    if len(expected) < 24:
        raise HTTPException(status_code=503, detail="Research administrator access is not configured.")
    if not supplied or not hmac.compare_digest(supplied, expected):
        raise HTTPException(status_code=401, detail="Invalid research administrator key.")


def record_server_event_for_request(
    request: Request,
    event_type: str,
    *,
    stage: str | None = None,
    payload: dict[str, Any] | None = None,
) -> None:
    if not research_enabled():
        return
    username = getattr(request.state, "username", None)
    if not username:
        return
    try:
        get_research_store().record_server_event(
            username,
            event_type,
            session_id=research_session_id(request),
            stage=stage,
            payload=payload,
        )
    except Exception as exc:
        print(f"Research event logging failed: {exc}")


def archive_file_for_request(
    request: Request,
    source_path: Path,
    *,
    category: str,
    original_name: str | None = None,
    mime_type: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    if not research_enabled():
        return None
    username = getattr(request.state, "username", None)
    session_id = research_session_id(request)
    if not username or not session_id:
        return None
    try:
        return get_research_store().archive_file(
            username,
            session_id,
            source_path,
            category=category,
            original_name=original_name,
            mime_type=mime_type,
            metadata=metadata,
        )
    except Exception as exc:
        print(f"Research artifact archiving failed: {exc}")
        return None


async def research_request_middleware(request: Request, call_next):
    started = time.perf_counter()
    response = None
    error_name = None
    try:
        response = await call_next(request)
        return response
    except Exception as exc:
        error_name = exc.__class__.__name__
        raise
    finally:
        path = request.url.path
        username = getattr(request.state, "username", None)
        should_record = (
            research_enabled()
            and bool(username)
            and path.startswith("/api/")
            and not path.startswith("/api/research/")
        )
        if should_record:
            payload = {
                "request_id": request.headers.get("x-request-id"),
                "method": request.method,
                "path": path,
                "query": sanitize_payload(dict(request.query_params)),
                "status_code": response.status_code if response else 500,
                "duration_ms": round((time.perf_counter() - started) * 1_000, 3),
                "request_content_type": request.headers.get("content-type", "")[:200],
                "request_content_length": request.headers.get("content-length"),
                "error_type": error_name,
            }
            record_server_event_for_request(request, "api_request", payload=payload)


@router.post("/sessions/start")
def start_research_session(request: Request, payload: ResearchSessionStart):
    _require_enabled()
    username = _authenticated_username(request)
    metadata = {**request_metadata(request), **payload.metadata}
    session_id = get_research_store().start_session(
        username,
        payload.session_id,
        client_started_at=payload.client_started_at,
        metadata=metadata,
    )
    return {"success": True, "session_id": session_id, "server_started_at": utc_now()}


@router.post("/events")
def append_research_events(request: Request, payload: ResearchEventBatch):
    _require_enabled()
    username = _authenticated_username(request)
    if not payload.events:
        return {"success": True, "accepted": 0}
    if len(payload.events) > MAX_EVENT_BATCH:
        raise HTTPException(status_code=413, detail="Research event batch is too large.")
    serialized = json.dumps(payload.model_dump(), ensure_ascii=False).encode("utf-8")
    if len(serialized) > MAX_EVENT_BYTES:
        raise HTTPException(status_code=413, detail="Research event payload is too large.")
    accepted = get_research_store().append_events(
        username,
        payload.session_id,
        [event.model_dump() for event in payload.events],
    )
    return {"success": True, "accepted": accepted}


@router.post("/heartbeat")
def research_heartbeat(request: Request, payload: ResearchHeartbeat):
    _require_enabled()
    username = _authenticated_username(request)
    get_research_store().heartbeat(
        username,
        payload.session_id,
        active_ms=payload.active_ms,
        idle_ms=payload.idle_ms,
        payload={
            "visible": payload.visible,
            "stage": payload.stage,
            "last_activity_at": payload.last_activity_at,
        },
    )
    return {"success": True, "server_received_at": utc_now()}


@router.post("/sessions/end")
def end_research_session(request: Request, payload: ResearchSessionEnd):
    _require_enabled()
    username = _authenticated_username(request)
    get_research_store().end_session(
        username,
        payload.session_id,
        active_ms=payload.active_ms,
        idle_ms=payload.idle_ms,
        reason=payload.reason,
        payload={
            "visible": payload.visible,
            "stage": payload.stage,
            "last_activity_at": payload.last_activity_at,
        },
    )
    return {"success": True, "server_received_at": utc_now()}


@router.post("/artifacts")
async def upload_research_artifact(
    request: Request,
    image: UploadFile = File(...),
    category: str = Form(...),
    metadata_json: str = Form("{}"),
):
    _require_enabled()
    username = _authenticated_username(request)
    session_id = research_session_id(request)
    if not session_id:
        raise HTTPException(status_code=400, detail="Research session header is required.")
    content = await image.read()
    if not content:
        raise HTTPException(status_code=400, detail="Research artifact is empty.")
    if len(content) > MAX_ARTIFACT_BYTES:
        raise HTTPException(status_code=413, detail="Research artifact exceeds 15 MB.")
    try:
        metadata = json.loads(metadata_json or "{}")
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Invalid artifact metadata.") from exc
    artifact = get_research_store().archive_bytes(
        username,
        session_id,
        content,
        category=category,
        original_name=image.filename or "artifact.bin",
        mime_type=image.content_type,
        metadata=metadata,
    )
    return {"success": True, "artifact": artifact}


@router.get("/me/summary")
def current_participant_summary(request: Request):
    _require_enabled()
    username = _authenticated_username(request)
    summaries = get_research_store().participant_summaries([username])
    return {"success": True, "participant": summaries[0] if summaries else None}


@router.get("/me/export")
def export_current_participant(request: Request, background_tasks: BackgroundTasks):
    _require_enabled()
    username = _authenticated_username(request)
    path = get_research_store().build_export([username], configured_usernames=[username])
    background_tasks.add_task(path.unlink, missing_ok=True)
    return FileResponse(
        path,
        media_type="application/zip",
        filename=f"vividwrite-{username}-research-data.zip",
        background=background_tasks,
    )


@router.get("/admin/participants")
def list_research_participants(request: Request):
    require_research_admin(request)
    participants = get_research_store().participant_summaries(configured_users())
    return {"success": True, "participant_count": len(participants), "participants": participants}


@router.get("/admin/export/{username}")
def export_research_participant(
    username: str,
    request: Request,
    background_tasks: BackgroundTasks,
):
    require_research_admin(request)
    normalized = safe_username(username)
    if normalized not in configured_users():
        raise HTTPException(status_code=404, detail="Unknown test account.")
    path = get_research_store().build_export([normalized], configured_usernames=configured_users())
    background_tasks.add_task(path.unlink, missing_ok=True)
    return FileResponse(
        path,
        media_type="application/zip",
        filename=f"vividwrite-{normalized}-research-data.zip",
        background=background_tasks,
    )


@router.get("/admin/export-all")
def export_all_research_data(request: Request, background_tasks: BackgroundTasks):
    require_research_admin(request)
    usernames = sorted(configured_users())
    if not usernames:
        return JSONResponse(status_code=404, content={"detail": "No test accounts are configured."})
    path = get_research_store().build_export(usernames, configured_usernames=usernames)
    background_tasks.add_task(path.unlink, missing_ok=True)
    return FileResponse(
        path,
        media_type="application/zip",
        filename="vividwrite-all-participants-research-data.zip",
        background=background_tasks,
    )

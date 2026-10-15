import base64
import hashlib
import hmac
import json
import os
import secrets
import threading
import time
from collections import defaultdict, deque

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel


AUTH_COOKIE_NAME = "vividwrite_session"
DEFAULT_SESSION_TTL_SECONDS = 12 * 60 * 60
PASSWORD_HASH_ITERATIONS = 310_000
LOGIN_WINDOW_SECONDS = 15 * 60
MAX_FAILED_LOGINS = 10

router = APIRouter()
_failed_logins: dict[str, deque[float]] = defaultdict(deque)
_failed_logins_lock = threading.Lock()


class LoginRequest(BaseModel):
    username: str
    password: str = ""
    consent_granted: bool = False
    consent_version: str | None = None
    consented_at: str | None = None


def auth_enabled() -> bool:
    return os.getenv("APP_AUTH_ENABLED", "false").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def configured_users() -> set[str]:
    raw_users = os.getenv("APP_TEST_USERS", "")
    return {
        username.strip().lower()
        for username in raw_users.split(",")
        if username.strip()
    }


def create_password_hash(
    password: str,
    *,
    salt: bytes | None = None,
    iterations: int = PASSWORD_HASH_ITERATIONS,
) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        iterations,
    )
    return f"pbkdf2_sha256:{iterations}:{salt.hex()}:{digest.hex()}"


def verify_password_hash(password: str, encoded_hash: str) -> bool:
    try:
        algorithm, iterations_text, salt_hex, expected_hex = encoded_hash.split(":", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        iterations = int(iterations_text)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(expected_hex)
    except (TypeError, ValueError):
        return False

    actual = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        iterations,
    )
    return hmac.compare_digest(actual, expected)


def _base64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _base64url_decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _session_secret() -> str:
    secret = os.getenv("APP_SESSION_SECRET", "").strip()
    if secret:
        return secret
    if not auth_enabled():
        return "vividwrite-local-development-session"
    raise RuntimeError("APP_SESSION_SECRET is required when authentication is enabled")


def _session_ttl_seconds() -> int:
    try:
        return max(300, int(os.getenv("APP_SESSION_TTL_SECONDS", DEFAULT_SESSION_TTL_SECONDS)))
    except ValueError:
        return DEFAULT_SESSION_TTL_SECONDS


def create_session_token(
    username: str,
    now: int | None = None,
    *,
    consent_version: str | None = None,
) -> str:
    issued_at = int(time.time() if now is None else now)
    payload = json.dumps(
        {
            "username": username,
            "issued_at": issued_at,
            "expires_at": issued_at + _session_ttl_seconds(),
            "consent_version": consent_version,
        },
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    signature = hmac.new(
        _session_secret().encode("utf-8"),
        payload,
        hashlib.sha256,
    ).digest()
    return f"{_base64url_encode(payload)}.{_base64url_encode(signature)}"


def read_session_token(token: str | None, now: int | None = None) -> str | None:
    if not token:
        return None
    try:
        payload_text, signature_text = token.split(".", 1)
        payload = _base64url_decode(payload_text)
        signature = _base64url_decode(signature_text)
        expected_signature = hmac.new(
            _session_secret().encode("utf-8"),
            payload,
            hashlib.sha256,
        ).digest()
        if not hmac.compare_digest(signature, expected_signature):
            return None
        data = json.loads(payload)
        username = str(data["username"]).strip().lower()
        expires_at = int(data["expires_at"])
        token_consent_version = data.get("consent_version")
    except (KeyError, RuntimeError, TypeError, ValueError, json.JSONDecodeError):
        return None

    current_time = int(time.time() if now is None else now)
    if expires_at <= current_time:
        return None
    if auth_enabled() and username not in configured_users():
        return None
    try:
        from research_data import (
            research_consent_required,
            research_consent_version,
            research_enabled,
        )

        if (
            research_enabled()
            and research_consent_required()
            and token_consent_version != research_consent_version()
        ):
            return None
    except ImportError:
        return None
    return username


def authenticated_username(request: Request) -> str | None:
    return read_session_token(request.cookies.get(AUTH_COOKIE_NAME))


def _client_key(request: Request) -> str:
    return (
        request.headers.get("x-real-ip")
        or (request.client.host if request.client else None)
        or "unknown"
    )


def _is_rate_limited(client_key: str, now: float) -> bool:
    with _failed_logins_lock:
        attempts = _failed_logins[client_key]
        while attempts and attempts[0] <= now - LOGIN_WINDOW_SECONDS:
            attempts.popleft()
        return len(attempts) >= MAX_FAILED_LOGINS


def _record_failed_login(client_key: str, now: float) -> None:
    with _failed_logins_lock:
        _failed_logins[client_key].append(now)


def _clear_failed_logins(client_key: str) -> None:
    with _failed_logins_lock:
        _failed_logins.pop(client_key, None)


def _set_session_cookie(
    response: Response,
    username: str,
    *,
    consent_version: str | None = None,
) -> None:
    ttl = _session_ttl_seconds()
    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=create_session_token(username, consent_version=consent_version),
        max_age=ttl,
        httponly=True,
        secure=os.getenv("APP_COOKIE_SECURE", "false").strip().lower() == "true",
        samesite="lax",
        path="/",
    )


def _record_research_auth_event(
    username: str,
    event_type: str,
    request: Request,
    *,
    consent_version: str | None = None,
    consented_at: str | None = None,
) -> None:
    try:
        from research_data import get_research_store, research_enabled

        if not research_enabled():
            return
        client_key = _client_key(request)
        salt = os.getenv("APP_SESSION_SECRET", "") or "vividwrite-research"
        client_fingerprint = hashlib.sha256(
            f"{salt}|{client_key}|{request.headers.get('user-agent', '')}".encode("utf-8")
        ).hexdigest()
        get_research_store().record_auth_event(
            username,
            event_type,
            payload={
                "client_fingerprint": client_fingerprint,
                "user_agent": request.headers.get("user-agent", "")[:1_000],
                "accept_language": request.headers.get("accept-language", "")[:500],
            },
            consent_version=consent_version,
            consented_at=consented_at,
        )
    except Exception as exc:
        print(f"Research authentication logging failed: {exc}")


@router.get("/api/auth/config")
def auth_config() -> dict[str, bool | str]:
    from research_data import (
        research_consent_required,
        research_consent_version,
        research_enabled,
    )

    enabled = research_enabled()
    return {
        "password_required": auth_enabled(),
        "research_enabled": enabled,
        "consent_required": enabled and research_consent_required(),
        "consent_version": research_consent_version(),
    }


@router.post("/api/auth/login")
def login(payload: LoginRequest, request: Request, response: Response):
    from research_data import (
        research_consent_required,
        research_consent_version,
        research_enabled,
    )

    username = payload.username.strip().lower()
    client_key = _client_key(request)
    now = time.time()

    if _is_rate_limited(client_key, now):
        return JSONResponse(
            status_code=429,
            content={"detail": "Too many failed login attempts. Please try again later."},
        )

    if auth_enabled():
        password_hash = os.getenv("APP_SHARED_PASSWORD_HASH", "")
        credentials_valid = (
            bool(username)
            and username in configured_users()
            and verify_password_hash(payload.password, password_hash)
        )
    else:
        credentials_valid = bool(username)

    if not credentials_valid:
        _record_failed_login(client_key, now)
        return JSONResponse(
            status_code=401,
            content={"detail": "Incorrect username or password."},
        )

    if research_enabled() and research_consent_required():
        expected_version = research_consent_version()
        if not payload.consent_granted or payload.consent_version != expected_version:
            return JSONResponse(
                status_code=400,
                content={"detail": "Research-session consent is required before signing in."},
            )

    _clear_failed_logins(client_key)
    _set_session_cookie(
        response,
        username,
        consent_version=payload.consent_version if research_enabled() else None,
    )
    _record_research_auth_event(
        username,
        "auth_login_succeeded",
        request,
        consent_version=payload.consent_version,
        consented_at=payload.consented_at,
    )
    return {"authenticated": True, "username": username}


@router.get("/api/auth/me")
def current_user(request: Request):
    username = authenticated_username(request)
    if not username:
        return JSONResponse(
            status_code=401,
            content={"detail": "Authentication required."},
        )
    return {"authenticated": True, "username": username}


@router.post("/api/auth/logout")
def logout(request: Request, response: Response) -> dict[str, bool]:
    username = authenticated_username(request)
    if username:
        _record_research_auth_event(username, "auth_logout", request)
    response.delete_cookie(AUTH_COOKIE_NAME, path="/")
    return {"authenticated": False}


async def authentication_middleware(request: Request, call_next):
    path = request.url.path
    is_public = (
        path == "/health"
        or path.startswith("/api/auth/")
        or path.startswith("/api/research/admin/")
    )
    is_protected = (
        path.startswith("/api/")
        or path.startswith("/charts/")
        or path.startswith("/uploads/")
    )

    if not auth_enabled() or is_public or not is_protected:
        return await call_next(request)

    username = authenticated_username(request)
    if not username:
        return JSONResponse(
            status_code=401,
            content={"detail": "Authentication required."},
        )

    request.state.username = username
    return await call_next(request)

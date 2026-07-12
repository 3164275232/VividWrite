import re
import time
import uuid
from pathlib import Path

from fastapi import UploadFile

from paths import BASE_DIR, USER_DATA_DIR


def _safe_suffix(filename: str | None, default: str = ".png") -> str:
    suffix = Path(filename or "").suffix.lower()
    if 1 < len(suffix) <= 10 and suffix[1:].isalnum():
        return suffix
    return default


async def save_uploaded_file(upload: UploadFile, directory: Path) -> Path:
    content = await upload.read()
    if not content:
        raise ValueError("Uploaded file is empty")

    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{uuid.uuid4().hex}{_safe_suffix(upload.filename)}"
    path.write_bytes(content)
    return path


def user_directory(username: str) -> Path:
    normalized = username.strip()
    if not normalized:
        raise ValueError("username required")

    safe_name = re.sub(r"[^\w.-]+", "_", normalized, flags=re.UNICODE)
    safe_name = safe_name.replace("..", "_").strip(".")
    if not safe_name:
        raise ValueError("invalid username")

    directory = USER_DATA_DIR / safe_name
    directory.mkdir(parents=True, exist_ok=True)
    return directory


async def save_user_image(username: str, upload: UploadFile) -> Path:
    directory = user_directory(username)
    suffix = _safe_suffix(upload.filename)
    content = await upload.read()
    if not content:
        raise ValueError("Uploaded file is empty")

    path = directory / f"drafting_image_{int(time.time())}_{uuid.uuid4().hex[:8]}{suffix}"
    path.write_bytes(content)
    return path


def save_user_revision(username: str, text: str) -> Path:
    directory = user_directory(username)
    path = directory / f"revision_{int(time.time())}.txt"
    path.write_text(text or "", encoding="utf-8")
    return path


def relative_runtime_path(path: Path) -> str:
    return path.relative_to(BASE_DIR).as_posix()

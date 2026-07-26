"""Alibaba Cloud Model Studio endpoint helpers."""

from __future__ import annotations

from urllib.parse import urlparse


DEFAULT_MODEL_STUDIO_REGION = "cn-beijing"

REGION_ALIASES = {
    "beijing": "cn-beijing",
    "china": "cn-beijing",
    "china-beijing": "cn-beijing",
    "cn-beijing": "cn-beijing",
    "singapore": "ap-southeast-1",
    "sg": "ap-southeast-1",
    "ap-southeast-1": "ap-southeast-1",
}


def normalize_model_studio_region(region: str | None) -> str:
    value = (region or DEFAULT_MODEL_STUDIO_REGION).strip().lower()
    return REGION_ALIASES.get(value, value or DEFAULT_MODEL_STUDIO_REGION)


def model_studio_workspace_host(
    workspace_id: str,
    *,
    region: str | None = None,
) -> str:
    """Return a Model Studio workspace host from an ID, hostname, or URL."""
    raw = workspace_id.strip().rstrip("/")
    parsed = urlparse(raw if "://" in raw else f"//{raw}")
    hostname = (parsed.hostname or raw).strip().rstrip("/")
    if hostname.endswith(".maas.aliyuncs.com"):
        return hostname
    selected_region = normalize_model_studio_region(region)
    return f"{hostname}.{selected_region}.maas.aliyuncs.com"

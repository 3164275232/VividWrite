"""Qwen vision task-type classification for IELTS Academic Task 1 images."""

from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import threading
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from openai import OpenAI
from PIL import Image

from spatial_sample_essay import get_qwen_vl_api_key, get_qwen_vl_base_url, get_qwen_vl_model


STATISTICAL_TASK_TYPES = {"bar", "line", "area", "pie"}
SPATIAL_TASK_TYPES = {"map", "process"}
SUPPORTED_TASK_TYPES = STATISTICAL_TASK_TYPES | SPATIAL_TASK_TYPES | {"unknown"}
HIGH_CONFIDENCE_THRESHOLD = 0.85
DEFAULT_CLASSIFICATION_MAX_SIDE = 1600
DEFAULT_CLASSIFICATION_MAX_TOKENS = 150

_classification_cache: OrderedDict[str, "TaskImageClassification"] = OrderedDict()
_cache_lock = threading.Lock()


class TaskImageDetectionError(RuntimeError):
    pass


@dataclass(frozen=True)
class TaskImageClassification:
    task_type: str
    confidence: float
    detection_source: str = "qwen-vision"
    reason: str = ""


def clear_task_image_detection_cache() -> None:
    with _cache_lock:
        _classification_cache.clear()


def _cache_limit() -> int:
    try:
        return max(1, min(256, int(os.getenv("TASK_TYPE_DETECTION_CACHE_SIZE", "64"))))
    except ValueError:
        return 64


def _cache_get(key: str) -> TaskImageClassification | None:
    with _cache_lock:
        value = _classification_cache.get(key)
        if value is not None:
            _classification_cache.move_to_end(key)
        return value


def _cache_set(key: str, value: TaskImageClassification) -> None:
    with _cache_lock:
        _classification_cache[key] = value
        _classification_cache.move_to_end(key)
        while len(_classification_cache) > _cache_limit():
            _classification_cache.popitem(last=False)


def _image_digest(image_path: str | Path) -> str:
    digest = hashlib.sha256()
    with open(image_path, "rb") as image_file:
        for chunk in iter(lambda: image_file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _classification_max_side() -> int:
    try:
        return max(512, min(2400, int(os.getenv("TASK_TYPE_DETECTION_MAX_SIDE", "1600"))))
    except ValueError:
        return DEFAULT_CLASSIFICATION_MAX_SIDE


def _classification_max_tokens() -> int:
    try:
        return max(80, min(300, int(os.getenv("TASK_TYPE_DETECTION_MAX_TOKENS", "150"))))
    except ValueError:
        return DEFAULT_CLASSIFICATION_MAX_TOKENS


def _encode_image_for_classification(image_path: str | Path) -> str:
    path = Path(image_path)
    if not path.is_file():
        raise TaskImageDetectionError("The uploaded task image is missing.")
    try:
        with Image.open(path) as source:
            image = source.convert("RGB")
            max_side = _classification_max_side()
            image.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
            buffer = io.BytesIO()
            image.save(buffer, format="JPEG", quality=92, optimize=True)
    except (OSError, ValueError) as exc:
        raise TaskImageDetectionError(f"Cannot prepare the image for Qwen vision: {exc}") from exc
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"


def _classification_prompt() -> str:
    return """
Classify the attached IELTS Academic Writing Task 1 visual.

Return only one JSON object with this schema:
{"task_type":"bar|line|area|pie|map|process|unknown","confidence":0.0,"reason":"short reason"}

Definitions:
- bar: bar, column, grouped bar, stacked bar or histogram-style statistical chart.
- line: line graph, multi-line graph or time-series line chart.
- area: area chart or stacked area chart with filled regions under lines.
- pie: one or more pie or doughnut charts.
- map: map, site plan, floor plan, campus/town layout, before-and-after map or land-use plan.
- process: process diagram, flow diagram, cycle, manufacturing/natural process, arrows between stages.
- unknown: unsupported or ambiguous visuals, including pure tables or mixed visuals where no primary type is clear.

Use the visual structure, not the task title alone. Choose map/process before statistical
types when the image is a spatial layout or flow diagram. Set confidence below 0.85 if
manual confirmation would be sensible.
""".strip()


def _completion_text(completion: Any) -> str:
    if not getattr(completion, "choices", None):
        return ""
    message = completion.choices[0].message
    return str(getattr(message, "content", "") or "").strip()


def _extract_json_object(text: str) -> dict[str, Any]:
    decoder = json.JSONDecoder()
    start = text.find("{")
    while start != -1:
        try:
            parsed, _ = decoder.raw_decode(text[start:])
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass
        start = text.find("{", start + 1)
    raise ValueError("No JSON object found")


def _normalise_confidence(value: Any) -> float:
    if isinstance(value, str):
        text = value.strip()
        percentage = text.endswith("%")
        if percentage:
            text = text[:-1].strip()
        try:
            number = float(text)
        except ValueError:
            return 0.0
        if percentage or number > 1:
            number /= 100
    else:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return 0.0
    return max(0.0, min(1.0, number))


def _normalise_classification(payload: dict[str, Any]) -> TaskImageClassification:
    task_type = str(payload.get("task_type") or "unknown").strip().lower()
    if task_type not in SUPPORTED_TASK_TYPES:
        task_type = "unknown"
    confidence = _normalise_confidence(payload.get("confidence"))
    if task_type == "unknown":
        confidence = min(confidence, 0.4)
    reason = str(payload.get("reason") or "").strip()
    return TaskImageClassification(task_type=task_type, confidence=confidence, reason=reason)


def classify_task_image(
    image_path: str | Path,
    *,
    client: Any | None = None,
) -> TaskImageClassification:
    digest = _image_digest(image_path)
    cached = _cache_get(digest)
    if cached is not None:
        return cached

    api_key = get_qwen_vl_api_key()
    if not api_key and client is None:
        raise TaskImageDetectionError(
            "Qwen vision is not configured. Set QWEN_VL_API_KEY, DASHSCOPE_API_KEY, or WAN_API_KEY."
        )

    model = get_qwen_vl_model()
    vision_client = client or OpenAI(api_key=api_key, base_url=get_qwen_vl_base_url())
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": _classification_prompt()},
                {"type": "image_url", "image_url": {"url": _encode_image_for_classification(image_path)}},
            ],
        }
    ]
    try:
        completion = vision_client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0,
            max_tokens=_classification_max_tokens(),
            response_format={"type": "json_object"},
            extra_body={"enable_thinking": False},
        )
    except Exception as exc:
        raise TaskImageDetectionError(f"Qwen vision task classification failed: {exc}") from exc

    raw = _completion_text(completion)
    try:
        classification = _normalise_classification(_extract_json_object(raw))
    except (TypeError, ValueError, json.JSONDecodeError):
        classification = TaskImageClassification(
            task_type="unknown",
            confidence=0.0,
            reason="Qwen vision did not return valid classification JSON.",
        )
    _cache_set(digest, classification)
    return classification

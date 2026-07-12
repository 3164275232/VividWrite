"""Alibaba Cloud Wan2.7 image editing adapter for spatial IELTS tasks."""

from __future__ import annotations

import base64
import io
import os
import uuid
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv
from PIL import Image


load_dotenv()


DEFAULT_WAN_ENDPOINT = (
    "https://dashscope.aliyuncs.com/api/v1/services/"
    "aigc/multimodal-generation/generation"
)
DEFAULT_WAN_MODEL = "wan2.7-image-pro"
SPATIAL_TASK_TYPES = {"map", "process"}


class WanImageRendererError(RuntimeError):
    pass


def get_wan_api_key() -> str | None:
    return os.getenv("WAN_API_KEY") or os.getenv("DASHSCOPE_API_KEY")


def get_wan_endpoint() -> str:
    explicit = (os.getenv("WAN_API_ENDPOINT") or "").strip()
    if explicit:
        return explicit
    workspace_id = (os.getenv("WAN_WORKSPACE_ID") or "").strip()
    if workspace_id:
        return (
            f"https://{workspace_id}.cn-beijing.maas.aliyuncs.com/api/v1/services/"
            "aigc/multimodal-generation/generation"
        )
    return DEFAULT_WAN_ENDPOINT


def get_wan_model() -> str:
    return (os.getenv("WAN_IMAGE_MODEL") or DEFAULT_WAN_MODEL).strip() or DEFAULT_WAN_MODEL


def _encode_reference_image(image_path: str | Path) -> str:
    path = Path(image_path)
    if not path.is_file():
        raise WanImageRendererError("The original image file is missing.")
    try:
        with Image.open(path) as source:
            image = source.convert("RGB")
            width, height = image.size
            if width < 240 or height < 240:
                scale = max(240 / width, 240 / height)
                image = image.resize((round(width * scale), round(height * scale)))
            image.thumbnail((8000, 8000))
            buffer = io.BytesIO()
            image.save(buffer, format="JPEG", quality=94, optimize=True)
    except (OSError, ValueError) as exc:
        raise WanImageRendererError(f"Cannot prepare the original image for Wan2.7: {exc}") from exc
    if buffer.tell() > 20 * 1024 * 1024:
        raise WanImageRendererError("The prepared reference image exceeds Wan2.7's 20 MB limit.")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"


def _build_edit_prompt(task_type: str, requirement: str, student_answer: str) -> str:
    subject = "before-and-after map" if task_type == "map" else "process diagram"
    return f"""
You are producing visual feedback for an IELTS Academic Task 1 student.
The supplied image is the official {subject}. Treat it as the authoritative visual
framework and style reference. Create a new clean diagram showing what the student's
written answer describes, so the student can compare it with the official image.

STRICT CONTENT RULES:
1. Preserve the original canvas orientation, visual style, colour family, typography,
   major regions and overall layout wherever the student's description supports them.
2. Include only objects, stages, connections, directions and changes that the student
   explicitly states or unambiguously implies.
3. Do not silently copy details from the official image when the student omits them.
   Leave omitted elements absent or visually neutral instead of inventing facts.
4. Keep all English labels short, legible and correctly spelled. Do not add explanatory
   paragraphs, scores, feedback notes, watermarks or decorative illustrations.
5. For a map, maintain north/south/east/west and relative positions. For a process,
   maintain the described sequence and arrow direction.
6. Output one flat, professional IELTS-style diagram, not a mockup or screenshot.

TASK REQUIREMENT:
{requirement.strip() or '(No separate task wording supplied.)'}

STUDENT ANSWER (source facts for the generated feedback image):
{student_answer.strip()}
""".strip()


def _extract_image_url(payload: dict[str, Any]) -> str:
    choices = payload.get("output", {}).get("choices", [])
    for choice in choices or []:
        content = choice.get("message", {}).get("content", [])
        for item in content or []:
            if item.get("type") == "image" and item.get("image"):
                return str(item["image"])
    code = payload.get("code") or "UnknownError"
    message = payload.get("message") or "Wan2.7 returned no image URL."
    raise WanImageRendererError(f"Wan2.7 generation failed ({code}): {message}")


def _save_downloaded_image(content: bytes, output_path: Path) -> None:
    if not content or len(content) > 30 * 1024 * 1024:
        raise WanImageRendererError("Wan2.7 returned an empty or unexpectedly large image.")
    try:
        with Image.open(io.BytesIO(content)) as source:
            image = source.convert("RGB")
            output_path.parent.mkdir(parents=True, exist_ok=True)
            image.save(output_path, format="PNG", optimize=True)
    except (OSError, ValueError) as exc:
        raise WanImageRendererError(f"Wan2.7 returned an invalid image: {exc}") from exc


class WanSpatialFeedbackService:
    def __init__(self, output_dir: str | Path, session=None):
        self.output_dir = Path(output_dir)
        self.session = session or requests.Session()

    def generate(
        self,
        *,
        task_type: str,
        requirement: str,
        student_answer: str,
        image_path: str | Path,
    ) -> tuple[dict, str]:
        task_type = (task_type or "").strip().lower()
        if task_type not in SPATIAL_TASK_TYPES:
            raise WanImageRendererError(f"Unsupported spatial task type: {task_type}")
        if not student_answer.strip():
            raise WanImageRendererError("Student answer cannot be empty.")
        api_key = get_wan_api_key()
        if not api_key:
            raise WanImageRendererError(
                "Wan2.7 is not configured. Set WAN_API_KEY (or DASHSCOPE_API_KEY) in backend/.env, "
                "then restart the backend."
            )

        model = get_wan_model()
        prompt = _build_edit_prompt(task_type, requirement, student_answer)
        request_body = {
            "model": model,
            "input": {
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"image": _encode_reference_image(image_path)},
                            {"text": prompt},
                        ],
                    }
                ]
            },
            "parameters": {"size": "2K", "n": 1, "watermark": False},
        }
        try:
            response = self.session.post(
                get_wan_endpoint(),
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=request_body,
                timeout=(15, 240),
            )
        except requests.RequestException as exc:
            raise WanImageRendererError(f"Cannot reach the Wan2.7 API: {exc}") from exc
        try:
            payload = response.json()
        except ValueError as exc:
            raise WanImageRendererError(f"Wan2.7 returned HTTP {response.status_code} with invalid JSON.") from exc
        if response.status_code >= 400:
            code = payload.get("code") or response.status_code
            message = payload.get("message") or "Request failed."
            raise WanImageRendererError(f"Wan2.7 API error ({code}): {message}")

        image_url = _extract_image_url(payload)
        try:
            image_response = self.session.get(image_url, timeout=(15, 120))
            image_response.raise_for_status()
        except requests.RequestException as exc:
            raise WanImageRendererError(f"Cannot download the Wan2.7 result image: {exc}") from exc

        filename = f"visual_feedback_{uuid.uuid4().hex}.png"
        _save_downloaded_image(image_response.content, self.output_dir / filename)
        result = {
            "schema_version": "1.0",
            "chart_type": task_type,
            "title": "Student-described map" if task_type == "map" else "Student-described process",
            "records": [],
            "comparison": {
                "strategy": "reference-image editing",
                "verification": "manual-review-required",
                "warnings": [
                    "This feedback image is generative and may contain text or layout errors.",
                    "Compare it with the original image before drawing conclusions.",
                ],
            },
            "style": {
                "renderer": "generative-image",
                "provider": "aliyun-wan",
                "model": model,
            },
        }
        return result, filename

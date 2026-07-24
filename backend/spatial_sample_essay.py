"""Qwen vision-language sample essays for IELTS map and process tasks."""

from __future__ import annotations

import base64
import io
import os
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from dotenv import load_dotenv
from openai import OpenAI
from PIL import Image

from next_sentence import summarize_flowchart
from sample_essay import SampleEssayResponse
from structure_feedback_agents import (
    OPTION_C_LABELS,
    REQUIRED_OPTION_C_NODE_TYPES,
    normalize_node_type,
)
from wan_image_renderer import SPATIAL_TASK_TYPES


load_dotenv()


DEFAULT_QWEN_VL_MODEL = "qwen3.7-plus"
DEFAULT_QWEN_VL_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"


def get_qwen_vl_api_key() -> str | None:
    return (
        os.getenv("QWEN_VL_API_KEY")
        or os.getenv("DASHSCOPE_API_KEY")
        or os.getenv("WAN_API_KEY")
    )


def get_qwen_vl_model() -> str:
    return (os.getenv("QWEN_VL_MODEL") or DEFAULT_QWEN_VL_MODEL).strip() or DEFAULT_QWEN_VL_MODEL


def get_qwen_vl_base_url() -> str:
    explicit = (os.getenv("QWEN_VL_BASE_URL") or "").strip()
    if explicit:
        return explicit.rstrip("/")

    workspace = (os.getenv("QWEN_VL_WORKSPACE_ID") or os.getenv("WAN_WORKSPACE_ID") or "").strip()
    if not workspace:
        return DEFAULT_QWEN_VL_BASE_URL
    parsed = urlparse(workspace if "://" in workspace else f"//{workspace}")
    hostname = (parsed.hostname or workspace).strip().rstrip("/")
    if not hostname.endswith(".maas.aliyuncs.com"):
        hostname = f"{hostname}.cn-beijing.maas.aliyuncs.com"
    return f"https://{hostname}/compatible-mode/v1"


def _encode_image(image_path: str | Path) -> str:
    path = Path(image_path)
    if not path.is_file():
        raise ValueError("The uploaded map or process image is missing.")
    try:
        with Image.open(path) as source:
            image = source.convert("RGB")
            image.thumbnail((4000, 4000))
            buffer = io.BytesIO()
            image.save(buffer, format="JPEG", quality=94, optimize=True)
    except (OSError, ValueError) as exc:
        raise ValueError(f"Cannot prepare the image for Qwen vision: {exc}") from exc
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"


def _structure_choice(flowchart: dict | None, use_standard_structure: bool | None) -> SampleEssayResponse | None:
    nodes = flowchart.get("nodes", []) if isinstance(flowchart, dict) else []
    node_types = {
        normalize_node_type(node.get("type"))
        for node in nodes
        if isinstance(node, dict)
    }
    missing = [
        OPTION_C_LABELS[node_type]
        for node_type in REQUIRED_OPTION_C_NODE_TYPES
        if node_type not in node_types
    ]
    if missing and use_standard_structure is None:
        return SampleEssayResponse(
            success=False,
            requires_choice=True,
            choice_info={
                "title": "Flowchart Structure Analysis",
                "missing_structures": missing,
                "options": [
                    {
                        "id": "flowchart",
                        "title": "Continue with current flowchart structure",
                        "description": "Use your flowchart as-is (may result in incomplete essay)",
                        "value": False,
                    },
                    {
                        "id": "standard",
                        "title": "Use standard IELTS structure",
                        "description": "Use an introduction, overview and detailed paragraphs",
                        "value": True,
                    },
                ],
                "message": f"Your flowchart is missing: {', '.join(missing)}. Choose how to proceed:",
            },
        )
    return None


def _prompt(
    task_type: str,
    requirement: str,
    flowchart: dict | None,
    use_standard_structure: bool | None,
    min_words: int,
) -> str:
    visual_name = "map or site-plan visual" if task_type == "map" else "process diagram"
    target_min = max(180, min_words + 30)
    target_max = max(220, target_min + 40)
    if use_standard_structure or not flowchart or not flowchart.get("nodes"):
        structure = (
            "Use the standard IELTS Task 1 structure: a paraphrased introduction, a clear overview, "
            "and two logically grouped detail paragraphs."
        )
    else:
        structure = (
            "Follow this student-selected writing plan while keeping the report coherent:\n"
            f"{summarize_flowchart(flowchart)}"
        )

    task_guidance = (
        "For a map, identify only the time states actually shown, preserve compass directions and "
        "relative positions, and describe visible additions, removals, replacements and unchanged "
        "features. If the image shows only one layout, do not invent a second state or changes."
        if task_type == "map"
        else
        "For a process, identify whether it is linear or cyclical, state the start and end points, "
        "and describe every visible stage and arrow in the correct order using the passive voice where appropriate."
    )
    return f"""
The attached image is the authoritative IELTS Academic Task 1 {visual_name}.
Write a high-quality sample report between {target_min} and {target_max} words. The final
report must never contain fewer than {min_words} words.

Factual rules:
- Read facts directly from the image. Do not invent objects, stages, directions, changes, causes or measurements.
- Cover the main features in the overview and support them with accurate details.
- Use a neutral academic tone, no bullet points, no headings, no first person and no conclusion with personal opinions.
- Do not mention that you are an AI or that you inspected an image.
- {task_guidance}

Writing structure:
{structure}

Task wording:
{requirement.strip() or f'Write an IELTS Academic Task 1 report for this {visual_name}.'}

Return only the raw English essay.
""".strip()


def _extract_content(completion: Any) -> str:
    if not completion.choices:
        return ""
    content = completion.choices[0].message.content
    return str(content or "").strip()


def generate_spatial_sample_essay(
    *,
    image_path: str | Path,
    chart_type: str,
    requirement: str,
    flowchart: dict | None,
    use_standard_structure: bool | None = None,
    min_words: int = 150,
    client: Any | None = None,
) -> SampleEssayResponse:
    task_type = (chart_type or "").strip().lower()
    if task_type not in SPATIAL_TASK_TYPES:
        return SampleEssayResponse(success=False, error=f"Unsupported spatial task type: {task_type}")

    choice = _structure_choice(flowchart, use_standard_structure)
    if choice:
        return choice
    api_key = get_qwen_vl_api_key()
    if not api_key and client is None:
        return SampleEssayResponse(
            success=False,
            error=(
                "Qwen vision is not configured. Set DASHSCOPE_API_KEY (or reuse WAN_API_KEY) "
                "and WAN_WORKSPACE_ID in backend/.env, then restart the backend."
            ),
        )

    model = get_qwen_vl_model()
    prompt = _prompt(task_type, requirement, flowchart, use_standard_structure, min_words)
    vision_client = client or OpenAI(api_key=api_key, base_url=get_qwen_vl_base_url())
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": _encode_image(image_path)}},
            ],
        }
    ]
    try:
        essay = ""
        attempts = 0
        target_min = max(180, min_words + 30)
        target_max = max(220, target_min + 40)
        for attempt in range(3):
            completion = vision_client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.2 if attempt == 0 else 0,
                max_tokens=1200,
                extra_body={"enable_thinking": False},
            )
            essay = _extract_content(completion)
            attempts = attempt + 1
            word_count = len(essay.split())
            if word_count >= min_words:
                break
            messages.append({"role": "assistant", "content": essay})
            messages.append(
                {
                    "role": "user",
                    "content": (
                        f"The draft is only {word_count} words and does not meet the {min_words}-word "
                        f"minimum. Rewrite the complete report to between {target_min} and "
                        f"{target_max} words. Add accurate visible details, not repetition or invented facts. "
                        "Return only the complete revised report."
                    ),
                }
            )

        word_count = len(essay.split())
        if essay and word_count < min_words:
            required_addition = max(30, min_words - word_count + 15)
            messages.append({"role": "assistant", "content": essay})
            messages.append(
                {
                    "role": "user",
                    "content": (
                        f"Write one additional detail paragraph of at least {required_addition} words "
                        "to append to the report. Use only facts visible in the image, avoid repeating "
                        "the overview, and return only the new paragraph."
                    ),
                }
            )
            completion = vision_client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0,
                max_tokens=300,
                extra_body={"enable_thinking": False},
            )
            addition = _extract_content(completion)
            if addition:
                essay = f"{essay}\n\n{addition}"
            attempts += 1
    except Exception as exc:
        return SampleEssayResponse(
            success=False,
            error=f"Qwen vision sample essay generation failed with model {model}: {exc}",
            debug={"model": model, "error_type": exc.__class__.__name__},
        )

    if not essay:
        return SampleEssayResponse(
            success=False,
            error=f"Qwen vision returned an empty sample essay with model {model}.",
            debug={"model": model, "words": 0},
        )
    word_count = len(essay.split())
    if word_count < min_words:
        return SampleEssayResponse(
            success=False,
            error=(
                f"Qwen vision returned only {word_count} words after automatic rewriting and "
                f"expansion; at least {min_words} are required for an IELTS sample answer."
            ),
            debug={"model": model, "words": word_count, "attempts": attempts},
        )
    return SampleEssayResponse(
        success=True,
        essay=essay,
        debug={
            "provider": "aliyun-qwen-vl",
            "model": model,
            "words": word_count,
            "attempts": attempts,
            "chart_type": task_type,
        },
    )

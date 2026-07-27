"""Deterministic process-diagram feedback from a Qwen-extracted plan."""

from __future__ import annotations

import json
import math
import os
import re
import textwrap
import uuid
from pathlib import Path
from typing import Any

from openai import OpenAI
from PIL import Image, ImageDraw, ImageFont

from spatial_sample_essay import (
    _encode_image,
    get_qwen_vl_api_key,
    get_qwen_vl_base_url,
    get_qwen_vl_model,
)


PROCESS_PLAN_MODEL_MAX_TOKENS = 2200
PROCESS_PALETTE = [
    "#dbeafe",
    "#dcfce7",
    "#fef3c7",
    "#cffafe",
    "#fee2e2",
    "#ffedd5",
    "#ede9fe",
    "#e0f2fe",
]
LABEL_STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "been",
    "being",
    "by",
    "for",
    "from",
    "in",
    "into",
    "is",
    "it",
    "of",
    "on",
    "or",
    "subsequently",
    "the",
    "then",
    "these",
    "they",
    "this",
    "to",
    "was",
    "were",
    "with",
}


class ProcessFeedbackError(RuntimeError):
    pass


def _build_process_plan_prompt(requirement: str, student_answer: str) -> str:
    return f"""
You are extracting a process-diagram feedback specification for an IELTS writing tool.
The attached official diagram is authoritative ONLY for the framework: title, number
and order of stage slots, arrow direction, and whether the process is cyclical.
The STUDENT ANSWER is authoritative for every label that will appear inside those slots.

Return one JSON object with exactly this shape:
{{
  "source_title": "short title read from the image",
  "source_subtitle": "short subtitle or empty string",
  "cyclical": true,
  "stages": [
    {{
      "number": 1,
      "source_label": "label read from the official image",
      "student_evidence": "short exact contiguous quote from STUDENT ANSWER, or null",
      "student_label": "concise label using only facts and content words from student_evidence",
      "status": "accurate, changed, or omitted"
    }}
  ],
  "cycle_evidence": "short exact quote describing repetition, or null"
}}

Non-negotiable rules:
1. Return one stage object per numbered source stage, in source order.
2. Never correct, normalize, or replace a student's object with the official object.
   If the source says "recycling truck" but the student says "huge plane", the stage's
   student_evidence and student_label MUST say "plane"; source_label alone says "truck";
   status is "changed".
3. student_evidence must be an exact contiguous quote from STUDENT ANSWER and should be
   the shortest quote that identifies that stage, preferably 12 words or fewer.
4. When the student omits a source stage, use null evidence, an empty student_label,
   and status "omitted". Never copy source_label into student_label.
5. Do not add world knowledge or facts visible only in the source image.
6. Output JSON only, without Markdown fences.

TASK REQUIREMENT:
{requirement.strip() or "(No separate task wording supplied.)"}

STUDENT ANSWER:
{student_answer.strip()}
""".strip()


def _completion_text(completion: Any) -> str:
    if not completion.choices:
        return ""
    return str(completion.choices[0].message.content or "").strip()


def _parse_json_object(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ProcessFeedbackError(f"Qwen returned invalid process-plan JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ProcessFeedbackError("Qwen process plan must be a JSON object.")
    return payload


def _normalise_space(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _word_stem(word: str) -> str:
    value = word.casefold()
    for suffix in ("ingly", "edly", "ing", "ied", "ed", "es", "s"):
        if len(value) > len(suffix) + 3 and value.endswith(suffix):
            value = value[: -len(suffix)]
            break
    return value


def _content_words(text: str) -> set[str]:
    return {
        _word_stem(word)
        for word in re.findall(r"[A-Za-z0-9]+", text)
        if word.casefold() not in LABEL_STOP_WORDS
    }


def _student_label(label: str, evidence: str) -> str:
    cleaned_label = _normalise_space(label)
    evidence_words = _content_words(evidence)
    if cleaned_label and _content_words(cleaned_label) <= evidence_words:
        return cleaned_label
    words = _normalise_space(evidence).split()
    return " ".join(words[:14]).rstrip(".,;:")


def _validated_process_plan(payload: dict[str, Any], student_answer: str) -> dict[str, Any]:
    stages = payload.get("stages")
    if not isinstance(stages, list) or not 2 <= len(stages) <= 16:
        raise ProcessFeedbackError("Qwen process plan must contain between 2 and 16 stages.")

    normalised_answer = _normalise_space(student_answer).casefold()
    validated_stages: list[dict[str, Any]] = []
    for index, raw_stage in enumerate(stages, start=1):
        if not isinstance(raw_stage, dict):
            raise ProcessFeedbackError(f"Process stage {index} is not an object.")
        source_label = _normalise_space(str(raw_stage.get("source_label") or ""))
        evidence_value = raw_stage.get("student_evidence")
        evidence = (
            _normalise_space(str(evidence_value))
            if evidence_value is not None and str(evidence_value).strip()
            else ""
        )
        if evidence and evidence.casefold() not in normalised_answer:
            raise ProcessFeedbackError(
                f"Process stage {index} cites text that is not an exact quote from the student answer."
            )
        display_label = (
            _student_label(str(raw_stage.get("student_label") or ""), evidence)
            if evidence
            else ""
        )
        raw_status = str(raw_stage.get("status") or "").strip().casefold()
        status = raw_status if raw_status in {"accurate", "changed"} and evidence else "omitted"
        validated_stages.append(
            {
                "number": index,
                "source_label": source_label,
                "student_evidence": evidence or None,
                "student_label": display_label,
                "status": status,
            }
        )

    cycle_value = payload.get("cycle_evidence")
    cycle_evidence = (
        _normalise_space(str(cycle_value))
        if cycle_value is not None and str(cycle_value).strip()
        else ""
    )
    if cycle_evidence and cycle_evidence.casefold() not in normalised_answer:
        cycle_evidence = ""

    return {
        "source_title": _normalise_space(
            str(payload.get("source_title") or "Process described by the student")
        )[:120],
        "source_subtitle": _normalise_space(str(payload.get("source_subtitle") or ""))[:160],
        "cyclical": bool(payload.get("cyclical")),
        "cycle_evidence": cycle_evidence or None,
        "stages": validated_stages,
    }


def _font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    filenames = (
        ["DejaVuSans-Bold.ttf", "arialbd.ttf"]
        if bold
        else ["DejaVuSans.ttf", "arial.ttf"]
    )
    locations = [
        Path("/usr/share/fonts/truetype/dejavu"),
        Path("C:/Windows/Fonts"),
    ]
    for location in locations:
        for filename in filenames:
            path = location / filename
            if path.is_file():
                return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


def _wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, width: int) -> list[str]:
    lines: list[str] = []
    current = ""
    for word in text.split():
        candidate = f"{current} {word}".strip()
        if not current or draw.textbbox((0, 0), candidate, font=font)[2] <= width:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or [""]


def _fit_label(
    draw: ImageDraw.ImageDraw,
    text: str,
    *,
    width: int,
    height: int,
) -> tuple[ImageFont.ImageFont, list[str]]:
    for size in range(28, 15, -1):
        font = _font(size, bold=True)
        lines = _wrap_text(draw, text, font, width)
        line_height = draw.textbbox((0, 0), "Ag", font=font)[3] + 5
        if len(lines) <= 4 and len(lines) * line_height <= height:
            return font, lines
    font = _font(16, bold=True)
    return font, _wrap_text(draw, textwrap.shorten(text, width=70), font, width)[:4]


def _draw_arrow(
    draw: ImageDraw.ImageDraw,
    start: tuple[int, int],
    end: tuple[int, int],
    *,
    color: str = "#475569",
) -> None:
    draw.line([start, end], fill=color, width=8)
    x1, y1 = start
    x2, y2 = end
    angle = math.atan2(y2 - y1, x2 - x1)
    length = 18
    spread = 10
    points = [
        (x2, y2),
        (
            round(x2 - length * math.cos(angle) + spread * math.sin(angle)),
            round(y2 - length * math.sin(angle) - spread * math.cos(angle)),
        ),
        (
            round(x2 - length * math.cos(angle) - spread * math.sin(angle)),
            round(y2 - length * math.sin(angle) + spread * math.cos(angle)),
        ),
    ]
    draw.polygon(points, fill=color)


def _stage_positions(stage_count: int, box_width: int) -> list[tuple[int, int]]:
    if stage_count <= 4:
        columns = stage_count
        xs = [
            round(70 + index * ((1460 - box_width) / max(1, columns - 1)))
            for index in range(columns)
        ]
        return [(x, 390) for x in xs]

    top_count = math.ceil(stage_count / 2)
    bottom_count = stage_count - top_count
    top_xs = [
        round(70 + index * ((1460 - box_width) / max(1, top_count - 1)))
        for index in range(top_count)
    ]
    bottom_xs = [
        round(70 + index * ((1460 - box_width) / max(1, bottom_count - 1)))
        for index in range(bottom_count)
    ]
    return [(x, 230) for x in top_xs] + [(x, 620) for x in reversed(bottom_xs)]


def _connection_points(
    source: tuple[int, int],
    target: tuple[int, int],
    box_width: int,
    box_height: int,
) -> tuple[tuple[int, int], tuple[int, int]]:
    sx, sy = source
    tx, ty = target
    if sy == ty and tx > sx:
        return (sx + box_width + 12, sy + box_height // 2), (tx - 14, ty + box_height // 2)
    if sy == ty:
        return (sx - 12, sy + box_height // 2), (tx + box_width + 14, ty + box_height // 2)
    return (sx + box_width // 2, sy + box_height + 12), (tx + box_width // 2, ty - 14)


def render_process_feedback(plan: dict[str, Any], output_path: str | Path) -> None:
    canvas = Image.new("RGB", (1600, 1000), "#f8fafc")
    draw = ImageDraw.Draw(canvas)
    title_font = _font(46, bold=True)
    subtitle_font = _font(23)
    body_color = "#172033"
    line_color = "#475569"
    title = plan["source_title"] or "Process described by the student"
    subtitle = plan["source_subtitle"] or (
        f"Student-described content in the official {len(plan['stages'])}-stage framework"
    )
    draw.text((800, 55), title, font=title_font, fill=body_color, anchor="ma")
    draw.text((800, 118), subtitle, font=subtitle_font, fill="#64748b", anchor="ma")

    box_width = 270
    box_height = 150
    positions = _stage_positions(len(plan["stages"]), box_width)
    for source, target in zip(positions, positions[1:]):
        start, end = _connection_points(source, target, box_width, box_height)
        _draw_arrow(draw, start, end, color=line_color)

    if plan["cyclical"] and len(positions) > 1:
        last_x, last_y = positions[-1]
        first_x, first_y = positions[0]
        return_y = 900
        start = (last_x + box_width // 2, last_y + box_height + 10)
        end = (first_x - 18, first_y + box_height // 2)
        route = [
            start,
            (start[0], return_y),
            (35, return_y),
            (35, end[1]),
        ]
        draw.line(route, fill=line_color, width=8)
        _draw_arrow(draw, route[-1], end, color=line_color)
        if plan.get("cycle_evidence"):
            draw.text(
                (800, 930),
                str(plan["cycle_evidence"]),
                font=_font(20),
                fill="#64748b",
                anchor="ma",
            )

    number_font = _font(23, bold=True)
    for index, (stage, (x, y)) in enumerate(zip(plan["stages"], positions)):
        status = stage["status"]
        fill = PROCESS_PALETTE[index % len(PROCESS_PALETTE)]
        outline = "#be185d" if status == "changed" else "#334155"
        if status == "omitted":
            fill = "#f1f5f9"
            outline = "#94a3b8"
        draw.rounded_rectangle(
            (x, y, x + box_width, y + box_height),
            radius=8,
            fill=fill,
            outline=outline,
            width=5,
        )
        circle_x = x + 38
        circle_y = y + 36
        draw.ellipse(
            (circle_x - 25, circle_y - 25, circle_x + 25, circle_y + 25),
            fill=outline,
        )
        draw.text(
            (circle_x, circle_y),
            str(stage["number"]),
            font=number_font,
            fill="white",
            anchor="mm",
        )

        label = stage["student_label"] or "Not described"
        font, lines = _fit_label(draw, label, width=box_width - 40, height=88)
        line_height = draw.textbbox((0, 0), "Ag", font=font)[3] + 5
        block_height = line_height * len(lines)
        text_y = y + 55 + max(0, (box_height - 55 - block_height) // 2)
        text_fill = "#64748b" if status == "omitted" else body_color
        for line in lines:
            draw.text(
                (x + box_width // 2, text_y),
                line,
                font=font,
                fill=text_fill,
                anchor="ma",
            )
            text_y += line_height

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output, format="PNG", optimize=True)


class ProcessFeedbackService:
    def __init__(self, output_dir: str | Path, client: Any | None = None):
        self.output_dir = Path(output_dir)
        self.client = client

    def _extract_plan(
        self,
        *,
        requirement: str,
        student_answer: str,
        image_path: str | Path,
    ) -> tuple[dict[str, Any], str, int]:
        api_key = get_qwen_vl_api_key()
        if not api_key and self.client is None:
            raise ProcessFeedbackError(
                "Qwen vision is required for process feedback. Configure QWEN_VL_API_KEY "
                "(or reuse WAN_API_KEY) and restart the backend."
            )
        model = get_qwen_vl_model()
        client = self.client or OpenAI(api_key=api_key, base_url=get_qwen_vl_base_url())
        messages: list[dict[str, Any]] = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": _build_process_plan_prompt(requirement, student_answer),
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": _encode_image(image_path)},
                    },
                ],
            }
        ]
        last_error = ""
        for attempt in range(2):
            completion = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0,
                max_tokens=PROCESS_PLAN_MODEL_MAX_TOKENS,
                extra_body={"enable_thinking": False},
            )
            raw = _completion_text(completion)
            try:
                return _validated_process_plan(_parse_json_object(raw), student_answer), model, attempt + 1
            except ProcessFeedbackError as exc:
                last_error = str(exc)
                messages.extend(
                    [
                        {"role": "assistant", "content": raw},
                        {
                            "role": "user",
                            "content": (
                                f"The JSON failed validation: {last_error} "
                                "Return a corrected complete JSON object. Every student_evidence "
                                "must be an exact quote, and source wording must never leak into "
                                "student_label."
                            ),
                        },
                    ]
                )
        raise ProcessFeedbackError(last_error or "Qwen could not produce a valid process plan.")

    def generate(
        self,
        *,
        task_type: str,
        requirement: str,
        student_answer: str,
        image_path: str | Path,
    ) -> tuple[dict[str, Any], str]:
        if (task_type or "").strip().casefold() != "process":
            raise ProcessFeedbackError(f"Unsupported deterministic process type: {task_type}")
        if not student_answer.strip():
            raise ProcessFeedbackError("Student answer cannot be empty.")

        plan, model, attempts = self._extract_plan(
            requirement=requirement,
            student_answer=student_answer,
            image_path=image_path,
        )
        filename = f"visual_feedback_{uuid.uuid4().hex}.png"
        render_process_feedback(plan, self.output_dir / filename)
        changed = [stage for stage in plan["stages"] if stage["status"] == "changed"]
        omitted = [stage for stage in plan["stages"] if stage["status"] == "omitted"]
        result = {
            "schema_version": "1.0",
            "chart_type": "process",
            "title": plan["source_title"],
            "records": [
                {
                    "category": f"Stage {stage['number']}",
                    "value": stage["student_label"] or None,
                    "official_value": stage["source_label"] or None,
                    "feedback_status": stage["status"],
                    "student_evidence": stage["student_evidence"],
                }
                for stage in plan["stages"]
            ],
            "comparison": {
                "strategy": "source-framework/student-evidence",
                "changed_stages": [stage["number"] for stage in changed],
                "omitted_stages": [stage["number"] for stage in omitted],
                "warnings": [],
            },
            "style": {
                "renderer": "deterministic-process-diagram",
                "provider": "aliyun-qwen-vl",
                "model": model,
                "planning_attempts": attempts,
            },
        }
        return result, filename

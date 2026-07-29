"""Verified map feedback built from student-supported labels and Wan image editing."""

from __future__ import annotations

import json
import re
import tempfile
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
from wan_image_renderer import WanSpatialFeedbackService


MAP_PLAN_MAX_TOKENS = 3200
MAP_AUDIT_MAX_TOKENS = 1200
MAP_LABEL_STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "been",
    "being",
    "between",
    "by",
    "called",
    "constructed",
    "currently",
    "existing",
    "for",
    "from",
    "has",
    "have",
    "in",
    "include",
    "includes",
    "is",
    "it",
    "located",
    "marked",
    "new",
    "north",
    "north-east",
    "north-west",
    "northeast",
    "northwest",
    "of",
    "on",
    "one",
    "original",
    "position",
    "positions",
    "remain",
    "remains",
    "situated",
    "south",
    "south-east",
    "south-west",
    "southeast",
    "southwest",
    "the",
    "their",
    "to",
    "unchanged",
    "was",
    "west",
    "were",
    "which",
    "with",
    "east",
}


class MapFeedbackError(RuntimeError):
    pass


def _build_map_plan_prompt(requirement: str, student_answer: str) -> str:
    return f"""
You are preparing a label-replacement plan for visual feedback on an IELTS map task.
The attached official map is authoritative only for the visual framework: panel count,
panel titles, roads, relative positions, boundaries, compass directions and drawing style.
The STUDENT ANSWER is authoritative for feature names and described map contents.

Read every visible English label and return one JSON object with exactly this shape:
{{
  "source_title": "short overall title or empty string",
  "labels": [
    {{
      "source_text": "exact visible label",
      "role": "framework or feature",
      "bbox": [left, top, right, bottom],
      "rotation": 0,
      "student_evidence": "short exact contiguous quote from STUDENT ANSWER, or null",
      "student_text": "short map label supported only by student_evidence, or empty string",
      "action": "preserve, replace, or omit"
    }}
  ]
}}

Bounding boxes use integer coordinates from 0 to 1000 relative to the complete image.
Return a separate label entry for every visible occurrence, including a feature repeated
in present/future panels.

Non-negotiable rules:
1. role="framework" covers panel titles, compass letters, scale labels and legend headings.
   Framework labels are preserved even when the essay does not repeat them.
2. role="feature" covers places, buildings, roads, facilities, land uses, symbols and
   feature legend items.
3. For each feature, decide solely from STUDENT ANSWER:
   - preserve when the student names the same feature at that position;
   - replace when the student names a different feature at that position;
   - omit when the student does not describe that feature.
4. student_evidence must be a short exact contiguous quote from STUDENT ANSWER. Never
   paraphrase evidence. Use null for omitted features and framework labels.
5. student_text must use only facts and content words found in student_evidence. If the
   source says "school" but the student says "restaurant", student_text MUST be
   "restaurant", action MUST be "replace", and "school" may appear only in source_text.
6. Never copy a source-only feature into student_text. Do not correct the student's facts.
7. Keep road names when the student names them. Treat map symbols with text labels as
   feature labels. Ignore tiny unreadable text rather than guessing it.
8. Output JSON only, without Markdown fences.

TASK REQUIREMENT:
{requirement.strip() or "(No separate task wording supplied.)"}

STUDENT ANSWER:
{student_answer.strip()}
""".strip()


def _build_audit_prompt(
    forbidden_replacements: dict[str, str],
) -> str:
    rules = [
        {
            "forbidden": source,
            "replacement": replacement or None,
        }
        for source, replacement in sorted(forbidden_replacements.items())
    ]
    return f"""
Inspect the attached generated IELTS map as OCR, not as a semantic scene.
Check whether any forbidden source label is still visibly written anywhere.

LABEL RULES:
{json.dumps(rules, ensure_ascii=True)}

Return one JSON object:
{{
  "forbidden_occurrences": [
    {{
      "text": "exact forbidden text that is visibly present",
      "bbox": [left, top, right, bottom],
      "replacement_visible_nearby": true
    }}
  ]
}}

Bounding boxes use integer coordinates from 0 to 1000 relative to the complete image.
Only report actual visible text. Do not infer a word from a shape or location. If none
of the forbidden labels is visibly written, return an empty list. JSON only.
""".strip()


def _completion_text(completion: Any) -> str:
    if not getattr(completion, "choices", None):
        return ""
    return str(completion.choices[0].message.content or "").strip()


def _parse_json_object(text: str, *, context: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise MapFeedbackError(f"Qwen returned invalid {context} JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise MapFeedbackError(f"Qwen {context} must be a JSON object.")
    return payload


def _normalise_space(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _canonical_label(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.casefold()).strip()


def _looks_like_framework_label(text: str) -> bool:
    canonical = _canonical_label(text)
    if canonical in {
        "after",
        "before",
        "current",
        "current plan",
        "future",
        "future plan",
        "key",
        "legend",
        "n",
        "north",
        "present",
        "present day",
        "proposed",
        "proposed plan",
    }:
        return True
    if re.fullmatch(r"(?:19|20)\d{2}", canonical):
        return True
    if re.fullmatch(r"\d+(?:\.\d+)?\s*(?:m|km|metres|meters)", canonical):
        return True
    return bool(
        re.search(r"\b(?:present|future|current|proposed)\b.*\b(?:day|map|plan)\b", canonical)
    )


def _content_words(text: str) -> set[str]:
    return {
        word.casefold()
        for word in re.findall(r"[A-Za-z0-9]+", text)
        if word.casefold() not in MAP_LABEL_STOP_WORDS
    }


def _fallback_student_label(evidence: str) -> str:
    words = [
        word
        for word in re.findall(r"[A-Za-z0-9]+(?:[-'][A-Za-z0-9]+)*", evidence)
        if word.casefold() not in MAP_LABEL_STOP_WORDS
    ]
    return " ".join(words[:4])


def _student_label(proposed: str, evidence: str) -> str:
    cleaned = _normalise_space(proposed)
    evidence_words = _content_words(evidence)
    if cleaned and _content_words(cleaned) and _content_words(cleaned) <= evidence_words:
        return cleaned[:80]
    return _fallback_student_label(evidence)[:80]


def _validated_bbox(
    value: Any,
    *,
    context: str,
    image_size: tuple[int, int] | None = None,
) -> list[int]:
    if not isinstance(value, list) or len(value) != 4:
        raise MapFeedbackError(f"{context} must have a four-number bbox.")
    try:
        raw = [float(item) for item in value]
    except (TypeError, ValueError) as exc:
        raise MapFeedbackError(f"{context} bbox contains a non-number.") from exc
    if image_size and max(raw) > 1000:
        width, height = image_size
        raw = [
            raw[0] * 1000 / width,
            raw[1] * 1000 / height,
            raw[2] * 1000 / width,
            raw[3] * 1000 / height,
        ]
    left, top, right, bottom = [round(item) for item in raw]
    left = max(0, min(1000, left))
    top = max(0, min(1000, top))
    right = max(0, min(1000, right))
    bottom = max(0, min(1000, bottom))
    if right - left < 3 or bottom - top < 3:
        raise MapFeedbackError(f"{context} bbox is empty or too small.")
    return [left, top, right, bottom]


def _validated_map_plan(
    payload: dict[str, Any],
    student_answer: str,
    *,
    image_size: tuple[int, int] | None = None,
) -> dict[str, Any]:
    raw_labels = payload.get("labels")
    if not isinstance(raw_labels, list) or not raw_labels:
        raise MapFeedbackError("Qwen map plan must contain at least one visible label.")
    if len(raw_labels) > 100:
        raise MapFeedbackError("Qwen map plan contains an unreasonable number of labels.")

    normalised_answer = _normalise_space(student_answer).casefold()
    labels: list[dict[str, Any]] = []
    for index, raw in enumerate(raw_labels, start=1):
        if not isinstance(raw, dict):
            raise MapFeedbackError(f"Map label {index} is not an object.")
        source_text = _normalise_space(str(raw.get("source_text") or ""))
        if not source_text:
            raise MapFeedbackError(f"Map label {index} has no source text.")
        bbox = _validated_bbox(
            raw.get("bbox"),
            context=f"Map label {index}",
            image_size=image_size,
        )
        proposed_role = str(raw.get("role") or "").strip().casefold()
        role = (
            "framework"
            if proposed_role == "framework" and _looks_like_framework_label(source_text)
            else "feature"
        )
        try:
            rotation = max(-180, min(180, round(float(raw.get("rotation") or 0))))
        except (TypeError, ValueError):
            rotation = 0

        evidence_value = raw.get("student_evidence")
        evidence = (
            _normalise_space(str(evidence_value))
            if evidence_value is not None and str(evidence_value).strip()
            else ""
        )
        if evidence and evidence.casefold() not in normalised_answer:
            raise MapFeedbackError(
                f"Map label {index} cites text that is not an exact quote from the student answer."
            )

        action = str(raw.get("action") or "").strip().casefold()
        if role == "framework":
            action = "preserve"
            evidence = ""
            student_text = source_text
        elif action in {"preserve", "replace"} and evidence:
            student_text = _student_label(str(raw.get("student_text") or ""), evidence)
            if not student_text:
                action = "omit"
        else:
            action = "omit"
            evidence = ""
            student_text = ""

        if action == "preserve" and _canonical_label(student_text) != _canonical_label(source_text):
            action = "replace"
        if action == "replace" and _canonical_label(student_text) == _canonical_label(source_text):
            action = "preserve"

        labels.append(
            {
                "source_text": source_text,
                "role": role,
                "bbox": bbox,
                "rotation": rotation,
                "student_evidence": evidence or None,
                "student_text": student_text,
                "action": action,
            }
        )

    return {
        "source_title": _normalise_space(str(payload.get("source_title") or ""))[:140],
        "labels": labels,
    }


def _forbidden_replacements(plan: dict[str, Any], student_answer: str) -> dict[str, str]:
    answer = _canonical_label(student_answer)
    replacements: dict[str, str] = {}
    for label in plan["labels"]:
        if label["role"] != "feature" or label["action"] not in {"replace", "omit"}:
            continue
        source = _canonical_label(label["source_text"])
        if not source or re.search(rf"\b{re.escape(source)}\b", answer):
            continue
        replacement = label["student_text"] if label["action"] == "replace" else ""
        existing = replacements.get(source)
        if existing is None or (not existing and replacement):
            replacements[source] = replacement
    return replacements


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in (
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("C:/Windows/Fonts/arial.ttf"),
    ):
        if path.is_file():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


def _pixel_bbox(normalised: list[int], size: tuple[int, int], *, pad: int = 0) -> tuple[int, int, int, int]:
    width, height = size
    left = max(0, round(normalised[0] * width / 1000) - pad)
    top = max(0, round(normalised[1] * height / 1000) - pad)
    right = min(width, round(normalised[2] * width / 1000) + pad)
    bottom = min(height, round(normalised[3] * height / 1000) + pad)
    return left, top, right, bottom


def _background_colour(image: Image.Image, box: tuple[int, int, int, int]) -> tuple[int, int, int]:
    left, top, right, bottom = box
    points = [
        (max(0, left - 2), max(0, top - 2)),
        (min(image.width - 1, right + 2), max(0, top - 2)),
        (max(0, left - 2), min(image.height - 1, bottom + 2)),
        (min(image.width - 1, right + 2), min(image.height - 1, bottom + 2)),
    ]
    colours = [image.getpixel(point)[:3] for point in points]
    return max(colours, key=sum)


def _draw_label(
    image: Image.Image,
    box: tuple[int, int, int, int],
    text: str,
) -> None:
    if not text:
        return
    draw = ImageDraw.Draw(image)
    left, top, right, bottom = box
    max_width = max(10, right - left - 4)
    max_height = max(10, bottom - top - 2)
    chosen = _font(10)
    for size in range(min(42, max_height), 9, -1):
        candidate = _font(size)
        text_box = draw.textbbox((0, 0), text, font=candidate)
        if text_box[2] - text_box[0] <= max_width and text_box[3] - text_box[1] <= max_height:
            chosen = candidate
            break
    draw.text(
        ((left + right) // 2, (top + bottom) // 2),
        text,
        font=chosen,
        fill="#111827",
        anchor="mm",
    )


def _prepare_reference(
    image_path: str | Path,
    output_path: str | Path,
    plan: dict[str, Any],
) -> None:
    try:
        with Image.open(image_path) as source:
            image = source.convert("RGB")
    except (OSError, ValueError) as exc:
        raise MapFeedbackError(f"Cannot prepare the source map: {exc}") from exc

    draw = ImageDraw.Draw(image)
    for label in plan["labels"]:
        if label["action"] not in {"replace", "omit"}:
            continue
        box = _pixel_bbox(label["bbox"], image.size, pad=4)
        draw.rectangle(box, fill=_background_colour(image, box))
        if label["action"] == "replace":
            _draw_label(image, box, label["student_text"])
    image.save(output_path, format="PNG", optimize=True)


def _validated_audit(
    payload: dict[str, Any],
    forbidden_replacements: dict[str, str],
    *,
    image_size: tuple[int, int] | None = None,
) -> list[dict[str, Any]]:
    raw_occurrences = payload.get("forbidden_occurrences")
    if not isinstance(raw_occurrences, list):
        raise MapFeedbackError("Qwen map audit did not return an occurrence list.")
    occurrences: list[dict[str, Any]] = []
    for index, raw in enumerate(raw_occurrences, start=1):
        if not isinstance(raw, dict):
            continue
        text = _canonical_label(str(raw.get("text") or ""))
        matched = next(
            (
                forbidden
                for forbidden in forbidden_replacements
                if text == forbidden or re.search(rf"\b{re.escape(forbidden)}\b", text)
            ),
            None,
        )
        if not matched:
            continue
        occurrences.append(
            {
                "text": matched,
                "bbox": _validated_bbox(
                    raw.get("bbox"),
                    context=f"Audit occurrence {index}",
                    image_size=image_size,
                ),
                "replacement": forbidden_replacements[matched],
                "replacement_visible_nearby": bool(raw.get("replacement_visible_nearby")),
            }
        )
    return occurrences


def _repair_output_labels(image_path: str | Path, occurrences: list[dict[str, Any]]) -> None:
    try:
        with Image.open(image_path) as source:
            image = source.convert("RGB")
    except (OSError, ValueError) as exc:
        raise MapFeedbackError(f"Cannot open the generated map for label repair: {exc}") from exc
    draw = ImageDraw.Draw(image)
    for occurrence in occurrences:
        box = _pixel_bbox(occurrence["bbox"], image.size, pad=5)
        draw.rectangle(box, fill=_background_colour(image, box))
        if occurrence["replacement"] and not occurrence["replacement_visible_nearby"]:
            _draw_label(image, box, occurrence["replacement"])
    image.save(image_path, format="PNG", optimize=True)


class MapFeedbackService:
    def __init__(
        self,
        output_dir: str | Path,
        *,
        client: Any | None = None,
        wan_service: Any | None = None,
    ):
        self.output_dir = Path(output_dir)
        self.client = client
        self.wan_service = wan_service

    def _vision_client(self) -> Any:
        api_key = get_qwen_vl_api_key()
        if not api_key and self.client is None:
            raise MapFeedbackError(
                "Qwen vision is required for verified map feedback. Configure "
                "QWEN_VL_API_KEY (or reuse WAN_API_KEY) and restart the backend."
            )
        return self.client or OpenAI(api_key=api_key, base_url=get_qwen_vl_base_url())

    def _complete(self, messages: list[dict[str, Any]], *, max_tokens: int) -> str:
        completion = self._vision_client().chat.completions.create(
            model=get_qwen_vl_model(),
            messages=messages,
            temperature=0,
            max_tokens=max_tokens,
            extra_body={"enable_thinking": False},
        )
        return _completion_text(completion)

    def _extract_plan(
        self,
        *,
        requirement: str,
        student_answer: str,
        image_path: str | Path,
    ) -> tuple[dict[str, Any], int]:
        messages: list[dict[str, Any]] = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": _build_map_plan_prompt(requirement, student_answer),
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": _encode_image(image_path)},
                    },
                ],
            }
        ]
        last_error = ""
        try:
            with Image.open(image_path) as source:
                image_size = source.size
        except (OSError, ValueError) as exc:
            raise MapFeedbackError(f"Cannot inspect the source map: {exc}") from exc
        for attempt in range(2):
            raw = self._complete(messages, max_tokens=MAP_PLAN_MAX_TOKENS)
            try:
                plan = _validated_map_plan(
                    _parse_json_object(raw, context="map-plan"),
                    student_answer,
                    image_size=image_size,
                )
                return plan, attempt + 1
            except MapFeedbackError as exc:
                last_error = str(exc)
                messages.extend(
                    [
                        {"role": "assistant", "content": raw},
                        {
                            "role": "user",
                            "content": (
                                f"The JSON failed validation: {last_error} Return a corrected "
                                "complete JSON object. Evidence must be an exact quote, and no "
                                "source-only feature word may appear in student_text."
                            ),
                        },
                    ]
                )
        raise MapFeedbackError(last_error or "Qwen could not produce a valid map plan.")

    def _audit(
        self,
        image_path: str | Path,
        forbidden_replacements: dict[str, str],
    ) -> list[dict[str, Any]]:
        if not forbidden_replacements:
            return []
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": _build_audit_prompt(forbidden_replacements),
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": _encode_image(image_path)},
                    },
                ],
            }
        ]
        raw = self._complete(messages, max_tokens=MAP_AUDIT_MAX_TOKENS)
        try:
            with Image.open(image_path) as source:
                image_size = source.size
        except (OSError, ValueError) as exc:
            raise MapFeedbackError(f"Cannot inspect the generated map: {exc}") from exc
        return _validated_audit(
            _parse_json_object(raw, context="map-audit"),
            forbidden_replacements,
            image_size=image_size,
        )

    def generate(
        self,
        *,
        task_type: str,
        requirement: str,
        student_answer: str,
        image_path: str | Path,
    ) -> tuple[dict[str, Any], str]:
        if (task_type or "").strip().casefold() != "map":
            raise MapFeedbackError(f"Unsupported verified map type: {task_type}")
        if not student_answer.strip():
            raise MapFeedbackError("Student answer cannot be empty.")

        plan, planning_attempts = self._extract_plan(
            requirement=requirement,
            student_answer=student_answer,
            image_path=image_path,
        )
        forbidden_replacements = _forbidden_replacements(plan, student_answer)
        replacement_manifest = [
            {
                "source": label["source_text"],
                "student": label["student_text"] or None,
                "action": label["action"],
            }
            for label in plan["labels"]
            if label["action"] in {"replace", "omit"}
        ]
        augmented_requirement = f"""
{requirement.strip()}

VERIFIED LABEL MANIFEST:
{json.dumps(replacement_manifest, ensure_ascii=True)}

The supplied reference image has already had source-only labels physically removed
or replaced. Preserve those sanitized labels exactly. Never recreate any forbidden
source label: {", ".join(sorted(forbidden_replacements)) or "(none)"}.
""".strip()

        self.output_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="vividwrite-map-") as folder:
            prepared_path = Path(folder) / "student-supported-reference.png"
            _prepare_reference(image_path, prepared_path, plan)
            wan = self.wan_service or WanSpatialFeedbackService(self.output_dir)
            wan_result, filename = wan.generate(
                task_type="map",
                requirement=augmented_requirement,
                student_answer=student_answer,
                image_path=prepared_path,
            )

        output_path = self.output_dir / filename
        if not output_path.is_file():
            raise MapFeedbackError("Wan did not save the generated map.")

        occurrences = self._audit(output_path, forbidden_replacements)
        repair_count = len(occurrences)
        if occurrences:
            _repair_output_labels(output_path, occurrences)
            remaining = self._audit(output_path, forbidden_replacements)
            if remaining:
                output_path.unlink(missing_ok=True)
                remaining_words = ", ".join(sorted({item["text"] for item in remaining}))
                raise MapFeedbackError(
                    "Generated map still contains source-only labels after repair: "
                    f"{remaining_words}. No misleading feedback image was returned."
                )

        records = [
            {
                "category": f"Map label {index}",
                "value": label["student_text"] or None,
                "official_value": label["source_text"],
                "feedback_status": label["action"],
                "student_evidence": label["student_evidence"],
                "bbox": label["bbox"],
            }
            for index, label in enumerate(plan["labels"], start=1)
            if label["role"] == "feature"
        ]
        result = {
            **wan_result,
            "chart_type": "map",
            "title": plan["source_title"] or "Student-described map",
            "records": records,
            "comparison": {
                "strategy": "sanitized-reference/student-evidence/post-generation-audit",
                "forbidden_source_labels": sorted(forbidden_replacements),
                "label_repairs": repair_count,
                "warnings": [
                    "Map geometry remains generative; labels are checked against the student answer."
                ],
            },
            "style": {
                **wan_result.get("style", {}),
                "renderer": "verified-generative-map",
                "planning_provider": "aliyun-qwen-vl",
                "planning_model": get_qwen_vl_model(),
                "planning_attempts": planning_attempts,
            },
        }
        return result, filename

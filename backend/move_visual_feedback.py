"""Render complementary visual cues for rhetorical Moves 2, 3, and 5.

The renderer annotates a copy of the original task image. It never changes the
official image or invents chart values; target records come from the validated
move-feedback contract.
"""

from __future__ import annotations

import math
import uuid
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps


CURRENT_COLOR = "#D92D20"
RECOMMENDED_COLOR = "#1677CC"
HEADER_BACKGROUND = "#FFFFFF"
HEADER_TEXT = "#202124"


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _official_value(record: dict) -> float | None:
    official = _number(record.get("official_value"))
    return official if official is not None else _number(record.get("value"))


def _record_label(record: dict) -> str:
    parts: list[str] = []
    for field in ("category", "series", "period", "region"):
        value = record.get(field)
        if value not in (None, "") and str(value) not in parts:
            parts.append(str(value))
    value = _official_value(record)
    value_text = f"{value:g}" if value is not None else ""
    return " · ".join(parts + ([value_text] if value_text else [])) or "Chart feature"


def _load_font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    candidates = (
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    )
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def _colour_data_bbox(image: Image.Image) -> tuple[int, int, int, int] | None:
    """Estimate a plot-data extent from saturated marks, excluding titles/legends."""
    rgb = np.asarray(image.convert("RGB"))
    height, width = rgb.shape[:2]
    maximum = rgb.max(axis=2)
    minimum = rgb.min(axis=2)
    saturation = maximum - minimum
    mask = (saturation >= 34) & (maximum <= 250) & (maximum >= 45)

    crop = np.zeros_like(mask)
    crop[
        max(0, int(height * 0.08)) : min(height, int(height * 0.86)),
        max(0, int(width * 0.05)) : min(width, int(width * 0.92)),
    ] = True
    mask &= crop
    y_values, x_values = np.nonzero(mask)
    if len(x_values) < max(40, int(width * height * 0.00015)):
        return None

    # Quantiles keep isolated coloured legend markers from stretching the plot.
    x0, x1 = np.quantile(x_values, [0.01, 0.99])
    y0, y1 = np.quantile(y_values, [0.01, 0.99])
    if x1 - x0 < width * 0.15 or y1 - y0 < height * 0.12:
        return None
    return int(x0), int(y0), int(x1), int(y1)


def _fallback_plot_bbox(image: Image.Image) -> tuple[int, int, int, int]:
    width, height = image.size
    return (
        int(width * 0.14),
        int(height * 0.14),
        int(width * 0.88),
        int(height * 0.80),
    )


def _unique(records: list[dict], field: str) -> list[str]:
    values: list[str] = []
    for record in records:
        value = str(record.get(field) or "").strip()
        if value and value not in values:
            values.append(value)
    return values


def _axis_field(records: list[dict]) -> str:
    return "period" if any(record.get("period") not in (None, "") for record in records) else "category"


def _line_points(
    records: list[dict],
    bbox: tuple[int, int, int, int],
) -> dict[int, tuple[float, float, float]]:
    x0, y0, x1, y1 = bbox
    field = _axis_field(records)
    axis_values = _unique(records, field)
    values = [_official_value(record) for record in records]
    numeric = [value for value in values if value is not None]
    if not axis_values or not numeric:
        return {}
    minimum, maximum = min(numeric), max(numeric)
    value_span = maximum - minimum or 1.0
    points: dict[int, tuple[float, float, float]] = {}
    for index, record in enumerate(records):
        value = _official_value(record)
        axis_value = str(record.get(field) or "").strip()
        if value is None or axis_value not in axis_values:
            continue
        axis_index = axis_values.index(axis_value)
        x = x0 + (axis_index / max(1, len(axis_values) - 1)) * (x1 - x0)
        y = y1 - ((value - minimum) / value_span) * (y1 - y0)
        points[index] = (x, y, max(11.0, min(x1 - x0, y1 - y0) * 0.035))
    return points


def _bar_points(
    records: list[dict],
    bbox: tuple[int, int, int, int],
) -> dict[int, tuple[float, float, float]]:
    x0, y0, x1, y1 = bbox
    categories = _unique(records, "category")
    if not categories:
        categories = _unique(records, "period")
        category_field = "period"
    else:
        category_field = "category"
    series = _unique(records, "series") or [""]
    values = [_official_value(record) for record in records]
    numeric = [value for value in values if value is not None]
    if not categories or not numeric:
        return {}
    maximum = max(numeric) or 1.0
    group_width = (x1 - x0) / max(1, len(categories))
    bar_step = group_width * 0.72 / max(1, len(series))
    points: dict[int, tuple[float, float, float]] = {}
    for index, record in enumerate(records):
        value = _official_value(record)
        category = str(record.get(category_field) or "").strip()
        series_value = str(record.get("series") or "").strip()
        if value is None or category not in categories:
            continue
        category_index = categories.index(category)
        series_index = series.index(series_value) if series_value in series else 0
        group_center = x0 + (category_index + 0.5) * group_width
        offset = (series_index - (len(series) - 1) / 2) * bar_step
        x = group_center + offset
        y = y1 - (value / maximum) * (y1 - y0)
        points[index] = (x, y, max(12.0, min(bar_step * 0.7, (y1 - y0) * 0.06)))
    return points


def _pie_points(
    records: list[dict],
    bbox: tuple[int, int, int, int],
) -> dict[int, tuple[float, float, float]]:
    x0, y0, x1, y1 = bbox
    center_x, center_y = (x0 + x1) / 2, (y0 + y1) / 2
    radius = min(x1 - x0, y1 - y0) / 2
    values = [max(0.0, _official_value(record) or 0.0) for record in records]
    total = sum(values)
    if total <= 0 or radius <= 0:
        return {}
    points: dict[int, tuple[float, float, float]] = {}
    cumulative = 0.0
    for index, value in enumerate(values):
        midpoint = cumulative + value / 2
        angle = math.radians(-90 + (midpoint / total) * 360)
        x = center_x + math.cos(angle) * radius * 0.58
        y = center_y + math.sin(angle) * radius * 0.58
        points[index] = (x, y, max(18.0, radius * 0.20))
        cumulative += value
    return points


def _record_points(
    chart_type: str,
    records: list[dict],
    image: Image.Image,
) -> dict[int, tuple[float, float, float]]:
    bbox = _colour_data_bbox(image) or _fallback_plot_bbox(image)
    if chart_type in {"line", "area"}:
        return _line_points(records, bbox)
    if chart_type == "bar":
        return _bar_points(records, bbox)
    if chart_type == "pie":
        return _pie_points(records, bbox)
    return {}


def _draw_legend(draw: ImageDraw.ImageDraw, width: int, header_height: int, has_current: bool) -> None:
    font = _load_font(max(13, min(24, width // 70)), bold=True)
    y = header_height // 2
    x = max(18, width // 40)
    items = []
    if has_current:
        items.append((CURRENT_COLOR, "Current draft focus"))
    items.append((RECOMMENDED_COLOR, "Suggested focus"))
    for colour, label in items:
        radius = max(6, header_height // 8)
        draw.ellipse((x, y - radius, x + radius * 2, y + radius), outline=colour, width=max(3, radius // 2))
        x += radius * 2 + 9
        draw.text((x, y), label, fill=HEADER_TEXT, font=font, anchor="lm")
        text_box = draw.textbbox((x, y), label, font=font, anchor="lm")
        x = text_box[2] + max(24, width // 35)


def _draw_targets(
    overlay: Image.Image,
    points: dict[int, tuple[float, float, float]],
    indices: list[int],
    colour: str,
    y_offset: int,
) -> None:
    draw = ImageDraw.Draw(overlay, "RGBA")
    line_width = max(4, overlay.width // 350)
    for index in indices[:4]:
        point = points.get(index)
        if point is None:
            continue
        x, y, radius = point
        y += y_offset
        box = (x - radius, y - radius, x + radius, y + radius)
        fill = (*ImageColor_getrgb(colour), 24)
        draw.ellipse(box, fill=fill, outline=colour, width=line_width)


def ImageColor_getrgb(colour: str) -> tuple[int, int, int]:
    """Small local helper avoids importing another Pillow module at call sites."""
    value = colour.lstrip("#")
    return tuple(int(value[index : index + 2], 16) for index in (0, 2, 4))


def _render_assessment(
    source: Image.Image,
    output_path: Path,
    chart_type: str,
    records: list[dict],
    assessment: dict,
) -> dict | None:
    targets = assessment.get("visual_targets")
    if not isinstance(targets, dict):
        return None
    current = [index for index in targets.get("current_focus_record_indices", []) if isinstance(index, int)]
    recommended = [index for index in targets.get("recommended_record_indices", []) if isinstance(index, int)]
    if not recommended:
        return None

    points = _record_points(chart_type, records, source)
    recommended = [index for index in recommended if index in points]
    current = [index for index in current if index in points and index not in recommended]
    if not recommended:
        return None

    width, height = source.size
    header_height = max(44, min(72, int(height * 0.09)))
    canvas = Image.new("RGBA", (width, height + header_height), HEADER_BACKGROUND)
    canvas.paste(source.convert("RGBA"), (0, header_height))
    _draw_legend(ImageDraw.Draw(canvas), width, header_height, bool(current))

    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    _draw_targets(overlay, points, current, CURRENT_COLOR, header_height)
    _draw_targets(overlay, points, recommended, RECOMMENDED_COLOR, header_height)
    canvas = Image.alpha_composite(canvas, overlay).convert("RGB")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path, format="PNG", optimize=True)

    return {
        "image_filename": output_path.name,
        "current_focus_labels": [_record_label(records[index]) for index in current],
        "recommended_focus_labels": [_record_label(records[index]) for index in recommended],
        "legend": {
            "current": "Current draft focus" if current else None,
            "recommended": "Suggested focus",
        },
    }


def render_move_visuals(
    image_path: str | Path | None,
    output_dir: str | Path,
    chart_data: dict,
) -> dict:
    """Attach per-move annotated-image metadata without making analysis fail."""
    feedback = chart_data.get("move_feedback")
    assessments = feedback.get("assessments") if isinstance(feedback, dict) else None
    if not image_path or not isinstance(assessments, list):
        return chart_data
    source_path = Path(image_path)
    if not source_path.is_file():
        return chart_data

    records = [record for record in chart_data.get("records", []) if isinstance(record, dict)]
    if not records:
        return chart_data
    try:
        with Image.open(source_path) as opened:
            source = ImageOps.exif_transpose(opened).convert("RGB")
    except (OSError, ValueError):
        return chart_data

    output_root = Path(output_dir)
    visual_count = 0
    for assessment in assessments:
        if not isinstance(assessment, dict) or not assessment.get("visual_available"):
            continue
        filename = (
            f'move_{assessment.get("number", "cue")}_'
            f'{uuid.uuid4().hex}.png'
        )
        visual = _render_assessment(
            source,
            output_root / filename,
            str(chart_data.get("chart_type") or ""),
            records,
            assessment,
        )
        if visual is None:
            assessment["visual_available"] = False
            continue
        assessment["visual"] = visual
        visual_count += 1
    feedback["visual_count"] = visual_count
    return chart_data

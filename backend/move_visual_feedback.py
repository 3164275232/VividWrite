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
CURRENT_LABEL = "Your current focus"
RECOMMENDED_LABEL = "Suggested focus"
HEADER_BACKGROUND = "#FFFFFF"


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


def _line_data_bbox(image: Image.Image) -> tuple[int, int, int, int] | None:
    """Find the continuous line-mark span without absorbing detached legend swatches."""
    rgb = np.asarray(image.convert("RGB"))
    height, width = rgb.shape[:2]
    maximum = rgb.max(axis=2)
    minimum = rgb.min(axis=2)
    saturation = maximum - minimum
    mask = (saturation >= 34) & (maximum <= 250) & (maximum >= 45)

    crop = np.zeros_like(mask)
    crop[
        max(0, int(height * 0.04)) : min(height, int(height * 0.96)),
        max(0, int(width * 0.03)) : min(width, int(width * 0.97)),
    ] = True
    mask &= crop

    # A plotted line occupies a long, continuous run of x coordinates. Legend
    # swatches form short detached runs, even when the legend sits beside the plot.
    active_columns = mask.sum(axis=0) >= max(2, int(height * 0.002))
    runs = sorted(
        _contiguous_runs(active_columns),
        key=lambda run: run[1] - run[0],
        reverse=True,
    )
    for start, end in runs:
        if end - start < width * 0.15:
            continue
        section = mask[:, start : end + 1]
        y_values, x_values = np.nonzero(section)
        if len(x_values) < max(40, int(width * height * 0.0001)):
            continue
        return (
            int(start + x_values.min()),
            int(y_values.min()),
            int(start + x_values.max()),
            int(y_values.max()),
        )
    return None


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


def _contiguous_runs(active: np.ndarray) -> list[tuple[int, int]]:
    indices = np.flatnonzero(active)
    if not len(indices):
        return []
    breaks = np.flatnonzero(np.diff(indices) > 1)
    starts = np.concatenate(([indices[0]], indices[breaks + 1]))
    ends = np.concatenate((indices[breaks], [indices[-1]]))
    return [(int(start), int(end)) for start, end in zip(starts, ends)]


def _box_iou(
    first: tuple[float, float, float, float],
    second: tuple[float, float, float, float],
) -> float:
    x0 = max(first[0], second[0])
    y0 = max(first[1], second[1])
    x1 = min(first[2], second[2])
    y1 = min(first[3], second[3])
    intersection = max(0.0, x1 - x0) * max(0.0, y1 - y0)
    if not intersection:
        return 0.0
    first_area = max(0.0, first[2] - first[0]) * max(0.0, first[3] - first[1])
    second_area = max(0.0, second[2] - second[0]) * max(0.0, second[3] - second[1])
    return intersection / max(1.0, first_area + second_area - intersection)


def _detect_bar_boxes(
    image: Image.Image,
    expected_count: int,
) -> list[tuple[float, float, float, float]]:
    """Find solid bar bounds so annotations follow the pixels, not inferred axes."""
    if expected_count <= 0:
        return []
    rgb = np.asarray(image.convert("RGB"))
    height, width = rgb.shape[:2]
    maximum = rgb.max(axis=2)
    minimum = rgb.min(axis=2)
    saturation = maximum - minimum
    valid = (saturation >= 34) & (maximum <= 250) & (maximum >= 45)
    crop = np.zeros(valid.shape, dtype=bool)
    crop[
        max(0, int(height * 0.07)) : min(height, int(height * 0.84)),
        max(0, int(width * 0.03)) : min(width, int(width * 0.97)),
    ] = True
    valid &= crop
    if not valid.any():
        return []

    quantized = rgb.astype(np.uint16) >> 4
    colour_ids = (
        (quantized[:, :, 0] << 8)
        | (quantized[:, :, 1] << 4)
        | quantized[:, :, 2]
    )
    counts = np.bincount(colour_ids[valid], minlength=4096)
    minimum_pixels = max(180, int(width * height * 0.0008))
    candidates: dict[str, list[tuple[tuple[float, float, float, float], int]]] = {
        "vertical": [],
        "horizontal": [],
    }

    for colour_id in np.argsort(counts)[::-1][:24]:
        if counts[colour_id] < minimum_pixels:
            break
        mask = valid & (colour_ids == colour_id)

        active_columns = mask.sum(axis=0) >= max(10, int(height * 0.035))
        for start, end in _contiguous_runs(active_columns):
            section = mask[:, start : end + 1]
            y_values, x_values = np.nonzero(section)
            if not len(y_values):
                continue
            box = (
                float(start + x_values.min()),
                float(y_values.min()),
                float(start + x_values.max() + 1),
                float(y_values.max() + 1),
            )
            box_width = box[2] - box[0]
            box_height = box[3] - box[1]
            density = len(y_values) / max(1.0, box_width * box_height)
            if (
                box_width >= width * 0.008
                and box_height >= height * 0.06
                and box_height >= box_width * 1.2
                and density >= 0.55
            ):
                candidates["vertical"].append((box, len(y_values)))

        active_rows = mask.sum(axis=1) >= max(10, int(width * 0.035))
        for start, end in _contiguous_runs(active_rows):
            section = mask[start : end + 1, :]
            y_values, x_values = np.nonzero(section)
            if not len(x_values):
                continue
            box = (
                float(x_values.min()),
                float(start + y_values.min()),
                float(x_values.max() + 1),
                float(start + y_values.max() + 1),
            )
            box_width = box[2] - box[0]
            box_height = box[3] - box[1]
            density = len(x_values) / max(1.0, box_width * box_height)
            if (
                box_width >= width * 0.06
                and box_height >= height * 0.008
                and box_width >= box_height * 1.2
                and density >= 0.55
            ):
                candidates["horizontal"].append((box, len(x_values)))

    choices: list[tuple[int, str, list[tuple[float, float, float, float]]]] = []
    for orientation, entries in candidates.items():
        selected: list[tuple[tuple[float, float, float, float], int]] = []
        for box, score in sorted(entries, key=lambda item: item[1], reverse=True):
            if any(_box_iou(box, existing[0]) >= 0.72 for existing in selected):
                continue
            selected.append((box, score))
        if len(selected) < expected_count:
            continue
        selected = sorted(selected, key=lambda item: item[1], reverse=True)[:expected_count]
        boxes = [box for box, _ in selected]
        if orientation == "vertical":
            boxes.sort(key=lambda box: ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2))
        else:
            boxes.sort(key=lambda box: ((box[1] + box[3]) / 2, (box[0] + box[2]) / 2))
        choices.append((sum(score for _, score in selected), orientation, boxes))

    if not choices:
        return []
    return max(choices, key=lambda item: item[0])[2]


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


def _record_boxes(
    chart_type: str,
    records: list[dict],
    image: Image.Image,
) -> dict[int, tuple[float, float, float, float]]:
    if chart_type in {"line", "area"}:
        bbox = _line_data_bbox(image) or _colour_data_bbox(image) or _fallback_plot_bbox(image)
    else:
        bbox = _colour_data_bbox(image) or _fallback_plot_bbox(image)
    if chart_type == "bar":
        detected = _detect_bar_boxes(image, len(records))
        if len(detected) == len(records):
            return dict(enumerate(detected))
        points = _bar_points(records, bbox)
        baseline = bbox[3]
        return {
            index: (x - radius, y, x + radius, baseline)
            for index, (x, y, radius) in points.items()
        }
    if chart_type in {"line", "area"}:
        points = _line_points(records, bbox)
    elif chart_type == "pie":
        points = _pie_points(records, bbox)
    else:
        return {}
    return {
        index: (x - radius, y - radius, x + radius, y + radius)
        for index, (x, y, radius) in points.items()
    }


def _target_boxes(
    chart_type: str,
    records: list[dict],
    boxes: dict[int, tuple[float, float, float, float]],
    indices: list[int],
    image_size: tuple[int, int],
) -> list[tuple[float, float, float, float]]:
    selected = [(index, boxes[index]) for index in indices if index in boxes]
    if chart_type != "bar":
        return [box for _, box in selected]

    grouped: dict[str, list[tuple[float, float, float, float]]] = {}
    for index, box in selected:
        record = records[index]
        group = str(record.get("category") or record.get("period") or index)
        grouped.setdefault(group, []).append(box)

    width, height = image_size
    padded: list[tuple[float, float, float, float]] = []
    for group_boxes in grouped.values():
        x0 = min(box[0] for box in group_boxes)
        y0 = min(box[1] for box in group_boxes)
        x1 = max(box[2] for box in group_boxes)
        y1 = max(box[3] for box in group_boxes)
        box_width = x1 - x0
        box_height = y1 - y0
        pad_x = max(14.0, min(34.0, box_width * 0.14))
        pad_y = max(14.0, min(28.0, box_height * 0.05))
        padded.append((
            max(1.0, x0 - pad_x),
            max(1.0, y0 - pad_y),
            min(width - 1.0, x1 + pad_x),
            min(height - 1.0, y1 + pad_y),
        ))
    return padded


def _draw_targets(
    overlay: Image.Image,
    boxes: list[tuple[float, float, float, float]],
    colour: str,
    y_offset: int,
) -> list[tuple[float, float, float, float]]:
    draw = ImageDraw.Draw(overlay, "RGBA")
    line_width = max(4, overlay.width // 350)
    rendered: list[tuple[float, float, float, float]] = []
    for source_box in boxes[:4]:
        box = (
            source_box[0],
            source_box[1] + y_offset,
            source_box[2],
            source_box[3] + y_offset,
        )
        fill = (*ImageColor_getrgb(colour), 24)
        draw.ellipse(box, fill=fill, outline=colour, width=line_width)
        rendered.append(box)
    return rendered


def _bezier_points(
    start: tuple[float, float],
    control_1: tuple[float, float],
    control_2: tuple[float, float],
    end: tuple[float, float],
    steps: int = 36,
) -> list[tuple[float, float]]:
    points: list[tuple[float, float]] = []
    for step in range(steps + 1):
        t = step / steps
        inverse = 1 - t
        x = (
            inverse ** 3 * start[0]
            + 3 * inverse ** 2 * t * control_1[0]
            + 3 * inverse * t ** 2 * control_2[0]
            + t ** 3 * end[0]
        )
        y = (
            inverse ** 3 * start[1]
            + 3 * inverse ** 2 * t * control_1[1]
            + 3 * inverse * t ** 2 * control_2[1]
            + t ** 3 * end[1]
        )
        points.append((x, y))
    return points


def _draw_callout(
    overlay: Image.Image,
    label: str,
    colour: str,
    target_boxes: list[tuple[float, float, float, float]],
    header_height: int,
    side: str,
) -> int:
    if not target_boxes:
        return 0
    draw = ImageDraw.Draw(overlay, "RGBA")
    font = _load_font(max(16, min(32, overlay.width // 50)), bold=True)
    stroke_width = max(1, overlay.width // 1000)
    text_box = draw.textbbox((0, 0), label, font=font, stroke_width=stroke_width)
    text_width = text_box[2] - text_box[0]
    text_height = text_box[3] - text_box[1]
    margin = max(20, overlay.width // 45)
    x = margin if side == "left" else overlay.width - margin - text_width
    y = max(8, (header_height - text_height) // 2 - 4)
    draw.text(
        (x, y),
        label,
        fill=colour,
        font=font,
        stroke_width=stroke_width,
        stroke_fill="white",
    )

    line_width = max(4, overlay.width // 330)
    arrow_size = max(11, min(22, overlay.width // 75))
    ordered_targets = sorted(target_boxes, key=lambda box: (box[0] + box[2]) / 2)
    target_count = len(ordered_targets)
    for index, target in enumerate(ordered_targets):
        progress = 0.08 if target_count == 1 else 0.08 + 0.76 * index / (target_count - 1)
        start_x = x + text_width * (progress if side == "left" else 1 - progress)
        start = (start_x, y + text_height + 7)
        target_center_x = (target[0] + target[2]) / 2
        approaches_from_left = start_x <= target_center_x
        end_x = target_center_x
        end = (end_x, target[1])
        horizontal_bend = max(45, overlay.width * 0.045)
        approach_x = end_x - horizontal_bend if approaches_from_left else end_x + horizontal_bend
        side_offset = 0 if side == "left" else max(36, overlay.height * 0.045)
        lane_y = (
            header_height
            + max(48, overlay.height * 0.065)
            + side_offset
            + index * 10
        )
        lane_start = (start_x, lane_y)
        turn = max(16, min(34, overlay.width * 0.018))
        turn = turn if approaches_from_left else -turn
        lead = _bezier_points(
            start,
            (start_x, start[1] + (lane_y - start[1]) * 0.35),
            (start_x - turn, lane_y),
            lane_start,
            steps=12,
        )
        sweep = _bezier_points(
            lane_start,
            (start_x + turn, lane_y),
            (approach_x, lane_y),
            end,
            steps=32,
        )
        curve = lead[:-1] + sweep
        draw.line(curve, fill=colour, width=line_width, joint="curve")

        previous = curve[-2]
        angle = math.atan2(end[1] - previous[1], end[0] - previous[0])
        arrow_left = (
            end[0] - arrow_size * math.cos(angle - math.pi / 6),
            end[1] - arrow_size * math.sin(angle - math.pi / 6),
        )
        arrow_right = (
            end[0] - arrow_size * math.cos(angle + math.pi / 6),
            end[1] - arrow_size * math.sin(angle + math.pi / 6),
        )
        draw.polygon((end, arrow_left, arrow_right), fill=colour)
    return target_count


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

    record_boxes = _record_boxes(chart_type, records, source)
    recommended = [index for index in recommended if index in record_boxes]
    current = [index for index in current if index in record_boxes and index not in recommended]
    if not recommended:
        return None

    width, height = source.size
    header_height = max(88, min(128, int(height * 0.13)))
    canvas = Image.new("RGBA", (width, height + header_height), HEADER_BACKGROUND)
    canvas.paste(source.convert("RGBA"), (0, header_height))

    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    current_boxes = _target_boxes(
        chart_type,
        records,
        record_boxes,
        current,
        source.size,
    )
    recommended_boxes = _target_boxes(
        chart_type,
        records,
        record_boxes,
        recommended,
        source.size,
    )
    rendered_current = _draw_targets(
        overlay,
        current_boxes,
        CURRENT_COLOR,
        header_height,
    )
    rendered_recommended = _draw_targets(
        overlay,
        recommended_boxes,
        RECOMMENDED_COLOR,
        header_height,
    )
    if rendered_current:
        _draw_callout(
            overlay,
            CURRENT_LABEL,
            CURRENT_COLOR,
            rendered_current,
            header_height,
            "left",
        )
    _draw_callout(
        overlay,
        RECOMMENDED_LABEL,
        RECOMMENDED_COLOR,
        rendered_recommended,
        header_height,
        "right" if rendered_current else "left",
    )
    canvas = Image.alpha_composite(canvas, overlay).convert("RGB")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path, format="PNG", optimize=True)

    return {
        "image_filename": output_path.name,
        "current_focus_labels": [_record_label(records[index]) for index in current],
        "recommended_focus_labels": [_record_label(records[index]) for index in recommended],
        "legend": {
            "current": CURRENT_LABEL if current else None,
            "recommended": RECOMMENDED_LABEL,
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

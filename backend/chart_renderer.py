"""Render validated Vega-Lite specifications to PNG.

The renderer is deliberately chart-type agnostic. DeepSeek produces the
declarative specification; this module only applies safety/size limits and
hands the result to Vega-Lite.
"""

from __future__ import annotations

import copy
import json
from collections import deque
from pathlib import Path
from typing import Any

import vl_convert as vlc
from PIL import Image


ALLOWED_MARKS = {"arc", "area", "bar", "line", "point", "rect", "rule", "text", "tick"}
FORBIDDEN_KEYS = {"url", "href", "calculate", "expr", "signal"}
TEXT_OUTLINE_KEYS = {
    "stroke",
    "strokeWidth",
    "strokeOpacity",
    "strokeDash",
    "strokeDashOffset",
    "strokeJoin",
    "strokeMiterLimit",
}


class InvalidChartSpec(ValueError):
    pass


def _legend_swatch_candidates(
    image: Image.Image, color: tuple[int, int, int], tolerance: float = 26
) -> list[tuple[float, float]]:
    width, height = image.size
    pixels = image.load()
    matching: set[tuple[int, int]] = set()
    for y in range(height):
        for x in range(width):
            pixel = pixels[x, y]
            distance = sum((pixel[index] - color[index]) ** 2 for index in range(3)) ** 0.5
            if distance <= tolerance:
                matching.add((x, y))

    candidates: list[tuple[float, float]] = []
    while matching:
        start = matching.pop()
        queue = deque([start])
        points = [start]
        while queue:
            x, y = queue.popleft()
            for neighbour in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                if neighbour in matching:
                    matching.remove(neighbour)
                    queue.append(neighbour)
                    points.append(neighbour)

        if not 3 <= len(points) <= 500:
            continue
        xs = [point[0] for point in points]
        ys = [point[1] for point in points]
        component_width = max(xs) - min(xs) + 1
        component_height = max(ys) - min(ys) + 1
        if (
            component_width < 3
            or component_height < 3
            or component_width > 48
            or component_height > 48
        ):
            continue
        center_x = sum(xs) / len(xs)
        center_y = sum(ys) / len(ys)
        in_legend_margin = (
            center_y >= height * 0.72
            or center_x >= width * 0.72
            or center_y <= height * 0.22
        )
        if in_legend_margin:
            candidates.append((center_x, center_y))
    return candidates


def _legend_ordered_palette(image: Image.Image, palette: list[str]) -> list[str]:
    if len(palette) < 2:
        return palette

    swatches: dict[int, list[tuple[float, float]]] = {}
    for index, color in enumerate(palette):
        rgb = tuple(int(color[offset : offset + 2], 16) for offset in (1, 3, 5))
        candidates = _legend_swatch_candidates(image, rgb)
        if candidates:
            swatches[index] = candidates
    if len(swatches) < 2:
        return palette

    best: tuple[int, float, list[int]] | None = None
    all_candidates = [
        (color_index, point)
        for color_index, points in swatches.items()
        for point in points
    ]
    for orientation in ("horizontal", "vertical"):
        cross_index = 1 if orientation == "horizontal" else 0
        order_index = 0 if orientation == "horizontal" else 1
        for _, anchor in all_candidates:
            matches: list[tuple[int, tuple[float, float]]] = []
            for color_index, points in swatches.items():
                nearest = min(points, key=lambda point: abs(point[cross_index] - anchor[cross_index]))
                if abs(nearest[cross_index] - anchor[cross_index]) <= 8:
                    matches.append((color_index, nearest))
            if len(matches) < 2:
                continue
            spread = max(point[cross_index] for _, point in matches) - min(
                point[cross_index] for _, point in matches
            )
            ordered_indices = [
                color_index
                for color_index, _ in sorted(matches, key=lambda item: item[1][order_index])
            ]
            score = (len(ordered_indices), -spread, ordered_indices)
            if best is None or score[:2] > best[:2]:
                best = score

    if best is None:
        return palette
    ordered = [palette[index] for index in best[2]]
    ordered.extend(color for index, color in enumerate(palette) if index not in best[2])
    return ordered


def extract_image_palette(image_path: str | Path | None, max_colors: int = 8) -> list[str]:
    """Extract saturated foreground colours without interpreting chart semantics."""
    if not image_path:
        return []
    path = Path(image_path)
    if not path.is_file():
        return []
    try:
        with Image.open(path) as source:
            image = source.convert("RGB")
            palette_image = image.copy()
            palette_image.thumbnail((320, 320))
            legend_image = image.copy()
            legend_image.thumbnail((640, 640))
            quantized = palette_image.quantize(
                colors=max_colors * 3, method=Image.Quantize.MEDIANCUT
            ).convert("RGB")
            colors = quantized.getcolors(maxcolors=320 * 320) or []
    except (OSError, ValueError):
        return []

    palette: list[str] = []
    for _, (red, green, blue) in sorted(colors, reverse=True):
        brightness = (red + green + blue) / 3
        saturation = max(red, green, blue) - min(red, green, blue)
        if brightness < 35 or brightness > 240 or saturation < 28:
            continue
        rgb = (red, green, blue)
        existing = [tuple(int(color[index : index + 2], 16) for index in (1, 3, 5)) for color in palette]
        if any(sum((left - right) ** 2 for left, right in zip(rgb, saved)) ** 0.5 < 32 for saved in existing):
            continue
        palette.append(f"#{red:02x}{green:02x}{blue:02x}")
        if len(palette) >= max_colors:
            break
    return _legend_ordered_palette(legend_image, palette)


def _mark_type(mark: Any) -> str | None:
    if isinstance(mark, str):
        return mark
    if isinstance(mark, dict):
        value = mark.get("type")
        return value if isinstance(value, str) else None
    return None


def _remove_text_outlines(value: Any) -> None:
    """Keep all Vega text marks free of halo/outline styling."""
    if isinstance(value, list):
        for item in value:
            _remove_text_outlines(item)
        return
    if not isinstance(value, dict):
        return

    if _mark_type(value.get("mark")) == "text":
        mark = value.get("mark")
        if isinstance(mark, dict):
            for key in TEXT_OUTLINE_KEYS:
                mark.pop(key, None)
        encoding = value.get("encoding")
        if isinstance(encoding, dict):
            for key in TEXT_OUTLINE_KEYS:
                encoding.pop(key, None)

    for child in value.values():
        _remove_text_outlines(child)


def _validate_tree(value: Any, *, depth: int = 0) -> None:
    if depth > 20:
        raise InvalidChartSpec("Chart specification is too deeply nested.")
    if isinstance(value, list):
        if len(value) > 100:
            raise InvalidChartSpec("Chart specification contains too many layers or settings.")
        for item in value:
            _validate_tree(item, depth=depth + 1)
        return
    if not isinstance(value, dict):
        return

    for key, child in value.items():
        if key in FORBIDDEN_KEYS:
            raise InvalidChartSpec(f"Unsupported Vega-Lite property: {key}")
        if key == "mark":
            mark = _mark_type(child)
            if mark not in ALLOWED_MARKS:
                raise InvalidChartSpec(f"Unsupported Vega-Lite mark: {mark}")
        _validate_tree(child, depth=depth + 1)


def _remove_nested_data(value: Any, *, root: bool = True) -> None:
    if isinstance(value, list):
        for item in value:
            _remove_nested_data(item, root=False)
        return
    if not isinstance(value, dict):
        return
    if not root:
        value.pop("data", None)
    for child in value.values():
        _remove_nested_data(child, root=False)


def _unique_field_values(records: list[dict], field: str) -> list[Any]:
    values: list[Any] = []
    for record in records:
        value = record.get(field)
        if value is None or value in values:
            continue
        values.append(value)
    return values


def _apply_encoding_order(
    value: Any, records: list[dict], palette: list[str] | None
) -> None:
    """Keep model-provided record order stable across Vega-Lite encodings."""
    if isinstance(value, list):
        for item in value:
            _apply_encoding_order(item, records, palette)
        return
    if not isinstance(value, dict):
        return

    encoding = value.get("encoding")
    if isinstance(encoding, dict):
        for channel, definition in encoding.items():
            if not isinstance(definition, dict):
                continue
            field = definition.get("field")
            field_type = definition.get("type")
            if not isinstance(field, str):
                continue
            domain = _unique_field_values(records, field)
            if not domain:
                continue
            if channel == "color":
                scale = definition.get("scale") if isinstance(definition.get("scale"), dict) else {}
                scale["domain"] = domain
                if palette:
                    scale["range"] = palette
                definition["scale"] = scale
                definition["sort"] = domain
            elif channel in {"x", "y", "column", "row"} and field_type in {"nominal", "ordinal"}:
                definition["sort"] = domain
                if channel == "x" and len(domain) <= 12 and max(len(str(item)) for item in domain) <= 12:
                    axis = definition.get("axis") if isinstance(definition.get("axis"), dict) else {}
                    axis["labelAngle"] = 0
                    definition["axis"] = axis

    for child in value.values():
        _apply_encoding_order(child, records, palette)


def _pie_label_field(records: list[dict]) -> str:
    for field in ("category", "series", "region", "period"):
        if len(_unique_field_values(records, field)) > 1:
            return field
    return "category"


def _number_label(value: Any) -> str:
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return f"{value:g}" if isinstance(value, (int, float)) else ""


def _prepare_pie_chart(
    records: list[dict], unit: str
) -> tuple[dict, list[dict]]:
    label_field = _pie_label_field(records)
    values = [record.get("value") for record in records]
    total = sum(value for value in values if isinstance(value, (int, float)))
    values_are_percentages = "%" in unit or "percent" in unit.lower()
    labelled_records = copy.deepcopy(records)
    for index, record in enumerate(labelled_records):
        category = record.get(label_field) or "Item"
        value = record.get("value")
        number = _number_label(value)
        record["_order"] = index
        if values_are_percentages:
            displayed_value = f"{number}%"
        elif isinstance(value, (int, float)) and total > 0:
            share = value / total * 100
            share_label = f"{share:.1f}".rstrip("0").rstrip(".")
            displayed_value = f"{number} ({share_label}%)"
        else:
            displayed_value = number
        record["_display_label"] = f"{category} {displayed_value}".strip()

    theta = {"field": "value", "type": "quantitative", "stack": True}
    order = {"field": "_order", "type": "quantitative", "sort": "ascending"}
    pie_spec = {
        "layer": [
            {
                "mark": {"type": "arc", "outerRadius": 175, "stroke": "white", "strokeWidth": 2},
                "encoding": {
                    "theta": theta,
                    "color": {
                        "field": label_field,
                        "type": "nominal",
                        "legend": {"title": label_field.replace("_", " ").title()},
                    },
                    "order": order,
                },
            },
            {
                "mark": {
                    "type": "text",
                    "radius": 125,
                    "fontSize": 12,
                    "fontWeight": "bold",
                    "fill": "white",
                },
                "encoding": {
                    "theta": theta,
                    "order": order,
                    "text": {"field": "_display_label", "type": "nominal"},
                },
            },
        ]
    }
    return pie_spec, labelled_records


def prepare_vega_lite_spec(
    spec: dict,
    records: list[dict],
    title: str,
    palette: list[str] | None = None,
    *,
    chart_type: str | None = None,
    unit: str = "",
) -> dict:
    if not records:
        raise InvalidChartSpec("No chart records were produced from the student answer.")
    if chart_type == "pie":
        prepared, render_records = _prepare_pie_chart(records, unit)
    else:
        if not isinstance(spec, dict):
            raise InvalidChartSpec("DeepSeek did not return a Vega-Lite object.")
        if "mark" not in spec and "layer" not in spec:
            raise InvalidChartSpec("Vega-Lite specification needs a mark or layer.")
        prepared = copy.deepcopy(spec)
        _validate_tree(prepared)
        _remove_nested_data(prepared)
        render_records = records
    _validate_tree(prepared)
    _remove_text_outlines(prepared)
    _apply_encoding_order(prepared, render_records, palette)
    prepared["$schema"] = "https://vega.github.io/schema/vega-lite/v6.json"
    prepared["data"] = {"values": render_records}
    prepared["title"] = title or "Student answer visualisation"
    prepared["width"] = 760
    prepared["height"] = 420
    prepared["autosize"] = {"type": "fit", "contains": "padding"}
    if not isinstance(prepared.get("config"), dict):
        prepared["config"] = {}
    prepared["config"].update(
        {
            "background": "white",
            "font": "Arial",
            "axis": {"labelFontSize": 12, "titleFontSize": 13, "gridColor": "#e5e7eb"},
            "legend": {
                "labelFontSize": 12,
                "titleFontSize": 12,
                "labelLimit": 320,
                "titleLimit": 320,
            },
            "title": {"fontSize": 16, "anchor": "middle", "offset": 16},
            "text": {"stroke": None, "strokeWidth": 0, "strokeOpacity": 0},
            "view": {"stroke": None},
        }
    )
    if palette:
        prepared["config"]["range"] = {"category": palette}
    return prepared


def render_vega_lite_png(
    spec: dict,
    records: list[dict],
    title: str,
    output_path: str | Path,
    palette: list[str] | None = None,
    *,
    chart_type: str | None = None,
    unit: str = "",
) -> dict:
    prepared = prepare_vega_lite_spec(
        spec,
        records,
        title,
        palette,
        chart_type=chart_type,
        unit=unit,
    )
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    png = vlc.vegalite_to_png(json.dumps(prepared), scale=2)
    path.write_bytes(png)
    return prepared

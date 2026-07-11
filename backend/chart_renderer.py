"""Render validated Vega-Lite specifications to PNG.

The renderer is deliberately chart-type agnostic. DeepSeek produces the
declarative specification; this module only applies safety/size limits and
hands the result to Vega-Lite.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import vl_convert as vlc
from PIL import Image


ALLOWED_MARKS = {"arc", "area", "bar", "line", "point", "rect", "rule", "text", "tick"}
FORBIDDEN_KEYS = {"url", "href", "calculate", "expr", "signal"}


class InvalidChartSpec(ValueError):
    pass


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
            image.thumbnail((320, 320))
            quantized = image.quantize(colors=max_colors * 3, method=Image.Quantize.MEDIANCUT).convert("RGB")
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
    return palette


def _mark_type(mark: Any) -> str | None:
    if isinstance(mark, str):
        return mark
    if isinstance(mark, dict):
        value = mark.get("type")
        return value if isinstance(value, str) else None
    return None


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


def prepare_vega_lite_spec(
    spec: dict, records: list[dict], title: str, palette: list[str] | None = None
) -> dict:
    if not isinstance(spec, dict):
        raise InvalidChartSpec("DeepSeek did not return a Vega-Lite object.")
    if not records:
        raise InvalidChartSpec("No chart records were produced from the student answer.")
    if "mark" not in spec and "layer" not in spec:
        raise InvalidChartSpec("Vega-Lite specification needs a mark or layer.")

    prepared = copy.deepcopy(spec)
    _validate_tree(prepared)
    _remove_nested_data(prepared)
    prepared["$schema"] = "https://vega.github.io/schema/vega-lite/v6.json"
    prepared["data"] = {"values": records}
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
            "legend": {"labelFontSize": 12, "titleFontSize": 12},
            "title": {"fontSize": 16, "anchor": "middle", "offset": 16},
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
) -> dict:
    prepared = prepare_vega_lite_spec(spec, records, title, palette)
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    png = vlc.vegalite_to_png(json.dumps(prepared), scale=2)
    path.write_bytes(png)
    return prepared

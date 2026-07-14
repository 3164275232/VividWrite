"""Small, deterministic visual heuristics used by Auto Detect."""

from collections import deque
from pathlib import Path

from PIL import Image


def _foreground_mask(image: Image.Image) -> list[list[bool]]:
    rgb = image.convert("RGB")
    width, height = rgb.size
    pixels = rgb.load()
    mask = [[False] * width for _ in range(height)]
    for y in range(height):
        for x in range(width):
            red, green, blue = pixels[x, y]
            saturation = max(red, green, blue) - min(red, green, blue)
            brightness = (red + green + blue) / 3
            mask[y][x] = saturation >= 32 and 35 <= brightness <= 238
    return mask


def _dilate(mask: list[list[bool]], passes: int = 2) -> list[list[bool]]:
    height = len(mask)
    width = len(mask[0]) if height else 0
    current = mask
    for _ in range(passes):
        expanded = [row[:] for row in current]
        for y in range(height):
            for x in range(width):
                if not current[y][x]:
                    continue
                for offset_y in (-1, 0, 1):
                    for offset_x in (-1, 0, 1):
                        next_x, next_y = x + offset_x, y + offset_y
                        if 0 <= next_x < width and 0 <= next_y < height:
                            expanded[next_y][next_x] = True
        current = expanded
    return current


def _large_round_component_bounds(
    mask: list[list[bool]],
) -> tuple[int, int, int, int] | None:
    height = len(mask)
    width = len(mask[0]) if height else 0
    visited: set[tuple[int, int]] = set()
    minimum_diameter = max(34, int(min(width, height) * 0.2))
    best: tuple[int, int, int, int, int] | None = None

    for start_y in range(height):
        for start_x in range(width):
            if not mask[start_y][start_x] or (start_x, start_y) in visited:
                continue
            queue = deque([(start_x, start_y)])
            visited.add((start_x, start_y))
            count = 0
            min_x = max_x = start_x
            min_y = max_y = start_y
            while queue:
                x, y = queue.popleft()
                count += 1
                min_x, max_x = min(min_x, x), max(max_x, x)
                min_y, max_y = min(min_y, y), max(max_y, y)
                for next_x, next_y in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                    if (
                        0 <= next_x < width
                        and 0 <= next_y < height
                        and mask[next_y][next_x]
                        and (next_x, next_y) not in visited
                    ):
                        visited.add((next_x, next_y))
                        queue.append((next_x, next_y))

            component_width = max_x - min_x + 1
            component_height = max_y - min_y + 1
            if min(component_width, component_height) < minimum_diameter:
                continue
            aspect_ratio = component_width / component_height
            fill_ratio = count / (component_width * component_height)
            # A filled circle occupies about 79% of its square bounding box.
            # The upper bound rejects map regions and square legend swatches.
            if 0.78 <= aspect_ratio <= 1.28 and 0.52 <= fill_ratio <= 0.9:
                candidate = (min_x, min_y, max_x + 1, max_y + 1, count)
                if best is None or candidate[4] > best[4]:
                    best = candidate
    return best[:4] if best else None


def _large_round_component(mask: list[list[bool]]) -> bool:
    return _large_round_component_bounds(mask) is not None


def crop_pie_plot(image: Image.Image) -> Image.Image | None:
    """Crop a pie plot away from legends that can confuse chart-to-table OCR."""
    original = image.convert("RGB")
    preview = original.copy()
    preview.thumbnail((480, 480))
    bounds = _large_round_component_bounds(_dilate(_foreground_mask(preview)))
    if bounds is None:
        return None

    left, top, right, bottom = bounds
    scale_x = original.width / preview.width
    scale_y = original.height / preview.height
    left = int(left * scale_x)
    top = int(top * scale_y)
    right = int(right * scale_x)
    bottom = int(bottom * scale_y)

    diameter = max(right - left, bottom - top)
    horizontal_margin = max(16, int(diameter * 0.16))
    vertical_margin = max(8, int(diameter * 0.05))
    crop_box = (
        max(0, left - horizontal_margin),
        max(0, top - vertical_margin),
        min(original.width, right + horizontal_margin),
        min(original.height, bottom + vertical_margin),
    )
    return original.crop(crop_box)


def detect_chart_type(image_path: str | Path | None) -> str | None:
    """Detect visually distinctive chart families without a paid model call.

    Only high-confidence pie detection is enabled. Other chart families remain
    delegated to the alignment model so a weak heuristic cannot override them.
    """
    if not image_path:
        return None
    path = Path(image_path)
    if not path.is_file():
        return None
    try:
        with Image.open(path) as source:
            image = source.convert("RGB")
            image.thumbnail((320, 320))
    except OSError:
        return None

    mask = _dilate(_foreground_mask(image))
    return "pie" if _large_round_component(mask) else None

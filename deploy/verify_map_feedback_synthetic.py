"""Verify the live map pipeline using synthetic, non-user data."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from map_feedback_renderer import MapFeedbackService


def font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    path = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
    if path.is_file():
        return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def draw_source(path: Path) -> None:
    image = Image.new("RGB", (1600, 800), "white")
    draw = ImageDraw.Draw(image)
    title_font = font(36)
    label_font = font(28)
    road_font = font(24)
    for offset, title in ((40, "Present day"), (820, "Future plan")):
        draw.text((offset, 30), title, font=title_font, fill="#111827")
        draw.rectangle((offset, 90, offset + 730, 740), outline="#374151", width=4)
        draw.line((offset + 20, 450, offset + 700, 300), fill="#475569", width=22)
        draw.text((offset + 300, 350), "City Road", font=road_font, fill="#111827")
        draw.ellipse(
            (offset + 80, 150, offset + 340, 280),
            outline="#374151",
            width=4,
        )
        draw.text((offset + 145, 195), "school", font=label_font, fill="#111827")
        draw.rectangle(
            (offset + 500, 140, offset + 690, 260),
            outline="#374151",
            width=4,
        )
        draw.text((offset + 515, 180), "supermarket", font=font(21), fill="#111827")
        draw.text((offset + 660, 680), "N", font=label_font, fill="#111827")
        draw.line((offset + 675, 650, offset + 675, 590), fill="#111827", width=4)
    image.save(path)


student_answer = (
    "The maps show the present layout and a future plan for City Road. "
    "In both periods, a restaurant is situated in the north-west, while a supermarket "
    "stands in the north-east. City Road crosses the centre of the area. Overall, the "
    "restaurant and supermarket remain unchanged in their original positions."
)

with tempfile.TemporaryDirectory() as folder:
    root = Path(folder)
    source_path = root / "synthetic-map.png"
    draw_source(source_path)
    result, filename = MapFeedbackService(root).generate(
        task_type="map",
        requirement="Summarise the synthetic present and future maps.",
        student_answer=student_answer,
        image_path=source_path,
    )
    student_values = [
        str(record.get("value") or "")
        for record in result["records"]
    ]
    official_values = [
        str(record.get("official_value") or "")
        for record in result["records"]
    ]
    print(
        json.dumps(
            {
                "output_exists": (root / filename).is_file(),
                "renderer": result["style"]["renderer"],
                "school_in_official_labels": any(
                    "school" in value.casefold() for value in official_values
                ),
                "school_in_student_labels": any(
                    "school" in value.casefold() for value in student_values
                ),
                "restaurant_in_student_labels": any(
                    "restaurant" in value.casefold() for value in student_values
                ),
                "forbidden_source_labels": result["comparison"]["forbidden_source_labels"],
                "label_repairs": result["comparison"]["label_repairs"],
            }
        )
    )

"""Generate deterministic IELTS map and process fixtures."""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


OUTPUT_DIR = Path(__file__).resolve().parent / "charts"


def font(size: int, *, bold: bool = False):
    names = ("arialbd.ttf", "DejaVuSans-Bold.ttf") if bold else ("arial.ttf", "DejaVuSans.ttf")
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default()


def arrow(draw: ImageDraw.ImageDraw, start: tuple[int, int], end: tuple[int, int], color: str = "#475569") -> None:
    draw.line((start, end), fill=color, width=7)
    x, y = end
    if abs(end[0] - start[0]) >= abs(end[1] - start[1]):
        direction = 1 if end[0] > start[0] else -1
        draw.polygon([(x, y), (x - 18 * direction, y - 12), (x - 18 * direction, y + 12)], fill=color)
    else:
        direction = 1 if end[1] > start[1] else -1
        draw.polygon([(x, y), (x - 12, y - 18 * direction), (x + 12, y - 18 * direction)], fill=color)


def generate_map() -> Path:
    output = OUTPUT_DIR / "06_map_riverside_town.png"
    image = Image.new("RGB", (1200, 800), "#f7f6ef")
    draw = ImageDraw.Draw(image)
    draw.text((600, 35), "Riverside town before redevelopment", fill="#1f2937", font=font(34), anchor="mm")
    draw.rounded_rectangle((525, 110, 675, 735), radius=55, fill="#8ecae6", outline="#397aa3", width=4)
    draw.text((600, 420), "River", fill="#174a6e", font=font(24), anchor="mm")
    draw.rectangle((500, 385, 700, 445), fill="#8b6f47", outline="#4e3f2c", width=4)
    draw.text((600, 415), "Old bridge", fill="white", font=font(18), anchor="mm")
    draw.line((90, 415, 500, 415), fill="#777777", width=34)
    draw.line((700, 415, 1110, 415), fill="#777777", width=34)
    draw.line((320, 140, 320, 690), fill="#777777", width=28)
    draw.text((200, 388), "Main road", fill="#333333", font=font(20), anchor="mm")
    draw.rounded_rectangle((120, 155, 275, 285), radius=8, fill="#f4a261", outline="#9a4f1e", width=4)
    draw.text((198, 220), "School", fill="#4a2a14", font=font(23), anchor="mm")
    draw.rounded_rectangle((355, 520, 495, 660), radius=8, fill="#e9c46a", outline="#967b23", width=4)
    draw.text((425, 590), "Market", fill="#4c3a08", font=font(23), anchor="mm")
    draw.rounded_rectangle((755, 150, 1045, 305), radius=10, fill="#90be6d", outline="#3f6b2a", width=4)
    draw.text((900, 225), "Forest", fill="#254719", font=font(25), anchor="mm")
    draw.rounded_rectangle((770, 520, 1040, 665), radius=10, fill="#cdb4db", outline="#69477a", width=4)
    draw.text((905, 590), "Housing", fill="#442b50", font=font(25), anchor="mm")
    draw.line((1110, 120, 1110, 210), fill="#111827", width=5)
    draw.polygon([(1110, 95), (1097, 125), (1123, 125)], fill="#111827")
    draw.text((1110, 70), "N", fill="#111827", font=font(26), anchor="mm")
    draw.rectangle((70, 90, 1130, 730), outline="#4b5563", width=5)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    image.save(output, format="PNG")
    return output


def generate_process() -> Path:
    output = OUTPUT_DIR / "07_process_glass_recycling.png"
    image = Image.new("RGB", (1400, 900), "#f8fafc")
    draw = ImageDraw.Draw(image)
    draw.text((700, 58), "How used glass bottles are recycled", fill="#172033", font=font(40, bold=True), anchor="mm")
    draw.text((700, 105), "A cyclical eight-stage process", fill="#526174", font=font(23), anchor="mm")

    stages = [
        (1, "Used bottles\nplaced in bins", (60, 190, 300, 340), "#dbeafe"),
        (2, "Collected by\nrecycling truck", (390, 190, 630, 340), "#dcfce7"),
        (3, "Sorted by\ncolour", (720, 190, 960, 340), "#fef3c7"),
        (4, "Washed with\nwater", (1050, 190, 1290, 340), "#cffafe"),
        (5, "Crushed into\nglass pieces", (1050, 550, 1290, 700), "#fee2e2"),
        (6, "Melted in a\nhigh-temperature\nfurnace", (720, 550, 960, 700), "#ffedd5"),
        (7, "Moulded into\nnew bottles", (390, 550, 630, 700), "#ede9fe"),
        (8, "Delivered to\nshops", (60, 550, 300, 700), "#e0f2fe"),
    ]
    for number, label, bounds, fill in stages:
        draw.rounded_rectangle(bounds, radius=10, fill=fill, outline="#334155", width=4)
        draw.ellipse((bounds[0] + 14, bounds[1] + 14, bounds[0] + 58, bounds[1] + 58), fill="#334155")
        draw.text((bounds[0] + 36, bounds[1] + 36), str(number), fill="white", font=font(21, bold=True), anchor="mm")
        draw.multiline_text(
            ((bounds[0] + bounds[2]) // 2, (bounds[1] + bounds[3]) // 2 + 12),
            label,
            fill="#1e293b",
            font=font(22, bold=True),
            anchor="mm",
            align="center",
            spacing=8,
        )

    arrow(draw, (305, 265), (380, 265))
    arrow(draw, (635, 265), (710, 265))
    arrow(draw, (965, 265), (1040, 265))
    arrow(draw, (1170, 350), (1170, 540))
    arrow(draw, (1040, 625), (970, 625))
    arrow(draw, (710, 625), (640, 625))
    arrow(draw, (380, 625), (310, 625))
    draw.line((180, 710, 180, 790, 1325, 790, 1325, 265, 1300, 265), fill="#475569", width=7)
    draw.polygon([(1300, 265), (1318, 253), (1318, 277)], fill="#475569")
    draw.text((700, 825), "After use, bottles can enter the cycle again", fill="#475569", font=font(22), anchor="mm")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    image.save(output, format="PNG")
    return output


if __name__ == "__main__":
    for path in (generate_map(), generate_process()):
        print(path)

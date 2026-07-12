"""Generate a simple IELTS-style town map for Wan2.7 integration testing."""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


OUTPUT = Path(__file__).resolve().parent / "charts" / "06_map_riverside_town.png"


def font(size: int):
    for name in ("arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default()


image = Image.new("RGB", (1200, 800), "#f7f6ef")
draw = ImageDraw.Draw(image)

draw.text((600, 35), "Riverside town before redevelopment", fill="#1f2937", font=font(34), anchor="mm")

# River and bridge
draw.rounded_rectangle((525, 110, 675, 735), radius=55, fill="#8ecae6", outline="#397aa3", width=4)
draw.text((600, 420), "River", fill="#174a6e", font=font(24), anchor="mm")
draw.rectangle((500, 385, 700, 445), fill="#8b6f47", outline="#4e3f2c", width=4)
draw.text((600, 415), "Old bridge", fill="white", font=font(18), anchor="mm")

# Main roads
draw.line((90, 415, 500, 415), fill="#777777", width=34)
draw.line((700, 415, 1110, 415), fill="#777777", width=34)
draw.line((320, 140, 320, 690), fill="#777777", width=28)
draw.text((200, 388), "Main road", fill="#333333", font=font(20), anchor="mm")

# Buildings and land uses
draw.rounded_rectangle((120, 155, 275, 285), radius=8, fill="#f4a261", outline="#9a4f1e", width=4)
draw.text((198, 220), "School", fill="#4a2a14", font=font(23), anchor="mm")

draw.rounded_rectangle((355, 520, 495, 660), radius=8, fill="#e9c46a", outline="#967b23", width=4)
draw.text((425, 590), "Market", fill="#4c3a08", font=font(23), anchor="mm")

draw.rounded_rectangle((755, 150, 1045, 305), radius=10, fill="#90be6d", outline="#3f6b2a", width=4)
draw.text((900, 225), "Forest", fill="#254719", font=font(25), anchor="mm")

draw.rounded_rectangle((770, 520, 1040, 665), radius=10, fill="#cdb4db", outline="#69477a", width=4)
draw.text((905, 590), "Housing", fill="#442b50", font=font(25), anchor="mm")

# Compass
draw.line((1110, 120, 1110, 210), fill="#111827", width=5)
draw.polygon([(1110, 95), (1097, 125), (1123, 125)], fill="#111827")
draw.text((1110, 70), "N", fill="#111827", font=font(26), anchor="mm")

draw.rectangle((70, 90, 1130, 730), outline="#4b5563", width=5)
OUTPUT.parent.mkdir(parents=True, exist_ok=True)
image.save(OUTPUT, format="PNG")
print(OUTPUT)

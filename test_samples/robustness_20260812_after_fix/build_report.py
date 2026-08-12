from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent
BASELINE_SUMMARY = ROOT.parent / "robustness_20260812" / "summary.json"
DIAGNOSTIC_SUMMARY = ROOT.parent / "robustness_20260812_after_fix" / "summary.json"


def display_error(value: str) -> str:
    return value.replace("_", " ").title()


def image_note(item: dict) -> str:
    if not item.get("success"):
        return item.get("error", "The workflow failed.")
    if not item["png_validation"].get("valid"):
        return "The PNG is missing, blank, or has invalid dimensions."
    if not item["image_data_validation"]["correct"]:
        mismatches = item["image_data_validation"].get("mismatches") or []
        return "; ".join(
            f"{'/'.join(value['key'])}: expected {value['expected']}, rendered {value['actual']}"
            for value in mismatches
        ) or "The rendered records do not match the essay."
    semantic = item["semantic_visual_validation"]
    if not semantic["correct"]:
        return "The required semantic conflict warning is missing or an unexpected warning is present."
    if semantic["required"]:
        return "The chart data match the essay and a visible TEXT CONFLICT subtitle exposes the false verbal claim."
    return "The chart data and omission state match the essay, and the PNG is readable."


def build_contact_sheet(chart_type: str, items: list[dict]) -> Path:
    thumb_width, thumb_height = 480, 300
    label_height, margin = 46, 18
    columns = 3
    rows = (len(items) + columns - 1) // columns
    sheet = Image.new(
        "RGB",
        (margin + columns * (thumb_width + margin), margin + rows * (thumb_height + label_height + margin)),
        "white",
    )
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    for index, item in enumerate(items):
        row, column = divmod(index, columns)
        x = margin + column * (thumb_width + margin)
        y = margin + row * (thumb_height + label_height + margin)
        image_path = ROOT / item["image_file"]
        with Image.open(image_path) as source:
            rendered = source.convert("RGB")
            rendered.thumbnail((thumb_width, thumb_height))
            canvas = Image.new("RGB", (thumb_width, thumb_height), "#f3f4f6")
            canvas.paste(rendered, ((thumb_width - rendered.width) // 2, (thumb_height - rendered.height) // 2))
            sheet.paste(canvas, (x, y))
        status = "PASS" if item["taxonomy_pass"] and item["image_correct"] else "FAIL"
        draw.text((x, y + thumb_height + 6), f"{item['case_id']} [{status}]", fill="black", font=font)
        actual = ", ".join(item["actual_unique_errors"]) or "N/A"
        draw.text((x, y + thumb_height + 23), f"actual: {actual}", fill="#991b1b" if status == "FAIL" else "#166534", font=font)
    path = ROOT / f"{chart_type}_contact_sheet.jpg"
    sheet.save(path, quality=90)
    return path


def main() -> None:
    manifest = json.loads((ROOT / "cases.json").read_text(encoding="utf-8"))
    results = json.loads((ROOT / "results_raw.json").read_text(encoding="utf-8"))["results"]
    baseline = json.loads(BASELINE_SUMMARY.read_text(encoding="utf-8"))
    diagnostic = (
        json.loads(DIAGNOSTIC_SUMMARY.read_text(encoding="utf-8"))
        if DIAGNOSTIC_SUMMARY.exists() and DIAGNOSTIC_SUMMARY.resolve() != (ROOT / "summary.json").resolve()
        else None
    )
    manifest_hash = (ROOT / "manifest.sha256").read_text(encoding="ascii").split()[0]
    failures = [item for item in results if not (item["taxonomy_pass"] and item["image_correct"])]
    actual_counter = Counter(error for item in results for error in item.get("actual_unique_errors", []))
    contact_sheets = {}
    for chart_type in ("bar", "line", "pie"):
        contact_sheets[chart_type] = build_contact_sheet(
            chart_type, [item for item in results if item["chart_type"] == chart_type]
        )

    lines = [
        "# VividWrite Post-fix Held-out Robustness Report",
        "",
        "## Protocol",
        "",
        f"- Frozen manifest SHA-256: `{manifest_hash}`",
        f"- Fixed random seed: `{manifest['seed']}`",
        "- 45 new essays: 3 chart types x 5 taxonomy classes x 3 randomized replicates.",
        "- Randomized before inference: target entity/period, error magnitude, detail order, and wording.",
        "- The manifest also froze SHA-256 hashes for the three product modules under test.",
        "- Workflow: previously captured DePlot output from each real chart -> DeepSeek alignment -> local evidence correction -> taxonomy -> Vega-Lite PNG.",
        "- No essay or product module was changed after the first held-out output was observed.",
        "- Single-period pie trend cases expect N/A because the source chart has no temporal direction.",
        "",
        "## Before and after",
        "",
        "| Run | Taxonomy exact | Image correct | Fully passed |",
        "| --- | ---: | ---: | ---: |",
        f"| Before repair | {baseline['taxonomy_passes']}/45 | {baseline['image_passes']}/45 | {baseline['fully_passed']}/45 |",
    ]
    if diagnostic is not None:
        lines.append(
            f"| First held-out diagnostic run | {diagnostic['taxonomy_passes']}/45 | "
            f"{diagnostic['image_passes']}/45 | {diagnostic['fully_passed']}/45 |"
        )
    lines.extend([
        f"| Final new held-out run | {sum(item['taxonomy_pass'] for item in results)}/45 | {sum(item['image_correct'] for item in results)}/45 | {sum(item['taxonomy_pass'] and item['image_correct'] for item in results)}/45 |",
        "",
        "## Results by chart",
        "",
        "| Chart | Taxonomy exact | Image correct |",
        "| --- | ---: | ---: |",
    ])
    for chart_type in ("bar", "line", "pie"):
        items = [item for item in results if item["chart_type"] == chart_type]
        lines.append(
            f"| {chart_type.title()} | {sum(item['taxonomy_pass'] for item in items)}/15 | "
            f"{sum(item['image_correct'] for item in items)}/15 |"
        )
    lines.extend([
        "",
        f"- API/workflow errors: {sum(not item.get('success') for item in results)}",
        f"- Failed cases requiring review: {len(failures)}",
        f"- Actual detected-class counts: {dict(actual_counter)}",
        "",
        "Contact sheets: " + ", ".join(f"[{name}]({path.name})" for name, path in contact_sheets.items()),
        "",
        "## Per-case evidence",
        "",
    ])
    current = None
    for item in results:
        if item["chart_type"] != current:
            current = item["chart_type"]
            lines.extend([f"### {current.title()} chart", ""])
        expected = (
            "N/A: trend not applicable"
            if current == "pie" and item["expected_error"] == "trend_direction_error"
            else display_error(item["expected_error"])
        )
        actual = ", ".join(display_error(value) for value in item["actual_unique_errors"]) or "None"
        status = "PASS" if item["taxonomy_pass"] and item["image_correct"] else "FAIL"
        lines.extend([
            f"#### {item['case_id']} - {status}",
            "",
            f"- Expected taxonomy: **{expected}**",
            f"- Actual taxonomy: **{actual}**",
            f"- Taxonomy exact: **{item['taxonomy_pass']}**",
            f"- Image correct: **{item['image_correct']}** - {image_note(item)}",
            f"- Image: [{item.get('image_file', 'not generated')}]({item.get('image_file', '')})" if item.get("image_file") else "- Image: not generated",
            "",
            "Essay:",
            "",
            item["essay"],
            "",
        ])
    lines.extend(["## Remaining failures", ""])
    if not failures:
        lines.append("No failures occurred in this held-out batch.")
    else:
        for item in failures:
            lines.append(
                f"- `{item['case_id']}`: expected {item['expected_output']}; actual "
                f"{item.get('actual_unique_errors') or ['none']}; {image_note(item)}"
            )
    (ROOT / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")
    print(ROOT / "REPORT.md")


if __name__ == "__main__":
    main()

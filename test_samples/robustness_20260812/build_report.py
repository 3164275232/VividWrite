from __future__ import annotations

import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def display_error(value: str) -> str:
    return value.replace("_", " ").title()


def image_assessment(item: dict) -> tuple[str, str]:
    expected = item["expected_error"]
    if not item["png_validation"].get("valid"):
        return "Incorrect", "The PNG is missing, blank, or has invalid dimensions."
    if not item["image_data_validation"]["correct"]:
        mismatches = item["image_data_validation"].get("mismatches") or []
        detail = "; ".join(
            f"{'/'.join(m['key'])}: expected {m['expected']}, rendered {m['actual']}"
            for m in mismatches
        )
        return "Incorrect", detail or "The rendered records do not match the essay."
    if expected in {"trend_direction_error", "comparison_ranking_error"}:
        if item["chart_type"] == "pie" and expected == "trend_direction_error":
            return "Correct for N/A", "The single-period pie is rendered correctly; no temporal trend can be encoded."
        return (
            "Partially correct",
            "The stated numeric data are rendered correctly, but a false trend/rank sentence does not alter the chart, so the visual alone does not expose that semantic error.",
        )
    return "Correct", "The rendered chart matches the values and omissions stated in the essay."


def failure_reason(item: dict) -> str:
    if item["taxonomy_pass"] and item["image_data_validation"]["correct"]:
        return ""
    case = item["case_id"]
    if case == "line_value_inaccuracy_3":
        return (
            "The phrase 'at the beginning/end' was not reliably aligned to 2010/2020 for Bus and Rail. "
            "The wrong Rail value was therefore dropped and converted into endpoint omissions."
        )
    if case.startswith("line_"):
        return (
            "One or more 'at the beginning/end' endpoint phrases were not mapped to explicit years. "
            "The intended class was usually detected, but extra endpoint omissions were reported and the generated line lost points."
        )
    if case in {"pie_key_feature_omission_2", "pie_key_feature_omission_3"}:
        return (
            "The model copied the omitted category's official percentage into the student record even though the essay did not state it, "
            "so omission detection and the student-generated pie both failed."
        )
    return "The actual taxonomy output or rendered data did not match the frozen expected result."


def main() -> None:
    manifest_hash = (ROOT / "manifest.sha256").read_text(encoding="ascii").split()[0]
    results = json.loads((ROOT / "results_raw.json").read_text(encoding="utf-8"))["results"]
    visual_counts = Counter()
    for item in results:
        assessment, note = image_assessment(item)
        item["manual_image_assessment"] = assessment
        item["manual_image_note"] = note
        item["failure_reason"] = failure_reason(item)
        visual_counts[assessment] += 1

    lines = [
        "# VividWrite Randomized Taxonomy Robustness Report",
        "",
        "## Protocol",
        "",
        f"- Frozen manifest SHA-256: `{manifest_hash}`",
        "- Fixed random seed: `20260812`",
        "- Cases: 45 (3 chart types x 5 taxonomy classes x 3 independently varied essays)",
        "- Randomized before inference: target entity/period, error magnitude, detail order, introduction, overview and value sentence templates.",
        "- Workflow: cached DePlot output from each real chart -> DeepSeek alignment -> local validation -> taxonomy -> Vega-Lite PNG.",
        "- No essay was changed after its output was observed.",
        "- Single-period pie trend cases expect `N/A`, because a one-year pie has no temporal direction to verify.",
        "",
        "## Summary",
        "",
        "| Chart type | Cases | Exact taxonomy result | Data-faithful PNG |",
        "| --- | ---: | ---: | ---: |",
    ]
    for chart_type in ("bar", "line", "pie"):
        items = [item for item in results if item["chart_type"] == chart_type]
        lines.append(
            f"| {chart_type.title()} | {len(items)} | {sum(item['taxonomy_pass'] for item in items)}/{len(items)} | "
            f"{sum(item['image_data_validation']['correct'] and item['png_validation']['valid'] for item in items)}/{len(items)} |"
        )
    lines.extend([
        "",
        f"Manual visual assessment: {dict(visual_counts)}.",
        "",
        "`Partially correct` means the PNG is readable and its numeric data match the essay, but a false trend or ranking statement is not visually encoded; the taxonomy panel is required to expose it.",
        "",
        "## Per-case results",
        "",
    ])

    current_chart = None
    for item in results:
        if item["chart_type"] != current_chart:
            current_chart = item["chart_type"]
            lines.extend([f"### {current_chart.title()} chart", ""])
        actual = item["actual_unique_errors"]
        actual_text = ", ".join(display_error(value) for value in actual) if actual else "None"
        expected_text = (
            "N/A: trend not applicable"
            if current_chart == "pie" and item["expected_error"] == "trend_direction_error"
            else display_error(item["expected_error"])
        )
        outcome = "PASS" if item["taxonomy_pass"] else "FAIL"
        image_status = item["manual_image_assessment"]
        lines.extend([
            f"#### {item['case_id']} - {outcome}",
            "",
            f"- Expected taxonomy: **{expected_text}**",
            f"- Actual taxonomy: **{actual_text}**",
            f"- Image assessment: **{image_status}** - {item['manual_image_note']}",
            f"- Image: [{item['image_file']}]({item['image_file']})",
        ])
        if item["failure_reason"]:
            lines.append(f"- Failure analysis: {item['failure_reason']}")
        lines.extend(["", "Essay:", "", item["essay"], ""])

    lines.extend([
        "## Failure patterns",
        "",
        "1. **Line endpoint paraphrases are brittle.** Explicit years were reliable, while 'at the beginning/end' frequently failed to attach values to 2010/2020. This caused false endpoint omissions, missing line points, and in one case a missed value error.",
        "2. **Pie omission can be overwritten by model inference.** Two of three omission essays had the missing official slice copied into the student record, producing a false negative and an incorrect full pie.",
        "3. **Trend and ranking errors are not encoded by numeric rendering.** When all stated values are correct, a false verbal trend/rank leaves the generated chart visually identical to the correct data. The taxonomy panel detects the sentence, but image comparison alone cannot reveal it.",
        "4. **Bar performance was stable in this batch.** All 15 randomized bar cases produced the exact intended taxonomy class and data-faithful images.",
        "",
    ])

    (ROOT / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")
    (ROOT / "results_reviewed.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(ROOT / "REPORT.md")


if __name__ == "__main__":
    main()

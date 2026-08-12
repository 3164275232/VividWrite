from __future__ import annotations

import json
import shutil
import sys
import time
from collections import Counter
from pathlib import Path

from dotenv import load_dotenv
from PIL import Image, ImageStat


ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parents[1]
BACKEND = PROJECT / "backend"
sys.path.insert(0, str(BACKEND))
load_dotenv(BACKEND / ".env")

from chart_feedback import ChartFeedbackService  # noqa: E402


DEPLOT = {
    "bar": (
        "TITLE | Household recycling rates in five UK cities, 2015 and 2020<0x0A>"
        "CHART TYPE | Bar chart<0x0A>City | 2015 | 2020<0x0A>"
        "Bristol | 41.70 | 55.20<0x0A>Leeds | 35.26 | 48.16<0x0A>"
        "Liverpool | 28.05 | 39.15<0x0A>Manchester | 30.78 | 46.13<0x0A>"
        "Sheffield | 38.19 | 50.80"
    ),
    "line": (
        "TITLE | Average daily passengers using public transport, 2010-2020<0x0A>"
        "CHART TYPE | Line graph<0x0A>Year | Bus | Rail | Metro<0x0A>"
        "2010 | 1.8 | 1.1 | 0.8<0x0A>2012 | 1.9 | 1.3 | 1<0x0A>"
        "2014 | 1.7 | 1.5 | 1.2<0x0A>2016 | 1.6 | 1.8 | 1.5<0x0A>"
        "2018 | 1.5 | 2 | 1.7<0x0A>2020 | 1.3 | 2.2 | 1.9"
    ),
    "pie": (
        "TITLE | Average household expenditure in Canada, 2024<0x0A>"
        "CHART TYPE | Pie chart<0x0A>Category | Percentage<0x0A>"
        "Housing | 32%<0x0A>Food | 21%<0x0A>Transport | 17%<0x0A>"
        "Leisure | 12%<0x0A>Utilities | 10%<0x0A>Other | 8%"
    ),
}

IMAGES = {
    "bar": PROJECT / "test_samples" / "charts" / "01_bar_recycling_rates.png",
    "line": PROJECT / "test_samples" / "charts" / "02_line_daily_passengers.png",
    "pie": PROJECT / "test_samples" / "charts" / "04_pie_household_spending.png",
}

BAR = {
    "Bristol": {"2015": 42.0, "2020": 55.0},
    "Leeds": {"2015": 35.0, "2020": 48.0},
    "Liverpool": {"2015": 28.0, "2020": 39.0},
    "Manchester": {"2015": 31.0, "2020": 46.0},
    "Sheffield": {"2015": 38.0, "2020": 51.0},
}
LINE = {
    "Bus": {"2010": 1.8, "2012": 1.9, "2014": 1.7, "2016": 1.6, "2018": 1.5, "2020": 1.3},
    "Rail": {"2010": 1.1, "2012": 1.3, "2014": 1.5, "2016": 1.8, "2018": 2.0, "2020": 2.2},
    "Metro": {"2010": 0.8, "2012": 1.0, "2014": 1.2, "2016": 1.5, "2018": 1.7, "2020": 1.9},
}
PIE = {"Housing": 32.0, "Food": 21.0, "Transport": 17.0, "Leisure": 12.0, "Utilities": 10.0, "Other": 8.0}


def intended_values(case: dict) -> dict[tuple[str, str], float | None]:
    error = case["expected_error"]
    meta = case["generation_metadata"]
    chart_type = case["chart_type"]
    if chart_type == "bar":
        values = {(city, year): value for city, years in BAR.items() for year, value in years.items()}
        if error == "value_inaccuracy":
            values[(meta["entity"], meta["period"])] = float(meta["claimed"])
        elif error == "entity_misalignment":
            left, right = meta["entities"]
            period = meta["period"]
            values[(left, period)], values[(right, period)] = values[(right, period)], values[(left, period)]
        elif error == "key_feature_omission":
            for year in BAR[meta["omitted_entity"]]:
                values[(meta["omitted_entity"], year)] = None
        return values

    if chart_type == "line":
        midpoint = meta["sampled_midpoint"]
        values = {
            (mode, year): value if year in {"2010", midpoint, "2020"} else None
            for mode, years in LINE.items()
            for year, value in years.items()
        }
        if error == "value_inaccuracy":
            values[(meta["entity"], meta["period"])] = float(meta["claimed"])
        elif error == "entity_misalignment":
            left, right = meta["entities"]
            period = meta["period"]
            values[(left, period)], values[(right, period)] = values[(right, period)], values[(left, period)]
        elif error == "key_feature_omission":
            for year in LINE[meta["omitted_entity"]]:
                values[(meta["omitted_entity"], year)] = None
        return values

    values = {(category, ""): value for category, value in PIE.items()}
    if error == "value_inaccuracy":
        values[(meta["entity"], "")] = float(meta["claimed"])
    elif error == "entity_misalignment":
        left, right = meta["entities"]
        values[(left, "")], values[(right, "")] = values[(right, "")], values[(left, "")]
    elif error == "key_feature_omission":
        values[(meta["omitted_entity"], "")] = None
    return values


def record_key(chart_type: str, record: dict) -> tuple[str, str]:
    category = str(record.get("category") or "")
    series = str(record.get("series") or "")
    period = str(record.get("period") or "")
    if chart_type == "pie":
        return category or series, ""
    temporal = category if category[:4].isdigit() else period if period[:4].isdigit() else series if series[:4].isdigit() else ""
    entity = series if temporal == category else category if temporal == series else series or category
    return entity, temporal


def validate_records(case: dict, records: list[dict]) -> dict:
    expected = intended_values(case)
    actual = {}
    duplicates = []
    for record in records:
        key = record_key(case["chart_type"], record)
        if key in actual:
            duplicates.append(key)
        value = record.get("value")
        actual[key] = None if value is None or record.get("missing") else float(value)

    mismatches = []
    for key, expected_value in expected.items():
        actual_value = actual.get(key)
        if expected_value is None and actual_value is None:
            continue
        if expected_value is None or actual_value is None or abs(expected_value - actual_value) > 1e-6:
            mismatches.append({"key": list(key), "expected": expected_value, "actual": actual_value})
    unexpected = [list(key) for key in actual if key not in expected and actual[key] is not None]
    return {
        "correct": not mismatches and not unexpected and not duplicates,
        "mismatches": mismatches,
        "unexpected_records": unexpected,
        "duplicate_keys": [list(key) for key in duplicates],
    }


def validate_png(path: Path) -> dict:
    if not path.exists() or path.stat().st_size < 1000:
        return {"valid": False, "reason": "missing_or_too_small"}
    with Image.open(path) as image:
        rgb = image.convert("RGB")
        stat = ImageStat.Stat(rgb)
        extrema = rgb.getextrema()
        nonblank = any(high - low >= 15 for low, high in extrema)
        return {
            "valid": bool(nonblank and image.width >= 400 and image.height >= 250),
            "width": image.width,
            "height": image.height,
            "mean_rgb": [round(value, 2) for value in stat.mean],
            "extrema": [list(item) for item in extrema],
        }


def expected_outcome(case: dict) -> tuple[list[str], bool | None]:
    if case["chart_type"] == "pie" and case["expected_error"] == "trend_direction_error":
        return [], False
    return [case["expected_error"]], None


def main() -> None:
    manifest = json.loads((ROOT / "cases.json").read_text(encoding="utf-8"))
    output_dir = ROOT / "generated_images"
    output_dir.mkdir(parents=True, exist_ok=True)
    raw_path = ROOT / "results_raw.json"
    existing = {}
    if raw_path.exists():
        existing = {item["case_id"]: item for item in json.loads(raw_path.read_text(encoding="utf-8"))["results"]}

    results = []
    service = ChartFeedbackService(BACKEND / "generated_charts")
    started = time.time()
    for index, case in enumerate(manifest["cases"], start=1):
        if case["case_id"] in existing and existing[case["case_id"]].get("success"):
            results.append(existing[case["case_id"]])
            print(f"[{index:02d}/45] {case['case_id']} RESUME", flush=True)
            continue
        expected_errors, expected_trend_applicable = expected_outcome(case)
        case_started = time.time()
        try:
            chart_data, filename = service.generate(
                chart_type=case["chart_type"],
                requirement="Summarise the information by selecting and reporting the main features, and make comparisons where relevant.",
                student_answer=case["essay"],
                deplot_text=DEPLOT[case["chart_type"]],
                image_path=IMAGES[case["chart_type"]],
            )
            source = BACKEND / "generated_charts" / filename
            destination = output_dir / f"{case['case_id']}.png"
            shutil.copy2(source, destination)
            taxonomy = chart_data.get("error_taxonomy") or {}
            issues = taxonomy.get("issues") or []
            actual_errors = [item.get("error_type") for item in issues]
            unique_errors = list(dict.fromkeys(actual_errors))
            trend_applicable = (taxonomy.get("applicability") or {}).get("trend_direction_error", {}).get("applicable")
            taxonomy_pass = unique_errors == expected_errors
            if expected_trend_applicable is not None:
                taxonomy_pass = taxonomy_pass and trend_applicable is expected_trend_applicable
            data_validation = validate_records(case, chart_data.get("records") or [])
            png_validation = validate_png(destination)
            image_correct = data_validation["correct"] and png_validation["valid"]
            item = {
                "case_id": case["case_id"],
                "chart_type": case["chart_type"],
                "expected_error": case["expected_error"],
                "expected_output": expected_errors or ["N/A: trend not applicable"],
                "actual_errors": actual_errors,
                "actual_unique_errors": unique_errors,
                "trend_applicable": trend_applicable,
                "taxonomy_pass": taxonomy_pass,
                "image_correct": image_correct,
                "image_file": str(destination.relative_to(ROOT)).replace("\\", "/"),
                "image_data_validation": data_validation,
                "png_validation": png_validation,
                "issues": issues,
                "records": chart_data.get("records") or [],
                "essay": case["essay"],
                "generation_metadata": case["generation_metadata"],
                "duration_seconds": round(time.time() - case_started, 2),
                "success": True,
            }
            status = "PASS" if taxonomy_pass and image_correct else "FAIL"
            print(
                f"[{index:02d}/45] {case['case_id']} {status} "
                f"actual={unique_errors or ['N/A']} image={image_correct} "
                f"{item['duration_seconds']:.1f}s",
                flush=True,
            )
        except Exception as exc:
            item = {
                "case_id": case["case_id"],
                "chart_type": case["chart_type"],
                "expected_error": case["expected_error"],
                "expected_output": expected_errors or ["N/A: trend not applicable"],
                "actual_errors": [],
                "actual_unique_errors": [],
                "trend_applicable": None,
                "taxonomy_pass": False,
                "image_correct": False,
                "essay": case["essay"],
                "generation_metadata": case["generation_metadata"],
                "duration_seconds": round(time.time() - case_started, 2),
                "success": False,
                "error": f"{type(exc).__name__}: {exc}",
            }
            print(f"[{index:02d}/45] {case['case_id']} ERROR {item['error']}", flush=True)

        results.append(item)
        raw_path.write_text(
            json.dumps({"manifest_sha256": (ROOT / "manifest.sha256").read_text().split()[0], "results": results}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    counts = Counter((item["chart_type"], bool(item["taxonomy_pass"]), bool(item["image_correct"])) for item in results)
    summary = {
        "manifest_sha256": (ROOT / "manifest.sha256").read_text().split()[0],
        "case_count": len(results),
        "taxonomy_passes": sum(bool(item["taxonomy_pass"]) for item in results),
        "image_passes": sum(bool(item["image_correct"]) for item in results),
        "fully_passed": sum(bool(item["taxonomy_pass"] and item["image_correct"]) for item in results),
        "api_errors": sum(not item["success"] for item in results),
        "duration_seconds": round(time.time() - started, 2),
        "by_chart": {
            chart_type: {
                "cases": sum(item["chart_type"] == chart_type for item in results),
                "taxonomy_passes": sum(item["chart_type"] == chart_type and item["taxonomy_pass"] for item in results),
                "image_passes": sum(item["chart_type"] == chart_type and item["image_correct"] for item in results),
            }
            for chart_type in ("bar", "line", "pie")
        },
    }
    (ROOT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()

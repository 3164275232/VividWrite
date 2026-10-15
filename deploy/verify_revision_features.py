"""Render deterministic provenance fixtures for browser checks; no model calls."""

import json
import copy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from chart_renderer import render_vega_lite_png
from move_feedback import MOVE_DEFINITIONS


def main():
    output = ROOT / "backend" / "user_data" / "revision_feature_checks"
    output.mkdir(parents=True, exist_ok=True)
    records = []
    series_values = {"Bus": [1.8, 1.9, 1.7, 1.6, 1.5, 1.3],
                     "Rail": [1.1, 1.32, 1.54, 1.76, 1.98, 2.2],
                     "Metro": [0.8, 1.02, 1.24, 1.46, 1.68, 1.9]}
    for series, values in series_values.items():
        for index, value in enumerate(values):
            estimated = series != "Bus" and index not in (0, 5)
            record = {"category": str(2010 + index * 2), "period": str(2010 + index * 2),
                      "series": series, "value": value, "estimated": estimated,
                      "explicit_student_value": not estimated, "missing": False}
            if estimated:
                record["inference"] = {"method": "linear_interpolation",
                                       "student_evidence": ("Rail rose steadily from 1.1 million in 2010 to 2.2 million in 2020."
                                                            if series == "Rail" else "Metro use grew steadily from 0.8 million to 1.9 million."),
                                       "from": {"period": "2010", "value": values[0]},
                                       "to": {"period": "2020", "value": values[-1]}}
            records.append(record)
    spec = {"mark": "line", "encoding": {
        "x": {"field": "period", "type": "ordinal", "title": "Year"},
        "y": {"field": "value", "type": "quantitative", "title": "Passengers (millions)"},
        "color": {"field": "series", "type": "nominal", "title": "Transport mode"}}}
    title = "Average daily passengers using public transport, 2010-2020"
    rendered_spec = render_vega_lite_png(spec, records, title, output / "line_estimates.png",
                         palette=["#d0443e", "#287d80", "#edbf5f"], chart_type="line")
    wrong_records = copy.deepcopy(records)
    wrong_records[0].update(value=1.4, official_value=1.8, feedback_status="incorrect")
    render_vega_lite_png(spec, wrong_records, title, output / "line_wrong_value.png",
                        palette=["#d0443e", "#287d80", "#edbf5f"], chart_type="line")
    bar_records = [{"category": city, "series": year, "value": value,
                    "estimated": city == "Leeds" and year == "2020"}
                   for city, before, after in [("Bristol", 42, 55), ("Leeds", 35, 48),
                                                ("Liverpool", 28, 39), ("Manchester", 31, 46),
                                                ("Sheffield", 38, 51)]
                   for year, value in [("2015", before), ("2020", after)]]
    bar_spec = {"mark": "bar", "encoding": {
        "x": {"field": "category", "type": "nominal", "title": "City"},
        "y": {"field": "value", "type": "quantitative", "title": "Recycling rate (%)"},
        "xOffset": {"field": "series"}, "color": {"field": "series", "type": "nominal", "title": "Year"}}}
    render_vega_lite_png(bar_spec, bar_records, "Household recycling rates", output / "bar_estimates.png",
                         palette=["#2f6690", "#d97706"], chart_type="bar")
    pie_records = [{"category": category, "value": value, "estimated": category == "Food"}
                   for category, value in [("Housing", 32), ("Food", 21), ("Transport", 17),
                                            ("Leisure", 12), ("Utilities", 10), ("Other", 8)]]
    render_vega_lite_png({}, pie_records, "Average household expenditure in Canada, 2024",
                         output / "pie_estimates.png", chart_type="pie", unit="%")
    stacked_records = [{"category": year, "series": series, "value": value,
                        "estimated": year == "2010" and series == "A"}
                       for year, first, second in [("2010", 40, 60), ("2020", 45, 65)]
                       for series, value in [("A", first), ("B", second)]]
    stacked_spec = {"mark": "bar", "encoding": {
        "x": {"field": "category", "type": "nominal", "title": "Year"},
        "y": {"field": "value", "type": "quantitative", "title": "Value"},
        "color": {"field": "series", "type": "nominal"}}}
    render_vega_lite_png(stacked_spec, stacked_records, "Estimated value in a stacked chart",
                        output / "stacked_estimates.png", chart_type="bar")
    fixtures = {"records": records, "definitions": MOVE_DEFINITIONS, "title": title, "spec": rendered_spec}
    (output / "fixtures.json").write_text(json.dumps(fixtures), encoding="utf-8")
    print(f"Deterministic renderer fixtures: {output}")


if __name__ == "__main__":
    main()

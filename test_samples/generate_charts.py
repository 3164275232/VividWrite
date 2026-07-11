"""Generate deterministic IELTS Task 1 chart fixtures for manual testing."""

from __future__ import annotations

import json
from pathlib import Path

import vl_convert as vlc


OUTPUT_DIR = Path(__file__).resolve().parent / "charts"


def save_chart(filename: str, title: str, values: list[dict], spec: dict) -> None:
    chart = {
        "$schema": "https://vega.github.io/schema/vega-lite/v6.json",
        "data": {"values": values},
        "title": {"text": title, "fontSize": 18, "anchor": "middle", "offset": 18},
        "width": 760,
        "height": 440,
        "background": "white",
        "autosize": {"type": "fit", "contains": "padding"},
        "config": {
            "font": "Arial",
            "axis": {
                "labelFontSize": 12,
                "titleFontSize": 14,
                "gridColor": "#e5e7eb",
                "domainColor": "#4b5563",
            },
            "legend": {"labelFontSize": 12, "titleFontSize": 13, "orient": "bottom"},
            "view": {"stroke": None},
        },
        **spec,
    }
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    png = vlc.vegalite_to_png(json.dumps(chart), scale=2)
    (OUTPUT_DIR / filename).write_bytes(png)


def generate_bar_chart() -> None:
    values = [
        {"city": city, "year": year, "rate": rate}
        for city, rates in {
            "Bristol": {"2015": 42, "2020": 55},
            "Leeds": {"2015": 35, "2020": 48},
            "Liverpool": {"2015": 28, "2020": 39},
            "Manchester": {"2015": 31, "2020": 46},
            "Sheffield": {"2015": 38, "2020": 51},
        }.items()
        for year, rate in rates.items()
    ]
    save_chart(
        "01_bar_recycling_rates.png",
        "Household recycling rates in five UK cities, 2015 and 2020",
        values,
        {
            "mark": {"type": "bar", "cornerRadiusTopLeft": 2, "cornerRadiusTopRight": 2},
            "encoding": {
                "x": {"field": "city", "type": "nominal", "title": "City", "sort": None},
                "xOffset": {"field": "year"},
                "y": {"field": "rate", "type": "quantitative", "title": "Households recycling (%)", "scale": {"domain": [0, 60]}},
                "color": {
                    "field": "year",
                    "type": "nominal",
                    "title": "Year",
                    "scale": {"domain": ["2015", "2020"], "range": ["#2f6690", "#d97706"]},
                },
            },
        },
    )


def generate_line_chart() -> None:
    values = [
        {"year": year, "mode": mode, "passengers": passengers}
        for year, modes in {
            "2010": {"Bus": 1.8, "Rail": 1.1, "Metro": 0.8},
            "2012": {"Bus": 1.9, "Rail": 1.3, "Metro": 1.0},
            "2014": {"Bus": 1.7, "Rail": 1.5, "Metro": 1.2},
            "2016": {"Bus": 1.6, "Rail": 1.8, "Metro": 1.5},
            "2018": {"Bus": 1.5, "Rail": 2.0, "Metro": 1.7},
            "2020": {"Bus": 1.3, "Rail": 2.2, "Metro": 1.9},
        }.items()
        for mode, passengers in modes.items()
    ]
    save_chart(
        "02_line_daily_passengers.png",
        "Average daily passengers using public transport, 2010-2020",
        values,
        {
            "mark": {"type": "line", "point": {"filled": True, "size": 70}, "strokeWidth": 3},
            "encoding": {
                "x": {"field": "year", "type": "ordinal", "title": "Year", "sort": None},
                "y": {"field": "passengers", "type": "quantitative", "title": "Passengers (millions)", "scale": {"domain": [0.5, 2.4]}},
                "color": {
                    "field": "mode",
                    "type": "nominal",
                    "title": "Transport mode",
                    "scale": {"domain": ["Bus", "Rail", "Metro"], "range": ["#c2413b", "#287271", "#e9c46a"]},
                },
            },
        },
    )


def generate_area_chart() -> None:
    values = [
        {"year": year, "source": source, "electricity": amount}
        for year, sources in {
            "2000": {"Hydro": 45, "Wind": 5, "Solar": 1},
            "2005": {"Hydro": 48, "Wind": 12, "Solar": 3},
            "2010": {"Hydro": 50, "Wind": 25, "Solar": 8},
            "2015": {"Hydro": 52, "Wind": 42, "Solar": 20},
            "2020": {"Hydro": 55, "Wind": 65, "Solar": 38},
        }.items()
        for source, amount in sources.items()
    ]
    save_chart(
        "03_area_renewable_electricity.png",
        "Electricity generated from renewable sources, 2000-2020",
        values,
        {
            "mark": {"type": "area", "opacity": 0.88, "line": {"color": "white", "strokeWidth": 1}},
            "encoding": {
                "x": {"field": "year", "type": "ordinal", "title": "Year", "sort": None},
                "y": {"field": "electricity", "type": "quantitative", "title": "Electricity (TWh)", "stack": "zero"},
                "color": {
                    "field": "source",
                    "type": "nominal",
                    "title": "Source",
                    "scale": {"domain": ["Hydro", "Wind", "Solar"], "range": ["#277da1", "#43aa8b", "#f9c74f"]},
                },
                "order": {"field": "source", "sort": "ascending"},
            },
        },
    )


def generate_pie_chart() -> None:
    values = [
        {"category": category, "percentage": percentage, "label": f"{category} {percentage}%", "order": order}
        for order, (category, percentage) in enumerate([
            ("Housing", 32),
            ("Food", 21),
            ("Transport", 17),
            ("Leisure", 12),
            ("Utilities", 10),
            ("Other", 8),
        ])
    ]
    save_chart(
        "04_pie_household_spending.png",
        "Average household expenditure in Canada, 2024",
        values,
        {
            "layer": [
                {
                    "mark": {"type": "arc", "outerRadius": 175, "stroke": "white", "strokeWidth": 2},
                    "encoding": {
                        "theta": {"field": "percentage", "type": "quantitative", "stack": True},
                        "order": {"field": "order", "type": "ordinal", "sort": "ascending"},
                        "color": {
                            "field": "category",
                            "type": "nominal",
                            "title": "Spending category",
                            "scale": {
                                "domain": ["Housing", "Food", "Transport", "Leisure", "Utilities", "Other"],
                                "range": ["#355070", "#6d597a", "#b56576", "#e56b6f", "#eaac8b", "#7f8c8d"],
                            },
                        },
                    },
                },
                {
                    "mark": {"type": "text", "radius": 120, "fontSize": 12, "fontWeight": "bold", "color": "white"},
                    "encoding": {
                        "theta": {"field": "percentage", "type": "quantitative", "stack": True},
                        "order": {"field": "order", "type": "ordinal", "sort": "ascending"},
                        "text": {"field": "label", "type": "nominal"},
                    },
                },
            ]
        },
    )


def generate_scatter_chart() -> None:
    values = [
        {"country": "A", "study_hours": 4.0, "score": 58, "region": "Europe"},
        {"country": "B", "study_hours": 5.5, "score": 64, "region": "Europe"},
        {"country": "C", "study_hours": 7.0, "score": 71, "region": "Europe"},
        {"country": "D", "study_hours": 8.5, "score": 77, "region": "Europe"},
        {"country": "E", "study_hours": 10.0, "score": 83, "region": "Asia"},
        {"country": "F", "study_hours": 11.5, "score": 88, "region": "Asia"},
        {"country": "G", "study_hours": 6.0, "score": 67, "region": "Asia"},
        {"country": "H", "study_hours": 9.0, "score": 80, "region": "Asia"},
    ]
    save_chart(
        "05_scatter_study_and_scores.png",
        "Weekly independent study and average examination scores",
        values,
        {
            "layer": [
                {
                    "mark": {"type": "point", "filled": True, "size": 170, "opacity": 0.88},
                    "encoding": {
                        "x": {"field": "study_hours", "type": "quantitative", "title": "Independent study (hours per week)", "scale": {"domain": [3, 13]}},
                        "y": {"field": "score", "type": "quantitative", "title": "Average examination score", "scale": {"domain": [50, 95]}},
                        "color": {"field": "region", "type": "nominal", "title": "Region", "scale": {"range": ["#3a86ff", "#ff7f51"]}},
                    },
                },
                {
                    "mark": {"type": "text", "dx": 10, "dy": -10, "fontSize": 11},
                    "encoding": {
                        "x": {"field": "study_hours", "type": "quantitative"},
                        "y": {"field": "score", "type": "quantitative"},
                        "text": {"field": "country", "type": "nominal"},
                    },
                },
            ]
        },
    )


if __name__ == "__main__":
    generate_bar_chart()
    generate_line_chart()
    generate_area_chart()
    generate_pie_chart()
    generate_scatter_chart()
    print(f"Generated 5 charts in {OUTPUT_DIR}")

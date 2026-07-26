"""Render a deterministic chart for deployment font verification."""

from pathlib import Path

from chart_renderer import render_vega_lite_png


records = [
    {"category": city, "series": year, "value": value}
    for city, values in (
        ("Bristol", (42, 55)),
        ("Leeds", (35, 48)),
        ("Liverpool", (28, 39)),
        ("Manchester", (31, 46)),
        ("Sheffield", (38, 51)),
    )
    for year, value in zip(("2015", "2020"), values)
]

spec = {
    "mark": "bar",
    "encoding": {
        "x": {
            "field": "category",
            "type": "ordinal",
            "title": "City",
            "axis": {"labelColor": "white", "titleColor": "white"},
        },
        "xOffset": {"field": "series"},
        "y": {
            "field": "value",
            "type": "quantitative",
            "title": "Household recycling rate (%)",
            "axis": {"labelColor": "white", "titleColor": "white"},
        },
        "color": {
            "field": "series",
            "type": "nominal",
            "title": "Year",
            "legend": {"labelColor": "white", "titleColor": "white"},
        },
    },
}

output_path = Path("/tmp/chart-text-verification.png")
render_vega_lite_png(
    spec,
    records,
    "Household recycling rates",
    output_path,
    ["#356d96", "#df7900"],
    chart_type="bar",
    unit="%",
)
print(output_path)

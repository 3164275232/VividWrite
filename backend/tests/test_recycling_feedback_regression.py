import tempfile
import unittest
from pathlib import Path

from PIL import Image

from chart_feedback import (
    _annotate_cartesian_accuracy,
    _merge_explicit_cartesian_values,
    _remove_unsupported_cartesian_values,
)
from chart_renderer import render_vega_lite_png


DEPLOT_TABLE = """TITLE | Household recycling rates in five UK cities, 2015 and 2020
City | 2015 | 2020
Bristol | 42 | 55
Leeds | 35 | 48
Liverpool | 28 | 39
Manchester | 31 | 46
Sheffield | 38 | 51"""

STUDENT_ESSAY = (
    "In 2015, Bristol led with 42%. Sheffield followed with 38%, and Leeds was "
    "close behind at 35%. Manchester and Liverpool recorded 31% and 28% "
    "respectively. By 2020, Bristol had reached 55%. Sheffield reached 51%. "
    "Leeds increased from 35% to 48%, a gain of 13 percentage points. Manchester "
    "moved from 31% to 46%. Liverpool grew from 28% to 39%."
)


class RecyclingFeedbackRegressionTests(unittest.TestCase):
    def test_recycling_values_are_aligned_to_the_official_city_year_framework(self):
        result = {
            "chart_type": "bar",
            "axes": {"unit": "%", "y_label": "Households recycling (%)"},
            "records": [
                {"category": "2015", "series": "Bristol", "value": 42},
                {"category": "2020", "series": "Bristol", "value": 55},
            ],
            "comparison": {},
        }

        _merge_explicit_cartesian_values(result, DEPLOT_TABLE, STUDENT_ESSAY)
        _remove_unsupported_cartesian_values(result, DEPLOT_TABLE, STUDENT_ESSAY)
        _annotate_cartesian_accuracy(result, DEPLOT_TABLE)

        self.assertEqual(len(result["records"]), 10)
        actual = {
            (record["category"], record["series"]): record["value"]
            for record in result["records"]
        }
        self.assertEqual(
            actual,
            {
                ("Bristol", "2015"): 42,
                ("Bristol", "2020"): 55,
                ("Leeds", "2015"): 35,
                ("Leeds", "2020"): 48,
                ("Liverpool", "2015"): 28,
                ("Liverpool", "2020"): 39,
                ("Manchester", "2015"): 31,
                ("Manchester", "2020"): 46,
                ("Sheffield", "2015"): 38,
                ("Sheffield", "2020"): 51,
            },
        )
        self.assertTrue(
            all(record["feedback_status"] == "correct" for record in result["records"])
        )
        self.assertEqual(result["comparison"]["incorrect_official_items"], [])

    def test_exported_png_contains_visible_title_text(self):
        records = [
            {"category": "Bristol", "series": "2015", "value": 42},
            {"category": "Bristol", "series": "2020", "value": 55},
            {"category": "Leeds", "series": "2015", "value": 35},
            {"category": "Leeds", "series": "2020", "value": 48},
        ]
        spec = {
            "mark": "bar",
            "encoding": {
                "x": {"field": "category", "type": "ordinal", "title": "City"},
                "y": {
                    "field": "value",
                    "type": "quantitative",
                    "title": "Households recycling (%)",
                },
                "color": {"field": "series", "type": "nominal", "title": "Year"},
                "xOffset": {"field": "series"},
            },
        }

        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "recycling.png"
            render_vega_lite_png(
                spec,
                records,
                "Household recycling rates",
                output,
                ["#31688e", "#e27600"],
                chart_type="bar",
                unit="%",
            )
            with Image.open(output).convert("RGB") as image:
                title_region = image.crop((0, 0, image.width, min(55, image.height)))
                pixels = (
                    title_region.get_flattened_data()
                    if hasattr(title_region, "get_flattened_data")
                    else title_region.getdata()
                )
                dark_pixels = sum(
                    1
                    for red, green, blue in pixels
                    if red < 90 and green < 90 and blue < 90
                )

        self.assertGreater(dark_pixels, 100)


if __name__ == "__main__":
    unittest.main()

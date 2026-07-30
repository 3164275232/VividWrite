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

SCREENSHOT_SAMPLE_ESSAY = (
    "The bar chart illustrates the percentage of household waste recycled in five "
    "UK cities in the years 2015 and 2020. "
    "Overall, recycling rates increased in all five cities over the five-year period, "
    "with Bristol consistently recording the highest figures and Liverpool the lowest. "
    "The ranking of the cities remained unchanged between the two years, and the gap "
    "between the highest and lowest performers widened slightly. "
    "In 2015, Bristol led the group with a recycling rate of 42%, followed by Sheffield "
    "at 38%. Leeds and Manchester recorded somewhat lower rates of 35% and 31% "
    "respectively, while Liverpool had the smallest proportion at 28%. By 2020, all "
    "cities had achieved notable growth. Bristol's rate rose by 13 percentage points "
    "to reach 55%, maintaining its top position. Sheffield similarly saw a substantial "
    "increase of 13 percentage points, climbing to 51%. "
    "The remaining three cities also experienced clear upward trends, though their "
    "rates remained below 50%. Leeds improved from 35% to 48%, and Manchester advanced "
    "from 31% to 46%. Liverpool, despite remaining in last place, recorded the largest "
    "relative gain of 11 percentage points, rising from 28% to 39%. Consequently, the "
    "overall spread between the highest and lowest figures grew from 14 percentage "
    "points in 2015 to 16 percentage points in 2020."
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

    def test_screenshot_sample_essay_does_not_cross_assign_adjacent_city_ranges(self):
        result = {
            "chart_type": "bar",
            "axes": {"unit": "%", "y_label": "Households recycling (%)"},
            "records": [],
            "comparison": {},
        }

        _merge_explicit_cartesian_values(result, DEPLOT_TABLE, SCREENSHOT_SAMPLE_ESSAY)
        _remove_unsupported_cartesian_values(result, DEPLOT_TABLE, SCREENSHOT_SAMPLE_ESSAY)
        _annotate_cartesian_accuracy(result, DEPLOT_TABLE)

        manchester = {
            record["series"]: record
            for record in result["records"]
            if record["category"] == "Manchester"
        }
        self.assertEqual(manchester["2015"]["value"], 31)
        self.assertEqual(manchester["2020"]["value"], 46)
        self.assertEqual(manchester["2015"].get("conflicting_values"), [])
        self.assertEqual(manchester["2020"].get("conflicting_values"), [])
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

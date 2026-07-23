import unittest
from pathlib import Path

from PIL import Image

from chart_detection import crop_pie_plot, detect_chart_type
from chart_text import (
    InvalidExtractedChartData,
    add_chart_type_metadata,
    build_table_fact_checks,
    infer_deplot_value_precision,
    normalize_deplot_numeric_precision,
    normalize_pie_deplot_text,
    parse_numeric_chart_table,
    parse_series_framework,
    parse_validated_pie_table,
    round_chart_value,
    round_deplot_table_values,
)


FULL_DEPLOT_TEXT = (
    "TITLE | Average household expenditure in Canada, 2024<0x0A>"
    "Spending category | Housing | Food | Transport | Leisure | Utilities | Other<0x0A>"
    "Spending category | 8% | 8% | 12% | 11% | 17% | 21%<0x0A>"
    "Housing 32% | 32% | 8% | 12% | 10% | 10% | 12%"
)

ISOLATED_PLOT_TEXT = (
    "TITLE |<0x0A>Other 8% | 8%<0x0A>Utilities 10% | 10%<0x0A>"
    "Leisure 12% | 12%<0x0A>Transport 17% | 17%<0x0A>"
    "Food 21% | 21%<0x0A>Housing 32% | 32%"
)


class ChartTextTests(unittest.TestCase):
    def test_deplot_values_use_conventional_integer_rounding(self):
        rounded = round_deplot_table_values(
            "TITLE | Recycling<0x0A>Year | City A | City B<0x0A>"
            "2015 | 48.12% | 48.50%<0x0A>2020 | 49.51% | 46%"
        )

        self.assertEqual(round_chart_value(48.5), 49.0)
        self.assertIn("2015 | 48% | 49%", rounded)
        self.assertIn("2020 | 50% | 46%", rounded)

    def test_small_scale_deplot_values_keep_meaningful_decimals(self):
        rounded = round_deplot_table_values(
            "TITLE | Passengers<0x0A>Year | Bus | Rail<0x0A>"
            "2010 | 1.8 | 1.1<0x0A>2020 | 1.3 | 2.2",
            chart_type="line",
        )

        self.assertEqual(
            infer_deplot_value_precision(rounded, "line"),
            1,
        )
        self.assertIn("2010 | 1.8 | 1.1", rounded)
        self.assertIn("2020 | 1.3 | 2.2", rounded)

    def test_numeric_chart_table_supports_single_and_grouped_bar_series(self):
        single = parse_numeric_chart_table(
            "TITLE | Calls<0x0A>Year | Local<0x0A>2001 | 72<0x0A>2002 | 75"
        )
        grouped = parse_numeric_chart_table(
            "City | 2015 | 2020<0x0A>Bristol | 42 | 55<0x0A>Leeds | 35 | 48"
        )

        self.assertEqual(
            single,
            [
                {"axis_label": "Year", "category": "2001", "series": "Local", "value": 72.0},
                {"axis_label": "Year", "category": "2002", "series": "Local", "value": 75.0},
            ],
        )
        self.assertEqual(grouped[3]["value"], 48.0)

    def test_line_table_snaps_deplot_noise_to_the_shared_tenth_grid(self):
        raw = (
            "TITLE | Passengers<0x0A>Year | Bus | Rail | Metro<0x0A>"
            "2010 | 1.80 | 1.06 | 0.80<0x0A>2012 | 1.90 | 1.33 | 1<0x0A>"
            "2014 | 1.70 | 1.49 | 1.20<0x0A>2016 | 1.60 | 1.80 | 1.50<0x0A>"
            "2018 | 1.50 | 2 | 1.70<0x0A>2020 | 1.30 | 2.20 | 1.90"
        )

        normalized = add_chart_type_metadata(normalize_deplot_numeric_precision(raw), "line")

        self.assertIn("CHART TYPE | Line graph", normalized)
        self.assertIn("2010 | 1.8 | 1.1 | 0.8", normalized)
        self.assertIn("2012 | 1.9 | 1.3 | 1", normalized)
        self.assertIn("2014 | 1.7 | 1.5 | 1.2", normalized)
        self.assertEqual(len(parse_series_framework(normalized)), 18)
        facts = build_table_fact_checks(normalized)
        self.assertIn("2016 ranking: Rail (1.8) > Bus (1.6) > Metro (1.5)", facts)
        self.assertIn("Between 2014 and 2016, Rail overtakes Bus", facts)
        self.assertIn("Between 2016 and 2018, Metro overtakes Bus", facts)

    def test_pie_normalization_uses_full_metadata_and_isolated_values(self):
        normalized = normalize_pie_deplot_text(FULL_DEPLOT_TEXT, ISOLATED_PLOT_TEXT)

        self.assertIn("TITLE | Average household expenditure in Canada, 2024", normalized)
        self.assertEqual(
            parse_validated_pie_table(normalized),
            {
                "Housing": 32.0,
                "Food": 21.0,
                "Transport": 17.0,
                "Leisure": 12.0,
                "Utilities": 10.0,
                "Other": 8.0,
            },
        )
        self.assertLess(normalized.index("Housing | 32%"), normalized.index("Food | 21%"))

    def test_pie_normalization_rejects_an_incomplete_plot_extraction(self):
        incomplete = ISOLATED_PLOT_TEXT.replace("Other 8% | 8%<0x0A>", "")

        with self.assertRaisesRegex(InvalidExtractedChartData, "Other"):
            normalize_pie_deplot_text(FULL_DEPLOT_TEXT, incomplete)

    def test_pie_validation_rejects_a_non_100_percent_total(self):
        with self.assertRaisesRegex(InvalidExtractedChartData, "total is 90%"):
            parse_validated_pie_table(
                "CHART TYPE | Pie chart\nCategory | Percentage\nHousing | 60%\nOther | 30%"
            )

    def test_sample_pie_crop_excludes_title_and_legend(self):
        source = (
            Path(__file__).resolve().parents[2]
            / "test_samples"
            / "charts"
            / "04_pie_household_spending.png"
        )
        self.assertEqual(detect_chart_type(source), "pie")

        with Image.open(source) as image:
            cropped = crop_pie_plot(image)
            self.assertIsNotNone(cropped)
            assert cropped is not None
            self.assertLess(cropped.height, image.height)
            self.assertGreater(cropped.width, cropped.height)


if __name__ == "__main__":
    unittest.main()

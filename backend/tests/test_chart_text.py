import unittest
from pathlib import Path

from PIL import Image

from chart_detection import crop_pie_plot, detect_chart_type
from chart_text import (
    InvalidExtractedChartData,
    normalize_pie_deplot_text,
    parse_validated_pie_table,
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

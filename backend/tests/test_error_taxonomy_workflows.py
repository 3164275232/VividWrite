import unittest
from pathlib import Path

from chart_feedback import (
    _annotate_line_accuracy,
    _annotate_pie_accuracy,
    _merge_explicit_cartesian_values,
    _merge_explicit_pie_percentages,
    _remove_unsupported_cartesian_values,
)
from chart_text import parse_numeric_chart_table, parse_validated_pie_table
from error_taxonomy import attach_error_taxonomy


SAMPLES = Path(__file__).resolve().parents[2] / "test_samples" / "error_taxonomy"

LINE_TABLE = """Year | Bus | Rail | Metro
2010 | 1.8 | 1.1 | 0.8
2012 | 1.9 | 1.3 | 1.0
2014 | 1.7 | 1.5 | 1.2
2016 | 1.6 | 1.8 | 1.5
2018 | 1.5 | 2.0 | 1.7
2020 | 1.3 | 2.2 | 1.9"""

PIE_TABLE = """Category | Percentage
Housing | 32%
Food | 21%
Transport | 17%
Leisure | 12%
Utilities | 10%
Other | 8%"""


def analyse_line_sample(filename: str) -> dict:
    essay = (SAMPLES / "line" / filename).read_text(encoding="utf-8")
    records = [
        {
            "category": record["category"],
            "period": record["category"],
            "series": record["series"],
            "value": None,
            "missing": True,
            "confidence": 0.0,
        }
        for record in parse_numeric_chart_table(LINE_TABLE)
    ]
    result = {"chart_type": "line", "records": records, "comparison": {}}
    _merge_explicit_cartesian_values(result, LINE_TABLE, essay)
    _remove_unsupported_cartesian_values(result, LINE_TABLE, essay)
    _annotate_line_accuracy(result, LINE_TABLE)
    return attach_error_taxonomy(result, essay)


def analyse_pie_sample(filename: str) -> dict:
    essay = (SAMPLES / "pie" / filename).read_text(encoding="utf-8")
    records = [
        {
            "category": category,
            "value": None,
            "missing": True,
            "confidence": 0.0,
        }
        for category in parse_validated_pie_table(PIE_TABLE)
    ]
    result = {"chart_type": "pie", "records": records, "comparison": {}}
    _merge_explicit_pie_percentages(result, PIE_TABLE, essay)
    _annotate_pie_accuracy(result, PIE_TABLE)
    return attach_error_taxonomy(result, essay)


class ErrorTaxonomyWorkflowTests(unittest.TestCase):
    def test_line_samples_each_produce_only_the_intended_class(self):
        expected = {
            "01_value_inaccuracy.txt": "value_inaccuracy",
            "02_entity_misalignment.txt": "entity_misalignment",
            "03_trend_direction_error.txt": "trend_direction_error",
            "04_comparison_ranking_error.txt": "comparison_ranking_error",
            "05_key_feature_omission.txt": "key_feature_omission",
        }

        for filename, error_type in expected.items():
            with self.subTest(filename=filename):
                taxonomy = analyse_line_sample(filename)["error_taxonomy"]
                self.assertEqual(
                    [issue["error_type"] for issue in taxonomy["issues"]],
                    [error_type],
                )
                self.assertEqual(taxonomy["summary"]["applicable_checks"], 5)

    def test_pie_samples_cover_four_classes_and_trend_non_applicability(self):
        expected = {
            "01_value_inaccuracy.txt": "value_inaccuracy",
            "02_entity_misalignment.txt": "entity_misalignment",
            "04_comparison_ranking_error.txt": "comparison_ranking_error",
            "05_key_feature_omission.txt": "key_feature_omission",
        }

        for filename, error_type in expected.items():
            with self.subTest(filename=filename):
                taxonomy = analyse_pie_sample(filename)["error_taxonomy"]
                self.assertEqual(
                    [issue["error_type"] for issue in taxonomy["issues"]],
                    [error_type],
                )
                self.assertEqual(taxonomy["summary"]["applicable_checks"], 4)

        taxonomy = analyse_pie_sample("03_trend_not_applicable.txt")["error_taxonomy"]
        self.assertEqual(taxonomy["issues"], [])
        self.assertFalse(taxonomy["applicability"]["trend_direction_error"]["applicable"])
        self.assertEqual(taxonomy["summary"]["not_applicable_checks"], 1)


if __name__ == "__main__":
    unittest.main()

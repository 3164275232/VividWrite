import unittest

from error_taxonomy import ERROR_CODES, build_error_taxonomy, taxonomy_catalog


def chart_data(chart_type, records, tolerance=0.0):
    return {
        "chart_type": chart_type,
        "records": records,
        "comparison": {"accepted_value_tolerance": tolerance},
    }


PIE_VALUES = {
    "Housing": 32.0,
    "Food": 21.0,
    "Transport": 17.0,
    "Leisure": 12.0,
    "Utilities": 10.0,
    "Other": 8.0,
}

LINE_VALUES = {
    ("2010", "Bus"): 1.8,
    ("2010", "Rail"): 1.1,
    ("2010", "Metro"): 0.8,
    ("2020", "Bus"): 1.3,
    ("2020", "Rail"): 2.2,
    ("2020", "Metro"): 1.9,
}


def pie_records(overrides=None):
    overrides = overrides or {}
    records = []
    for category, official_value in PIE_VALUES.items():
        value = overrides.get(category, official_value)
        records.append(
            {
                "category": category,
                "value": value,
                "official_value": official_value,
                "feedback_status": (
                    "missing" if value is None else "correct" if value == official_value else "incorrect"
                ),
            }
        )
    return records


def line_records(overrides=None):
    overrides = overrides or {}
    records = []
    for (period, series), official_value in LINE_VALUES.items():
        value = overrides.get((period, series), official_value)
        records.append(
            {
                "category": period,
                "period": period,
                "series": series,
                "value": value,
                "official_value": official_value,
                "feedback_status": (
                    "missing" if value is None else "correct" if value == official_value else "incorrect"
                ),
            }
        )
    return records


class ErrorTaxonomyTests(unittest.TestCase):
    def test_catalog_exposes_exactly_five_stable_error_types(self):
        catalog = taxonomy_catalog()

        self.assertEqual(catalog["version"], "1.1")
        self.assertEqual(
            [definition["code"] for definition in catalog["definitions"]],
            list(ERROR_CODES),
        )
        self.assertEqual(len(catalog["definitions"]), 5)
        self.assertTrue(all(definition["verification_rule"] for definition in catalog["definitions"]))

    def test_value_inaccuracy_contains_reproducible_numeric_evidence(self):
        result = build_error_taxonomy(
            chart_data(
                "bar",
                [
                    {
                        "category": "Bristol",
                        "series": "2015",
                        "value": 47.0,
                        "official_value": 42.0,
                        "feedback_status": "incorrect",
                        "explicit_student_value": True,
                        "confidence": 1.0,
                    }
                ],
            ),
            "Bristol recorded 47% in 2015.",
        )

        issue = result["issues"][0]
        self.assertEqual(issue["error_type"], "value_inaccuracy")
        self.assertEqual(issue["student_claim"], {"value": 47.0})
        self.assertEqual(issue["official_fact"], {"value": 42.0})
        self.assertEqual(issue["verification"]["method"], "aligned_numeric_comparison")
        self.assertEqual(issue["evidence"]["source_sentences"], ["Bristol recorded 47% in 2015."])

    def test_reciprocal_value_swap_is_entity_misalignment_not_two_value_errors(self):
        records = [
            {
                "category": "Bristol",
                "series": "2015",
                "value": 35.0,
                "official_value": 42.0,
                "feedback_status": "incorrect",
            },
            {
                "category": "Leeds",
                "series": "2015",
                "value": 42.0,
                "official_value": 35.0,
                "feedback_status": "incorrect",
            },
        ]

        result = build_error_taxonomy(
            chart_data("bar", records),
            "In 2015, Bristol was 35%, while Leeds was 42%.",
        )

        self.assertEqual([issue["error_type"] for issue in result["issues"]], ["entity_misalignment"])
        self.assertEqual(result["issues"][0]["verification"]["method"], "reciprocal_value_swap")
        self.assertEqual(len(records[0]["taxonomy_issue_ids"]), 1)
        self.assertEqual(records[0]["taxonomy_issue_ids"], records[1]["taxonomy_issue_ids"])

    def test_explicit_trend_claim_is_checked_against_official_endpoints(self):
        result = build_error_taxonomy(
            chart_data(
                "line",
                [
                    {
                        "category": "2010",
                        "period": "2010",
                        "series": "Bus",
                        "value": 10.0,
                        "official_value": 10.0,
                        "feedback_status": "correct",
                    },
                    {
                        "category": "2020",
                        "period": "2020",
                        "series": "Bus",
                        "value": 20.0,
                        "official_value": 20.0,
                        "feedback_status": "correct",
                    },
                ],
            ),
            "Bus use decreased steadily over the period.",
        )

        issue = next(issue for issue in result["issues"] if issue["error_type"] == "trend_direction_error")
        self.assertEqual(issue["student_claim"]["direction"], "decrease")
        self.assertEqual(issue["official_fact"]["direction"], "increase")
        self.assertEqual(issue["official_fact"]["start_value"], 10.0)
        self.assertEqual(issue["official_fact"]["end_value"], 20.0)

    def test_trend_claim_resolves_an_unambiguous_cross_sentence_pronoun(self):
        result = build_error_taxonomy(
            chart_data(
                "bar",
                [
                    {
                        "category": "Manchester",
                        "series": "2015",
                        "value": 50.0,
                        "official_value": 31.0,
                        "feedback_status": "incorrect",
                    },
                    {
                        "category": "Manchester",
                        "series": "2020",
                        "value": 46.0,
                        "official_value": 46.0,
                        "feedback_status": "correct",
                    },
                ],
            ),
            "Manchester followed a different pattern. Its rate decreased from 50 to 46.",
        )

        issue = next(issue for issue in result["issues"] if issue["error_type"] == "trend_direction_error")
        self.assertEqual(
            issue["evidence"]["source_sentences"],
            [
                "Manchester followed a different pattern.",
                "Its rate decreased from 50 to 46.",
            ],
        )

    def test_explicit_superlative_is_checked_in_the_same_period(self):
        result = build_error_taxonomy(
            chart_data(
                "line",
                [
                    {
                        "category": "2020",
                        "period": "2020",
                        "series": "Bus",
                        "value": 20.0,
                        "official_value": 20.0,
                        "feedback_status": "correct",
                    },
                    {
                        "category": "2020",
                        "period": "2020",
                        "series": "Rail",
                        "value": 10.0,
                        "official_value": 10.0,
                        "feedback_status": "correct",
                    },
                ],
            ),
            "In 2020, Rail was the highest mode.",
        )

        issue = next(issue for issue in result["issues"] if issue["error_type"] == "comparison_ranking_error")
        self.assertEqual(issue["student_claim"]["entity"], "Rail")
        self.assertEqual(issue["official_fact"]["entities"], ["Bus"])
        self.assertEqual(issue["verification"]["method"], "official_context_ranking")

    def test_nearest_rank_word_is_assigned_to_each_pie_category(self):
        result = build_error_taxonomy(
            chart_data("pie", pie_records()),
            (
                "Overall, housing formed the largest share of spending and other expenses "
                "the smallest. Housing was 32%, food 21%, transport 17%, leisure 12%, "
                "utilities 10%, and other spending 8%."
            ),
        )

        ranking_issues = [
            issue for issue in result["issues"]
            if issue["error_type"] == "comparison_ranking_error"
        ]
        self.assertEqual(ranking_issues, [])

    def test_least_is_assigned_to_the_nearest_pie_category(self):
        result = build_error_taxonomy(
            chart_data("pie", pie_records()),
            (
                "Overall, housing occupied the greatest proportion and other costs the least. "
                "Housing was 32%, food 21%, transport 17%, leisure 12%, utilities 10%, "
                "and other spending 8%."
            ),
        )

        ranking_issues = [
            issue for issue in result["issues"]
            if issue["error_type"] == "comparison_ranking_error"
        ]
        self.assertEqual(ranking_issues, [])

    def test_grouped_smallest_categories_do_not_claim_a_unique_minimum(self):
        result = build_error_taxonomy(
            chart_data("pie", pie_records()),
            (
                "Overall, housing was the largest category, while utilities and other spending "
                "made up the two smallest portions. Housing was 32%, food 21%, transport 17%, "
                "leisure 12%, utilities 10%, and other spending 8%."
            ),
        )

        ranking_issues = [
            issue for issue in result["issues"]
            if issue["error_type"] == "comparison_ranking_error"
        ]
        self.assertEqual(ranking_issues, [])

    def test_complete_entity_absence_is_a_key_feature_omission(self):
        result = build_error_taxonomy(
            chart_data(
                "line",
                [
                    {
                        "category": "2010",
                        "period": "2010",
                        "series": "Bus",
                        "value": 10.0,
                        "official_value": 10.0,
                        "feedback_status": "correct",
                    },
                    {
                        "category": "2020",
                        "period": "2020",
                        "series": "Bus",
                        "value": 20.0,
                        "official_value": 20.0,
                        "feedback_status": "correct",
                    },
                    {
                        "category": "2010",
                        "period": "2010",
                        "series": "Rail",
                        "value": None,
                        "official_value": 12.0,
                        "feedback_status": "unmentioned",
                    },
                    {
                        "category": "2020",
                        "period": "2020",
                        "series": "Rail",
                        "value": None,
                        "official_value": 16.0,
                        "feedback_status": "unmentioned",
                    },
                ],
            ),
            "Bus increased from 10 to 20.",
        )

        omissions = [
            issue for issue in result["issues"] if issue["error_type"] == "key_feature_omission"
        ]
        self.assertEqual(len(omissions), 1)
        self.assertEqual(omissions[0]["item"], "Rail")
        self.assertEqual(omissions[0]["verification"]["method"], "complete_entity_coverage_check")

    def test_clean_chart_still_reports_zero_counts_for_all_five_types(self):
        result = build_error_taxonomy(
            chart_data(
                "pie",
                [
                    {
                        "category": "Housing",
                        "value": 60.0,
                        "official_value": 60.0,
                        "feedback_status": "correct",
                    },
                    {
                        "category": "Food",
                        "value": 40.0,
                        "official_value": 40.0,
                        "feedback_status": "correct",
                    },
                ],
            ),
            "Housing accounted for 60%, while food made up 40%.",
        )

        self.assertEqual(result["issues"], [])
        self.assertEqual(result["summary"]["total_issues"], 0)
        self.assertEqual(result["summary"]["counts"], {code: 0 for code in ERROR_CODES})
        self.assertEqual(result["summary"]["applicable_checks"], 4)
        self.assertFalse(result["applicability"]["trend_direction_error"]["applicable"])

    def test_line_chart_supports_all_five_error_classes_independently(self):
        cases = {
            "value_inaccuracy": (
                line_records({("2010", "Bus"): 2.0}),
                "Bus carried 2.0 million passengers in 2010 and 1.3 million in 2020. "
                "Rail recorded 1.1 and 2.2 million, while Metro recorded 0.8 and 1.9 million.",
            ),
            "entity_misalignment": (
                line_records({("2010", "Bus"): 1.1, ("2010", "Rail"): 1.8}),
                "In 2010, Bus carried 1.1 million passengers and Rail carried 1.8 million. "
                "By 2020, their figures were 1.3 and 2.2 million respectively. "
                "Metro recorded 0.8 million in 2010 and 1.9 million in 2020.",
            ),
            "trend_direction_error": (
                line_records(),
                "Bus increased from 1.8 million passengers in 2010 to 1.3 million in 2020. "
                "Rail rose from 1.1 to 2.2 million, while Metro grew from 0.8 to 1.9 million.",
            ),
            "comparison_ranking_error": (
                line_records(),
                "In 2010, Bus, Rail and Metro recorded 1.8, 1.1 and 0.8 million passengers. "
                "In 2020, their figures were 1.3, 2.2 and 1.9 million respectively, and Metro was the highest mode.",
            ),
            "key_feature_omission": (
                line_records({("2010", "Metro"): None, ("2020", "Metro"): None}),
                "Bus recorded 1.8 million passengers in 2010 and 1.3 million in 2020. "
                "Rail moved from 1.1 million to 2.2 million over the same period.",
            ),
        }

        for expected_code, (records, essay) in cases.items():
            with self.subTest(expected_code=expected_code):
                result = build_error_taxonomy(chart_data("line", records), essay)
                self.assertEqual(
                    [issue["error_type"] for issue in result["issues"]],
                    [expected_code],
                )
                self.assertEqual(result["summary"]["applicable_checks"], 5)
                self.assertTrue(
                    all(item["applicable"] for item in result["applicability"].values())
                )

    def test_single_period_pie_supports_four_classes_and_marks_trend_not_applicable(self):
        cases = {
            "value_inaccuracy": (
                pie_records({"Utilities": 14.0}),
                "Housing accounted for 32%, food 21%, transport 17%, leisure 12%, "
                "utilities 14%, and other spending 8%.",
            ),
            "entity_misalignment": (
                pie_records({"Food": 17.0, "Transport": 21.0}),
                "Housing accounted for 32%, food 17%, transport 21%, leisure 12%, "
                "utilities 10%, and other spending 8%.",
            ),
            "comparison_ranking_error": (
                pie_records(),
                "Food was the largest category at 21%. Housing accounted for 32%, transport 17%, "
                "leisure 12%, utilities 10%, and other spending 8%.",
            ),
            "key_feature_omission": (
                pie_records({"Other": None}),
                "Housing accounted for 32%, food 21%, transport 17%, leisure 12%, and utilities 10%.",
            ),
        }

        for expected_code, (records, essay) in cases.items():
            with self.subTest(expected_code=expected_code):
                result = build_error_taxonomy(chart_data("pie", records), essay)
                self.assertEqual(
                    [issue["error_type"] for issue in result["issues"]],
                    [expected_code],
                )
                self.assertEqual(result["summary"]["applicable_checks"], 4)
                trend = result["applicability"]["trend_direction_error"]
                self.assertFalse(trend["applicable"])
                self.assertIn("no temporal endpoints", trend["reason"])

    def test_comparative_pie_records_enable_trend_verification(self):
        records = [
            {
                "category": "Housing",
                "series": "2020",
                "value": 30.0,
                "official_value": 30.0,
                "feedback_status": "correct",
            },
            {
                "category": "Housing",
                "series": "2024",
                "value": 32.0,
                "official_value": 32.0,
                "feedback_status": "correct",
            },
            {
                "category": "Food",
                "series": "2020",
                "value": 25.0,
                "official_value": 25.0,
                "feedback_status": "correct",
            },
            {
                "category": "Food",
                "series": "2024",
                "value": 21.0,
                "official_value": 21.0,
                "feedback_status": "correct",
            },
        ]

        result = build_error_taxonomy(
            chart_data("pie", records),
            "Housing decreased from 30% in 2020 to 32% in 2024, while food fell from 25% to 21%.",
        )

        self.assertTrue(result["applicability"]["trend_direction_error"]["applicable"])
        self.assertEqual(result["summary"]["applicable_checks"], 5)
        self.assertEqual(
            [issue["error_type"] for issue in result["issues"]],
            ["trend_direction_error"],
        )


if __name__ == "__main__":
    unittest.main()

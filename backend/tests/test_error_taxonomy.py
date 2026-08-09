import unittest

from error_taxonomy import ERROR_CODES, build_error_taxonomy, taxonomy_catalog


def chart_data(chart_type, records, tolerance=0.0):
    return {
        "chart_type": chart_type,
        "records": records,
        "comparison": {"accepted_value_tolerance": tolerance},
    }


class ErrorTaxonomyTests(unittest.TestCase):
    def test_catalog_exposes_exactly_five_stable_error_types(self):
        catalog = taxonomy_catalog()

        self.assertEqual(catalog["version"], "1.0")
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


if __name__ == "__main__":
    unittest.main()

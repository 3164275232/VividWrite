import tempfile
import unittest
from pathlib import Path

from PIL import Image

from move_feedback import MOVE_CODES, build_move_feedback, move_catalog
from move_visual_feedback import CURRENT_COLOR, RECOMMENDED_COLOR, render_move_visuals


def line_chart_data():
    return {
        "chart_type": "line",
        "records": [
            {"period": "2010", "series": "North", "value": 10, "official_value": 10},
            {"period": "2020", "series": "North", "value": 30, "official_value": 30},
            {"period": "2010", "series": "South", "value": 18, "official_value": 18},
            {"period": "2020", "series": "South", "value": 16, "official_value": 16},
        ],
    }


def pie_chart_data():
    return {
        "chart_type": "pie",
        "records": [
            {"category": label, "value": value, "official_value": value}
            for label, value in (
                ("Housing", 32),
                ("Food", 21),
                ("Transport", 17),
                ("Leisure", 12),
                ("Utilities", 10),
                ("Other", 8),
            )
        ],
    }


class MoveFeedbackTests(unittest.TestCase):
    def test_move_1_rejects_a_generic_visual_introduction(self):
        essay = "The supplied graphic contains six different shares."
        feedback = build_move_feedback(
            pie_chart_data(),
            essay,
            [{
                "code": "move_1_introducing_topic",
                "status": "effective",
                "excerpt": essay,
            }],
        )

        assessment = feedback["assessments"][0]
        self.assertEqual(assessment["status"], "developing")
        self.assertEqual(assessment["excerpt"], essay)

    def test_move_2_rejects_an_overview_that_only_lists_values(self):
        essay = "Overall, housing represented 32% and food 21%, while transport accounted for 17%."
        feedback = build_move_feedback(
            pie_chart_data(),
            essay,
            [{
                "code": "move_2_stating_overview",
                "status": "effective",
                "excerpt": essay,
            }],
        )

        assessment = feedback["assessments"][1]
        self.assertEqual(assessment["status"], "developing")
        self.assertTrue(assessment["visual_available"])
        self.assertTrue(assessment["visual_targets"]["current_focus_record_indices"])
        self.assertTrue(assessment["visual_targets"]["recommended_record_indices"])

    def test_move_4_requires_evidence_for_the_prioritised_entity(self):
        essay = (
            "The line chart compares North and South from 2010 to 2020. "
            "The main trend was North's strong growth. North rose markedly. "
            "South changed from 18 to 16."
        )
        feedback = build_move_feedback(
            line_chart_data(),
            essay,
            [{
                "code": "move_4_elaborating_key_trends",
                "status": "effective",
                "excerpt": "North rose markedly.",
                "rationale": "The model treated a qualitative restatement as elaboration.",
            }],
        )

        assessment = feedback["assessments"][3]
        self.assertEqual(assessment["status"], "developing")
        self.assertIn("North", assessment["excerpt"])
        self.assertEqual(
            essay[assessment["range"]["start"]:assessment["range"]["end"]],
            assessment["excerpt"],
        )

    def test_move_5_rejects_evidence_from_a_different_entity(self):
        essay = "North showed the main growth, supported by South falling from 18 to 16."
        feedback = build_move_feedback(
            line_chart_data(),
            essay,
            [{
                "code": "move_5_integrating_trend_and_detail",
                "status": "effective",
                "excerpt": essay,
                "rationale": "The model accepted the support link.",
            }],
        )

        assessment = feedback["assessments"][4]
        self.assertEqual(assessment["status"], "developing")
        self.assertEqual(
            assessment["visual_targets"]["current_focus_record_indices"],
            [2, 3],
        )
        self.assertEqual(
            assessment["visual_targets"]["recommended_record_indices"],
            [0, 1],
        )

    def test_move_6_rejects_an_unspecified_comparison(self):
        essay = "The two regions can be compared, and some figures were higher than others."
        feedback = build_move_feedback(
            line_chart_data(),
            essay,
            [{
                "code": "move_6_comparing_contrasting",
                "status": "effective",
                "excerpt": essay,
            }],
        )

        assessment = feedback["assessments"][5]
        self.assertEqual(assessment["status"], "developing")
        self.assertIn("unspecified", assessment["rationale"])

    def test_move_7_reviews_a_weak_conclusion_that_is_present(self):
        essay = (
            "The chart compares North and South. "
            "In conclusion, the graph contains two lines and the figures were described above."
        )
        feedback = build_move_feedback(
            line_chart_data(),
            essay,
            [{
                "code": "move_7_closing_summary",
                "status": "not_applicable",
                "excerpt": "",
            }],
        )

        assessment = feedback["assessments"][6]
        self.assertEqual(assessment["status"], "developing")
        self.assertTrue(assessment["excerpt"].startswith("In conclusion"))

    def test_catalog_exposes_seven_moves_in_documented_order(self):
        catalog = move_catalog()

        self.assertEqual(len(catalog["definitions"]), 7)
        self.assertEqual(
            tuple(item["code"] for item in catalog["definitions"]),
            MOVE_CODES,
        )
        visual_moves = [
            item["number"]
            for item in catalog["definitions"]
            if item["feedback_mode"] == "textual_visual"
        ]
        self.assertEqual(visual_moves, [2, 3, 5])

    def test_model_excerpt_is_mapped_to_an_exact_editor_range(self):
        essay = (
            "The chart compares two regions from 2010 to 2020. "
            "Overall, North rose substantially while South changed only slightly."
        )
        excerpt = "Overall, North rose substantially while South changed only slightly."
        feedback = build_move_feedback(
            line_chart_data(),
            essay,
            [{
                "code": "move_2_stating_overview",
                "status": "developing",
                "excerpt": excerpt,
                "rationale": "The overview identifies directions but not the most notable scale of change.",
                "hint": "Prioritise the dominant movement before the smaller change.",
            }],
        )

        assessment = feedback["assessments"][1]
        self.assertEqual(assessment["status"], "developing")
        self.assertEqual(essay[assessment["range"]["start"]:assessment["range"]["end"]], excerpt)
        self.assertNotIn("replacement", assessment)
        self.assertEqual(feedback["summary"]["attention_count"], 1)

    def test_hallucinated_excerpt_is_not_allowed_to_highlight_unrelated_text(self):
        feedback = build_move_feedback(
            line_chart_data(),
            "The chart compares two regions.",
            [{
                "code": "move_3_highlighting_key_trends",
                "status": "developing",
                "excerpt": "North doubled across the period.",
                "hint": "Focus on the dominant change.",
            }],
        )

        assessment = feedback["assessments"][2]
        self.assertEqual(assessment["status"], "not_detected")
        self.assertIsNone(assessment["range"])

    def test_model_visual_selectors_are_resolved_against_unseen_record_labels(self):
        essay = "The South figure changed from 18 to 16."
        feedback = build_move_feedback(
            line_chart_data(),
            essay,
            [{
                "code": "move_3_highlighting_key_trends",
                "status": "developing",
                "excerpt": essay,
                "visual_focus": {
                    "current": [{"series": "South", "period": "2020"}],
                    "recommended": [
                        {"series": "North", "period": "2010"},
                        {"series": "North", "period": "2020"},
                    ],
                },
            }],
        )

        targets = feedback["assessments"][2]["visual_targets"]
        self.assertEqual(targets["current_focus_record_indices"], [3])
        self.assertEqual(targets["recommended_record_indices"], [0, 1])

    def test_visual_fallback_maps_a_relationship_value_to_named_entities(self):
        essay = "The main feature was the 2-point gap between North and South in 2020."
        feedback = build_move_feedback(
            line_chart_data(),
            essay,
            [{
                "code": "move_3_highlighting_key_trends",
                "status": "developing",
                "excerpt": essay,
                "visual_focus": {
                    "recommended": [
                        {"series": "North", "period": "2010"},
                        {"series": "North", "period": "2020"},
                    ],
                },
            }],
        )

        targets = feedback["assessments"][2]["visual_targets"]
        self.assertEqual(targets["current_focus_record_indices"], [1, 3])
        self.assertEqual(targets["recommended_record_indices"], [0, 1])

    def test_missing_optional_conclusion_is_not_counted_as_an_error(self):
        feedback = build_move_feedback(
            line_chart_data(),
            "The chart compares North and South.",
            [{
                "code": "move_7_closing_summary",
                "status": "not_applicable",
                "excerpt": "",
                "rationale": "A separate conclusion is unnecessary here.",
                "hint": "",
            }],
        )

        assessment = feedback["assessments"][6]
        self.assertEqual(assessment["status"], "not_applicable")
        self.assertEqual(feedback["summary"]["attention_count"], 0)

    def test_visual_renderer_marks_current_and_suggested_features_on_a_copy(self):
        essay = "The South figure changed from 18 to 16."
        chart_data = line_chart_data()
        chart_data["move_feedback"] = build_move_feedback(
            chart_data,
            essay,
            [{
                "code": "move_3_highlighting_key_trends",
                "status": "developing",
                "excerpt": essay,
                "visual_focus": {
                    "current": [{"series": "South", "period": "2020"}],
                    "recommended": [
                        {"series": "North", "period": "2010"},
                        {"series": "North", "period": "2020"},
                    ],
                },
            }],
        )

        with tempfile.TemporaryDirectory() as folder:
            source_path = Path(folder) / "source.png"
            Image.new("RGB", (800, 500), "white").save(source_path)
            render_move_visuals(source_path, folder, chart_data)

            assessment = chart_data["move_feedback"]["assessments"][2]
            output_path = Path(folder) / assessment["visual"]["image_filename"]
            self.assertTrue(output_path.exists())
            with Image.open(output_path) as rendered:
                self.assertGreater(rendered.height, 500)
                colours = rendered.convert("RGB").getcolors(maxcolors=2_000_000)
            colour_set = {colour for _, colour in colours}
            self.assertIn(tuple(int(CURRENT_COLOR[index:index + 2], 16) for index in (1, 3, 5)), colour_set)
            self.assertIn(tuple(int(RECOMMENDED_COLOR[index:index + 2], 16) for index in (1, 3, 5)), colour_set)
            self.assertEqual(assessment["visual"]["current_focus_labels"][0], "South · 2020 · 16")


if __name__ == "__main__":
    unittest.main()

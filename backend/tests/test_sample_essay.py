import unittest
from types import SimpleNamespace
from unittest.mock import patch

from sample_essay import SampleEssayRequest, generate_sample_essay


OPTION_C_NODES = [
    {"type": "introduction"},
    {"type": "overview"},
    {"type": "key_details_a"},
    {"type": "key_details_b"},
]


class SampleEssayTests(unittest.TestCase):
    @patch("sample_essay.get_deepseek_api_key", return_value="test-key")
    def test_line_prompt_names_the_original_visual_instead_of_the_internal_table(self, _key):
        captured = {}

        class Completions:
            def create(self, **kwargs):
                captured.update(kwargs)
                message = SimpleNamespace(content="The line graph compares public transport use over time.")
                return SimpleNamespace(choices=[SimpleNamespace(message=message)])

        client = SimpleNamespace(chat=SimpleNamespace(completions=Completions()))
        request = SampleEssayRequest(
            chart_type="line",
            min_words=1,
            deplot_text=(
                "TITLE | Passengers<0x0A>CHART TYPE | Line graph<0x0A>"
                "Year | Bus | Rail<0x0A>2010 | 1.8 | 1.1<0x0A>2020 | 1.3 | 2.2"
            ),
            flowchart={
                "nodes": OPTION_C_NODES,
                "edges": [],
            },
        )

        with patch("sample_essay.get_deepseek_client", return_value=client):
            response = generate_sample_essay(request)

        self.assertTrue(response.success, response.error)
        self.assertEqual(captured["temperature"], 0.2)
        self.assertIn("never as a table", captured["messages"][0]["content"])
        self.assertIn("ORIGINAL VISUAL TYPE:\nLine graph", captured["messages"][1]["content"])
        self.assertIn("2020 ranking: Rail (2.2) > Bus (1.3)", captured["messages"][1]["content"])
        self.assertIn("2010 | 1.8 | 1.1", captured["messages"][1]["content"])
        self.assertIn("retain up to 1 decimal place", captured["messages"][0]["content"])
        self.assertIn("Rail overtakes Bus", captured["messages"][1]["content"])
        self.assertIn("Introduction", captured["messages"][0]["content"])
        self.assertIn("Overview", captured["messages"][0]["content"])
        self.assertIn("Key Details A", captured["messages"][0]["content"])
        self.assertIn("Do not generate an independent conclusion", captured["messages"][0]["content"])
        self.assertNotIn("Background", captured["messages"][0]["content"])
        self.assertTrue(response.debug["structure_check"]["all_required_present"])
        self.assertFalse(response.debug["structure_check"]["optional_commentary"])

    @patch("sample_essay.get_deepseek_client")
    @patch("sample_essay.get_deepseek_api_key", return_value="test-key")
    def test_missing_overview_requests_option_c_structure_choice(self, _key, client):
        response = generate_sample_essay(
            SampleEssayRequest(
                chart_type="bar",
                deplot_text="City | 2010 | 2020<0x0A>A | 10 | 20",
                flowchart={
                    "nodes": [
                        {"type": "introduction"},
                        {"type": "key_details_a"},
                        {"type": "key_details_b"},
                        {"type": "optional_commentary"},
                    ],
                    "edges": [],
                },
            )
        )

        self.assertFalse(response.success)
        self.assertTrue(response.requires_choice)
        self.assertIn(
            "Overview / Highlight Key Patterns",
            response.choice_info["missing_structures"],
        )
        client.assert_not_called()

    @patch("sample_essay.get_deepseek_api_key", return_value="test-key")
    def test_small_scale_sample_essay_keeps_one_decimal_place(self, _key):
        class Completions:
            def create(self, **kwargs):
                return SimpleNamespace(
                    choices=[
                        SimpleNamespace(
                            message=SimpleNamespace(
                                content="Bus use fell from 1.80 million to 1.26 million."
                            )
                        )
                    ]
                )

        client = SimpleNamespace(chat=SimpleNamespace(completions=Completions()))
        request = SampleEssayRequest(
            chart_type="line",
            min_words=1,
            deplot_text=(
                "TITLE | Passengers<0x0A>CHART TYPE | Line graph<0x0A>"
                "Year | Bus<0x0A>2010 | 1.8<0x0A>2020 | 1.3"
            ),
            flowchart={
                "nodes": OPTION_C_NODES,
                "edges": [],
            },
        )

        with patch("sample_essay.get_deepseek_client", return_value=client):
            response = generate_sample_essay(request)

        self.assertTrue(response.success, response.error)
        self.assertEqual(response.essay, "Bus use fell from 1.8 million to 1.3 million.")

    @patch("sample_essay.get_deepseek_api_key", return_value="test-key")
    def test_sample_essay_data_values_are_returned_as_integers(self, _key):
        captured = {}

        class Completions:
            def create(self, **kwargs):
                captured.update(kwargs)
                return SimpleNamespace(
                    choices=[
                        SimpleNamespace(
                            message=SimpleNamespace(
                                content="Bristol recorded 41.70%, while Leeds reached 48.16%."
                            )
                        )
                    ]
                )

        client = SimpleNamespace(chat=SimpleNamespace(completions=Completions()))
        request = SampleEssayRequest(
            chart_type="bar",
            min_words=1,
            deplot_text=(
                "TITLE | Recycling<0x0A>CHART TYPE | Bar chart<0x0A>"
                "City | 2015 | 2020<0x0A>Bristol | 41.70 | 55.20<0x0A>"
                "Leeds | 35.26 | 48.16"
            ),
            flowchart={
                "nodes": OPTION_C_NODES,
                "edges": [],
            },
        )

        with patch("sample_essay.get_deepseek_client", return_value=client):
            response = generate_sample_essay(request)

        self.assertTrue(response.success)
        self.assertEqual(response.essay, "Bristol recorded 42%, while Leeds reached 48%.")
        self.assertIn("Bristol | 42 | 55", captured["messages"][1]["content"])
        self.assertIn("Leeds | 35 | 48", captured["messages"][1]["content"])

    @patch("sample_essay.get_deepseek_client")
    @patch("sample_essay.get_deepseek_api_key", return_value="test-key")
    def test_invalid_pie_data_is_rejected_before_calling_deepseek(self, _key, client):
        response = generate_sample_essay(
            SampleEssayRequest(
                chart_type="pie",
                deplot_text=(
                    "TITLE | Spending<0x0A>Category | Percentage<0x0A>"
                    "Housing | 32%<0x0A>Food | 8%<0x0A>Other | 8%"
                ),
                flowchart={
                    "nodes": OPTION_C_NODES,
                    "edges": [],
                },
            )
        )

        self.assertFalse(response.success)
        self.assertIn("expected about 100%", response.error or "")
        client.assert_not_called()

    @patch("sample_essay.get_deepseek_api_key", return_value="test-key")
    def test_false_line_comparisons_trigger_one_automatic_rewrite(self, _key):
        drafts = [
            (
                "The graph covers an eleven-year period from 2010 to 2020. "
                "Overall, bus usage experienced a consistent decline. "
                "In 2016, rail equalled bus usage."
            ),
            (
                "Bus usage rose initially and then declined, while rail increased throughout. "
                "In 2016, rail carried 1.8 million passengers, exceeding the bus figure of 1.6 million."
            ),
        ]

        class Completions:
            def __init__(self):
                self.call_count = 0
                self.calls = []

            def create(self, **kwargs):
                self.calls.append(kwargs)
                content = drafts[min(self.call_count, len(drafts) - 1)]
                self.call_count += 1
                return SimpleNamespace(
                    choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
                )

        completions = Completions()
        client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
        request = SampleEssayRequest(
            chart_type="line",
            min_words=1,
            deplot_text=(
                "TITLE | Passengers<0x0A>CHART TYPE | Line graph<0x0A>"
                "Year | Bus | Rail<0x0A>2010 | 1.8 | 1.1<0x0A>2012 | 1.9 | 1.3<0x0A>"
                "2014 | 1.7 | 1.5<0x0A>2016 | 1.2 | 1.8<0x0A>"
                "2018 | 1.5 | 2.0<0x0A>2020 | 1.3 | 2.2"
            ),
            flowchart={
                "nodes": OPTION_C_NODES,
                "edges": [],
            },
        )

        with patch("sample_essay.get_deepseek_client", return_value=client):
            response = generate_sample_essay(request)

        self.assertTrue(response.success)
        self.assertEqual(completions.call_count, 2)
        self.assertIn("exceeding the bus figure", response.essay or "")
        self.assertIn("equality claim for 2016 is false", completions.calls[1]["messages"][1]["content"])
        self.assertIn("is 10 years, not 11 years", completions.calls[1]["messages"][1]["content"])
        self.assertEqual((response.debug or {}).get("fact_validation_attempts"), 2)

    @patch("sample_essay.get_deepseek_api_key", return_value="test-key")
    def test_repeated_false_monotonic_wording_gets_a_safe_local_fallback(self, _key):
        drafts = [
            "Overall, bus usage experienced a consistent decline across the period.",
            "Overall, bus usage experienced a consistent decline across the period.",
        ]

        class Completions:
            def __init__(self):
                self.call_count = 0

            def create(self, **kwargs):
                content = drafts[min(self.call_count, len(drafts) - 1)]
                self.call_count += 1
                return SimpleNamespace(
                    choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
                )

        completions = Completions()
        client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
        request = SampleEssayRequest(
            chart_type="line",
            min_words=1,
            deplot_text=(
                "TITLE | Passengers<0x0A>CHART TYPE | Line graph<0x0A>"
                "Year | Bus | Rail<0x0A>2010 | 1.8 | 1.1<0x0A>"
                "2012 | 1.9 | 1.3<0x0A>2020 | 1.3 | 2.2"
            ),
            flowchart={
                "nodes": OPTION_C_NODES,
                "edges": [],
            },
        )

        with patch("sample_essay.get_deepseek_client", return_value=client):
            response = generate_sample_essay(request)

        self.assertTrue(response.success, response.error)
        self.assertEqual(completions.call_count, 2)
        self.assertIn("overall decline", response.essay or "")
        self.assertNotIn("consistent decline", response.essay or "")


if __name__ == "__main__":
    unittest.main()

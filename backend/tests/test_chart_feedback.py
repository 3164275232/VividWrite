import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from PIL import Image, ImageDraw

from chart_detection import detect_chart_type
from chart_feedback import (
    ChartFeedbackService,
    _annotate_bar_accuracy,
    _annotate_line_accuracy,
    _annotate_pie_accuracy,
    _collect_explicit_cartesian_values,
    _normalise_result,
)
from chart_renderer import InvalidChartSpec, extract_image_palette, prepare_vega_lite_spec


def _model_payload(chart_type="bar"):
    return {
        "schema_version": "1.0",
        "chart_type": chart_type,
        "title": "Telephone calls described by the student",
        "axes": {"x_label": "Year", "y_label": "Minutes", "unit": "billions"},
        "records": [
            {
                "category": "2001",
                "series": "Local",
                "period": "2001",
                "region": None,
                "value": "72 billion",
                "x": None,
                "y": None,
                "estimated": False,
                "missing": False,
                "confidence": 0.98,
            },
            {
                "category": "2002",
                "series": "Local",
                "period": "2002",
                "region": None,
                "value": None,
                "x": None,
                "y": None,
                "estimated": False,
                "missing": True,
                "confidence": 1.4,
            },
        ],
        "comparison": {
            "omitted_official_items": ["Local calls in 2002"],
            "uncertain_items": [],
            "alignment_notes": ["local fixed line -> Local"],
        },
        "vega_lite_spec": {
            "data": {"values": []},
            "mark": "bar",
            "encoding": {
                "x": {"field": "category", "type": "ordinal", "title": "Year"},
                "y": {"field": "value", "type": "quantitative", "title": "Minutes"},
                "color": {"field": "series", "type": "nominal"},
            },
        },
    }


class FakeCompletions:
    def __init__(self, payload):
        self.payload = payload
        self.kwargs = None
        self.call_count = 0

    def create(self, **kwargs):
        self.call_count += 1
        self.kwargs = kwargs
        message = SimpleNamespace(content=json.dumps(self.payload))
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


class FakeClient:
    def __init__(self, payload):
        self.completions = FakeCompletions(payload)
        self.chat = SimpleNamespace(completions=self.completions)


class SequenceCompletions(FakeCompletions):
    def __init__(self, payloads):
        super().__init__(payloads[0])
        self.payloads = payloads

    def create(self, **kwargs):
        payload = self.payloads[min(self.call_count, len(self.payloads) - 1)]
        self.payload = payload
        return super().create(**kwargs)


class SequenceClient:
    def __init__(self, payloads):
        self.completions = SequenceCompletions(payloads)
        self.chat = SimpleNamespace(completions=self.completions)


class UnifiedChartFeedbackTests(unittest.TestCase):
    def test_aligns_started_and_reached_values_without_treating_change_as_endpoint(self):
        official_records = [
            {"category": "Manchester", "series": "2015"},
            {"category": "Manchester", "series": "2020"},
        ]

        claims = _collect_explicit_cartesian_values(
            "Manchester started at 31% and reached 46% by 2020, giving it "
            "the largest increase among the cities discussed, at 15 percentage points.",
            official_records,
        )

        self.assertEqual(claims, {("Manchester", "2015"): [31.0], ("Manchester", "2020"): [46.0]})

    def test_normalises_long_form_records(self):
        result = _normalise_result(_model_payload(), "auto")
        self.assertEqual(result["records"][0]["value"], 72.0)
        self.assertTrue(result["records"][1]["missing"])
        self.assertEqual(result["records"][1]["confidence"], 1.0)

    def test_service_renders_png_without_chart_specific_python(self):
        client = FakeClient(_model_payload())
        with tempfile.TemporaryDirectory() as folder:
            result, filename = ChartFeedbackService(folder, client=client).generate(
                chart_type="auto",
                requirement="Summarise the chart.",
                student_answer="Local calls were 72 billion minutes in 2001.",
                deplot_text="TITLE | Calls<0x0A>Year | Local<0x0A>2001 | 72<0x0A>2002 | 75",
            )
            output = Path(folder) / filename
            self.assertTrue(output.exists())
            self.assertGreater(output.stat().st_size, 1000)
            self.assertEqual(result["chart_type"], "bar")
            self.assertEqual(result["schema_version"], "1.1")
            self.assertEqual(len(result["error_taxonomy"]["definitions"]), 5)
            self.assertIn("issues", result["error_taxonomy"])
            self.assertEqual(client.completions.kwargs["response_format"], {"type": "json_object"})

    def test_rejects_external_chart_data(self):
        spec = _model_payload()["vega_lite_spec"]
        spec["data"] = {"url": "https://example.com/data.json"}
        with self.assertRaises(InvalidChartSpec):
            prepare_vega_lite_spec(spec, _model_payload()["records"], "Unsafe")

    def test_color_domain_preserves_series_order(self):
        payload = _model_payload()
        payload["records"] = [
            {"category": "2001", "series": series, "value": value}
            for series, value in (("Local", 72), ("National", 38), ("Mobile", 3))
        ]
        prepared = prepare_vega_lite_spec(
            payload["vega_lite_spec"],
            payload["records"],
            "Calls",
            ["#1f77b4", "#ff7f0e", "#2ca02c"],
        )

        color = prepared["encoding"]["color"]
        self.assertEqual(color["scale"]["domain"], ["Local", "National", "Mobile"])
        self.assertEqual(color["scale"]["range"], ["#1f77b4", "#ff7f0e", "#2ca02c"])
        self.assertEqual(prepared["encoding"]["x"]["axis"]["labelAngle"], 0)

    def test_renderer_uses_installed_font_and_visible_guide_text(self):
        payload = _model_payload()
        payload["vega_lite_spec"]["config"] = {"font": "Arial"}
        payload["vega_lite_spec"]["encoding"]["x"]["axis"] = {
            "labelColor": "white",
            "titleColor": "white",
        }
        payload["vega_lite_spec"]["encoding"]["y"]["axis"] = {
            "labelColor": "white",
            "titleColor": "white",
        }
        payload["vega_lite_spec"]["encoding"]["color"]["legend"] = {
            "labelColor": "white",
            "titleColor": "white",
        }

        prepared = prepare_vega_lite_spec(
            payload["vega_lite_spec"],
            payload["records"],
            "Calls",
            chart_type="bar",
        )

        self.assertEqual(prepared["config"]["font"], "sans-serif")
        self.assertEqual(prepared["config"]["title"]["color"], "#111827")
        for channel in ("x", "y"):
            axis = prepared["encoding"][channel]["axis"]
            self.assertTrue(axis["labels"])
            self.assertEqual(axis["labelColor"], "#374151")
            self.assertEqual(axis["titleColor"], "#111827")
        self.assertEqual(axis["labelFont"], "sans-serif")
        legend = prepared["encoding"]["color"]["legend"]
        self.assertEqual(legend["labelColor"], "#374151")
        self.assertEqual(legend["titleColor"], "#111827")
        self.assertEqual(legend["labelFont"], "sans-serif")

    def test_bar_accuracy_is_compared_with_official_cells_locally(self):
        result = {
            "chart_type": "bar",
            "records": [
                {"category": "Bristol", "series": "2015", "value": 47.0},
                {"category": "Bristol", "series": "2020", "value": 55.0},
                {"category": "Leeds", "series": "2015", "value": 35.0},
                {"category": "Leeds", "series": "2020", "value": None},
            ],
            "comparison": {"omitted_official_items": []},
        }

        _annotate_bar_accuracy(
            result,
            "City | 2015 | 2020<0x0A>Bristol | 42 | 55<0x0A>Leeds | 35 | 48",
        )

        bristol_2015 = result["records"][0]
        leeds_2020 = result["records"][3]
        self.assertEqual(bristol_2015["feedback_status"], "incorrect")
        self.assertEqual(bristol_2015["official_value"], 42.0)
        self.assertEqual(bristol_2015["feedback_label"], "Bristol - 2015")
        self.assertEqual(result["records"][1]["feedback_status"], "correct")
        self.assertEqual(leeds_2020["feedback_status"], "unmentioned")
        self.assertIn("Leeds - 2020", result["comparison"]["omitted_official_items"])
        self.assertNotIn("Leeds - 2020", " ".join(result["comparison"]["incorrect_official_items"]))

    def test_bar_accuracy_matches_transposed_model_fields_without_false_issues(self):
        result = {
            "chart_type": "bar",
            "records": [
                {"category": "2015", "period": "2015", "series": "Bristol", "value": 41.7},
                {"category": "2020", "period": "2020", "series": "Bristol", "value": 55.2},
                {"category": "2015", "period": "2015", "series": "Leeds", "value": 35.3},
                {"category": "2020", "period": "2020", "series": "Leeds", "value": 48.2},
            ],
            "comparison": {"omitted_official_items": []},
        }

        _annotate_bar_accuracy(
            result,
            "City | 2015 | 2020<0x0A>Bristol | 41.7 | 55.2<0x0A>Leeds | 35.3 | 48.2",
        )

        self.assertEqual(len(result["records"]), 4)
        self.assertTrue(all(record["feedback_status"] == "correct" for record in result["records"]))
        self.assertEqual(result["comparison"]["incorrect_official_items"], [])

    def test_unmentioned_bar_cells_are_not_reported_as_errors(self):
        result = {
            "chart_type": "bar",
            "records": [
                {"category": "Bristol", "series": "2015", "value": 42.0},
            ],
            "comparison": {"omitted_official_items": []},
        }

        _annotate_bar_accuracy(
            result,
            "City | 2015 | 2020<0x0A>Bristol | 42 | 55",
        )

        self.assertEqual(result["records"][1]["feedback_status"], "unmentioned")
        self.assertFalse(result["records"][1]["incorrect"])
        self.assertEqual(result["comparison"]["incorrect_official_items"], [])

    def test_percentage_bar_values_within_one_point_are_accepted(self):
        result = {
            "chart_type": "bar",
            "axes": {"unit": "%", "y_label": "Recycling rate (%)"},
            "records": [
                {"category": "Leeds", "series": "2020", "value": 49.0},
            ],
            "comparison": {"omitted_official_items": []},
        }

        _annotate_bar_accuracy(
            result,
            "City | 2020<0x0A>Leeds | 48.16",
        )

        self.assertEqual(result["records"][0]["feedback_status"], "correct")
        self.assertEqual(result["records"][0]["official_value"], 48.0)
        self.assertFalse(result["records"][0]["incorrect"])
        self.assertEqual(result["comparison"]["incorrect_official_items"], [])
        self.assertEqual(result["comparison"]["accepted_value_tolerance"], 2.0)
        self.assertEqual(
            result["comparison"]["accepted_value_tolerance_unit"],
            "percentage points",
        )

    def test_percentage_bar_values_outside_two_points_are_incorrect(self):
        result = {
            "chart_type": "bar",
            "axes": {"unit": "%", "y_label": "Recycling rate (%)"},
            "records": [
                {"category": "Leeds", "series": "2020", "value": 51.0},
            ],
            "comparison": {"omitted_official_items": []},
        }

        _annotate_bar_accuracy(
            result,
            "City | 2020<0x0A>Leeds | 48.16",
        )

        self.assertEqual(result["records"][0]["feedback_status"], "incorrect")
        self.assertTrue(result["records"][0]["incorrect"])

    def test_small_scale_line_values_keep_decimals_and_use_tighter_tolerance(self):
        result = {
            "chart_type": "line",
            "axes": {"unit": "millions", "y_label": "Passengers"},
            "records": [
                {"period": "2010", "series": "Bus", "value": 1.9, "estimated": False},
                {"period": "2015", "series": "Bus", "value": 1.7, "estimated": False},
                {"period": "2020", "series": "Bus", "value": 1.5, "estimated": False},
            ],
            "comparison": {"omitted_official_items": []},
        }

        _annotate_line_accuracy(
            result,
            "Year | Bus<0x0A>2010 | 1.8<0x0A>2015 | 1.8<0x0A>2020 | 1.3",
        )

        self.assertEqual(result["records"][0]["feedback_status"], "correct")
        self.assertEqual(result["records"][1]["feedback_status"], "correct")
        self.assertEqual(result["records"][2]["feedback_status"], "incorrect")
        self.assertEqual(result["records"][0]["official_value"], 1.8)
        self.assertEqual(result["records"][2]["official_value"], 1.3)
        self.assertEqual(result["comparison"]["accepted_value_tolerance"], 0.1)
        self.assertEqual(result["comparison"]["official_value_precision"], 1)

    def test_explicit_wrong_line_value_overrides_model_copy_of_official_value(self):
        periods = ["2010", "2012", "2014", "2016", "2018", "2020"]
        series_values = {
            "Bus": [1.8, 1.9, 1.7, 1.6, 1.5, 1.3],
            "Rail": [1.1, 1.3, 1.5, 1.8, 2.0, 2.2],
            "Metro": [0.8, 1.0, 1.2, 1.5, 1.7, 1.9],
        }
        payload = _model_payload("line")
        payload["title"] = "Average daily passengers using public transport, 2010-2020"
        payload["axes"] = {
            "x_label": "Year",
            "y_label": "Average daily passengers",
            "unit": "millions",
        }
        payload["records"] = [
            {
                "period": period,
                "category": period,
                "series": series,
                "value": value,
                "missing": False,
                "estimated": False,
                "confidence": 1,
            }
            for series, values in series_values.items()
            for period, value in zip(periods, values)
        ]
        payload["vega_lite_spec"] = {
            "mark": "line",
            "encoding": {
                "x": {"field": "period", "type": "ordinal"},
                "y": {"field": "value", "type": "quantitative"},
                "color": {"field": "series", "type": "nominal"},
            },
        }
        deplot = (
            "Year | Bus | Rail | Metro<0x0A>2010 | 1.8 | 1.1 | 0.8<0x0A>"
            "2012 | 1.9 | 1.3 | 1.0<0x0A>2014 | 1.7 | 1.5 | 1.2<0x0A>"
            "2016 | 1.6 | 1.8 | 1.5<0x0A>2018 | 1.5 | 2.0 | 1.7<0x0A>"
            "2020 | 1.3 | 2.2 | 1.9"
        )
        answer = (
            "In 2010, Bus was the clear leader with 1.8 million daily passengers, "
            "significantly ahead of Rail at 4.1 million and Metro at 0.8 million. "
            "Rail passenger numbers climbed steadily from 4.1 million in 2010 to "
            "1.5 million in 2014, before reaching 1.8 million in 2016, 2.0 million "
            "in 2018 and 2.2 million in 2020. Similarly, Metro usage rose at every "
            "interval, starting at 0.8 million and reaching 1.9 million by 2020."
        )

        with tempfile.TemporaryDirectory() as folder:
            result, _ = ChartFeedbackService(
                folder,
                client=FakeClient(payload),
            ).generate(
                chart_type="line",
                requirement="Summarise the graph.",
                student_answer=answer,
                deplot_text=deplot,
            )

        rail_2010 = next(
            record
            for record in result["records"]
            if record["period"] == "2010" and record["series"] == "Rail"
        )
        rendered_rail_2010 = next(
            record
            for record in result["vega_lite_spec"]["data"]["values"]
            if record["period"] == "2010" and record["series"] == "Rail"
        )
        metro_2020 = next(
            record
            for record in result["records"]
            if record["period"] == "2020" and record["series"] == "Metro"
        )
        rail_2012 = next(
            record
            for record in result["records"]
            if record["period"] == "2012" and record["series"] == "Rail"
        )
        self.assertEqual(rail_2010["value"], 4.1)
        self.assertEqual(rail_2010["official_value"], 1.1)
        self.assertEqual(rail_2010["feedback_status"], "incorrect")
        self.assertTrue(rail_2010["explicit_student_value"])
        self.assertEqual(rendered_rail_2010["_line_error_value"], 4.1)
        self.assertEqual(
            rendered_rail_2010["_line_feedback_label"],
            "YOU: 4.1\nCORRECT: 1.1",
        )
        self.assertEqual(metro_2020["value"], 1.9)
        self.assertNotEqual(metro_2020["feedback_status"], "conflicting")
        self.assertEqual(rail_2012["value"], 2.8)
        self.assertEqual(rail_2012["feedback_status"], "estimated")
        self.assertIn(
            "2010 - Rail: student 4.1, official 1.1",
            result["comparison"]["incorrect_official_items"],
        )

    def test_estimated_line_points_are_not_treated_as_explicit_errors(self):
        result = {
            "chart_type": "line",
            "axes": {"unit": "millions", "y_label": "Passengers"},
            "records": [
                {"period": "2010", "series": "Bus", "value": 10.0, "estimated": True},
            ],
            "comparison": {"omitted_official_items": []},
        }

        _annotate_line_accuracy(
            result,
            "Year | Bus<0x0A>2010 | 1.8",
        )

        self.assertEqual(result["records"][0]["feedback_status"], "estimated")
        self.assertFalse(result["records"][0]["incorrect"])
        self.assertEqual(result["comparison"]["incorrect_official_items"], [])

    def test_incorrect_bar_gets_a_pink_dashed_overlay_and_direct_comparison_label(self):
        prepared = prepare_vega_lite_spec(
            {
                "mark": "bar",
                "encoding": {
                    "x": {"field": "category", "type": "ordinal"},
                    "xOffset": {"field": "series", "type": "nominal"},
                    "y": {"field": "value", "type": "quantitative"},
                    "color": {"field": "series", "type": "nominal"},
                },
            },
            [
                {
                    "category": "Bristol",
                    "series": "2015",
                    "value": 47.0,
                    "official_value": 42.0,
                    "feedback_status": "incorrect",
                },
                {
                    "category": "Bristol",
                    "series": "2020",
                    "value": 55.0,
                    "official_value": 55.0,
                    "feedback_status": "correct",
                },
            ],
            "Recycling",
            chart_type="bar",
            unit="%",
        )

        self.assertEqual(len(prepared["layer"]), 3)
        overlay = prepared["layer"][1]
        label = prepared["layer"][2]
        self.assertEqual(overlay["mark"]["color"], "#f9a8d4")
        self.assertEqual(overlay["mark"]["strokeDash"], [6, 3])
        self.assertNotIn("color", overlay["encoding"])
        self.assertEqual(overlay["encoding"]["y"]["field"], "_bar_error_value")
        self.assertEqual(label["mark"]["color"], "#701a3d")
        self.assertEqual(
            prepared["data"]["values"][0]["_bar_feedback_label"],
            "YOU: 47\nCORRECT: 42",
        )
        self.assertIsNone(prepared["data"]["values"][1]["_bar_error_value"])

    def test_palette_follows_source_legend_instead_of_bar_area(self):
        source = Path(__file__).parents[2] / "test_samples" / "charts" / "01_bar_recycling_rates.png"
        palette = extract_image_palette(source)

        self.assertEqual(palette[:2], ["#2f6690", "#d97706"])

    def test_line_palette_preserves_all_thin_series_colours(self):
        source = Path(__file__).parents[2] / "test_samples" / "charts" / "02_line_daily_passengers.png"

        self.assertEqual(
            extract_image_palette(source)[:3],
            ["#c2413b", "#287271", "#e9c46a"],
        )

    def test_line_renderer_adds_points_and_does_not_force_zero(self):
        prepared = prepare_vega_lite_spec(
            {
                "mark": "line",
                "encoding": {
                    "x": {"field": "period", "type": "ordinal"},
                    "y": {"field": "value", "type": "quantitative"},
                    "color": {"field": "series", "type": "nominal"},
                },
            },
            [
                {"period": "2010", "series": "Bus", "value": 1.8},
                {"period": "2020", "series": "Bus", "value": 1.3},
            ],
            "Passengers",
            chart_type="line",
        )

        self.assertEqual(prepared["mark"]["point"], {"filled": True, "size": 60})
        self.assertFalse(prepared["encoding"]["y"]["scale"]["zero"])

    def test_incorrect_line_value_gets_a_prominent_pink_point_overlay(self):
        prepared = prepare_vega_lite_spec(
            {
                "mark": "line",
                "encoding": {
                    "x": {"field": "period", "type": "ordinal"},
                    "y": {"field": "value", "type": "quantitative"},
                    "color": {"field": "series", "type": "nominal"},
                },
            },
            [
                {
                    "period": "2010",
                    "series": "Bus",
                    "value": 2.2,
                    "official_value": 1.8,
                    "feedback_status": "incorrect",
                },
                {
                    "period": "2020",
                    "series": "Bus",
                    "value": 1.3,
                    "official_value": 1.3,
                    "feedback_status": "correct",
                },
            ],
            "Passengers",
            chart_type="line",
        )

        self.assertEqual(len(prepared["layer"]), 3)
        overlay = prepared["layer"][1]
        label = prepared["layer"][2]
        self.assertEqual(overlay["mark"]["type"], "point")
        self.assertEqual(overlay["mark"]["color"], "#f9a8d4")
        self.assertEqual(overlay["mark"]["stroke"], "#be185d")
        self.assertEqual(overlay["mark"]["size"], 220)
        self.assertNotIn("color", overlay["encoding"])
        self.assertEqual(overlay["encoding"]["y"]["field"], "_line_error_value")
        self.assertEqual(overlay["encoding"]["y"]["title"], "value")
        self.assertEqual(prepared["data"]["values"][0]["_line_error_value"], 2.2)
        self.assertEqual(
            prepared["data"]["values"][0]["_line_feedback_label"],
            "YOU: 2.2\nCORRECT: 1.8",
        )
        self.assertEqual(label["mark"]["type"], "text")
        self.assertEqual(label["mark"]["color"], "#701a3d")
        self.assertIsNone(prepared["data"]["values"][1]["_line_error_value"])

    def test_pie_renderer_adds_category_and_percentage_labels(self):
        records = [
            {"category": "Housing", "series": None, "value": 32.0},
            {"category": "Food", "series": None, "value": 21.0},
            {"category": "Other", "series": None, "value": 8.0},
        ]
        prepared = prepare_vega_lite_spec(
            {"mark": "arc", "encoding": {}},
            records,
            "Spending",
            chart_type="pie",
            unit="percentage of total spending",
        )

        self.assertEqual([layer["mark"]["type"] for layer in prepared["layer"]], ["arc", "text"])
        self.assertEqual(
            [record["_display_label"] for record in prepared["data"]["values"]],
            ["Housing 32%", "Food 21%", "Other 8%", "MISSING 39%"],
        )
        missing = prepared["data"]["values"][-1]
        self.assertEqual(missing["feedback_status"], "missing_total")
        self.assertEqual((missing["_main_start"], missing["_main_end"]), (61.0, 100.0))
        self.assertEqual(prepared["title"], "Spending")
        values = prepared["data"]["values"]
        self.assertEqual([record["_label_mid"] for record in values], [16.0, 42.5, 57.0, 80.5])
        text_encoding = prepared["layer"][-1]["encoding"]
        self.assertEqual(text_encoding["theta"]["field"], "_label_mid")
        self.assertNotIn("theta2", text_encoding)

    def test_pie_renderer_computes_shares_when_unit_is_missing(self):
        records = [
            {"category": "Housing", "value": 60.0},
            {"category": "Other", "value": 40.0},
        ]
        prepared = prepare_vega_lite_spec(
            {"mark": "arc", "encoding": {}},
            records,
            "Spending",
            chart_type="pie",
        )

        self.assertEqual(
            [record["_display_label"] for record in prepared["data"]["values"]],
            ["Housing 60 (60%)", "Other 40 (40%)"],
        )

    def test_pie_accuracy_is_compared_with_official_values_locally(self):
        result = {
            "chart_type": "pie",
            "records": [
                {"category": "Housing", "value": 29.0, "missing": False},
                {"category": "Food", "value": 24.0, "missing": False},
            ],
            "comparison": {"omitted_official_items": []},
        }

        _annotate_pie_accuracy(
            result,
            "Category | Percentage<0x0A>Housing | 32%<0x0A>Food | 21%<0x0A>Other | 47%",
        )

        self.assertEqual([record["category"] for record in result["records"]], ["Housing", "Food", "Other"])
        self.assertTrue(result["records"][0]["incorrect"])
        self.assertEqual(result["records"][0]["official_value"], 32.0)
        self.assertTrue(result["records"][2]["missing"])
        self.assertEqual(result["comparison"]["student_percentage_total"], 53.0)
        self.assertEqual(result["comparison"]["percentage_balance"], "under")

    def test_pie_uses_rounded_official_values_without_tolerance(self):
        result = {
            "chart_type": "pie",
            "records": [
                {"category": "Housing", "value": 48.0, "missing": False},
                {"category": "Other", "value": 52.0, "missing": False},
            ],
            "comparison": {"omitted_official_items": []},
        }

        _annotate_pie_accuracy(
            result,
            "Category | Percentage<0x0A>Housing | 48.12%<0x0A>Other | 51.88%",
        )

        self.assertEqual(result["records"][0]["official_value"], 48.0)
        self.assertEqual(result["records"][1]["official_value"], 52.0)
        self.assertTrue(all(record["feedback_status"] == "correct" for record in result["records"]))
        self.assertEqual(result["comparison"]["expected_percentage_total"], 100.0)
        self.assertEqual(result["comparison"]["accepted_value_tolerance"], 0.0)

    def test_pie_rejects_even_a_one_point_difference(self):
        result = {
            "chart_type": "pie",
            "records": [
                {"category": "Housing", "value": 49.0, "missing": False},
                {"category": "Other", "value": 51.0, "missing": False},
            ],
            "comparison": {"omitted_official_items": []},
        }

        _annotate_pie_accuracy(
            result,
            "Category | Percentage<0x0A>Housing | 48.12%<0x0A>Other | 51.88%",
        )

        self.assertEqual(result["records"][0]["official_value"], 48.0)
        self.assertTrue(result["records"][0]["incorrect"])
        self.assertEqual(result["records"][0]["feedback_status"], "incorrect")

    def test_explicit_pie_percentage_restores_a_model_omission(self):
        payload = _model_payload("pie")
        payload["title"] = "Average household expenditure in Canada, 2024"
        payload["axes"] = {"x_label": "", "y_label": "", "unit": "%"}
        payload["records"] = [
            {"category": "Housing", "value": 32, "confidence": 1},
            {"category": "Food", "value": 21, "confidence": 1},
            {"category": "Transport", "value": 17, "confidence": 1},
            {"category": "Leisure", "value": 12, "confidence": 1},
            {"category": "Other", "value": 8, "confidence": 1},
        ]
        payload["vega_lite_spec"] = {"mark": "arc", "encoding": {}}
        client = FakeClient(payload)

        with tempfile.TemporaryDirectory() as folder:
            result, filename = ChartFeedbackService(folder, client=client).generate(
                chart_type="pie",
                requirement="Summarise the chart.",
                student_answer=(
                    "Housing was 32%. Food and transport represented 21% and 17% respectively. "
                    "Leisure spending was recorded at 12%, while utilities claimed a 50% share. "
                    "Other items constituted 8% of total spending."
                ),
                deplot_text=(
                    "Category | Percentage<0x0A>Housing | 32%<0x0A>Food | 21%"
                    "<0x0A>Transport | 17%<0x0A>Leisure | 12%<0x0A>Utilities | 10%"
                    "<0x0A>Other | 8%"
                ),
            )
            self.assertTrue((Path(folder) / filename).exists())

        utilities = next(record for record in result["records"] if record["category"] == "Utilities")
        self.assertEqual(utilities["value"], 50.0)
        self.assertEqual(utilities["official_value"], 10.0)
        self.assertFalse(utilities["missing"])
        self.assertTrue(utilities["incorrect"])
        self.assertEqual(result["comparison"]["student_percentage_total"], 140.0)
        self.assertEqual(result["comparison"]["percentage_balance"], "over")
        self.assertEqual(result["comparison"]["percentage_difference"], 40.0)

    def test_pie_aggregate_percentages_do_not_override_individual_values(self):
        payload = _model_payload("pie")
        payload["title"] = "Average household expenditure in Canada, 2024"
        payload["axes"] = {"x_label": "", "y_label": "", "unit": "%"}
        payload["records"] = [
            {"category": "Housing", "value": 32, "confidence": 1},
            {"category": "Food", "value": 21, "confidence": 1},
            {"category": "Transport", "value": 17, "confidence": 1},
            {"category": "Leisure", "value": 12, "confidence": 1},
            {"category": "Utilities", "value": 10, "confidence": 1},
            {"category": "Other", "value": 8, "confidence": 1},
        ]
        payload["vega_lite_spec"] = {"mark": "arc", "encoding": {}}
        client = FakeClient(payload)

        with tempfile.TemporaryDirectory() as folder:
            result, _ = ChartFeedbackService(folder, client=client).generate(
                chart_type="pie",
                requirement="Summarise the chart.",
                student_answer=(
                    "Housing was the most significant expenditure, at 32%. Food was the "
                    "second-highest cost, representing 21% of the total, followed by transport at 17%. "
                    "Leisure accounted for 12%, while utilities constituted 10%. Other made up 8%. "
                    "The combined expenditure on housing and food alone amounted to 53%. "
                    "The addition of transport costs brings this cumulative figure to 70%. "
                    "Leisure, utilities, and other collectively accounted for 30%."
                ),
                deplot_text=(
                    "Category | Percentage<0x0A>Housing | 32%<0x0A>Food | 21%"
                    "<0x0A>Transport | 17%<0x0A>Leisure | 12%<0x0A>Utilities | 10%"
                    "<0x0A>Other | 8%"
                ),
            )

        values = {record["category"]: record["value"] for record in result["records"]}
        self.assertEqual(values["Transport"], 17.0)
        self.assertEqual(values, {
            "Housing": 32.0,
            "Food": 21.0,
            "Transport": 17.0,
            "Leisure": 12.0,
            "Utilities": 10.0,
            "Other": 8.0,
        })
        self.assertEqual(result["comparison"]["student_percentage_total"], 100.0)
        self.assertEqual(result["comparison"]["percentage_balance"], "complete")
        self.assertEqual(result["comparison"]["incorrect_official_items"], [])

    def test_direct_value_is_kept_when_the_same_sentence_has_an_aggregate_percentage(self):
        payload = _model_payload("pie")
        payload["title"] = "Average household expenditure in Canada, 2024"
        payload["axes"] = {"x_label": "", "y_label": "", "unit": "%"}
        payload["records"] = [
            {"category": "Housing", "value": 32, "confidence": 1},
            {"category": "Food", "value": 21, "confidence": 1},
            {"category": "Transport", "value": 17, "confidence": 1},
            {"category": "Leisure", "value": 12, "confidence": 1},
            {"category": "Utilities", "value": 10, "confidence": 1},
            {"category": "Other", "value": 8, "confidence": 1},
        ]
        payload["vega_lite_spec"] = {"mark": "arc", "encoding": {}}
        client = FakeClient(payload)

        with tempfile.TemporaryDirectory() as folder:
            result, _ = ChartFeedbackService(folder, client=client).generate(
                chart_type="pie",
                requirement="Summarise the chart.",
                student_answer=(
                    "Housing dominated the breakdown at 32%. Food was the second most substantial "
                    "cost, claiming 21% of the average household budget. Transport followed at 47%, "
                    "meaning that these top three categories together absorbed exactly 70% of total "
                    "spending. The remaining 30% was distributed among leisure, which accounted for "
                    "12%, utilities at 10%, and a miscellaneous other segment representing 8%. "
                    "Furthermore, the combined spending on food and transport, at 38%, exceeded the "
                    "housing share."
                ),
                deplot_text=(
                    "Category | Percentage<0x0A>Housing | 32%<0x0A>Food | 21%"
                    "<0x0A>Transport | 17%<0x0A>Leisure | 12%<0x0A>Utilities | 10%"
                    "<0x0A>Other | 8%"
                ),
            )

        transport = next(record for record in result["records"] if record["category"] == "Transport")
        rendered_transport = next(
            record for record in result["vega_lite_spec"]["data"]["values"]
            if record.get("category") == "Transport"
        )
        self.assertEqual(transport["value"], 47.0)
        self.assertEqual(transport["official_value"], 17.0)
        self.assertEqual(transport["feedback_status"], "incorrect")
        self.assertEqual(result["comparison"]["student_percentage_total"], 130.0)
        self.assertEqual(result["comparison"]["percentage_balance"], "over")
        self.assertEqual(
            rendered_transport["_display_label"],
            "Transport\nYOU: 47%\nCORRECT: 17%",
        )

    def test_pie_synonym_conflict_uses_latest_value_and_reports_both_claims(self):
        payload = _model_payload("pie")
        payload["title"] = "Average household expenditure in Canada, 2024"
        payload["axes"] = {"x_label": "", "y_label": "", "unit": "%"}
        payload["records"] = [
            {"category": "Housing", "value": 32, "confidence": 1},
            {"category": "Food", "value": 21, "confidence": 1},
            {"category": "Transport", "value": 17, "confidence": 1},
            {"category": "Leisure", "value": 12, "confidence": 1},
            {"category": "Utilities", "value": 10, "confidence": 1},
            {"category": "Other", "value": 8, "confidence": 1},
        ]
        payload["vega_lite_spec"] = {"mark": "arc", "encoding": {}}
        client = FakeClient(payload)

        with tempfile.TemporaryDirectory() as folder:
            result, _ = ChartFeedbackService(folder, client=client).generate(
                chart_type="pie",
                requirement="Summarise the chart.",
                student_answer=(
                    "Housing was 32%, food was 21%, transport was 17%, leisure was 12%, "
                    "and utilities were 10%. The smallest category was 'Other' miscellaneous "
                    "expenses, which made up just 8% of the average household budget. "
                    "The relatively small 24% assigned to miscellaneous items underscored "
                    "the dominance of essential spending."
                ),
                deplot_text=(
                    "Category | Percentage<0x0A>Housing | 32%<0x0A>Food | 21%"
                    "<0x0A>Transport | 17%<0x0A>Leisure | 12%<0x0A>Utilities | 10%"
                    "<0x0A>Other | 8%"
                ),
            )

        other = next(record for record in result["records"] if record["category"] == "Other")
        rendered_other = next(
            record for record in result["vega_lite_spec"]["data"]["values"]
            if record.get("category") == "Other"
        )
        self.assertEqual(other["value"], 24.0)
        self.assertEqual(other["conflicting_values"], [8.0, 24.0])
        self.assertEqual(other["feedback_status"], "conflicting")
        self.assertTrue(other["incorrect"])
        self.assertEqual(result["comparison"]["student_percentage_total"], 116.0)
        self.assertEqual(result["comparison"]["percentage_balance"], "over")
        self.assertEqual(
            rendered_other["_display_label"],
            "Other\nCONFLICT: 8% / 24%\nCORRECT: 8%",
        )

    def test_incorrect_pie_slices_get_red_error_rings_and_labels(self):
        records = [
            {
                "category": "Housing",
                "value": 30.0,
                "official_value": 32.0,
                "incorrect": True,
                "feedback_status": "incorrect",
            },
            {
                "category": "Food",
                "value": 23.0,
                "official_value": 21.0,
                "incorrect": True,
                "feedback_status": "incorrect",
            },
            {
                "category": "Other",
                "value": 47.0,
                "official_value": 47.0,
                "incorrect": False,
                "feedback_status": "correct",
            },
        ]

        prepared = prepare_vega_lite_spec(
            {"mark": "arc", "encoding": {}},
            records,
            "Spending",
            ["#355c7d", "#6c5b7b", "#84949c"],
            chart_type="pie",
            unit="%",
        )

        self.assertEqual(
            [layer["mark"]["type"] for layer in prepared["layer"]],
            ["arc", "arc", "rule", "text"],
        )
        error_layer = prepared["layer"][1]
        hatch_layer = prepared["layer"][2]
        self.assertEqual(error_layer["mark"]["color"], "#f9a8d4")
        self.assertEqual(error_layer["mark"]["stroke"], "#be185d")
        self.assertEqual(error_layer["mark"]["opacity"], 1)
        self.assertEqual(hatch_layer["mark"]["type"], "rule")
        self.assertEqual(hatch_layer["mark"]["stroke"], "#be185d")
        self.assertEqual(hatch_layer["encoding"]["x"]["scale"]["domain"], [0, 600])
        self.assertEqual(hatch_layer["encoding"]["y"]["scale"]["domain"], [420, 0])
        self.assertGreater(
            len([record for record in prepared["data"]["values"] if record.get("_hatch_x") is not None]),
            0,
        )
        self.assertEqual(
            prepared["data"]["values"][0]["_display_label"],
            "Housing\nYOU: 30%\nCORRECT: 32%",
        )
        self.assertEqual(prepared["data"]["values"][0]["_label_color"], "#701a3d")
        self.assertEqual((prepared["width"], prepared["height"]), (600, 420))
        self.assertEqual(prepared["autosize"], {"type": "pad", "contains": "padding"})
        self.assertEqual(prepared["title"], "Spending")

    def test_pie_total_over_100_uses_a_separate_excess_ring(self):
        prepared = prepare_vega_lite_spec(
            {"mark": "arc", "encoding": {}},
            [
                {
                    "category": "Housing",
                    "value": 60.0,
                    "official_value": 60.0,
                    "incorrect": False,
                    "feedback_status": "correct",
                },
                {
                    "category": "Other",
                    "value": 50.0,
                    "official_value": 40.0,
                    "incorrect": True,
                    "feedback_status": "incorrect",
                },
            ],
            "Spending",
            chart_type="pie",
            unit="%",
        )

        excess = next(
            record for record in prepared["data"]["values"]
            if record.get("feedback_status") == "excess_total"
        )
        self.assertEqual(excess["feedback_status"], "excess_total")
        self.assertEqual((excess["_excess_start"], excess["_excess_end"]), (0.0, 10.0))
        self.assertEqual(excess["_legend_label"], "Excess over 100%: 10%")
        self.assertEqual(
            [layer["mark"]["type"] for layer in prepared["layer"]],
            ["arc", "arc", "rule", "arc", "text"],
        )
        error_layer = prepared["layer"][1]
        excess_layer = prepared["layer"][3]
        self.assertEqual(error_layer["mark"]["outerRadius"], 145)
        self.assertEqual(error_layer["mark"]["stroke"], "#be185d")
        self.assertEqual((excess_layer["mark"]["innerRadius"], excess_layer["mark"]["outerRadius"]), (165, 177))
        self.assertFalse(any(record.get("_excess_label") for record in prepared["data"]["values"]))
        self.assertEqual(prepared["title"], "Spending")

    def test_rounded_pie_total_of_99_is_not_shown_as_missing(self):
        prepared = prepare_vega_lite_spec(
            {"mark": "arc", "encoding": {}},
            [
                {
                    "category": category,
                    "value": 33.0,
                    "official_value": 33.0,
                    "feedback_status": "correct",
                }
                for category in ("A", "B", "C")
            ],
            "Rounded shares",
            chart_type="pie",
            unit="%",
        )

        self.assertFalse(
            any(
                record.get("feedback_status") == "missing_total"
                for record in prepared["data"]["values"]
            )
        )
        self.assertEqual(prepared["layer"][0]["encoding"]["theta"]["scale"]["domain"], [0, 99.0])

    def test_pie_labels_have_no_text_outline(self):
        prepared = prepare_vega_lite_spec(
            {"mark": "arc", "encoding": {}},
            [
                {"category": "Housing", "value": 60.0},
                {"category": "Other", "value": 40.0},
            ],
            "Spending",
            chart_type="pie",
            unit="%",
        )

        text_mark = prepared["layer"][1]["mark"]
        self.assertNotIn("stroke", text_mark)
        self.assertNotIn("strokeWidth", text_mark)
        self.assertEqual(prepared["config"]["text"]["strokeWidth"], 0)

    def test_ai_text_labels_cannot_add_an_outline_to_other_charts(self):
        prepared = prepare_vega_lite_spec(
            {
                "layer": [
                    {"mark": "bar", "encoding": {"x": {"field": "category"}, "y": {"field": "value"}}},
                    {
                        "mark": {
                            "type": "text",
                            "stroke": "black",
                            "strokeWidth": 2,
                            "fill": "white",
                        },
                        "encoding": {
                            "text": {"field": "value"},
                            "stroke": {"value": "black"},
                        },
                    },
                ]
            },
            [{"category": "Housing", "value": 60.0}],
            "Spending",
            chart_type="bar",
        )

        text_layer = prepared["layer"][1]
        self.assertNotIn("stroke", text_layer["mark"])
        self.assertNotIn("strokeWidth", text_layer["mark"])
        self.assertNotIn("stroke", text_layer["encoding"])

    def test_auto_detection_distinguishes_pie_from_map_blocks(self):
        with tempfile.TemporaryDirectory() as folder:
            pie_path = Path(folder) / "pie.png"
            map_path = Path(folder) / "map.png"

            pie = Image.new("RGB", (320, 240), "white")
            draw = ImageDraw.Draw(pie)
            draw.pieslice((80, 40, 280, 240), 0, 120, fill="#355c7d")
            draw.pieslice((80, 40, 280, 240), 120, 240, fill="#c06c84")
            draw.pieslice((80, 40, 280, 240), 240, 360, fill="#f8b195")
            pie.save(pie_path)

            map_image = Image.new("RGB", (320, 240), "white")
            ImageDraw.Draw(map_image).rectangle((80, 40, 230, 190), fill="#8fbc6d")
            map_image.save(map_path)

            self.assertEqual(detect_chart_type(pie_path), "pie")
            self.assertIsNone(detect_chart_type(map_path))

    def test_auto_detected_pie_overrides_a_bar_model_response(self):
        payload = _model_payload("bar")
        payload["records"] = [
            {"category": "Housing", "value": 60, "confidence": 1},
            {"category": "Other", "value": 40, "confidence": 1},
        ]
        client = FakeClient(payload)
        with tempfile.TemporaryDirectory() as folder:
            image_path = Path(folder) / "pie.png"
            image = Image.new("RGB", (320, 240), "white")
            draw = ImageDraw.Draw(image)
            draw.pieslice((80, 40, 280, 240), 0, 216, fill="#355c7d")
            draw.pieslice((80, 40, 280, 240), 216, 360, fill="#c06c84")
            image.save(image_path)

            result, _ = ChartFeedbackService(folder, client=client).generate(
                chart_type="auto",
                requirement="Summarise the chart.",
                student_answer="Housing was 60%, compared with 40% for other spending.",
                deplot_text="Category | Percentage<0x0A>Housing | 60<0x0A>Other | 40",
                image_path=image_path,
            )

        self.assertEqual(result["chart_type"], "pie")
        self.assertEqual(client.completions.kwargs["messages"][1]["content"].count('"requested_chart_type": "pie"'), 1)
        self.assertEqual(result["vega_lite_spec"]["layer"][1]["mark"]["type"], "text")

    def test_pie_discards_unsafe_model_spec_because_renderer_is_canonical(self):
        payload = _model_payload("pie")
        payload["records"] = [
            {"category": "Housing", "value": 60, "confidence": 1},
            {"category": "Other", "value": 40, "confidence": 1},
        ]
        payload["vega_lite_spec"] = {
            "mark": "arc",
            "transform": [{"calculate": "datum.value + '%'", "as": "label"}],
            "encoding": {},
        }
        client = FakeClient(payload)
        with tempfile.TemporaryDirectory() as folder:
            result, _ = ChartFeedbackService(folder, client=client).generate(
                chart_type="pie",
                requirement="Summarise the chart.",
                student_answer="Housing was 60%, while other spending was 40%.",
                deplot_text="Category | Percentage<0x0A>Housing | 60<0x0A>Other | 40",
            )

        self.assertEqual(client.completions.call_count, 1)
        self.assertEqual(result["style"]["alignment_attempts"], 1)
        self.assertEqual(result["vega_lite_spec"]["layer"][1]["mark"]["type"], "text")

    def test_invalid_statistical_spec_is_retried_once(self):
        invalid = _model_payload("bar")
        invalid["vega_lite_spec"]["transform"] = [
            {"calculate": "datum.value", "as": "display_value"}
        ]
        client = SequenceClient([invalid, _model_payload("bar")])
        with tempfile.TemporaryDirectory() as folder:
            result, filename = ChartFeedbackService(folder, client=client).generate(
                chart_type="bar",
                requirement="Summarise the chart.",
                student_answer="Local calls were 72 billion minutes in 2001.",
                deplot_text="Year | Local<0x0A>2001 | 72",
            )
            self.assertTrue((Path(folder) / filename).exists())

        self.assertEqual(client.completions.call_count, 2)
        self.assertEqual(result["style"]["alignment_attempts"], 2)
        self.assertIn("previous chart JSON was rejected", client.completions.kwargs["messages"][1]["content"])

    def test_temporal_claims_marked_missing_are_retried(self):
        periods = ["2010", "2012", "2014", "2016", "2018", "2020"]
        series_values = {
            "Bus": [1.8, 1.9, 1.7, 1.6, 1.5, 1.3],
            "Rail": [1.1, 1.3, 1.5, 1.8, 2.0, 2.2],
            "Metro": [0.8, 1.0, 1.2, 1.5, 1.7, 1.9],
        }

        def payload(include_2010):
            result = _model_payload("line")
            result["records"] = []
            for series, values in series_values.items():
                for period, value in zip(periods, values):
                    present = include_2010 or period != "2010"
                    result["records"].append(
                        {
                            "period": period,
                            "category": period,
                            "series": series,
                            "value": value if present else None,
                            "missing": not present,
                            "estimated": False,
                            "confidence": 1,
                        }
                    )
            result["vega_lite_spec"] = {
                "mark": "line",
                "encoding": {
                    "x": {"field": "period", "type": "ordinal"},
                    "y": {"field": "value", "type": "quantitative"},
                    "color": {"field": "series", "type": "nominal"},
                },
            }
            return result

        client = SequenceClient([payload(False), payload(True)])
        deplot = (
            "Year | Bus | Rail | Metro<0x0A>2010 | 1.8 | 1.1 | 0.8<0x0A>"
            "2012 | 1.9 | 1.3 | 1.0<0x0A>2014 | 1.7 | 1.5 | 1.2<0x0A>"
            "2016 | 1.6 | 1.8 | 1.5<0x0A>2018 | 1.5 | 2.0 | 1.7<0x0A>"
            "2020 | 1.3 | 2.2 | 1.9"
        )
        answer = "In 2010, buses carried 1.8 million passengers, compared with 1.1 million for rail and 0.8 million for metro."

        with tempfile.TemporaryDirectory() as folder:
            result, _ = ChartFeedbackService(folder, client=client).generate(
                chart_type="line",
                requirement="Summarise the line graph.",
                student_answer=answer,
                deplot_text=deplot,
            )

        self.assertEqual(client.completions.call_count, 1)
        first_period = [record for record in result["records"] if record["period"] == "2010"]
        self.assertTrue(all(record["value"] is not None for record in first_period))
        self.assertTrue(all(record["explicit_student_value"] for record in first_period))

    def test_continuous_trend_interpolates_internal_line_gaps(self):
        periods = ["2010", "2012", "2014", "2016", "2018", "2020"]
        payload = _model_payload("line")
        payload["records"] = []
        for period in periods:
            value = {"2010": 0.8, "2020": 1.9}.get(period)
            payload["records"].append(
                {
                    "period": period,
                    "category": period,
                    "series": "Metro",
                    "value": value,
                    "missing": value is None,
                    "estimated": False,
                    "confidence": 1,
                }
            )
        payload["vega_lite_spec"] = {
            "mark": "line",
            "encoding": {
                "x": {"field": "period", "type": "ordinal"},
                "y": {"field": "value", "type": "quantitative"},
                "color": {"field": "series", "type": "nominal"},
            },
        }
        deplot = (
            "Year | Metro | Other<0x0A>2010 | 0.8 | 1<0x0A>2012 | 1 | 1<0x0A>"
            "2014 | 1.2 | 1<0x0A>2016 | 1.5 | 1<0x0A>2018 | 1.7 | 1<0x0A>2020 | 1.9 | 1"
        )
        for period in periods:
            payload["records"].append(
                {
                    "period": period,
                    "category": period,
                    "series": "Other",
                    "value": 1,
                    "missing": False,
                    "estimated": False,
                    "confidence": 1,
                }
            )

        with tempfile.TemporaryDirectory() as folder:
            result, _ = ChartFeedbackService(folder, client=FakeClient(payload)).generate(
                chart_type="line",
                requirement="Summarise the line graph.",
                student_answer="Metro usage rose steadily from 0.8 million in 2010 to 1.9 million in 2020.",
                deplot_text=deplot,
            )

        metro = [record for record in result["records"] if record["series"] == "Metro"]
        self.assertTrue(all(record["value"] is not None for record in metro))
        self.assertTrue(all(record["estimated"] for record in metro[1:-1]))
        self.assertAlmostEqual(metro[3]["value"], 1.46)

    def test_line_gap_remains_without_continuous_trend_wording(self):
        payload = _model_payload("line")
        payload["records"] = [
            {"period": "2010", "category": "2010", "series": "Bus", "value": 1.8},
            {"period": "2012", "category": "2012", "series": "Bus", "value": None},
            {"period": "2010", "category": "2010", "series": "Rail", "value": 1.1},
            {"period": "2012", "category": "2012", "series": "Rail", "value": 1.3},
        ]
        payload["vega_lite_spec"] = {
            "mark": "line",
            "encoding": {
                "x": {"field": "period", "type": "ordinal"},
                "y": {"field": "value", "type": "quantitative"},
                "color": {"field": "series", "type": "nominal"},
            },
        }
        with tempfile.TemporaryDirectory() as folder:
            result, _ = ChartFeedbackService(folder, client=FakeClient(payload)).generate(
                chart_type="line",
                requirement="Summarise the line graph.",
                student_answer="Bus use was 1.8 million in 2010.",
                deplot_text="Year | Bus | Rail<0x0A>2010 | 1.8 | 1.1<0x0A>2012 | 1.9 | 1.3",
            )

        missing = next(
            record for record in result["records"]
            if record["series"] == "Bus" and record["period"] == "2012"
        )
        self.assertIsNone(missing["value"])
        self.assertTrue(missing["missing"])


if __name__ == "__main__":
    unittest.main()

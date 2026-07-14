import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from PIL import Image, ImageDraw

from chart_detection import detect_chart_type
from chart_feedback import ChartFeedbackService, _normalise_result
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
            ["Housing 32%", "Food 21%", "Other 8%"],
        )

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

        self.assertEqual(client.completions.call_count, 2)
        first_period = [record for record in result["records"] if record["period"] == "2010"]
        self.assertTrue(all(record["value"] is not None for record in first_period))
        self.assertIn("explicitly states values", client.completions.kwargs["messages"][1]["content"])

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

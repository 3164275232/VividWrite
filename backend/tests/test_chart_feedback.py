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

    def create(self, **kwargs):
        self.kwargs = kwargs
        message = SimpleNamespace(content=json.dumps(self.payload))
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


class FakeClient:
    def __init__(self, payload):
        self.completions = FakeCompletions(payload)
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


if __name__ == "__main__":
    unittest.main()

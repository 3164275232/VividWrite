import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from chart_feedback import ChartFeedbackService, _normalise_result
from chart_renderer import InvalidChartSpec, prepare_vega_lite_spec


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


if __name__ == "__main__":
    unittest.main()

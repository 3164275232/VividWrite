import io
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from PIL import Image

from main import app
from task_image_detection import TaskImageClassification, TaskImageDetectionError


def png_bytes() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (320, 240), "white").save(buffer, format="PNG")
    return buffer.getvalue()


class PrepareTaskImageEndpointTests(unittest.TestCase):
    def post_image(self, *, chart_type: str = "auto", extract_deplot: str = "false"):
        client = TestClient(app)
        return client.post(
            "/api/prepare-task-image",
            files={"image": ("task.png", png_bytes(), "image/png")},
            data={"chart_type": chart_type, "extract_deplot": extract_deplot},
        )

    def test_auto_map_classification_skips_deplot(self):
        with (
            patch(
                "main.classify_task_image",
                return_value=TaskImageClassification(task_type="map", confidence=0.96),
            ),
            patch("main.extract_table_from_image_deplot") as deplot,
        ):
            response = self.post_image(extract_deplot="true")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["task_type"], "map")
        self.assertFalse(payload["needs_confirmation"])
        self.assertIsNone(payload["deplot_text"])
        deplot.assert_not_called()

    def test_auto_qwen_failure_requires_manual_choice_without_deplot(self):
        with (
            patch("main.classify_task_image", side_effect=TaskImageDetectionError("no qwen key")),
            patch("main.extract_table_from_image_deplot") as deplot,
        ):
            response = self.post_image(extract_deplot="true")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["task_type"], "unknown")
        self.assertTrue(payload["needs_confirmation"])
        self.assertEqual(payload["detection_source"], "qwen-vision-error")
        deplot.assert_not_called()

    def test_explicit_statistical_type_can_prepare_deplot(self):
        with patch("main.extract_table_from_image_deplot", return_value="Year | 2020\nValue | 10") as deplot:
            response = self.post_image(chart_type="bar", extract_deplot="true")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["task_type"], "bar")
        self.assertFalse(payload["needs_confirmation"])
        self.assertEqual(payload["deplot_text"], "Year | 2020<0x0A>Value | 10")
        deplot.assert_called_once()


if __name__ == "__main__":
    unittest.main()

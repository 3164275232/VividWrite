import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from wan_image_renderer import WanImageRendererError, WanSpatialFeedbackService, get_wan_endpoint


def png_bytes() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (320, 240), "white").save(buffer, format="PNG")
    return buffer.getvalue()


class FakeResponse:
    def __init__(self, *, status_code=200, payload=None, content=b""):
        self.status_code = status_code
        self._payload = payload
        self.content = content

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeSession:
    def __init__(self):
        self.post_args = None
        self.get_url = None

    def post(self, url, **kwargs):
        self.post_args = (url, kwargs)
        return FakeResponse(
            payload={
                "output": {
                    "choices": [
                        {
                            "message": {
                                "content": [
                                    {"type": "image", "image": "https://example.test/result.png"}
                                ]
                            }
                        }
                    ]
                }
            }
        )

    def get(self, url, **kwargs):
        self.get_url = url
        return FakeResponse(content=png_bytes())


class WanSpatialFeedbackTests(unittest.TestCase):
    def make_reference(self, folder: str) -> Path:
        path = Path(folder) / "original.png"
        Image.new("RGBA", (640, 480), (245, 245, 245, 255)).save(path)
        return path

    def test_sends_reference_image_and_saves_result_locally(self):
        session = FakeSession()
        with tempfile.TemporaryDirectory() as folder, patch.dict(
            os.environ,
            {
                "WAN_API_KEY": "test-key",
                "WAN_API_ENDPOINT": "https://example.test/generate",
                "WAN_IMAGE_MODEL": "wan2.7-image-pro",
            },
            clear=False,
        ):
            reference = self.make_reference(folder)
            result, filename = WanSpatialFeedbackService(folder, session=session).generate(
                task_type="map",
                requirement="Describe the changes to the town.",
                student_answer="A bridge was added east of the school.",
                image_path=reference,
            )
            output = Path(folder) / filename
            self.assertTrue(output.exists())
            self.assertGreater(output.stat().st_size, 100)
        self.assertEqual(result["style"]["renderer"], "generative-image")
        self.assertEqual(session.get_url, "https://example.test/result.png")
        url, kwargs = session.post_args
        self.assertEqual(url, "https://example.test/generate")
        body = kwargs["json"]
        content = body["input"]["messages"][0]["content"]
        self.assertTrue(content[0]["image"].startswith("data:image/jpeg;base64,"))
        self.assertIn("A bridge was added east of the school", content[1]["text"])
        self.assertFalse(body["parameters"]["watermark"])

    def test_reports_missing_api_key(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(
            os.environ, {"WAN_API_KEY": "", "DASHSCOPE_API_KEY": ""}, clear=False
        ):
            reference = self.make_reference(folder)
            with self.assertRaisesRegex(WanImageRendererError, "WAN_API_KEY"):
                WanSpatialFeedbackService(folder, session=FakeSession()).generate(
                    task_type="process",
                    requirement="Describe the process.",
                    student_answer="The material is heated.",
                    image_path=reference,
                )

    def test_workspace_endpoint_accepts_short_id_or_full_hostname(self):
        with patch.dict(os.environ, {"WAN_API_ENDPOINT": "", "WAN_WORKSPACE_ID": "ws-example"}, clear=False):
            self.assertEqual(
                get_wan_endpoint(),
                "https://ws-example.cn-beijing.maas.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation",
            )
        with patch.dict(
            os.environ,
            {
                "WAN_API_ENDPOINT": "",
                "WAN_WORKSPACE_ID": "ws-example.cn-beijing.maas.aliyuncs.com",
            },
            clear=False,
        ):
            self.assertEqual(
                get_wan_endpoint(),
                "https://ws-example.cn-beijing.maas.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation",
            )

    def test_workspace_endpoint_can_target_singapore(self):
        with patch.dict(
            os.environ,
            {
                "WAN_API_ENDPOINT": "",
                "WAN_WORKSPACE_ID": "ws-example",
                "WAN_REGION": "ap-southeast-1",
            },
            clear=False,
        ):
            self.assertEqual(
                get_wan_endpoint(),
                "https://ws-example.ap-southeast-1.maas.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation",
            )


if __name__ == "__main__":
    unittest.main()

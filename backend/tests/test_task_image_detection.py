import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from PIL import Image

from task_image_detection import (
    classify_task_image,
    clear_task_image_detection_cache,
)


def make_image(path: Path) -> None:
    Image.new("RGB", (640, 360), "white").save(path)


class FakeCompletions:
    def __init__(self, content: str):
        self.content = content
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=self.content))]
        )


class TaskImageDetectionTests(unittest.TestCase):
    def setUp(self):
        clear_task_image_detection_cache()
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.image_path = Path(self.temporary_directory.name) / "task.png"
        make_image(self.image_path)

    def tearDown(self):
        clear_task_image_detection_cache()
        self.temporary_directory.cleanup()

    def test_qwen_classification_uses_json_mode_and_disables_thinking(self):
        completions = FakeCompletions('{"task_type":"map","confidence":0.96,"reason":"site plan"}')
        client = SimpleNamespace(chat=SimpleNamespace(completions=completions))

        result = classify_task_image(self.image_path, client=client)

        self.assertEqual(result.task_type, "map")
        self.assertEqual(result.confidence, 0.96)
        kwargs = completions.calls[0]
        self.assertEqual(kwargs["temperature"], 0)
        self.assertEqual(kwargs["response_format"], {"type": "json_object"})
        self.assertEqual(kwargs["extra_body"], {"enable_thinking": False})
        content = kwargs["messages"][0]["content"]
        self.assertIn("IELTS Academic Writing Task 1", content[0]["text"])
        self.assertTrue(content[1]["image_url"]["url"].startswith("data:image/jpeg;base64,"))

    def test_repeated_image_reuses_cached_classification(self):
        completions = FakeCompletions('{"task_type":"process","confidence":"92%","reason":"arrows"}')
        client = SimpleNamespace(chat=SimpleNamespace(completions=completions))

        first = classify_task_image(self.image_path, client=client)
        second = classify_task_image(self.image_path, client=client)

        self.assertEqual(first.task_type, "process")
        self.assertEqual(second.task_type, "process")
        self.assertEqual(len(completions.calls), 1)

    def test_invalid_model_output_requires_manual_confirmation(self):
        completions = FakeCompletions("not json")
        client = SimpleNamespace(chat=SimpleNamespace(completions=completions))

        result = classify_task_image(self.image_path, client=client)

        self.assertEqual(result.task_type, "unknown")
        self.assertEqual(result.confidence, 0.0)


if __name__ == "__main__":
    unittest.main()

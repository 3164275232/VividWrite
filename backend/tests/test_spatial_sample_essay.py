import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image

from spatial_sample_essay import generate_spatial_sample_essay, get_qwen_vl_base_url


class FakeCompletions:
    def __init__(self, essay: str):
        self.essay = essay
        self.kwargs = None
        self.call_count = 0

    def create(self, **kwargs):
        self.kwargs = kwargs
        self.call_count += 1
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=self.essay))]
        )


class SequenceCompletions(FakeCompletions):
    def __init__(self, essays: list[str]):
        super().__init__(essays[0])
        self.essays = essays
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        self.essay = self.essays[min(self.call_count, len(self.essays) - 1)]
        return super().create(**kwargs)


class SpatialSampleEssayTests(unittest.TestCase):
    def make_image(self, folder: str) -> Path:
        path = Path(folder) / "process.png"
        Image.new("RGB", (640, 480), "white").save(path)
        return path

    def complete_flowchart(self) -> dict:
        return {
            "nodes": [
                {"type": "introduction"},
                {"type": "overview"},
                {"type": "key_details_a"},
                {"type": "key_details_b"},
            ],
            "edges": [],
        }

    def test_process_image_is_sent_to_qwen_vision(self):
        essay = " ".join(["process"] * 160)
        completions = FakeCompletions(essay)
        client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
        with tempfile.TemporaryDirectory() as folder, patch.dict(
            os.environ, {"QWEN_VL_MODEL": "qwen3.7-plus"}, clear=False
        ):
            response = generate_spatial_sample_essay(
                image_path=self.make_image(folder),
                chart_type="process",
                requirement="Describe the glass recycling process.",
                flowchart=self.complete_flowchart(),
                client=client,
            )

        self.assertTrue(response.success)
        self.assertEqual(response.essay, essay)
        self.assertEqual(completions.kwargs["model"], "qwen3.7-plus")
        content = completions.kwargs["messages"][0]["content"]
        self.assertIn("process diagram", content[0]["text"])
        self.assertTrue(content[1]["image_url"]["url"].startswith("data:image/jpeg;base64,"))

    def test_incomplete_plan_returns_structure_choice_before_model_call(self):
        completions = FakeCompletions("unused")
        client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
        with tempfile.TemporaryDirectory() as folder:
            response = generate_spatial_sample_essay(
                image_path=self.make_image(folder),
                chart_type="map",
                requirement="Describe the changes.",
                flowchart={"nodes": [{"type": "presentation"}], "edges": []},
                client=client,
            )

        self.assertTrue(response.requires_choice)
        self.assertEqual(completions.call_count, 0)

    def test_map_prompt_requests_spatial_change_analysis(self):
        essay = " ".join(["map"] * 150)
        completions = FakeCompletions(essay)
        client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
        with tempfile.TemporaryDirectory() as folder, patch.dict(
            os.environ, {"QWEN_VL_MODEL": "qwen3.7-plus"}, clear=False
        ):
            response = generate_spatial_sample_essay(
                image_path=self.make_image(folder),
                chart_type="map",
                requirement="Describe the changes to the town.",
                flowchart=self.complete_flowchart(),
                client=client,
            )

        self.assertTrue(response.success)
        prompt = completions.kwargs["messages"][0]["content"][0]["text"]
        self.assertIn("map or site-plan visual", prompt)
        self.assertIn("compass directions and relative positions", prompt)
        self.assertIn("do not invent a second state", prompt)

    def test_workspace_id_builds_openai_compatible_url(self):
        with patch.dict(
            os.environ,
            {
                "QWEN_VL_BASE_URL": "",
                "QWEN_VL_WORKSPACE_ID": "",
                "WAN_WORKSPACE_ID": "ws-example",
                "WAN_REGION": "",
                "ALIBABA_MODEL_STUDIO_REGION": "",
            },
            clear=False,
        ):
            self.assertEqual(
                get_qwen_vl_base_url(),
                "https://ws-example.cn-beijing.maas.aliyuncs.com/compatible-mode/v1",
            )

    def test_workspace_id_can_target_singapore_openai_compatible_url(self):
        with patch.dict(
            os.environ,
            {
                "QWEN_VL_BASE_URL": "",
                "QWEN_VL_WORKSPACE_ID": "",
                "WAN_WORKSPACE_ID": "ws-example",
                "WAN_REGION": "singapore",
            },
            clear=False,
        ):
            self.assertEqual(
                get_qwen_vl_base_url(),
                "https://ws-example.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1",
            )

    def test_map_and_process_retry_a_147_word_draft_instead_of_failing(self):
        for task_type in ("map", "process"):
            with self.subTest(task_type=task_type):
                first_draft = " ".join(["short"] * 147)
                revised_draft = " ".join(["complete"] * 180)
                completions = SequenceCompletions([first_draft, revised_draft])
                client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
                with tempfile.TemporaryDirectory() as folder:
                    response = generate_spatial_sample_essay(
                        image_path=self.make_image(folder),
                        chart_type=task_type,
                        requirement="Write an IELTS Academic Task 1 report.",
                        flowchart=self.complete_flowchart(),
                        client=client,
                    )

                self.assertTrue(response.success)
                self.assertEqual(len((response.essay or "").split()), 180)
                self.assertEqual(completions.call_count, 2)
                retry_text = completions.calls[1]["messages"][-1]["content"]
                self.assertIn("between 180 and 220 words", retry_text)
                self.assertEqual((response.debug or {}).get("attempts"), 2)


if __name__ == "__main__":
    unittest.main()

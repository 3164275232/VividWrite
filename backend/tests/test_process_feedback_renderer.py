import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from PIL import Image

from process_feedback_renderer import ProcessFeedbackService


STUDENT_ANSWER = (
    "The cycle starts when used bottles are placed in bins. "
    "They are collected by a huge plane before being sorted by colour. "
    "The bottles are washed with water, crushed, melted, moulded into new bottles "
    "and delivered to shops. After use, the bottles can enter the cycle again."
)


def process_plan(*, stage_two_evidence: str, stage_two_label: str) -> dict:
    labels = [
        ("Used bottles placed in bins", "used bottles are placed in bins"),
        ("Collected by recycling truck", stage_two_evidence),
        ("Sorted by colour", "sorted by colour"),
        ("Washed with water", "washed with water"),
        ("Crushed into glass pieces", "crushed"),
        ("Melted in a high-temperature furnace", "melted"),
        ("Moulded into new bottles", "moulded into new bottles"),
        ("Delivered to shops", "delivered to shops"),
    ]
    return {
        "source_title": "How used glass bottles are recycled",
        "source_subtitle": "A cyclical eight-stage process",
        "cyclical": True,
        "cycle_evidence": "After use, the bottles can enter the cycle again",
        "stages": [
            {
                "number": index,
                "source_label": source_label,
                "student_evidence": evidence,
                "student_label": stage_two_label if index == 2 else evidence,
                "status": "changed" if index == 2 else "accurate",
            }
            for index, (source_label, evidence) in enumerate(labels, start=1)
        ],
    }


class FakeCompletions:
    def __init__(self, payloads: list[dict]):
        self.payloads = payloads
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        payload = self.payloads[min(len(self.calls) - 1, len(self.payloads) - 1)]
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content=json.dumps(payload))
                )
            ]
        )


class ProcessFeedbackRendererTests(unittest.TestCase):
    def make_image(self, folder: str) -> Path:
        path = Path(folder) / "process.png"
        Image.new("RGB", (1200, 800), "#f8fafc").save(path)
        return path

    def test_student_evidence_overrides_a_source_label_leaked_by_the_model(self):
        payload = process_plan(
            stage_two_evidence="collected by a huge plane",
            stage_two_label="Collected by recycling truck",
        )
        completions = FakeCompletions([payload])
        client = SimpleNamespace(chat=SimpleNamespace(completions=completions))

        with tempfile.TemporaryDirectory() as folder:
            result, filename = ProcessFeedbackService(folder, client=client).generate(
                task_type="process",
                requirement="Describe the glass recycling process.",
                student_answer=STUDENT_ANSWER,
                image_path=self.make_image(folder),
            )
            output = Path(folder) / filename
            self.assertTrue(output.exists())
            self.assertGreater(output.stat().st_size, 1000)

        stage_two = result["records"][1]
        self.assertEqual(stage_two["value"], "collected by a huge plane")
        self.assertEqual(stage_two["official_value"], "Collected by recycling truck")
        self.assertEqual(stage_two["feedback_status"], "changed")
        self.assertNotIn(
            "truck",
            " ".join(str(record["value"] or "") for record in result["records"]).casefold(),
        )
        self.assertEqual(result["comparison"]["changed_stages"], [2])
        self.assertEqual(result["style"]["renderer"], "deterministic-process-diagram")

        prompt = completions.calls[0]["messages"][0]["content"][0]["text"]
        self.assertIn('source says "recycling truck"', prompt)
        self.assertIn('student says "huge plane"', prompt)
        image_url = completions.calls[0]["messages"][0]["content"][1]["image_url"]["url"]
        self.assertTrue(image_url.startswith("data:image/jpeg;base64,"))

    def test_non_verbatim_student_evidence_triggers_one_plan_retry(self):
        invalid = process_plan(
            stage_two_evidence="collected by recycling truck",
            stage_two_label="Collected by recycling truck",
        )
        corrected = process_plan(
            stage_two_evidence="collected by a huge plane",
            stage_two_label="Collected by huge plane",
        )
        completions = FakeCompletions([invalid, corrected])
        client = SimpleNamespace(chat=SimpleNamespace(completions=completions))

        with tempfile.TemporaryDirectory() as folder:
            result, _ = ProcessFeedbackService(folder, client=client).generate(
                task_type="process",
                requirement="Describe the glass recycling process.",
                student_answer=STUDENT_ANSWER,
                image_path=self.make_image(folder),
            )

        self.assertEqual(len(completions.calls), 2)
        self.assertIn(
            "not an exact quote",
            completions.calls[1]["messages"][-1]["content"],
        )
        self.assertEqual(result["records"][1]["value"], "Collected by huge plane")
        self.assertEqual(result["style"]["planning_attempts"], 2)


if __name__ == "__main__":
    unittest.main()

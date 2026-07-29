import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

from map_feedback_renderer import (
    MapFeedbackError,
    MapFeedbackService,
    _validated_map_plan,
)


STUDENT_ANSWER = (
    "Key landmarks include a restaurant situated in the north-west, a supermarket "
    "in the north-east, and a cluster of residences near Low Lane. The restaurant, "
    "supermarket, and housing locations remain unchanged."
)


def map_plan(*, evidence: str = "a restaurant situated in the north-west") -> dict:
    return {
        "source_title": "Present day and future plan",
        "labels": [
            {
                "source_text": "Present day",
                "role": "framework",
                "bbox": [20, 20, 180, 90],
                "rotation": 0,
                "student_evidence": None,
                "student_text": "",
                "action": "preserve",
            },
            {
                "source_text": "school",
                # Deliberately simulate a second Qwen error: a place is not framework text.
                "role": "framework",
                "bbox": [90, 130, 300, 240],
                "rotation": 0,
                "student_evidence": evidence,
                # Deliberately simulate source-label leakage from Qwen.
                "student_text": "school",
                "action": "replace",
            },
            {
                "source_text": "school",
                "role": "feature",
                "bbox": [590, 130, 800, 240],
                "rotation": 0,
                "student_evidence": evidence,
                "student_text": "restaurant",
                "action": "replace",
            },
            {
                "source_text": "supermarket",
                "role": "feature",
                "bbox": [340, 140, 480, 220],
                "rotation": 0,
                "student_evidence": "a supermarket in the north-east",
                "student_text": "supermarket",
                "action": "preserve",
            },
        ],
    }


class FakeMessage:
    def __init__(self, content: str):
        self.content = content


class FakeChoice:
    def __init__(self, content: str):
        self.message = FakeMessage(content)


class FakeCompletion:
    def __init__(self, content: str):
        self.choices = [FakeChoice(content)]


class FakeCompletions:
    def __init__(self, responses: list[dict]):
        self.responses = list(responses)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if not self.responses:
            raise AssertionError("Unexpected Qwen completion call")
        return FakeCompletion(json.dumps(self.responses.pop(0)))


class FakeChat:
    def __init__(self, responses: list[dict]):
        self.completions = FakeCompletions(responses)


class FakeClient:
    def __init__(self, responses: list[dict]):
        self.chat = FakeChat(responses)


class FakeWanService:
    def __init__(self, output_dir: str | Path, *, add_school: bool = False):
        self.output_dir = Path(output_dir)
        self.add_school = add_school
        self.prepared_bytes = b""

    def generate(self, **kwargs):
        prepared = Path(kwargs["image_path"])
        self.prepared_bytes = prepared.read_bytes()
        with Image.open(prepared) as source:
            image = source.convert("RGB")
        if self.add_school:
            draw = ImageDraw.Draw(image)
            draw.text((330, 190), "school", fill="black")
        filename = "fake-map.png"
        image.save(self.output_dir / filename)
        return (
            {
                "style": {
                    "renderer": "generative-image",
                    "provider": "fake-wan",
                    "model": "fake-wan",
                }
            },
            filename,
        )


class MapFeedbackRendererTests(unittest.TestCase):
    def make_source(self, folder: str) -> Path:
        path = Path(folder) / "source-map.png"
        image = Image.new("RGB", (1000, 500), "white")
        draw = ImageDraw.Draw(image)
        draw.rectangle((0, 0, 490, 490), outline="black", width=3)
        draw.rectangle((510, 0, 999, 490), outline="black", width=3)
        draw.text((90, 70), "school", fill="black")
        draw.text((590, 70), "school", fill="black")
        draw.text((340, 70), "supermarket", fill="black")
        image.save(path)
        return path

    def test_source_only_school_cannot_leak_into_student_label(self):
        validated = _validated_map_plan(map_plan(), STUDENT_ANSWER)
        feature_labels = [
            label for label in validated["labels"] if label["role"] == "feature"
        ]
        self.assertEqual(feature_labels[0]["student_text"], "restaurant")
        self.assertEqual(feature_labels[0]["action"], "replace")
        self.assertNotIn(
            "school",
            " ".join(label["student_text"] for label in feature_labels).casefold(),
        )

    def test_generates_from_sanitized_reference_and_reports_replacements(self):
        with tempfile.TemporaryDirectory() as folder:
            source = self.make_source(folder)
            original_bytes = source.read_bytes()
            client = FakeClient(
                [
                    map_plan(),
                    {"forbidden_occurrences": []},
                ]
            )
            wan = FakeWanService(folder)
            result, filename = MapFeedbackService(
                folder,
                client=client,
                wan_service=wan,
            ).generate(
                task_type="map",
                requirement="Summarise the proposed road changes.",
                student_answer=STUDENT_ANSWER,
                image_path=source,
            )

            self.assertTrue((Path(folder) / filename).is_file())
            self.assertEqual(source.read_bytes(), original_bytes)
            self.assertNotEqual(wan.prepared_bytes, original_bytes)
            self.assertEqual(result["style"]["renderer"], "verified-generative-map")
            self.assertEqual(result["comparison"]["forbidden_source_labels"], ["school"])
            self.assertEqual(result["comparison"]["label_repairs"], 0)
            student_values = [
                record["value"] for record in result["records"] if record["value"]
            ]
            self.assertIn("restaurant", student_values)
            self.assertNotIn("school", [value.casefold() for value in student_values])

    def test_repairs_a_forbidden_label_found_after_wan_generation(self):
        with tempfile.TemporaryDirectory() as folder:
            source = self.make_source(folder)
            client = FakeClient(
                [
                    map_plan(),
                    {
                        "forbidden_occurrences": [
                            {
                                "text": "school",
                                "bbox": [300, 300, 430, 430],
                                "replacement_visible_nearby": False,
                            }
                        ]
                    },
                    {"forbidden_occurrences": []},
                ]
            )
            result, filename = MapFeedbackService(
                folder,
                client=client,
                wan_service=FakeWanService(folder, add_school=True),
            ).generate(
                task_type="map",
                requirement="Summarise the map.",
                student_answer=STUDENT_ANSWER,
                image_path=source,
            )

            self.assertTrue((Path(folder) / filename).is_file())
            self.assertEqual(result["comparison"]["label_repairs"], 1)
            self.assertEqual(len(client.chat.completions.calls), 3)

    def test_retries_a_plan_with_non_verbatim_student_evidence(self):
        invalid = map_plan(evidence="restaurant in the wrong place")
        with tempfile.TemporaryDirectory() as folder:
            source = self.make_source(folder)
            client = FakeClient(
                [
                    invalid,
                    map_plan(),
                    {"forbidden_occurrences": []},
                ]
            )
            result, _ = MapFeedbackService(
                folder,
                client=client,
                wan_service=FakeWanService(folder),
            ).generate(
                task_type="map",
                requirement="Summarise the map.",
                student_answer=STUDENT_ANSWER,
                image_path=source,
            )

            self.assertEqual(result["style"]["planning_attempts"], 2)

    def test_rejects_output_when_forbidden_label_survives_repair(self):
        occurrence = {
            "forbidden_occurrences": [
                {
                    "text": "school",
                    "bbox": [300, 300, 430, 430],
                    "replacement_visible_nearby": True,
                }
            ]
        }
        with tempfile.TemporaryDirectory() as folder:
            source = self.make_source(folder)
            client = FakeClient([map_plan(), occurrence, occurrence])
            with self.assertRaisesRegex(MapFeedbackError, "still contains source-only labels"):
                MapFeedbackService(
                    folder,
                    client=client,
                    wan_service=FakeWanService(folder, add_school=True),
                ).generate(
                    task_type="map",
                    requirement="Summarise the map.",
                    student_answer=STUDENT_ANSWER,
                    image_path=source,
                )
            self.assertFalse((Path(folder) / "fake-map.png").exists())


if __name__ == "__main__":
    unittest.main()

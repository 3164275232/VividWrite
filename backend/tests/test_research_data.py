import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from research_data import ResearchStore


class ResearchStoreTests(unittest.TestCase):
    def test_sessions_events_artifacts_and_export_remain_participant_scoped(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = ResearchStore(Path(temp_dir))
            session_id = store.start_session(
                "tester01",
                "session-test-0001",
                client_started_at="2026-09-01T10:00:00.000Z",
                metadata={"browser": "test"},
            )
            accepted = store.append_events(
                "tester01",
                session_id,
                [
                    {
                        "event_id": "event-00000001",
                        "event_type": "essay_snapshot",
                        "source": "frontend",
                        "occurred_at": "2026-09-01T10:01:00.000Z",
                        "stage": "drafting",
                        "payload": {
                            "text": "The chart compares two groups.",
                            "word_count": 5,
                            "password": "must-not-be-exported",
                        },
                    }
                ],
            )
            self.assertEqual(accepted, 1)
            store.heartbeat(
                "tester01",
                session_id,
                active_ms=30_000,
                idle_ms=5_000,
            )
            artifact = store.archive_bytes(
                "tester01",
                session_id,
                b"image-data",
                category="generated_feedback_image",
                original_name="feedback.png",
                mime_type="image/png",
            )
            store.end_session(
                "tester01",
                session_id,
                active_ms=40_000,
                idle_ms=7_000,
                reason="logout",
            )
            store.ensure_participant("tester02")

            summaries = store.participant_summaries(["tester01", "tester02"])
            by_user = {item["username"]: item for item in summaries}
            self.assertEqual(by_user["tester01"]["session_count"], 1)
            self.assertEqual(by_user["tester01"]["artifact_count"], 1)
            self.assertEqual(by_user["tester02"]["session_count"], 0)

            export_path = store.build_export(
                ["tester01"],
                configured_usernames=["tester01", "tester02"],
            )
            with zipfile.ZipFile(export_path) as archive:
                names = set(archive.namelist())
                self.assertIn("summary.html", names)
                self.assertIn("essay_versions.csv", names)
                self.assertIn("raw/events.jsonl", names)
                self.assertTrue(any(name.startswith("artifacts/tester01/") for name in names))
                self.assertFalse(any("tester02" in name for name in names))
                events = [
                    json.loads(line)
                    for line in archive.read("raw/events.jsonl").decode("utf-8").splitlines()
                ]
            snapshot = next(item for item in events if item["event_type"] == "essay_snapshot")
            payload = json.loads(snapshot["payload_json"])
            self.assertEqual(payload["password"], "[redacted]")
            self.assertEqual(artifact["sha256"], "2b700b7786d5a3f0cb487c3afaccb889fae829504a0ad1b70881e4643360f344")

    def test_csv_export_neutralizes_formula_prefixes_but_raw_events_remain_exact(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = ResearchStore(Path(temp_dir))
            session_id = store.start_session("tester01", "session-csv-test-0001")
            store.append_events(
                "tester01",
                session_id,
                [{
                    "event_id": "event-csv-0000001",
                    "event_type": "essay_snapshot",
                    "occurred_at": "2026-09-01T10:00:00.000Z",
                    "payload": {"text": "=HYPERLINK(\"unsafe\")", "word_count": 1},
                }],
            )

            export_path = store.build_export(["tester01"])
            with zipfile.ZipFile(export_path) as archive:
                csv_text = archive.read("essay_versions.csv").decode("utf-8-sig")
                raw_events = [
                    json.loads(line)
                    for line in archive.read("raw/events.jsonl").decode("utf-8").splitlines()
                ]
                raw_event = next(
                    item for item in raw_events if item["event_type"] == "essay_snapshot"
                )

            self.assertIn("'=HYPERLINK", csv_text)
            self.assertEqual(
                json.loads(raw_event["payload_json"])["text"],
                "=HYPERLINK(\"unsafe\")",
            )


if __name__ == "__main__":
    unittest.main()

import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import research_data
from auth import create_password_hash
from main import app
from research_data import ResearchStore


class ResearchApiTests(unittest.TestCase):
    def test_consent_collection_event_capture_and_admin_export(self):
        environment = {
            "APP_AUTH_ENABLED": "true",
            "APP_TEST_USERS": "tester01,tester02",
            "APP_SHARED_PASSWORD_HASH": create_password_hash("shared-test-password", iterations=1_000),
            "APP_SESSION_SECRET": "research-api-test-session-secret",
            "APP_COOKIE_SECURE": "false",
            "APP_RESEARCH_LOGGING_ENABLED": "true",
            "APP_RESEARCH_CONSENT_REQUIRED": "true",
            "APP_RESEARCH_CONSENT_VERSION": "test-consent-v1",
            "APP_RESEARCH_ADMIN_KEY": "research-admin-key-that-is-long-enough",
        }
        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(os.environ, environment, clear=False):
            original_store = research_data._default_store
            research_data._default_store = ResearchStore(Path(temp_dir))
            try:
                client = TestClient(app)
                rejected = client.post(
                    "/api/auth/login",
                    json={"username": "tester01", "password": "shared-test-password"},
                )
                self.assertEqual(rejected.status_code, 400)

                login = client.post(
                    "/api/auth/login",
                    json={
                        "username": "tester01",
                        "password": "shared-test-password",
                        "consent_granted": True,
                        "consent_version": "test-consent-v1",
                        "consented_at": "2026-09-01T10:00:00.000Z",
                    },
                )
                self.assertEqual(login.status_code, 200)

                session_id = "session-api-test-0001"
                started = client.post(
                    "/api/research/sessions/start",
                    json={
                        "session_id": session_id,
                        "client_started_at": "2026-09-01T10:00:01.000Z",
                        "metadata": {"viewport": {"width": 1440, "height": 900}},
                    },
                )
                self.assertEqual(started.status_code, 200)

                events = client.post(
                    "/api/research/events",
                    json={
                        "session_id": session_id,
                        "events": [
                            {
                                "event_id": "event-api-0000001",
                                "event_type": "essay_snapshot",
                                "source": "frontend",
                                "occurred_at": "2026-09-01T10:00:02.000Z",
                                "stage": "drafting",
                                "payload": {"text": "A test essay", "word_count": 3},
                            }
                        ],
                    },
                )
                self.assertEqual(events.status_code, 200)
                self.assertEqual(events.json()["accepted"], 1)

                artifact = client.post(
                    "/api/research/artifacts",
                    headers={"x-vividwrite-session": session_id},
                    data={"category": "original_task_image", "metadata_json": "{}"},
                    files={"image": ("task.png", io.BytesIO(b"image-data"), "image/png")},
                )
                self.assertEqual(artifact.status_code, 200)

                unauthorised_admin = client.get("/api/research/admin/participants")
                self.assertEqual(unauthorised_admin.status_code, 401)
                admin_headers = {"x-research-admin-key": environment["APP_RESEARCH_ADMIN_KEY"]}
                participants = client.get(
                    "/api/research/admin/participants",
                    headers=admin_headers,
                )
                self.assertEqual(participants.status_code, 200)
                self.assertEqual(participants.json()["participant_count"], 2)
                by_user = {
                    item["username"]: item
                    for item in participants.json()["participants"]
                }
                self.assertEqual(by_user["tester01"]["session_count"], 1)
                self.assertEqual(by_user["tester02"]["session_count"], 0)

                export = client.get(
                    "/api/research/admin/export/tester01",
                    headers=admin_headers,
                )
                self.assertEqual(export.status_code, 200)
                self.assertEqual(export.headers["content-type"], "application/zip")
                self.assertGreater(len(export.content), 500)
            finally:
                research_data._default_store = original_store


if __name__ == "__main__":
    unittest.main()

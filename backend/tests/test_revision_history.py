import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from revision_history import RevisionHistoryStore, router


class RevisionHistoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = RevisionHistoryStore(Path(self.temp.name) / "history.sqlite3")

    def save(self, username="alice", image=b"chart", chart_type="bar", **kwargs):
        return self.store.save(
            username, image, chart_type, kwargs.get("reference", "A | 10"),
            kwargs.get("essay", "The figure shows a rise."),
            {"title": "Practice", "move_feedback": {"version": "1.0", "assessments": [
                {"code": "move_1", "status": "effective", "excerpt": "The figure"}]},
             "records": [{"category": "A", "value": 10}]},
            "/charts/test.png", "/uploads/input.png",
        )

    def test_snapshots_are_immutable_and_survive_store_reopen(self):
        first = self.save()
        first["assessments"][0]["status"] = "developing"
        second = self.save(essay="The figure now shows its subject.")
        reopened = RevisionHistoryStore(self.store.path)
        rows = reopened.list("alice", first["task_id"])
        self.assertEqual([item["sequence"] for item in rows], [2, 1])
        self.assertEqual(rows[1]["assessments"][0]["status"], "effective")
        self.assertEqual(rows[0]["essay"], second["essay"])
        self.assertNotEqual(first["id"], second["id"])

    def test_users_tasks_and_chart_types_are_isolated(self):
        alice = self.save()
        bob = self.save(username="bob")
        other = self.save(image=b"new chart")
        line = self.save(chart_type="line")
        self.assertEqual(len(self.store.list("alice", alice["task_id"])), 1)
        self.assertNotEqual(alice["task_id"], other["task_id"])
        self.assertNotEqual(alice["task_id"], line["task_id"])
        self.assertEqual(bob["sequence"], 1)
        self.assertEqual(self.store.list("unknown", alice["task_id"]), [])

    def test_reference_changes_remain_identifiable(self):
        old = self.save()
        new = self.save(reference="A | 12")
        self.assertEqual(old["task_id"], new["task_id"])
        self.assertNotEqual(old["reference_id"], new["reference_id"])

    def test_value_tolerance_model_and_evidence_survive_history_storage(self):
        result = {"chart_type": "bar", "axes": {"unit": "%"},
                  "comparison": {"accepted_value_tolerance": 2},
                  "style": {"analysis_model": "test-model"},
                  "records": [{"category": "A", "value": 47, "official_value": 42,
                               "explicit_student_value": True, "student_evidence": "A was 47%."}]}
        saved = self.store.save("alice", b"chart", "bar", "A | 42", "A was 47%.", result, "/charts/test.png", "/uploads/test.png")
        loaded = self.store.list("alice", saved["task_id"])[0]
        self.assertEqual(loaded["value_tolerance"], 2)
        self.assertEqual(loaded["analysis_model"], "test-model")
        self.assertEqual(loaded["records"][0]["student_evidence"], "A was 47%.")

    def test_concurrent_reviews_and_pagination(self):
        # Create the schema before the concurrent requests, as on a running server.
        first = self.save()
        with ThreadPoolExecutor(max_workers=4) as executor:
            snapshots = list(executor.map(lambda _: self.save(), range(8)))
        self.assertEqual(sorted(item["sequence"] for item in snapshots), list(range(2, 10)))
        rows = self.store.list("alice", first["task_id"], before=5, limit=2)
        self.assertEqual([row["sequence"] for row in rows], [4, 3])

    def test_api_requires_identity_and_never_accepts_another_username(self):
        snapshot = self.save()
        app = FastAPI()
        app.include_router(router)
        with TestClient(app) as client:
            with patch("revision_history.history_username", return_value=None):
                self.assertEqual(client.get(f'/api/revision-history/{snapshot["task_id"]}').status_code, 401)
            with patch("revision_history.history_username", return_value="bob"), patch(
                "revision_history.RevisionHistoryStore", return_value=self.store,
            ):
                response = client.get(f'/api/revision-history/{snapshot["task_id"]}?username=alice')
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["revisions"], [])

    def test_successful_analysis_archives_result_and_failure_does_not(self):
        from main import app
        chart_data = {"chart_type": "bar", "records": [], "move_feedback": {
            "version": "1.0", "assessments": [{"code": "move_1", "status": "effective"}]}}
        with patch("auth.auth_enabled", return_value=False), patch(
            "main.history_username", return_value="alice",
        ), patch("main.RevisionHistoryStore", return_value=self.store), patch(
            "main.UPLOADS_DIR", Path(self.temp.name) / "uploads",
        ), patch("main.archive_file_for_request", return_value=None), patch(
            "main.record_server_event_for_request",
        ), patch("main.HybridFeedbackService") as service, TestClient(app) as client:
            service.return_value.generate.return_value = (chart_data, "test.png")
            form = {"chart_type": "bar", "requirement": "Describe", "student_answer": "My first draft.",
                    "deplot_text": "A | 10"}
            result = client.post("/api/analyze-chart-with-image", data=form,
                                 files={"image": ("image.png", b"chart", "image/png")}).json()
            self.assertTrue(result["success"])
            self.assertEqual(result["analysis_revision"]["essay"], "My first draft.")
            self.assertEqual(result["analysis_revision"]["chart_url"], "/charts/test.png")
            task_id = result["analysis_revision"]["task_id"]
            service.return_value.generate.side_effect = RuntimeError("Analysis failed")
            failed = client.post("/api/analyze-chart-with-image", data=form,
                                 files={"image": ("image.png", b"chart", "image/png")}).json()
            self.assertFalse(failed["success"])
            self.assertEqual(len(self.store.list("alice", task_id)), 1)

    def test_storage_failure_does_not_discard_successful_feedback(self):
        from main import app
        with patch("auth.auth_enabled", return_value=False), patch(
            "main.history_username", return_value="alice",
        ), patch("main.UPLOADS_DIR", Path(self.temp.name) / "uploads"), patch(
            "main.archive_file_for_request", return_value=None,
        ), patch("main.record_server_event_for_request"), patch(
            "main.HybridFeedbackService",
        ) as service, patch("main.RevisionHistoryStore.save", side_effect=OSError("Disk full")), TestClient(app) as client:
            service.return_value.generate.return_value = ({"chart_type": "bar", "records": []}, "test.png")
            result = client.post("/api/analyze-chart-with-image", data={
                "chart_type": "bar", "requirement": "Describe", "student_answer": "Draft",
            }, files={"image": ("image.png", b"chart", "image/png")}).json()
            self.assertTrue(result["success"])
            self.assertIsNone(result["analysis_revision"])
            self.assertIn("could not be saved", result["history_warning"])


if __name__ == "__main__":
    unittest.main()

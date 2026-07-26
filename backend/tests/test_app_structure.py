import unittest

from main import app, generate_revision_suggestions


class AppStructureTests(unittest.TestCase):
    def test_only_business_routes_remain(self):
        paths = set(app.openapi()["paths"])

        self.assertIn("/health", paths)
        self.assertIn("/api/auth/login", paths)
        self.assertIn("/api/auth/me", paths)
        self.assertIn("/api/auth/logout", paths)
        self.assertIn("/api/deplot-extract", paths)
        self.assertIn("/api/analyze-chart-with-image", paths)
        self.assertIn("/api/generate-spatial-sample-essay", paths)
        self.assertNotIn("/api/hello", paths)
        self.assertNotIn("/api/echo", paths)
        self.assertNotIn("/api/analyze-chart", paths)

    def test_revision_suggestions_report_missing_and_short_answers(self):
        suggestions = generate_revision_suggestions(
            {"records": [{"missing": True}, {"estimated": True}]},
            "A short answer",
        )
        types = {item["type"] for item in suggestions}

        self.assertEqual(types, {"data_completeness", "data_accuracy", "length"})


if __name__ == "__main__":
    unittest.main()

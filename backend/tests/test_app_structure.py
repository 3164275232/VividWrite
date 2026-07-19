import unittest

from main import app, generate_revision_suggestions


class AppStructureTests(unittest.TestCase):
    def test_only_business_routes_remain(self):
        paths = {getattr(route, "path", None) for route in app.routes}

        self.assertIn("/health", paths)
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

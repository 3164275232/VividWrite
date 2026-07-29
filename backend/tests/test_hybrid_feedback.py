import tempfile
import unittest
from pathlib import Path

from hybrid_feedback import HybridFeedbackService


class FakeStatisticalService:
    def __init__(self):
        self.kwargs = None

    def generate(self, **kwargs):
        self.kwargs = kwargs
        return {"style": {"renderer": "vega-lite"}, "records": []}, "statistical.png"


class FakeSpatialService:
    def __init__(self):
        self.kwargs = None

    def generate(self, **kwargs):
        self.kwargs = kwargs
        return {"style": {"renderer": "generative-image"}, "records": []}, "spatial.png"


class HybridFeedbackTests(unittest.TestCase):
    def test_routes_statistical_chart_to_vega_pipeline(self):
        statistical = FakeStatisticalService()
        spatial = FakeSpatialService()
        with tempfile.TemporaryDirectory() as folder:
            result, filename = HybridFeedbackService(
                folder, statistical_service=statistical, spatial_service=spatial
            ).generate(
                chart_type="line",
                requirement="Summarise the chart.",
                student_answer="The value increased.",
                deplot_text="TITLE | Test",
            )
        self.assertEqual(filename, "statistical.png")
        self.assertEqual(result["style"]["renderer"], "vega-lite")
        self.assertEqual(statistical.kwargs["chart_type"], "line")
        self.assertIsNone(spatial.kwargs)

    def test_routes_map_to_spatial_image_pipeline_without_deplot(self):
        statistical = FakeStatisticalService()
        spatial = FakeSpatialService()
        with tempfile.TemporaryDirectory() as folder:
            image_path = Path(folder) / "map.png"
            image_path.write_bytes(b"reference")
            result, filename = HybridFeedbackService(
                folder, statistical_service=statistical, spatial_service=spatial
            ).generate(
                chart_type="map",
                requirement="Describe the changes.",
                student_answer="A road was built east of the river.",
                image_path=image_path,
            )
        self.assertEqual(filename, "spatial.png")
        self.assertEqual(result["style"]["renderer"], "generative-image")
        self.assertEqual(spatial.kwargs["task_type"], "map")
        self.assertIsNone(statistical.kwargs)

    def test_routes_map_to_dedicated_verified_map_pipeline(self):
        statistical = FakeStatisticalService()
        fallback_spatial = FakeSpatialService()
        map_service = FakeSpatialService()
        with tempfile.TemporaryDirectory() as folder:
            image_path = Path(folder) / "map.png"
            image_path.write_bytes(b"reference")
            result, filename = HybridFeedbackService(
                folder,
                statistical_service=statistical,
                spatial_service=fallback_spatial,
                map_service=map_service,
            ).generate(
                chart_type="map",
                requirement="Describe the changes.",
                student_answer="The school was replaced by a restaurant.",
                image_path=image_path,
            )

        self.assertEqual(filename, "spatial.png")
        self.assertEqual(result["style"]["renderer"], "generative-image")
        self.assertEqual(map_service.kwargs["task_type"], "map")
        self.assertIsNone(fallback_spatial.kwargs)
        self.assertIsNone(statistical.kwargs)

    def test_routes_process_to_deterministic_process_pipeline(self):
        statistical = FakeStatisticalService()
        map_service = FakeSpatialService()
        process_service = FakeSpatialService()
        with tempfile.TemporaryDirectory() as folder:
            image_path = Path(folder) / "process.png"
            image_path.write_bytes(b"reference")
            result, filename = HybridFeedbackService(
                folder,
                statistical_service=statistical,
                spatial_service=map_service,
                process_service=process_service,
            ).generate(
                chart_type="process",
                requirement="Describe the process.",
                student_answer="The material is carried by plane.",
                image_path=image_path,
            )

        self.assertEqual(filename, "spatial.png")
        self.assertEqual(result["style"]["renderer"], "generative-image")
        self.assertEqual(process_service.kwargs["task_type"], "process")
        self.assertIsNone(map_service.kwargs)
        self.assertIsNone(statistical.kwargs)

    def test_spatial_json_call_requires_an_image(self):
        with tempfile.TemporaryDirectory() as folder:
            service = HybridFeedbackService(folder, spatial_service=FakeSpatialService())
            with self.assertRaisesRegex(ValueError, "original image upload endpoint"):
                service.generate(
                    chart_type="process",
                    requirement="Describe the process.",
                    student_answer="Water is heated.",
                )


if __name__ == "__main__":
    unittest.main()

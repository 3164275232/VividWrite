"""Route statistical charts and spatial IELTS tasks to different renderers."""

from __future__ import annotations

from pathlib import Path

from chart_feedback import ChartFeedbackService, SUPPORTED_CHART_TYPES
from map_feedback_renderer import MapFeedbackService
from process_feedback_renderer import ProcessFeedbackService
from wan_image_renderer import SPATIAL_TASK_TYPES, WanSpatialFeedbackService


ALL_FEEDBACK_TYPES = SUPPORTED_CHART_TYPES | SPATIAL_TASK_TYPES


class HybridFeedbackService:
    def __init__(
        self,
        output_dir: str | Path,
        statistical_service=None,
        spatial_service=None,
        map_service=None,
        process_service=None,
    ):
        self.output_dir = Path(output_dir)
        self.statistical_service = statistical_service
        self.spatial_service = spatial_service
        self.map_service = map_service
        self.process_service = process_service

    def generate(
        self,
        *,
        chart_type: str,
        requirement: str,
        student_answer: str,
        deplot_text: str = "",
        image_path: str | Path | None = None,
    ) -> tuple[dict, str]:
        task_type = (chart_type or "auto").strip().lower()
        if task_type not in ALL_FEEDBACK_TYPES:
            raise ValueError(f"Unsupported IELTS visual type: {task_type}")
        if task_type in SPATIAL_TASK_TYPES:
            if not image_path:
                raise ValueError("Map and process feedback require the original image upload endpoint.")
            if task_type == "process":
                service = (
                    self.process_service
                    or self.spatial_service
                    or ProcessFeedbackService(self.output_dir)
                )
            else:
                service = (
                    self.map_service
                    or self.spatial_service
                    or MapFeedbackService(self.output_dir)
                )
            return service.generate(
                task_type=task_type,
                requirement=requirement,
                student_answer=student_answer,
                image_path=image_path,
            )

        service = self.statistical_service or ChartFeedbackService(self.output_dir)
        return service.generate(
            chart_type=task_type,
            requirement=requirement,
            student_answer=student_answer,
            deplot_text=deplot_text,
            image_path=image_path,
        )

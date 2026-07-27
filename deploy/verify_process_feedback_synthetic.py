"""Verify the live Qwen process pipeline using synthetic, non-user data."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from process_feedback_renderer import ProcessFeedbackService, render_process_feedback


source_stages = [
    "Material placed in bins",
    "Collected by recycling truck",
    "Sorted by colour",
    "Washed with water",
    "Crushed into small pieces",
    "Melted in a furnace",
    "Moulded into new containers",
    "Delivered to shops",
]
source_plan = {
    "source_title": "A synthetic recycling process",
    "source_subtitle": "A cyclical eight-stage process",
    "cyclical": True,
    "cycle_evidence": "The cycle then starts again",
    "stages": [
        {
            "number": index,
            "student_label": label,
            "status": "accurate",
        }
        for index, label in enumerate(source_stages, start=1)
    ],
}
student_answer = (
    "Material is first placed in bins. It is collected by a huge plane and then "
    "sorted by colour. Next, it is washed with water and crushed into small pieces. "
    "The pieces are melted in a furnace, moulded into new containers and delivered "
    "to shops. The cycle then starts again."
)

with tempfile.TemporaryDirectory() as folder:
    root = Path(folder)
    source_path = root / "synthetic-source.png"
    render_process_feedback(source_plan, source_path)
    result, filename = ProcessFeedbackService(root).generate(
        task_type="process",
        requirement="Describe the synthetic process.",
        student_answer=student_answer,
        image_path=source_path,
    )
    stage_two = result["records"][1]
    print(
        json.dumps(
            {
                "output_exists": (root / filename).is_file(),
                "stage_count": len(result["records"]),
                "stage_two_label": stage_two["value"],
                "stage_two_status": stage_two["feedback_status"],
                "truck_in_student_labels": any(
                    "truck" in str(record["value"] or "").casefold()
                    for record in result["records"]
                ),
                "renderer": result["style"]["renderer"],
            }
        )
    )

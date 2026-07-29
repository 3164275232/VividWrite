"""Verify explicit student line values with synthetic, non-user data."""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

from chart_feedback import ChartFeedbackService


deplot_text = (
    "Year | Bus | Rail | Metro<0x0A>2010 | 1.8 | 1.1 | 0.8<0x0A>"
    "2012 | 1.9 | 1.3 | 1.0<0x0A>2014 | 1.7 | 1.5 | 1.2<0x0A>"
    "2016 | 1.6 | 1.8 | 1.5<0x0A>2018 | 1.5 | 2.0 | 1.7<0x0A>"
    "2020 | 1.3 | 2.2 | 1.9"
)
student_answer = (
    "In 2010, buses carried 1.8 million passengers, compared with 4.1 million "
    "for rail and 0.8 million for metro. Rail changed steadily from 4.1 million "
    "in 2010 to 1.5 million in 2014, then reached 1.8 million in 2016, "
    "2.0 million in 2018 and 2.2 million in 2020."
)

with tempfile.TemporaryDirectory() as folder:
    result, filename = ChartFeedbackService(Path(folder)).generate(
        chart_type="line",
        requirement="Summarise this synthetic public-transport chart.",
        student_answer=student_answer,
        deplot_text=deplot_text,
    )
    rail_2010 = next(
        record
        for record in result["records"]
        if record.get("feedback_label") == "2010 - Rail"
    )
    rendered = next(
        record
        for record in result["vega_lite_spec"]["data"]["values"]
        if record.get("feedback_label") == "2010 - Rail"
    )
    shutil.copy2(Path(folder) / filename, "/tmp/explicit-line-smoke.png")
    print(
        json.dumps(
            {
                "output_exists": (Path(folder) / filename).is_file(),
                "student_value": rail_2010.get("value"),
                "official_value": rail_2010.get("official_value"),
                "feedback_status": rail_2010.get("feedback_status"),
                "explicit_student_value": rail_2010.get("explicit_student_value"),
                "rendered_error_value": rendered.get("_line_error_value"),
                "rendered_feedback_label": rendered.get("_line_feedback_label"),
                "issues": result["comparison"].get("incorrect_official_items"),
            }
        )
    )

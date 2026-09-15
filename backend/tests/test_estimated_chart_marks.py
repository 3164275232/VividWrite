import copy
import json
import unittest

import vl_convert as vlc

from chart_renderer import ESTIMATE_STROKE, prepare_vega_lite_spec


class EstimatedChartMarksTests(unittest.TestCase):
    def records(self):
        return [
            {"category": "2010", "period": "2010", "series": "Rail", "value": 10,
             "explicit_student_value": True},
            {"category": "2015", "period": "2015", "series": "Rail", "value": 15,
             "estimated": True, "feedback_status": "estimated"},
            {"category": "2020", "period": "2020", "series": "Rail", "value": 20,
             "explicit_student_value": True},
        ]

    def spec(self, chart_type):
        return {"mark": chart_type, "encoding": {
            "x": {"field": "category", "type": "ordinal"},
            "y": {"field": "value", "type": "quantitative"},
            "color": {"field": "series", "type": "nominal"},
        }}

    def test_line_and_bar_mark_only_estimates_without_changing_values(self):
        for chart_type in ("bar", "line", "area"):
            with self.subTest(chart_type=chart_type):
                records = self.records()
                original = copy.deepcopy(records)
                spec = prepare_vega_lite_spec(self.spec(chart_type), records, "Travel", chart_type=chart_type)
                self.assertEqual(records, original)
                self.assertEqual([row["_estimate_value"] for row in spec["data"]["values"]], [None, 15, None])
                self.assertEqual(spec["layer"][-1]["mark"]["shape"], "diamond")
                self.assertEqual(spec["layer"][-1]["mark"]["stroke"], ESTIMATE_STROKE)
                self.assertTrue(any("system estimates" in line for line in spec["title"]["subtitle"]))
                svg = vlc.vegalite_to_svg(json.dumps(spec))
                self.assertIn("system estimates", svg)
                self.assertIn(ESTIMATE_STROKE, svg)

    def test_pie_estimate_marker_is_inside_the_matching_sector(self):
        records = [{"category": "A", "value": 40, "estimated": True},
                   {"category": "B", "value": 60}]
        spec = prepare_vega_lite_spec({}, records, "Spending", chart_type="pie", unit="%")
        first, second = spec["data"]["values"]
        self.assertGreater(first["_estimate_x"], 300)
        self.assertLess(first["_estimate_y"], 210)
        self.assertIsNone(second["_estimate_x"])
        self.assertIn(ESTIMATE_STROKE, vlc.vegalite_to_svg(json.dumps(spec)))

    def test_estimate_points_use_the_same_stack_as_bar_and_area_segments(self):
        for chart_type in ("bar", "area"):
            for stack_mode in ("zero", "normalize", "center"):
                with self.subTest(chart_type=chart_type, stack=stack_mode):
                    records = [{"category": "2010", "series": "A", "value": 40, "estimated": True},
                               {"category": "2010", "series": "B", "value": 60},
                               {"category": "2020", "series": "A", "value": 45},
                               {"category": "2020", "series": "B", "value": 65}]
                    source = self.spec(chart_type)
                    source["encoding"]["y"]["stack"] = stack_mode
                    spec = prepare_vega_lite_spec(source, records, "Stacked chart", chart_type=chart_type)
                    overlay = spec["layer"][-1]["encoding"]
                    self.assertEqual(overlay["y"]["stack"], stack_mode)
                    self.assertEqual(overlay["detail"]["field"], "series")
                    self.assertEqual([row["_estimate_value"] for row in spec["data"]["values"]], [40, 60, 45, 65])
                    self.assertEqual([row["_estimate_opacity"] for row in spec["data"]["values"]], [1, 0, 0, 0])
                    compiled = vlc.vegalite_to_vega(spec)
                    stacks = [t for data in compiled["data"] for t in data.get("transform", []) if t["type"] == "stack"]
                    self.assertEqual(len(stacks), 2)
                    self.assertEqual(stacks[0]["offset"], stacks[1]["offset"])
                    self.assertEqual(stacks[0]["groupby"], stacks[1]["groupby"])
                    self.assertIn(ESTIMATE_STROKE, vlc.vegalite_to_svg(json.dumps(spec)))

    def test_explicit_and_missing_points_never_get_estimate_marks(self):
        records = self.records()
        records[0]["estimated"] = True
        records[1]["missing"] = True
        spec = prepare_vega_lite_spec(self.spec("line"), records, "Travel", chart_type="line")
        self.assertFalse(any("diamonds" in line for line in spec["title"]["subtitle"]))
        self.assertNotIn("_estimate_value", spec["data"]["values"][0])

    def test_estimates_do_not_remove_error_marks_or_offsets(self):
        records = self.records()
        records[0].update(feedback_status="incorrect", official_value=12)
        source = self.spec("bar")
        source["encoding"]["xOffset"] = {"field": "series"}
        spec = prepare_vega_lite_spec(source, records, "Travel", chart_type="bar")
        self.assertEqual(spec["layer"][-1]["encoding"]["xOffset"], {"field": "series"})
        self.assertEqual(spec["data"]["values"][0]["_bar_error_value"], 10)
        self.assertIsNone(spec["data"]["values"][0]["_estimate_value"])
        self.assertEqual(spec["data"]["values"][1]["_estimate_value"], 15)
        self.assertIn("YOU: 10", vlc.vegalite_to_svg(json.dumps(spec)))

    def test_missing_line_points_get_dashed_connections_without_invented_values(self):
        records = self.records()
        records[1].update(value=None, missing=True, estimated=False)
        original = copy.deepcopy(records)
        spec = prepare_vega_lite_spec(self.spec("line"), records, "Travel", chart_type="line")
        self.assertEqual(records, original)
        rows = spec["data"]["values"]
        self.assertIsNone(rows[1]["value"])
        self.assertNotEqual(rows[0]["_line_run"], rows[2]["_line_run"])
        self.assertEqual(rows[2]["_connection_from_x"], "2010")
        self.assertEqual(rows[2]["_connection_from_value"], 10)
        self.assertEqual(spec["usermeta"]["vividwrite"]["inferred_connection_count"], 1)
        svg = vlc.vegalite_to_svg(json.dumps(spec))
        self.assertIn('stroke-dasharray="6,4"', svg)
        self.assertIn('Dashed lines: system connections', svg)

    def test_estimates_have_dashed_connections_and_explicit_adjacent_points_stay_solid(self):
        records = self.records()
        records.append({"category": "2025", "period": "2025", "series": "Rail",
                        "value": 25, "explicit_student_value": True})
        spec = prepare_vega_lite_spec(self.spec("line"), records, "Travel", chart_type="line")
        rows = spec["data"]["values"]
        self.assertEqual(spec["usermeta"]["vividwrite"]["inferred_connection_count"], 2)
        self.assertEqual(rows[2]["_line_run"], rows[3]["_line_run"])
        self.assertNotEqual(rows[0]["_line_run"], rows[1]["_line_run"])
        self.assertIn(ESTIMATE_STROKE, vlc.vegalite_to_svg(json.dumps(spec)))

    def test_dashed_connections_do_not_cross_between_series_or_overwrite_error_values(self):
        records = self.records()
        records[2].update(feedback_status="incorrect", official_value=30)
        records += [{**row, "series": "Bus", "value": row["value"] * 2} for row in self.records()]
        spec = prepare_vega_lite_spec(self.spec("line"), records, "Travel", chart_type="line")
        rows = spec["data"]["values"]
        self.assertEqual(rows[1]["_connection_from_value"], 10)
        self.assertEqual(rows[4]["_connection_from_value"], 20)
        self.assertEqual(rows[2]["_line_error_value"], 20)
        svg = vlc.vegalite_to_svg(json.dumps(spec))
        self.assertIn('YOU: 20', svg)
        self.assertIn('stroke-dasharray="6,4"', svg)


if __name__ == "__main__":
    unittest.main()

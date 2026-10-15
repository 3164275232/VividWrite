import copy
import json
import unittest
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image

import vl_convert as vlc

from chart_renderer import ESTIMATE_STROKE, prepare_vega_lite_spec, render_prepared_svg, render_vega_lite_png


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

    def hatches(self, spec):
        return [node for node in ET.fromstring(render_prepared_svg(spec)).iter()
                if node.get("data-vividwrite-inferred") == "true"]

    def test_bar_line_and_area_hatch_only_inferred_shapes_and_export_real_png(self):
        for chart_type in ("bar", "line", "area"):
            with self.subTest(chart_type=chart_type), tempfile.TemporaryDirectory() as directory:
                records = self.records()
                original = copy.deepcopy(records)
                path = Path(directory) / 'chart.png'
                spec = render_vega_lite_png(self.spec(chart_type), records, "Travel", path, chart_type=chart_type)
                self.assertEqual(records, original)
                self.assertEqual(len(self.hatches(spec)), 1)
                self.assertIn('Diagonal stripes: system-inferred', render_prepared_svg(spec))
                with Image.open(path) as png:
                    self.assertGreater(png.width, 700)
                    self.assertGreater(png.height, 400)
                if chart_type == 'line':
                    self.assertEqual(spec['layer'][-1]['mark']['shape'], 'circle')

    def test_pie_hatches_the_actual_sector_without_changing_other_sectors(self):
        records = [{"category": "A", "value": 40, "estimated": True},
                   {"category": "B", "value": 60, "explicit_student_value": True}]
        spec = prepare_vega_lite_spec({}, records, "Spending", chart_type="pie", unit="%")
        source = ET.fromstring(vlc.vegalite_to_svg(json.dumps(spec)))
        sector = next(node for node in source.iter() if node.get('aria-label') == 'System-inferred: A')
        hatches = self.hatches(spec)
        self.assertEqual(len(hatches), 1)
        self.assertEqual(hatches[0].get('d'), sector.get('d'))
        self.assertEqual(hatches[0].get('transform'), sector.get('transform'))
        self.assertIn('Stated in report: B', render_prepared_svg(spec))

    def test_grouped_horizontal_and_stacked_bars_keep_exact_geometry(self):
        for orientation in ('vertical', 'horizontal'):
            for stack_mode in ('zero', 'normalize', 'center', None):
                with self.subTest(orientation=orientation, stack=stack_mode):
                    records = [{"category": "2010", "series": "A", "value": 40, "estimated": True},
                               {"category": "2010", "series": "B", "value": 60},
                               {"category": "2020", "series": "A", "value": 45},
                               {"category": "2020", "series": "B", "value": 65}]
                    source = self.spec('bar')
                    source['encoding']['y']['stack'] = stack_mode
                    if stack_mode is None:
                        source['encoding']['xOffset'] = {'field': 'series'}
                    if orientation == 'horizontal':
                        source['encoding']['x'], source['encoding']['y'] = source['encoding']['y'], source['encoding']['x']
                        if 'xOffset' in source['encoding']:
                            source['encoding']['yOffset'] = source['encoding'].pop('xOffset')
                    spec = prepare_vega_lite_spec(source, records, "Stacked chart", chart_type='bar')
                    svg = ET.fromstring(vlc.vegalite_to_svg(json.dumps(spec)))
                    bar = next(node for node in svg.iter() if node.get('aria-label') == 'System-inferred: 2010 / A')
                    hatches = self.hatches(spec)
                    self.assertEqual(len(hatches), 1)
                    for attr in ('d', 'x', 'y', 'width', 'height', 'transform'):
                        self.assertEqual(hatches[0].get(attr), bar.get(attr))

    def test_stacked_area_estimated_points_keep_the_stack_offset(self):
        source = self.spec('area')
        source['encoding']['y']['stack'] = 'normalize'
        records = [{'category': '2010', 'series': 'A', 'value': 40, 'estimated': True},
                   {'category': '2010', 'series': 'B', 'value': 60}]
        spec = prepare_vega_lite_spec(source, records, 'Area', chart_type='area')
        stacks = [transform for data in vlc.vegalite_to_vega(spec)['data']
                  for transform in data.get('transform', []) if transform['type'] == 'stack']
        self.assertEqual(len(stacks), 2)
        self.assertEqual(stacks[0]['offset'], stacks[1]['offset'])
        self.assertEqual(len(self.hatches(spec)), 1)

    def test_explicit_missing_and_invalid_values_never_get_hatching(self):
        records = self.records()
        records[0]['estimated'] = True
        records[1]['missing'] = True
        spec = prepare_vega_lite_spec(self.spec('line'), records, 'Travel', chart_type='line')
        self.assertEqual(self.hatches(spec), [])
        self.assertEqual(spec['usermeta']['vividwrite']['estimated_value_count'], 0)

    def test_hatching_does_not_replace_explicit_error_cues(self):
        records = self.records()
        records[0].update(feedback_status='incorrect', official_value=12)
        source = self.spec('bar')
        source['encoding']['xOffset'] = {'field': 'series'}
        spec = prepare_vega_lite_spec(source, records, 'Travel', chart_type='bar')
        self.assertEqual(spec['data']['values'][0]['_bar_error_value'], 10)
        self.assertEqual(len(self.hatches(spec)), 1)
        self.assertIn('YOU: 10', render_prepared_svg(spec))

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

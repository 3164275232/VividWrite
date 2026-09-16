import unittest

from chart_feedback import (_enforce_explicit_cartesian_values, _enforce_explicit_pie_values,
                            _annotate_bar_accuracy, _annotate_pie_accuracy,
                            _interpolate_supported_temporal_gaps)
from chart_inference import infer_supported_comparisons, finalise_provenance
from chart_renderer import prepare_vega_lite_spec, render_prepared_svg


class ChartInferenceTests(unittest.TestCase):
    def chart(self, chart_type='bar', essay='A stood at 40% in 2020. B was half of A in 2020.'):
        table = 'City | 2020\nA | 42\nB | 30'
        result = {'chart_type': chart_type, 'axes': {'unit': '%'}, 'records': []}
        _enforce_explicit_cartesian_values(result, table, essay)
        infer_supported_comparisons(result, essay)
        _annotate_bar_accuracy(result, table)
        finalise_provenance(result)
        return result

    def test_bar_ratio_uses_student_anchor_not_official_value(self):
        result = self.chart()
        first, second = result['records']
        self.assertEqual(first['value'], 40)
        self.assertEqual(first['data_source'], 'stated')
        self.assertEqual(second['value'], 20)
        self.assertTrue(second['estimated'])
        self.assertFalse(second['explicit_student_value'])
        self.assertEqual(second['feedback_status'], 'estimated')
        self.assertNotIn('B: student', ' '.join(result['comparison']['incorrect_official_items']))
        self.assertEqual(second['inference']['student_evidence'], 'B was half of A in 2020.')
        spec = prepare_vega_lite_spec({'mark': 'bar', 'encoding': {
            'x': {'field': 'category', 'type': 'nominal'}, 'y': {'field': 'value', 'type': 'quantitative'}}},
            result['records'], 'Inferred values', chart_type='bar')
        self.assertIn('data-vividwrite-inferred="true"', render_prepared_svg(spec))

    def test_difference_requires_compatible_units(self):
        chart = self.chart(essay='A stood at 40% in 2020. B was 5 percentage points lower than A in 2020.')
        self.assertEqual(chart['records'][1]['value'], 35)
        chart = self.chart(essay='A stood at 40% in 2020. B was 5 million lower than A in 2020.')
        self.assertIsNone(chart['records'][1]['value'])

    def test_no_anchor_qualitative_only_ambiguous_or_contradictory_claims_stay_empty(self):
        for essay in ('B was half of A in 2020.', 'A stood at 40% in 2020. B was lower than A.',
                      'A stood at 40% in 2020. B was half of A. B was twice A.',
                      'A stood at 40% in 2020. B was not half of A.',
                      'A stood at 40% in 2020. If B was half of A, it would be lower.',
                      'A stood at 40% in 2020. Perhaps B was half of A.'):
            with self.subTest(essay=essay):
                self.assertIsNone(self.chart(essay=essay)['records'][1]['value'])
        result = {'chart_type': 'bar', 'records': [
            {'category': 'A', 'series': '2015', 'value': 40, 'explicit_student_value': True},
            {'category': 'B', 'series': '2015', 'value': None},
            {'category': 'A', 'series': '2020', 'value': 60, 'explicit_student_value': True},
            {'category': 'B', 'series': '2020', 'value': None}]}
        infer_supported_comparisons(result, 'B was half of A.')
        self.assertIsNone(result['records'][1]['value'])
        self.assertIsNone(result['records'][3]['value'])

    def test_explicit_value_wins_over_inference(self):
        chart = self.chart(essay='A stood at 40% in 2020. B was half of A. B stood at 25% in 2020.')
        self.assertEqual(chart['records'][1]['value'], 25)
        self.assertFalse(chart['records'][1]['estimated'])

    def test_pie_relation_survives_explicit_value_enforcement(self):
        table = 'Category | Percentage\nHousing | 40%\nFood | 30%\nOther | 30%'
        essay = 'Housing accounted for 40%. Food was half of Housing.'
        result = {'chart_type': 'pie', 'axes': {'unit': '%'}, 'records': []}
        _enforce_explicit_pie_values(result, table, essay)
        infer_supported_comparisons(result, essay)
        _annotate_pie_accuracy(result, table)
        finalise_provenance(result)
        self.assertEqual(result['records'][1]['value'], 20)
        self.assertEqual(result['records'][1]['feedback_status'], 'estimated')
        self.assertIsNone(result['records'][2]['value'])

    def test_pie_remainder_requires_explicit_description_and_stated_other_shares(self):
        table = 'Category | Percentage\nHousing | 40%\nFood | 30%\nOther | 30%'
        for suffix, expected in (('', None), (' Other accounted for the remainder.', 40)):
            essay = 'Housing accounted for 40%. Food represented 20%.' + suffix
            result = {'chart_type': 'pie', 'axes': {'unit': '%'}, 'records': []}
            _enforce_explicit_pie_values(result, table, essay)
            infer_supported_comparisons(result, essay)
            self.assertEqual(result['records'][2]['value'], expected)

    def test_time_based_bar_and_area_interpolation_has_traceable_provenance(self):
        table = 'Year | Rail\n2010 | 10\n2015 | 18\n2020 | 20'
        essay = 'Rail rose steadily from 10 in 2010 to 20 in 2020.'
        for chart_type in ('bar', 'line', 'area'):
            with self.subTest(chart_type=chart_type):
                result = {'chart_type': chart_type, 'records': []}
                _enforce_explicit_cartesian_values(result, table, essay)
                _interpolate_supported_temporal_gaps(result, table, essay)
                finalise_provenance(result)
                self.assertEqual(result['records'][1]['value'], 15)
                self.assertEqual(result['records'][1]['data_source'], 'inferred')
                self.assertEqual(result['records'][1]['inference']['student_evidence'], essay)
        cities = table.replace('2010', 'London').replace('2015', 'Paris').replace('2020', 'Berlin')
        result = {'chart_type': 'bar', 'records': [
            {'category': 'London', 'series': 'Rail', 'value': 10},
            {'category': 'Paris', 'series': 'Rail', 'value': None},
            {'category': 'Berlin', 'series': 'Rail', 'value': 20}]}
        _interpolate_supported_temporal_gaps(result, cities, 'Rail increased steadily.')
        self.assertIsNone(result['records'][1]['value'])

    def test_negated_or_hypothetical_trend_does_not_fill_gaps(self):
        table = 'Year | Rail\n2010 | 10\n2015 | 18\n2020 | 20'
        for wording in ('Rail did not rise steadily.', 'If Rail rose steadily, the middle value would differ.',
                        'Rail might have increased steadily.', "Rail didn't rise steadily."):
            essay = 'Rail stood at 10 in 2010 and 20 in 2020. ' + wording
            for chart_type in ('bar', 'line', 'area'):
                with self.subTest(wording=wording, chart_type=chart_type):
                    result = {'chart_type': chart_type, 'records': []}
                    _enforce_explicit_cartesian_values(result, table, essay)
                    _interpolate_supported_temporal_gaps(result, table, essay)
                    self.assertIsNone(result['records'][1]['value'])

import csv
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import Mock, patch

from starlette.requests import Request

from research_api import record_server_event_for_request
from research_data import ResearchStore
from revision_history import RevisionHistoryStore


class FeedbackExportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = ResearchStore(self.root / 'user_data/research')
        self.history = RevisionHistoryStore(self.root / 'user_data/revision_history.sqlite3')

    def record(self, kind, payload, username='tester01'):
        self.store.record_server_event(username, kind, payload=payload)

    def export(self):
        return zipfile.ZipFile(self.store.build_export(['tester01'], configured_usernames=['tester01']))

    def test_all_feedback_types_and_shared_submission_are_exported_with_prose_escaped(self):
        essay = '<script>alert("essay")</script>'
        self.record('chart_analysis_completed', {'submission_id': 'submission-one', 'student_answer': essay,
                    'chart_data': {'move_feedback': {'assessments': [{'label': 'Overview', 'rationale': 'Describe both trends.', 'hint': 'Compare the endpoints.'}]},
                                   'records': [{'value': 48, 'estimated': True, 'inference': {'explanation': '51 minus 3'}}]},
                    'revision_suggestions': ['Check the comparison.']})
        self.record('revision_language_review_completed', {'submission_id': 'submission-one',
                    'request': {'text': essay}, 'response': {'success': True, 'overall': {'summary': 'Clear overall.'},
                    'suggestions': [{'excerpt': 'rose', 'replacement': 'increased', 'message': 'Use a precise verb.'}],
                    'prompt_used': 'Stored prompt', 'used_model': 'test-model'}})
        for kind in ('sample_essay_completed', 'spatial_sample_essay_completed', 'next_sentence_completed'):
            self.record(kind, {'response': {'essay': 'Generated example', 'sentence': 'A continuation.'}})
        self.record('chart_analysis_failed', {'student_answer': 'Failed draft', 'error': 'Timeout'})
        self.record('revision_comparison_ready', {'criteria': {'items': [{'state': 'addressed'}]}})
        self.record('chart_analysis_completed', {'student_answer': 'PRIVATE OTHER USER'}, username='tester02')
        with self.export() as archive:
            rows = [json.loads(line) for line in archive.read('raw/feedback.jsonl').decode().splitlines()]
            self.assertEqual(len(rows), 7)
            self.assertEqual(sum(row['submission_id'] == 'submission-one' for row in rows), 2)
            self.assertEqual(sum(row['status'] == 'failed' for row in rows), 1)
            page = archive.read('feedback.html').decode()
            self.assertNotIn('<script>', page)
            self.assertIn('&lt;script&gt;', page)
            self.assertEqual(page.count('<section>'), 6)
            self.assertIn('Use a precise verb.', page)
            language = next(row for row in rows if row['kind'] == 'revision_language_review')
            self.assertIn('Stored prompt', archive.read(language['json_file']).decode())
            self.assertNotIn('PRIVATE OTHER USER', ''.join(archive.read(name).decode(errors='replace') for name in archive.namelist()))
            csv_rows = list(csv.DictReader(io.StringIO(archive.read('feedback.csv').decode('utf-8-sig'))))
            self.assertIn('Describe both trends.', csv_rows[0]['feedback_text'])
            self.assertTrue(all(row['occurred_at'].endswith('+08:00') for row in rows))

    def test_history_without_research_event_includes_images_and_is_user_scoped(self):
        (self.root / 'generated_charts').mkdir()
        (self.root / 'uploaded_images').mkdir()
        (self.root / 'generated_charts/chart.png').write_bytes(b'chart-image')
        (self.root / 'uploaded_images/task.png').write_bytes(b'task-image')
        for username in ('tester01', 'tester02'):
            self.history.save(username, b'image', 'bar', 'A | 1', username + ' essay',
                              {'move_feedback': {'assessments': [{'hint': 'Check the overview.'}]}},
                              '/charts/chart.png', '/uploads/task.png', submission_id='submission-history')
        with self.export() as archive:
            snapshots = json.loads(archive.read('raw/revision_history.json'))
            self.assertEqual(len(snapshots), 1)
            self.assertEqual(snapshots[0]['username'], 'tester01')
            rows = [json.loads(line) for line in archive.read('raw/feedback.jsonl').decode().splitlines()]
            self.assertEqual(rows[0]['kind'], 'history_snapshot')
            self.assertEqual(len(rows[0]['image_files']), 2)
            for name in rows[0]['image_files']:
                self.assertIn(name, archive.namelist())
            self.assertFalse(any(name.endswith('.sqlite3') for name in archive.namelist()))

    def test_browser_recovery_and_duplicate_copies_do_not_drop_other_feedback(self):
        response = {'success': True, 'suggestions': [{'message': 'Recorded feedback'}]}
        request = {'text': 'Same essay'}
        self.record('revision_language_review_completed', {'request': request, 'response': response})
        self.record('api_call_completed', {'path': '/api/revision-review', 'request': request, 'response': response})
        self.record('api_call_completed', {'path': '/api/revision-review', 'request': request,
                                          'response': {'success': True, 'suggestions': ['Different review']}})
        self.record('revision_language_review_completed', {'request': request, 'response': response})
        with self.export() as archive:
            rows = [json.loads(line) for line in archive.read('raw/feedback.jsonl').decode().splitlines()]
            self.assertEqual(len(rows), 3)
            self.assertEqual(sum(row['source'] == 'browser_recovery' for row in rows), 1)
            self.assertTrue(all(row['submission_id'] is None for row in rows))

    def test_client_url_cannot_copy_unowned_runtime_file_and_missing_media_is_reported(self):
        (self.root / 'generated_charts').mkdir()
        (self.root / 'generated_charts/private.png').write_bytes(b'OTHER USERS IMAGE')
        self.record('api_call_completed', {'path': '/api/analyze-chart-with-image',
                    'response': {'chart_url': '/charts/private.png', 'success': True}})
        self.history.save('tester01', b'chart', 'bar', 'A | 1', 'Draft', {}, '/charts/missing.png', '/uploads/missing.png')
        with self.export() as archive:
            self.assertFalse(any('private.png' in name for name in archive.namelist()))
            self.assertEqual(len(json.loads(archive.read('feedback_manifest.json'))['missing_history_media']), 2)

    def test_identical_feedback_for_another_submission_is_not_dropped(self):
        payload = {'request': {'text': 'Same essay'}, 'response': {'success': True, 'score': 0}}
        self.record('revision_language_review_completed', {**payload, 'submission_id': 'submission-first'})
        self.record('api_call_completed', {**payload, 'submission_id': 'submission-second', 'path': '/api/revision-review'})
        with self.export() as archive:
            rows = [json.loads(line) for line in archive.read('raw/feedback.jsonl').decode().splitlines()]
            self.assertEqual(len(rows), 2)
            self.assertIn('<span class="text">0</span>', archive.read('feedback.html').decode())

    def test_submission_header_is_recorded_by_server_and_invalid_values_are_ignored(self):
        store = Mock()
        for header, expected in ((b'submission-test-one', 'submission-test-one'), (b'../invalid', None)):
            request = Request({'type': 'http', 'headers': [(b'x-vividwrite-submission', header)]})
            request.state.username = 'tester01'
            with patch('research_api.research_enabled', return_value=True), patch('research_api.get_research_store', return_value=store):
                record_server_event_for_request(request, 'chart_analysis_completed', payload={'chart_data': {}})
            self.assertEqual(store.record_server_event.call_args.kwargs['payload']['submission_id'], expected)

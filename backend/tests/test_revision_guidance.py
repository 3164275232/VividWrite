import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from research_data import ResearchStore
from revision_history import RevisionHistoryStore
from revision_guidance import build_facts, generate_guidance, language_reviews, router, select_history


def snapshot(sequence, essay='Overall, recycling rose.', status='developing', **extra):
    return {'id': f'review-{sequence}', 'submission_id': f'submission-{sequence}', 'sequence': sequence,
            'task_id': 'task', 'reference_id': 'ref', 'feedback_version': '1', 'analysis_model': 'test',
            'essay': essay, 'assessments': [{'code': 'overview', 'label': 'Overview', 'status': status,
                'excerpt': essay, 'rationale': 'The overview needs a meaningful comparison.',
                'hint': 'Choose the most important contrast.'}], 'records': [], **extra}


class RevisionGuidanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = RevisionHistoryStore(self.root / 'user_data/revision_history.sqlite3')

    def test_selection_uses_recent_distinct_compatible_drafts(self):
        current = snapshot(10)
        history = [snapshot(9, 'Same draft'), snapshot(8, 'Same draft'), snapshot(7, 'Other draft'),
                   snapshot(6, 'Wrong reference', reference_id='other'), snapshot(5, 'Wrong task', task_id='other'),
                   snapshot(4, 'Wrong model', analysis_model='other'), snapshot(3, 'Third draft'), snapshot(2, 'Oldest')]
        self.assertEqual([row['sequence'] for row in select_history(current, history)], [9, 7, 3])
        self.assertEqual(select_history(current, [snapshot(11)]), [])

    def test_identical_draft_and_unchanged_flagged_passage_do_not_count_as_progress(self):
        old = snapshot(1)
        same = snapshot(2, status='effective')
        self.assertEqual(build_facts(same, [old], {})[0]['status'], 'uncertain')
        added = snapshot(3, old['essay'] + ' Another sentence.', status='effective')
        self.assertEqual(build_facts(added, [old], {})[0]['status'], 'uncertain')
        edited = snapshot(4, 'Overall, all cities rose, but gains varied.', status='effective')
        self.assertEqual(build_facts(edited, [old], {})[0]['status'], 'improved')
        edited['assessments'][0]['analysis_source'] = 'local_fallback'
        self.assertEqual(build_facts(edited, [old], {})[0]['status'], 'uncertain')

    def test_recurrent_criterion_retains_different_concerns_for_synthesis(self):
        old, current = snapshot(1), snapshot(2, 'Overall, the gap was three points.')
        current['assessments'][0]['rationale'] = 'A minor gap has displaced the overall pattern.'
        fact = build_facts(current, [old], {})[0]
        self.assertEqual(fact['status'], 'recurring')
        self.assertNotEqual(fact['reason'], fact['history'][0]['assessment']['rationale'])

    def test_overview_and_trend_feedback_on_same_passage_is_one_priority(self):
        current = snapshot(2)
        current['assessments'].append({**current['assessments'][0], 'code': 'key_trends', 'label': 'Key trends'})
        facts = build_facts(current, [], {})
        self.assertEqual(len(facts), 1)
        self.assertEqual(len(facts[0]['related_criteria']), 2)

    def test_value_correction_requires_explicit_edited_evidence(self):
        old = snapshot(1, 'Bristol was 47%.', value_tolerance=1)
        old['records'] = [{'category': 'Bristol', 'value': 47, 'official_value': 42,
                          'explicit_student_value': True, 'student_evidence': old['essay']}]
        current = snapshot(2, 'Bristol was 42%.', value_tolerance=1)
        current['records'] = [{**old['records'][0], 'value': 42, 'student_evidence': current['essay']}]
        values = lambda: [f for f in build_facts(current, [old], {}) if f['id'].startswith('value:')]
        self.assertEqual(values()[0]['status'], 'improved')
        current['records'][0]['estimated'] = True
        self.assertEqual(values(), [])
        current['records'][0]['estimated'] = False
        current['value_tolerance'] = 2
        self.assertEqual(values(), [])

    def mock_client(self, data):
        client = MagicMock()
        client.with_options.return_value.__enter__.return_value.chat.completions.create.return_value = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(data)))])
        return client

    def test_model_synthesizes_supported_facts_and_cannot_override_metadata(self):
        item = {'fact_ids': ['criterion:overview'], 'title': 'Make the overview meaningful',
                'explanation': 'The key comparison is still missing after the latest edit.',
                'action': 'Select a broad contrast before discussing individual figures.',
                'self_check': 'Can a reader identify the main pattern without the chart?'}
        client = self.mock_client({'summary': 'Focus on the overview.', 'priorities': [item],
                                   'improvements': [], 'analysis_revision_id': 'forged', 'facts': []})
        with patch('revision_guidance.get_deepseek_client', return_value=client):
            result = generate_guidance(snapshot(2), [snapshot(1)], {})
        self.assertEqual(result['source'], 'ai')
        self.assertEqual(result['analysis_revision_id'], 'review-2')
        self.assertTrue(result['facts'])
        self.assertTrue(result['unchanged_since_latest'])
        self.assertTrue(result['created_at'].endswith('+08:00'))
        client.with_options.assert_called_once_with(timeout=50, max_retries=0)

    def test_unsupported_improvement_falls_back_honestly(self):
        item = {'fact_ids': ['criterion:overview'], 'title': 'Fixed', 'explanation': 'Fixed',
                'action': 'Keep it', 'self_check': 'Check'}
        client = self.mock_client({'summary': 'Improved', 'improvements': [item], 'priorities': []})
        with patch('revision_guidance.get_deepseek_client', return_value=client):
            result = generate_guidance(snapshot(2), [snapshot(1)], {})
        self.assertEqual(result['source'], 'saved_feedback')
        self.assertEqual(result['improvements'], [])
        self.assertEqual(len(result['priorities']), 1)

    def save(self, username='alice', essay='Overall, all cities improved.'):
        return self.store.save(username, b'chart', 'bar', 'A | 10', essay,
            {'move_feedback': {'version': '1', 'assessments': snapshot(1)['assessments']}},
            '/charts/example.png', '/uploads/example.png', submission_id='submission-one')

    def test_endpoint_ownership_caching_and_export_without_event_logging(self):
        saved = self.save()
        app = FastAPI()
        app.include_router(router)
        with TestClient(app) as client, patch('revision_guidance.RevisionHistoryStore', return_value=self.store), patch(
            'revision_guidance.language_reviews', return_value={}), patch('revision_guidance.get_deepseek_client', side_effect=RuntimeError('unavailable')) as model, patch(
            'research_api.record_server_event_for_request') as record:
            url = f'/api/revision-history/{saved["id"]}/guidance'
            with patch('revision_guidance.history_username', return_value=None):
                self.assertEqual(client.post(url).status_code, 401)
            with patch('revision_guidance.history_username', return_value='bob'):
                self.assertEqual(client.post(url + '?username=alice').status_code, 404)
            with patch('revision_guidance.history_username', return_value='alice'):
                first = client.post(url)
                self.assertEqual(first.status_code, 200)
                self.assertEqual(client.post(url).json(), first.json())
                model.assert_called_once()
                record.assert_called_once()
        self.assertIsNotNone(RevisionHistoryStore(self.store.path).get_guidance('alice', saved['id']))
        self.assertIsNone(self.store.get_guidance('bob', saved['id']))
        research = ResearchStore(self.root / 'user_data/research')
        with zipfile.ZipFile(research.build_export(['alice'])) as archive:
            histories = json.loads(archive.read('raw/revision_history.json'))
            self.assertIn('revision_guidance', histories[0])
            rows = [json.loads(row) for row in archive.read('raw/feedback.jsonl').decode().splitlines()]
            self.assertTrue(any(row['kind'] == 'revision_guidance' for row in rows))

    def test_language_context_only_uses_owner_and_exact_submission(self):
        research = ResearchStore(self.root / 'user_data/research')
        for user, sub, message in [('alice', 'submission-2', 'Own feedback'), ('bob', 'submission-2', 'Private'),
                                   ('alice', 'submission-other', 'Another attempt'), ('alice', None, 'Legacy')]:
            research.record_server_event(user, 'revision_language_review_completed', payload={
                'submission_id': sub, 'response': {'suggestions': [{'message': message}]}})
        with patch('revision_guidance.USER_DATA_DIR', self.root / 'user_data'):
            result = language_reviews('alice', [snapshot(2)])
        self.assertEqual(list(result), ['submission-2'])
        self.assertEqual(result['submission-2']['suggestions'][0]['message'], 'Own feedback')


if __name__ == '__main__':
    unittest.main()

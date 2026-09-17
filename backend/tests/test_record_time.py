import csv
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from record_time import beijing_timestamp, normalise_record_times
from research_data import ResearchStore
from revision_history import RevisionHistoryStore


class RecordTimeTests(unittest.TestCase):
    def test_conversion_preserves_instant_and_prose(self):
        expected = '2026-09-18T00:30:00.000+08:00'
        for source in ('2026-09-17T16:30:00Z', '2026-09-17T12:30:00-04:00', expected):
            self.assertEqual(beijing_timestamp(source), expected)
        self.assertEqual(beijing_timestamp(None), None)
        self.assertEqual(beijing_timestamp('unknown'), 'unknown')
        row = normalise_record_times({'created_at': '2026-09-17T16:30:00Z',
                                      'text': '2026-09-17T16:30:00Z', 'active_ms': 30000})
        self.assertEqual(row['created_at'], expected)
        self.assertEqual(row['text'], '2026-09-17T16:30:00Z')
        self.assertEqual(row['active_ms'], 30000)

    def test_client_utc_is_normalised_on_write_and_legacy_export_remains_ordered(self):
        with tempfile.TemporaryDirectory() as folder:
            store = ResearchStore(Path(folder))
            store.record_auth_event('tester01', 'auth_login_succeeded',
                                    consented_at='2026-09-17T00:00:00Z')
            sid = store.start_session('tester01', 'session-timezone-check',
                                      client_started_at='2026-09-17T00:00:00Z')
            for event_id, occurred in (('old', '2026-09-17T01:00:00Z'),
                                       ('new', '2026-09-17T08:30:00+08:00')):
                store.append_events('tester01', sid, [{
                    'event_id': event_id, 'event_type': 'essay_snapshot',
                    'occurred_at': occurred, 'payload': {
                        'text': 'An essay mentioning 2026-09-17T01:00:00Z.',
                        'last_activity_at': occurred,
                        'response': {'analysis_revision': {'created_at': occurred}},
                    },
                }])
            with store._connection() as conn:
                self.assertEqual(conn.execute('SELECT consented_at FROM participants').fetchone()[0],
                                 '2026-09-17T08:00:00.000+08:00')
                self.assertTrue(conn.execute('SELECT started_at FROM sessions').fetchone()[0].endswith('+08:00'))
                self.assertTrue(conn.execute("SELECT occurred_at FROM events WHERE event_id='old'").fetchone()[0].endswith('+08:00'))
                # Simulate existing, immutable UTC rows alongside new Beijing rows.
                conn.execute("UPDATE events SET received_at=?, occurred_at=? WHERE event_id='old'",
                             ('2026-09-17T01:00:00Z', '2026-09-17T01:00:00Z'))
                conn.execute("UPDATE events SET received_at=? WHERE event_id='new'", ('2026-09-17T08:30:00+08:00',))
                conn.execute("UPDATE participants SET first_login_at=?", ('2026-09-17T00:00:00Z',))
            path = store.build_export(['tester01'], configured_usernames=['tester01'])
            with zipfile.ZipFile(path) as archive:
                rows = [json.loads(line) for line in archive.read('raw/events.jsonl').decode().splitlines()]
                selected = [row for row in rows if row['event_id'] in {'old', 'new'}]
                self.assertEqual([row['event_id'] for row in selected], ['new', 'old'])
                for row in rows:
                    for key in ('occurred_at', 'received_at'):
                        self.assertTrue(row[key].endswith('+08:00'))
                payload = json.loads(selected[1]['payload_json'])
                self.assertEqual(payload['response']['analysis_revision']['created_at'], '2026-09-17T09:00:00.000+08:00')
                self.assertEqual(payload['text'], 'An essay mentioning 2026-09-17T01:00:00Z.')
                for name in ('participants.csv', 'sessions.csv', 'events.csv', 'essay_versions.csv'):
                    for row in csv.DictReader(io.StringIO(archive.read(name).decode('utf-8-sig'))):
                        for key, value in row.items():
                            if key.endswith('_at') and value:
                                self.assertTrue(value.endswith('+08:00'), (name, key, value))
                self.assertIn('UTC+08:00', archive.read('summary.html').decode())
                self.assertIn('UTC+08:00', archive.read('README.txt').decode())
            with store._connection() as conn:
                self.assertEqual(conn.execute("SELECT occurred_at FROM events WHERE event_id='old'").fetchone()[0],
                                 '2026-09-17T01:00:00Z')

    def test_history_writes_beijing_and_reads_legacy_without_rewriting_it(self):
        with tempfile.TemporaryDirectory() as folder:
            store = RevisionHistoryStore(Path(folder) / 'history.sqlite3')
            args = ('tester01', b'chart', 'bar', 'A | 10', 'A is 10.', {}, '/charts/a.png', '/uploads/a.png')
            current = store.save(*args)
            self.assertTrue(current['created_at'].endswith('+08:00'))
            with patch('revision_history.beijing_now', return_value='2026-09-17T16:30:00Z'):
                old = store.save(*args)
            rows = store.list('tester01', old['task_id'])
            self.assertEqual(rows[0]['created_at'], '2026-09-18T00:30:00.000+08:00')
            self.assertEqual(rows[0]['essay'], old['essay'])

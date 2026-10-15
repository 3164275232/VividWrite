"""Small opt-in live model check using synthetic writing; does not write study data."""
import json
import sys
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from revision_guidance import generate_guidance, validate_guidance

old_essay = ('The chart compares recycling rates in five UK cities in 2015 and 2020. '
             'Overall, every city improved, and the main feature was the three-point difference between Sheffield and Leeds in 2020. '
             'Manchester rose from 31% to 46%, while Bristol increased from 42% to 55%.')
new_essay = ('The chart compares recycling rates in five UK cities in 2015 and 2020. '
             'Overall, recycling increased in every city, with Manchester recording the largest rise and Bristol remaining highest. '
             'Manchester rose from 31% to 46%, while Bristol increased from 42% to 55%.')


def revision(sequence, essay, status):
    excerpt = essay.split('Overall, ')[1].split('. ')[0]
    return {'id': f'demo-{sequence}', 'submission_id': f'demo-submission-{sequence}', 'sequence': sequence,
            'task_id': 'recycling', 'reference_id': 'same', 'feedback_version': '1', 'analysis_model': 'demo',
            'title': 'Recycling rates', 'chart_type': 'bar', 'essay': essay, 'records': [],
            'assessments': [{'code': code, 'label': label, 'status': status, 'excerpt': 'Overall, ' + excerpt + '.',
                'rationale': ('The overview identifies the broad rise, largest increase and highest city.' if status == 'effective'
                              else 'All cities increased, but the three-point gap between Sheffield and Leeds is a minor feature. Manchester had the largest rise and Bristol stayed highest.'),
                'hint': 'Choose a broad pattern and a major contrast before giving supporting numbers.'}
                for code, label in [('overview', 'Stating the overview'), ('key_trends', 'Highlighting key trends')]]}


if __name__ == '__main__':
    scenarios = {
        'unchanged': (revision(8, old_essay, 'developing'), [revision(7, old_essay, 'developing'), revision(6, old_essay.replace('main feature', 'key feature'), 'developing')]),
        'improved': (revision(9, new_essay, 'effective'), [revision(8, old_essay, 'developing')]),
    }
    def check(pair):
        name, (current, previous) = pair
        result = generate_guidance(current, previous, {})
        assert result['source'] == 'ai', f'{name}: {result.get("error_type")}'
        if name == 'unchanged':
            assert not result['improvements'] and result['priorities']
            assert len(result['priorities']) <= 2
        else:
            assert result['improvements']
        return name, result
    def inspect(data, facts):
        try:
            validate_guidance(data, facts)
        except ValueError as error:
            print(json.dumps({'validation_error': str(error), 'response': data,
                              'fact_states': [(f['id'], f['status']) for f in facts]}, ensure_ascii=False))
            raise
    with patch('revision_guidance.validate_guidance', side_effect=inspect), ThreadPoolExecutor(max_workers=2) as pool:
        results = dict(pool.map(check, scenarios.items()))
    target = Path(__file__).resolve().parents[1] / 'tmp/guidance-live-results.json'
    target.parent.mkdir(exist_ok=True)
    target.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({name: {key: result[key] for key in ('summary', 'improvements', 'priorities', 'model')}
                      for name, result in results.items()}, ensure_ascii=False, indent=2))

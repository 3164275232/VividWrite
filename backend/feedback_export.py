"""Export recorded feedback without re-running a model or guessing legacy pairings."""

import hashlib
import html
import json
import sqlite3
from collections import defaultdict
from contextlib import closing
from datetime import datetime
from pathlib import Path
from urllib.parse import quote, urlparse

from record_time import normalise_record_times

EVENT_KINDS = {
    'chart_analysis': '图表与写作标准反馈',
    'revision_language_review': '语言修改反馈',
    'sample_essay': '范文生成',
    'spatial_sample_essay': '地图／流程图范文生成',
    'next_sentence': '续写建议',
    'revision_comparison': '前后版本比较（系统计算）',
    'revision_guidance': '结合历史反馈的综合修改建议',
    'history_snapshot': '历史反馈版本',
}
API_KINDS = {
    '/api/analyze-chart-with-image': 'chart_analysis',
    '/api/revision-review': 'revision_language_review',
    '/api/generate-sample-essay': 'sample_essay',
    '/api/generate-spatial-sample-essay': 'spatial_sample_essay',
    '/api/next-sentence': 'next_sentence',
}


def parse_payload(text):
    try:
        value = json.loads(text)
        return value if isinstance(value, dict) else {'value': value}
    except (ValueError, TypeError):
        return {'unreadable_payload': text}


def load_history(path, usernames):
    """Read only selected users; never include a shared SQLite database in their ZIP."""
    if not path.is_file():
        return []
    with closing(sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True)) as conn:
        rows = conn.execute(
            'SELECT username, snapshot FROM analysis_revisions WHERE username IN ('
            + ','.join('?' for _ in usernames) + ') ORDER BY username, task_id, sequence', usernames,
        ).fetchall()
        guidance = {}
        if conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='revision_guidance'").fetchone():
            guidance = {(username, revision_id): json.loads(value) for username, revision_id, value in conn.execute(
                'SELECT username, revision_id, guidance FROM revision_guidance WHERE username IN ('
                + ','.join('?' for _ in usernames) + ')', usernames).fetchall()}
    result = []
    for username, snapshot in rows:
        item = {**json.loads(snapshot), 'username': username}
        if (username, item['id']) in guidance:
            item['revision_guidance'] = guidance[(username, item['id'])]
        result.append(normalise_record_times(item))
    return result


def media_urls(value):
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {'chart_url', 'original_url', 'image_url'} and isinstance(item, str):
                yield item
            elif key == 'image_filename' and isinstance(item, str):
                yield '/charts/' + item
            else:
                yield from media_urls(item)
    elif isinstance(value, list):
        for item in value:
            yield from media_urls(item)


def write_feedback_export(archive, events, histories, artifacts, research_root, csv_bytes):
    media = {}
    media_warnings = []
    for artifact in artifacts:
        source = (research_root / artifact['stored_path']).resolve()
        if source.is_file() and source.is_relative_to(research_root.resolve()):
            target = f"artifacts/{artifact['username']}/{artifact['session_id'] or 'unassigned'}/{source.name}"
            media[(artifact['username'], artifact.get('original_name'))] = target

    # Only trusted, owner-scoped history snapshots may recover missing archive copies.
    # Never copy a runtime file solely because a client event claims its URL.
    for snapshot in histories:
        for url in set(media_urls(snapshot)):
            path = Path(urlparse(url).path)
            parts = path.parts
            if len(parts) != 3 or parts[1] not in {'charts', 'uploads'}:
                continue
            key = (snapshot['username'], path.name)
            if key in media:
                continue
            folder = research_root.parent.parent / ('generated_charts' if parts[1] == 'charts' else 'uploaded_images')
            source = (folder / path.name).resolve()
            if source.is_file() and source.is_relative_to(folder.resolve()):
                digest = hashlib.sha256((snapshot['username'] + url).encode()).hexdigest()[:20]
                target = f"feedback_media/{snapshot['username']}/{digest}{source.suffix}"
                archive.write(source, target)
                media[key] = target
            else:
                media_warnings.append({'username': snapshot['username'], 'revision_id': snapshot['id'], 'url': url})

    snapshots_by_url = {(item['username'], item.get('chart_url')): item for item in histories}
    records = []
    known_outputs = set()

    def add(event, kind, payload, browser=False):
        response = payload.get('response') or {}
        request = payload.get('request') or {}
        response = response if isinstance(response, dict) else {'value': response}
        request = request if isinstance(request, dict) else {}
        chart_url = payload.get('chart_url') or response.get('chart_url')
        snapshot = snapshots_by_url.get((event['username'], chart_url), {}) if chart_url else {}
        essay = payload.get('student_answer') or payload.get('essay') or request.get('text') or request.get('student_answer') or snapshot.get('essay', '')
        # Suppress a browser copy only when the same recorded output exists on the server.
        submission = payload.get('submission_id') or snapshot.get('submission_id')
        signature = (event['username'], event.get('session_id'), submission, kind,
                     chart_url or json.dumps([essay, response], sort_keys=True, ensure_ascii=False))
        if browser and signature in known_outputs:
            return
        if not browser:
            known_outputs.add(signature)
        source_id = str(event.get('event_id') or event.get('id'))
        record_id = hashlib.sha256((event['username'] + ':' + source_id).encode()).hexdigest()[:24]
        failed = event['event_type'].endswith('failed') or response.get('success') is False or bool(payload.get('error') or response.get('error'))
        records.append({
            'feedback_id': record_id, 'username': event['username'], 'session_id': event.get('session_id'),
            'submission_id': submission, 'revision_id': payload.get('analysis_revision_id') or snapshot.get('id'),
            'occurred_at': event.get('occurred_at'), 'kind': kind, 'label': EVENT_KINDS[kind],
            'status': 'failed' if failed else 'recorded', 'essay': essay,
            'source_event_id': source_id, 'source_event_type': event['event_type'],
            'source': 'browser_recovery' if browser else 'recorded_event',
            'history_snapshot': snapshot or None,
            'payload': payload,
            'json_file': f"feedback/{event['username']}/{record_id}.json",
        })

    for event in events:
        kind = next((name for name in EVENT_KINDS if event['event_type'] in
                     {name + '_completed', name + '_failed', name + '_ready'}), None)
        if kind:
            add(event, kind, parse_payload(event['payload_json']))
    for event in events:
        if event['event_type'] not in {'api_call_completed', 'api_call_failed'}:
            continue
        payload = parse_payload(event['payload_json'])
        kind = API_KINDS.get(payload.get('path'))
        if kind:
            add(event, kind, payload, browser=True)

    represented = {row['revision_id'] for row in records if row['revision_id']}
    for snapshot in histories:
        guidance = snapshot.get('revision_guidance')
        if guidance and not any(row['kind'] == 'revision_guidance' and row['revision_id'] == snapshot['id'] for row in records):
            add({'username': snapshot['username'], 'event_id': 'guidance-' + snapshot['id'],
                 'event_type': 'revision_guidance_completed', 'occurred_at': guidance['created_at']},
                'revision_guidance', {'response': guidance, 'student_answer': snapshot['essay'],
                                     'submission_id': snapshot.get('submission_id'), 'analysis_revision_id': snapshot['id']})
        if snapshot['id'] not in represented:
            add({'username': snapshot['username'], 'event_id': 'history-' + snapshot['id'],
                 'event_type': 'history_snapshot_completed', 'occurred_at': snapshot['created_at']},
                'history_snapshot', {**snapshot, 'analysis_revision_id': snapshot['id']})

    def sort_time(row):
        try:
            return datetime.fromisoformat(row['occurred_at'].replace('Z', '+00:00')).timestamp()
        except (ValueError, TypeError, AttributeError, KeyError):
            return 0
    records.sort(key=sort_time)

    def visible_feedback(payload):
        response = payload.get('response') or payload
        chart = payload.get('chart_data') or (response.get('chart_data') if isinstance(response, dict) else None)
        if isinstance(response, dict) and 'priorities' in response and 'based_on' in response:
            return {key: response.get(key) for key in ('summary', 'improvements', 'priorities', 'based_on', 'source', 'unchanged_since_latest')}
        if isinstance(chart, dict) and chart:
            return {**{key: chart[key] for key in ('move_feedback', 'comparison', 'records') if key in chart},
                    'revision_suggestions': payload.get('revision_suggestions') or response.get('revision_suggestions') or []}
        return {key: value for key, value in response.items() if key not in {'prompt_used', 'request', 'context'}} if isinstance(response, dict) else response
    csv_rows = []
    grouped = defaultdict(list)
    for record in records:
        urls = set(media_urls(record['payload']))
        urls.update(media_urls(record.get('history_snapshot')))
        record['image_files'] = sorted({media[(record['username'], Path(urlparse(url).path).name)]
                                       for url in urls if (record['username'], Path(urlparse(url).path).name) in media})
        archive.writestr(record['json_file'], json.dumps(record, ensure_ascii=False, indent=2))
        csv_rows.append({**{key: value for key, value in record.items() if key not in {'payload', 'history_snapshot'}},
                         'feedback_text': json.dumps(visible_feedback(record['payload']), ensure_ascii=False, indent=2),
                         'image_files': '\n'.join(record['image_files'])})
        grouped[(record['username'], record['submission_id'] or record['feedback_id'])].append(record)

    def esc(value):
        return html.escape('' if value is None else str(value))

    labels = {
        'move_feedback': '写作标准反馈', 'assessments': '各项评价', 'label': '评价项目',
        'status': '评价结果', 'excerpt': '对应原句', 'rationale': '评价理由', 'hint': '修改提示',
        'overall': '总体评价', 'summary': '总结', 'suggestions': '逐项修改建议',
        'message': '建议', 'replacement': '建议表达', 'note': '说明', 'severity': '程度',
        'vocabulary': '词汇', 'grammar': '语法', 'coherence': '连贯性', 'score': '分数',
        'comment': '评语', 'records': '图表数据及来源', 'comparison': '与题目数据的比较',
        'revision_suggestions': '修改建议', 'criteria': '写作标准的变化',
        'reported_values': '所述数值的变化', 'inference': '推断依据',
        'student_evidence': '作文中的依据', 'estimated': '是否为系统推断',
        'category': '类别', 'series': '系列', 'value': '数值', 'error': '失败原因',
        'improvements': '本次改进', 'priorities': '下一步重点', 'action': '具体行动',
        'self_check': '自我检查', 'explanation': '说明', 'based_on': '参考的历史版本',
    }

    def pretty(value):
        if isinstance(value, dict):
            return '<dl>' + ''.join('<dt>' + esc(labels.get(key, key)) + '</dt><dd>' + pretty(item) + '</dd>'
                                    for key, item in value.items()) + '</dl>'
        if isinstance(value, list):
            return '<ol>' + ''.join('<li>' + pretty(item) + '</li>' for item in value) + '</ol>' if value else '<span>无</span>'
        return '<span class="text">' + esc('是' if value is True else '否' if value is False else value) + '</span>'

    sections = []
    for (username, group_id), group in grouped.items():
        parts = [f'<section><h2>{esc(username)} · {esc(group[0]["occurred_at"])}</h2>',
                 f'<p>作答编号：{esc(group[0]["submission_id"] or "旧记录未保存共同作答编号，按原始反馈分别列出")}</p>']
        essay = next((row['essay'] for row in group if row['essay']), '')
        if essay:
            parts.append('<details open><summary>本次作文</summary><pre>' + esc(essay) + '</pre></details>')
        for row in group:
            parts.append(f'<article><h3>{esc(row["label"])} · {esc(row["status"])}</h3>')
            parts.append(pretty(visible_feedback(row['payload'])))
            for filename in row['image_files']:
                parts.append(f'<a href="{quote(filename)}"><img loading="lazy" src="{quote(filename)}" alt="本次反馈图片"></a>')
            parts.append(f'<p><a href="{quote(row["json_file"])}">完整反馈 JSON（包含全部已保存字段）</a></p></article>')
        parts.append('</section>')
        sections.append(''.join(parts))

    overview = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>每次作答的反馈</title>
<style>body{font:15px system-ui;max-width:1100px;margin:32px auto;padding:0 20px;color:#20252b}section{border:1px solid #ddd;border-radius:10px;padding:20px;margin:20px 0}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f6f7f8;padding:14px;line-height:1.6}img{max-width:100%;max-height:600px}article{border-top:1px solid #ddd;margin-top:16px}summary{cursor:pointer}dt{font-weight:600;margin-top:10px;color:#42516b}dd{margin:4px 0 12px 16px}.text{white-space:pre-wrap;overflow-wrap:anywhere}li{padding:8px 0;border-bottom:1px solid #eee}</style>
<h1>每次作答的反馈</h1><p>时间均为北京时间 UTC+08:00。包含已保存的 AI 反馈及系统比较结果，未重新调用 AI。</p>
<p>同一作答编号的图表反馈和语言反馈放在一起。旧记录没有共同编号时分别列出，不能把条目数当作作答次数。失败记录保留错误原因。</p>'''
    archive.writestr('feedback.html', overview + ''.join(sections) + '</html>')
    archive.writestr('feedback.csv', csv_bytes(csv_rows, [
        'username', 'submission_id', 'revision_id', 'occurred_at', 'kind', 'label', 'status',
        'essay', 'feedback_text', 'session_id', 'source_event_id', 'source_event_type', 'source', 'json_file', 'image_files',
    ]))
    archive.writestr('raw/feedback.jsonl', ''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in records))
    archive.writestr('raw/revision_history.json', json.dumps(histories, ensure_ascii=False, indent=2))
    archive.writestr('feedback_manifest.json', json.dumps({
        'timezone': '+08:00', 'feedback_records': len(records), 'history_snapshots': len(histories),
        'missing_history_media': media_warnings,
        'note': 'All available stored feedback is included; previously unrecorded or truncated data cannot be recreated.',
    }, ensure_ascii=False, indent=2))

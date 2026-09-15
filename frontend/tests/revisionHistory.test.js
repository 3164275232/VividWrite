import test from 'node:test';
import assert from 'node:assert/strict';
import { compareRevisions, compareRecordValues, comparableRevisions, inferredRecords, inferenceGroups, sameDraftText } from '../src/revisionHistoryUtils.js';
import { locateMoveRange } from '../src/moveFeedbackUtils.js';

const snapshot = (status, essay, excerpt = essay, extra = {}) => ({
  id: essay, task_id: 'chart-a', reference_id: 'reference-a', feedback_version: '1',
  essay, assessments: [{ code: 'move_4', status, excerpt }], ...extra,
});

test('changed evidence plus effective review is addressed', () => {
  const result = compareRevisions(snapshot('developing', 'It went up.'), snapshot('effective', 'It rose from 10 to 20.'));
  assert.equal(result.items[0].state, 'addressed');
});

test('multipart CRLF conversion is not an edit, but content and spacing edits are', () => {
  assert.equal(sameDraftText('First.\r\n\r\nSecond.', 'First.\n\nSecond.'), true);
  assert.equal(sameDraftText('First.\nSecond.', 'First.\nEdited.'), false);
  assert.equal(sameDraftText('First sentence.', 'First  sentence.'), false);
  assert.deepEqual(locateMoveRange({ excerpt: 'First.\r\nSecond.', range: { start: 0, end: 15 } }, 'First.\nSecond.'),
    { start: 0, end: 14 });
});

test('identical draft with different status is not progress or a new writing error', () => {
  for (const statuses of [['developing', 'effective'], ['effective', 'developing']]) {
    const result = compareRevisions(snapshot(statuses[0], 'Same text.'), snapshot(statuses[1], 'Same text.'));
    assert.equal(result.items[0].state, 'reassessed');
  }
});

test('unrelated edits do not prove that a cited problem was corrected', () => {
  const result = compareRevisions(snapshot('developing', 'It went up. End.', 'It went up.'),
    snapshot('effective', 'It went up. A different ending.', 'It went up.'));
  assert.equal(result.items[0].state, 'reassessed');
});

test('an effective status without grounded current evidence is not a verified correction', () => {
  const result = compareRevisions(snapshot('developing', 'It went up.'),
    snapshot('effective', 'The essay has been edited.', 'A sentence that was never written.'));
  assert.equal(result.items[0].state, 'unverified');
});

test('continuing, newly flagged, optional and unavailable are distinct', () => {
  assert.equal(compareRevisions(snapshot('developing', 'Old.'), snapshot('developing', 'New.')).items[0].state, 'continuing');
  assert.equal(compareRevisions(snapshot('effective', 'Old.'), snapshot('developing', 'New.')).items[0].state, 'new');
  assert.equal(compareRevisions(snapshot('developing', 'Old.'), snapshot('not_applicable', 'New.')).items[0].state, 'optional');
  assert.equal(compareRevisions(snapshot('developing', 'Old.'), snapshot('effective', 'New.', '', { assessments: [] })).items[0].state, 'unverified');
});

test('different charts, reference versions and frameworks cannot measure progress', () => {
  for (const field of ['task_id', 'reference_id', 'feedback_version']) {
    assert.ok(compareRevisions(snapshot('developing', 'Old.'), snapshot('effective', 'New.', '', { [field]: 'different' })).warning);
  }
});

test('only earlier reviews for the current task are offered', () => {
  const current = snapshot('effective', 'Latest', '', { sequence: 3 });
  const earlier = snapshot('developing', 'Earlier', '', { sequence: 1 });
  assert.deepEqual(comparableRevisions(current, [earlier, current,
    { ...earlier, sequence: 4 }, { ...earlier, task_id: 'other' }]), [earlier]);
});

test('inference list excludes explicit, missing, null and invalid values', () => {
  const inferred = { value: 15, estimated: true };
  assert.deepEqual(inferredRecords({ records: [inferred,
    { ...inferred, explicit_student_value: true }, { ...inferred, missing: true },
    { ...inferred, value: null }, { ...inferred, value: NaN }, { value: 20 }] }), [inferred]);
});

test('an unchanged flagged sentence is not resolved by a new positive excerpt elsewhere', () => {
  const result = compareRevisions(snapshot('developing', 'It went up. A short ending.', 'It went up.'),
    snapshot('effective', 'It went up. Rail was the most popular mode.', 'Rail was the most popular mode.'));
  assert.equal(result.items[0].state, 'reassessed');
});

test('invented previous evidence and local fallback cannot establish improvement', () => {
  const old = snapshot('developing', 'Old report.', 'Never written.');
  assert.notEqual(compareRevisions(old, snapshot('effective', 'New report.')).items[0].state, 'addressed');
  const fallback = snapshot('effective', 'New report.');
  fallback.assessments[0].analysis_source = 'local_fallback';
  assert.equal(compareRevisions(snapshot('developing', 'Old report.'), fallback).items[0].state, 'unverified');
});

test('new grounded evidence can demonstrate a previously undetected move', () => {
  assert.equal(compareRevisions(snapshot('not_detected', 'Some details.', ''),
    snapshot('effective', 'Overall, rail rose. Some details.', 'Overall, rail rose.')).items[0].state, 'addressed');
});

const valueReview = (value, extra = {}) => {
  const essay = `Bristol recorded ${value}% in 2015.`;
  return snapshot('developing', essay, essay, {
    value_tolerance: 2, chart_type: 'bar',
    records: [{ category: 'Bristol', series: '2015', value, official_value: 42,
      explicit_student_value: true, student_evidence: essay }], ...extra,
  });
};

test('a corrected explicit value is visible even while the criterion still needs revision', () => {
  const before = valueReview(47);
  const after = valueReview(42);
  assert.equal(compareRevisions(before, after).items[0].state, 'continuing');
  const item = compareRecordValues(before, after).items[0];
  assert.equal(item.state, 'addressed');
  assert.equal(item.before.value, 47);
  assert.equal(item.after.value, 42);
});

test('deleting a wrong value or replacing it with a system estimate is not a correction', () => {
  for (const changes of [{ value: null, missing: true }, { value: 42, estimated: true }]) {
    const after = valueReview(42, { essay: 'Bristol increased steadily.' });
    Object.assign(after.records[0], changes, { explicit_student_value: false });
    assert.equal(compareRecordValues(valueReview(47), after).items[0].state, 'unverified');
  }
});

test('repeated analysis and unchanged value evidence are not writing progress', () => {
  const before = valueReview(47);
  assert.equal(compareRecordValues(before, valueReview(42, { essay: before.essay })).items[0].state, 'reassessed');
  const after = valueReview(42, { essay: `${before.essay} A new conclusion.` });
  after.records[0].student_evidence = before.essay;
  assert.equal(compareRecordValues(before, after).items[0].state, 'reassessed');
});

test('value checks distinguish continuing, new and unverified findings', () => {
  assert.equal(compareRecordValues(valueReview(47), valueReview(49)).items[0].state, 'continuing');
  assert.equal(compareRecordValues(valueReview(42), valueReview(49)).items[0].state, 'new');
  const after = valueReview(42);
  delete after.records[0].student_evidence;
  assert.equal(compareRecordValues(valueReview(47), after).items[0].state, 'unverified');
});

test('value comparison does not reward data enumeration or use incompatible evidence', () => {
  const before = valueReview(42);
  const after = valueReview(42);
  before.records[0].value = null;
  before.records[0].missing = true;
  assert.deepEqual(compareRecordValues(before, after).items, []);
  for (const changes of [{ value_tolerance: 0 }, { value_tolerance: undefined },
    { records: [{ ...after.records[0], official_value: 44 }] }, { records: [...after.records, ...after.records] }]) {
    assert.deepEqual(compareRecordValues(valueReview(47), { ...after, ...changes }).items, []);
  }
  assert.ok(compareRecordValues({ ...valueReview(47), analysis_model: 'v1' },
    { ...after, analysis_model: 'v2' }).warning);
});

test('shared interpolation explanations are grouped without hiding any estimated period', () => {
  const record = { series: 'Rail', estimated: true, value: 15,
    inference: { method: 'linear_interpolation', from: { period: '2010', value: 10 },
      to: { period: '2020', value: 20 }, student_evidence: 'Rail rose steadily.' } };
  const groups = inferenceGroups({ records: [{ ...record, period: '2012', value: 12 },
    { ...record, period: '2015' }, { ...record, series: 'Bus', period: '2015' }] });
  assert.equal(groups.length, 2);
  assert.deepEqual(groups[0].records.map((item) => item.period), ['2012', '2015']);
  assert.equal(groups[1].label, 'Bus');
});

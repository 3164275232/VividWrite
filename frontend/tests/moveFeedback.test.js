import assert from 'node:assert/strict';
import test from 'node:test';

import {
  findMoveAssessment,
  locateMoveRange,
  withResolvedMoveVisualUrls,
} from '../src/moveFeedbackUtils.js';


const chartData = {
  chart_type: 'line',
  move_feedback: {
    assessments: [{
      id: 'move_3_highlighting_key_trends',
      excerpt: 'Rail recorded the largest rise.',
      range: { start: 8, end: 39 },
      visual: { image_url: '/charts/move-3.png' },
    }],
  },
};


test('resolves nested move visual URLs without mutating the API result', () => {
  const resolved = withResolvedMoveVisualUrls(chartData, (url) => `http://local.test${url}`);

  assert.equal(
    resolved.move_feedback.assessments[0].visual.image_url,
    'http://local.test/charts/move-3.png',
  );
  assert.equal(chartData.move_feedback.assessments[0].visual.image_url, '/charts/move-3.png');
});

test('finds the selected assessment and relocates its exact excerpt after edits', () => {
  const assessment = findMoveAssessment(chartData, 'move_3_highlighting_key_trends');
  const editedText = 'Overall, bus declined. Rail recorded the largest rise.';
  const range = locateMoveRange(assessment, editedText);

  assert.equal(editedText.slice(range.start, range.end), assessment.excerpt);
});

test('does not highlight text when the model excerpt is absent from the draft', () => {
  const assessment = findMoveAssessment(chartData, 'move_3_highlighting_key_trends');

  assert.equal(locateMoveRange(assessment, 'A completely different draft.'), null);
});

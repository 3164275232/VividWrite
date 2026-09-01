import assert from 'node:assert/strict';
import test from 'node:test';

import {
  calculateTextDelta,
  serializeResearchValue,
} from '../src/researchTelemetry.js';


test('captures a minimal essay insertion and deletion delta', () => {
  assert.deepEqual(
    calculateTextDelta('Rail rose in 2020.', 'Rail sharply rose in 2020.'),
    {
      change_start: 5,
      deleted_text: '',
      inserted_text: 'sharply ',
      previous_character_count: 18,
      character_count: 26,
    },
  );
  assert.deepEqual(
    calculateTextDelta('Bus fell sharply.', 'Bus fell.'),
    {
      change_start: 8,
      deleted_text: ' sharply',
      inserted_text: '',
      previous_character_count: 17,
      character_count: 9,
    },
  );
});


test('serializes form input while redacting credential-like fields', () => {
  const form = new FormData();
  form.append('student_answer', 'The chart compares three modes.');
  form.append('api_key', 'never-store-this');
  form.append('image', new File(['image'], 'task.png', { type: 'image/png' }));

  const value = serializeResearchValue(form);
  assert.equal(value.student_answer, 'The chart compares three modes.');
  assert.equal(value.api_key, '[redacted]');
  assert.deepEqual(value.image, {
    file_name: 'task.png',
    mime_type: 'image/png',
    byte_size: 5,
    last_modified: value.image.last_modified,
  });
});

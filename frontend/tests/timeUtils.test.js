import assert from 'node:assert/strict';
import test from 'node:test';
import { beijingTimestamp } from '../src/timeUtils.js';

test('Beijing timestamps preserve the instant across midnight and source time zones', () => {
  for (const source of ['2026-09-17T16:30:00Z', '2026-09-17T12:30:00-04:00', '2026-09-18T00:30:00+08:00']) {
    const result = beijingTimestamp(source);
    assert.equal(result, '2026-09-18T00:30:00.000+08:00');
    assert.equal(Date.parse(result), Date.parse(source));
  }
});

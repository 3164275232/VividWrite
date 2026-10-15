import assert from 'node:assert/strict';
import test from 'node:test';

import {
  getPracticeSample,
  loadPracticeSample,
  PRACTICE_SAMPLES,
} from '../src/practiceSamples.js';


test('provides one preprocessed sample for each supported practice chart type', () => {
  assert.deepEqual(
    PRACTICE_SAMPLES.map((sample) => sample.chartType).sort(),
    ['bar', 'line', 'pie'],
  );
  assert.equal(new Set(PRACTICE_SAMPLES.map((sample) => sample.id)).size, 3);

  for (const sample of PRACTICE_SAMPLES) {
    assert.match(sample.imageUrl, /^\/practice-samples\/.*\.png(?:\?.+)?$/);
    assert.match(sample.deplotText, /^TITLE \| /);
    assert.match(sample.deplotText, /<0x0A>CHART TYPE \| /);
    assert.ok(sample.deplotText.split('<0x0A>').length >= 8);
  }
});

test('loads a practice image only from static assets and returns its saved DePlot text', async () => {
  const requestedUrls = [];
  const fetchImpl = async (url) => {
    requestedUrls.push(url);
    return new Response(new Blob(['sample-image'], { type: 'image/png' }), { status: 200 });
  };

  const { sample, file } = await loadPracticeSample('line-passengers', fetchImpl);

  assert.deepEqual(requestedUrls, ['/practice-samples/02_line_daily_passengers.png?v=32b88ae2']);
  assert.ok(requestedUrls.every((url) => !url.startsWith('/api/')));
  assert.equal(file.name, '02_line_daily_passengers.png');
  assert.equal(file.type, 'image/png');
  assert.equal(sample, getPracticeSample('line-passengers'));
  assert.match(sample.deplotText, /2020 \| 1\.3 \| 2\.2 \| 1\.9$/);
});

test('rejects an unknown practice sample without making a request', async () => {
  let requestCount = 0;
  await assert.rejects(
    () => loadPracticeSample('unknown-sample', async () => {
      requestCount += 1;
      return new Response();
    }),
    /unavailable/,
  );
  assert.equal(requestCount, 0);
});

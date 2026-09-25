import assert from 'node:assert/strict';
import { afterEach, test } from 'node:test';

import { generateSampleEssay, analyzeChartWithImage, reviewRevision, getRevisionGuidance } from '../src/api.js';


const originalFetch = globalThis.fetch;

test('guidance requests share an in-flight call, preserve submission ID and permit a later retry', async () => {
  const calls = [];
  globalThis.fetch = async (url, options) => {
    calls.push({ url, id: options.headers['X-VividWrite-Submission'] });
    return Response.json({ guidance: { analysis_revision_id: 'review-one' } });
  };
  await Promise.all([getRevisionGuidance('review-one', 'submission-one'), getRevisionGuidance('review-one', 'submission-one')]);
  assert.equal(calls.length, 1);
  assert.equal(calls[0].id, 'submission-one');
  assert.match(calls[0].url, /revision-history\/review-one\/guidance$/);
  await getRevisionGuidance('review-one', 'submission-one');
  assert.equal(calls.length, 2);
});

test('one submission ID links parallel chart and language feedback without reusing it for the next draft', async () => {
  const calls = [];
  globalThis.fetch = async (url, options) => {
    calls.push({ url, id: options.headers['X-VividWrite-Submission'] });
    return Response.json({ success: true });
  };
  await Promise.all([analyzeChartWithImage(new FormData(), 'submission-one'),
    reviewRevision({ text: 'Draft one' }, 'submission-one')]);
  await analyzeChartWithImage(new FormData(), 'submission-two');
  assert.deepEqual(calls.map(call => call.id), ['submission-one', 'submission-one', 'submission-two']);
});

afterEach(() => {
  globalThis.fetch = originalFetch;
});

test('sample essay retries one transient gateway failure', async () => {
  let calls = 0;
  globalThis.fetch = async () => {
    calls += 1;
    if (calls === 1) {
      return new Response('', { status: 502 });
    }
    return Response.json({ success: true, essay: 'Recovered essay.' });
  };

  const result = await generateSampleEssay({ deplot_text: 'Year | Value' });

  assert.equal(calls, 2);
  assert.equal(result.essay, 'Recovered essay.');
});

test('sample essay retries one interrupted connection', async () => {
  let calls = 0;
  globalThis.fetch = async () => {
    calls += 1;
    if (calls === 1) {
      throw new TypeError('network connection lost');
    }
    return Response.json({ success: true, essay: 'Recovered essay.' });
  };

  const result = await generateSampleEssay({ deplot_text: 'Year | Value' });

  assert.equal(calls, 2);
  assert.equal(result.essay, 'Recovered essay.');
});

test('sample essay does not retry a request error', async () => {
  let calls = 0;
  globalThis.fetch = async () => {
    calls += 1;
      return Response.json({ detail: 'Invalid request' }, { status: 400 });
  };

  await assert.rejects(
    () => generateSampleEssay({ deplot_text: 'Year | Value' }),
      /Invalid request/,
  );
  assert.equal(calls, 1);
});

test('sample essay replaces a repeated bare 502 with a useful message', async () => {
  let calls = 0;
  globalThis.fetch = async () => {
    calls += 1;
    return new Response('', { status: 502 });
  };

  await assert.rejects(
    () => generateSampleEssay({ deplot_text: 'Year | Value' }),
    /after one automatic retry \(HTTP 502\)/,
  );
  assert.equal(calls, 2);
});

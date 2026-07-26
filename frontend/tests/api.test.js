import assert from 'node:assert/strict';
import { afterEach, test } from 'node:test';

import { generateSampleEssay } from '../src/api.js';


const originalFetch = globalThis.fetch;

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
    return Response.json({ detail: 'Invalid flowchart' }, { status: 400 });
  };

  await assert.rejects(
    () => generateSampleEssay({ deplot_text: 'Year | Value' }),
    /Invalid flowchart/,
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

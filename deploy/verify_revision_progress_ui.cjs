/* Browser integration checks with synthetic API responses, not a model accuracy test. */
const { chromium } = require(process.argv[2] || 'playwright');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '..');
const output = path.join(root, 'backend/user_data/revision_feature_checks');
const fixtures = JSON.parse(fs.readFileSync(path.join(output, 'fixtures.json'), 'utf8'));
const firstEssay = 'The figure shows some numbers.\n\nOverall, rail and metro use rose, while bus use fell. Rail rose steadily from 1.1 million in 2010 to 2.2 million in 2020. Metro use grew steadily from 0.8 million to 1.9 million. Bus use declined from 1.8 million to 1.3 million.';
const secondEssay = firstEssay.replace('The figure shows some numbers.',
  'The line graph compares daily bus, rail and metro passengers from 2010 to 2020, in millions.');
const thirdEssay = secondEssay.replace('Rail rose steadily', 'Rail increased steadily');

function responseFor(sequence, essay) {
  const assessments = fixtures.definitions.map((definition) => ({
    ...definition, id: definition.code,
    status: (definition.number === 1 && sequence === 1) || (definition.number === 4 && sequence >= 4) ? 'developing' : 'effective',
    excerpt: definition.number === 1 ? essay.split(/\r?\n/)[0] : 'Overall, rail and metro use rose, while bus use fell.',
    rationale: definition.number === 1 && sequence === 1 ? 'The opening does not identify the subject or time span.' : 'The passage identifies its subject and supports the comparison.',
    hint: 'Identify the transport modes, years and measurement unit.',
  }));
  const records = structuredClone(fixtures.records);
  const busSentence = essay.match(/Bus use declined from [^.]+(?:\.\d+[^.]*)*\./)?.[0]
    || essay.slice(essay.indexOf('Bus use declined'));
  const busValue = Number(essay.match(/Bus use declined from ([\d.]+) million/)?.[1]);
  records[0] = { ...records[0], value: busValue, official_value: 1.8, student_evidence: busSentence,
    feedback_status: busValue === 1.8 ? 'correct' : 'incorrect' };
  const chartUrl = busValue === 1.8 ? '/charts/line_estimates.png' : '/charts/line_wrong_value.png';
  const revision = { id: `review-${sequence}`, task_id: 'line-test', reference_id: 'ref-test', feedback_version: '1.0', sequence,
    created_at: `2026-09-04T10:0${sequence}:00Z`, essay, assessments, chart_type: 'line', records,
    value_tolerance: 0.1, unit: 'millions', analysis_model: 'ui-fixture',
    original_url: '/practice-samples/02_line_daily_passengers.png', chart_url: chartUrl };
  return { success: true, chart_url: revision.chart_url, analysis_revision: revision,
    chart_data: { chart_type: 'line', title: fixtures.title, records, axes: { unit: 'millions' }, vega_lite_spec: fixtures.spec,
      move_feedback: { version: '1.0', assessments, summary: { attention_count: sequence === 1 ? 1 : 0 } } } };
}

(async () => {
  const browser = await chromium.launch({ headless: true, channel: process.env.BROWSER_CHANNEL || 'chrome' });
  try {
    const page = await browser.newPage({ viewport: { width: 1440, height: 1080 } });
    const errors = [], saved = [], chartIds = [], languageIds = [], coachingIds = [], events = [];
    let failAnalysis = false, failHistory = false, failGuidance = false;
    page.on('pageerror', error => errors.push(error.message));
    await page.route('**/practice-samples/**', route => route.fulfill({ path: path.join(root, 'frontend/public/practice-samples', path.basename(new URL(route.request().url()).pathname)), contentType: 'image/png' }));
    await page.route('**/charts/**', route => route.fulfill({ path: path.join(output, 'line_estimates.png'), contentType: 'image/png' }));
    await page.route('**/api/**', async route => {
      const url = new URL(route.request().url());
      const submissionId = route.request().headers()['x-vividwrite-submission'];
      let payload = { success: true };
      if (url.pathname === '/api/auth/config') payload = { password_required: false, research_enabled: true };
      if (url.pathname === '/api/auth/me') payload = { authenticated: true, username: 'ui-fixture' };
      if (url.pathname === '/api/research/events') events.push(...route.request().postDataJSON().events);
      if (url.pathname === '/api/analyze-chart-with-image') {
        assert.ok(submissionId);
        chartIds.push(submissionId);
        const form = await new Request(route.request().url(), { method: 'POST', headers: route.request().headers(), body: route.request().postDataBuffer() }).formData();
        payload = responseFor(saved.length + 1, form.get('student_answer'));
        payload.analysis_revision.submission_id = submissionId;
        if (failAnalysis) { payload = { success: false, error: 'Synthetic analysis failure' }; failAnalysis = false; }
        else if (failHistory) { payload.analysis_revision = null; payload.history_warning = 'This review could not be saved to your revision history.'; }
        else saved.unshift(payload.analysis_revision);
      }
      if (url.pathname === '/api/revision-review') {
        languageIds.push(submissionId);
        payload = { success: true, overall: null, suggestions: [] };
      }
      if (url.pathname.endsWith('/guidance')) {
        const review = saved.find(item => url.pathname.includes('/' + item.id + '/'));
        assert.ok(review);
        assert.equal(submissionId, review.submission_id);
        coachingIds.push(submissionId);
        if (failGuidance) { failGuidance = false; await route.fulfill({ status: 500, json: { detail: 'Synthetic connection failure' } }); return; }
        const improved = review.sequence === 2;
        const quote = review.essay.split('\n')[0];
        const item = { fact_ids: ['criterion:introduction'], title: improved ? 'A clear introduction' : 'Make the subject clear',
          explanation: improved ? 'You replaced a vague opening with the transport modes, years and unit, addressing the previous review.' : 'A reader needs the subject and time span before following the trends.',
          action: improved ? 'Introduce the subject and scope together in future tasks.' : 'Name the transport modes, years and measurement unit.',
          self_check: 'Can your reader tell what is measured without looking at the chart?' };
        payload = { guidance: { analysis_revision_id: review.id, source: 'ai',
          based_on: saved.filter(item => item.sequence < review.sequence).slice(0, 3).map(item => ({ id: item.id, sequence: item.sequence })),
          unchanged_since_latest: review.sequence === 3,
          summary: improved ? 'Your opening now gives the reader a clear frame for the comparison.' : 'Start with the one change that makes the report easier to follow.',
          improvements: improved ? [item] : [], priorities: improved ? [] : [item],
          facts: [{ id: 'criterion:introduction', excerpt: quote }] } };
      }
      await route.fulfill({ json: payload });
    });
    await page.goto('http://127.0.0.1:5173/');
    await page.getByLabel('Practice sample').selectOption('line-passengers');
    const editor = page.locator('.cm-content[contenteditable="true"]');
    const coaching = page.getByRole('region', { name: 'Revision guidance' });
    await editor.fill(firstEssay);
    await page.getByRole('button', { name: 'Next Stage', exact: true }).click();
    await page.getByRole('button', { name: 'Confirm', exact: true }).click();
    await page.getByRole('button', { name: 'Analyze report', exact: true }).click();
    await coaching.getByText('Focus on next', { exact: true }).waitFor();
    assert.equal(await coaching.locator('select').count(), 0);
    assert.equal(await coaching.getByText('Try this:', { exact: true }).count(), 1);
    await coaching.getByText('Passage in your report').click();
    await coaching.getByRole('button', { name: 'Show in draft', exact: true }).click();
    await page.locator('.cm-hl-yellow').first().waitFor();
    await page.getByText('How were these values inferred?').click();
    await page.getByText('Interpolated between 2010 (1.1) and 2020 (2.2)', { exact: false }).first().waitFor();
    await editor.fill(secondEssay);
    await coaching.getByText('Draft changed since Review 1.', { exact: false }).waitFor();
    assert.equal(await coaching.getByRole('button', { name: 'Show in draft', exact: true }).isDisabled(), true);
    await page.getByRole('button', { name: 'Compare again', exact: true }).click();
    await coaching.getByText('What improved', { exact: true }).waitFor();
    await coaching.getByText('Automatically informed by 1 recent draft', { exact: false }).waitFor();
    assert.equal(await coaching.locator('.revision-evidence-grid').count(), 0);
    await coaching.scrollIntoViewIfNeeded();
    await page.screenshot({ path: path.join(output, 'guidance-desktop.png'), fullPage: true });
    failGuidance = true;
    await page.getByRole('button', { name: 'Compare again', exact: true }).click();
    await coaching.getByRole('alert').waitFor();
    assert.equal(await coaching.getByText('What improved', { exact: true }).count(), 0, 'No stale coaching from the prior review');
    await coaching.getByRole('button', { name: 'Retry', exact: true }).click();
    await coaching.getByText('This draft is unchanged', { exact: false }).waitFor();
    assert.equal(await coaching.locator('select').count(), 0);
    await page.setViewportSize({ width: 390, height: 844 });
    await coaching.scrollIntoViewIfNeeded();
    await page.screenshot({ path: path.join(output, 'guidance-mobile.png'), fullPage: true });
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1), false);
    failAnalysis = true;
    await page.getByRole('button', { name: 'Compare again', exact: true }).click();
    await page.getByText('Synthetic analysis failure', { exact: true }).waitFor();
    assert.equal(saved.length, 3);
    assert.equal(await page.getByAltText('Visual interpretation generated from the report').count(), 1);
    failHistory = true;
    await page.getByRole('button', { name: 'Compare again', exact: true }).click();
    await page.getByText('This review could not be saved to your revision history.', { exact: true }).waitFor();
    await page.waitForTimeout(2700);
    assert.deepEqual(chartIds, languageIds);
    assert.equal(new Set(chartIds).size, chartIds.length);
    assert.equal(coachingIds.length, 4, 'Three reviews plus one explicitly retried request');
    assert.ok(events.some(event => event.event_type === 'revision_guidance_viewed'));
    assert.deepEqual(errors, []);
    console.log(JSON.stringify({ result: 'PASS', checks: ['automatic history guidance', 'no version selector or parallel reviews', 'action and self-check', 'traceable passage', 'stale draft protection', 'loading error and retry', 'unchanged draft', 'shared submission IDs', 'research telemetry', 'inference details', 'failed analysis preservation', 'desktop and mobile'], output }, null, 2));
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
